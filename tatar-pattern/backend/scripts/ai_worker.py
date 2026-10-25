"""Single persistent worker, advisory lock survives no restart; jobs do.

Configured transport is required; new submissions also require verified readiness.
One concurrent cloud job; bounded
poll errors (3), total wall deadline 15 min, 20 queued tasks. No submit retry and
no automatic fallback to flat. A restarted uncertain submission is reported as
failed, never blindly resubmitted/paid. Known cloud IDs continue polling. Local
failure/timeout does not assert cancellation of GPU computation.
"""
import io
import hashlib
import time
import signal
import os
from datetime import datetime, timezone
from uuid import uuid4
from PIL import Image
from psycopg.errors import DeadlockDetected, LockNotAvailable, QueryCanceled
from psycopg.types.json import Jsonb
from app.ai_provider import configured_provider, ProviderError
from app.catalog import safe_path
from app.ai_catalog import validate_task, TASK_SCHEMA
from app.errors import APIError
from app.config import Settings
from app.erasure import enqueue_files, remember_provider
from app import guest
from .db_admin import connect


DRAIN_SECONDS=930
HARD_STOP_SECONDS=950


class Shutdown:
    """The first signal owns the deadline; repeated signals cannot extend it."""
    def __init__(self):
        self.requested_at=None

    @property
    def deadline(self):
        return None if self.requested_at is None else self.requested_at+DRAIN_SECONDS

    def is_set(self):
        return self.requested_at is not None

    def set(self):
        if self.requested_at is None:
            self.requested_at=time.monotonic()
            return True
        return False


def install_shutdown_handlers(stop):
    # An explicit handler also works when Python is container PID 1 (which may
    # ignore a default-action SIGALRM). No cleanup/commit/success acknowledgement
    # is attempted from this emergency path. Beget must retain tunnel and DB.
    def hard_stop(signum,frame):os._exit(75)
    signal.signal(signal.SIGALRM,hard_stop)
    def shutdown(signum,frame):
        if stop.set():
            signal.setitimer(signal.ITIMER_REAL,max(.001,HARD_STOP_SECONDS-(time.monotonic()-stop.requested_at)))
    signal.signal(signal.SIGTERM,shutdown)
    signal.signal(signal.SIGINT,shutdown)


def fail(conn,job,code):
    error={'code':code,'message':'ИИ-задача не завершена. Удаленная GPU-задача может продолжаться; обратитесь к оператору.'}
    # Same lock order as expiry cleanup, erasure, submit and result commit.
    conn.execute("UPDATE generations SET status='failed',error=%s,finished_at=now(),progress=NULL WHERE id=%s",(Jsonb(error),job['generation_id']))
    conn.execute("UPDATE ai_jobs SET state='failed',updated_at=now() WHERE generation_id=%s",(job['generation_id'],))
    conn.commit()


def save_ack(conn,job,cloud_id):
    generation=conn.execute('SELECT id,deleted_at,guest_expires_at FROM generations WHERE id=%s FOR UPDATE',(job['generation_id'],)).fetchone()
    if generation is None or (generation['guest_expires_at'] and generation['guest_expires_at']<=datetime.now(timezone.utc)):
        remember_provider(conn,job,cloud_id)
        if generation:
            conn.execute("UPDATE ai_jobs SET state='failed',provider_job_id=%s,updated_at=now() WHERE generation_id=%s",(cloud_id,job['generation_id']))
    else:
        conn.execute("UPDATE ai_jobs SET state='polling',provider_job_id=%s,updated_at=now() WHERE generation_id=%s",(cloud_id,job['generation_id']))
    conn.commit()


