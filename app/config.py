import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    ollama_url: str
    chat_model: str
    embed_model: str
    min_score: float
    max_upload_mb: int = 100
    max_pdf_pages: int = 5000
    max_document_chunks: int = 30000

    database_backend: str = 'sqlite'
    database_url: str = field(default='', repr=False)

    def __post_init__(self):
        if self.database_backend not in {'sqlite', 'postgres'}:
            raise ValueError('DATABASE_BACKEND must be sqlite or postgres')
        if self.database_backend == 'postgres' and not self.database_url:
            raise ValueError('DATABASE_URL is required for postgres')

        for name in ('max_upload_mb', 'max_pdf_pages', 'max_document_chunks'):
            if getattr(self, name) < 1:
                raise ValueError(f'{name} must be positive')

    @classmethod
    def load(cls):
        load_dotenv()
        url = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
        parsed = urlparse(url)
        if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1', 'host.containers.internal', 'host.docker.internal'} or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError('OLLAMA_URL must be a local HTTP origin or a container host gateway')
        score = float(os.getenv('MIN_SCORE', '0.35'))
        if not -1 <= score <= 1:
            raise ValueError('MIN_SCORE must be between -1 and 1')
        return cls(Path(os.getenv('DATA_DIR', './data')).resolve(), url,
                   os.getenv('CHAT_MODEL', 'qwen3:14b'),
                   os.getenv('EMBED_MODEL', 'embeddinggemma:300m'), score,
                   int(os.getenv('MAX_UPLOAD_MB', '100')),
                   int(os.getenv('MAX_PDF_PAGES', '5000')),
                   int(os.getenv('MAX_DOCUMENT_CHUNKS', '30000')),
                   os.getenv('DATABASE_BACKEND', 'sqlite'), os.getenv('DATABASE_URL', ''))
