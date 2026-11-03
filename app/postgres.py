"""PostgreSQL/pgvector storage with disk-backed import staging."""
import hashlib
import json
import math
import re
import tempfile
import threading
from dataclasses import replace
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.rag import Store, Ollama, RagError


class PostgresStore(Store):
    def __init__(self, settings, model=None):
        self.settings = settings
        self.model = model or Ollama(settings)
        self.lock = threading.RLock()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            row = db.execute("SELECT format_type(atttypid,atttypmod) AS type FROM pg_attribute WHERE attrelid='public.chunks'::regclass AND attname='embedding'").fetchone()
            if not row or row['type'] != 'vector(768)':
                raise RagError('Expected initialized pgvector schema with vector(768).')

    def connection(self):
        try:
            return psycopg.connect(self.settings.database_url, row_factory=dict_row, connect_timeout=5)
        except psycopg.Error:
            raise RagError('PostgreSQL unavailable. Check Podman, credentials and port.') from None

    def documents(self):
        with self.connection() as db:
            rows = db.execute("""SELECT d.id,d.name,d.model,
              to_char(d.created_at AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS') AS created_at,
              count(c.id) AS chunks FROM documents d LEFT JOIN chunks c ON d.id=c.document_id
              GROUP BY d.id ORDER BY d.created_at DESC""").fetchall()
        return rows

    def publish(self, document, rows):
        with self.connection() as db:
            # Serializes publication across CLI and web processes.
            db.execute('SELECT pg_advisory_xact_lock(679413)')
            existing = db.execute('SELECT model FROM documents WHERE id=%s', (document['id'],)).fetchone()
            if existing:
                if existing['model'] != document['model']:
                    raise RagError('Document indexed with another embedding model.')
                return {'id': document['id'], 'duplicate': True}
            if db.execute('SELECT 1 FROM documents WHERE model<>%s LIMIT 1', (self.settings.embed_model,)).fetchone():
                raise RagError('Embedding model mismatch. Reindex existing documents first.')
            if document['model'] != self.settings.embed_model:
                raise RagError('Source embedding model does not match EMBED_MODEL.')
            db.execute('INSERT INTO documents(id,name,model,created_at) VALUES(%s,%s,%s,%s)',
                       (document['id'],document['name'],document['model'],document['created_at']))
            count = 0
            with db.cursor() as cursor:
                for row in rows:
                    vector = json.loads(row['vector'])
                    if len(vector) != 768 or any(not math.isfinite(x) for x in vector) or not any(vector):
                        raise RagError('PostgreSQL requires finite, nonzero 768-dimensional embeddings.')
                    cursor.execute('INSERT INTO chunks(document_id,page,text,embedding) VALUES(%s,%s,%s,%s::vector)',
                                   (document['id'],row['page'],row['text'],json.dumps(vector)))
                    count += 1
            return {'id': document['id'], 'duplicate': False, 'chunks': count}

    def ingest_stream(self, filename, stream, progress=lambda **kw: None):
        checksum = hashlib.sha256()
        size = 0
        while block := stream.read(1024*1024):
            size += len(block)
            if size > self.settings.max_upload_mb * 1024*1024:
                raise RagError('File exceeds configured upload limit.')
            checksum.update(block)
        stream.seek(0)
        with self.connection() as db:
            existing = db.execute('SELECT model FROM documents WHERE id=%s', (checksum.hexdigest(),)).fetchone()
            if existing:
                if existing['model'] != self.settings.embed_model:
                    raise RagError('Document indexed with another embedding model.')
                return {'id': checksum.hexdigest(), 'duplicate': True}
        with self.lock, tempfile.TemporaryDirectory(dir=self.settings.data_dir) as temporary:
            staging = Store(replace(self.settings, data_dir=Path(temporary)), self.model)
            result = staging.ingest_stream(filename, stream, progress)
            with staging.connection() as source:
                document = source.execute('SELECT * FROM documents WHERE id=?', (result['id'],)).fetchone()
                rows = source.execute('SELECT page,text,vector FROM chunks WHERE document_id=? ORDER BY id', (result['id'],))
                return self.publish(document, rows)

    def delete(self, document_id):
        with self.connection() as db:
            return db.execute('DELETE FROM documents WHERE id=%s', (document_id,)).rowcount > 0

    def query(self, question, top_k=5):
        with self.connection() as db:
            if not db.execute('SELECT 1 FROM documents LIMIT 1').fetchone():
                return {'answer': 'Import documents into the knowledge base first.', 'sources': []}
            if db.execute('SELECT 1 FROM documents WHERE model<>%s LIMIT 1', (self.settings.embed_model,)).fetchone():
                raise RagError('Embedding model mismatch. Reindex existing documents first.')
        vector = self.model.embed([f'task: search result | query: {question}'])[0]
        if len(vector) != 768:
            raise RagError('PostgreSQL schema requires 768-dimensional embeddings.')
        with self.connection() as db:
            # Exact cosine search in PostgreSQL. No approximate-recall surprises.
            rows = db.execute("""SELECT d.id AS document_id,d.name,c.page,c.text,
              1-(c.embedding <=> %s::vector) AS score FROM chunks c
              JOIN documents d ON d.id=c.document_id
              ORDER BY c.embedding <=> %s::vector LIMIT %s""",
              (json.dumps(vector),json.dumps(vector),top_k)).fetchall()
        sources = [r for r in rows if r['score'] >= self.settings.min_score]
        if not sources:
            return {'answer': 'No sufficiently relevant excerpts were found in the imported documents.', 'sources': []}
        answer = self.model.answer(question, sources)
        citations = [int(x) for x in re.findall(r'\[(\d+)\]', answer)]
        return {'answer': answer, 'sources': sources,
                'citations_valid': bool(citations) and all(1 <= n <= len(sources) for n in citations),
                'model': self.settings.chat_model}
