# OpsAtlas - Local RAG assistant with optional cloud backup

OpsAtlas is a Python application inspired by [rag-devops-assistant](https://github.com/sainathmitalakar/rag-devops-assistant). It imports PDF, Markdown and TXT documents, generates embeddings through local Ollama models, and answers questions with cited excerpts. It does not execute generated commands or send questions to external AI APIs.

The application supports SQLite and PostgreSQL with pgvector. The default installation uses SQLite; the Compose deployment uses PostgreSQL. AWS S3 backup is optional and currently supports SQLite only.

## Run with Podman Compose

Requirements: Python 3.12+, [Ollama](https://ollama.com/download) running on the host, and a working Podman engine with a Compose provider. Windows uses a running Podman machine; Linux can run Podman natively.

Expand the Windows or Linux command section for your platform. GitHub README files do not support interactive tabs, so these sections use collapsible panels.

For a new checkout, create the virtual environment and configuration first:

<details>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r requirements-containers.txt
Copy-Item .env.example .env
ollama pull qwen3:14b
ollama pull embeddinggemma:300m
.\.venv\Scripts\python.exe -m cli.configure_postgres
```

</details>

<details>
<summary><strong>Linux (Bash)</strong></summary>

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-dev.txt -r requirements-containers.txt
cp -n .env.example .env
ollama pull qwen3:14b
ollama pull embeddinggemma:300m
./.venv/bin/python -m cli.configure_postgres
```

</details>

Do not overwrite an existing `.env`: it contains the database credentials and your model settings. You can use an installed chat model by setting `CHAT_MODEL` to its exact name from `ollama list`. The local checkout was tested with `qwen2.5:7b`.

For automatic Podman and Compose discovery, use the [start and stop scripts](#start-and-stop-scripts). To configure the environment manually and build both services:

<details>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
$env:PATH = "$env:LOCALAPPDATA/Programs/Podman;" + $env:PATH
$env:PODMAN_COMPOSE_PROVIDER = (Resolve-Path .venv/Scripts/podman-compose.exe).Path
podman compose up -d --build
```

</details>

<details>
<summary><strong>Linux (Bash)</strong></summary>

```bash
export PODMAN_COMPOSE_PROVIDER="$PWD/.venv/bin/podman-compose"
podman compose up -d --build
```

</details>

Open **http://127.0.0.1:8080**. Use `--build` after source changes; starting without it may reuse the previous image. Ollama stays on the host and uses its configured compute device. The application connects through `host.containers.internal`.

On Linux, ensure the host Ollama service is reachable through `host.containers.internal`; host loopback reachability depends on the Podman network configuration. Keep any changed Ollama listener restricted by the host firewall. On SELinux-enforcing hosts, bind mounts may need an appropriate label such as `:ro,Z` for project-owned directories; review labeling before changing shared system directories. Linux commands are documented here but were not executed in this Windows workspace.

The application runs as an unprivileged user with a read-only root filesystem and dropped Linux capabilities. Credentials, documents, databases, backups and Git history are excluded from the image build context.

Useful commands:

**Windows / Linux**

```bash
podman compose logs -f app
podman compose stop
podman compose up -d
```

The named volumes `opsatlas_pgdata` and `opsatlas_appdata` preserve database data and application staging storage. Stopping containers or running `compose down` preserves these volumes. Removing volumes, using `down -v`, or resetting the Podman machine can delete their data. A volume is not a backup.

See [PostgreSQL and Podman operations](infra/postgres/README.md) for connection settings, migration, backups, restoration and troubleshooting. Docker Desktop is not required.

## Run directly on Windows or Linux

For a new installation without containers:

<details>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
ollama pull qwen3:14b
ollama pull embeddinggemma:300m
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

</details>

<details>
<summary><strong>Linux (Bash)</strong></summary>

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
cp -n .env.example .env
ollama pull qwen3:14b
ollama pull embeddinggemma:300m
./.venv/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

</details>

Open **http://127.0.0.1:8000**. Ollama must be running through its desktop application or `ollama serve`. Preserve any existing `.env` instead of copying over it. An existing PostgreSQL configuration also works when running the application directly.

On Linux, install the Python venv package provided by your distribution if virtual environment creation fails. The commands use the virtual environment interpreter directly, so activation is optional.

In Git Bash on Windows, use `./.venv/Scripts/python.exe`. Activating the virtual environment is optional. If Windows reports `No such file or directory` when writing under Documents, check Windows Security Protection history for Controlled folder access blocks, or use a development directory outside Documents.

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

**Windows / Linux**

```bash
./.venv/bin/python -m cli.import_docs --dry-run
```

Start Ollama and stop the directly running web server before a CLI import:

**Windows / Linux**

```bash
./.venv/bin/python -m cli.import_docs
```

For the container deployment, with no concurrent web uploads:

**Windows / Linux**

```bash
podman compose exec app python -m cli.import_docs
```

The container mounts `docs/` read-only, so adding source documents does not require rebuilding the image.

Use `--path "C:/path/to/documents"` on Windows or `--path "/path/to/documents"` on Linux to select another directory when running locally. The same configured limits apply. The command reports progress, continues after individual file errors, and exits with code 1 if any file fails. Hidden files and directories, symbolic links and junctions within the directory tree are skipped.

Duplicate content is skipped by SHA-256. Changed files become new documents; previous versions are not automatically removed. Delete obsolete versions explicitly in the interface. Source labels use filenames, so use distinctive names for different documents in separate subdirectories. There is no automatic directory watcher or synchronization.

Original files remain under `docs/` and are excluded from Git. Refresh the interface after importing.

## PostgreSQL migration and backups

Generate credentials once with `cli.configure_postgres`, start PostgreSQL, and check connectivity:

**Windows / Linux**

```bash
./.venv/bin/python -m cli.check_postgres
```

Copy existing SQLite documents and embeddings without deleting the source:

**Windows / Linux**

```bash
./.venv/bin/python -m cli.migrate_postgres
```

Run migration without concurrent imports. It commits per document and skips duplicates, so an interrupted migration can be rerun. Keep SQLite until you verify document counts and answers.

Create a local PostgreSQL backup:

**Windows / Linux**

```bash
./.venv/bin/python -m cli.postgres_backup backup
```

Restore a trusted backup into an empty initialized PostgreSQL database, with the application stopped:

**Windows / Linux**

```bash
./.venv/bin/python -m cli.postgres_backup restore --file backups/NAME.dump
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

**Windows / Linux**

```bash
./.venv/bin/python -m app.backup upload
```

The command prints the object key. To restore, stop the server, set `DATA_DIR=./data-restored` to a new location, and run:

**Windows / Linux**

```bash
./.venv/bin/python -m app.backup restore --key devops-rag/backups/PRINTED-KEY.sqlite3
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

**Windows / Linux**

```bash
./.venv/bin/python -m pip install -r requirements-dev.txt
./.venv/bin/python -m pytest -q
```

Run the optional PostgreSQL integration test against the initialized local database:

<details>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
$env:RUN_POSTGRES_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/test_postgres.py -q
```

</details>

<details>
<summary><strong>Linux (Bash)</strong></summary>

```bash
export RUN_POSTGRES_TESTS=1
./.venv/bin/python -m pytest tests/test_postgres.py -q
```

</details>

This inserts and deletes a uniquely identified test document. Do not point it at a shared production database.

Check real Ollama ingestion, retrieval and generation using a temporary SQLite corpus:

**Windows / Linux**

```bash
./.venv/bin/python -m cli.verify_local
```

References: [Ollama embeddings](https://docs.ollama.com/api/embed), [Ollama chat](https://docs.ollama.com/api/chat), [Boto3 uploads](https://docs.aws.amazon.com/boto3/latest/guide/s3-uploading-files.html).

## Start and stop scripts

The scripts automatically locate Podman, set the Compose provider and run from the project root.
Environment changes apply only to the launched process; no manual exports or permanent PATH changes are needed.
They require an existing .env, configured PostgreSQL credentials, a running Podman engine,
and Compose tooling installed with requirements-containers.txt. They never install software or regenerate credentials.

<details>
<summary><strong>Windows (Git Bash) / Linux (Bash)</strong></summary>

```bash
bash scripts/start.sh
bash scripts/stop.sh
```

</details>

<details>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
.\scripts\start.ps1
.\scripts\stop.ps1
```

If your PowerShell execution policy blocks scripts, use the Python launcher instead of changing system policy:

```powershell
.\.venv\Scripts\python.exe -m cli.compose start
.\.venv\Scripts\python.exe -m cli.compose stop
```

</details>

Start runs `podman compose up -d --build`. Stop runs `podman compose stop`,
preserving containers, networks and named volumes. Neither script stops Ollama or the Podman machine.
To verify tooling without starting or stopping containers, append `--check` to either script.
The default web address is http://127.0.0.1:8080; an APP_PORT override takes precedence.


### Shell wrappers and Python commands

`scripts/` contains only shell entry points. The shared Python launcher and other
command-line utilities live in the `cli/` package. Older commands using
`python -m scripts.<command>` must now use `python -m cli.<command>`.

| Task | Python module |
| --- | --- |
| Start or stop Compose | `cli.compose start` / `cli.compose stop` |
| Generate local PostgreSQL configuration | `cli.configure_postgres` |
| Check PostgreSQL connectivity | `cli.check_postgres` |
| Import local documents | `cli.import_docs` |
| Migrate SQLite documents to PostgreSQL | `cli.migrate_postgres` |
| Back up or restore PostgreSQL data | `cli.postgres_backup backup` / `cli.postgres_backup restore` |
| Verify local Ollama ingestion and answers | `cli.verify_local` |

Run modules from the repository root with the virtual environment interpreter:
`./.venv/bin/python -m <module>` on Linux, or
`.\\.venv\\Scripts\\python.exe -m <module>` in Windows PowerShell.
The shell wrappers locate the repository automatically and can also be called by absolute path.

## Repository layout

- `app/`: API, retrieval, storage and web interface.
- `cli/`: Python command-line utilities, invoked with `python -m cli.<command>`.
- `scripts/`: Bash and PowerShell start/stop wrappers only.
- `infra/`: PostgreSQL initialization and operations documentation.
- `tests/`: automated tests.

## Test coverage and service-dependent checks

pytest-cov measures all Python modules under app/ and cli/, including branch coverage.
Every normal pytest run writes a terminal report, htmlcov/index.html, and coverage.xml.
Generated coverage files are ignored by Git. No coverage threshold is enforced yet.

**Windows PowerShell**

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

**Linux Bash**

```bash
./.venv/bin/python -m pip install -r requirements-dev.txt
./.venv/bin/python -m pytest -q
```

Open htmlcov/index.html in a browser to inspect unexecuted lines and branches.
Use --no-cov for a test run without coverage instrumentation.

For the complete currently implemented Python suite, start the initialized PostgreSQL container
and Ollama with the configured chat and embedding models, then enable both opt-in checks:

**Windows PowerShell**

```powershell
$env:RUN_POSTGRES_TESTS='1'
$env:RUN_OLLAMA_TESTS='1'
.\.venv\Scripts\python.exe -m pytest -q
```

**Linux Bash**

```bash
RUN_POSTGRES_TESTS=1 RUN_OLLAMA_TESTS=1 ./.venv/bin/python -m pytest -q
```

The PostgreSQL integration test adds/deletes a uniquely identified test document;
the Ollama test uses a temporary SQLite corpus. Do not use a shared production database.
These opt-in checks fail if enabled services are unavailable; ordinary runs skip them.
Real-model checks take longer and can fail if model answers do not meet the citation/content assertions.

Coverage is not proof that everything works. Python coverage does not measure JavaScript,
browser interactions, shell scripts, container lifecycle, live AWS operations or factual RAG quality.
S3 tests use a simulated adapter. A restore drill against a separate disposable PostgreSQL database,
browser end-to-end checks and a representative RAG evaluation dataset remain separate validation work.
