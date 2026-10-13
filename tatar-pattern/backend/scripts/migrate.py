"""Apply SQL additions safely; supports legacy databases initialized by Docker."""
import hashlib
from .db_admin import DB_DIR, backup, connect


def main():
    backup()
    with connect() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(107198005)')
        conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations(name TEXT PRIMARY KEY, sha256 TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())')
        # Old Docker entrypoint had no ledger. Verify every defining object before
        # recording an already applied legacy migration; never replay its CREATE.
        legacy={
            '001_catalog.sql': ['sources','elements','element_files','palettes','composition_schemes'],
            '002_operational.sql': ['users','generations'],
            '003_site.sql': ['projects'],
            '004_artifacts.sql': ['artifacts','artifact_files'],
        }
        for file in sorted((DB_DIR/'migrations').glob('*.sql')):
            sql=file.read_text()
            digest=hashlib.sha256(sql.encode()).hexdigest()
            recorded=conn.execute('SELECT sha256 FROM schema_migrations WHERE name=%s',(file.name,)).fetchone()
            if recorded:
                if recorded['sha256']!=digest:
                    raise RuntimeError(f'Изменилась примененная миграция {file.name}; добавьте новую.')
                continue
            tables=legacy.get(file.name,[])
            exists=[conn.execute('SELECT to_regclass(%s) AS name',(t,)).fetchone()['name'] is not None for t in tables]
            if any(exists) and not all(exists):
                raise RuntimeError(f'Частичная legacy-схема {file.name}; нужна ручная сверка, без reset.')
            if tables and all(exists):
                checks={'003_site.sql':[('generations','project_id'),('generations','rating'),('generations','progress')],
                        '004_artifacts.sql':[('elements','artifact_id'),('element_files','ai_retouched')]}
                for table,column in checks.get(file.name,[]):
                    found=conn.execute('SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s AND column_name=%s',(table,column)).fetchone()
                    if not found:
                        raise RuntimeError(f'Неполная legacy-миграция {file.name}: {table}.{column}')
                print(f'Record legacy: {file.name}')
            else:
                conn.execute(sql)
                print(f'Applied: {file.name}')
            conn.execute('INSERT INTO schema_migrations(name,sha256) VALUES(%s,%s)',(file.name,digest))
    print('Migrations committed; seeds were not loaded.')

if __name__=='__main__':
    main()
