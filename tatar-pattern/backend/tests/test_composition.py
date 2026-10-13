"""Actual pilot/API/DB chain and invariant checks; no working DB or storage."""
import hashlib
import io
import json
import os
import shutil
from pathlib import Path
from uuid import uuid4
import pytest
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from PIL import Image
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.catalog import catalog
from app.composition import replay, transformed
from app.composition_metadata import metadata, review
from app.descriptions import describe, saved_or_fallback
from app.errors import APIError
from app.legacy_review_renderer import render as old_render
from scripts.catalog_import import validate, import_reviewed

BASE=Path(__file__).resolve().parents[1]
GALLERY=Path(os.getenv('TP_COMPOSITION_GALLERY',str(BASE/'local-test/composition-2026-10-12/regression-gallery')))


def digest(raw): return hashlib.sha256(raw).hexdigest()


def test_pilot_real_catalog_history_replay_exports_gallery(prepared,tmp_path):
    parent,_=prepared
    root=tmp_path/'storage'
    shutil.copytree(BASE/'catalog-input',root,ignore=shutil.ignore_patterns('results'))
    data,report=validate(root/'owner-accepted-2026-10-08.json',root);assert report['valid']
    schema='composition_'+uuid4().hex
    with psycopg.connect(parent.database_url,row_factory=psycopg.rows.dict_row) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
        for migration in sorted((BASE.parent/'db/migrations').glob('*.sql')):conn.execute(migration.read_text())
        import_reviewed(conn,data,report)
    scoped=psycopg.conninfo.make_conninfo(parent.database_url,options=f'-c search_path={schema}')
    settings=Settings(scoped,root,local_catalog=True)
    GALLERY.mkdir(parents=True,exist_ok=True)
    email=uuid4().hex+'@example.com';password='composition test password'
    pilots=review()[0]['families.json']['pilot_recipes']
    records=[];generations=[]
    with TestClient(create_app(settings)) as client:
        assert client.post('/api/auth/register',json={'email':email,'password':password}).status_code==201
        items=client.get('/api/elements').json()['items'];assert len(items)==110
        assert all(i['compositionMetadata']['flat_sha256']==i['sha256'] for i in items)
        assert client.get('/api/capabilities').json()['renderers']['default']=='legacy'
        project=client.post('/api/projects',json={'title':'Composition pilot'}).json()['project']['id']
        with psycopg.connect(scoped,row_factory=psycopg.rows.dict_row) as conn: rows=catalog(conn,settings)
        for pilot in pilots:
            chosen=[r for r in rows if r['code'] in pilot['codes']]
            for index in range(2):
                tag=pilot['id']+('-paper' if index==0 else ('-sage' if pilot['id']=='P2' else '-dark'))
                selections={'renderer':'composition-v1','style':'heritage','composition':pilot['composition'],
                            'parameters':('sparse' if pilot['id']=='P2' else 'dense') if index else 'default',
                            'elementCodes':pilot['codes'],'palette':'emerald','usage':'textile','scale':1,
                            'colorMode':'original','backgroundColor':('#d8ddd0' if pilot['id']=='P2' else '#172d24') if index else '#f3ebdb',
                            'outputSize':([720,1280] if index else [900,1200]) if pilot['id']=='P3' else ([1200,900] if pilot['id']=='P2' else [1024,1024])}
                if pilot['id']=='P3':selections['rapportOutput']='sample'
                body={'selections':selections,'seed':42,'projectId':project}
                response=client.post('/api/generations',json=body);assert response.status_code==201,response.text
                gen=response.json()['generation'];generations.append(gen)
                raw=client.get(gen['imageUrl']).content
                jpg=client.get(f"/api/generations/{gen['id']}/file?format=jpg&download=true")
                assert jpg.status_code==200 and 'attachment' in jpg.headers['content-disposition']
                im=Image.open(io.BytesIO(raw));assert im.mode=='RGBA';assert im.size==tuple(selections['outputSize'])
                assert im.getchannel('A').getextrema()==(255,255)
                assert Image.open(io.BytesIO(jpg.content)).mode=='RGB'
                recipe=gen['recipe'];assert set(recipe['usedElementCodes'])==set(pilot['codes'])
                assert recipe['selectedElementCodes']==pilot['codes'] and not recipe['isFixture']
                assert recipe['seed']==42 and recipe['description']['text']==gen['description']
                assert all(not p['reflected'] and p['longSideBeforeRotation']>=p['recommendedMinLongSide'] for p in recipe['placements'])
                assert recipe['diagnostics']['overlapPixels']==0
                (GALLERY/(tag+'.png')).write_bytes(raw);(GALLERY/(tag+'.jpg')).write_bytes(jpg.content)
                (GALLERY/(tag+'.json')).write_text(json.dumps({'request':body,'generation':gen},ensure_ascii=False,indent=2))
                replay(chosen,recipe,tmp_path/'replay.png',tmp_path/'replay.jpg')
                assert digest((tmp_path/'replay.png').read_bytes())==digest(raw)
                assert digest((tmp_path/'replay.jpg').read_bytes())==digest(jpg.content)
                again=client.post('/api/generations',json=body).json()['generation']
                assert again['recipe']==recipe
                assert client.get(again['imageUrl']).content==raw
                records.append({'name':tag,'image':tag+'.png','recipe':tag+'.json','elementCodes':pilot['codes'],'pngSha256':digest(raw),'size':list(im.size),'description':gen['description'],'outputKind':gen['outputKind'],'seamless':gen['seamless']})
                if pilot['id']=='P3':
                    module=client.get(gen['moduleUrl']);assert module.status_code==200
                    mod=Image.open(io.BytesIO(module.content));mw,mh=mod.size
                    assert mw>=380 and mh>=380 and recipe['repeat']['moduleSha256']==digest(module.content)
                    assert all(p['longSideBeforeRotation']>=64 for p in recipe['placements'])
                    assert not gen['seamless'] and gen['outputKind']=='pattern_sample'
                    assert im.crop((0,0,mw,mh)).tobytes()==mod.tobytes()
                    preview=Image.new('RGBA',(mw*3,mh*3))
                    for y in range(3):
                        for x in range(3):preview.paste(mod,(mw*x,mh*y))
                    preview.save(GALLERY/(tag+'-3x3.png'))
                    (GALLERY/(tag+'-module.png')).write_bytes(module.content)
                    for axis in (0,1):
                        # Check crop periodicity at arbitrary offset, not merely identical pasted subtiles.
                        offset=37
                        if axis==0: aa=preview.crop((offset,37,mw+offset,mh+37));bb=preview.crop((mw+offset,37,2*mw+offset,mh+37))
                        else: aa=preview.crop((37,offset,mw+37,mh+offset));bb=preview.crop((37,mh+offset,mw+37,2*mh+offset))
                        assert aa.tobytes()==bb.tobytes()
            # Frozen v0.2 comparison, same elements/background/seed/size, not a deployed renderer.
            old_sel={**selections,'parameters':'default','backgroundColor':'#f3ebdb','outputSize':[900,1200] if pilot['id']=='P3' else selections['outputSize']}
            palette={'bg':'#f3ebdb','ink':'#152c23','gold':'#948861','red':'#9c3833','blue':'#23415c'}
            old,warnings=old_render(chosen,old_sel,palette,{},GALLERY/(pilot['id']+'-old.png'),GALLERY/(pilot['id']+'-old.jpg'))
            old.update(seed=42,selections=old_sel,comparisonOnly=True,rendererSourceSha256=digest((BASE/'app/legacy_review_renderer.py').read_bytes()))
            (GALLERY/(pilot['id']+'-old.json')).write_text(json.dumps({'recipe':old,'warnings':warnings},ensure_ascii=False,indent=2))
            records.append({'name':pilot['id']+'-old','image':pilot['id']+'-old.png','recipe':pilot['id']+'-old.json','elementCodes':pilot['codes'],'pngSha256':digest((GALLERY/(pilot['id']+'-old.png')).read_bytes()),'size':old['size'],'description':'Сравнение с renderer v0.2 на том же наборе PNG.'})
        # Explain unsupported manual combinations. No hidden subset/replacement.
        s={**selections,'composition':'medallion','elementCodes':['TP-E-020','TP-E-019'],'rapportOutput':'module'}
        rejected=client.post('/api/generations',json={'selections':s});assert rejected.status_code==422
        assert rejected.json()['error']['details']['selectedElementCodes']==s['elementCodes']
        assert rejected.json()['error']['details']['requiresExplicitSelection']
        # Scoped output validation and readable-size rejection.
        for override,code in [({'composition':'rapport','elementCodes':pilots[2]['codes'],'moduleSize':[256,256]},'MODULE_TOO_SMALL'),
                              ({'composition':'medallion','elementCodes':pilots[0]['codes'],'outputSize':[720,1280],'scale':2,'rapportOutput':'module'},'COMPOSITION_TOO_LARGE'),
                              ({'composition':'rapport','elementCodes':pilots[2]['codes'],'colorMode':'silhouette'},'PILOT_REQUIRES_ORIGINAL')]:
            res=client.post('/api/generations',json={'selections':{**selections,**override}});assert res.status_code==422,res.text;assert res.json()['error']['code']==code
        module_sel={**selections,'rapportOutput':'module','moduleSize':[480,480]}
        module_gen=client.post('/api/generations',json={'selections':module_sel}).json()['generation']
        assert module_gen['seamless'] and module_gen['outputKind']=='repeat_module'
        aligned={**module_sel,'rapportOutput':'sample','moduleSize':[400,400],'parameters':'dense','outputSize':[800,1200]}
        aligned_gen=client.post('/api/generations',json={'selections':aligned}).json()['generation']
        assert aligned_gen['seamless'] and aligned_gen['outputKind']=='pattern_sample'
        transparent={**module_sel,'transparentBackground':True}
        tg=client.post('/api/generations',json={'selections':transparent}).json()['generation']
        tim=Image.open(io.BytesIO(client.get(tg['imageUrl']).content));assert tim.getchannel('A').getextrema()[0]==0
        assert 'TRANSPARENT_CONTRAST_UNKNOWN' in [w['code'] for w in tg['warnings']]
        # Current unavailable AI stays unavailable; no provider/GPU launch.
        assert client.post('/api/generations',json={'mode':'ai','selections':selections}).json()['error']['code']=='AI_PROVIDER_UNCONFIGURED'
        # Legacy rapport rectangular periods: exact divisibility, large modules instead of gcd collapse.
        for wh in ([900,1200],[720,1280]):
            legacy=client.post('/api/generations',json={'selections':{**selections,'renderer':'legacy','parameters':'default','rapportOutput':'module','outputSize':wh}}).json()['generation']
            assert legacy['seamless'] and legacy['outputKind']=='repeat_module'
            tw,th=legacy['repeat']['periodPx'];assert wh[0]%tw==wh[1]%th==0;assert min(tw,th)>=150
        first=generations[0]
        client.patch('/api/generations/'+first['id'],json={'title':'Review pilot','rating':'like'})
        # Store an actual old recipe row: fallback must not rewrite DB params.
        old_params={'selections':{'composition':'border','parameters':'default','usage':'web'},'recipe':{'algorithmVersion':'algorithmic-pillow-v0.2','elements':[],'colorMode':'original','layout':{'rows':3}}}
        with psycopg.connect(scoped) as conn:
            old_id=conn.execute("INSERT INTO generations(user_id,status,params,model_version) VALUES((SELECT id FROM users WHERE email=%s),'done',%s,'algorithmic-pillow-v0.2') RETURNING id",(email,Jsonb(old_params))).fetchone()[0]
    with TestClient(create_app(settings)) as reopened:
        assert reopened.post('/api/auth/login',json={'email':email,'password':password}).status_code==200
        for gen in generations:
            got=reopened.get('/api/generations/'+gen['id']).json()['generation']
            assert got['descriptionDetails']==gen['descriptionDetails'] and got['recipe']==gen['recipe']
            assert digest(reopened.get(got['imageUrl']).content)==gen['recipe']['outputSha256']['png']
        assert reopened.get('/api/generations').json()['total']>=len(generations)
        fallback=reopened.get('/api/generations/'+str(old_id)).json()['generation']
        assert fallback['descriptionDetails']['basis']=='legacy_recipe' and fallback['culturalNote'] is None
        with psycopg.connect(scoped) as conn:assert conn.execute('SELECT params FROM generations WHERE id=%s',(old_id,)).fetchone()[0]==old_params
    with TestClient(create_app(settings)) as other:
        other.post('/api/auth/register',json={'email':uuid4().hex+'@example.com','password':password})
        assert other.get(first['imageUrl']).status_code==404
        assert other.get('/api/generations/'+first['id']).status_code==404
        assert other.get(generations[-1]['moduleUrl']).status_code==404
        assert other.post('/api/generations',json={'selections':selections,'projectId':project}).status_code==404
    assert len(records)==9
    (GALLERY/'manifest.json').write_text(json.dumps({'status':'awaiting_owner_visual_review','database':'isolated_test:55432','schema':schema,'records':records,'snapshotSha256':review()[1]},ensure_ascii=False,indent=2))


