"""Generate local PostgreSQL credentials without printing them."""
import secrets
from pathlib import Path
from dotenv import dotenv_values

def main():
    path = Path('.env')
    values = dotenv_values(path)
    updates = {}
    for key in ('POSTGRES_ADMIN_PASSWORD','OPSATLAS_DB_PASSWORD'):
        if not values.get(key):
            updates[key] = secrets.token_hex(24)
    password = values.get('OPSATLAS_DB_PASSWORD') or updates['OPSATLAS_DB_PASSWORD']
    port = values.get('POSTGRES_PORT') or '5433'
    updates.update(DATABASE_BACKEND='postgres', POSTGRES_PORT=port,
                   DATABASE_URL=f'postgresql://opsatlas:{password}@127.0.0.1:{port}/opsatlas')
    lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
    output = [line for line in lines if line.split('=',1)[0].strip() not in updates]
    output.extend(f'{key}={value}' for key,value in updates.items())
    path.write_text('\n'.join(output)+'\n', encoding='utf-8')
    print('Local .env configured. Credentials preserved on subsequent runs. No database was modified.')

if __name__ == '__main__':
    main()
