from app.storage import create_store
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import Settings
from app.rag import RagError, Store
from app.jobs import ImportJobs


def create_app(settings=None, store=None):
    settings = settings or Settings.load()
    store = store or create_store(settings)
    jobs = ImportJobs(store)

    @asynccontextmanager
    async def lifespan(app):
        yield
        jobs.close()

    app = FastAPI(title='OpsAtlas', docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    token = secrets.token_urlsafe(32)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', '[::1]', 'testserver'])

    @app.middleware('http')
    async def protect(request: Request, call_next):
        if request.method not in {'GET', 'HEAD', 'OPTIONS'} and not secrets.compare_digest(request.headers.get('x-local-token', ''), token):
            return JSONResponse({'detail': 'Token local invalid. Reîncarcă pagina.'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(RagError)
    async def rag_error(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        logging.getLogger(__name__).exception('Request failed')
        return JSONResponse({'detail': 'Eroare internă. Verifică terminalul aplicației.'}, status_code=500)

    @app.get('/health')
    def health():
        try:
            with store.connection() as db:
                db.execute('SELECT 1').fetchone()
            return {'status': 'ok'}
        except Exception:
            return JSONResponse({'status': 'unavailable'}, status_code=503)

    @app.get('/api/status')
    def status():
        try:
            installed = store.model.request('/api/tags').get('models', [])
            names = [m['name'] for m in installed]
            ready = all(m in names for m in [settings.chat_model, settings.embed_model])
            ollama = 'ready' if ready else 'models_missing'
        except RagError:
            ollama = 'offline'
        return {'ollama': ollama, 'chat_model': settings.chat_model, 'embed_model': settings.embed_model,
                'max_upload_mb': settings.max_upload_mb, 'max_pdf_pages': settings.max_pdf_pages,
                'max_document_chunks': settings.max_document_chunks,
                'token': token, 'storage': 'PostgreSQL + pgvector' if settings.database_backend == 'postgres' else 'SQLite local', 'aws': 'Backup opțional prin CLI'}

    @app.get('/api/documents')
    def documents():
        return store.documents()

    @app.get('/api/imports')
    def imports():
        return jobs.list()

    @app.post('/api/documents', status_code=202)
    def upload(file: UploadFile = File(...)):
        if file.size is not None and file.size > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, f'Maximum {settings.max_upload_mb} MiB per file.')
        return jobs.submit(file)

    @app.delete('/api/documents/{document_id}')
    def delete(document_id: str):
        if not store.delete(document_id):
            raise HTTPException(404, 'Document inexistent.')
        return {'deleted': True}

    class Question(BaseModel):
        question: str = Field(min_length=1, max_length=4000)
        top_k: int = Field(default=5, ge=1, le=8)

    @app.post('/api/chat')
    def chat(body: Question):
        if not body.question.strip():
            raise HTTPException(422, 'Introdu o întrebare.')
        return store.query(body.question.strip(), body.top_k)

    static = Path(__file__).parent / 'static'
    app.mount('/static', StaticFiles(directory=static), name='static')

    @app.get('/')
    def index():
        return FileResponse(static / 'index.html')

    return app
