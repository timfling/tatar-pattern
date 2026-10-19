"""Interleaved visual weights are an explicit alternative, not a cultural claim."""
import io
import json
import shutil
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from PIL import Image
from fastapi.testclient import TestClient
from app.catalog import catalog
from app.config import Settings
from app.main import create_app
from app.composition import replay
from scripts.catalog_import import validate,import_reviewed
BASE=Path(__file__).resolve().parents[1]
OUTPUT=BASE/'local-test/composition-2026-10-12/border-weights'


def test_interwoven_explicit_api_seed_replay_history_and_saved_registers(prepared,tmp_path):
    parent,_=prepared;root=tmp_path/'storage'
    shutil.copytree(BASE/'catalog-input',root,ignore=shutil.ignore_patterns('results'))
    data,report=validate(root/'owner-accepted-2026-10-08.json',root);assert report['valid']
    schema='weights_'+uuid4().hex
    with psycopg.connect(parent.database_url,row_factory=psycopg.rows.dict_row) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
        for migration in sorted((BASE.parent/'db/migrations').glob('*.sql')):conn.execute(migration.read_text())
        import_reviewed(conn,data,report)
    url=psycopg.conninfo.make_conninfo(parent.database_url,options=f'-c search_path={schema}')
    settings=Settings(url,root,local_catalog=True)
    with psycopg.connect(url,row_factory=psycopg.rows.dict_row) as conn:rows=[r for r in catalog(conn,settings) if r['code'] in ['TP-E-061','TP-E-063','TP-E-066']]
    OUTPUT.mkdir(exist_ok=True)
    email=uuid4().hex+'@example.com';password='weighted border test password'
    records=[];results=[]
    with TestClient(create_app(settings)) as client:
        client.post('/api/auth/register',json={'email':email,'password':password})
        capabilities=client.get('/api/capabilities').json()['renderers']['composition-v1']
        assert capabilities['borderLayouts']==['registers','interwoven']
        base=json.loads((BASE/'local-test/composition-2026-10-12/border-revision/paper-default.json').read_text())
        request={k:v for k,v in base['request'].items() if k!='projectId'}
        old=client.post('/api/generations',json=request).json()['generation']
        assert client.get(old['imageUrl']).content==(BASE/'local-test/composition-2026-10-12/border-revision/paper-default.png').read_bytes()
        (OUTPUT/'registers.png').write_bytes(client.get(old['imageUrl']).content)
        (OUTPUT/'registers.json').write_text(json.dumps({'request':request,'generation':old},ensure_ascii=False,indent=2))
        for name,density,bg in [('interwoven-default','default','#f3ebdb'),('interwoven-dense','dense','#f3ebdb'),('interwoven-sage','dense','#d8ddd0')]:
            request={**request,'selections':{**request['selections'],'borderLayout':'interwoven','parameters':density,'backgroundColor':bg}}
            res=client.post('/api/generations',json=request);assert res.status_code==201,res.text
            gen=res.json()['generation'];results.append(gen);recipe=gen['recipe']
            layout=recipe['layout'];assert layout['variant']=='interwoven' and layout['registers'] is None
            assert layout['visualWeights']=={'primary_flower':'heavy','horizontal_connector_accent':'medium','small_accent':'light'}
            placements=recipe['placements'];n=layout['repeatCount']
            assert len(placements)==6*n
            heavy=[p for p in placements if p['role']=='primary_flower'];medium=[p for p in placements if p['role']=='horizontal_connector_accent'];light=[p for p in placements if p['role']=='small_accent']
            assert len({p['anchorPosition'][1] for p in heavy})==2
            assert len({p['anchorPosition'][1] for p in medium})==2
            assert len({round(p['anchorPosition'][1]) for p in light})>=4
            assert all(not p['reflected'] and p['longSideBeforeRotation']>=p['recommendedMinLongSide'] for p in placements)
            assert recipe['diagnostics']['overlapPixels']==0
            assert gen['compatibility']['cultural']=='unknown'
            assert recipe['culturalNote']['appliesTo']=='motif_object_context_only_not_interwoven_layout'
            assert 'три яруса' not in gen['description'] and 'волнообразному' in gen['description']
            if density=='dense':assert 'с небольшими просветами' in gen['description']
            assert set(recipe['usedElementCodes'])==set(request['selections']['elementCodes'])
            png=client.get(gen['imageUrl']).content;jpg=client.get(f"/api/generations/{gen['id']}/file?format=jpg").content
            assert Image.open(io.BytesIO(png)).getchannel('A').getextrema()==(255,255)
            replay(rows,recipe,tmp_path/'replay.png',tmp_path/'replay.jpg')
            assert (tmp_path/'replay.png').read_bytes()==png and (tmp_path/'replay.jpg').read_bytes()==jpg
            again=client.post('/api/generations',json=request).json()['generation'];assert again['recipe']==recipe
            (OUTPUT/(name+'.png')).write_bytes(png);(OUTPUT/(name+'.jpg')).write_bytes(jpg)
            (OUTPUT/(name+'.json')).write_text(json.dumps({'request':request,'generation':gen},ensure_ascii=False,indent=2))
            records.append({'name':name,'pngSha256':recipe['outputSha256']['png'],'density':density,'size':recipe['size'],'elementCodes':recipe['usedElementCodes'],'status':'awaiting_owner_visual_review'})
        bad={**request,'selections':{**request['selections'],'renderer':'legacy'}}
        assert client.post('/api/generations',json=bad).json()['error']['code']=='BORDER_LAYOUT_REQUIRES_COMPOSITION'
    with TestClient(create_app(settings)) as reopened:
        reopened.post('/api/auth/login',json={'email':email,'password':password})
        for gen in results:
            saved=reopened.get('/api/generations/'+gen['id']).json()['generation']
            assert saved['recipe']==gen['recipe'] and saved['description']==gen['description']
    with TestClient(create_app(settings)) as other:
        other.post('/api/auth/register',json={'email':uuid4().hex+'@example.com','password':password})
        assert other.get(results[0]['imageUrl']).status_code==404
    (OUTPUT/'manifest.json').write_text(json.dumps({'date':'2026-10-13','schema':schema,'database':'isolated_test:55432','records':records,'oldRegistersPixelsUnchanged':True},ensure_ascii=False,indent=2))
