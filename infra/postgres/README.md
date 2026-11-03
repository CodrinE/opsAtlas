# PostgreSQL local with Podman

Podman Desktop is the GUI; a working Podman engine/machine and the podman command are required.
In Podman Desktop, finish Podman provider setup and start the machine first.
Install/configure a Compose provider through Podman Desktop if podman compose is unavailable.
No Docker Desktop is required.

From the project root:
1. Stop the application and any document importer.
2. Run: .venv/Scripts/python.exe -m scripts.configure_postgres
3. Run: podman compose up -d postgres
4. Run: podman logs opsatlas-postgres
5. Run: .venv/Scripts/python.exe -m scripts.check_postgres
6. Optional migration: .venv/Scripts/python.exe -m scripts.migrate_postgres
7. Start the application normally.

configure_postgres generates separate random administrator and application passwords in the ignored .env.
It sets DATABASE_BACKEND=postgres and DATABASE_URL using the restricted opsatlas role.
Port 5433 is published only on 127.0.0.1.
Never print or commit the .env or expanded compose configuration.
Keep the SQLite file until you have checked migration counts and answers.
Migration copies existing embeddings without calling Ollama, preserves the source, skips duplicate hashes,
and commits atomically per document. An interrupted migration can be rerun.
Documents must match EMBED_MODEL and the 768 dimensions used by embeddinggemma:300m.
Different embedding dimensions require a deliberate schema migration and reindexing.

## Persistence

The named volume opsatlas_pgdata is mounted at /var/lib/postgresql/data in the Podman VM.
podman stop opsatlas-postgres and podman compose down preserve it.
Starting again reuses the same data.
Do not run compose down -v, podman volume rm, volume prune, or reset/delete the Podman machine
unless you intentionally want to delete its data.
A volume is not a backup: deleting the Podman VM or losing the disk can lose the database.

The init script only runs on a new empty volume.
Changing passwords in .env does not rotate passwords in an existing database.
configure_postgres preserves generated passwords on subsequent runs.
Do not change the PostgreSQL major version on an existing volume without a planned pg_dump/restore upgrade.

## Backup and restore

Stop application/importers before a restore.
Backup data to an ignored local file:
.venv/Scripts/python.exe -m scripts.postgres_backup backup

Restore a trusted dump into an EMPTY initialized PostgreSQL database:
.venv/Scripts/python.exe -m scripts.postgres_backup restore --file backups/NAME.dump

These are data-only custom pg_dump archives for this version of the initialized schema.
They do not contain role definitions, passwords, models or original PDFs.
Keep source/schema version and embedding model metadata with your backup.
Backup files contain document text and embeddings; protect and copy them to a separate disk.
Restore is transactional and refuses a nonempty documents table.
The PostgreSQL S3 integration is not implemented; the existing app.backup command is explicitly SQLite-only.
Use an external controlled process to archive PostgreSQL dumps to cloud storage if needed.

## Implementation and verification

Cosine distances are computed in PostgreSQL by pgvector using exact search.
The document_id index accelerates joins/deletes; there is no HNSW index yet.
Benchmark before adding approximate indexes; they can change recall.
The application role has table DML/sequence permissions, not superuser or schema modification privileges.
The host-to-VM connection is localhost-only, not TLS; use TLS for any remote deployment.

Optional real database integration test:
PowerShell: $env:RUN_POSTGRES_TESTS='1'
.venv/Scripts/python.exe -m pytest tests/test_postgres.py -q

This adds and deletes one uniquely identified test document in the configured database.
Do not run with a shared production database.

## Verified setup on this Windows machine

Podman executable: C:/Users/cod_ec/AppData/Local/Programs/Podman/podman.exe.
If an existing terminal does not find podman, reopen it or add that directory to its session PATH.
The Compose provider is installed in the project virtual environment.
For the current PowerShell session:

```powershell
$env:PATH = "$env:LOCALAPPDATA/Programs/Podman;" + $env:PATH
$env:PODMAN_COMPOSE_PROVIDER = (Resolve-Path .venv/Scripts/podman-compose.exe).Path
podman compose up -d postgres
```

To reinstall the optional Compose tooling:
.venv/Scripts/python.exe -m pip install -r requirements-containers.txt

PostgreSQL can need a few seconds after container start/restart before accepting connections.
Check status with podman ps, then scripts.check_postgres.

## Run the complete application with Podman Compose

From the project root, after the one-time PostgreSQL configuration:

```powershell
$env:PATH = "$env:LOCALAPPDATA/Programs/Podman;" + $env:PATH
$env:PODMAN_COMPOSE_PROVIDER = (Resolve-Path .venv/Scripts/podman-compose.exe).Path
podman compose up -d --build
```

Open **http://127.0.0.1:8080**. The app is built locally from Dockerfile.
Use --build after source changes; compose up without --build may reuse the previous image.
Both services start together; app waits for the PostgreSQL healthcheck.
Ollama continues running on Windows and uses the host GPU. It is not downloaded into the app image.

APP_PORT in .env changes the published web port. The container talks to postgres:5432,
regardless of the PostgreSQL port published on Windows.
CONTAINER_OLLAMA_URL defaults to http://host.containers.internal:11434 for Podman.
For Docker Engine/Desktop on a different machine, use http://host.docker.internal:11434.
Only explicit local gateway hostnames and loopback are accepted by OLLAMA_URL validation.
If Ollama cannot be reached, check its host binding and firewall; do not expose it publicly.

Commands:
- podman compose logs -f app
- podman compose stop
- podman compose up -d
- podman compose exec app python -m scripts.import_docs

Do not run a CLI import and a web upload simultaneously.
docs/ is mounted read-only; new documents do not require an image rebuild.
Credentials, .env, PDFs, local databases, backups and Git history are excluded from the build context.
AWS credentials are not passed into the app container.

The app runs as UID 10001, drops Linux capabilities, has a read-only root filesystem and writes
temporary/index staging files into the separate named volume opsatlas_appdata.
The database remains in opsatlas_pgdata. Both survive compose down without -v.
The healthcheck verifies app and database availability, independently of Ollama's status.

Verified locally: both containers healthy, five existing documents visible, Ollama ready,
and an HTTP chat request returning sources and valid citation identifiers.
