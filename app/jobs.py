import logging
import secrets
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.rag import RagError


class ImportJobs:
    """One active import per process; bounded history, disk-backed staging."""
    def __init__(self, store):
        self.store = store
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='document-import')
        self.lock = threading.Lock()
        self.slot = threading.BoundedSemaphore(1)
        self.jobs = {}

    def list(self):
        with self.lock:
            return [dict(job) for job in self.jobs.values()]

    def update(self, job_id, **changes):
        with self.lock:
            self.jobs[job_id].update(changes)

    def submit(self, file):
        if not self.slot.acquire(blocking=False):
            raise RagError('An import is already running. Wait for it to finish.')
        temporary = None
        try:
            temporary = tempfile.TemporaryDirectory(dir=self.store.settings.data_dir)
            path = Path(temporary.name) / 'upload'
            size = 0
            with path.open('wb') as output:
                while block := file.file.read(1024 * 1024):
                    size += len(block)
                    if size > self.store.settings.max_upload_mb * 1024 * 1024:
                        raise RagError(f'Maximum {self.store.settings.max_upload_mb} MiB per file.')
                    output.write(block)
            if not size:
                raise RagError('Empty file.')
            name = (file.filename or '').replace('\\', '/').split('/')[-1][:180]
            if name.rsplit('.', 1)[-1].lower() not in {'pdf', 'txt', 'md'}:
                raise RagError('Only PDF, Markdown and TXT are supported.')
            job_id = secrets.token_hex(16)
            with self.lock:
                while len(self.jobs) >= 100:
                    self.jobs.pop(next(iter(self.jobs)))
                self.jobs[job_id] = {'id': job_id, 'name': name, 'state': 'queued', 'phase': 'indexing',
                                     'chunks_done': 0, 'pages_done': 0, 'pages_total': None}
            self.executor.submit(self.run, job_id, name, path, temporary)
            return {'job_id': job_id}
        except Exception:
            if temporary:
                temporary.cleanup()
            self.slot.release()
            raise

    def run(self, job_id, name, path, temporary):
        try:
            self.update(job_id, state='running')
            with path.open('rb') as stream:
                result = self.store.ingest_stream(name, stream, lambda **kw: self.update(job_id, **kw))
            outcome = {'state': 'completed', 'result': result}
        except RagError as exc:
            outcome = {'state': 'failed', 'error': str(exc)}
        except Exception:
            logging.getLogger(__name__).exception('Document import failed')
            outcome = {'state': 'failed', 'error': 'Internal error. Check the application terminal.'}
        finally:
            try:
                temporary.cleanup()
            finally:
                self.slot.release()
                self.update(job_id, **outcome)

    def close(self):
        self.executor.shutdown(wait=True)
