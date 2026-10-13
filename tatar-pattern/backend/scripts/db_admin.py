"""Backup before connecting to any existing database for maintenance."""
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4
from dotenv import load_dotenv

import psycopg
from psycopg.rows import dict_row

DB_DIR=Path(__file__).resolve().parents[2]/'db'
load_dotenv(Path(__file__).resolve().parents[1]/'.env',override=False)


def database_url():
    return os.environ['DATABASE_URL']


def backup():
    pg_bin=os.getenv('PG_BIN','')
    executable=str(Path(pg_bin)/'pg_dump') if pg_bin else shutil.which('pg_dump')
    if not executable:
        raise RuntimeError('Нужен pg_dump PostgreSQL 16+ (или PG_BIN). Бэкап обязателен.')
    directory=DB_DIR/'backups'
    if os.getenv('TP_TEST_BACKUP_ROOT'):
        fields=psycopg.conninfo.conninfo_to_dict(database_url())
        if os.getenv('TP_ENVIRONMENT')!='isolated_test' or not fields.get('dbname','').endswith('_test') or fields.get('host') not in ('127.0.0.1','localhost'):
            raise RuntimeError('Test backup override requires isolated loopback test DB')
        directory=Path(os.environ['TP_TEST_BACKUP_ROOT'])
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/f"backend_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid4().hex[:8]}.dump"
    env=os.environ.copy()
    # pg_dump does not expand a URI placed in PGDATABASE. Parse it and pass
    # libpq fields separately so credentials still stay out of argv.
    fields=psycopg.conninfo.conninfo_to_dict(database_url())
    names={'dbname':'PGDATABASE','user':'PGUSER','password':'PGPASSWORD',
           'host':'PGHOST','hostaddr':'PGHOSTADDR','port':'PGPORT',
           'options':'PGOPTIONS','sslmode':'PGSSLMODE','sslcert':'PGSSLCERT',
           'sslkey':'PGSSLKEY','sslrootcert':'PGSSLROOTCERT',
           'connect_timeout':'PGCONNECT_TIMEOUT','service':'PGSERVICE'}
    for key,value in fields.items():
        if key not in names:
            raise RuntimeError(f'Параметр подключения {key} не поддержан резервным копированием.')
        env[names[key]]=value
    # URL/password stay in environment, not command line or command output.
    result=subprocess.run([executable,'--format=custom','--file',str(path)],env=env,capture_output=True)
    if result.returncode or not path.exists() or path.stat().st_size<100:
        path.unlink(missing_ok=True)
        raise RuntimeError('Резервная копия не создана; операция остановлена. Проверьте pg_dump и подключение.')
    path.chmod(0o600)
    print(f'Backup: {path}')
    return path


def connect():
    return psycopg.connect(database_url(),row_factory=dict_row,connect_timeout=5)


def require_local_environment():
    fields=psycopg.conninfo.conninfo_to_dict(database_url())
    if os.getenv('TP_ENVIRONMENT') not in ('local_project','isolated_test') or fields.get('host') not in ('127.0.0.1','localhost'):
        raise RuntimeError('Explicit TP_ENVIRONMENT=local_project/isolated_test and loopback DB required for catalog maintenance')
    print('Environment:',os.environ['TP_ENVIRONMENT'],'database:',fields.get('dbname'),'host:',fields['host'],'port:',fields.get('port','5432'))


def backup_files(root):
    import tarfile
    root=Path(root).resolve()
    if root==DB_DIR or DB_DIR.is_relative_to(root):
        raise RuntimeError('Storage root must not contain backup directory')
    directory=DB_DIR/'backups'; directory.mkdir(exist_ok=True)
    path=directory/f"files_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid4().hex[:8]}.tar.gz"
    with tarfile.open(path,'w:gz') as archive:
        if root.exists(): archive.add(root,arcname='storage')
    path.chmod(0o600)
    print('Files backup:',path)
    return path
