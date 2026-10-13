"""Dedicated frontend integration schema, never the working database."""
import os
from pathlib import Path
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from scripts.db_admin import backup
from scripts.catalog_import import validate, db_conflicts, import_reviewed
BASE=Path(__file__).resolve().parents[1]
def main():
    url=os.environ['DATABASE_URL']
    info=psycopg.conninfo.conninfo_to_dict(url)
    if os.getenv('TP_ENVIRONMENT')!='isolated_test' or not info['dbname'].endswith('_test'):
        raise RuntimeError('Separate test database required')
    backup()
    schema='frontend_qa_20261009'
    with psycopg.connect(url,row_factory=dict_row) as conn:
        exists=conn.execute('SELECT 1 FROM information_schema.schemata WHERE schema_name=%s',(schema,)).fetchone()
        if not exists:
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
            conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
            for migration in sorted((BASE.parent/'db/migrations').glob('*.sql')): conn.execute(migration.read_text())
            root=BASE/'catalog-input'; data, report=validate(root/'owner-accepted-2026-10-08.json',root)
            db_conflicts(conn,data,report)
            if not report['valid']: raise RuntimeError('Catalog validation failed')
            import_reviewed(conn,data,report)
    os.environ['DATABASE_URL']=psycopg.conninfo.make_conninfo(url,options=f'-c search_path={schema}')
    import uvicorn
    uvicorn.run('app.main:create_app',factory=True,host='127.0.0.1',port=8014)
if __name__=='__main__': main()
