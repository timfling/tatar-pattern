"""Owner-bound pixel preservation and meaningful revised-layout/replay/API checks."""
import hashlib,io,json,shutil
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from PIL import Image
from fastapi.testclient import TestClient
from app.scheme_catalog import registry
from app.composition_metadata import review
from app.generator_v2 import render,replay
from app.models import Selections
from app.config import Settings
from app.main import create_app
from scripts.catalog_import import validate,import_reviewed
BASE=Path(__file__).resolve().parents[1];ORIGINAL=BASE/'local-test/design-revision-2026-10-13/original'


def reviewed_rows():
    return {i['code']:{'code':i['code'],'content_sha256':i['flat_sha256'],'local_path':BASE/'catalog-input/flat'/(i['code']+'.png'),
                     'artifact_code':i['cultural_attribution']['artifact_code'],'frame':i['cultural_attribution']['frame'],'motif_key':i['code']} for i in review()[0]['metadata.json']['items']}


def test_owner_accepted_pixels_and_old_replay_preserved(tmp_path):
    rows=reviewed_rows();owner=json.loads((BASE/'docs/OWNER-SCHEME-REVIEW-2026-10-13.json').read_text())
    assert len(owner['accepted'])==24 and len(owner['needsRedesign'])==21 and len(owner['needsPolish'])==16
    for scheme in registry()['schemes']:
        old=json.loads((ORIGINAL/(scheme['id']+'.json')).read_text());codes=old['recipe']['usedElementCodes'];chosen=[rows[c] for c in codes]
        replay(chosen,old['recipe'],tmp_path/'old.png',tmp_path/'old.jpg')
        assert hashlib.sha256((tmp_path/'old.png').read_bytes()).hexdigest()==old['fullSha256']
        if scheme['id'] in owner['accepted']:
            assert scheme['reviewStatus']=='owner_accepted_2026_10_13' and 'design' not in scheme
            sel={**old['request']['selections'],'registryVersion':registry()['registryVersion']}
            render(chosen,sel,{'bg':sel['backgroundColor']},tmp_path/'current.png',tmp_path/'current.jpg',42)
            assert (tmp_path/'current.png').read_bytes()==(ORIGINAL/(scheme['id']+'.png')).read_bytes(),scheme['id']


def test_revised_all_profiles_density_masks_roles_periods(tmp_path):
    rows=reviewed_rows();tested=0
    for scheme in registry()['schemes']:
        if not scheme.get('design'):continue
        tested+=1;chosen=[rows[c] for c in scheme['defaultElementCodes']]
        for density,scale in [('default',1),('sparse',.8),('dense',1.1)]:
            sel=Selections(renderer='composition-v2',schemeId=scheme['id'],registryVersion=registry()['registryVersion'],
                style='heritage',composition=scheme['composition'],elementCodes=scheme['defaultElementCodes'],parameters=density,scale=scale,
                palette='emerald',usage='textile',outputSize=[1200,900],backgroundColor='#f3ebdb').model_dump()
            recipe,_=render(chosen,sel,{'bg':'#f3ebdb'},tmp_path/'current.png',tmp_path/'current.jpg',42)
            assert set(recipe['usedElementCodes'])==set(sel['elementCodes'])
            assert recipe['diagnostics']['overlapPixels']==0
            assert all(p['role']==recipe['roles'][p['code']] and not p['reflected'] and p['longSideBeforeRotation']>=p['recommendedMinLongSide'] for p in recipe['placements'])
            replay(chosen,recipe,tmp_path/'replay.png',tmp_path/'replay.jpg')
            assert (tmp_path/'replay.png').read_bytes()==(tmp_path/'current.png').read_bytes()
            assert (tmp_path/'replay.jpg').read_bytes()==(tmp_path/'current.jpg').read_bytes()
            if scheme['composition']=='rapport':
                assert recipe['seamless'] and recipe['layout']['offsetRepeat']
                module=Image.open(tmp_path/'current.png').convert('RGBA');w,h=module.size
                sample=Image.new('RGBA',(w*3,h*3))
                for y in range(3):
                    for x in range(3):sample.paste(module,(x*w,y*h))
                assert sample.crop((37,37,w+37,h+37)).tobytes()==sample.crop((w+37,h+37,2*w+37,2*h+37)).tobytes()
    assert tested==37


