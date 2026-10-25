#!/usr/bin/env python3
"""GET-only qualification transport check inside the actual deployed worker."""
import importlib.util
import json
import os
import sys
import time

BODY=r'''
import json,urllib.request,urllib.error
from pathlib import Path
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
url='http://gpu-tunnel:18765/v1/health'
def call(headers):
 try:r=opener.open(urllib.request.Request(url,headers=headers),timeout=8)
 except urllib.error.HTTPError as error:r=error
 with r:return r.status,json.load(r)
unauth,_=call({})
token=Path('/run/secrets/gpu_bearer').read_text().strip()
code,h=call({'Authorization':'Bearer '+token})
assert unauth==401 and code==503 and h.get('qualificationMode') is True and h.get('draining') is False
assert h.get('bootId')=='99fa5828-85de-4c5c-9084-5bb087dbabdc'
assert h.get('deploymentDigest')=='51615fddf6fa09d8ad2155f432a3c79bccef9f810e996f4167000e5abe617771'
assert h.get('contractVersion')=='tp-gpu-img2img/1.0' and h.get('catalogVersion')=='2026-10-18.1'
assert len(h['profiles'])==28 and h['queueDepth']==0
result={'authWithoutToken':unauth,'httpStatus':code,'qualificationMode':True,'bootId':h['bootId'],
'deploymentDigest':h['deploymentDigest'],'profiles':len(h['profiles']),'queueDepth':h['queueDepth'],
'submitCount':0,'workerNamespace':True,'finalWorkerProof':False}
Path('/data/storage/gpu-qualification-transport-20261024.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True)
print('REAL WORKER QUALIFICATION TRANSPORT PASS; submit0; final qualification proof pending',flush=True)
'''


def main():
    if os.geteuid()!=0:raise RuntimeError('Run on Beget as root')
    sys.path.insert(0,'/srv/tatar-pattern/releases/guest-20261020-1/deploy')
    import ops,maintenance
    spec=importlib.util.spec_from_file_location('staging_v2','/etc/tatar-pattern/staging-maintenance.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    deadline=time.monotonic()+45
    while True:
        try:lock=maintenance.lock(m.DATA,blocking=False);break
        except BlockingIOError:
            if time.monotonic()>deadline:raise RuntimeError('Maintenance lock busy') from None
            time.sleep(1)
    with lock:
        values=ops.read_env(m.ENVFILE)
        if values.get('AI_API_CONFIG')!='true':raise RuntimeError('Real adapter required')
        dc=m.make_dc(values);m.validate_config(json.loads(dc('config','--format','json',capture=True)),True)
        result=dc('exec','-T','ai-worker','python','-c',BODY,capture=True,check=False)
        print(result.decode(errors='replace'),flush=True)
        if b'REAL WORKER QUALIFICATION TRANSPORT PASS;' not in result:raise RuntimeError('Worker qualification transport not verified')
        m.health(dc,True)


if __name__=='__main__':
    try:main()
    except Exception as exc:raise SystemExit('STOP: '+str(exc))
