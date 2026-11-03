# OpsAtlas - Local RAG assistant with optional cloud backup

OpsAtlas is a Python application inspired by [rag-devops-assistant](https://github.com/sainathmitalakar/rag-devops-assistant). It imports PDF, Markdown and TXT documents, generates embeddings through local Ollama models, and answers questions with cited excerpts. It does not execute generated commands or send questions to external AI APIs.

The application supports SQLite and PostgreSQL with pgvector. The default installation uses SQLite; the Compose deployment uses PostgreSQL. AWS S3 backup is optional and currently supports SQLite only.

## Run with Podman Compose

Requirements: a running Podman machine, Python 3.12+ for local setup tools, and [Ollama](https://ollama.com/download) running on Windows.

For a new checkout, create the virtual environment and configuration first:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r requirements-containers.txt
Copy-Item .env.example .env
ollama pull qwen3:14b
ollama pull embeddinggemma:300m
.\.venv\Scripts\python.exe -m scripts.configure_postgres
```

Do not overwrite an existing `.env`: it contains the database credentials and your model settings. You can use an installed chat model by setting `CHAT_MODEL` to its exact name from `ollama list`. The local checkout was tested with `qwen2.5:7b`.

Build the application locally and start both containers:

```powershell
$env:PATH = "$env:LOCALAPPDATA/Programs/Podman;" + $env:PATH
$env:PODMAN_COMPOSE_PROVIDER = (Resolve-Path .venv/Scripts/podman-compose.exe).Path
podman compose up -d --build
```

Open **http://127.0.0.1:8080**. Use `--build` after source changes; starting without it may reuse the previous image. Ollama stays on Windows and uses the host GPU. The application connects through `host.containers.internal`.

The application runs as an unprivileged user with a read-only root filesystem and dropped Linux capabilities. Credentials, documents, databases, backups and Git history are excluded from the image build context.

Useful commands:

```powershell
podman compose logs -f app
podman compose stop
podman compose up -d
```

The named volumes `opsatlas_pgdata` and `opsatlas_appdata` preserve database data and application staging storage. Stopping containers or running `compose down` preserves these volumes. Removing volumes, using `down -v`, or resetting the Podman machine can delete their data. A volume is not a backup.

See [PostgreSQL and Podman operations](infra/postgres/README.md) for connection settings, migration, backups, restoration and troubleshooting. Docker Desktop is not required.

## Run directly on Windows

For a new installation without containers:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
ollama pull qwen3:14b
ollama pull embeddinggemma:300m
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. Ollama must be running through its desktop application or `ollama serve`. Preserve any existing `.env` instead of copying over it. An existing PostgreSQL configuration also works when running the application directly.

In Git Bash, use `./.venv/Scripts/python.exe`. Activating the virtual environment is optional. If Windows reports `No such file or directory` when writing under Documents, check Windows Security Protection history for Controlled folder access blocks, or use a development directory outside Documents.

Downloading packages and models requires internet access. Once installed, application inference is local and the interface uses no external fonts or CDNs. Ollama may perform its own update checks; enforce system-level egress rules if a completely isolated workstation is required.

You may rename the project directory to `opsatlas`. Stop the server and close project terminals first, reopen the renamed folder in your IDE, and recreate `.venv` because Python virtual environments are not portable. Update any absolute paths in `.env`. Local documents, databases, backups and `.env` are excluded from Git.

## Usage and limits

The interface supports Romanian and English, with the selected language saved in the browser. Changing the interface language does not translate documents or existing answers. The model answers in the language of the question. Ollama status is checked automatically at approximately five-second intervals; the application healthcheck separately checks database connectivity.

- Default per-document limits: **100 MiB, 5,000 PDF pages and 30,000 chunks**. Scanned PDFs require separate OCR.
- Configure limits using `MAX_UPLOAD_MB`, `MAX_PDF_PAGES` and `MAX_DOCUMENT_CHUNKS` in `.env`, then restart or recreate the application. MiB means 1,024 x 1,024 bytes. The interface reads the upload limit from the backend.
- Uploads return HTTP 202 and a `job_id`. Progress and errors are available at `GET /api/imports`. The interface displays indexed chunks and PDF pages read, rather than an overall completion percentage.
- One import runs at a time per application process. Multiple selected files are submitted sequentially by the browser. Run a single web worker and avoid simultaneous CLI imports and web uploads.
- Chat remains available during indexing. Reloading the page restores visible job progress while the server process remains running.
- The last 100 import states are kept in process memory. Restarting the server loses unfinished job progress; resubmit unfinished imports. Completed documents remain in the configured database. Normal shutdown waits for the active import. Files selected but not yet submitted must be selected again after a page reload.
- Uploads and intermediate indexes use temporary disk storage. Embeddings are generated in batches of 16, and documents become visible only after atomic publication. Text is read in blocks and PDFs page by page, but complex or decompressed PDF pages may still consume substantial memory. File size is not a strict memory bound.
- Keep enough free disk space for uploaded files, staging indexes and the final database. A forced shutdown may leave temporary `tmp*` directories in `DATA_DIR`; inspect and remove them only while the server is stopped.
- Identical documents are deduplicated by SHA-256. Failed imports do not leave partially indexed documents.
- Questions are independent. Conversation history is retained only until the page reloads and is not sent to the model.
- Sources include the document name, page and excerpt. Similarity scores are not probabilities of correctness. Calibrate `MIN_SCORE` using relevant questions and questions with no answer in the corpus.
- Citation identifiers are checked, but claim accuracy is not. Models may generate incorrect answers, cite the wrong passage or follow malicious document content despite defensive instructions. Verify sources before operational changes.
- SQLite stores extracted text, metadata and embeddings in `data/knowledge.sqlite3`. PostgreSQL stores them in its database. Original files are not archived by database backups.
- Deleting a document removes it from the active index, not existing backups or necessarily the underlying free disk space.
- Reindex documents when changing the embedding model, including updates under the same model tag. Record model digests from `ollama list` for reproducibility.
- SQLite performs exact vector search in the application and suits small or medium local libraries. PostgreSQL performs exact cosine search through pgvector; approximate HNSW indexing is not currently enabled. The supplied PostgreSQL schema requires 768-dimensional embeddings.

## Import documents from docs/

Place PDF, Markdown or TXT files under `docs/`, including subdirectories. Preview the file list without indexing or contacting Ollama:

```powershell
.\.venv\Scripts\python.exe -m scripts.import_docs --dry-run
```

Start Ollama and stop the directly running web server before a CLI import:

```powershell
.\.venv\Scripts\python.exe -m scripts.import_docs
```

For the container deployment, with no concurrent web uploads:

```powershell
podman compose exec app python -m scripts.import_docs
```

The container mounts `docs/` read-only, so adding source documents does not require rebuilding the image.

Use `--path "C:/path/to/documents"` to select another directory when running locally. The same configured limits apply. The command reports progress, continues after individual file errors, and exits with code 1 if any file fails. Hidden files and directories, symbolic links and junctions within the directory tree are skipped.

Duplicate content is skipped by SHA-256. Changed files become new documents; previous versions are not automatically removed. Delete obsolete versions explicitly in the interface. Source labels use filenames, so use distinctive names for different documents in separate subdirectories. There is no automatic directory watcher or synchronization.

Original files remain under `docs/` and are excluded from Git. Refresh the interface after importing.

## PostgreSQL migration and backups

Generate credentials once with `scripts.configure_postgres`, start PostgreSQL, and check connectivity:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_postgres
```

Copy existing SQLite documents and embeddings without deleting the source:

```powershell
.\.venv\Scripts\python.exe -m scripts.migrate_postgres
```

Run migration without concurrent imports. It commits per document and skips duplicates, so an interrupted migration can be rerun. Keep SQLite until you verify document counts and answers.

Create a local PostgreSQL backup:

```powershell
.\.venv\Scripts\python.exe -m scripts.postgres_backup backup
```

Restore a trusted backup into an empty initialized PostgreSQL database, with the application stopped:

```powershell
.\.venv\Scripts\python.exe -m scripts.postgres_backup restore --file backups/NAME.dump
```

These are data-only archives for the supplied schema, not backups of credentials, original documents or models. Use `--runtime` to specify the Podman executable if it is not on PATH. PostgreSQL uploads to S3 are not implemented. See the [operations guide](infra/postgres/README.md) for persistence, credentials and restoration details.

## Optional AWS S3 backup for SQLite

The default is `S3_ENABLED=false`. The web server makes no AWS requests. Only the explicit command below uploads a database snapshot: **document text and embeddings leave your computer**. Models and questions are not included. This command refuses to run when the selected backend is PostgreSQL.

1. Use a private bucket with Block Public Access, versioning and encryption enabled. Configure retention and lifecycle rules appropriate to your data. The application does not create or modify the bucket.
2. Prefer AWS CLI SSO and temporary credentials: `aws sso login --profile personal`. The SDK uses its standard credential chain; do not put credentials in source code.
3. Configure `.env` for the SQLite backend:

```dotenv
DATABASE_BACKEND=sqlite
S3_ENABLED=true
S3_BUCKET=your-bucket-name
S3_PREFIX=devops-rag/backups/
AWS_PROFILE=personal
AWS_DEFAULT_REGION=eu-central-1
```

Upload a consistent SQLite snapshot with SHA-256 metadata:

```powershell
.\.venv\Scripts\python.exe -m app.backup upload
```

The command prints the object key. To restore, stop the server, set `DATA_DIR=./data-restored` to a new location, and run:

```powershell
.\.venv\Scripts\python.exe -m app.backup restore --key devops-rag/backups/PRINTED-KEY.sqlite3
```

Restoration refuses to overwrite an existing database and checks SHA-256, SQLite integrity and the basic schema. The backup limit is 512 MiB. The checksum detects corruption but does not authenticate an object changed by someone with bucket write access. Restore only trusted backups. Restart with the restored `DATA_DIR` and the original embedding model. Archive original PDFs and Ollama models separately if complete recovery is required.

Minimum prefix-scoped IAM policy; replace the bucket name and match your configured prefix:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:GetObject", "s3:AbortMultipartUpload"],
    "Resource": "arn:aws:s3:::YOUR-BUCKET/devops-rag/backups/*"
  }]
}
```

Bucket administration and deletion permissions are not needed. For SSE-KMS, set `S3_KMS_KEY_ID` and separately configure `kms:GenerateDataKey` and `kms:Decrypt`, restricted to the intended key and role. Snapshots use SSE-S3 by default, or SSE-KMS when configured. Protect local disks with BitLocker and appropriate Windows permissions.

## Security and operations

This application is intended for one local user. Direct execution should bind only to `127.0.0.1`; Compose publishes the web and database ports only on host loopback. Inside its container, the application listens on all container interfaces.

Host validation, write-operation tokens, restrictive CSP, no permissive CORS and plain-text rendering provide basic protections. They do not replace authentication: local processes that can access the port can obtain a token. Do not expose this deployment directly to a LAN or the internet.

An enterprise deployment requires OIDC, document-level authorization before retrieval, audit logs, global request limits, isolated PDF processing, RAG evaluations, dependencies locked with hashes, an SBOM, and documented vulnerability handling and update processes. Current dependency ranges are development requirements, not a production lockfile. This application does not constitute CRA certification.

## Verification

Run automated tests without GPU or AWS access:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Run the optional PostgreSQL integration test against the initialized local database:

```powershell
$env:RUN_POSTGRES_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/test_postgres.py -q
```

This inserts and deletes a uniquely identified test document. Do not point it at a shared production database.

Check real Ollama ingestion, retrieval and generation using a temporary SQLite corpus:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_local
```

References: [Ollama embeddings](https://docs.ollama.com/api/embed), [Ollama chat](https://docs.ollama.com/api/chat), [Boto3 uploads](https://docs.aws.amazon.com/boto3/latest/guide/s3-uploading-files.html).
