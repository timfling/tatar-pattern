"""Real isolated PostgreSQL/flat; explicit synthetic AI only, no cloud requests."""
import hashlib
import json
import os
import shutil
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import psycopg
import pytest
from fastapi.testclient import TestClient
from app import guest
from app.main import create_app
from app.ai_provider import ProviderError
from scripts.ai_worker import step
from scripts.guest_maintenance import reset
from scripts.production_catalog import checked,decision_template,install
from test_ai_mvp import released,request


def db(settings):return psycopg.connect(settings.database_url,row_factory=psycopg.rows.dict_row)

def session(client):
    response=client.post('/api/guest/session',json={})
    assert response.status_code==200,response.text
    return response.json()['expiresAt']

def flat():
    body=json.loads((Path(__file__).resolve().parents[1]/'app/ai-assets/f10-wreath.recipe.json').read_text())['request']
    return {**body,'requestId':str(uuid4())}

@pytest.fixture(scope="module")
def real_guest(prepared,tmp_path_factory):
    tmp_path=tmp_path_factory.mktemp("guest-real-catalog")
    settings,_=prepared
    source=Path(__file__).resolve().parents[1]/'catalog-input'
    data,report=checked(source);decision=decision_template(data,report)
    decision.update(approved=True,approvedBy='isolated_only',approvedAt=datetime.now(timezone.utc).isoformat(),evidence='synthetic_test_scope_only')
    root=tmp_path/'storage';root.mkdir()
    for name in report['files']:
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);os.link(source/name,target)
    shutil.copyfile(source/'owner-accepted-2026-10-08.json',root/'owner-accepted-2026-10-08.json')
    with db(settings) as conn:install(conn,root,decision)
    return replace(settings,storage_root=root,public_guest_mode=True,allow_fixtures=False,local_catalog=False,guest_creates_per_minute=1000)

@pytest.fixture
def ai_guest(released,real_guest):
    settings,provider=released
    return replace(settings,storage_root=real_guest.storage_root,public_guest_mode=True,guest_gpu_budget=100,guest_creates_per_minute=1000),provider


def test_real_flat_two_guests_http_protection_and_strict_input(real_guest):
    settings=real_guest
    # A real, still valid legacy account cookie must not bypass guest/public mode.
    with TestClient(create_app(replace(settings,public_guest_mode=False))) as legacy:
        registered=legacy.post('/api/auth/register',json={'email':uuid4().hex+'@example.com','password':'isolated legacy password 2026'})
        assert registered.status_code==201
        old_cookie=legacy.cookies.get('tp_session')
        legacy_body=flat();legacy_body.pop('requestId')
        old_result=legacy.post('/api/generations',json=legacy_body)
        assert old_result.status_code==201,old_result.text
        old_id=old_result.json()['generation']['id']
    with db(settings) as conn:before=conn.execute('SELECT count(*) n FROM users').fetchone()['n']
    with TestClient(create_app(settings)) as a,TestClient(create_app(settings)) as b:
        expires=session(a);session(b)
        body=flat()
        assert a.post('/api/guest/preflight',json=body).status_code==200
        made=a.post('/api/guest/generations',json=body);assert made.status_code==201,made.text
        g=made.json()['generation'];gid=g['id']
        assert g['expiresAt']==expires and g['status']=='done'
        assert a.post('/api/guest/generations',json=body).json()['generation']['id']==gid
        assert a.post('/api/guest/generations',json={**body,'seed':body['seed']+1}).status_code==409
        second=b.post('/api/guest/generations',json=body);assert second.status_code==201,second.text
        assert second.json()['generation']['id']!=gid
        for fmt,mime in [('png','image/png'),('jpg','image/jpeg')]:
            url=f'/api/guest/generations/{gid}/file?format={fmt}&download=true'
            response=a.get(url);assert response.status_code==200
            assert response.headers['content-type']==mime and response.headers['cache-control']=='no-store'
            assert 'attachment' in response.headers['content-disposition']
            assert hashlib.sha256(response.content).hexdigest()==g['recipe']['outputSha256'][fmt]
            assert b.get(url).status_code==404
        assert b.get('/api/guest/generations/'+gid).status_code==404
        module_body=json.loads((Path(__file__).resolve().parents[1]/'app/ai-assets/f07-repeat.recipe.json').read_text())['request']
        module_body['requestId']=str(uuid4())
        module_response=a.post('/api/guest/generations',json=module_body)
        assert module_response.status_code==201,module_response.text
        module=module_response.json()['generation']['moduleUrl'];assert module
        assert a.get(module).status_code==200 and b.get(module).status_code==404
        assert a.get('/api/composition-schemes').json()['acceptedSchemeCount']==24
        assert a.get('/api/capabilities').json()['profile'] is False
        assert a.post('/api/guest/session',json={}).json()['expiresAt']==expires
        cookie=a.cookies.get(guest.COOKIE)
        assert len(cookie)==43
        with TestClient(create_app(settings)) as stranger:
            stranger.cookies.set('tp_session',old_cookie)
            assert stranger.get('/api/generations/'+old_id+'/file').status_code==404
            assert stranger.get('/api/guest/generations/'+old_id).status_code==401
            assert stranger.get('/api/guest/generations/'+gid).status_code==401
            stranger.cookies.set(guest.COOKIE,'x'*43)
            assert stranger.get(g['imageUrl']).status_code==401
        for field in ['email','password','profile','avatar','projectId','prompt','title','notes','rating']:
            r=a.post('/api/guest/generations',json={**body,field:'forbidden'})
            assert r.status_code==422,(field,r.text)
            assert 'forbidden' not in r.text
        assert a.post('/api/guest/generations',content='x'*16385,headers={'content-type':'application/json'}).status_code==413
        for method,path in [('POST','/api/auth/register'),('POST','/api/auth/login'),('GET','/api/auth/me'),('PATCH','/api/auth/profile'),('GET','/api/projects'),('GET','/api/generations'),('GET','/api/generations/'+gid+'/file'),('POST','/api/generations/'+gid+'/restore'),('GET','/api/trash'),('POST','/api/composition-preflight')]:
            assert a.request(method,path,json={} if method!='GET' else None).status_code==404,path
    with db(settings) as conn:
        assert conn.execute('SELECT count(*) n FROM users').fetchone()['n']==before
        row=conn.execute('SELECT * FROM generations WHERE id=%s',(gid,)).fetchone()
        assert row['user_id'] is None and row['project_id'] is None
        token=conn.execute('SELECT token_hash FROM guest_processes WHERE id=%s',(row['guest_process_id'],)).fetchone()['token_hash']
        assert token==hashlib.sha256(cookie.encode()).hexdigest() and token!=cookie


