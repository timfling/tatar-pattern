#!/usr/bin/env python3
"""Enable one owner-approved pair on closed staging, budget2; no submit."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BOOT='99fa5828-85de-4c5c-9084-5bb087dbabdc'
FIXED_SHA='7776b706ed864472d89f48bd9eed346a871c8e5f4eb5263d0027b76e39607546'


def require(ok,msg):
    if not ok:raise RuntimeError(msg)


def validate_registry(original,proposed,rows,flag,select):
    require({k:v for k,v in original.items() if k!=rows}=={k:v for k,v in proposed.items() if k!=rows},'Registry header changed')
    require(len(original[rows])==len(proposed[rows]),'Registry row count changed')
    for a,b in zip(original[rows],proposed[rows]):
        require({k:v for k,v in a.items() if k!=flag}=={k:v for k,v in b.items() if k!=flag},'Registry recipe/identity changed')
        require(b.get(flag) is bool(select(b)),'Unapproved registry gate')
    require(sum(bool(p[flag]) for p in proposed[rows])==1,'Exactly one authorized gate required')


def main():
    require(os.geteuid()==0,'Run on Beget as root')
    os.umask(0o077)
    incoming=Path('/srv/tatar-pattern/incoming')
    profiles=json.loads((incoming/'ai-profiles.proposed.json').read_text())
    bases=json.loads((incoming/'ai-bases-index.proposed.json').read_text())
    approved=json.loads((incoming/'qualification-current-20261024.json').read_text())
    require(approved.get('ownerAccepted') is True and approved.get('bootId')==BOOT,'Current owner-accepted qualification required')
    sys.path.insert(0,'/srv/tatar-pattern/releases/guest-20261020-1/deploy')
    import ops,maintenance
    spec=importlib.util.spec_from_file_location('v2','/etc/tatar-pattern/staging-maintenance.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    deadline=time.monotonic()+45
    while True:
        try:lock=maintenance.lock(m.DATA,blocking=False);break
        except BlockingIOError:
            require(time.monotonic()<deadline,'Maintenance lock busy');time.sleep(1)
    with lock:
        values=ops.read_env(m.ENVFILE);require(values.get('AI_API_CONFIG')=='true','Real adapter required')
        dc=m.make_dc(values);config=json.loads(dc('config','--format','json',capture=True));m.validate_config(config,True)
        require(config['services']['backend']['environment']['AI_MVP_ENABLED']=='false','Enable already attempted; inspect before retry')
        require(time.time()<1792847400,'Admission deadline reached') #24Oct2026 13:10UTC
        proof=json.loads((m.DATA/'storage/ai-gpu-worker-proof.json').read_text())
        require(proof.get('workerNamespace') is True and proof.get('bootId')==BOOT and
                proof.get('deploymentDigest')==approved['deploymentDigest'] and
                0<=time.time()-proof['checkedAt']<=86400 and len(proof['profiles'])==25,'Fresh real proof required')
        require({p['jobId'] for p in proof['results']}=={p['jobId'] for p in approved['profiles']},'Proof jobs differ from fresh qualification')
        app=m.RELEASE/'backend/app'
        validate_registry(json.loads((app/'ai-profiles.json').read_text()),profiles,'profiles','releaseApproved',
                          lambda p:p['baseId']=='f10-wreath' and p['ornamentStyle']=='graphic')
        validate_registry(json.loads((app/'ai-assets/index.json').read_text()),bases,'bases','externalTransferApproved',
                          lambda p:p['id']=='f10-wreath')
        used=int(ops.pg(dc,'psql','-At','-c',"SELECT coalesce((SELECT used FROM guest_budget WHERE key='gpu-total'),0)").strip())
        require(used==0,'Guest GPU budget already used; no reset/increase attempted')
        require(int(ops.pg(dc,'psql','-At','-c',"SELECT count(*) FROM ai_jobs WHERE state IN ('queued','submitting','polling')").strip())==0,'Unfinished jobs; no config switch')
        hotfix=Path('/etc/tatar-pattern/runtime-hotfix/ai_provider.py')
        require(hashlib.sha256(hotfix.read_bytes()).hexdigest()==FIXED_SHA,'Verified HTTP client hotfix required')
        for service in ('backend','ai-worker'):
            cid=dc('ps','-q',service,capture=True).decode().strip()
            actual=subprocess.check_output(['docker','exec',cid,'python','-c',"from pathlib import Path;import hashlib;print(hashlib.sha256(Path('/app/backend/app/ai_provider.py').read_bytes()).hexdigest())"]).decode().strip()
            require(actual==FIXED_SHA,'Runtime hotfix mismatch')
        # Live normal health before any gate change.
        dc('exec','-T','ai-worker','python','/opt/deploy/ai-readiness.py')
        dc('stop','-t','120','backend');m.drain(dc,m.worker_info(dc))
        target=Path('/etc/tatar-pattern/ai-window');require(not target.is_symlink(),'Unsafe registry directory')
        target.mkdir(mode=0o700,exist_ok=True)
        for filename,data in [('ai-profiles.json',profiles),('ai-bases-index.json',bases)]:
            path=target/filename;require(not path.exists() and not path.is_symlink(),'Registry already exists; no overwrite')
            with path.open('x') as stream:json.dump(data,stream,ensure_ascii=False,indent=2);stream.write('\n')
            os.chown(path,10001,10001);path.chmod(0o600)
        override=Path('/etc/tatar-pattern/staging-ai.yml')
        backup=override.with_name('staging-ai.before-site-20261024.yml');require(not backup.exists(),'Enable already attempted')
        with backup.open('xb') as stream:stream.write(override.read_bytes())
        backup.chmod(0o600)
        source='# Owner approved closed f10-wreath:graphic window; totalguestbudget2\nservices:\n'
        for service in ('backend','ai-worker'):
            source+=f'  {service}:\n    environment:\n      AI_MVP_ENABLED: "true"\n      GUEST_GPU_BUDGET: "2"\n    volumes:\n'
            for src,dest in [(str(hotfix),'/app/backend/app/ai_provider.py'),(str(target/'ai-profiles.json'),'/app/backend/app/ai-profiles.json'),(str(target/'ai-bases-index.json'),'/app/backend/app/ai-assets/index.json')]:
                source+='      - type: bind\n        source: '+src+'\n        target: '+dest+'\n        read_only: true\n        bind: {create_host_path: false}\n'
        temp=override.with_name('.staging-ai.site.tmp');require(not temp.exists(),'Temporary override exists')
        temp.write_text(source);temp.chmod(0o600);os.replace(temp,override)
        dc=m.make_dc(values);m.validate_config(json.loads(dc('config','--format','json',capture=True)),True)
        dc('up','-d','--wait','--no-build','--no-deps','backend','ai-worker');time.sleep(2)
        command=['python','-m','scripts.ai_gpu_probe','--owner-run','--worker-namespace']
        for p in approved['profiles']:command+=['--job-id',p['jobId']]
        dc('exec','-T','ai-worker',*command)
        m.health(dc,True)
        curl=['curl','--fail','--silent','--show-error','--max-time','15','--cacert','/etc/tatar-pattern/staging-root-ca.crt','--resolve','localhost:18080:127.0.0.1']
        catalog=json.loads(subprocess.check_output(curl+['https://localhost:18080/api/ai-bases']))
        allowed=[b['id']+':'+s['id'] for b in catalog['bases'] for s in b['styles'] if s['available']]
        require(allowed==['f10-wreath:graphic'],'Unexpected available AI pairs')
        m.atomic_json(m.DATA/'checks/site-ai-window-20261024.json',{'enabledPair':allowed[0],'guestGpuBudget':2,
           'bootId':BOOT,'proofRefreshedInNewWorker':True,'startedAt':time.time(),'admissionUntil':'2026-10-24T13:10:00Z','gpuJobsBeforeSite':25})
        print('CLOSED SITE AI READY: f10-wreath:graphic only; totalguestbudget2; readonly registries+hotfix; fresh worker proof; submit0')


if __name__=='__main__':
    try:main()
    except Exception as exc:raise SystemExit('STOP: '+str(exc))
