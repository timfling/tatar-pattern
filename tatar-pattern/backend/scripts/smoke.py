"""Real HTTP lifecycle check against an explicitly selected localhost API."""
import argparse
import json
import secrets
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import httpx
from PIL import Image


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8000')
    parser.add_argument('--output-dir',type=Path,default=Path('local-test/smoke'))
    args=parser.parse_args()
    if httpx.URL(args.url).host not in ('localhost','127.0.0.1'):
        parser.error('This development check only accepts localhost')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    email=f'smoke-{uuid4().hex}@example.com'
    password=secrets.token_urlsafe(24)
    with httpx.Client(base_url=args.url,timeout=60,headers={'Origin':args.url}) as client:
        health=client.get('/api/health'); health.raise_for_status()
        registered=client.post('/api/auth/register',json={'email':email,'password':password})
        registered.raise_for_status()
        assert 'HttpOnly' in registered.headers['set-cookie']
        client.get('/api/auth/me').raise_for_status()
        project=client.post('/api/projects',json={'title':'HTTP-проверка'})
        project.raise_for_status()
        pid=project.json()['project']['id']
        response=client.post('/api/generations',json={'selections':{'style':'festive','composition':'medallion','parameters':'default','motifs':['tulip','bud'],'palette':'emerald','usage':'web'},'projectId':pid})
        response.raise_for_status()
        gen=response.json()['generation']
        gid=gen['id']
        assert gen['status']=='done'
        patched=client.patch(f'/api/generations/{gid}',json={'title':'Узор HTTP-проверки','rating':'like'})
        patched.raise_for_status()
        for format,expected in [('png','PNG'),('jpg','JPEG')]:
            file=client.get(f'/api/generations/{gid}/file',params={'format':format,'download':'true'})
            file.raise_for_status()
            with Image.open(BytesIO(file.content)) as im:
                assert im.format==expected and im.size==(800,600)
            (args.output_dir/f'result.{format}').write_bytes(file.content)
        client.post('/api/auth/logout',json={}).raise_for_status()
        assert client.get('/api/auth/me').status_code==401
        client.post('/api/auth/login',json={'email':email,'password':password}).raise_for_status()
        opened=client.get(f'/api/generations/{gid}')
        opened.raise_for_status()
        assert opened.json()['generation']['title']=='Узор HTTP-проверки'
        client.delete(f'/api/projects/{pid}').raise_for_status()
        assert client.get(f'/api/generations/{gid}').json()['generation']['projectId'] is None
        assert client.get('/api/generations').json()['total']>=1
        client.post('/api/auth/logout',json={}).raise_for_status()
    result={'ok':True,'generationId':gid,'isFixture':gen['recipe']['isFixture'],
            'png':str((args.output_dir/'result.png').resolve()),'jpg':str((args.output_dir/'result.jpg').resolve()),
            'checks':['register','me','projects','generate','rename','rate','png','jpg','logout','login','reopen','delete-project-preserves-history']}
    (args.output_dir/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    main()
