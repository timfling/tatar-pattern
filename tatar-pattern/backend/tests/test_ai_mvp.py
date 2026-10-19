"""Local contract/queue tests. Synthetic provider is never configured in runtime."""
import hashlib
import io
import json
from dataclasses import replace
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError
from psycopg.types.json import Jsonb

from app import ai_catalog
from app.ai_provider import CloudStatus
from app.config import Settings
from app.errors import APIError
from app.main import create_app
from app.models import Generate
from scripts.ai_worker import step


def request(**kwargs):
    return {'mode':'ai','ai':{'baseId':'f10-wreath','ornamentStyle':'graphic','profileVersion':'2026-10-18.local-v1'},'requestId':str(uuid4()),'seed':20261008,**kwargs}


def test_catalog_exports_and_closed_release(tmp_path):
    settings=Settings('unused',tmp_path)
    data=ai_catalog.catalog_response(settings,None)
    assert len(data['bases'])==15 and not data['available']
    assert all(not s['available'] for b in data['bases'] for s in b['styles'])
    assert len({b['id'] for b in data['bases']})==15
    for b in ai_catalog.document()['bases']:
        assert b['ownerStatus']=='owner_accepted_2026_10_13'
        with Image.open(ai_catalog.asset_file(b)) as im:
            assert im.mode=='RGB' and im.size==(1024,1024)
        r=json.loads(ai_catalog.asset_file(b,'recipe').read_text())
        assert r['recipe']['schemeId']==b['id']
        assert r['export']['sha256']==b['sha256']
    assert ai_catalog.find_base('f24-wreath')['palette']['background']!='#f3ebdb'
    assert ai_catalog.find_base('f10-directed')['palette']['background']!='#f3ebdb'
    assert ai_catalog.find_base('f07-repeat')['aiSeamless'] is False


def test_ai_validation_and_profiles():
    assert Generate.model_validate(request()).ai.ornamentStyle=='graphic'
    for mutation,code in [({'prompt':'добавь цветы'},'AI_PROMPT_UNSUPPORTED'),({'selections':{'style':'modern','composition':'border','palette':'leather','usage':'web'}},'AI_SELECTIONS_UNSUPPORTED'),({'requestId':None},'AI_SELECTION_REQUIRED')]:
        with pytest.raises(APIError) as exc:Generate.model_validate(request(**mutation))
        assert exc.value.payload['error']['code']==code
    for extra in [{'strength':.99},{'steps':1000},{'palette':'red'},{'prompt':'x'}]:
        value=request();value['ai'].update(extra)
        with pytest.raises(ValidationError):Generate.model_validate(value)
    with pytest.raises(APIError) as exc:ai_catalog.select_profile('f10-wreath','graphic','stale')
    assert exc.value.status==409
    with pytest.raises(APIError) as exc:ai_catalog.select_profile('f17-wreath','textured','new')
    assert exc.value.payload['error']['code']=='AI_COMBINATION_UNAVAILABLE'
    assert ai_catalog.select_profile('f14-directed','textured','2026-10-18.local-v1')[1]['steps']==100


class SyntheticProvider:
    name='explicit-local-test'
    model_version='synthetic-not-GPU'
    ready=True
    contract_version=ai_catalog.TASK_SCHEMA
    def __init__(self):self.submissions=0;self.invalid=False
    def submit(self,payload,*,request_id,timeout):
        assert payload['schemaVersion']==self.contract_version
        assert 'prompt' not in payload and 'selections' not in payload
        assert payload['inputArtifact']['sha256']==ai_catalog.find_base(payload['baseId'])['sha256']
        self.submissions+=1
        return 'synthetic-'+request_id
    def poll(self,job_id,*,timeout):return CloudStatus('done')
    def download(self,job_id,*,timeout,max_bytes):
        buf=io.BytesIO();Image.new('RGB',(64,64) if self.invalid else (1024,1024),(25,50,75)).save(buf,format='PNG');return buf.getvalue()


@pytest.fixture
def released(prepared,tmp_path,monkeypatch):
    # Release flags apply only to temporary JSON in this test, never repository files.
    original=ai_catalog.ASSETS
    doc=ai_catalog.document()
    for b in doc['bases']:
        b['externalTransferApproved']=True
        (tmp_path/b['image']).symlink_to(original/b['image'])
        (tmp_path/b['recipe']).symlink_to(original/b['recipe'])
    # Containment check requires real files under the test root, not symlinks.
    for b in doc['bases']:
        for kind in ['image','recipe']:
            p=tmp_path/b[kind];p.unlink();p.write_bytes((original/b[kind]).read_bytes())
    (tmp_path/'index.json').write_text(json.dumps(doc))
    profiles=ai_catalog.profiles()
    for p in profiles:p['releaseApproved']=True
    pp=tmp_path/'profiles.json';pp.write_text(json.dumps({'profiles':profiles}))
    monkeypatch.setattr(ai_catalog,'ASSETS',tmp_path);monkeypatch.setattr(ai_catalog,'PROFILES',pp)
    provider=SyntheticProvider()
    monkeypatch.setattr('app.jobs.configured_provider',lambda:provider)
    monkeypatch.setattr('app.main.configured_provider',lambda:provider)
    return replace(prepared[0],ai_mvp_enabled=True),provider


def register(client):
    email=uuid4().hex+'@example.com';password='local test password 2026'
    assert client.post('/api/auth/register',json={'email':email,'password':password}).status_code==201
    return email,password