def test_expiry_no_sliding_cleanup_retry_and_orphans(real_guest,monkeypatch):
    settings=real_guest
    with TestClient(create_app(settings)) as client:
        session(client);g=client.post('/api/guest/generations',json=flat()).json()['generation'];gid=g['id']
        with db(settings) as conn:
            row=conn.execute('SELECT * FROM generations WHERE id=%s',(gid,)).fetchone()
            conn.execute("UPDATE generations SET guest_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",(gid,))
        assert client.get(g['imageUrl']).status_code==404
        path=settings.storage_root/row['result_path'];original=Path.unlink
        def denied(p,*args,**kw):
            if p==path:raise PermissionError('synthetic')
            return original(p,*args,**kw)
        with monkeypatch.context() as patch:
            patch.setattr(Path,'unlink',denied);guest.clean(settings)
        assert path.exists()
        with db(settings) as conn:
            assert not conn.execute('SELECT 1 FROM generations WHERE id=%s',(gid,)).fetchone()
            assert conn.execute('SELECT state FROM storage_deletions WHERE path=%s',(row['result_path'],)).fetchone()['state']=='pending'
        guest.clean(settings);assert not path.exists()
        orphan=settings.storage_root/'guest-results/orphan.tmp';orphan.write_bytes(b'stale')
        os.utime(orphan,(0,0));guest.clean(settings);assert not orphan.exists()
        expired_orphan=settings.storage_root/'guest-results/1000000000000000-uncommitted.png'
        expired_orphan.write_bytes(b'fresh mtime but original expiry elapsed')
        guest.clean(settings);assert not expired_orphan.exists()
        with db(settings) as conn:
            conn.execute("UPDATE guest_processes SET created_at=now()-interval '25 hours',expires_at=now()-interval '1 hour' WHERE id=%s",(row['guest_process_id'],))
        assert client.get('/api/guest/generations/'+gid).status_code==401
        guest.clean(settings)
        with db(settings) as conn:assert not conn.execute('SELECT 1 FROM guest_processes WHERE id=%s',(row['guest_process_id'],)).fetchone()


def test_ai_unavailable_no_fallback(real_guest):
    with TestClient(create_app(real_guest)) as client:
        session(client)
        for endpoint in ['preflight','generations']:
            response=client.post('/api/guest/'+endpoint,json=request())
            assert response.status_code==503 and response.json()['error']['code']=='AI_UNAVAILABLE'


