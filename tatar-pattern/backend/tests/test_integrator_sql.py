"""Two real connections; assigned isolated DB and mandatory prepared backup only."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from app import guest
from scripts import ai_worker
from test_ai_mvp import request, released


def connection(settings):
    return psycopg.connect(settings.database_url,row_factory=psycopg.rows.dict_row)


@pytest.fixture
def queued(released):
    settings,provider=released
    settings=replace(settings,public_guest_mode=True,guest_gpu_budget=1000,guest_creates_per_minute=1000)
    with TestClient(__import__('app.main',fromlist=['create_app']).create_app(settings)) as client:
        assert client.post('/api/guest/session',json={}).status_code==200
        response=client.post('/api/guest/generations',json=request())
        assert response.status_code==201,response.text
        gid=response.json()['generation']['id']
    with connection(settings) as conn:
        job=conn.execute('SELECT * FROM ai_jobs WHERE generation_id=%s',(gid,)).fetchone()
    return settings,provider,job


def wait_blocked(observer,pid):
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        if observer.execute('SELECT cardinality(pg_blocking_pids(%s)) n',(pid,)).fetchone()['n']:
            return
        time.sleep(.01)
    raise AssertionError('Expected SQL wait was not reached')


@pytest.mark.parametrize('known',[False,True])
def test_cleanup_and_fail_share_lock_order_and_preserve_reconciliation(queued,known):
    settings,provider,job=queued
    cloud=str(uuid4()) if known else None
    with connection(settings) as cleanup,connection(settings) as worker:
        cleanup.execute("UPDATE ai_jobs SET state=%s,provider_job_id=%s WHERE generation_id=%s",('polling' if known else 'submitting',cloud,job['generation_id']))
        cleanup.execute("UPDATE generations SET guest_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",(job['generation_id'],))
        cleanup.commit()
        worker.execute("SET lock_timeout='2s'")
        worker.execute("SET statement_timeout='3s'")
        row=cleanup.execute('SELECT * FROM generations WHERE id=%s FOR UPDATE',(job['generation_id'],)).fetchone()
        with ThreadPoolExecutor(1) as pool:
            waiting=pool.submit(ai_worker.fail,worker,job,'AI_SUBMISSION_UNCERTAIN')
            wait_blocked(cleanup,worker.info.backend_pid)
            # This used to wait on the worker's ai_jobs lock: now it completes.
            cleanup.execute("SET lock_timeout='300ms'")
            guest.erase(cleanup,row)
            cleanup.commit()
            waiting.result(timeout=3)
        trace=cleanup.execute('SELECT * FROM guest_reconciliations WHERE provider_request_id=%s',(job['provider_request_id'],)).fetchone()
        assert trace['provider_job_id']==cloud and trace['submit_uncertain']==(not known)
        assert not cleanup.execute('SELECT 1 FROM generations WHERE id=%s',(job['generation_id'],)).fetchone()
        assert not cleanup.execute('SELECT 1 FROM ai_jobs WHERE generation_id=%s',(job['generation_id'],)).fetchone()
        assert not ai_worker.step(worker,provider,settings) and provider.submissions==0
        print(json.dumps({'after':'cleanup+fail','knownId':known,'refsPreservedInTrace':True,'deadlock':False,'submits':0}))


@pytest.mark.parametrize('known',[False,True])
def test_run_survives_real_lock_timeout_without_resubmit(queued,known,monkeypatch,capsys):
    settings,provider,job=queued
    cloud=str(uuid4()) if known else None
    with connection(settings) as locker,connection(settings) as worker:
        locker.execute("UPDATE ai_jobs SET state=%s,provider_job_id=%s,deadline=now()-interval '1 second' WHERE generation_id=%s",('polling' if known else 'submitting',cloud,job['generation_id']))
        locker.commit()
        locker.execute('SELECT * FROM generations WHERE id=%s FOR UPDATE',(job['generation_id'],))
        worker.execute("SET lock_timeout='100ms'");worker.commit()
        stop=ai_worker.Shutdown()
        monkeypatch.setattr(guest,'clean',lambda _:0)
        ticks=[]
        def advance(_):
            ticks.append(1)
            if len(ticks)==1:
                saved=locker.execute('SELECT * FROM ai_jobs WHERE generation_id=%s',(job['generation_id'],)).fetchone()
                assert saved['provider_request_id']==job['provider_request_id'] and saved['provider_job_id']==cloud
                locker.commit()
            else:stop.set()
        monkeypatch.setattr(ai_worker,'time',SimpleNamespace(monotonic=time.monotonic,sleep=advance))
        ai_worker.run(worker,provider,settings,stop)
        saved=locker.execute('SELECT * FROM ai_jobs WHERE generation_id=%s',(job['generation_id'],)).fetchone()
        assert saved['state']=='failed' and saved['provider_request_id']==job['provider_request_id'] and saved['provider_job_id']==cloud
        assert provider.submissions==0
        assert 'AI_WORKER_SQL_DEFERRED: LockNotAvailable' in capsys.readouterr().out
        print(json.dumps({'after':'run lock_timeout','knownId':known,'workerSurvived':True,'refsPreserved':True,'submits':0}))


def test_run_survives_real_deadlock_without_losing_known_job(queued,monkeypatch,capsys):
    settings,provider,job=queued
    cloud=str(uuid4())
    with connection(settings) as locker,connection(settings) as worker:
        locker.execute("UPDATE ai_jobs SET state='polling',provider_job_id=%s,deadline=now()-interval '1 second' WHERE generation_id=%s",(cloud,job['generation_id']))
        locker.commit()
        locker.execute("SET deadlock_timeout='10s'")
        locker.execute("SET lock_timeout='3s'")
        locker.execute('SELECT * FROM ai_jobs WHERE generation_id=%s FOR UPDATE',(job['generation_id'],))
        worker.execute("SET deadlock_timeout='50ms'");worker.execute("SET lock_timeout='2s'");worker.commit()
        stop=ai_worker.Shutdown();released=__import__('threading').Event();ticks=[]
        monkeypatch.setattr(guest,'clean',lambda _:0)
        def advance(_):
            ticks.append(1)
            assert released.wait(3)
            if len(ticks)>1:stop.set()
        monkeypatch.setattr(ai_worker,'time',SimpleNamespace(monotonic=time.monotonic,sleep=advance))
        with ThreadPoolExecutor(1) as pool:
            running=pool.submit(ai_worker.run,worker,provider,settings,stop)
            # Worker holds generations, waits for this deliberately inverted
            # test transaction's ai_jobs lock. This is an injected SQL fault.
            wait_blocked(locker,worker.info.backend_pid)
            locker.execute('SELECT * FROM generations WHERE id=%s FOR UPDATE',(job['generation_id'],))
            locker.commit();released.set()
            running.result(timeout=4)
        saved=locker.execute('SELECT * FROM ai_jobs WHERE generation_id=%s',(job['generation_id'],)).fetchone()
        assert saved['state']=='failed' and saved['provider_request_id']==job['provider_request_id'] and saved['provider_job_id']==cloud
        assert provider.submissions==0
        assert 'AI_WORKER_SQL_DEFERRED: DeadlockDetected' in capsys.readouterr().out
        print(json.dumps({'after':'injected real deadlock','workerSurvived':True,'knownIdPreserved':True,'submits':0}))


def test_submit_failure_sql_timeout_keeps_durable_request_without_resubmit(queued,monkeypatch,capsys):
    """The queued submit error branch is outside the poll exception handler."""
    from app.ai_provider import ProviderError
    settings,provider,job=queued
    with connection(settings) as locker,connection(settings) as worker:
        worker.execute("SET lock_timeout='100ms'");worker.commit()
        submitted=[]
        def uncertain(payload,*,request_id,timeout):
            submitted.append(request_id)
            locker.execute('SELECT id FROM generations WHERE id=%s FOR UPDATE',(job['generation_id'],))
            raise ProviderError('synthetic_submit_timeout')
        provider.submit=uncertain
        monkeypatch.setattr(guest,'clean',lambda _:0)
        stop=ai_worker.Shutdown();ticks=[]
        def advance(_):
            ticks.append(1)
            if len(ticks)==1:
                saved=locker.execute('SELECT * FROM ai_jobs WHERE generation_id=%s',(job['generation_id'],)).fetchone()
                assert saved['state']=='submitting' and saved['provider_job_id'] is None
                assert str(saved['provider_request_id'])==submitted[0]
                locker.commit()
            else:stop.set()
        monkeypatch.setattr(ai_worker,'time',SimpleNamespace(monotonic=time.monotonic,sleep=advance))
        ai_worker.run(worker,provider,settings,stop)
        saved=locker.execute('SELECT * FROM ai_jobs WHERE generation_id=%s',(job['generation_id'],)).fetchone()
        assert saved['state']=='failed' and saved['provider_request_id']==job['provider_request_id'] and saved['provider_job_id'] is None
        assert submitted==[str(job['provider_request_id'])]
        assert 'AI_WORKER_SQL_DEFERRED: LockNotAvailable' in capsys.readouterr().out
        print(json.dumps({'after':'submit failure plus real SQL timeout','mockSubmits':1,'resubmits':0,'durableRequestPreserved':True}))
