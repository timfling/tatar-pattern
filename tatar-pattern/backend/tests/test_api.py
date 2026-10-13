from io import BytesIO
from uuid import uuid4
from PIL import Image, ImageChops
import psycopg
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings

SELECTIONS={'style':'heritage','composition':'medallion','parameters':'default','motifs':['tulip','bud'],'palette':'emerald','usage':'web'}


def test_sessions_password_and_logout(signed_in,prepared):
    client,email,password=signed_in
    assert client.get('/api/auth/me').json()['user']['email']==email
    cookie=client.cookies.get('tp_session')
    with psycopg.connect(prepared[0].database_url) as conn:
        row=conn.execute('SELECT password_hash FROM users WHERE email=%s',(email,)).fetchone()
        assert row[0].startswith('$argon2id$') and password not in row[0]
        assert conn.execute('SELECT count(*) FROM sessions WHERE token_hash=%s',(cookie,)).fetchone()[0]==0
    assert client.post('/api/auth/register',json={'email':email.upper(),'password':password}).status_code==409
    assert client.post('/api/auth/logout',json={}).json()=={'ok':True}
    assert client.get('/api/auth/me').status_code==401
    assert client.post('/api/auth/login',json={'email':email,'password':'wrong-password'}).status_code==401
    assert client.post('/api/auth/login',json={'email':email,'password':password}).status_code==200
    # Expired server-side session is rejected even if browser cookie remains.
    with psycopg.connect(prepared[0].database_url) as conn:
        conn.execute("UPDATE sessions SET expires_at=now()-interval '1 second' WHERE user_id=(SELECT id FROM users WHERE email=%s)",(email,))
    assert client.get('/api/auth/me').status_code==401


def test_origin_and_validation(client):
    assert client.post('/api/auth/login',json={'email':'me@example.com','password':'test password'},headers={'Origin':'https://attacker.example'}).status_code==403
    assert client.post('/api/auth/login',content='email=a').status_code==415
    response=client.post('/api/auth/register',json={'email':'invalid','password':'secret'})
    assert response.status_code==422
    assert 'secret' not in response.text
    assert response.json()['error']['code']=='VALIDATION_ERROR'
    assert client.get('/api/generations').status_code==401
    assert client.get('/api/health').json()['ok']
    assert client.get('/api/unknown').json()['error']['code']=='NOT_FOUND'
    oversized=client.post('/api/auth/login',content=b' '*16385,headers={'Content-Type':'application/json'})
    assert oversized.status_code==413


def test_generation_history_projects_files_and_ownership(signed_in,prepared):
    client,email,password=signed_in
    project=client.post('/api/projects',json={'title':'Проба'}).json()['project']
    pid=project['id']
    assert client.patch(f'/api/projects/{pid}',json={'title':'Новая проба'}).json()['project']['title']=='Новая проба'
    response=client.post('/api/generations',json={'selections':SELECTIONS,'prompt':'сделай больше','projectId':pid})
    assert response.status_code==201,response.text
    generation=response.json()['generation']
    gid=generation['id']
    assert generation['status']=='done' and generation['progress']==100
    assert generation['recipe']['isFixture']
    assert len(generation['recipe']['elements'])==2
    assert {'TEST_FIXTURE','PROMPT_UNSUPPORTED'}<={w['code'] for w in generation['warnings']}
    for fmt,expected in [('png','PNG'),('jpg','JPEG')]:
        file=client.get(f'/api/generations/{gid}/file?format={fmt}&download=true')
        assert file.status_code==200
        assert 'attachment;' in file.headers['content-disposition']
        with Image.open(BytesIO(file.content)) as im:
            assert im.format==expected and im.size==(800,600)
            assert len(im.getcolors(im.width*im.height))>2
    assert client.get('/api/generations',params={'projectId':pid}).json()['total']==1
    patched=client.patch(f'/api/generations/{gid}',json={'title':'Мой узор','rating':'like'}).json()['generation']
    assert patched['title']=='Мой узор' and patched['rating']=='like' and patched['projectId']==pid
    assert client.patch(f'/api/generations/{gid}',json={'rating':None}).json()['generation']['rating'] is None
    assert client.patch(f'/api/generations/{gid}',json={'rating':'invalid'}).status_code==422
    # New app instance + new login demonstrates DB/file persistence.
    with TestClient(create_app(prepared[0])) as restarted:
        assert restarted.post('/api/auth/login',json={'email':email,'password':password}).status_code==200
        assert restarted.get(f'/api/generations/{gid}').json()['generation']['title']=='Мой узор'
        assert restarted.get(generation['imageUrl']).status_code==200
    with TestClient(create_app(prepared[0])) as other:
        other.post('/api/auth/register',json={'email':f'{uuid4().hex}@example.com','password':password})
        for route in (f'/api/generations/{gid}',f'/api/generations/{gid}/file'):
            assert other.get(route).status_code==404
        assert other.patch(f'/api/generations/{gid}',json={'title':'Чужое'}).status_code==404
        assert other.patch(f'/api/projects/{pid}',json={'title':'Чужое'}).status_code==404
        assert other.delete(f'/api/projects/{pid}').status_code==404
        assert other.post('/api/generations',json={'selections':SELECTIONS,'projectId':pid}).status_code==404
    assert client.delete(f'/api/projects/{pid}').status_code==200
    assert client.get(f'/api/generations/{gid}').json()['generation']['projectId'] is None
    assert client.get(generation['imageUrl']).status_code==200


