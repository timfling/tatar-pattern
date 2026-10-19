"""Full reviewed catalogue through isolated PostgreSQL/API, saved pixels and replay."""
import io
import json
import shutil
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from fastapi.testclient import TestClient
from PIL import Image
from app.config import Settings
from app.main import create_app
from app.catalog import catalog
from app.scheme_catalog import registry, ASSETS
from app.generator_v2 import replay
from app.composition_metadata import review
from scripts.catalog_import import validate, import_reviewed

BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'local-test/expansion-2026-10-13'


def test_expanded_catalogue_api_history_replay(prepared,tmp_path):
    root=tmp_path/'storage'
    shutil.copytree(BASE/'catalog-input',root,ignore=shutil.ignore_patterns('results'))
    data,report=validate(root/'owner-accepted-2026-10-08.json',root)
    assert report['valid']
    schema='expansion_'+uuid4().hex
    with psycopg.connect(prepared[0].database_url,row_factory=psycopg.rows.dict_row) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
        for migration in sorted((BASE.parent/'db/migrations').glob('*.sql')):conn.execute(migration.read_text())
        import_reviewed(conn,data,report)
    scoped=psycopg.conninfo.make_conninfo(prepared[0].database_url,options=f'-c search_path={schema}')
    settings=Settings(scoped,root,local_catalog=True)
    with psycopg.connect(scoped,row_factory=psycopg.rows.dict_row) as conn:rows=catalog(conn,settings)
    bycode={r['code']:r for r in rows}
    email=uuid4().hex+'@example.com';password='expanded test password'
    OUT.mkdir(parents=True,exist_ok=True)
    records=[];covered=set();saved=[]
    with TestClient(create_app(settings)) as client:
        assert client.post('/api/composition-preflight',json={}).status_code==401
        assert client.post('/api/auth/register',json={'email':email,'password':password}).status_code==201
        reg=client.get('/api/composition-schemes').json()
        assert reg['totalElements']==110 and reg['totalFamilies']==25 and reg['totalSchemes']==61
        assert all(s['available'] for s in reg['schemes'])
        assert client.get('/api/capabilities').json()['renderers']['default']=='legacy'
        for scheme in reg['schemes']:
            selection={'renderer':'composition-v2','schemeId':scheme['id'],'registryVersion':reg['registryVersion'],
                       'style':'heritage','composition':scheme['composition'],'elementCodes':scheme['defaultElementCodes'],
                       'palette':'emerald','usage':'textile','backgroundColor':'#f3ebdb',
                       'outputSize':[1200,900] if scheme['composition']=='border' else [1024,1024]}
            body={'selections':selection,'seed':42}
            pf=client.post('/api/composition-preflight',json=body)
            assert pf.status_code==200,(scheme['id'],pf.text)
            response=client.post('/api/generations',json=body)
            assert response.status_code==201,(scheme['id'],response.text)
            gen=response.json()['generation'];recipe=gen['recipe']
            assert recipe['layout']==pf.json()['layout']
            assert set(recipe['usedElementCodes'])==set(selection['elementCodes'])
            assert recipe['diagnostics']['overlapPixels']==0 and recipe['compatibility']['cultural']=='unknown'
            assert all(not p['reflected'] and p['longSideBeforeRotation']>=p['recommendedMinLongSide'] for p in recipe['placements'])
            if scheme['layout']=='hanging_panel':assert all(p['targetAxis']==180 for p in recipe['placements'])
            raw=client.get(gen['imageUrl']).content;jpg=client.get(f"/api/generations/{gen['id']}/file?format=jpg&download=true")
            assert jpg.status_code==200 and 'attachment' in jpg.headers['content-disposition']
            assert Image.open(io.BytesIO(raw)).mode=='RGBA' and Image.open(io.BytesIO(jpg.content)).mode=='RGB'
            replay([bycode[c] for c in recipe['usedElementCodes']],recipe,tmp_path/'replay.png',tmp_path/'replay.jpg')
            assert (tmp_path/'replay.png').read_bytes()==raw and (tmp_path/'replay.jpg').read_bytes()==jpg.content
            if scheme['composition']=='rapport':
                mod=client.get(gen['moduleUrl']);assert mod.content==raw and gen['seamless']
            (OUT/(scheme['id']+'.png')).write_bytes(raw);(OUT/(scheme['id']+'.jpg')).write_bytes(jpg.content)
            (OUT/(scheme['id']+'.json')).write_text(json.dumps({'request':body,'generation':gen},ensure_ascii=False,indent=2))
            assert client.get(scheme['previewUrl']).status_code==200
            records.append({'id':scheme['id'],'title':scheme['titleRu'],'codes':recipe['usedElementCodes'],'image':scheme['id']+'.png','request':body,'sha256':recipe['outputSha256'],'layout':recipe['layout']})
            saved.append(gen)
            # Every eligible motif is tested with the default set; all selected assets survive.
            for code in scheme['allowedElementCodes']:
                chosen=list(dict.fromkeys(selection['elementCodes']+[code]))
                check=client.post('/api/composition-preflight',json={'selections':{**selection,'elementCodes':chosen},'seed':42})
                if check.status_code==422 and check.json()['error']['code']=='BORDER_TOO_TALL':
                    check=client.post('/api/composition-preflight',json={'selections':{**selection,'elementCodes':chosen,'outputSize':[900,1200]},'seed':42})
                assert check.status_code==200,(scheme['id'],code,check.text)
                assert set(check.json()['usedElementCodes'])==set(chosen)
                covered.add(code)
            # Distinct background/density, directed portrait and fractional scaling.
            variant={**selection,'parameters':'dense','scale':0.8,'backgroundColor':'#d8ddd0','transparentBackground':True}
            if scheme['composition']=='border':variant['outputSize']=[900,1200]
            if scheme['composition']=='rapport':variant.update(rapportOutput='sample',outputSize=[900,1200])
            res=client.post('/api/generations',json={'selections':variant,'seed':7})
            assert res.status_code==201,(scheme['id'],res.text)
            vg=res.json()['generation'];vim=Image.open(io.BytesIO(client.get(vg['imageUrl']).content))
            assert vim.getchannel('A').getextrema()[0]==0
            (OUT/(scheme['id']+'-variant.png')).write_bytes(client.get(vg['imageUrl']).content)
            (OUT/(scheme['id']+'-variant.json')).write_text(json.dumps({'request':{'selections':variant,'seed':7},'generation':vg},ensure_ascii=False,indent=2))
        assert len(covered)==110
        selection=records[0]['request']['selections']
        for patch,status,code in [({'registryVersion':'outdated'},409,'SCHEME_REGISTRY_CHANGED'),
                                  ({'schemeId':'missing'},422,'SCHEME_REQUIRED'),
                                  ({'composition':'rapport'},422,'SCHEME_COMPOSITION_MISMATCH'),
                                  ({'primaryElementCode':'TP-E-020'},422,'PRIMARY_NOT_SELECTED'),
                                  ({'colorMode':'silhouette'},422,'SCHEME_REQUIRES_ORIGINAL'),
                                  ({'elementCodes':['TP-E-020']},422,'SCHEME_ELEMENTS_UNSUPPORTED'),
                                  ({'renderer':'legacy'},422,'SCHEME_FIELDS_REQUIRE_V2')]:
            for endpoint in ['/api/composition-preflight','/api/generations']:
                res=client.post(endpoint,json={'selections':{**selection,**patch}})
                assert res.status_code==status and res.json()['error']['code']==code,res.text
        rs=next(r for r in records if r['layout']['variant']=='hierarchical_repeat')
        aligned={**rs['request']['selections'],'elementCodes':['TP-E-010'],'moduleSize':[600,800],'rapportOutput':'sample','outputSize':[1200,800]}
        res=client.post('/api/generations',json={'selections':aligned});assert res.status_code==201,res.text
        g=res.json()['generation'];assert g['seamless']
        mod=Image.open(io.BytesIO(client.get(g['moduleUrl']).content));sample=Image.open(io.BytesIO(client.get(g['imageUrl']).content))
        assert sample.crop((37,37,600,600)).tobytes()==sample.crop((637,37,1200,600)).tobytes()
        too_small={**aligned,'scale':2,'moduleSize':[256,256]}
        assert client.post('/api/composition-preflight',json={'selections':too_small}).status_code==422
        assert client.get('/api/composition-schemes/../../preview').status_code==404
    with TestClient(create_app(settings)) as client:
        assert client.post('/api/auth/login',json={'email':email,'password':password}).status_code==200
        for gen in saved:
            reopened=client.get('/api/generations/'+gen['id']).json()['generation']
            assert reopened['recipe']==gen['recipe'] and reopened['descriptionDetails']==gen['descriptionDetails']
    with TestClient(create_app(settings)) as other:
        other.post('/api/auth/register',json={'email':uuid4().hex+'@example.com','password':password})
        assert other.get(saved[0]['imageUrl']).status_code==404
        assert other.get(next(g for g in saved if g['moduleUrl'])['moduleUrl']).status_code==404
    (OUT/'manifest.json').write_text(json.dumps({'registryVersion':reg['registryVersion'],'registrySha256':reg['sha256'],'coveredElementCodes':sorted(covered),'schema':schema,'database':'isolated_test:55432','records':records,'review':'agent_review_pending_owner_not_individually_reviewed'},ensure_ascii=False,indent=2))


