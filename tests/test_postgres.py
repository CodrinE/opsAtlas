import io
import os
import uuid
from dataclasses import replace

import pytest

from app.config import Settings
from app.postgres import PostgresStore
from app.storage import create_store
from app.rag import Store, RagError
from scripts.migrate_postgres import migrate


def test_backend_settings_validation(tmp_path):
    settings = Settings(tmp_path,'http://127.0.0.1:11434','chat','embed',.35)
    assert isinstance(create_store(settings),Store)
    with pytest.raises(ValueError):
        replace(settings,database_backend='invalid')
    with pytest.raises(ValueError):
        replace(settings,database_backend='postgres')
    secret = replace(settings,database_backend='postgres',database_url='postgresql://secret')
    assert 'postgresql://secret' not in repr(secret)


def test_migration_preserves_source_and_skips_duplicates(tmp_path):
    settings = Settings(tmp_path,'http://127.0.0.1:11434','chat','embed',.35)
    class Model:
        def embed(self,texts):
            return [[1.,0.] for _ in texts]
    source = Store(settings,Model())
    source.ingest('sample.txt',b'example')
    class Target:
        seen = set()
        def publish(self,doc,rows):
            assert list(rows)[0]['text'] == 'example'
            duplicate = doc['id'] in self.seen
            self.seen.add(doc['id'])
            return {'duplicate':duplicate}
    target = Target()
    assert migrate(source.path,target)['imported'] == 1
    assert migrate(source.path,target)['duplicates'] == 1
    assert source.documents()[0]['name'] == 'sample.txt'


@pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1',reason='Requires initialized local PostgreSQL container')
def test_real_postgres_import_retrieval_and_delete(tmp_path):
    class Model:
        def embed(self,texts):
            return [[1.] + [0.]*767 for _ in texts]
        def answer(self,question,sources):
            return 'Evidence [1].'
    settings = replace(Settings.load(),data_dir=tmp_path,database_backend='postgres')
    store = PostgresStore(settings,Model())
    content = ('Unique test '+str(uuid.uuid4())).encode()
    result = store.ingest('test-only.txt',content)
    try:
        assert store.ingest('duplicate.txt',content)['duplicate']
        assert any(d['id'] == result['id'] for d in store.documents())
        assert store.query('test')['sources']
    finally:
        store.delete(result['id'])
