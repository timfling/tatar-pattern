#!/usr/bin/env python3
"""Start existing GPU HTTP in qualification/normal mode; never submits inference."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import pwd
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request

ROOT=Path('/srv/tatar-lora-kit')
CFG=ROOT/'service/config-window-20261024.json'
RECORD=ROOT/'service/http-record-20261024.json'
DROPIN=Path('/etc/systemd/system/tatar-inference.service.d/40-window.conf')
BOOT='99fa5828-85de-4c5c-9084-5bb087dbabdc'
DIGEST='51615fddf6fa09d8ad2155f432a3c79bccef9f810e996f4167000e5abe617771'
# Reserve 23min before16:33MSK for bounded drain, backup and Shelve.
DEADLINE=datetime(2026,10,24,13,10,tzinfo=timezone.utc).timestamp()


def require(ok,msg):
    if not ok:raise RuntimeError(msg)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('qualification','normal'))
    args=parser.parse_args()
    require(os.geteuid()==0,'Run sudo python3 on GPU')
    os.umask(0o077)
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT,'GPU boot changed; stop and reconcile')
    require(time.time()<DEADLINE,'Window admission deadline reached; do not reopen automatically')
    guard=DROPIN.with_name('30-egress.conf')
    require(guard.is_file() and 'IPAddressDeny=any' in guard.read_text() and
            'IPAddressAllow=localhost' in guard.read_text(),'Loopback-only service guard missing')
    config=json.loads((ROOT/'service/config.json').read_text())
    config.update(gpu_smoke_path=str(RECORD),admission_deadline_epoch=DEADLINE)
    text=json.dumps(config,indent=2)+'\n'
    if CFG.exists():require(CFG.read_text()==text,'Window config differs; no overwrite')
    else:
        with CFG.open('x') as stream:stream.write(text)
        owner=pwd.getpwnam('ubuntu');os.chown(CFG,owner.pw_uid,owner.pw_gid);CFG.chmod(0o600)
    state=subprocess.check_output(['systemctl','show','--value','-p','ActiveState','tatar-inference.service']).strip()
    if args.mode=='qualification':
        require(state in (b'inactive',b'failed'),'Qualification start requires stopped service')
        require(not RECORD.exists(),'Fresh record already exists; do not repeat qualification')
    else:
        record=json.loads(RECORD.read_text())
        pairs=json.loads(Path('/tmp/qualification-approved-20261024.json').read_text())['pairs']
        require(record.get('passed') is True and record.get('httpVerified') is True and
                record.get('bootId')==BOOT and record.get('deploymentDigest')==DIGEST and
                {p['baseId']+':'+p['ornamentStyle'] for p in record['completedProfiles']}==set(pairs),
                'Fresh accepted current-boot record for exactly25 pairs required')
        if state==b'active':subprocess.run(['systemctl','stop','tatar-inference.service'],check=True)
        else:require(state in (b'inactive',b'failed'),'Unexpected service state')
    with sqlite3.connect((ROOT/'service/state/jobs.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        require(db.execute("select count(*) from jobs where status in ('queued','running')").fetchone()[0]==0,
                'Unfinished GPU jobs exist; no service mode switch')
    command=f'{ROOT}/.venv/bin/python {ROOT}/service/server.py --config {CFG} --state {ROOT}/service/state --port 8765'
    if args.mode=='qualification':command+=' --qualification-mode'
    source='# Managed by gpu_window_service_20261024.py\n[Service]\nExecStart=\nExecStart='+command+'\n'
    if DROPIN.exists():require(not DROPIN.is_symlink() and '# Managed by gpu_window_service_20261024.py' in DROPIN.read_text(),'Unknown service override')
    temp=DROPIN.with_suffix('.tmp')
    require(not temp.exists() and not temp.is_symlink(),'Temporary service override exists')
    temp.write_text(source);temp.chmod(0o644);os.replace(temp,DROPIN)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','start','tatar-inference.service'],check=True)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    token=(ROOT/'service/token').read_text().strip()
    deadline=time.monotonic()+90
    while True:
        request=urllib.request.Request('http://127.0.0.1:8765/v1/health',headers={'Authorization':'Bearer '+token})
        try:
            try:response=opener.open(request,timeout=5)
            except urllib.error.HTTPError as error:response=error
            with response:code=response.status;health=json.load(response)
            break
        except (OSError,ValueError):
            require(time.monotonic()<deadline,'GPU HTTP startup timeout; inspect service without resubmit')
            time.sleep(1)
    expected=503 if args.mode=='qualification' else 200
    require(code==expected and health.get('qualificationMode')==(args.mode=='qualification') and
            health.get('bootId')==BOOT and health.get('deploymentDigest')==DIGEST and
            health.get('draining') is False,'Unexpected GPU health/mode/identity')
    (ROOT/'service'/('health-'+args.mode+'-20261024.json')).write_text(json.dumps({'httpStatus':code,'health':health},indent=2)+'\n')
    print('GPU HTTP '+args.mode.upper()+' MODE PASS; HTTP'+str(code)+'; boot='+BOOT)
    print('queueDepth='+str(health.get('queueDepth'))+'; qualified='+str(sum(p.get('qualified',False) for p in health['profiles'])))
    print('Admission ends16:10MSK; no inference submitted by this operation')


if __name__=='__main__':
    try:main()
    except Exception as exc:raise SystemExit('STOP: '+str(exc))
