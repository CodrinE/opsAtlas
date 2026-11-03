from types import SimpleNamespace
from scripts.import_docs import import_directory

class FakeStore:
    settings = SimpleNamespace(max_upload_mb=1)
    def __init__(self):
        self.seen = set()
    def ingest_stream(self, name, stream, progress):
        content = stream.read()
        if content == b'bad':
            raise ValueError('invalid document')
        duplicate = content in self.seen
        self.seen.add(content)
        progress(chunks_done=1)
        return {'duplicate': duplicate}

def test_recursive_duplicates_and_errors(tmp_path):
    (tmp_path/'nested').mkdir()
    (tmp_path/'a.txt').write_bytes(b'valid')
    (tmp_path/'nested'/'copy.MD').write_bytes(b'valid')
    (tmp_path/'bad.pdf').write_bytes(b'bad')
    (tmp_path/'ignore.exe').write_bytes(b'ignore')
    (tmp_path/'.hidden.txt').write_bytes(b'hidden')
    result = import_directory(tmp_path, FakeStore(), report=lambda _: None)
    assert result == dict(found=3, imported=1, duplicates=1, failed=1)

def test_dry_run(tmp_path):
    (tmp_path/'a.md').write_bytes(b'text')
    assert import_directory(tmp_path, dry_run=True, report=lambda _: None)['found'] == 1

def test_size_limit(tmp_path):
    (tmp_path/'large.txt').write_bytes(b'x'*(1024*1024+1))
    store = FakeStore()
    assert import_directory(tmp_path, store, report=lambda _: None)['failed'] == 1
    assert not store.seen