def test_mock_ai_retry_restart_budget_and_expiry(ai_guest):
    settings,provider=ai_guest
    with TestClient(create_app(settings)) as client:
        session(client);body=request()
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda _:client.post('/api/guest/generations',json=body),range(2)))
        assert all(r.status_code==201 for r in responses),[r.text for r in responses]
        gid=responses[0].json()['generation']['id'];assert responses[1].json()['generation']['id']==gid
        with db(settings) as conn:
            provider_request_id=conn.execute('SELECT provider_request_id FROM ai_jobs WHERE generation_id=%s',(gid,)).fetchone()['provider_request_id']
            assert provider_request_id!=__import__('uuid').UUID(body['requestId'])
        original_submit=provider.submit
        def checked_submit(payload,*,request_id,timeout):
            assert __import__('uuid').UUID(request_id)==provider_request_id
            return original_submit(payload,request_id=request_id,timeout=timeout)
        provider.submit=checked_submit
        with db(settings) as conn:step(conn,provider,settings)
        with db(settings) as conn:step(conn,provider,settings)
        assert provider.submissions==1
        provider.submit=original_submit
        assert client.get('/api/guest/generations/'+gid+'/file?format=jpg').status_code==200
        with db(settings) as conn:
            used=conn.execute("SELECT used FROM guest_budget WHERE key='gpu-total'").fetchone()['used']
        with TestClient(create_app(replace(settings,guest_gpu_budget=used))) as capped:
            session(capped);assert capped.post('/api/guest/generations',json=request()).json()['error']['code']=='AI_BUDGET_EXHAUSTED'
        with db(settings) as conn:
            conn.execute("UPDATE generations SET guest_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",(gid,))
        assert client.get('/api/guest/generations/'+gid+'/file').status_code==404
        guest.clean(settings)


def test_mock_timeout_retry_does_not_submit_twice(ai_guest):
    settings,provider=ai_guest
    def uncertain(*args,**kw):
        provider.submissions+=1
        raise ProviderError('synthetic_timeout',definitive=False)
    provider.submit=uncertain
    with TestClient(create_app(settings)) as client:
        session(client);body=request();g=client.post('/api/guest/generations',json=body).json()['generation'];gid=g['id']
        with db(settings) as conn:step(conn,provider,settings);step(conn,provider,settings)
        assert client.post('/api/guest/generations',json=body).json()['generation']['error']['code']=='AI_SUBMISSION_UNCERTAIN'
        assert provider.submissions==1
        with db(settings) as conn:conn.execute("UPDATE generations SET guest_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",(gid,))
        guest.clean(settings)
        with db(settings) as conn:
            trace=conn.execute('SELECT * FROM guest_reconciliations WHERE generation_id=%s',(gid,)).fetchone()
            assert trace['submit_uncertain'] and trace['provider_job_id'] is None
            assert set(trace)=={'provider_request_id','generation_id','provider','provider_job_id','submit_uncertain','expires_at','confirmation_ref'}
            conn.execute("UPDATE guest_reconciliations SET expires_at=clock_timestamp()-interval '1 second' WHERE generation_id=%s",(gid,))
        guest.clean(settings)
        with db(settings) as conn:assert not conn.execute('SELECT 1 FROM guest_reconciliations WHERE generation_id=%s',(gid,)).fetchone()

@pytest.mark.parametrize('phase',['submit','poll'])
def test_mock_late_ack_done_no_resurrection(ai_guest,phase):
    settings,provider=ai_guest
    with TestClient(create_app(settings)) as client:
        session(client);g=client.post('/api/guest/generations',json=request()).json()['generation'];gid=g['id']
        def expire():
            with db(settings) as conn:conn.execute("UPDATE generations SET guest_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",(gid,))
            guest.clean(settings)
        if phase=='submit':
            old=provider.submit
            def submit(*a,**kw):expire();return old(*a,**kw)
            provider.submit=submit
        else:
            with db(settings) as conn:step(conn,provider,settings)
            old=provider.poll
            def poll(*a,**kw):expire();return old(*a,**kw)
            provider.poll=poll
            provider.download=lambda *a,**kw:pytest.fail('Expired output must not be downloaded')
        with db(settings) as conn:
            step(conn,provider,settings)
            assert not step(conn,provider,settings)
            assert not conn.execute('SELECT 1 FROM generations WHERE id=%s',(gid,)).fetchone()
            assert conn.execute('SELECT provider_job_id FROM guest_reconciliations WHERE generation_id=%s',(gid,)).fetchone()['provider_job_id']
        assert client.get('/api/guest/generations/'+gid).status_code==404
        assert provider.submissions==1


