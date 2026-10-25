#!/usr/bin/env python3
"""Enforce/test loopback-only networking for GPU inference service; no inference."""
from pathlib import Path
import os
import subprocess
import time

CONFIG = '''# Managed by gpu_egress_guard_20261024.py
[Service]
IPAddressDeny=any
IPAddressAllow=localhost
'''
PROBE = r'''
import socket,errno
with socket.create_connection(('127.0.0.1',22),timeout=3):pass
try:
 with socket.create_connection(('195.209.221.75',22),timeout=3):pass
except OSError as error:
 if not isinstance(error,TimeoutError) and error.errno not in (errno.EPERM,errno.EACCES):raise
 print('EGRESS ENFORCEMENT PASS: loopback allowed; own public IP blocked ('+type(error).__name__+')',flush=True)
else:raise RuntimeError('Public-IP connection was allowed: cgroup IP filter not enforced')
'''


def main():
    if os.geteuid()!=0:raise RuntimeError('Run sudo python3 on GPU')
    os.umask(0o077)
    state=subprocess.check_output(['systemctl','show','--value','-p','ActiveState','tatar-inference.service']).strip()
    if state not in (b'inactive',b'failed'):raise RuntimeError('Inference service must remain stopped')
    # Only connect to this same VM:22, never to a third-party host.
    # Positive control separates an actual sandbox drop from an unreachable public endpoint.
    control = subprocess.run(['systemd-run','--quiet','--wait','--pipe','--collect',
       '--unit','tp-egress-control-'+str(time.time_ns()), '--property','User=ubuntu',
       '/usr/bin/python3','-c',
       "import socket; s=socket.create_connection(('195.209.221.75',22),timeout=3); s.close(); print('PUBLIC CONTROL CONNECT PASS',flush=True)"],
       stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    print(control.stdout.decode(errors='replace'),flush=True)
    if control.returncode or b'PUBLIC CONTROL CONNECT PASS' not in control.stdout:
        raise RuntimeError('Unfiltered positive control failed; cannot verify sandbox by timeout')
    result=subprocess.run(['systemd-run','--quiet','--wait','--pipe','--collect',
       '--unit','tp-egress-check-'+str(time.time_ns()),
       '--property','User=ubuntu','--property','IPAddressDeny=any','--property','IPAddressAllow=localhost',
       '/usr/bin/python3','-c',PROBE],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    print(result.stdout.decode(errors='replace'),flush=True)
    if result.returncode or b'EGRESS ENFORCEMENT PASS:' not in result.stdout:
        raise RuntimeError('Network sandbox not enforced; no inference service override installed')
    parent=Path('/etc/systemd/system/tatar-inference.service.d')
    if parent.is_symlink():raise RuntimeError('Unexpected service directory symlink')
    parent.mkdir(mode=0o755,exist_ok=True);parent.chmod(0o755)
    path=parent/'30-egress.conf'
    if path.is_symlink():raise RuntimeError('Unexpected egress override symlink')
    if path.exists():
        if path.read_text()!=CONFIG:raise RuntimeError('Unknown egress override; no overwrite')
    else:
        with path.open('x') as stream:stream.write(CONFIG)
        path.chmod(0o644)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    result=subprocess.check_output(['systemctl','show','tatar-inference.service','-p','IPAddressAllow','-p','IPAddressDeny','-p','ActiveState']).decode()
    print(result,flush=True)
    print('INFERENCE EGRESS GUARD INSTALLED; service remains stopped; no HTTP/inference started')


if __name__=='__main__':
    try:main()
    except Exception as exc:raise SystemExit('STOP: '+str(exc))