def test_registry_roles_and_single_motif_description():
    from app.generator_v2 import plan
    from app.models import Selections
    from app.descriptions import describe
    items=review()[0]['metadata.json']['items']
    rows={i['code']:{'code':i['code'],'content_sha256':i['flat_sha256'],'local_path':BASE/'catalog-input/flat'/(i['code']+'.png'),
                    'artifact_code':i['cultural_attribution']['artifact_code']} for i in items}
    for scheme in registry()['schemes']:
        selection=Selections(renderer='composition-v2',schemeId=scheme['id'],style='heritage',composition=scheme['composition'],
                             elementCodes=scheme['defaultElementCodes'],palette='emerald',usage='textile',
                             outputSize=[1200,900] if scheme['composition']=='border' else [1024,1024]).model_dump()
        scene,_,roles,primary,_,layout=plan([rows[c] for c in selection['elementCodes']],selection,42)
        assert all(p['role']==roles[p['code']] for p in scene.placements),(scheme['id'],roles)
        assert all(roles[c] in scheme['roleOptions'][c] for c in roles)
        recipe={'schemeId':scheme['id'],'usedElementCodes':selection['elementCodes'],'layout':layout,'placements':scene.placements}
        text=describe(recipe,selection)['text']
        if len(selection['elementCodes'])==1:
            assert 'вспомогательные' not in text and 'вспомогатель' not in text and 'отдельными обрамляющими' not in text
