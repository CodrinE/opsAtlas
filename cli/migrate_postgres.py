"""Copy SQLite documents and existing embeddings to PostgreSQL; never delete the source."""
import argparse
import sqlite3
from contextlib import closing
from pathlib import Path
from app.config import Settings
from app.postgres import PostgresStore

def migrate(path, target):
    path = Path(path).resolve(strict=True)
    counts = dict(imported=0, duplicates=0)
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as source:
        source.row_factory = sqlite3.Row
        for document in source.execute('SELECT * FROM documents ORDER BY created_at,id'):
            rows = source.execute('SELECT page,text,vector FROM chunks WHERE document_id=? ORDER BY id',(document['id'],))
            result = target.publish(document, rows)
            counts['duplicates' if result['duplicate'] else 'imported'] += 1
    return counts

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='data/knowledge.sqlite3')
    args = parser.parse_args()
    print(migrate(args.source, PostgresStore(Settings.load())))

if __name__ == '__main__':
    main()