def test_empty_production_catalog_and_unavailable_motifs(signed_in,prepared):
    settings,_=prepared
    production=Settings(settings.database_url,settings.storage_root,allow_fixtures=False)
    with TestClient(create_app(production)) as client:
        client.post('/api/auth/register',json={'email':f'{uuid4().hex}@example.com','password':'production-test-password'})
        assert client.get('/api/elements').json()['items']==[]
        error=client.post('/api/generations',json={'selections':SELECTIONS})
        assert error.status_code==409 and error.json()['error']['code']=='CATALOG_EMPTY'
    client=signed_in[0]
    rows=client.get('/api/elements').json()['items']
    assert len(rows)==8
    assert client.get(rows[0]['imageUrl']).headers['content-type']=='image/png'
    with psycopg.connect(settings.database_url) as conn:
        conn.execute("UPDATE artifacts SET review_status='авто'")
    try:
        assert client.get('/api/elements').json()['items']==[]
    finally:
        with psycopg.connect(settings.database_url) as conn:
            conn.execute("UPDATE artifacts SET review_status='проверено'")
    # Disallow one motif and verify server doesn't silently substitute another.
    with psycopg.connect(settings.database_url) as conn:
        conn.execute("UPDATE elements SET status='снято' WHERE motif_class='бутон'")
    try:
        error=client.post('/api/generations',json={'selections':SELECTIONS})
        assert error.status_code==422 and error.json()['error']['details']['motifs']==['bud']
    finally:
        with psycopg.connect(settings.database_url) as conn:
            conn.execute("UPDATE elements SET status='верифицировано' WHERE motif_class='бутон'")


def test_parameters_change_pixels_and_rapport_is_periodic(signed_in):
    client=signed_in[0]
    def image(**patch):
        selected={**SELECTIONS,'colorMode':'silhouette',**patch}
        response=client.post('/api/generations',json={'selections':selected})
        assert response.status_code==201,response.text
        gen=response.json()['generation']
        return Image.open(BytesIO(client.get(gen['imageUrl']).content)),gen
    baseline,_=image()
    for patch in ({'palette':'porcelain'},{'composition':'border'},{'motifs':['horn']},{'parameters':'dense'}, *({'style':s} for s in ('modern','porcelain-sign','leather-mosaic','festive'))):
        changed,_=image(**patch)
        assert ImageChops.difference(baseline.convert('RGB'),changed.convert('RGB')).getbbox() is not None,patch
    tiled,gen=image(composition='rapport')
    tile=gen['recipe']['layout']['tileSize']
    assert tiled.size==(800,800)
    assert 'RAPPORT_SQUARE' in {w['code'] for w in gen['warnings']}
    assert ImageChops.difference(tiled.crop((0,0,tile,tile)),tiled.crop((tile,tile,2*tile,2*tile))).getbbox() is None
    for usage,expected in [('packaging',(1200,900)),('architecture',(1024,1024))]:
        changed,_=image(usage=usage)
        assert changed.size==expected


def test_failure_persists_without_fake_result(signed_in,monkeypatch):
    client=signed_in[0]
    def fail(*args,**kwargs):
        raise OSError('test storage failure')
    monkeypatch.setattr('app.main.render',fail)
    response=client.post('/api/generations',json={'selections':SELECTIONS})
    assert response.status_code==503
    assert response.json()['error']['code']=='GENERATION_FAILED'
    generation=client.get('/api/generations').json()['items'][0]
    assert generation['status']=='failed'
    assert generation['progress']==0 and generation['imageUrl'] is None
    assert client.get(f"/api/generations/{generation['id']}/file").status_code==404
