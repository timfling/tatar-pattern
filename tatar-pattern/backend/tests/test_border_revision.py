"""The rejected P2 must have stable cadence, three roles, old history intact."""
import hashlib
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

BASE=Path(__file__).resolve().parents[1]
OUTPUT=BASE/'local-test/composition-2026-10-12/border-revision-regression'
ORIGINAL=BASE/'local-test/composition-2026-10-12/gallery'


def sha(data):return hashlib.sha256(data).hexdigest()


def test_border_registers_api_reopen_settings_and_accepted_pixels(prepared,tmp_path):
    parent,_=prepared
    root=tmp_path/'storage';shutil.copytree(BASE/'catalog-input',root,ignore=shutil.ignore_patterns('results'))
    from scripts.catalog_import import validate,import_reviewed
    data,report=validate(root/'owner-accepted-2026-10-08.json',root);assert report['valid']
    schema='border_'+uuid4().hex
    with psycopg.connect(parent.database_url,row_factory=psycopg.rows.dict_row) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
        for migration in sorted((BASE.parent/'db/migrations').glob('*.sql')):conn.execute(migration.read_text())
        import_reviewed(conn,data,report)
    url=psycopg.conninfo.make_conninfo(parent.database_url,options=f'-c search_path={schema}')
    settings=Settings(url,root,local_catalog=True)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    email=uuid4().hex+'@example.com';password='border revision test password'
    records=[];count_by_density={};generated=[]
    with psycopg.connect(url,row_factory=psycopg.rows.dict_row) as conn:all_rows=catalog(conn,settings)
    rows=[r for r in all_rows if r['code'] in ['TP-E-061','TP-E-063','TP-E-066']]
    with TestClient(create_app(settings)) as client:
        assert client.post('/api/auth/register',json={'email':email,'password':password}).status_code==201
        for tag,density,bg,size in [('paper-default','default','#f3ebdb',[1200,900]),
                                    ('sage-sparse','sparse','#d8ddd0',[1200,900]),
                                    ('paper-dense','dense','#f3ebdb',[1200,900]),
                                    ('portrait-default','default','#f3ebdb',[900,1200])]:
            selections={'renderer':'composition-v1','composition':'border','elementCodes':['TP-E-061','TP-E-063','TP-E-066'],
                        'parameters':density,'scale':1,'palette':'emerald','style':'heritage','usage':'textile',
                        'colorMode':'original','backgroundColor':bg,'outputSize':size}
            request={'selections':selections,'seed':42}
            response=client.post('/api/generations',json=request);assert response.status_code==201,response.text
            gen=response.json()['generation'];generated.append(gen);recipe=gen['recipe']
            assert recipe['layout']['rows']==3
            assert recipe['layout']['historicalReconstruction'] is False
            assert recipe['layout']['continuousJoinedRepeat'] is False
            assert gen['compatibility']['cultural']=='unknown'
            assert gen['culturalNote']['claimType']=='single_object_visual_observation'
            assert set(recipe['usedElementCodes'])==set(selections['elementCodes'])
            assert recipe['diagnostics']['overlapPixels']==0
            assert not [w for w in gen['warnings'] if w['code']=='LOW_AVERAGE_CONTRAST']
            by_role={role:[p for p in recipe['placements'] if p['role']==role] for role in recipe['roles'].values()}
            main=by_role['primary_flower'];link=by_role['horizontal_connector_accent'];small=by_role['small_accent']
            n=recipe['layout']['repeatCount'];assert len(main)==len(link)==n and len(small)==2*n-1
            assert [p['anchorPosition'][0] for p in main]==[p['anchorPosition'][0] for p in link]
            for group in (main,link,small):
                xs=[p['anchorPosition'][0] for p in group]
                assert abs((xs[0]+xs[-1])/2-size[0]/2)<0.01
                steps=[xs[i+1]-xs[i] for i in range(len(xs)-1)]
                assert max(steps)-min(steps)<0.01
                assert len({p['anchorPosition'][1] for p in group})==1
                assert all(p['clockwiseDegrees']==0 and not p['reflected'] for p in group)
            if size==[1200,900]:count_by_density[density]=n
            png=client.get(gen['imageUrl']).content;jpg=client.get(f"/api/generations/{gen['id']}/file?format=jpg&download=true").content
            assert Image.open(io.BytesIO(png)).size==tuple(size)
            assert Image.open(io.BytesIO(png)).getchannel('A').getextrema()==(255,255)
            replay(rows,recipe,tmp_path/'replay.png',tmp_path/'replay.jpg')
            assert (tmp_path/'replay.png').read_bytes()==png and (tmp_path/'replay.jpg').read_bytes()==jpg
            same=client.post('/api/generations',json=request).json()['generation'];assert same['recipe']==recipe
            (OUTPUT/(tag+'.png')).write_bytes(png);(OUTPUT/(tag+'.jpg')).write_bytes(jpg)
            (OUTPUT/(tag+'.json')).write_text(json.dumps({'request':request,'generation':gen},ensure_ascii=False,indent=2))
            records.append({'name':tag,'image':tag+'.png','recipe':tag+'.json','pngSha256':sha(png),'elementCodes':selections['elementCodes'],'size':size,'density':density,'description':gen['description'],'status':'revised_awaiting_owner_visual_review'})
        assert count_by_density=={'sparse':4,'default':5,'dense':6}
        # Both renderer-independent saved replay and current P1/P3 maintain approved pixels.
        for name in ['P1-paper','P1-dark','P3-paper','P3-dark']:
            old=json.loads((ORIGINAL/(name+'.json')).read_text());saved=old['generation']['recipe']
            old_rows=[r for r in all_rows if r['code'] in saved['usedElementCodes']]
            replay(old_rows,saved,tmp_path/'old.png',tmp_path/'old.jpg')
            assert (tmp_path/'old.png').read_bytes()==(ORIGINAL/(name+'.png')).read_bytes()
            request={k:v for k,v in old['request'].items() if k!='projectId'}
            current=client.post('/api/generations',json=request).json()['generation']
            assert client.get(current['imageUrl']).content==(ORIGINAL/(name+'.png')).read_bytes()
        # Explicit density+scale makes the accepted wreath fuller, without changing master files.
        request=json.loads((ORIGINAL/'P1-paper.json').read_text())['request'];request.pop('projectId',None)
        request['selections'].update(parameters='dense',scale=1.2)
        response=client.post('/api/generations',json=request);assert response.status_code==201,response.text
        wreath=response.json()['generation'];assert wreath['recipe']['layout']['rays']==11
        assert wreath['recipe']['layout']['centerLongSide']==244
        (OUTPUT/'wreath-denser.png').write_bytes(client.get(wreath['imageUrl']).content)
        (OUTPUT/'wreath-denser.jpg').write_bytes(client.get(f"/api/generations/{wreath['id']}/file?format=jpg").content)
        (OUTPUT/'wreath-denser.json').write_text(json.dumps({'request':request,'generation':wreath},ensure_ascii=False,indent=2))
    with TestClient(create_app(settings)) as restarted:
        assert restarted.post('/api/auth/login',json={'email':email,'password':password}).status_code==200
        for gen in generated:
            reopened=restarted.get('/api/generations/'+gen['id']).json()['generation']
            assert reopened['recipe']==gen['recipe'] and reopened['descriptionDetails']==gen['descriptionDetails']
            assert sha(restarted.get(reopened['imageUrl']).content)==gen['recipe']['outputSha256']['png']
    with TestClient(create_app(settings)) as other:
        other.post('/api/auth/register',json={'email':uuid4().hex+'@example.com','password':password})
        assert other.get(generated[0]['imageUrl']).status_code==404
    (OUTPUT/'manifest.json').write_text(json.dumps({'status':'revised_awaiting_owner_visual_review','database':'isolated_test:55432','schema':schema,'records':records,'densityRepeatCounts':count_by_density},ensure_ascii=False,indent=2))