def step(conn,provider,settings,*,allow_new=True,stop_requested=lambda:False,stop_deadline=None):
    job=conn.execute("SELECT j.*,g.guest_process_id,g.guest_expires_at,g.created_at FROM ai_jobs j JOIN generations g ON g.id=j.generation_id WHERE state IN ('submitting','polling') OR (state='queued' AND %s) ORDER BY CASE WHEN state='queued' THEN 1 ELSE 0 END,generation_id LIMIT 1",(allow_new,)).fetchone()
    conn.commit()
    if not job: return False
    if job['guest_expires_at'] and job['guest_expires_at']<=datetime.now(timezone.utc):
        row=conn.execute('SELECT * FROM generations WHERE id=%s FOR UPDATE',(job['generation_id'],)).fetchone()
        if row:guest.erase(conn,row)
        conn.commit()
        return True
    def current_stop_deadline():
        return stop_deadline() if callable(stop_deadline) else stop_deadline
    def budget(seconds):
        bounds=[seconds,(job['deadline']-datetime.now(timezone.utc)).total_seconds()]
        deadline=current_stop_deadline()
        if deadline is not None:bounds.append(deadline-time.monotonic())
        return max(.01,min(bounds))
    if job['provider']!=provider.name or job['model_version']!=provider.model_version:
        fail(conn,job,'AI_MODEL_CONFIGURATION_CHANGED'); return True
    if job['state']=='submitting' and not job['provider_job_id']:
        fail(conn,job,'AI_SUBMISSION_UNCERTAIN'); return True
    if job['deadline']<=datetime.now(timezone.utc):
        fail(conn,job,'AI_TIMEOUT'); return True
    if job['state']=='queued':
        if stop_requested(): return False
        try:
            base=validate_task(job['payload'])
            if job['payload']['profile'].get('qualityStatus') in ('owner_rejected_cloud_2026_10_19','excluded_from_cloud_qualification') or not settings.ai_mvp_enabled or not base.get('externalTransferApproved') or not job['payload']['profile'].get('releaseApproved') or not getattr(provider,'ready',False) or getattr(provider,'contract_version',None)!=TASK_SCHEMA or (hasattr(provider,'ready_for') and not provider.ready_for(base,job['payload']['profile'])):
                fail(conn,job,'AI_RELEASE_NOT_READY'); return True
        except APIError as exc:
            fail(conn,job,exc.payload['error']['code']); return True
        if stop_requested(): return False
        generation=conn.execute('SELECT deleted_at,guest_expires_at FROM generations WHERE id=%s AND NOT EXISTS (SELECT 1 FROM erasure_tombstones t WHERE t.generation_id=generations.id) FOR UPDATE',(job['generation_id'],)).fetchone()
        if generation is None or generation['deleted_at'] is not None or (generation['guest_expires_at'] and generation['guest_expires_at']<=datetime.now(timezone.utc)):
            if generation:fail(conn,job,'AI_DELETED')
            else:conn.commit()
            return True
        conn.execute("UPDATE ai_jobs SET state='submitting',updated_at=now() WHERE generation_id=%s",(job['generation_id'],))
        conn.execute("UPDATE generations SET status='processing',progress=NULL WHERE id=%s",(job['generation_id'],)); conn.commit()
        try:
            cloud_id=provider.submit(job['payload'],request_id=str(job['provider_request_id']),timeout=budget(30))
            if not isinstance(cloud_id,str) or not cloud_id or len(cloud_id)>1000: raise ValueError()
        except ProviderError as exc:
            if exc.job_id:
                save_ack(conn,job,exc.job_id)
            else: fail(conn,job,exc.code if exc.definitive else 'AI_SUBMISSION_UNCERTAIN')
            return True
        except Exception:
            fail(conn,job,'AI_SUBMISSION_UNCERTAIN'); return True
        save_ack(conn,job,cloud_id)
        return True
    if job['provider_job_id'] and hasattr(provider,'bind_task'):
        provider.bind_task(job['provider_job_id'],job['payload'])
    if job['next_poll_at']>datetime.now(timezone.utc): return False
    generated=[]
    try:
        status=provider.poll(job['provider_job_id'],timeout=budget(15))
        if status.state=='failed': fail(conn,job,status.error_code or 'AI_CLOUD_FAILED'); return True
        if status.state=='pending':
            conn.execute("UPDATE ai_jobs SET next_poll_at=now()+interval '5 seconds',poll_errors=0,updated_at=now() WHERE generation_id=%s",(job['generation_id'],)); conn.commit(); return True
        if status.state!='done': raise ValueError()
        deadline=current_stop_deadline()
        if deadline is not None and time.monotonic()>=deadline:return False
        generation=conn.execute('SELECT params,deleted_at,guest_expires_at FROM generations WHERE id=%s AND NOT EXISTS (SELECT 1 FROM erasure_tombstones t WHERE t.generation_id=generations.id) FOR UPDATE',(job['generation_id'],)).fetchone()
        if generation is None or generation['deleted_at'] is not None or (generation['guest_expires_at'] and generation['guest_expires_at']<=datetime.now(timezone.utc)):
            remember_provider(conn,job)
            if generation:fail(conn,job,'AI_DELETED')
            else:conn.commit()
            if hasattr(provider,'forget_job'):provider.forget_job(job['provider_job_id'])
            return True
        data=provider.download(job['provider_job_id'],timeout=budget(30),max_bytes=20*1024*1024)
        if len(data)>20*1024*1024: raise ValueError()
        with Image.open(io.BytesIO(data)) as source:
            if source.format!='PNG' or source.size!=(1024,1024): raise ValueError()
            source.load()
            if source.convert('RGBA').getchannel('A').getextrema()!=(255,255): raise ValueError()
            image=source.convert('RGB')
        if generation['guest_expires_at'] and generation['guest_expires_at']<=datetime.now(timezone.utc):
            remember_provider(conn,job);fail(conn,job,'AI_EXPIRED');return True
        relative=f"guest-results/{int(job['guest_expires_at'].timestamp()*1000000)}-ai-{uuid4().hex}.png" if job['guest_process_id'] else f'results/ai-{uuid4().hex}.png'; png=safe_path(settings.storage_root,relative)
        png.parent.mkdir(parents=True,exist_ok=True)
        temporary=png.with_suffix('.tmp'); generated=[temporary,png,png.with_suffix('.jpg')]; temporary.write_bytes(data); temporary.replace(png)
        image.save(png.with_suffix('.jpg'),format='JPEG',quality=95)
        params=generation['params']
        if status.metadata is not None:params['recipe']['gpuMetadata']=status.metadata
        params['recipe']['providerOutputSha256']=hashlib.sha256(data).hexdigest()
        params['recipe']['outputSha256']={'png':hashlib.sha256(png.read_bytes()).hexdigest(),'jpg':hashlib.sha256(png.with_suffix('.jpg').read_bytes()).hexdigest()}
        params['recipe']['outputSize']=list(image.size)
        if generation['guest_expires_at'] and generation['guest_expires_at']<=datetime.now(timezone.utc):
            raise APIError(410,'AI_EXPIRED','Временный результат истёк.')
        conn.execute('UPDATE generations SET params=%s WHERE id=%s',(Jsonb(params),job['generation_id']))
        conn.execute("UPDATE ai_jobs SET state='done',updated_at=now() WHERE generation_id=%s",(job['generation_id'],))
        conn.execute("UPDATE generations SET status='done',progress=100,result_path=%s,finished_at=now() WHERE id=%s",(relative,job['generation_id'])); conn.commit()
        if hasattr(provider,'forget_job'):provider.forget_job(job['provider_job_id'])
    except Exception as exc:
        conn.rollback()
        for path in generated:
            enqueue_files(conn,str(path.relative_to(settings.storage_root)))
        conn.commit()
        if isinstance(exc,ProviderError) and exc.definitive:
            fail(conn,job,exc.code)
        elif job['poll_errors']>=2: fail(conn,job,'AI_PROVIDER_ERRORS')
        else:
            conn.execute("UPDATE ai_jobs SET poll_errors=poll_errors+1,next_poll_at=now()+interval '10 seconds',updated_at=now() WHERE generation_id=%s",(job['generation_id'],)); conn.commit()
    return True


