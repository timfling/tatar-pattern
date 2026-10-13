"""Single persistent worker, advisory lock survives no restart; jobs do.

Run only after a verified provider is configured. One concurrent cloud job; bounded
poll errors (3), total wall deadline 15 min, 20 queued tasks. No submit retry and
no automatic fallback to flat. A restarted uncertain submission is reported as
failed, never blindly resubmitted/paid. Known cloud IDs continue polling. Local
failure/timeout does not assert cancellation of GPU computation.
"""
import io
import time
from datetime import datetime, timezone
from uuid import uuid4
from PIL import Image
from psycopg.types.json import Jsonb
from app.ai_provider import configured_provider
from app.catalog import safe_path
from app.config import Settings
from .db_admin import connect


def fail(conn,job,code):
    error={'code':code,'message':'ИИ-задача не завершена. Удаленная GPU-задача может продолжаться; обратитесь к оператору.'}
    conn.execute("UPDATE ai_jobs SET state='failed',updated_at=now() WHERE generation_id=%s",(job['generation_id'],))
    conn.execute("UPDATE generations SET status='failed',error=%s,finished_at=now(),progress=NULL WHERE id=%s",(Jsonb(error),job['generation_id']))
    conn.commit()


def step(conn,provider,settings):
    job=conn.execute("SELECT * FROM ai_jobs WHERE state IN ('queued','submitting','polling') ORDER BY CASE WHEN state='queued' THEN 1 ELSE 0 END,generation_id LIMIT 1").fetchone()
    conn.commit()
    if not job: return False
    if job['provider']!=provider.name or job['model_version']!=provider.model_version:
        fail(conn,job,'AI_MODEL_CONFIGURATION_CHANGED'); return True
    if job['deadline']<=datetime.now(timezone.utc):
        fail(conn,job,'AI_TIMEOUT'); return True
    if job['state']=='submitting':
        fail(conn,job,'AI_SUBMISSION_UNCERTAIN'); return True
    if job['state']=='queued':
        conn.execute("UPDATE ai_jobs SET state='submitting',updated_at=now() WHERE generation_id=%s",(job['generation_id'],))
        conn.execute("UPDATE generations SET status='processing',progress=NULL WHERE id=%s",(job['generation_id'],)); conn.commit()
        try:
            cloud_id=provider.submit(job['payload'],request_id=str(job['generation_id']),timeout=30)
            if not isinstance(cloud_id,str) or not cloud_id or len(cloud_id)>1000: raise ValueError()
        except Exception:
            fail(conn,job,'AI_SUBMISSION_UNCERTAIN'); return True
        conn.execute("UPDATE ai_jobs SET state='polling',provider_job_id=%s,updated_at=now() WHERE generation_id=%s",(cloud_id,job['generation_id'])); conn.commit()
        return True
    if job['next_poll_at']>datetime.now(timezone.utc): return False
    generated=[]
    try:
        status=provider.poll(job['provider_job_id'],timeout=15)
        if status.state=='failed': fail(conn,job,'AI_CLOUD_FAILED'); return True
        if status.state=='pending':
            conn.execute("UPDATE ai_jobs SET next_poll_at=now()+interval '5 seconds',poll_errors=0,updated_at=now() WHERE generation_id=%s",(job['generation_id'],)); conn.commit(); return True
        if status.state!='done': raise ValueError()
        data=provider.download(job['provider_job_id'],timeout=30,max_bytes=20*1024*1024)
        if len(data)>20*1024*1024: raise ValueError()
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in ('PNG','JPEG') or min(source.size)<16 or max(source.size)>4096: raise ValueError()
            source.load(); image=source.convert('RGBA')
        relative=f'results/ai-{uuid4().hex}.png'; png=safe_path(settings.storage_root,relative)
        png.parent.mkdir(parents=True,exist_ok=True)
        temporary=png.with_suffix('.tmp'); generated=[temporary,png,png.with_suffix('.jpg')]; image.save(temporary,format='PNG'); temporary.replace(png)
        background=job['payload']['selections'].get('backgroundColor') or '#ffffff'
        solid=Image.new('RGBA',image.size,background); solid.alpha_composite(image)
        solid.convert('RGB').save(png.with_suffix('.jpg'),format='JPEG',quality=95)
        conn.execute("UPDATE ai_jobs SET state='done',updated_at=now() WHERE generation_id=%s",(job['generation_id'],))
        conn.execute("UPDATE generations SET status='done',progress=100,result_path=%s,finished_at=now() WHERE id=%s",(relative,job['generation_id'])); conn.commit()
    except Exception:
        for path in generated: path.unlink(missing_ok=True)
        conn.rollback()
        if job['poll_errors']>=2: fail(conn,job,'AI_PROVIDER_ERRORS')
        else:
            conn.execute("UPDATE ai_jobs SET poll_errors=poll_errors+1,next_poll_at=now()+interval '10 seconds',updated_at=now() WHERE generation_id=%s",(job['generation_id'],)); conn.commit()
    return True


def main():
    provider=configured_provider()
    if provider is None: raise SystemExit('AI_PROVIDER_UNCONFIGURED: verified DSLab adapter required')
    settings=Settings.from_env()
    with connect() as conn:
        if not conn.execute('SELECT pg_try_advisory_lock(107198011) AS locked').fetchone()['locked']: raise SystemExit('Another worker is active')
        conn.commit()
        while True:
            step(conn,provider,settings); time.sleep(1)

if __name__=='__main__': main()
