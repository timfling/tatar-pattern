"""Explicit test provider only; these are not DSLab responses."""
import io
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import psycopg
from fastapi.testclient import TestClient
from PIL import Image
from app.ai_provider import CloudStatus
from app.main import create_app
from scripts.ai_worker import step

class TestProvider:
    __test__=False
    name='explicit-test-adapter'
    model_version='synthetic-test-v1'
    def __init__(self): self.submissions=0
    def submit(self,payload,*,request_id,timeout):
        assert set(payload)=={'prompt','seed','selections','elements'}
        assert timeout==30
        self.submissions+=1
        return 'test-cloud-id'
    def poll(self,job_id,*,timeout): return CloudStatus('done')
    def download(self,job_id,*,timeout,max_bytes):
        buf=io.BytesIO(); Image.new('RGBA',(64,64),(50,100,150,255)).save(buf,format='PNG'); return buf.getvalue()


def test_jobs_durable_resume_ownership_no_fallback(prepared,monkeypatch):
    settings,_=prepared; provider=TestProvider()
    monkeypatch.setattr('app.jobs.configured_provider',lambda:provider)
    selected={'style':'heritage','composition':'medallion','motifs':['tulip'],'palette':'emerald','usage':'web'}
    with TestClient(create_app(settings)) as client:
        client.post('/api/auth/register',json={'email':uuid4().hex+'@example.com','password':'persistent job password'})
        # No external permission from quality acceptance or legacy rights enums.
        denied=client.post('/api/generations',json={'mode':'ai','selections':selected})
        assert denied.status_code==422 and denied.json()['error']['code']=='MATERIAL_TRANSFER_NOT_AUTHORIZED'
        with psycopg.connect(settings.database_url) as conn:
            # Synthetic fixture only, authorized explicitly inside test schema.
            conn.execute("UPDATE elements SET provenance='{"+'"externalTransferAllowed":true'+"}'::jsonb WHERE motif_class='тюльпан'")
        queued=client.post('/api/generations',json={'mode':'ai','seed':17,'selections':selected})
        assert queued.status_code==201,queued.text
        g=queued.json()['generation']; gid=g['id']; assert g['status']=='queued' and g['progress'] is None
        with psycopg.connect(settings.database_url,row_factory=psycopg.rows.dict_row) as conn: step(conn,provider,settings)
        assert provider.submissions==1
        assert client.get('/api/generations/'+gid).json()['generation']['status']=='processing'
        # New connection simulates worker restart with cloud id already saved.
        with psycopg.connect(settings.database_url,row_factory=psycopg.rows.dict_row) as conn: step(conn,provider,settings)
        done=client.get('/api/generations/'+gid).json()['generation']
        assert done['status']=='done' and done['mode']=='ai' and done['seed']==17 and done['modelVersion']=='synthetic-test-v1'
        assert client.get(done['imageUrl']).status_code==200 and provider.submissions==1
        assert done['descriptionDetails']==g['descriptionDetails']
        assert done['descriptionDetails']['basis']=='requested_only'
        assert done['descriptionDetails']['facts']['observed'] is None and done['descriptionDetails']['facts']['verified'] is None
        assert done['recipe']['usedElementCodes'] is None and done['seamless'] is None
        assert done['description'].startswith('Для генерации выбраны')
        uncertain=client.post('/api/generations',json={'mode':'ai','selections':selected}).json()['generation']['id']
        with psycopg.connect(settings.database_url,row_factory=psycopg.rows.dict_row) as conn:
            conn.execute("UPDATE ai_jobs SET state='submitting' WHERE generation_id=%s",(uncertain,)); conn.commit(); step(conn,provider,settings)
        failed=client.get('/api/generations/'+uncertain).json()['generation']
        assert failed['status']=='failed' and failed['imageUrl'] is None and failed['error']['code']=='AI_SUBMISSION_UNCERTAIN'
        assert provider.submissions==1
        timed=client.post('/api/generations',json={'mode':'ai','selections':selected}).json()['generation']['id']
        with psycopg.connect(settings.database_url,row_factory=psycopg.rows.dict_row) as conn:
            conn.execute("UPDATE ai_jobs SET deadline=now()-interval '1 second' WHERE generation_id=%s",(timed,)); conn.commit(); step(conn,provider,settings)
        assert client.get('/api/generations/'+timed).json()['generation']['error']['code']=='AI_TIMEOUT'
        with TestClient(create_app(settings)) as other:
            other.post('/api/auth/register',json={'email':uuid4().hex+'@example.com','password':'another job password'})
            assert other.get(done['imageUrl']).status_code==404
            assert other.get('/api/generations/'+gid).status_code==404
        with psycopg.connect(settings.database_url) as conn: conn.execute("UPDATE elements SET provenance='{}' WHERE is_fixture")
