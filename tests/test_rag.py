import io
import sqlite3
import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.backup import check_database, digest, restore, upload
from app.config import Settings
from app.main import create_app
from app.rag import RagError, Store, chunks


def wait_import(client, response):
    assert response.status_code == 202, response.text
    job_id = response.json()['job_id']
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        job = next(j for j in client.get('/api/imports').json() if j['id'] == job_id)
        if job['state'] in {'completed', 'failed'}:
            return job
        time.sleep(0.01)
    pytest.fail('Import timed out')


class FakeModel:
    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def answer(self, question, sources):
        return 'Folosește NetworkPolicy [1].'

    def request(self, path):
        return {'models': [{'name': 'chat:test'}, {'name': 'embed:test'}]}


@pytest.fixture
def settings(tmp_path):
    return Settings(tmp_path, 'http://127.0.0.1:11434', 'chat:test', 'embed:test', 0.35)


def test_ingest_retrieve_duplicate_and_delete(settings):
    store = Store(settings, FakeModel())
    result = store.ingest('../runbook.md', b'Use NetworkPolicy to restrict network traffic.')
    assert store.documents()[0]['name'] == 'runbook.md'
    assert store.ingest('same.md', b'Use NetworkPolicy to restrict network traffic.')['duplicate']
    answer = store.query('How do I restrict traffic?')
    assert answer['citations_valid']
    assert answer['sources'][0]['page'] == 1
    assert store.delete(result['id'])
    assert store.query('anything')['sources'] == []


def test_failed_embeddings_do_not_leave_partial_document(settings):
    class Broken(FakeModel):
        def embed(self, texts):
            raise RagError('unavailable')
    store = Store(settings, Broken())
    with pytest.raises(RagError):
        store.ingest('test.txt', b'example')
    assert store.documents() == []


def test_model_change_requires_reindex(settings):
    store = Store(settings, FakeModel())
    store.ingest('test.txt', b'example')
    other = Settings(settings.data_dir, settings.ollama_url, settings.chat_model, 'other:model', 0.35)
    with pytest.raises(RagError, match='schimbat'):
        Store(other, FakeModel()).query('example')


def test_low_similarity_never_calls_generator(settings):
    class NoMatch(FakeModel):
        def embed(self, texts):
            return [[0.0, 1.0] for _ in texts]
        def answer(self, *args):
            pytest.fail('Generator must not run without matching sources')
    store = Store(settings, FakeModel())
    store.ingest('test.txt', b'example')
    store.model = NoMatch()
    assert store.query('unrelated')['sources'] == []


def test_api_requires_token_and_handles_upload(settings):
    client = TestClient(create_app(settings, Store(settings, FakeModel())))
    assert client.post('/api/chat', json={'question': 'hi'}).status_code == 403
    token = client.get('/api/status').json()['token']
    headers = {'X-Local-Token': token}
    response = client.post('/api/documents', headers=headers, files={'file': ('note.md', b'NetworkPolicy restricts traffic.')})
    assert wait_import(client, response)['state'] == 'completed'
    response = client.post('/api/chat', headers=headers, json={'question': 'traffic?'})
    assert response.status_code == 200
    assert response.json()['sources']
    assert client.post('/api/chat', headers=headers, json={'question': ' '}).status_code == 422
    assert client.post('/api/documents', headers=headers, files={'file': ('bad.exe', b'bad')}).status_code == 422
    assert "script-src 'self'" in client.get('/').headers['content-security-policy']
    assert client.get('/', headers={'Host': 'evil.example'}).status_code == 400


def test_upload_larger_than_twenty_mib(settings):
    with TestClient(create_app(settings, Store(settings, FakeModel()))) as client:
        headers = {'X-Local-Token': client.get('/api/status').json()['token']}
        # Large UTF-8 file with little text, independent of GPU performance.
        content = b' ' * (21 * 1024 * 1024) + b'NetworkPolicy restricts traffic.'
        response = client.post('/api/documents', headers=headers, files={'file': ('large.txt', content)})
        job = wait_import(client, response)
        assert job['state'] == 'completed', job
        assert job['chunks_done'] > 0
        assert client.get('/api/documents').json()[0]['name'] == 'large.txt'


def test_configured_upload_limit_enforced(settings):
    limited = replace(settings, max_upload_mb=1)
    with TestClient(create_app(limited, Store(limited, FakeModel()))) as client:
        status = client.get('/api/status').json()
        assert status['max_upload_mb'] == 1
        response = client.post('/api/documents', headers={'X-Local-Token': status['token']},
                               files={'file': ('large.txt', b'x' * (1024 * 1024 + 1))})
        assert response.status_code == 413
        assert client.get('/api/imports').json() == []