def test_transform_identity_points_unknown_and_requested_only(tmp_path):
    docs,_=review();items={i['code']:i for i in docs['metadata.json']['items']}
    def row(code):return {'code':code,'content_sha256':items[code]['flat_sha256'],'local_path':BASE/'catalog-input/flat'/(code+'.png')}
    # Unknown orientation stays exactly in PNG presentation even with a requested axis.
    sprite,info=transformed(row('TP-E-020'),128,90)
    assert info['clockwiseDegrees']==0 and info['attachmentSprite'] is None
    # A downward framing pair is not automatically turned upwards.
    _,info=transformed(row('TP-E-052'),144,180);assert info['clockwiseDegrees']==0
    # Named points use the same matrix as crop/mask including rotation+expand.
    _,info=transformed(row('TP-E-051'),112,35)
    uv=items['TP-E-051']['attachment']['uv'];w,h=info['cropSize'];matrix=info['cropToSpriteMatrix']
    expected=[matrix[0][0]*uv[0]*w+matrix[0][1]*uv[1]*h+matrix[0][2],matrix[1][0]*uv[0]*w+matrix[1][1]*uv[1]*h+matrix[1][2]]
    assert info['attachmentSprite']==pytest.approx(expected)
    wrong={**row('TP-E-020'),'content_sha256':'0'*64}
    with pytest.raises(APIError) as error:metadata(wrong)
    assert error.value.payload['error']['code']=='REVIEW_ASSET_MISMATCH'
    for composition in ['medallion','border','rapport']:
        selections={'composition':composition,'elementCodes':['TP-E-020'],'usage':'web'}
        explanation=describe({'input':{'elements':[{'code':'TP-E-020'}]}},selections,mode='ai')
        assert explanation['basis']=='requested_only' and explanation['claimType']=='request'
        assert explanation['facts']['observed'] is None and explanation['facts']['verified'] is None
        assert explanation['text'].startswith('Для генерации выбраны')
        assert 'сохранены' not in explanation['text'] and 'симметри' not in explanation['text'] and 'бесшовн' not in explanation['text']
        assert explanation['culturalNote'] is None
    saved={'text':'Сохранённый текст.','templateVersion':'old'}
    assert saved_or_fallback({'recipe':{'description':saved}})==saved
