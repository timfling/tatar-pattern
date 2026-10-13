"""Integration using 110 actual PNGs; test DB/schema only, no master mutations."""
import copy
import io
import json
import os
import shutil
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from fastapi.testclient import TestClient
from PIL import Image, ImageChops
from app.config import Settings
from app.main import create_app
from app.catalog import catalog
from scripts.catalog_import import validate,db_conflicts,import_reviewed

BASE=Path(__file__).resolve().parents[1]


def test_actual_110_catalog_api_history_rgba_3x3_and_negative(prepared, tmp_path):
    parent,_=prepared
    root=tmp_path/'storage'; shutil.copytree(BASE/'catalog-input',root,ignore=shutil.ignore_patterns('results'))
    manifest=root/'owner-accepted-2026-10-08.json'
    data,report=validate(manifest,root)
    assert report['valid'],report['errors']
    schema='real_'+uuid4().hex
    with psycopg.connect(parent.database_url,row_factory=psycopg.rows.dict_row) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
        for migration in sorted((BASE.parent/'db/migrations').glob('*.sql')): conn.execute(migration.read_text())
        db_conflicts(conn,data,report); assert report['valid']; import_reviewed(conn,data,report)
        proof=(BASE.parent/'db/queries/count_real_elements.sql').read_text().split(';')[0]+';'
        assert conn.execute(proof).fetchone()['real_unique_elements_with_files_and_provenance']==110
        assert conn.execute('SELECT count(*) AS n FROM elements WHERE verified_by IS NOT NULL').fetchone()['n']==0
        assert conn.execute("SELECT count(*) AS n FROM artifacts WHERE usage_scope!='контекст' OR rights!='неясно'").fetchone()['n']==0
        duplicate=validate(manifest,root)[1]; db_conflicts(conn,data,duplicate); assert not duplicate['valid']
        assert len(catalog(conn,Settings(parent.database_url,root)))==0 # local authorization does not grant publication
    scoped=psycopg.conninfo.make_conninfo(parent.database_url,options=f'-c search_path={schema}')
    settings=Settings(scoped,root,local_catalog=True)
    email=uuid4().hex+'@example.com'; password='real catalog test password'
    results=[]
    with TestClient(create_app(settings)) as client:
        items=client.get('/api/elements').json()
        assert items['total']==110
        assert len({r['sha256'] for r in items['items']})==110
        assert len({r['motifIdentity'] for r in items['items']})==110
        assert len({r['motifClass'] for r in items['items']})==65
        corner=next(r for r in items['items'] if r['code']=='TP-E-008'); assert corner['motifClass']=='угол рамки'
        assert client.get('/api/capabilities').json()['realUniqueElements']==110
        assert client.post('/api/auth/register',json={'email':email,'password':password}).status_code==201
        project=client.post('/api/projects',json={'title':'Настоящий каталог 08.10'}).json()['project']['id']
        selections={'style':'heritage','composition':'rapport','parameters':'default','motifs':[],'elementCodes':['TP-E-008','TP-E-010','TP-E-013'],'palette':'emerald','usage':'web','transparentBackground':True,'backgroundColor':'#faf2de','scale':1.0,'colorMode':'original'}
        for composition in ('rapport','border','medallion'):
            req=client.post('/api/generations',json={'mode':'flat','selections':{**selections,'composition':composition},'projectId':project})
            assert req.status_code==201,req.text
            gen=req.json()['generation']; results.append(gen)
            assert gen['mode']=='flat' and not gen['recipe']['isFixture']
            assert [r['code'] for r in gen['recipe']['elements']]==selections['elementCodes']
            png=client.get(gen['imageUrl']); image=Image.open(io.BytesIO(png.content)); assert image.mode=='RGBA' and image.getchannel('A').getextrema()[0]==0
            jpg=client.get(f"/api/generations/{gen['id']}/file?format=jpg&download=true")
            solid=Image.open(io.BytesIO(jpg.content)); assert solid.mode=='RGB' and solid.format=='JPEG'
            assert 'attachment' in jpg.headers['content-disposition']
            if composition=='rapport':
                tile=gen['recipe']['layout']['tileSize']; expected=image.crop((0,0,tile,tile))
                for y in range(0,image.height,tile):
                    for x in range(0,image.width,tile): assert image.crop((x,y,x+tile,y+tile)).tobytes()==expected.tobytes()
                # 3x3 inspectable preview, all 9 exports form one periodic lattice.
                preview=Image.new('RGBA',(image.width*3,image.height*3))
                for y in range(3):
                    for x in range(3): preview.paste(image,(image.width*x,image.height*y))
                preview.thumbnail((1200,1200)); preview.save(BASE/'local-test/real-rapport-3x3.png')
                (BASE/'local-test/real-rapport.png').write_bytes(png.content)
                (BASE/'local-test/real-rapport.jpg').write_bytes(jpg.content)
        base=client.post('/api/generations',json={'selections':selections}).json()['generation']
        dense=client.post('/api/generations',json={'selections':{**selections,'parameters':'dense','scale':0.5}}).json()['generation']
        assert client.get(base['imageUrl']).content!=client.get(dense['imageUrl']).content
        assert client.post('/api/generations',json={'selections':{**selections,'elementCodes':['TP-R-001']}}).status_code==422
        assert client.post('/api/generations',json={'selections':{**selections,'elementCodes':['missing']}}).status_code==422
        assert client.post('/api/generations',json={'selections':{**selections,'scale':4}}).status_code==422
        assert client.post('/api/generations',json={'mode':'ai','selections':selections}).json()['error']['code']=='AI_PROVIDER_UNCONFIGURED'
        assert client.patch('/api/generations/'+results[0]['id'],json={'title':'Принятый раппорт','rating':'like'}).status_code==200
    with TestClient(create_app(settings)) as restarted:
        assert restarted.post('/api/auth/login',json={'email':email,'password':password}).status_code==200
        assert restarted.get('/api/generations/'+results[0]['id']).json()['generation']['title']=='Принятый раппорт'
        assert restarted.get(results[0]['imageUrl']).status_code==200
        assert restarted.get('/api/generations').json()['total']==5
    with TestClient(create_app(settings)) as other:
        other.post('/api/auth/register',json={'email':uuid4().hex+'@example.com','password':password})
        assert other.get(results[0]['imageUrl']).status_code==404
        assert other.get('/api/generations/'+results[0]['id']).status_code==404
        assert other.post('/api/generations',json={'selections':selections,'projectId':project}).status_code==404
    (BASE/'local-test/real-check.json').write_text(json.dumps({'database':'isolated_test','uniqueElements':110,'classes':65,'expertVerified':0,'checks':['real catalogue API','3 compositions','elementCodes','scale/density','RGBA transparent PNG','solid-background JPG','exact periodic subtiles and 3x3','history after new app/login','ownership 404','missing/aux/scale negative','AI unavailable distinct error'],'generations':[g['id'] for g in results]},ensure_ascii=False,indent=2))


def test_v2_quality_does_not_grant_external_permissions(tmp_path):
    root=BASE/'catalog-input'; manifest=root/'owner-accepted-2026-10-08.json'
    data=json.loads(manifest.read_text())
    for mutate in (lambda d:d.update(trainingAllowed=True),lambda d:d['elements'][0].update(verifiedBy='invented expert'),lambda d:d['elements'][0]['qualityAcceptance'].update(sha256='0'*64),lambda d:d['elements'][0].update(artifactCode='wrong')):
        changed=copy.deepcopy(data); mutate(changed); path=tmp_path/'manifest.json'; path.write_text(json.dumps(changed))
        assert not validate(path,root)[1]['valid']
