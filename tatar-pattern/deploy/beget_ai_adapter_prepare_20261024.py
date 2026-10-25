#!/usr/bin/env python3
"""Receive GPU Bearer on stdin; configure real staging adapter with inference OFF."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OVERRIDE = '''# Managed by beget_ai_adapter_prepare_20261024.py
services:
  backend:
    environment:
      AI_MVP_ENABLED: "false"
      GUEST_GPU_BUDGET: "0"
  ai-worker:
    environment:
      AI_MVP_ENABLED: "false"
      GUEST_GPU_BUDGET: "0"
'''


def require(ok,msg):
    if not ok:raise RuntimeError(msg)


def exclusive_write(path,data,uid=0,gid=0):
    require(not path.is_symlink(),'Unexpected protected file symlink')
    if path.exists():
        require(path.read_bytes()==data,'Existing protected file differs; no overwrite')
        require(path.stat().st_uid==uid and path.stat().st_mode & 0o077==0,'Existing protected file permissions differ')
        return
    with path.open('xb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())
    os.chown(path,uid,gid);path.chmod(0o600)


def acquire_lock(maintenance,root,timeout=45):
    deadline=time.monotonic()+timeout
    announced=False
    while True:
        try:
            return maintenance.lock(root,blocking=False)
        except BlockingIOError:
            if not announced:
                print('Waiting for shared maintenance lock (up to45s)',flush=True)
                announced=True
            if time.monotonic()>=deadline:
                raise RuntimeError('Shared maintenance lock still busy; configuration not changed') from None
            time.sleep(1)


def main():
    require(os.geteuid()==0,'Run on Beget as root')
    os.umask(0o077)
    data=sys.stdin.buffer.read(4098)
    token=data.strip()
    require(32<=len(token)<=4096 and token.isascii() and not any(chr(c).isspace() for c in token),
            'Bearer transfer missing/invalid; no configuration changed')
    sys.path.insert(0,'/srv/tatar-pattern/releases/guest-20261020-1/deploy')
    import ops,maintenance
    spec=importlib.util.spec_from_file_location('staging_v2','/etc/tatar-pattern/staging-maintenance.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    with acquire_lock(maintenance,m.DATA):
        values=ops.read_env(m.ENVFILE)
        require(values.get('AI_API_CONFIG')=='false','Initial adapter preparation requires AI_API_CONFIG=false; inspect before retry')
        old_dc=m.make_dc(values)
        m.validate_config(json.loads(old_dc('config','--format','json',capture=True)),False)
        m.health(old_dc,False)
        require(m.worker_info(old_dc) is None,'Unexpected existing worker; reconcile before preparation')
        m.stopped_worker_safe(old_dc,None)
        root=Path('/etc/tatar-pattern/gpu')
        require(root.is_dir() and not root.is_symlink() and root.stat().st_uid==0 and
                root.stat().st_mode & 0o077==0,'Expected protected GPU directory')
        for filename in ('id_ed25519','known_hosts','transport-prepared.json'):
            require((root/filename).is_file() and not (root/filename).is_symlink(),'Transport files missing/unsafe')
        marker=json.loads((root/'transport-prepared.json').read_text())
        require(marker.get('clientFingerprint')=='SHA256:9rfANttjzdEGuC93eSPMalQRvvv7KoJNXAfBhSVxH5c',
                'Unexpected dedicated transport key')
        exclusive_write(root/'bearer',token+b'\n',10001,10001)
        exclusive_write(Path('/etc/tatar-pattern/staging-ai.yml'),OVERRIDE.encode())
        original=m.ENVFILE.read_bytes()
        exclusive_write(Path('/etc/tatar-pattern/staging.env.before-ai-20261024'),original)
        updated=dict(values,AI_API_CONFIG='true',GPU_SSH_HOST='195.209.221.75',GPU_SSH_PORT='22',
                     GPU_SSH_USER='tp-gpu-tunnel',GPU_API_PORT='8765',
                     GPU_SSH_KEY_FILE=str(root/'id_ed25519'),GPU_KNOWN_HOSTS_FILE=str(root/'known_hosts'),
                     GPU_BEARER_FILE=str(root/'bearer'),AI_EXPECTED_ONLINE='false')
        dc=m.make_dc(updated)
        config=json.loads(dc('config','--format','json',capture=True))
        m.validate_config(config,True)
        for service in ('backend','ai-worker'):
            env=config['services'][service]['environment']
            require(env['AI_MVP_ENABLED']=='false' and str(env['GUEST_GPU_BUDGET'])=='0','Inference must remain OFF')
            mounts=[v for v in config['services'][service]['volumes'] if v['target']=='/run/secrets/gpu_bearer']
            require(len(mounts)==1 and mounts[0]['read_only'] and not mounts[0]['bind']['create_host_path'],
                    'Readonly existing-file Bearer bind required')
        temp=m.ENVFILE.with_name('.staging.env.ai-prepare.tmp')
        require(not temp.exists() and not temp.is_symlink(),'Temporary env already exists')
        with temp.open('x') as stream:
            stream.write(''.join(k+'='+v+'\n' for k,v in updated.items()));stream.flush();os.fsync(stream.fileno())
        temp.chmod(0o600);os.replace(temp,m.ENVFILE)
        print('Protected Bearer received; adapter config validated; AI=false/budget0',flush=True)
        dc('up','-d','--wait','--no-build','--no-deps','gpu-tunnel')
        dc('up','-d','--wait','--no-build','--no-deps','backend')
        dc('up','-d','--wait','--no-build','--no-deps','ai-worker')
        time.sleep(2)
        m.health(dc,True)
        # Check running container flags, rather than relying only on Compose source.
        for service in ('backend','ai-worker'):
            cid=dc('ps','-q',service,capture=True).decode().strip()
            info=json.loads(subprocess.check_output(['docker','inspect',cid]))[0]
            env=dict(line.split('=',1) for line in info['Config']['Env'])
            require(env.get('AI_MVP_ENABLED')=='false' and env.get('GUEST_GPU_BUDGET')=='0','Runtime inference flags mismatch')
            mounts=[v for v in info['Mounts'] if v['Destination']=='/run/secrets/gpu_bearer']
            require(len(mounts)==1 and mounts[0]['RW'] is False,'Runtime Bearer bind is not readonly')
        print('REAL ADAPTER/WORKER/TUNNEL STARTED; runtime AI=false/budget0; readonly Bearer verified',flush=True)
        print('GPU HTTP/readiness/worker proof still pending; no inference submitted',flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:raise SystemExit('STOP: '+str(exc))