def test_revision_api_preflight_history_exports(prepared,tmp_path):
    root=tmp_path/'storage';shutil.copytree(BASE/'catalog-input',root,ignore=shutil.ignore_patterns('results'))
    data,report=validate(root/'owner-accepted-2026-10-08.json',root);assert report['valid']
    schema='design_'+uuid4().hex
    with psycopg.connect(prepared[0].database_url,row_factory=psycopg.rows.dict_row) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
        for migration in sorted((BASE.parent/'db/migrations').glob('*.sql')):conn.execute(migration.read_text())
        import_reviewed(conn,data,report)
    url=psycopg.conninfo.make_conninfo(prepared[0].database_url,options=f'-c search_path={schema}');settings=Settings(url,root,local_catalog=True)
    email=uuid4().hex+'@example.com';password='design revision test password';saved=[]
    with TestClient(create_app(settings)) as client:
        assert client.post('/api/auth/register',json={'email':email,'password':password}).status_code==201
        reg=client.get('/api/composition-schemes').json();assert reg['registryVersion']=='tp-schemes/2.1.0'
        assert sum(s['reviewStatus']=='owner_accepted_2026_10_13' for s in reg['schemes'])==24
        for sid in ('f09-repeat','f04-directed','f22-repeat','f24-directed','f17-repeat','f01-repeat','f01-directed','f07-directed','f15-directed'):
            s=next(s for s in reg['schemes'] if s['id']==sid)
            sel={'renderer':'composition-v2','schemeId':sid,'registryVersion':reg['registryVersion'],'style':'heritage','composition':s['composition'],
                 'elementCodes':s['defaultElementCodes'],'palette':'emerald','usage':'textile','outputSize':[1200,900]}
            body={'selections':sel,'seed':42}
            with psycopg.connect(url) as conn:before=conn.execute('SELECT count(*) FROM generations').fetchone()[0]
            pf=client.post('/api/composition-preflight',json=body);assert pf.status_code==200,pf.text
            with psycopg.connect(url) as conn:assert conn.execute('SELECT count(*) FROM generations').fetchone()[0]==before
            res=client.post('/api/generations',json=body);assert res.status_code==201,res.text
            gen=res.json()['generation'];saved.append(gen)
            assert gen['recipe']['layout']==pf.json()['layout'] and gen['recipe']['schemeDefinition']['design']==s['design']
            assert gen['recipe']['algorithmVersion']=='composition-pillow/2.1.0'
            assert client.get(gen['imageUrl']).status_code==200
            jpg=client.get(f"/api/generations/{gen['id']}/file?format=jpg&download=true");assert jpg.status_code==200 and 'attachment' in jpg.headers['content-disposition']
            assert Image.open(io.BytesIO(jpg.content)).mode=='RGB'
            if gen['moduleUrl']:assert client.get(gen['moduleUrl']).status_code==200
            stale=client.post('/api/composition-preflight',json={'selections':{**sel,'registryVersion':'tp-schemes/2.0.0'}})
            assert stale.status_code==409
    with TestClient(create_app(settings)) as client:
        assert client.post('/api/auth/login',json={'email':email,'password':password}).status_code==200
        for gen in saved:
            reopened=client.get('/api/generations/'+gen['id']).json()['generation']
            assert reopened['recipe']==gen['recipe'] and reopened['descriptionDetails']==gen['descriptionDetails']
    with TestClient(create_app(settings)) as client:
        client.post('/api/auth/register',json={'email':uuid4().hex+'@example.com','password':password})
        assert client.get(saved[0]['imageUrl']).status_code==404
    out=BASE/'local-test/design-revision-2026-10-13/api-proof.json'
    out.write_text(json.dumps({'schema':schema,'database':'isolated_test:55432','registrySha256':reg['sha256'],'schemeIds':[g['recipe']['schemeId'] for g in saved],'checks':'preflight_no_generation_write_POST_PNG_JPG_module_stale409_reopen_ownership404'},indent=2))
