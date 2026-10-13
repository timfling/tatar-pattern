import io
from datetime import datetime, timedelta, timezone
import psycopg
from PIL import Image
from fastapi.testclient import TestClient
from app.main import create_app

def test_profile_trash_restore_expiry_ownership_and_formats(prepared):
    settings, _ = prepared
    with TestClient(create_app(settings)) as owner, TestClient(create_app(settings)) as other:
        from uuid import uuid4
        email = uuid4().hex + '@example.com'
        credentials = {'email': email, 'password': 'integration test password'}
        profile = {'firstName':'Анна','lastName':'Тестовая','occupation':'designer','avatar':None}
        result = owner.post('/api/auth/register',json={**credentials,**profile})
        assert result.status_code == 201
        assert result.json()['user']['firstName'] == 'Анна'
        assert owner.patch('/api/auth/profile',json={**profile,'firstName':'Мария'}).json()['user']['firstName'] == 'Мария'
        owner.post('/api/auth/logout',json={})
        assert owner.post('/api/auth/login',json=credentials).status_code == 200
        assert owner.get('/api/auth/me').json()['user']['firstName'] == 'Мария'
        other.post('/api/auth/register',json={'email':uuid4().hex+'@example.com','password':credentials['password']})
        selections={'style':'modern','composition':'rapport','parameters':'default','motifs':['tulip'],'palette':'emerald','usage':'web','colorMode':'silhouette','transparentBackground':True}
        for size in ((1024,1024),(900,1200),(1200,900),(800,1200),(1200,800),(720,1280),(1280,720)):
            response=owner.post('/api/generations',json={'selections':{**selections,'outputSize':size}})
            assert response.status_code == 201,response.text
            g=response.json()['generation']
            png=Image.open(io.BytesIO(owner.get(g['imageUrl']).content))
            assert png.size == size and png.mode == 'RGBA'
            tw,th=g['recipe']['layout']['moduleSize']; tile=png.crop((0,0,tw,th)).tobytes()
            assert size[0]%tw==0 and size[1]%th==0
            for y in range(0,size[1],th):
                for x in range(0,size[0],tw):
                    assert png.crop((x,y,x+tw,y+th)).tobytes() == tile
        assert owner.post('/api/generations',json={'selections':{**selections,'outputSize':[3,5]}}).status_code == 422
        gid=g['id']
        assert other.delete('/api/generations/'+gid).status_code == 404
        assert other.post('/api/generations/'+gid+'/restore',json={}).status_code == 404
        assert owner.delete('/api/generations/'+gid).status_code == 200
        assert gid not in [g['id'] for g in owner.get('/api/generations').json()['items']]
        assert gid in [g['id'] for g in owner.get('/api/generations?trash=true').json()['items']]
        assert owner.post('/api/generations/'+gid+'/restore',json={}).status_code == 200
        assert gid in [g['id'] for g in owner.get('/api/generations').json()['items']]
        owner.delete('/api/generations/'+gid)
        with psycopg.connect(settings.database_url) as conn:
            conn.execute('UPDATE generations SET deleted_at=%s WHERE id=%s',(datetime.now(timezone.utc)-timedelta(days=8),gid))
        assert owner.get('/api/generations?trash=true').json()['items'] == []
        assert owner.post('/api/generations/'+gid+'/restore',json={}).status_code == 404
        assert owner.get(g['imageUrl']).status_code == 404
