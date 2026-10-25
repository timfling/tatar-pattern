"""Durable local cleanup. Provider deletion needs separate factual confirmation.

Caller owns the transaction. Tombstones must also be exported outside restorable backups.
No legal retention period or self-service account closure is implied by this module.
"""
import logging
from pathlib import Path
from .catalog import safe_path

logger=logging.getLogger(__name__)

def enqueue_files(conn,relative):
    if not relative:return
    p=Path(relative)
    for path in (p,p.with_suffix('.jpg'),p.with_name(p.stem+'.module.png'),p.with_suffix('.tmp')):
        conn.execute("INSERT INTO storage_deletions(path) VALUES(%s) ON CONFLICT(path) DO UPDATE SET state='pending',last_error=NULL,updated_at=now()",(str(path),))

def remember_provider(conn,job,cloud_id=None):
    if job.get('guest_process_id'):
        from .guest import remember_external
        return remember_external(conn,job,cloud_id)
    if job['state']=='queued' and not cloud_id:return
    conn.execute("""INSERT INTO provider_deletions(generation_id,provider,provider_job_id,submit_uncertain)
      VALUES(%s,%s,%s,%s) ON CONFLICT(generation_id) DO UPDATE SET
      provider_job_id=COALESCE(EXCLUDED.provider_job_id,provider_deletions.provider_job_id),
      submit_uncertain=(EXCLUDED.provider_job_id IS NULL AND provider_deletions.provider_job_id IS NULL),
      state='manual_required',confirmation_ref=NULL,updated_at=now()""",
      (job['generation_id'],job['provider'],cloud_id or job['provider_job_id'],not bool(cloud_id or job['provider_job_id'])))

def erase_generation(conn,row,reason):
    # Lock generation first, as the worker does before final storage/commit.
    current=conn.execute('SELECT * FROM generations WHERE id=%s FOR UPDATE',(row['id'],)).fetchone()
    if not current:return
    conn.execute('INSERT INTO erasure_tombstones(generation_id,user_id,reason) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',
                 (current['id'],current['user_id'],reason))
    job=conn.execute('SELECT * FROM ai_jobs WHERE generation_id=%s FOR UPDATE',(current['id'],)).fetchone()
    if job:remember_provider(conn,job)
    enqueue_files(conn,current['result_path']);enqueue_files(conn,current.get('skeleton_path'))
    # Explicit order: no accidental FK violation; no loss of provider reconciliation ID.
    conn.execute('DELETE FROM ai_jobs WHERE generation_id=%s',(current['id'],))
    conn.execute('DELETE FROM generations WHERE id=%s',(current['id'],))

def drain_files(conn,root,limit=200,*,path_prefix=None):
    where="state='pending'"
    args=[]
    if path_prefix is not None:
        where+=' AND starts_with(path,%s)';args.append(path_prefix)
    rows=conn.execute(f"SELECT * FROM storage_deletions WHERE {where} ORDER BY updated_at,path LIMIT %s FOR UPDATE SKIP LOCKED",(*args,limit)).fetchall()
    for row in rows:
        error=None
        try:
            path=safe_path(root,row['path']);path.unlink(missing_ok=True)
            if path.exists():raise OSError('File still exists')
        except (OSError,ValueError) as exc:
            error=type(exc).__name__  # Never log private paths or raw exception bodies.
            logger.warning('Storage deletion deferred (%s)',error)
        conn.execute("UPDATE storage_deletions SET state=%s,attempts=attempts+1,last_error=%s,updated_at=now() WHERE path=%s",
                     ('pending' if error else 'done',error,row['path']))
    return len(rows)


def block_account(conn,user_id,operation_ref,decision_ref):
    """Internal preparation: real operator checks identity/authority before calling."""
    conn.execute('SELECT pg_advisory_xact_lock(107198012)')
    existing=conn.execute('SELECT * FROM privacy_operations WHERE operation_ref=%s',(operation_ref,)).fetchone()
    if existing:
        if existing['user_id']!=user_id or existing['decision_ref']!=decision_ref:
            raise ValueError('Operation reference already belongs to another decision/subject')
        return
    row=conn.execute('SELECT id FROM users WHERE id=%s FOR UPDATE',(user_id,)).fetchone()
    if not row:raise ValueError('Subject missing')
    conn.execute('UPDATE users SET access_blocked=true WHERE id=%s',(user_id,))
    conn.execute('DELETE FROM sessions WHERE user_id=%s',(user_id,))
    conn.execute("INSERT INTO privacy_operations(operation_ref,user_id,state,decision_ref) VALUES(%s,%s,'blocked',%s)",
                 (operation_ref,user_id,decision_ref))


def erase_account_local(conn,operation_ref):
    """Local SQL removal only; no assertion about provider copies, logs or backups."""
    op=conn.execute('SELECT * FROM privacy_operations WHERE operation_ref=%s FOR UPDATE',(operation_ref,)).fetchone()
    if not op:raise ValueError('Block account first')
    if op['state']!='blocked':return
    uid=op['user_id']
    user=conn.execute('SELECT * FROM users WHERE id=%s FOR UPDATE',(uid,)).fetchone()
    if user and not user['access_blocked']:raise ValueError('Account must remain blocked')
    rows=conn.execute('SELECT * FROM generations WHERE user_id=%s ORDER BY id FOR UPDATE',(uid,)).fetchall()
    for row in rows:erase_generation(conn,row,'account_closure')
    conn.execute('DELETE FROM sessions WHERE user_id=%s',(uid,))
    conn.execute('DELETE FROM projects WHERE user_id=%s',(uid,))
    conn.execute('DELETE FROM users WHERE id=%s',(uid,))
    pending=conn.execute("SELECT 1 FROM provider_deletions p JOIN erasure_tombstones t USING(generation_id) WHERE t.user_id=%s AND p.state!='confirmed' LIMIT 1",(uid,)).fetchone()
    conn.execute('UPDATE privacy_operations SET state=%s,updated_at=now() WHERE operation_ref=%s',
                 ('provider_pending' if pending else 'local_erased',operation_ref))