def test_queue_idempotency_history_and_worker(released,monkeypatch):
    settings,provider=released
    with TestClient(create_app(settings)) as client:
        email,password=register(client)
        assert client.get('/api/ai-bases').json()['available']
        value=request()
        bad=client.post('/api/generations',json={**value,'prompt':'синий фон'})
        assert bad.status_code==422 and bad.json()['error']['code']=='AI_PROMPT_UNSUPPORTED'
        first=client.post('/api/generations',json=value)
        assert first.status_code==201,first.text
        g=first.json()['generation'];gid=g['id']
        again=client.post('/api/generations',json=value).json()['generation']
        assert again['id']==gid
        assert client.post('/api/generations',json={**value,'seed':11}).status_code==409
        assert g['ai']==value['ai'] and g['seed']==20261008 and g['prompt']==''
        assert g['selections'] is None and g['recipe']['profile']['strength']==.55
        with psycopg.connect(settings.database_url,row_factory=psycopg.rows.dict_row) as conn:
            assert step(conn,provider,settings)
        assert provider.submissions==1
        # Simulated worker restart resumes a known provider ID, without submit.
        with psycopg.connect(settings.database_url,row_factory=psycopg.rows.dict_row) as conn:
            assert step(conn,provider,settings)
        done=client.get('/api/generations/'+gid).json()['generation']
        assert done['status']=='done' and done['seamless'] is False and done['moduleUrl'] is None
        raw=client.get(done['imageUrl']).content
        assert hashlib.sha256(raw).hexdigest()==done['recipe']['outputSha256']['png']
        assert done['descriptionDetails']==g['descriptionDetails']
        assert provider.submissions==1
        assert client.post('/api/generations',json=value).json()['generation']['id']==gid
        # Offline provider/profile changes must not break history or idempotent retrieval.
        with monkeypatch.context() as offline:
            offline.setattr('app.jobs.configured_provider',lambda:None)
            offline.setattr(ai_catalog,'profiles',lambda:[])
            assert client.post('/api/generations',json=value).json()['generation']['recipe']==done['recipe']
            assert client.get('/api/generations/'+gid).json()['generation']['recipe']==done['recipe']
        # Concurrent retries must resolve to one persisted generation.
        from concurrent.futures import ThreadPoolExecutor
        concurrent=request()
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda _:client.post('/api/generations',json=concurrent),range(2)))
        assert all(r.status_code==201 for r in responses)
        assert len({r.json()['generation']['id'] for r in responses})==1
        with psycopg.connect(settings.database_url) as conn:
            conn.execute("UPDATE ai_jobs SET state='failed' WHERE generation_id=%s",(responses[0].json()['generation']['id'],))
        # Real legacy flat API request still works; no AI/profile fields are required.
        flat=client.post('/api/generations',json={'selections':{'style':'heritage','composition':'medallion','motifs':['tulip'],'palette':'emerald','usage':'web'}})
        assert flat.status_code==201,flat.text
        flatg=flat.json()['generation']
        # Simulate an existing old AI record: persisted free prompt and old recipe remain readable.
        with psycopg.connect(settings.database_url,row_factory=psycopg.rows.dict_row) as conn:
            owner=conn.execute('SELECT user_id FROM generations WHERE id=%s',(gid,)).fetchone()['user_id']
            oldparams={'mode':'ai','seed':7,'selections':{'composition':'medallion','elementCodes':['OLD']},'recipe':{'outputKind':'ai_image','seamless':None}}
            old=conn.execute("INSERT INTO generations(user_id,status,params,user_prompt,model_version) VALUES(%s,'failed',%s,'старое пожелание','old-ai') RETURNING id",(owner,Jsonb(oldparams))).fetchone()['id']
        with TestClient(create_app(settings)) as reopened:
            assert reopened.post('/api/auth/login',json={'email':email,'password':password}).status_code==200
            assert reopened.get('/api/generations/'+gid).json()['generation']['recipe']==done['recipe']
            assert reopened.get('/api/generations/'+flatg['id']).json()['generation']['recipe']==flatg['recipe']
            historic=reopened.get('/api/generations/'+str(old)).json()['generation']
            assert historic['prompt']=='старое пожелание' and historic['ai'] is None
            assert reopened.get('/api/generations').status_code==200
        with TestClient(create_app(settings)) as other:
            register(other)
            assert other.get('/api/generations/'+gid).status_code==404
            assert other.get(done['imageUrl']).status_code==404


def test_failures_no_resubmit_or_fallback(released):
    settings,provider=released
    with TestClient(create_app(settings)) as client:
        register(client)
        for state,code in [('submitting','AI_SUBMISSION_UNCERTAIN'),('deadline','AI_TIMEOUT'),('invalid','AI_PROVIDER_ERRORS')]:
            gid=client.post('/api/generations',json=request()).json()['generation']['id']
            with psycopg.connect(settings.database_url,row_factory=psycopg.rows.dict_row) as conn:
                if state=='submitting':conn.execute("UPDATE ai_jobs SET state='submitting' WHERE generation_id=%s",(gid,))
                elif state=='deadline':conn.execute("UPDATE ai_jobs SET deadline=now()-interval '1 second' WHERE generation_id=%s",(gid,))
                conn.commit();step(conn,provider,settings)
                if state=='invalid':
                    provider.invalid=True
                    for _ in range(3):
                        conn.execute("UPDATE ai_jobs SET next_poll_at=now() WHERE generation_id=%s",(gid,));conn.commit();step(conn,provider,settings)
            failed=client.get('/api/generations/'+gid).json()['generation']
            assert failed['status']=='failed' and failed['imageUrl'] is None and failed['error']['code']==code
        assert provider.submissions==1
