"""Release boundaries on real isolated SQL; no GPU calls or production changes."""
import copy
import json
from dataclasses import replace
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
import psycopg
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.scheme_catalog import release_catalog
from app.trash import purge
from app.erasure import erase_generation, drain_files
from scripts.production_catalog import checked, decision_template, check_decision, install
from scripts.privacy_maintenance import export_ledger, replay
from scripts.ai_worker import step
from test_ai_mvp import released,register,request


def connect(settings):return psycopg.connect(settings.database_url,row_factory=psycopg.rows.dict_row)

def test_catalog110_public_import_replay_conflicts_and_accepted_subset(prepared,tmp_path):
    settings,_=prepared;root=Path(__file__).resolve().parents[1]/'catalog-input'
    data,report=checked(root);decision=decision_template(data,report)
    import os,shutil
    original_root=root;root=tmp_path/'catalog';root.mkdir()
    for name in report['files']:
        dst=root/name;dst.parent.mkdir(parents=True,exist_ok=True);os.link(original_root/name,dst)
    shutil.copyfile(original_root/'owner-accepted-2026-10-08.json',root/'owner-accepted-2026-10-08.json')
    with pytest.raises(RuntimeError):check_decision(decision,data,report)
    # Explicit synthetic approval, solely inside isolated test schema.
    decision.update(approved=True,approvedBy='isolated_test_only',approvedAt=datetime.now(timezone.utc).isoformat(),evidence='synthetic_scope_test_not_owner_decision')
    with connect(settings) as conn:
        before=conn.execute('SELECT count(*) n FROM users').fetchone()['n']
        assert install(conn,root,decision)['publicRealUniqueElements']==110
        assert install(conn,root,decision)['replay']
        assert conn.execute('SELECT count(*) n FROM users').fetchone()['n']==before
        conn.commit()
    import subprocess,sys,os
    decision_file=tmp_path/'decision.synthetic.json';decision_file.write_text(json.dumps(decision))
    environment=os.environ.copy();environment['DATABASE_URL']=settings.database_url
    installed=tmp_path/'installed'
    command=[sys.executable,'-m','scripts.production_catalog','apply','--input',str(root),'--storage-root',str(installed),'--decision',str(decision_file),'--designated-operation','isolated-synthetic-only']
    applied=subprocess.run(command,env=environment,capture_output=True,text=True)
    assert applied.returncode==0,applied.stderr
    assert json.loads(applied.stdout.splitlines()[-1])['replay']
    verified=subprocess.run([sys.executable,'-m','scripts.production_catalog','verify','--input',str(installed),'--storage-root',str(installed),'--decision',str(decision_file)],env=environment,capture_output=True,text=True)
    assert verified.returncode==0,verified.stderr
    assert json.loads(verified.stdout)['publicRealUniqueElements']==110
    public=replace(settings,storage_root=root,local_catalog=False,allow_fixtures=False)
    with TestClient(create_app(public)) as client:
        reg=client.get('/api/composition-schemes').json()
        assert len(reg['schemes'])==24 and reg['registeredSchemeCount']==61
        assert reg['acceptedCoveredElementCount']==62 and len(reg['elementsWithoutAcceptedScheme'])==48
        assert all(s['reviewStatus']=='owner_accepted_2026_10_13' and s['available'] for s in reg['schemes'])
        assert client.get('/api/capabilities').json()['realUniqueElements']==110
        register(client)
        request_body=json.loads((Path(__file__).resolve().parents[1]/'app/ai-assets/f10-wreath.recipe.json').read_text())['request']
        made=client.post('/api/generations',json=request_body)
        assert made.status_code==201,made.text
        generation=made.json()['generation']
        assert client.get(generation['imageUrl']).status_code==200
        assert generation['recipe']['schemeId']=='f10-wreath'
        assert generation['id'] in [g['id'] for g in client.get('/api/generations').json()['items']]
        bad={'mode':'flat','selections':{'renderer':'composition-v2','schemeId':'f01-directed','style':'heritage','composition':'border','palette':'emerald','usage':'web','elementCodes':['TP-E-008']}}
        response=client.post('/api/composition-preflight',json=bad)
        assert response.status_code==422 and response.json()['error']['code']=='SCHEME_NOT_RELEASED'
    with connect(settings) as conn:
        conn.execute("UPDATE elements SET description='drift' WHERE code=%s",(decision['elementCodes'][0],))
        with pytest.raises(RuntimeError,match='changed'):install(conn,root,decision)
        conn.rollback()


def test_ai_fk_unlink_retry_sessions_and_offline_restore(released,tmp_path,monkeypatch):
    settings,provider=released
    with TestClient(create_app(settings)) as client:
        register(client)
        gid=client.post('/api/generations',json=request()).json()['generation']['id']
        with connect(settings) as conn:
            step(conn,provider,settings);step(conn,provider,settings)
            row=conn.execute('SELECT * FROM generations WHERE id=%s',(gid,)).fetchone()
        path=settings.storage_root/row['result_path']
        client.delete('/api/generations/'+gid)
        with connect(settings) as conn:
            conn.execute("UPDATE generations SET deleted_at=now()-interval '8 days' WHERE id=%s",(gid,))
            conn.execute("UPDATE sessions SET expires_at=now()-interval '1 second' WHERE user_id=%s",(row['user_id'],))
        original=Path.unlink
        def denied(p,*a,**kw):
            if p==path:raise PermissionError('synthetic')
            return original(p,*a,**kw)
        with monkeypatch.context() as patch:
            patch.setattr(Path,'unlink',denied);purge(settings)
        assert path.exists()
        with connect(settings) as conn:
            assert conn.execute('SELECT 1 FROM ai_jobs WHERE generation_id=%s',(gid,)).fetchone() is None
            assert conn.execute("SELECT state,attempts FROM storage_deletions WHERE path=%s",(row['result_path'],)).fetchone()['state']=='pending'
            assert conn.execute('SELECT 1 FROM sessions WHERE user_id=%s',(row['user_id'],)).fetchone() is None
            ledger=tmp_path/'erasure.json';assert len(export_ledger(conn,ledger))==64
            drain_files(conn,settings.storage_root)
        assert not path.exists()
        # Simulate offline restore of exactly the deleted row and file, then replay latest ledger.
        with connect(settings) as conn:
            conn.execute('INSERT INTO generations(id,user_id,status,result_path) OVERRIDING SYSTEM VALUE VALUES(%s,%s,%s,%s)',(gid,row['user_id'],'done',row['result_path']))
            path.write_bytes(b'restored stale file')
            replay(conn,json.loads(ledger.read_text()));conn.commit();drain_files(conn,settings.storage_root)
        assert not path.exists()
        assert client.get('/api/generations/'+gid).status_code==401
        assert provider.submissions==1


