#!/usr/bin/env python3
"""One-off SSH restriction check in sealed tunnel image, without HTTP/inference."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import subprocess

BODY = r'''
import subprocess,socket,time,sys
sys.stderr=sys.stdout
base=['ssh','-T','-p','22','-l','tp-gpu-tunnel','-i','/run/ssh/id_ed25519',
 '-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
 '-o','UserKnownHostsFile=/run/ssh/known_hosts','-o','GlobalKnownHostsFile=/dev/null',
 '-o','ConnectTimeout=10','-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=5',
 '-o','ServerAliveCountMax=2']
host='195.209.221.75'
p=subprocess.Popen(base+['-N','-L','127.0.0.1:18765:127.0.0.1:8765',host],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
try:
 deadline=time.monotonic()+15
 while True:
  if p.poll() is not None:
   raise RuntimeError('SSH tunnel exited: '+p.communicate()[1].decode())
  try:
   with socket.create_connection(('127.0.0.1',18765),timeout=.5):pass
   break
  except OSError:
   if time.monotonic()>deadline:raise RuntimeError('Tunnel listener not ready')
   time.sleep(.2)
 time.sleep(.5)
 if p.poll() is not None:raise RuntimeError('SSH tunnel did not remain alive')
 print('Dedicated key authentication + local tunnel listener PASS',flush=True)
finally:
 if p.poll() is None:p.terminate()
 try:p.communicate(timeout=5)
 except subprocess.TimeoutExpired:p.kill();p.communicate()
checks=[('shell',base+[host,'/bin/true'],('open failed','administratively prohibited','session open refused','channel 0: open failed')),
 ('remote forwarding',base+['-N','-R','127.0.0.1:18766:127.0.0.1:8765',host],('remote port forwarding failed',)),
 ('unapproved target',base+['-W','127.0.0.1:22',host],('administratively prohibited',))]
for label,args,markers in checks:
 result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
 detail=result.stderr.decode().lower()
 if result.returncode==0 or not any(s in detail for s in markers):
  raise RuntimeError(label+' rejection not verified: '+detail)
 print(label+' denied PASS',flush=True)
print('SSH TRANSPORT RESTRICTIONS PASS; HTTP/readiness/worker proof NOT TESTED',flush=True)
'''


def main():
    if os.geteuid()!=0:raise RuntimeError('Run on Beget as root')
    sys.path.insert(0,'/srv/tatar-pattern/releases/guest-20261020-1/deploy')
    import ops,maintenance
    spec=importlib.util.spec_from_file_location('staging_v2','/etc/tatar-pattern/staging-maintenance.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    with maintenance.lock(m.DATA,blocking=False):
        values=ops.read_env(m.ENVFILE)
        if values.get('AI_API_CONFIG')!='false':raise RuntimeError('Initial transport check requires current AI=false staging')
        dc=m.make_dc(values)
        m.validate_config(json.loads(dc('config','--format','json',capture=True)),False)
        subprocess.check_output(['docker','image','inspect','tatar-pattern-tunnel:guest-20261020-1'])
        result=dc('run','--rm','--no-deps','--pull','never','-T',
           '--name','tp-gpu-transport-check-20261024','--entrypoint','python',
           'gpu-tunnel','-c',BODY,capture=True,check=False)
        print(result.decode(errors='replace'),flush=True)
        if b'SSH TRANSPORT RESTRICTIONS PASS;' not in result:
            raise RuntimeError('Transport check incomplete; inspect output above')
        m.health(dc,False)


if __name__=='__main__':
    try:main()
    except Exception as exc:raise SystemExit('STOP: '+str(exc))
