"""Authorized local-project import after isolated tests; no overwrite/reset."""
import json
from pathlib import Path
from .db_admin import require_local_environment,backup_files,backup,connect
from .migrate import main as migrate
from .catalog_import import validate,db_conflicts,import_reviewed


def main():
    require_local_environment()
    base=Path(__file__).resolve().parents[1]; root=base/'catalog-input'
    manifest=root/'owner-accepted-2026-10-08.json'
    data,report=validate(manifest,root)
    if not report['valid']: raise RuntimeError('Invalid registry')
    digest=json.loads((root/'validation.json').read_text())['approvalDigest']
    if digest!=report['approvalDigest']: raise RuntimeError('Files/registry changed after validation')
    backups=[]
    for storage in (root,base/'storage',base/'local-test/storage'):
        backups.append(str(backup_files(storage)))
    backups.append(str(backup()))
    with connect() as conn:
        before={}
        for table in ('elements','users','generations','artifacts'):
            exists=conn.execute('SELECT to_regclass(%s) AS t',(table,)).fetchone()['t']
            before[table]=conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] if exists else 0
    migrate()
    with connect() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(107198006)')
        db_conflicts(conn,data,report)
        if not report['valid']: raise RuntimeError('DB conflicts: '+str(report['duplicates']))
        _,fresh=validate(manifest,root)
        if fresh['approvalDigest']!=digest: raise RuntimeError('Changed files')
        import_reviewed(conn,data,report)
        after={table:conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] for table in before}
        assert after['elements']==before['elements']+110
        assert after['users']==before['users'] and after['generations']==before['generations']
    (base/'local-test/local-import.json').write_text(json.dumps({'environment':'local_project','database':'tatar_pattern','host':'127.0.0.1','port':5432,'before':before,'after':after,'backups':backups,'validation':report},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'before':before,'after':after,'environment':'local_project'},ensure_ascii=False))

if __name__=='__main__': main()
