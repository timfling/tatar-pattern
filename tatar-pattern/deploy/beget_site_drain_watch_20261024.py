#!/usr/bin/env python3
"""Verify first site job, then watch the second owner UI job and back up during drain.

Never creates/resubmits GPU jobs. Run in a persistent systemd unit on Beget.
"""
import hashlib
import http.cookiejar
import importlib.util
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import time
import urllib.request
import urllib.error

FIRST_PNG_SHA='72028553c0812db8feb294ccae659687b0fb0768c8279a17956301e9c064a4dc'
SQL="""SELECT coalesce(json_agg(json_build_object('id',g.id,'status',g.status,'guestId',g.guest_process_id,
'expiresAt',g.guest_expires_at,'resultPath',g.result_path,'params',g.params,'state',j.state,
'providerJobId',j.provider_job_id,'providerRequestId',j.provider_request_id) ORDER BY g.id),'[]'::json)
FROM ai_jobs j JOIN generations g ON g.id=j.generation_id"""


def require(ok,msg):
    if not ok:raise RuntimeError(msg)


def main():
    require(os.geteuid()==0,'Run on Beget as root')
    os.umask(0o077)
    sys.path.insert(0,'/srv/tatar-pattern/releases/guest-20261020-1/deploy')
    import ops,maintenance
    spec=importlib.util.spec_from_file_location('v2','/etc/tatar-pattern/staging-maintenance.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    values=ops.read_env(m.ENVFILE);dc=m.make_dc(values)
    def rows():return json.loads(ops.pg(dc,'psql','-At','-c',SQL))
    def used():return int(ops.pg(dc,'psql','-At','-c',"SELECT coalesce((SELECT used FROM guest_budget WHERE key='gpu-total'),0)").strip())
    first=rows();require(len(first)==1 and first[0]['id']==4 and first[0]['status']=='done' and
      first[0]['state']=='done' and bool(first[0]['providerJobId']) and used()==1,'Expected only first completed site job4/budgetused1')
    row=first[0];recipe=row['params']['recipe']
    qualification=json.loads(Path('/srv/tatar-pattern/incoming/qualification-current-20261024.json').read_text())
    require(row['providerJobId'] not in {p['jobId'] for p in qualification['profiles']},'Site job must be distinct from qualification jobs')
    require(row['params']['mode']=='ai' and recipe['base']['id']=='f10-wreath' and
            recipe['profile']['ornamentStyle']=='graphic','Unexpected first recipe')
    require(recipe['providerOutputSha256']==FIRST_PNG_SHA and recipe['outputSha256']['png']==FIRST_PNG_SHA,'Browser export/recipe SHA mismatch')
    for format in ('png','jpg'):
        path=m.DATA/'storage'/row['resultPath'];path=path.with_suffix('.'+format)
        require(path.is_file() and ops.digest(path)==recipe['outputSha256'][format],'Stored export SHA mismatch')
    context=ssl.create_default_context(cafile='/etc/tatar-pattern/staging-root-ca.crt')
    def opener(jar=None):
        handlers=[urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context)]
        if jar is not None:handlers.append(urllib.request.HTTPCookieProcessor(jar))
        return urllib.request.build_opener(*handlers)
    def call(client,path,method='GET'):
        req=urllib.request.Request('https://localhost:18080'+path,method=method,
             data=b'{}' if method=='POST' else None,headers={'Origin':'https://localhost:18080','Content-Type':'application/json'})
        try:response=client.open(req,timeout=8)
        except urllib.error.HTTPError as error:response=error
        with response:return response.status,response.read(1024*1024)
    require(call(opener(),'/api/guest/generations/4')[0]==401,'No-cookie ownership check failed')
    jar=http.cookiejar.CookieJar();other=opener(jar)
    session_code,_=call(other,'/api/guest/session','POST')
    require(session_code==200,'Other temporary guest session failed: HTTP'+str(session_code))
    for path in ('/api/guest/generations/4','/api/guest/generations/4/file?format=png','/api/guest/generations/4/file?format=jpg'):
        require(call(other,path)[0]==404,'Other-guest ownership check failed')
    report={'first':row,'firstPngMatchesOwnerDownload':True,'firstPngAndJpgStorageShaVerified':True,
            'ownership':{'noCookie':401,'otherGuestMetadataPngJpg':404},'baselineBudgetUsed':1}
    report_path=m.DATA/'checks/site-e2e-drain-20261024.json';m.atomic_json(report_path,report)
    print('FIRST SITE E2E VERIFIED: generation4; real providerJobId='+row['providerJobId']+'; PNG/JPG storage SHA; ownership401/404 PASS',flush=True)
    print('DRAIN WATCH ARMED: now create the second f10-wreath:graphic job in Firefox; no automatic submit',flush=True)
    deadline=time.monotonic()+240
    while True:
        current=rows();new=[r for r in current if r['id']!=4]
        require(len(new)<=1 and used()<=2,'Unexpected extra site job; no further submit allowed')
        if new and new[0]['providerJobId'] and new[0]['state']=='polling':
            second=new[0];break
        if new and new[0]['status'] in ('done','failed'):
            raise RuntimeError('Second job already finished before active watch; no new inference permitted')
        require(time.monotonic()<deadline,'Watch expired without second acknowledged job; no job created by watcher')
        time.sleep(.4)
    require(second['params']['ai']['baseId']=='f10-wreath' and second['params']['ai']['ornamentStyle']=='graphic','Unexpected second pair')
    report['secondBeforeDrain']=second;report['budgetUsedAtTrigger']=used();m.atomic_json(report_path,report)
    # Only now take the common maintenance lock. Timers remain scheduled.
    lock_deadline=time.monotonic()+45
    while True:
        try:lock=maintenance.lock(m.DATA,blocking=False);break
        except BlockingIOError:
            require(time.monotonic()<lock_deadline,'Maintenance lock busy before drain');time.sleep(.2)
    with lock:
        original_drain=m.drain
        def observed_drain(active_dc,info,root=m.DATA):
            cid=active_dc('ps','-q','ai-worker',capture=True).decode().strip()
            code="from app.ai_provider import configured_provider;import json;p=configured_provider();r=p._json('GET','/v1/jobs/"+second['providerJobId']+"',timeout=5);print(json.dumps({'jobId':r['jobId'],'status':r['status']}))"
            remote=json.loads(subprocess.check_output(['docker','exec',cid,'python','-c',code]))
            report['gpuImmediatelyBeforeSignal']=remote;report['signalAtEpoch']=time.time();m.atomic_json(report_path,report)
            print('DRAIN SIGNAL: generationId='+str(second['id'])+' providerJobId='+remote['jobId']+' GPUstatus='+remote['status'],flush=True)
            original_drain(active_dc,info,root)
            report['drainElapsedSeconds']=time.time()-report['signalAtEpoch'];report['drainExit0FreshMarkerConfirmed']=True
            report['workerAfterDrain']=m.identity(m.worker_info(active_dc));m.atomic_json(report_path,report)
        m.drain=observed_drain
        target=m.snapshot(dc,values,ops)
        after=rows();require(len(after)==2 and all(r['state']=='done' and r['status']=='done' for r in after),
                                 'Not both site jobs completed; preserve IDs/state, no resubmit')
        require(after[0]['providerJobId']!=after[1]['providerJobId'] and used()==2,'Site job accounting differs')
        for entry in after:
            for fmt in ('png','jpg'):
                path=(m.DATA/'storage'/entry['resultPath']).with_suffix('.'+fmt)
                require(ops.digest(path)==entry['params']['recipe']['outputSha256'][fmt],'Post-drain output SHA mismatch')
        m.health(dc,True)
        from datetime import datetime,timezone
        m.atomic_json(m.DATA/'backups/.local-backup-ok.json',{'completedAt':datetime.now(timezone.utc).isoformat(),'backup':str(target),'offsite':False})
        report.update(after=after,backup=str(target),budgetUsedAfter=2,uniqueSiteJobs=2,
                      activeGpuAtSignal=report['gpuImmediatelyBeforeSignal']['status'] in ('queued','running'),
                      pngJpgShaPreserved=True,tunnelAndDbPreserved=True,workerRemainsStopped=True)
        m.atomic_json(report_path,report)
        print('SITE2 + DRAIN + BACKUP PASS; activeGPUatSignal='+str(report['activeGpuAtSignal'])+
              '; exit0/freshDRAINED; both jobs done; budgetused2; PNG/JPG SHA preserved; worker stopped; tunnel/DB kept',flush=True)
        print('Evidence: '+str(report_path)+'; backup='+str(target),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:raise SystemExit('STOP: '+str(exc))
