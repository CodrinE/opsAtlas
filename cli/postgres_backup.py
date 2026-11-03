"""Local PostgreSQL data backup/restore through the existing Podman container."""
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from app.config import Settings
from app.postgres import PostgresStore

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['backup','restore'])
    parser.add_argument('--file')
    parser.add_argument('--runtime',default='podman',help='Podman executable path')
    args = parser.parse_args()
    base = [args.runtime,'exec']
    if args.action == 'backup':
        path = Path(args.file or ('backups/postgres-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.dump'))
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as output:
            try:
                subprocess.run(base+['opsatlas-postgres','pg_dump','-U','postgres','-d','opsatlas',
                                    '--data-only','--format=custom'],stdout=output,check=True)
            except Exception:
                output.close()
                path.unlink(missing_ok=True)
                raise
        print(f'Backup: {path}')
    else:
        if not args.file:
            parser.error('restore requires --file')
        store = PostgresStore(Settings.load())
        if store.documents():
            parser.error('Restore requires an empty initialized database. Stop the application first.')
        with Path(args.file).open('rb') as source:
            subprocess.run(base+['-i','opsatlas-postgres','pg_restore','-U','postgres','-d','opsatlas',
                                 '--data-only','--no-owner','--no-privileges','--disable-triggers',
                                 '--single-transaction','--exit-on-error'],stdin=source,check=True)
        print('Restore completed.')

if __name__ == '__main__':
    main()
