from app.config import Settings
from app.postgres import PostgresStore

def main():
    store = PostgresStore(Settings.load())
    with store.connection() as db:
        row = db.execute("SELECT current_user AS role, (SELECT extversion FROM pg_extension WHERE extname='vector') AS pgvector").fetchone()
        print(row)
    print(f'Documents: {len(store.documents())}')

if __name__ == '__main__':
    main()
