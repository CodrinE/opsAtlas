from app.rag import Store

def create_store(settings):
    if settings.database_backend == 'sqlite':
        return Store(settings)
    from app.postgres import PostgresStore
    return PostgresStore(settings)