def test_hard_delete_during_poll_discards_late_output(released):
    settings,provider=released
    with TestClient(create_app(settings)) as client:
        register(client);gid=client.post('/api/generations',json=request()).json()['generation']['id']
        with connect(settings) as conn:step(conn,provider,settings)
        old_poll=provider.poll
        def poll(*a,**kw):
            with connect(settings) as other:
                row=other.execute('SELECT * FROM generations WHERE id=%s',(gid,)).fetchone()
                erase_generation(other,row,'account_closure')
            return old_poll(*a,**kw)
        provider.poll=poll
        provider.download=lambda *a,**kw:pytest.fail('Deleted result must not be downloaded')
        with connect(settings) as conn:
            step(conn,provider,settings)
            assert conn.execute('SELECT 1 FROM generations WHERE id=%s',(gid,)).fetchone() is None
            assert conn.execute('SELECT state FROM provider_deletions WHERE generation_id=%s',(gid,)).fetchone()['state']=='manual_required'
        assert client.get('/api/generations/'+gid+'/file').status_code==404


def test_delete_during_submit_retains_ack_without_resubmit(released):
    settings,provider=released;cloud_id=str(uuid4())
    with TestClient(create_app(settings)) as client:
        register(client);gid=client.post('/api/generations',json=request()).json()['generation']['id']
        def submit(*a,**kw):
            provider.submissions+=1
            with connect(settings) as other:
                row=other.execute('SELECT * FROM generations WHERE id=%s',(gid,)).fetchone()
                erase_generation(other,row,'account_closure')
            return cloud_id
        provider.submit=submit
        with connect(settings) as conn:
            step(conn,provider,settings);assert not step(conn,provider,settings)
            saved=conn.execute('SELECT * FROM provider_deletions WHERE generation_id=%s',(gid,)).fetchone()
            assert saved['provider_job_id']==cloud_id and not saved['submit_uncertain']
        assert provider.submissions==1


def test_account_block_local_erasure_and_restore_replay(released,tmp_path):
    from app.erasure import block_account,erase_account_local
    settings,provider=released
    with TestClient(create_app(settings)) as client:
        email,password=register(client);gid=client.post('/api/generations',json=request()).json()['generation']['id']
        user_id=int(client.get('/api/auth/me').json()['user']['id'])
        operation='isolated-test-'+uuid4().hex
        with connect(settings) as conn:
            step(conn,provider,settings)
            saved_user=conn.execute('SELECT * FROM users WHERE id=%s',(user_id,)).fetchone()
            block_account(conn,user_id,operation,'synthetic_legal_decision_not_owner_approval')
        assert client.get('/api/auth/me').status_code==401
        assert client.post('/api/auth/login',json={'email':email,'password':password}).status_code==401
        with connect(settings) as conn:
            erase_account_local(conn,operation);erase_account_local(conn,operation)
            assert conn.execute('SELECT 1 FROM users WHERE id=%s',(user_id,)).fetchone() is None
            assert conn.execute('SELECT 1 FROM ai_jobs WHERE generation_id=%s',(gid,)).fetchone() is None
            ledger=tmp_path/'latest-ledger.json';export_ledger(conn,ledger)
            # Offline copy restored an old user: replay removes it before public access.
            conn.execute('INSERT INTO users(id,email,password_hash) OVERRIDING SYSTEM VALUE VALUES(%s,%s,%s)',(user_id,email,saved_user['password_hash']))
            replay(conn,json.loads(ledger.read_text()))
            assert conn.execute('SELECT 1 FROM users WHERE id=%s',(user_id,)).fetchone() is None


def test_gpu_disabled_closes_new_admission_but_keeps_known_id_poll(released):
    settings,provider=released
    with TestClient(create_app(settings)) as client:
        register(client)
        gid=client.post('/api/generations',json=request()).json()['generation']['id']
        with connect(settings) as conn:step(conn,provider,settings)
        queued=client.post('/api/generations',json=request()).json()['generation']['id']
        offline=replace(settings,ai_mvp_enabled=False);provider.ready=False
        with connect(settings) as conn:
            step(conn,provider,offline)
            assert conn.execute('SELECT state FROM ai_jobs WHERE generation_id=%s',(gid,)).fetchone()['state']=='done'
            step(conn,provider,offline)
            assert conn.execute('SELECT error FROM generations WHERE id=%s',(queued,)).fetchone()['error']['code']=='AI_RELEASE_NOT_READY'
        assert provider.submissions==1
        assert client.post('/api/generations',json=request()).status_code==503
        assert client.get('/api/generations/'+gid+'/file').status_code==200
