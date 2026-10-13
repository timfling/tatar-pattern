"""Candidate own API; binds loopback for SSH tunnel. Never creates a Selectel account.

Persistent single-worker queue/idempotency; actual child renders or honest failure.
GPU preflight and cloud end-to-end remain unverified. No fake image generator.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse, hashlib, hmac, json, os, sqlite3, subprocess, sys, threading, time, uuid, signal

HERE=Path(__file__).resolve().parent
CFG={};STORE=HERE/'state';TOKEN='';READY=False;DB=None
def connect():
    db=sqlite3.connect(DB,timeout=30);db.row_factory=sqlite3.Row;return db
def file_for(j,suffix):return STORE/(j+suffix)
def worker():
    while True:
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("select * from jobs where status='queued' order by created limit 1").fetchone()
            if row:db.execute("update jobs set status='running' where id=?",(row['id'],))
        if not row:time.sleep(1);continue
        j=row['id'];status='failed';error='INFERENCE_FAILED';start=time.time()
        try:
            if time.time()-row['created']>900:raise TimeoutError('expired queue')
            with file_for(j,'.log').open('w') as log:
                p=subprocess.Popen([sys.executable,str(HERE/'render_one.py'),str(file_for(j,'.input.json')),str(file_for(j,'.png')),str(STORE/'config.json')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                try:p.wait(timeout=min(600,max(1,900-(time.time()-row['created']))))
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid,signal.SIGKILL);p.wait();raise
            if p.returncode==0:
                from PIL import Image
                im=Image.open(file_for(j,'.png'));im.load()
                assert im.size==(1024,1024) and file_for(j,'.png').stat().st_size<=20*1024**2
                status='done';error=None
        except (TimeoutError,subprocess.TimeoutExpired):error='INFERENCE_TIMEOUT'
        except Exception:error='INFERENCE_FAILED'
        with connect() as db:db.execute('update jobs set status=?,error=?,elapsed=?,finished=? where id=?',(status,error,time.time()-start,time.time(),j))

def maintenance():
    while True:
        with connect() as db:
            old=db.execute("select id,finished from jobs where status in ('done','failed') and finished < ?",(time.time()-24*3600,)).fetchall()
            for row in old:
                for suffix in ['.input.json','.png','.log','.metrics.json']:
                    file_for(row['id'],suffix).unlink(missing_ok=True)
            db.execute("delete from jobs where status in ('done','failed') and finished < ?",(time.time()-7*24*3600,))
        time.sleep(60)

def validate(r):
    required={'workflowVersion','modelVersion','scenario','prompt','seed','width','height','steps','guidanceScale','loraScale','templateId'}
    if set(r)!=required:return 'INVALID_PARAMETERS'
    if r['workflowVersion']!=CFG['workflow_version'] or r['modelVersion']!=CFG['adapter_sha256']:return 'VERSION_MISMATCH'
    if r['scenario'] not in ['motif','central_controlled']:return 'UNSUPPORTED_SCENARIO'
    if not isinstance(r['prompt'],str) or not 1<=len(r['prompt'])<=1200:return 'INVALID_PARAMETERS'
    if type(r['seed']) is not int or not 0<=r['seed']<=2147483647:return 'INVALID_PARAMETERS'
    if (r['width'],r['height'],r['steps'],r['guidanceScale'])!=(1024,1024,30,5.0):return 'INVALID_PARAMETERS'
    if r['loraScale'] not in [0.0,0.5,0.6,0.8]:return 'INVALID_PARAMETERS'
    if r['scenario']=='motif' and r['templateId'] is not None:return 'INVALID_PARAMETERS'
    if r['scenario']=='central_controlled' and r['templateId'] not in CFG.get('templates',{}):return 'INVALID_PARAMETERS'
    return None

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup();self.connection.settimeout(30)
    def log_message(self,*args):pass  # no prompt/token in web access logs
    def send_json(self,n,obj):
        b=json.dumps(obj).encode();self.send_response(n);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    def error(self,n,code):self.send_json(n,{'error':{'code':code,'message':code}})
    def authorized(self):
        if hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+TOKEN):return True
        self.error(401,'AUTH_REQUIRED');return False
    def do_GET(self):
        if not self.authorized():return
        if self.path=='/v1/health':
            with connect() as db:q=db.execute("select count(*) from jobs where status in ('queued','running')").fetchone()[0]
            return self.send_json(200 if READY else 503,dict(status='ready' if READY else 'unavailable',workflowVersion=CFG['workflow_version'],modelVersion=CFG['adapter_sha256'],queueDepth=q))
        bits=self.path.strip('/').split('/')
        if len(bits) not in [3,4] or bits[:2]!=['v1','jobs']:return self.error(404,'JOB_NOT_FOUND')
        with connect() as db:r=db.execute('select * from jobs where id=?',(bits[2],)).fetchone()
        if not r:return self.error(404,'JOB_NOT_FOUND')
        if len(bits)==4:
            if bits[3]!='image':return self.error(404,'JOB_NOT_FOUND')
            if r['status']!='done':return self.error(409,'RESULT_NOT_READY')
            p=file_for(r['id'],'.png')
            if not p.exists():return self.error(404,'RESULT_EXPIRED')
            b=p.read_bytes();self.send_response(200);self.send_header('Content-Type','image/png');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
        result=None;p=file_for(r['id'],'.png')
        if r['status']=='done' and p.exists():result=dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),mimeType='image/png',bytes=p.stat().st_size,width=1024,height=1024)
        self.send_json(200,dict(jobId=r['id'],status=r['status'],progress=None,error=None if not r['error'] else {'code':r['error'],'message':r['error']},result=result,elapsedSeconds=r['elapsed'],metadata=json.loads(r['metadata'] or '{}')))
    def do_POST(self):
        if not self.authorized():return
        if self.path!='/v1/jobs':return self.error(404,'JOB_NOT_FOUND')
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.error(400,'INVALID_JSON')
        try:n=int(self.headers.get('Content-Length','0'))
        except ValueError:return self.error(400,'INVALID_JSON')
        if n>1024**2:return self.error(413,'PAYLOAD_TOO_LARGE')
        try:r=json.loads(self.rfile.read(n));assert isinstance(r,dict)
        except Exception:return self.error(400,'INVALID_JSON')
        err=validate(r)
        if err:return self.error(409 if err=='VERSION_MISMATCH' else 422,err)
        key=self.headers.get('Idempotency-Key','')
        try:uuid.UUID(key)
        except ValueError:return self.error(422,'INVALID_PARAMETERS')
        payload=json.dumps(r,sort_keys=True,separators=(',',':'));digest=hashlib.sha256(payload.encode()).hexdigest()
        with connect() as db:
            db.execute('BEGIN IMMEDIATE');old=db.execute('select * from jobs where request_key=?',(key,)).fetchone()
            if old:
                if old['payload_sha']!=digest:return self.error(409,'IDEMPOTENCY_CONFLICT')
                return self.send_json(202,dict(jobId=old['id'],status=old['status'],workflowVersion=CFG['workflow_version'],modelVersion=CFG['adapter_sha256']))
            if not READY:return self.error(503,'GPU_UNAVAILABLE')
            if time.time()>=CFG.get('admission_deadline_epoch',0):return self.error(503,'BUDGET_EXHAUSTED')
            if db.execute("select count(*) from jobs where status in ('queued','running')").fetchone()[0]>=20:return self.error(429,'QUEUE_FULL')
            j=str(uuid.uuid4());file_for(j,'.input.json').write_text(payload)
            meta=dict(workflowVersion=CFG['workflow_version'],modelVersion=CFG['adapter_sha256'],baseRepo=CFG['base_repo'],baseRevision=CFG['base_revision'],seed=r['seed'],scenario=r['scenario'],width=1024,height=1024,steps=30,guidanceScale=5.0,loraScale=r['loraScale'],scheduler='EulerDiscreteScheduler',templateId=r['templateId'])
            if r['scenario']=='central_controlled':
                tp=Path(CFG['templates'][r['templateId']]);meta.update(controlRepo=CFG['control_repo'],controlRevision=CFG['control_revision'],controlImageSha256=hashlib.sha256(tp.read_bytes()).hexdigest(),preprocessing='alpha silhouette binary128 then Canny100/200',controlScale=0.5,controlStart=0.0,controlEnd=1.0)
            db.execute('insert into jobs(id,request_key,payload_sha,status,created,metadata) values(?,?,?,?,?,?)',(j,key,digest,'queued',time.time(),json.dumps(meta)))
        self.send_json(202,dict(jobId=j,status='queued',workflowVersion=CFG['workflow_version'],modelVersion=CFG['adapter_sha256']))

def main():
    global CFG,STORE,TOKEN,READY,DB
    ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path,required=True);ap.add_argument('--state',type=Path,default=STORE);ap.add_argument('--port',type=int,default=8765);a=ap.parse_args()
    TOKEN=os.environ.get('TP_INFERENCE_TOKEN','')
    if len(TOKEN)<32:raise SystemExit('Set a protected random TP_INFERENCE_TOKEN of at least32 characters')
    CFG=json.loads(a.config.read_text());STORE=a.state.resolve();STORE.mkdir(parents=True,exist_ok=True);DB=STORE/'jobs.sqlite'
    os.chmod(STORE,0o700);(STORE/'config.json').write_text(json.dumps(CFG))
    with connect() as db:
        db.execute('create table if not exists jobs(id text primary key,request_key text unique,payload_sha text,status text,created real,finished real,error text,elapsed real)')
        if 'metadata' not in {row[1] for row in db.execute('pragma table_info(jobs)')}:
            db.execute('alter table jobs add column metadata text')
        db.execute("update jobs set status='failed',error='INFERENCE_INTERRUPTED',finished=? where status='running'",(time.time(),))
    try:
        import torch
        adapter=Path(CFG['adapter_path']);smoke=json.loads(Path(CFG['gpu_smoke_path']).read_text())
        READY=torch.cuda.is_available() and adapter.exists() and hashlib.sha256(adapter.read_bytes()).hexdigest()==CFG['adapter_sha256'] and smoke.get('adapter_sha256')==CFG['adapter_sha256'] and smoke.get('passed') is True
    except Exception:READY=False
    if READY:threading.Thread(target=worker,daemon=True).start()
    threading.Thread(target=maintenance,daemon=True).start()
    ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()

if __name__=='__main__':main()
