#!/usr/bin/env python3
"""Confirm native HTTP1.0 EOF bug; install external readonly override, AI stays OFF."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

SOURCE_SHA='b125caa33bfb2d2f6c0fc445fdc480f6bac199ed29fdaadaaef5c40c6d6a85b9'
FIXED_SHA='7776b706ed864472d89f48bd9eed346a871c8e5f4eb5263d0027b76e39607546'
DIAG=r'''
import sys,errno
from app.ai_provider import configured_provider,ProviderError
seen=[]
def trace(frame,event,arg):
 if frame.f_code.co_name=='_request' and event=='exception':
  kind,error,_=arg
  if isinstance(error,OSError):
   seen.append(getattr(error,'errno',None))
   print('NATIVE HTTP ERROR: '+kind.__name__+' errno='+str(getattr(error,'errno',None)),flush=True)
 return trace
sys.settrace(trace)
try:
 configured_provider().health(refresh=True)
except ProviderError as error:print('Provider code: '+error.code,flush=True)
finally:sys.settrace(None)
if errno.EBADF not in seen:raise SystemExit('Expected HTTP1.0 EOF defect not confirmed; no hotfix applied')
print('NATIVE HTTP10 EOF DEFECT CONFIRMED',flush=True)
'''


def require(ok,msg):
    if not ok:raise RuntimeError(msg)


def main():
    require(os.geteuid()==0,'Run on Beget as root')
    os.umask(0o077)
    supplied=Path('/srv/tatar-pattern/incoming/ai_provider.http10.py')
    require(hashlib.sha256(supplied.read_bytes()).hexdigest()==FIXED_SHA,'Supplied hotfix SHA differs')
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
        require(all(config['services'][s]['environment']['AI_MVP_ENABLED']=='false' and
                    str(config['services'][s]['environment']['GUEST_GPU_BUDGET'])=='0' for s in ('backend','ai-worker')),
                'Hotfix only before site enablement with AI=false/budget0')
        unfinished=ops.pg(dc,'psql','-At','-c',"SELECT count(*) FROM ai_jobs WHERE state IN ('queued','submitting','polling')")
        require(int(unfinished.strip())==0,'Unfinished AI jobs; preserve state, no hotfix')
        cid=dc('ps','-q','ai-worker',capture=True).decode().strip();require(bool(cid),'Worker not running')
        actual=subprocess.check_output(['docker','exec',cid,'python','-c',
          "import hashlib;from pathlib import Path;print(hashlib.sha256(Path('/app/backend/app/ai_provider.py').read_bytes()).hexdigest())"]).decode().strip()
        require(actual==SOURCE_SHA,'Worker source differs from sealed baseline; no overwrite')
        result=subprocess.run(['docker','exec',cid,'python','-c',DIAG],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        print(result.stdout.decode(errors='replace'),flush=True)
        require(result.returncode==0 and b'NATIVE HTTP10 EOF DEFECT CONFIRMED' in result.stdout,'Native defect not confirmed')
        target=Path('/etc/tatar-pattern/runtime-hotfix/ai_provider.py');target.parent.mkdir(mode=0o700,exist_ok=True)
        require(not target.parent.is_symlink() and not target.is_symlink(),'Unsafe hotfix path')
        if target.exists():require(hashlib.sha256(target.read_bytes()).hexdigest()==FIXED_SHA,'Existing hotfix differs')
        else:
            with target.open('xb') as stream:stream.write(supplied.read_bytes())
            target.chmod(0o644)
        override=Path('/etc/tatar-pattern/staging-ai.yml');original=override.read_bytes()
        backup=override.with_name('staging-ai.before-http10-20261024.yml')
        require(not backup.exists() and not backup.is_symlink(),'Hotfix already attempted; inspect before retry')
        with backup.open('xb') as stream:stream.write(original)
        backup.chmod(0o600)
        source='# External HTTP1.0 EOF override; GPU payload and sealed release unchanged\nservices:\n'
        for service in ('backend','ai-worker'):
            source+=f'  {service}:\n    environment:\n      AI_MVP_ENABLED: "false"\n      GUEST_GPU_BUDGET: "0"\n    volumes:\n'
            source+='      - type: bind\n        source: '+str(target)+'\n        target: /app/backend/app/ai_provider.py\n        read_only: true\n        bind: {create_host_path: false}\n'
        dc('stop','-t','120','backend')
        info=m.worker_info(dc);m.drain(dc,info)
        temp=override.with_name('.staging-ai.http10.tmp');require(not temp.exists(),'Temporary override exists')
        temp.write_text(source);temp.chmod(0o600);os.replace(temp,override)
        dc=m.make_dc(values);m.validate_config(json.loads(dc('config','--format','json',capture=True)),True)
        dc('up','-d','--wait','--no-build','--no-deps','backend','ai-worker')
        time.sleep(2)
        for service in ('backend','ai-worker'):
            cid=dc('ps','-q',service,capture=True).decode().strip()
            digest=subprocess.check_output(['docker','exec',cid,'python','-c',
             "import hashlib;from pathlib import Path;print(hashlib.sha256(Path('/app/backend/app/ai_provider.py').read_bytes()).hexdigest())"]).decode().strip()
            require(digest==FIXED_SHA,'Runtime hotfix SHA mismatch')
        m.health(dc,True)
        print('HTTP10 EXTERNAL HOTFIX INSTALLED; API/worker SHA verified; idle worker drain confirmed; AI=false/budget0')


if __name__=='__main__':
    try:main()
    except Exception as exc:raise SystemExit('STOP: '+str(exc))