def test_offline_restored_guest_reset_no_access_or_resubmit(ai_guest,monkeypatch):
    settings,provider=ai_guest
    with TestClient(create_app(settings)) as client:
        session(client);gid=client.post('/api/guest/generations',json=request()).json()['generation']['id']
        with db(settings) as conn:
            before=conn.execute('SELECT count(*) n FROM elements').fetchone()['n']
            # Simulated restored submitting job: no provider id yet, must never resubmit.
            conn.execute("UPDATE ai_jobs SET state='submitting' WHERE generation_id=%s",(gid,))
        root=settings.storage_root/'guest-results';root.mkdir(exist_ok=True)
        orphan=root/'restored.tmp';orphan.write_bytes(b'restored file')
        monkeypatch.setenv('DATABASE_URL',settings.database_url)
        import subprocess,sys
        environment=os.environ.copy()
        environment.update(DATABASE_URL=settings.database_url,STORAGE_ROOT=str(settings.storage_root),TP_ENVIRONMENT='isolated_test')
        result=subprocess.run([sys.executable,'-m','scripts.guest_maintenance','reset-restored','--offline-restore','--designated-operation','isolated-restore-test'],env=environment,capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        assert json.loads(result.stdout.splitlines()[-1])['guestProcesses']==0
        reset(settings)
        assert not orphan.exists()
        assert client.get('/api/guest/generations/'+gid).status_code==401
        with db(settings) as conn:
            assert not step(conn,provider,settings)
            assert conn.execute('SELECT count(*) n FROM elements').fetchone()['n']==before
            assert not conn.execute('SELECT 1 FROM guest_processes').fetchone()
            assert not conn.execute('SELECT 1 FROM generations WHERE guest_process_id IS NOT NULL').fetchone()
            assert conn.execute('SELECT 1 FROM guest_reconciliations WHERE generation_id=%s',(gid,)).fetchone()
        assert provider.submissions==0


def test_mock_server_concurrency_and_global_rate(ai_guest):
    settings,provider=ai_guest
    with TestClient(create_app(settings)) as client:
        session(client)
        first=request();assert client.post('/api/guest/generations',json=first).status_code==201
        assert client.post('/api/guest/generations',json=request()).status_code==201
        assert client.post('/api/guest/generations',json=request()).json()['error']['code']=='GUEST_CONCURRENCY_LIMIT'
        assert client.post('/api/guest/generations',json=first).status_code==201
        with db(settings) as conn:
            while step(conn,provider,settings):pass
        assert provider.submissions==2
    with TestClient(create_app(replace(settings,guest_creates_per_minute=1))) as capped:
        assert capped.post('/api/guest/session',json={}).json()['error']['code']=='GUEST_RATE_LIMIT'


def test_real_loopback_http_smoke(real_guest):
    import httpx,socket,subprocess,sys,time
    settings=real_guest
    with socket.socket() as bound:
        bound.bind(('127.0.0.1',0));port=bound.getsockname()[1]
    environment=os.environ.copy()
    environment.update(DATABASE_URL=settings.database_url,STORAGE_ROOT=str(settings.storage_root),PUBLIC_GUEST_MODE='true',COOKIE_SECURE='false',AI_MVP_ENABLED='false',GUEST_GPU_BUDGET='0',GUEST_CREATES_PER_MINUTE='1000')
    process=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port',str(port),'--no-access-log'],env=environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=15) as client:
            for _ in range(100):
                try:
                    if client.get('/api/health').status_code==200:break
                except httpx.TransportError:pass
                time.sleep(.05)
            else:pytest.fail('Isolated HTTP server failed to start')
            response=client.post('/api/guest/session',json={});assert response.status_code==200
            cookie=response.headers['set-cookie'].lower()
            assert 'httponly' in cookie and 'samesite=strict' in cookie and 'path=/api/guest' in cookie
            expires=response.json()['expiresAt'];body=flat()
            assert client.post('/api/guest/preflight',json=body).status_code==200
            made=client.post('/api/guest/generations',json=body);assert made.status_code==201,made.text
            g=made.json()['generation'];gid=g['id']
            assert client.get('/api/guest/generations/'+gid).status_code==200
            report={'transport':'real_loopback_http','catalog':'real110_isolated_only','generationId':gid,'expiresAt':expires,'cloudSubmits':0,'accountMe':client.get('/api/auth/me').status_code,'artifacts':{}}
            for fmt in ['png','jpg']:
                result=client.get(f'/api/guest/generations/{gid}/file?format={fmt}&download=true');assert result.status_code==200
                report['artifacts'][fmt]={'status':result.status_code,'sha256':hashlib.sha256(result.content).hexdigest(),'bytes':len(result.content)}
            path=Path(__file__).resolve().parents[1]/'local-test/guest-release-2026-10-19/http-smoke.json'
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2))
            assert client.post('/api/guest/session',json={}).json()['expiresAt']==expires
            assert 'set-cookie' not in client.post('/api/guest/session',json={}).headers
    finally:
        process.terminate();process.wait(timeout=10)
