from pathlib import Path
import ast,json,os,secrets,socket,subprocess,time,urllib.request,urllib.error
ai=Path(__file__).resolve().parents[1]
for source in ai.rglob('*.py'): ast.parse(source.read_text(),filename=str(source))
state=ai/'service/local-test';state.mkdir(exist_ok=True)
token=secrets.token_urlsafe(40)
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
env=dict(os.environ,TP_INFERENCE_TOKEN=token)
p=subprocess.Popen(['python3',str(ai/'service/server.py'),'--config',str(ai/'service/config.example.json'),'--state',str(state),'--port',str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
checks=[]
def call(method,path,body=None,auth=True):
 hdr={'Content-Type':'application/json'}
 if auth:hdr['Authorization']='Bearer '+token
 if method=='POST':hdr['Idempotency-Key']='f4d96e7c-d0bd-4ce7-8f0b-512ac94a2631'
 req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,headers=hdr,data=json.dumps(body).encode() if body else None,method=method)
 try:
  with urllib.request.urlopen(req,timeout=3) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
try:
 for i in range(30):
  try:
   status,result=call('GET','/v1/health');break
  except urllib.error.URLError:time.sleep(.1)
 assert status==503 and result['status']=='unavailable';checks.append({'test':'health_without_gpu','http':status})
 status,result=call('GET','/v1/health',auth=False);assert status==401;checks.append({'test':'authentication_required','http':status})
 body=dict(workflowVersion='tp-sdxl-fiber-v1',modelVersion='PENDING_APPROVED_ADAPTER_SHA',scenario='motif',prompt='blue flower',seed=20261008,width=1024,height=1024,steps=30,guidanceScale=5.0,loraScale=.6,templateId=None)
 status,result=call('POST','/v1/jobs',body);assert status==503 and result['error']['code']=='GPU_UNAVAILABLE';checks.append({'test':'no_fake_submit_without_gpu','http':status})
 body['scenario']='full-pattern';status,result=call('POST','/v1/jobs',body);assert status==422;checks.append({'test':'unsupported_scenario','http':status})
 status,result=call('GET','/v1/jobs/unknown');assert status==404;checks.append({'test':'unknown_job','http':status})
 (ai/'service/local-http-checks.json').write_text(json.dumps({'date':'2026-10-11','scope':'local negative HTTP; NOT GPU/cloud smoke','checks':checks,'gpu_generated_images':0,'external_requests':0,'cost_rub':0},indent=2)+'\n')
 print(json.dumps(checks))
finally:p.terminate();p.wait(timeout=5)
