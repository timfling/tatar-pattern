#!/usr/bin/env python3
"""One explicit paid qualification batch, exactly25 approved pairs, no retry."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import urllib.request
import urllib.error

ROOT=Path('/srv/tatar-lora-kit')
APPROVED=Path('/tmp/qualification-approved-20261024.json')
APPROVED_SHA='a1ca9e2b6ba30a90c99005161aaf6aeabf91cde5f2e6a1658517334552d10dfc'
OUTPUT=ROOT/'service/proof-window-20261024'
MARKER=ROOT/'service/qualification-launch-20261024.json'
BOOT='99fa5828-85de-4c5c-9084-5bb087dbabdc'
DIGEST='51615fddf6fa09d8ad2155f432a3c79bccef9f810e996f4167000e5abe617771'
DEADLINE=datetime(2026,10,24,13,10,tzinfo=timezone.utc).timestamp()


def require(ok,msg):
    if not ok:raise RuntimeError(msg)


def jobs():
    with sqlite3.connect((ROOT/'service/state/jobs.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        return dict(db.execute('select id,status from jobs').fetchall())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if not args.execute:
        print('PLAN ONLY: exactly25 new GPU jobs; use --execute only in approved window')
        return
    os.umask(0o077)
    require(os.getuid()==1000,'Run as existing GPU ubuntu user using its venv Python')
    require(time.time()<DEADLINE-20*60,'Less than20min admission left; do not start batch')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT,'Boot changed')
    require(hashlib.sha256(APPROVED.read_bytes()).hexdigest()==APPROVED_SHA,'Approved pair list changed')
    doc=json.loads(APPROVED.read_text());pairs=doc['pairs']
    require(len(pairs)==25 and len(set(pairs))==25 and doc['maxNewJobs']==25 and doc['paidRetries']==0,
            'Expected exact approved batch25/no retry')
    require(not OUTPUT.exists() and not MARKER.exists(),'Qualification already launched; inspect evidence, NEVER rerun batch')
    baseline=jobs();require(all(s not in ('queued','running') for s in baseline.values()),'Existing unfinished GPU jobs; no new submit')
    token_file=ROOT/'service/token'
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request=urllib.request.Request('http://127.0.0.1:8765/v1/health',headers={'Authorization':'Bearer '+token_file.read_text().strip()})
    try:r=opener.open(request,timeout=8)
    except urllib.error.HTTPError as error:r=error
    with r:code=r.status;h=json.load(r)
    require(code==503 and h.get('qualificationMode') is True and h.get('bootId')==BOOT and
            h.get('deploymentDigest')==DIGEST and h.get('draining') is False and h.get('queueDepth')==0,
            'Current qualification health required')
    with MARKER.open('x') as stream:
        json.dump({'startedAt':datetime.now(timezone.utc).isoformat(),'bootId':BOOT,'pairs':pairs,
                   'baselineJobIds':sorted(baseline),'maxNewJobs':25,'paidRetries':0},stream,indent=2)
        stream.flush();os.fsync(stream.fileno())
    command=[sys.executable,'-B',str(ROOT/'service/qualify.py'),'--owner-run','--output',str(OUTPUT)]
    for pair in pairs:command+=['--pair',pair]
    env=os.environ.copy();env.pop('TP_INFERENCE_TOKEN',None);env['TP_INFERENCE_TOKEN_FILE']=str(token_file)
    process=subprocess.Popen(command,env=env,cwd=ROOT)
    seen=-1
    while process.poll() is None:
        path=OUTPUT/'http-evidence.json'
        try:
            evidence=json.loads(path.read_text());completed=len(evidence.get('completedProfiles',[]))
            if completed!=seen:
                active=evidence.get('activeSubmission',{})
                print('QUALIFICATION PROGRESS: '+str(completed)+'/25 completed; active='+str(active.get('status','none')),
                      flush=True);seen=completed
        except (FileNotFoundError,json.JSONDecodeError):pass
        time.sleep(3)
    require(process.returncode==0,'Qualification stopped; preserve activeSubmission/jobId; no retry/resubmit')
    evidence=json.loads((OUTPUT/'http-evidence.json').read_text());completed=evidence['completedProfiles']
    require(evidence['status']=='HTTP_TECHNICAL_PASS' and evidence['bootId']==BOOT and
            evidence['deploymentDigest']==DIGEST and len(completed)==25 and
            {p['baseId']+':'+p['ornamentStyle'] for p in completed}==set(pairs),'Incomplete/changed batch evidence')
    after=jobs();new=set(after)-set(baseline)
    require(new=={p['jobId'] for p in completed} and len(new)==25 and all(after[j]=='done' for j in new),
            'Unexpected GPU job accounting; no additional jobs allowed')
    (OUTPUT/'batch-accounting.json').write_text(json.dumps({'newGpuJobs':25,'done':25,'siteJobsRemaining':2,
        'bootId':BOOT,'qualificationEvidenceSha256':hashlib.sha256((OUTPUT/'http-evidence.json').read_bytes()).hexdigest()},indent=2)+'\n')
    print('FRESH QUALIFICATION TECHNICAL PASS:25 new jobs done;25 PNG; site jobs remaining2',flush=True)
    print('Evidence: '+str(OUTPUT)+'; owner PNG acceptance, normal mode and worker proof still pending',flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:raise SystemExit('STOP: '+str(exc))