def run(conn,provider,settings,stop):
    """Drain only already submitted jobs. Durable known IDs survive a bounded drain."""
    announced=False
    last_cleanup=0
    while True:
        if not stop.is_set() and time.monotonic()-last_cleanup>=60:
            try:guest.clean(settings)
            except Exception as exc:print('GUEST_CLEANUP_DEFERRED: '+type(exc).__name__,flush=True)
            last_cleanup=time.monotonic()
        drain_deadline=stop.deadline
        if stop.is_set() and not announced:
            announced=True
            print('AI_WORKER_DRAINING: admission closed; keep GPU tunnel running',flush=True)
        if drain_deadline is not None and time.monotonic()>=drain_deadline:
            # This is a resumable local interruption, not GPU cancellation.
            conn.execute("UPDATE generations SET params=jsonb_set(params,'{recipe,workerShutdown}',%s) WHERE id IN (SELECT generation_id FROM ai_jobs WHERE state IN ('submitting','polling'))",(Jsonb({'state':'poll_resume_required','gpuCancelled':False}),))
            conn.commit()
            print('AI_WORKER_DRAINED: poll_resume_required persisted; GPU may continue',flush=True)
            return
        try:
            step(conn,provider,settings,allow_new=not stop.is_set(),stop_requested=stop.is_set,stop_deadline=lambda:stop.deadline)
        except (DeadlockDetected, LockNotAvailable, QueryCanceled) as exc:
            # Resume from durable state on the next iteration. In particular a
            # committed submitting/known-ID job must never become queued again.
            conn.rollback()
            print('AI_WORKER_SQL_DEFERRED: '+type(exc).__name__,flush=True)
        if stop.is_set():
            active=conn.execute("SELECT count(*) AS n FROM ai_jobs WHERE state IN ('submitting','polling')").fetchone()['n']
            conn.commit()
            if not active:
                print('AI_WORKER_DRAINED: local states saved; queued jobs preserved; GPU cancellation not implied',flush=True)
                return
        time.sleep(1)


def main():
    stop=Shutdown()
    install_shutdown_handlers(stop)
    provider=configured_provider()
    if provider is None: raise SystemExit('AI_PROVIDER_UNCONFIGURED: img2img adapter configuration required')
    settings=Settings.from_env()
    with connect() as conn:
        conn.execute("SET statement_timeout='5s'")
        conn.execute("SET lock_timeout='5s'")
        if not conn.execute('SELECT pg_try_advisory_lock(107198011) AS locked').fetchone()['locked']: raise SystemExit('Another worker is active')
        conn.commit()
        run(conn,provider,settings,stop)

if __name__=='__main__': main()