def test_background_failure_is_reported_without_partial_index(settings):
    limited = replace(settings, max_document_chunks=17)
    store = Store(limited, FakeModel())
    with TestClient(create_app(limited, store)) as client:
        headers = {'X-Local-Token': client.get('/api/status').json()['token']}
        response = client.post('/api/documents', headers=headers, files={'file': ('too-many.txt', b'x' * 30000)})
        job = wait_import(client, response)
        assert job['state'] == 'failed'
        assert '17' in job['error']
        assert job['chunks_done'] == 16
        assert store.documents() == []
        assert not list(settings.data_dir.glob('tmp*'))


def test_only_one_active_import(settings):
    import threading
    started, release = threading.Event(), threading.Event()
    class Slow(FakeModel):
        def embed(self, texts):
            started.set()
            assert release.wait(5)
            return super().embed(texts)
    store = Store(settings, Slow())
    with TestClient(create_app(settings, store)) as client:
        headers = {'X-Local-Token': client.get('/api/status').json()['token']}
        response = client.post('/api/documents', headers=headers, files={'file': ('first.txt', b'text')})
        try:
            assert started.wait(5)
            assert client.get('/api/documents').json() == []
            rejected = client.post('/api/documents', headers=headers, files={'file': ('second.txt', b'other')})
            assert rejected.status_code == 422
        finally:
            release.set()
        assert wait_import(client, response)['state'] == 'completed'


def test_config_rejects_nonpositive_limits(settings):
    with pytest.raises(ValueError):
        replace(settings, max_upload_mb=0)


def test_pdf_page_limit_is_configurable(settings):
    from pypdf import PdfWriter
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_blank_page(width=100, height=100)
    writer.write(output)
    store = Store(replace(settings, max_pdf_pages=1), FakeModel())
    with pytest.raises(RagError, match='Maximum 1 pages'):
        store.ingest('two-pages.pdf', output.getvalue())
    assert store.documents() == []


def test_streaming_batches_are_bounded(settings):
    class BoundedStream(io.BytesIO):
        def read(self, size=-1):
            assert 0 < size <= 1024 * 1024
            return super().read(size)
    class BoundedModel(FakeModel):
        def embed(self, texts):
            assert len(texts) <= 16
            return super().embed(texts)
    store = Store(settings, BoundedModel())
    progress = []
    result = store.ingest_stream('utf8.md', BoundedStream(('rețea ' * 15000).encode()),
                                 lambda **kw: progress.append(kw))
    assert result['chunks'] > 16
    assert progress[-1] == {'phase': 'saving'}
    assert store.documents()[0]['chunks'] == result['chunks']


class FakeBody(io.BytesIO):
    def iter_chunks(self, chunk_size):
        while block := self.read(chunk_size):
            yield block


class FakeS3:
    def upload_file(self, path, bucket, key, ExtraArgs):
        self.content = open(path, 'rb').read()
        self.key, self.extra = key, ExtraArgs
    def head_object(self, **kwargs):
        return {'Metadata': self.extra['Metadata'], 'ContentLength': len(self.content), 'ETag': 'test'}
    def get_object(self, **kwargs):
        return {'Body': FakeBody(self.content)}


def test_backup_restore_roundtrip_and_refuses_overwrite(settings, tmp_path):
    store = Store(settings, FakeModel())
    store.ingest('test.txt', b'important document')
    client = FakeS3()
    upload(settings, client, 'bucket', 'rag/')
    assert client.extra['ServerSideEncryption'] == 'AES256'
    destination = Settings(tmp_path / 'restored', settings.ollama_url, settings.chat_model, settings.embed_model, .35)
    restore(destination, client, 'bucket', 'rag/', client.key)
    check_database(destination.data_dir / 'knowledge.sqlite3')
    assert Store(destination, FakeModel()).documents()[0]['name'] == 'test.txt'
    with pytest.raises(ValueError, match='nou'):
        restore(destination, client, 'bucket', 'rag/', client.key)


def test_restore_rejects_corrupt_download(settings, tmp_path):
    Store(settings, FakeModel()).ingest('test.txt', b'example')
    client = FakeS3()
    upload(settings, client, 'bucket', 'rag/')
    client.content += b'tampered'
    destination = Settings(tmp_path / 'bad', settings.ollama_url, settings.chat_model, settings.embed_model, .35)
    with pytest.raises(ValueError, match='Checksum'):
        restore(destination, client, 'bucket', 'rag/', client.key)
    assert not (destination.data_dir / 'knowledge.sqlite3').exists()


def test_chunking_and_invalid_files(settings):
    assert list(chunks('abc')) == ['abc']
    store = Store(settings, FakeModel())
    for name, content in [('empty.txt', b''), ('scan.pdf', b'not a pdf'), ('wrong.txt', b'\xff')]:
        with pytest.raises(RagError):
            store.ingest(name, content)
