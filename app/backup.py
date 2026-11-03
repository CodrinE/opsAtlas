"""Explicit opt-in S3 snapshots. Never uploads .env, credentials, or chat questions."""
import argparse
import hashlib
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings

MAX_BACKUP_BYTES = 512 * 1024 * 1024


def digest(path):
    value = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def check_database(path):
    # Check a downloaded DB in read-only mode; never deserialize executable objects.
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('PRAGMA trusted_schema=OFF')
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Backup SQLite corupt.')
        if db.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise ValueError('Backup cu referințe invalide.')
        db.execute('SELECT id,name,model,created_at FROM documents LIMIT 1')
        db.execute('SELECT document_id,page,text,vector FROM chunks LIMIT 1')


def s3_config():
    if os.getenv('S3_ENABLED', 'false').lower() != 'true':
        raise ValueError('S3 este dezactivat. Configurează S3_ENABLED=true în .env.')
    bucket = os.getenv('S3_BUCKET', '').strip()
    prefix = os.getenv('S3_PREFIX', 'devops-rag/backups/').strip('/') + '/'
    if not bucket or prefix == '/':
        raise ValueError('S3_BUCKET și un S3_PREFIX nevid sunt obligatorii.')
    import boto3
    return boto3.client('s3'), bucket, prefix


def upload(settings, client, bucket, prefix):
    source = settings.data_dir / 'knowledge.sqlite3'
    if not source.is_file():
        raise ValueError('Baza locală nu există. Pornește aplicația și importă documente.')
    with tempfile.TemporaryDirectory() as temporary:
        snapshot = Path(temporary) / 'snapshot.sqlite3'
        with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)) as src, closing(sqlite3.connect(snapshot)) as dst:
            src.backup(dst)
        check_database(snapshot)
        if snapshot.stat().st_size > MAX_BACKUP_BYTES:
            raise ValueError('Backupul depășește limita de 512 MiB.')
        checksum = digest(snapshot)
        key = prefix + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + checksum[:12] + '.sqlite3'
        extra = {'ServerSideEncryption': 'AES256', 'Metadata': {'sha256': checksum}, 'ChecksumAlgorithm': 'SHA256'}
        kms = os.getenv('S3_KMS_KEY_ID')
        if kms:
            extra.update(ServerSideEncryption='aws:kms', SSEKMSKeyId=kms)
        client.upload_file(str(snapshot), bucket, key, ExtraArgs=extra)
        print(f'Backup creat: s3://{bucket}/{key}')


def restore(settings, client, bucket, prefix, key):
    if not key.startswith(prefix) or not key.endswith('.sqlite3'):
        raise ValueError('Cheia trebuie să fie un backup SQLite din S3_PREFIX.')
    target = settings.data_dir / 'knowledge.sqlite3'
    if target.exists():
        raise ValueError('Restaurarea cere un DATA_DIR nou, fără bază existentă. Oprește aplicația înainte.')
    meta = client.head_object(Bucket=bucket, Key=key)
    expected = meta.get('Metadata', {}).get('sha256', '')
    if len(expected) != 64 or meta['ContentLength'] > MAX_BACKUP_BYTES:
        raise ValueError('Backup prea mare sau fără checksum SHA256.')
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=settings.data_dir) as temporary:
        downloaded = Path(temporary) / 'restore.sqlite3'
        # Stream with a hard size bound even if object changes after HEAD.
        obj = client.get_object(Bucket=bucket, Key=key, IfMatch=meta['ETag'])
        body = obj['Body']
        try:
            with downloaded.open('wb') as stream:
                total = 0
                for block in body.iter_chunks(chunk_size=1024 * 1024):
                    total += len(block)
                    if total > MAX_BACKUP_BYTES:
                        raise ValueError('Backup prea mare.')
                    stream.write(block)
        finally:
            body.close()
        if digest(downloaded) != expected:
            raise ValueError('Checksum diferit. Restaurarea a fost oprită.')
        check_database(downloaded)
        # Exclusive creation prevents accidental overwrite, including concurrent restore.
        with target.open('xb') as output, downloaded.open('rb') as source:
            try:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    output.write(block)
            except Exception:
                output.close()
                target.unlink(missing_ok=True)
                raise
    print(f'Restaurat în {target}. Configurează același EMBED_MODEL ca la indexare.')


def main():
    parser = argparse.ArgumentParser(description='Backup S3 opțional al documentelor extrase și embeddings.')
    parser.add_argument('action', choices=['upload', 'restore'])
    parser.add_argument('--key', help='Cheia S3 completă pentru restore')
    args = parser.parse_args()
    settings = Settings.load()
    if settings.database_backend != "sqlite":
        parser.error("S3 snapshots support SQLite only. Use scripts.postgres_backup for PostgreSQL.")
    try:
        client, bucket, prefix = s3_config()
        if args.action == 'upload':
            upload(settings, client, bucket, prefix)
        else:
            if not args.key:
                parser.error('restore necesită --key')
            restore(settings, client, bucket, prefix, args.key)
    except Exception as exc:
        parser.exit(1, f'Backup eșuat: {exc}\n')


if __name__ == '__main__':
    main()
