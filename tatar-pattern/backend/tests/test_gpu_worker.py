"""New worker recovery/drain paths; isolated prepared PostgreSQL fixture."""
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import psycopg

from app.ai_provider import CloudStatus, ProviderError
from app.main import create_app
from scripts.ai_worker import run, step, Shutdown
from test_ai_mvp import released, request, register


def connection(settings):
    return psycopg.connect(settings.database_url, row_factory=psycopg.rows.dict_row)


def test_drain_preserves_queued_and_finishes_known_id(released, monkeypatch):
    settings, provider = released
    with TestClient(create_app(settings)) as client:
        register(client)
        accepted = client.post('/api/generations', json=request()).json()['generation']['id']
        with connection(settings) as conn:
            step(conn, provider, settings)
        queued = client.post('/api/generations', json=request()).json()['generation']['id']
        stop = Shutdown(); stop.set()
        monkeypatch.setattr('scripts.ai_worker.time.sleep', lambda _: None)
        provider.poll = lambda *a, **kw: CloudStatus('done', metadata={'workflowVersion':'synthetic-unverified'})
        with connection(settings) as conn:
            run(conn, provider, settings, stop)
            rows = {str(r['generation_id']):r for r in conn.execute('SELECT * FROM ai_jobs').fetchall()}
            assert rows[accepted]['state'] == 'done'
            assert rows[queued]['state'] == 'queued' and rows[queued]['provider_job_id'] is None
            saved = conn.execute('SELECT params,result_path FROM generations WHERE id=%s', (accepted,)).fetchone()
            assert saved['params']['recipe']['gpuMetadata'] == {'workflowVersion':'synthetic-unverified'}
            assert saved['params']['recipe']['description']['basis'] == 'requested_only'
            raw = (settings.storage_root/saved['result_path']).read_bytes()
            import hashlib
            assert hashlib.sha256(raw).hexdigest() == saved['params']['recipe']['providerOutputSha256']
            assert saved['params']['recipe']['outputSha256']['png'] == saved['params']['recipe']['providerOutputSha256']
            conn.execute("UPDATE ai_jobs SET state='failed' WHERE generation_id=%s", (queued,))
        assert provider.submissions == 1


def test_known_id_even_in_submitting_resumes_without_ready(released):
    settings, provider = released
    with TestClient(create_app(settings)) as client:
        register(client)
        gid = client.post('/api/generations', json=request()).json()['generation']['id']
        with connection(settings) as conn:
            conn.execute("UPDATE ai_jobs SET state='submitting',provider_job_id=%s WHERE generation_id=%s", (str(uuid4()), gid));conn.commit()
            provider.ready = False
            step(conn, provider, settings, allow_new=False)
            assert conn.execute('SELECT state FROM ai_jobs WHERE generation_id=%s', (gid,)).fetchone()['state'] == 'done'
        assert provider.submissions == 0


def test_submit_rejection_uncertainty_and_ack_recovery(released):
    settings, provider = released
    with TestClient(create_app(settings)) as client:
        register(client)
        for error, expected in [(ProviderError('AI_GPU_QUEUE_FULL', definitive=True), 'AI_GPU_QUEUE_FULL'),
                                (ProviderError('AI_GPU_TRANSPORT_ERROR'), 'AI_SUBMISSION_UNCERTAIN'),
                                (ProviderError('AI_GPU_VERSION_MISMATCH', job_id=str(uuid4())), None)]:
            gid = client.post('/api/generations', json=request()).json()['generation']['id']
            def submit(*a, **kw): raise error
            provider.submit = submit
            with connection(settings) as conn:
                step(conn, provider, settings)
                job = conn.execute('SELECT * FROM ai_jobs WHERE generation_id=%s', (gid,)).fetchone()
                if expected:
                    assert job['state'] == 'failed'
                    assert conn.execute('SELECT error FROM generations WHERE id=%s', (gid,)).fetchone()['error']['code'] == expected
                    assert not step(conn, provider, settings)
                else:
                    assert job['state'] == 'polling' and job['provider_job_id'] == error.job_id
                    step(conn, provider, settings, allow_new=False)
                    assert conn.execute('SELECT state FROM ai_jobs WHERE generation_id=%s', (gid,)).fetchone()['state'] == 'done'


def test_expired_drain_persists_resumable_state(released, monkeypatch):
    settings, provider = released
    with TestClient(create_app(settings)) as client:
        register(client)
        gid = client.post('/api/generations', json=request()).json()['generation']['id']
        with connection(settings) as conn:
            conn.execute("UPDATE ai_jobs SET state='polling',provider_job_id=%s WHERE generation_id=%s", (str(uuid4()),gid));conn.commit()
            ticks = iter([0, 931])
            monkeypatch.setattr('scripts.ai_worker.time', SimpleNamespace(monotonic=lambda: next(ticks)))
            stop = Shutdown(); stop.set()
            run(conn, provider, settings, stop)
            assert conn.execute('SELECT state FROM ai_jobs WHERE generation_id=%s',(gid,)).fetchone()['state'] == 'polling'
            saved = conn.execute('SELECT params FROM generations WHERE id=%s',(gid,)).fetchone()['params']
            assert saved['recipe']['workerShutdown'] == {'state':'poll_resume_required','gpuCancelled':False}
            conn.execute("UPDATE ai_jobs SET state='failed' WHERE generation_id=%s",(gid,))
        assert provider.submissions == 0
