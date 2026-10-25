#!/usr/bin/env python3
"""Build real deployed-worker proof from today's25 accepted GPU jobs; submit0."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import UUID


def main():
    if os.geteuid()!=0:raise RuntimeError('Run on Beget as root')
    source=Path('/srv/tatar-pattern/incoming/qualification-current-20261024.json')
    data=json.loads(source.read_text())
    if data.get('ownerAccepted') is not True or data.get('bootId')!='99fa5828-85de-4c5c-9084-5bb087dbabdc':
        raise RuntimeError('Current accepted qualification job list required')
    jobs=[str(UUID(p['jobId'])) for p in data['profiles']]
    if len(jobs)!=25 or len(set(jobs))!=25:raise RuntimeError('Exactly25 fresh unique IDs required')
    sys.path.insert(0,'/srv/tatar-pattern/releases/guest-20261020-1/deploy')
    import ops,maintenance
    spec=importlib.util.spec_from_file_location('v2','/etc/tatar-pattern/staging-maintenance.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    deadline=time.monotonic()+45
    while True:
        try:lock=maintenance.lock(m.DATA,blocking=False);break
        except BlockingIOError:
            if time.monotonic()>deadline:raise RuntimeError('Maintenance lock busy') from None
            time.sleep(1)
    with lock:
        values=ops.read_env(m.ENVFILE)
        if values.get('AI_API_CONFIG')!='true':raise RuntimeError('Real shared adapter required')
        dc=m.make_dc(values);m.validate_config(json.loads(dc('config','--format','json',capture=True)),True)
        command=['python','-m','scripts.ai_gpu_probe','--owner-run','--worker-namespace']
        for job in jobs:command+=['--job-id',job]
        # Probe modules perform health/job/image/SHA/PNG/metadata/health, no POST.
        cid=dc('ps','-q','ai-worker',capture=True).decode().strip()
        if not cid:raise RuntimeError('Real worker is not running')
        for invocation in (command,['python','-m','scripts.gpu_proof_status']):
            result=subprocess.run(['docker','exec',cid,*invocation],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            if result.stdout:print(result.stdout.decode(errors='replace'),flush=True)
            if result.stderr:print(result.stderr.decode(errors='replace')[-3000:],file=sys.stderr,flush=True)
            if result.returncode:raise RuntimeError('Worker GET check exited'+str(result.returncode)+'; no inference/retry submitted')
        proof_path=m.DATA/'storage/ai-gpu-worker-proof.json'
        proof=json.loads(proof_path.read_text())
        if proof.get('bootId')!=data['bootId'] or proof.get('deploymentDigest')!=data['deploymentDigest']:
            raise RuntimeError('Saved proof identity mismatch')
        m.health(dc,True)
        print('FRESH REAL WORKER PROOF PASS;25 current qualification jobs; submit0; site still AI=false/budget0')


if __name__=='__main__':
    try:main()
    except Exception as exc:raise SystemExit('STOP: '+str(exc))
