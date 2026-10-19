"""Upgrade only designated isolated legacy QA (raw migrations, no main ledger)."""
import hashlib
import json
import os
from pathlib import Path
import psycopg
from .db_admin import backup,connect,DB_DIR

SCHEMA='frontend_expansion_20261013'
PATCHES=('011_public_catalog.sql','012_erasure_safeguards.sql')

def main():
    info=psycopg.conninfo.conninfo_to_dict(os.environ['DATABASE_URL'])
    if (os.getenv('TP_ENVIRONMENT')!='isolated_test' or info.get('host')!='127.0.0.1'
        or info.get('port')!='55432' or info.get('dbname')!='tatar_pattern_backend_test'):
        raise RuntimeError('Only designated isolated frontend QA database is allowed')
    os.environ['DATABASE_URL']=psycopg.conninfo.make_conninfo(os.environ['DATABASE_URL'],options=f'-c search_path={SCHEMA}')
    os.environ['TP_TEST_BACKUP_ROOT']=str(Path(__file__).resolve().parents[1]/'local-test/qa-repair-2026-10-19/backups')
    saved=backup()
    with connect() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(107198005)')
        if conn.execute('SELECT current_schema() s').fetchone()['s']!=SCHEMA:raise RuntimeError('QA schema absent')
        if conn.execute("SELECT to_regclass('schema_migrations') t").fetchone()['t']:
            raise RuntimeError('Use regular migrator for ledger-managed schemas')
        for table,column in [('users','profile'),('generations','deleted_at'),('ai_jobs','payload')]:
            if not conn.execute('SELECT 1 FROM information_schema.columns WHERE table_schema=%s AND table_name=%s AND column_name=%s',(SCHEMA,table,column)).fetchone():
                raise RuntimeError('Legacy QA must already contain migrations through010')
        before={t:conn.execute(f'SELECT count(*) n FROM {t}').fetchone()['n'] for t in ('users','generations','elements')}
        conn.execute('CREATE TABLE IF NOT EXISTS qa_schema_patches(name TEXT PRIMARY KEY,sha256 TEXT NOT NULL,applied_at TIMESTAMPTZ NOT NULL DEFAULT now())')
        for name in PATCHES:
            raw=(DB_DIR/'migrations'/name).read_bytes();sha=hashlib.sha256(raw).hexdigest()
            row=conn.execute('SELECT sha256 FROM qa_schema_patches WHERE name=%s',(name,)).fetchone()
            if row:
                if row['sha256']!=sha:raise RuntimeError('Applied QA patch changed')
                continue
            conn.execute(raw.decode());conn.execute('INSERT INTO qa_schema_patches(name,sha256) VALUES(%s,%s)',(name,sha))
        after={t:conn.execute(f'SELECT count(*) n FROM {t}').fetchone()['n'] for t in before}
        if before!=after:raise RuntimeError('QA repair must preserve existing data')
    report=dict(schema=SCHEMA,port=55432,patches=list(PATCHES),before=before,after=after,backup=str(saved))
    destination=Path(__file__).resolve().parents[1]/'local-test/qa-repair-2026-10-19/repair.json'
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
