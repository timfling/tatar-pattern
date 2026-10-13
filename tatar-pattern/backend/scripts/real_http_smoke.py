"""Real HTTP/process restart on explicitly selected local project DB.
Creates one test account/project/history result; no passwords/session in report.
"""
import hashlib
import json
import os
import subprocess
import socket
import time
from pathlib import Path
from uuid import uuid4
import httpx
from .db_admin import require_local_environment

BASE=Path(__file__).resolve().parents[1]
with socket.socket() as port_probe:
    port_probe.bind(('127.0.0.1',0))
    PORT=port_probe.getsockname()[1]
URL=f'http://127.0.0.1:{PORT}'


def server():
    logfile=(BASE/'local-test/real-http-server.log').open('a')
    proc=subprocess.Popen([str(BASE/'.venv/bin/python'),'-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port',str(PORT)],cwd=BASE,env=os.environ.copy(),stdout=logfile,stderr=logfile)
    for _ in range(60):
        if proc.poll() is not None: raise RuntimeError('HTTP test server exited')
        try:
            response=httpx.get(URL+'/api/health',timeout=1)
            if response.status_code==200 and response.json().get('algorithmVersion')=='algorithmic-pillow-v0.2': return proc,logfile
        except httpx.HTTPError: pass
        time.sleep(0.2)
    proc.terminate(); raise RuntimeError('HTTP server did not start')


def stop(proc,log):
    proc.terminate(); proc.wait(timeout=10); log.close()


def main():
    require_local_environment()
    email='http-check-'+uuid4().hex+'@example.com'; password=uuid4().hex+uuid4().hex
    proc,log=server()
    try:
        with httpx.Client(base_url=URL,timeout=30) as client:
            response=client.get('/api/elements'); assert response.status_code==200 and response.json()['total']==110
            items=response.json()['items']; assert len({e['sha256'] for e in items})==110
            assert client.post('/api/auth/register',json={'email':email,'password':password}).status_code==201
            pid=client.post('/api/projects',json={'title':'Локальная проверка 08.10'}).json()['project']['id']
            sel={'style':'heritage','composition':'rapport','parameters':'default','elementCodes':['TP-E-008','TP-E-010','TP-E-013'],'palette':'emerald','usage':'web','transparentBackground':True,'backgroundColor':'#faf2de'}
            response=client.post('/api/generations',json={'mode':'flat','selections':sel,'projectId':pid}); assert response.status_code==201,response.text
            gen=response.json()['generation']; gid=gen['id']
            assert gen['status']=='done' and not gen['recipe']['isFixture']
            png=client.get(gen['imageUrl']); assert png.status_code==200
            jpg=client.get(f'/api/generations/{gid}/file?format=jpg&download=true'); assert jpg.status_code==200
            (BASE/'local-test/local-http.png').write_bytes(png.content); (BASE/'local-test/local-http.jpg').write_bytes(jpg.content)
            digest=hashlib.sha256(png.content).hexdigest()
            assert client.patch('/api/generations/'+gid,json={'title':'Проверка перезапуска','rating':'like'}).status_code==200
            assert client.post('/api/generations',json={'mode':'ai','selections':sel}).json()['error']['code']=='AI_PROVIDER_UNCONFIGURED'
    finally: stop(proc,log)
    proc,log=server()
    try:
        with httpx.Client(base_url=URL,timeout=30) as client:
            assert client.post('/api/auth/login',json={'email':email,'password':password}).status_code==200
            reopened=client.get('/api/generations/'+gid).json()['generation']
            assert reopened['title']=='Проверка перезапуска' and reopened['recipe']==gen['recipe']
            assert hashlib.sha256(client.get(reopened['imageUrl']).content).hexdigest()==digest
            assert any(g['id']==gid for g in client.get('/api/generations').json()['items'])
        with httpx.Client(base_url=URL,timeout=30) as other:
            other.post('/api/auth/register',json={'email':'other-'+uuid4().hex+'@example.com','password':password})
            assert other.get(gen['imageUrl']).status_code==404
            assert other.patch('/api/generations/'+gid,json={'title':'Чужой'}).status_code==404
            assert other.post('/api/generations',json={'selections':sel,'projectId':pid}).status_code==404
    finally: stop(proc,log)
    report={'environment':os.environ['TP_ENVIRONMENT'],'database':'tatar_pattern','catalog':110,'generationId':gid,'pngSha256':digest,'checks':['HTTP real catalogue','generation from 3 TP-E','PNG/JPG downloads','process stop/start and login/history/files','ownership 404','AI_PROVIDER_UNCONFIGURED distinct'],'result':'passed'}
    (BASE/'local-test/real-http-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__': main()
