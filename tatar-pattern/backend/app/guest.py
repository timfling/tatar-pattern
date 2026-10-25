"""Temporary guest capabilities and durable cleanup; no account identity."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
import psycopg
from psycopg.rows import dict_row
from .errors import APIError
from .erasure import enqueue_files, drain_files

COOKIE='tp_guest'
ADMISSION_LOCK=107198013

def fingerprint(body):
    return hashlib.sha256(json.dumps(body.model_dump(mode='json',exclude={'requestId'}),sort_keys=True,separators=(',',':')).encode()).hexdigest()

def metadata(user):
    return (user.get('guest_id'),user.get('expires_at'),user.get('request_id'),user.get('fingerprint'))

def remember_external(conn,job,cloud_id=None):
    expires=job['created_at']+timedelta(days=7)
    if expires<=datetime.now(timezone.utc):return
    conn.execute("""INSERT INTO guest_reconciliations(provider_request_id,generation_id,provider,provider_job_id,submit_uncertain,expires_at)
        VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(provider_request_id) DO UPDATE SET
        provider_job_id=COALESCE(EXCLUDED.provider_job_id,guest_reconciliations.provider_job_id),
        submit_uncertain=(EXCLUDED.provider_job_id IS NULL AND guest_reconciliations.provider_job_id IS NULL),confirmation_ref=NULL""",
        (job['provider_request_id'],job['generation_id'],job['provider'],cloud_id or job['provider_job_id'],not bool(cloud_id or job['provider_job_id']),expires))

def erase(conn,row):
    job=conn.execute('SELECT * FROM ai_jobs WHERE generation_id=%s FOR UPDATE',(row['id'],)).fetchone()
    if job and job['state'] not in ('queued','done'):
        remember_external(conn,{**job,'created_at':row['created_at']})
    for path in (row['result_path'],row.get('skeleton_path')):
        if path and not path.startswith('guest-results/'):
            raise RuntimeError('Guest path outside transient zone; operator review required')
        enqueue_files(conn,path)
    conn.execute('DELETE FROM ai_jobs WHERE generation_id=%s',(row['id'],))
    conn.execute('DELETE FROM generations WHERE id=%s',(row['id'],))

def clean(settings,*,all_guests=False):
    with psycopg.connect(settings.database_url,row_factory=dict_row,connect_timeout=3) as conn:
        conn.execute('SET statement_timeout=10000')
        conn.execute('SELECT pg_advisory_xact_lock(%s)',(ADMISSION_LOCK,))
        rows=conn.execute('SELECT * FROM generations WHERE guest_process_id IS NOT NULL'+('' if all_guests else ' AND guest_expires_at<=clock_timestamp()')+' ORDER BY id FOR UPDATE').fetchall()
        for row in rows:erase(conn,row)
        conn.execute('DELETE FROM guest_processes WHERE '+('true' if all_guests else 'expires_at<=clock_timestamp()'))
        conn.execute('DELETE FROM guest_reconciliations WHERE expires_at<=clock_timestamp()')
        conn.execute("DELETE FROM guest_budget WHERE key LIKE 'minute:%%' AND split_part(key,':',2)::bigint < floor(extract(epoch from clock_timestamp())/60)-1")
        # A crash can leave a file before its generation transaction commits.
        root=settings.storage_root/'guest-results'
        cutoff=datetime.now(timezone.utc).timestamp()-settings.guest_ttl_seconds
        if root.is_symlink():raise RuntimeError('Guest storage must not be a symlink')
        if root.exists():
            for path in root.rglob('*'):
                if path.is_symlink():raise RuntimeError('Unexpected guest storage symlink')
                expiry=path.name.partition('-')[0]
                expired=(int(expiry)<=datetime.now(timezone.utc).timestamp()*1000000) if len(expiry)==16 and expiry.isdigit() else path.stat().st_mtime<=cutoff
                if path.is_file() and expired:
                    enqueue_files(conn,str(path.relative_to(settings.storage_root)))
        conn.commit()
        drain_files(conn,settings.storage_root,path_prefix="guest-results/")
        conn.execute("DELETE FROM storage_deletions WHERE state='done' AND path LIKE 'guest-results/%%'")
        conn.commit()
    return len(rows)

def admit(conn,settings,user):
    conn.execute('SELECT pg_advisory_xact_lock(%s)',(ADMISSION_LOCK,))
    if not conn.execute('SELECT id FROM guest_processes WHERE id=%s AND expires_at>clock_timestamp() FOR SHARE',(user['guest_id'],)).fetchone():
        raise APIError(401,'GUEST_ACCESS_EXPIRED','Временный доступ истёк. Начните новый процесс.')
    if conn.execute("SELECT count(*) n FROM generations WHERE guest_process_id=%s AND status IN ('queued','processing')",(user['guest_id'],)).fetchone()['n']>=settings.guest_concurrent_jobs:
        raise APIError(429,'GUEST_CONCURRENCY_LIMIT','Дождитесь завершения текущих задач.')
    key='minute:'+str(int(datetime.now(timezone.utc).timestamp())//60)
    count=conn.execute('INSERT INTO guest_budget(key,used) VALUES(%s,1) ON CONFLICT(key) DO UPDATE SET used=guest_budget.used+1 RETURNING used',(key,)).fetchone()['used']
    if count>settings.guest_creates_per_minute:
        raise APIError(429,'GUEST_RATE_LIMIT','Слишком много задач. Повторите позже.')

def charge_gpu(conn,settings):
    count=conn.execute("INSERT INTO guest_budget(key,used) VALUES('gpu-total',1) ON CONFLICT(key) DO UPDATE SET used=guest_budget.used+1 RETURNING used").fetchone()['used']
    if count>settings.guest_gpu_budget:
        raise APIError(503,'AI_BUDGET_EXHAUSTED','Окно AI недоступно: лимит задач исчерпан.')
