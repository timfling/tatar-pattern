"""Loopback img2img API candidate. Owner deploys/runs it; no cloud provisioning."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import contextmanager
from pathlib import Path
import argparse
import fcntl
import hmac
import importlib.metadata
import json
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid

from workflow import CONTRACT, MODEL, WORKFLOW, VERSIONS, canonical, deployment, digest, registry, resolved, sha, validate

HERE = Path(__file__).resolve().parent
CFG = {}
STORE = HERE / 'state'
TOKEN = ''
READY = False
PREFLIGHT = False
QUALIFICATION = False
IDENTITY = {}
QUALIFIED_PAIRS = set()
QUALIFIED_JOB_IDS = set()
BOOT_ID = None
DB = None
DRAIN = threading.Event()
DRAIN_AT = None
STOP = threading.Event()


@contextmanager
def connect():
    db = sqlite3.connect(DB, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def file_for(job, suffix):
    return STORE / (job + suffix)


def depth():
    with connect() as db:
        return db.execute("select count(*) from jobs where status in ('queued','running')").fetchone()[0]


def current_identity():
    # No model load/hash of multi-GB weights in a health request. Weights/assets are
    # checked at boot and in each renderer; manifests and code must remain immutable.
    return bool(IDENTITY) and deployment(CFG, verify_files=False) == IDENTITY


def available():
    try:
        return READY and not DRAIN.is_set() and time.time() < CFG.get('admission_deadline_epoch', 0) and current_identity()
    except Exception:
        return False


def fail(job, error):
    with connect() as db:
        db.execute("update jobs set status='failed',error=?,finished=? where id=?", (error, time.time(), job))


def worker():
    while not STOP.is_set():
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("select * from jobs where status='queued' order by created limit 1").fetchone()
            if row:
                db.execute("update jobs set status='running' where id=?", (row['id'],))
        if row is None:
            STOP.wait(.5)
            continue
        job = row['id']
        start = time.time()
        try:
            meta = json.loads(row['metadata'] or '{}')
            pair = (meta.get('baseId'), meta.get('ornamentStyle'), meta.get('profileDigest'))
            if meta.get('deploymentDigest') != IDENTITY['deploymentDigest'] or not current_identity() or (not QUALIFICATION and pair not in QUALIFIED_PAIRS):
                fail(job, 'VERSION_MISMATCH')
                continue
            deadline = min(start + 600, row['created'] + 900)
            if time.time() >= deadline:
                fail(job, 'INFERENCE_TIMEOUT')
                continue
            with file_for(job, '.log').open('w') as log:
                process = subprocess.Popen([sys.executable, str(HERE / 'render_one.py'),
                                            str(file_for(job, '.input.json')), str(file_for(job, '.png')),
                                            str(STORE / 'config.json')], stdout=log, stderr=subprocess.STDOUT,
                                           start_new_session=True)
                try:
                    while process.poll() is None:
                        if time.time() >= deadline or (DRAIN_AT is not None and time.time() >= DRAIN_AT + 910):
                            raise TimeoutError()
                        STOP.wait(.25)
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            if process.returncode != 0:
                raise RuntimeError('Render failed')
            from PIL import Image
            path = file_for(job, '.png')
            with Image.open(path) as im:
                im.load()
                if im.format != 'PNG' or im.size != (1024, 1024) or im.mode != 'RGB' or path.stat().st_size > 20*1024**2:
                    raise ValueError('Invalid output')
            metrics = json.loads(file_for(job, '.metrics.json').read_text())
            if metrics['deployment'] != IDENTITY or metrics['metadata'] != {k: v for k, v in meta.items() if k != 'deploymentDigest'} or metrics['outputSha256'] != sha(path):
                raise ValueError('Output identity mismatch')
            with connect() as db:
                db.execute("update jobs set status='done',error=null,elapsed=?,finished=? where id=?",
                           (time.time()-start, time.time(), job))
        except TimeoutError:
            fail(job, 'INFERENCE_TIMEOUT')
        except Exception:
            fail(job, 'INFERENCE_FAILED')


def maintenance():
    while not STOP.is_set():
        with connect() as db:
            rows = db.execute("select id from jobs where status in ('done','failed') and finished < ?", (time.time()-86400,)).fetchall()
            for row in rows:
                # Keep the real accepted qualification PNGs for daily worker HTTP
                # re-probes. No generated acceptance or boot-id rebinding.
                if row['id'] in QUALIFIED_JOB_IDS:
                    continue
                for suffix in ('.input.json', '.png', '.part', '.log', '.metrics.json'):
                    file_for(row['id'], suffix).unlink(missing_ok=True)
            expired = db.execute("select id from jobs where status in ('done','failed') and finished < ?", (time.time()-7*86400,)).fetchall()
            for row in expired:
                if row['id'] not in QUALIFIED_JOB_IDS:
                    db.execute('delete from jobs where id=?', (row['id'],))
        STOP.wait(60)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, *args):
        pass

    def send_json(self, status, obj):
        data = canonical(obj).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def error(self, status, code):
        self.send_json(status, {'error': {'code': code, 'message': code}})

    def authorized(self):
        if hmac.compare_digest(self.headers.get('Authorization', '').encode(), ('Bearer '+TOKEN).encode()):
            return True
        self.error(401, 'AUTH_REQUIRED')
        return False

    def acknowledgement(self, row):
        meta = json.loads(row['metadata'] or '{}')
        self.send_json(202, dict(jobId=row['id'], status=row['status'],
                                workflowVersion=meta.get('workflowVersion'), modelVersion=meta.get('modelVersion')))

    def do_GET(self):
        if not self.authorized():
            return
        if self.path == '/v1/health':
            ready = available()
            try:
                index, _, profiles = registry(CFG)
                supported = [dict(baseId=p['baseId'], baseSha256=p['baseSha256'], ornamentStyle=p['ornamentStyle'],
                                  profileVersion=p['version'], promptVersion=p['promptVersion'], profileDigest=digest(p),
                                  qualified=(p['baseId'], p['ornamentStyle'], digest(p)) in QUALIFIED_PAIRS)
                             for p in profiles.values()]
                catalog = index['catalogVersion']
            except Exception:
                supported, catalog = [], None
            return self.send_json(200 if ready else 503, dict(status='ready' if ready else 'unavailable',
                contractVersion=CONTRACT, workflowVersion=WORKFLOW, modelVersion=MODEL, queueDepth=depth(),
                catalogVersion=catalog, deploymentDigest=IDENTITY.get('deploymentDigest'),
                qualificationMode=QUALIFICATION, bootId=BOOT_ID, draining=DRAIN.is_set(), profiles=supported))
        bits = self.path.strip('/').split('/')
        if len(bits) not in (3, 4) or bits[:2] != ['v1', 'jobs']:
            return self.error(404, 'JOB_NOT_FOUND')
        with connect() as db:
            row = db.execute('select * from jobs where id=?', (bits[2],)).fetchone()
        if row is None:
            return self.error(404, 'JOB_NOT_FOUND')
        path = file_for(row['id'], '.png')
        if len(bits) == 4:
            if bits[3] != 'image':
                return self.error(404, 'JOB_NOT_FOUND')
            if row['status'] != 'done':
                return self.error(409, 'RESULT_NOT_READY')
            try:
                data = path.read_bytes()
            except FileNotFoundError:
                return self.error(404, 'RESULT_EXPIRED')
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        result = None
        try:
            if row['status'] == 'done':
                result = dict(sha256=sha(path), mimeType='image/png', bytes=path.stat().st_size, width=1024, height=1024)
        except FileNotFoundError:
            pass
        self.send_json(200, dict(jobId=row['id'], status=row['status'], progress=None,
            error=None if row['error'] is None else dict(code=row['error'], message=row['error']),
            result=result, elapsedSeconds=row['elapsed'], metadata=json.loads(row['metadata'] or '{}')))

    def do_POST(self):
        if not self.authorized():
            return
        if self.path != '/v1/jobs':
            return self.error(404, 'JOB_NOT_FOUND')
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json' or self.headers.get('Transfer-Encoding'):
            return self.error(400, 'INVALID_JSON')
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return self.error(400, 'INVALID_JSON')
        if length > 16384:
            return self.error(413, 'PAYLOAD_TOO_LARGE')
        if length <= 0:
            return self.error(400, 'INVALID_JSON')
        try:
            request = json.loads(self.rfile.read(length))
            if not isinstance(request, dict):
                raise ValueError()
        except Exception:
            return self.error(400, 'INVALID_JSON')
        try:
            key = str(uuid.UUID(self.headers.get('Idempotency-Key', '')))
        except ValueError:
            return self.error(422, 'INVALID_PARAMETERS')
        payload = canonical(request)
        payload_sha = digest(request)
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('select * from jobs where request_key=?', (key,)).fetchone()
            if old is not None:
                if old['payload_sha'] != payload_sha:
                    return self.error(409, 'IDEMPOTENCY_CONFLICT')
                return self.acknowledgement(old)
            try:
                error = validate(request, CFG)
            except Exception:
                return self.error(503, 'REGISTRY_UNAVAILABLE')
            if error:
                return self.error(409 if error == 'VERSION_MISMATCH' else 422, error)
            if DRAIN.is_set():
                return self.error(503, 'SERVICE_DRAINING')
            if time.time() >= CFG.get('admission_deadline_epoch', 0):
                return self.error(503, 'BUDGET_EXHAUSTED')
            try:
                profile = resolved(request, CFG)
                qualified = (request['baseId'], request['ornamentStyle'], profile['profileDigest']) in QUALIFIED_PAIRS
                admit = ((READY and qualified) or (QUALIFICATION and PREFLIGHT)) and current_identity()
            except Exception:
                admit = False
            if not admit:
                return self.error(503, 'GPU_UNAVAILABLE')
            if db.execute("select count(*) from jobs where status in ('queued','running')").fetchone()[0] >= 20:
                return self.error(429, 'QUEUE_FULL')
            job = str(uuid.uuid4())
            temporary = file_for(job, '.input.part')
            temporary.write_text(payload)
            temporary.replace(file_for(job, '.input.json'))
            meta = resolved(request, CFG) | {'deploymentDigest': IDENTITY['deploymentDigest']}
            db.execute('insert into jobs(id,request_key,payload_sha,status,created,metadata) values(?,?,?,?,?,?)',
                       (job, key, payload_sha, 'queued', time.time(), canonical(meta)))
        self.send_json(202, dict(jobId=job, status='queued', workflowVersion=WORKFLOW, modelVersion=MODEL))


def secret():
    value, filename = os.environ.get('TP_INFERENCE_TOKEN'), os.environ.get('TP_INFERENCE_TOKEN_FILE')
    if bool(value) == bool(filename):
        raise SystemExit('Set exactly one TP_INFERENCE_TOKEN or TP_INFERENCE_TOKEN_FILE')
    token = Path(filename).read_text().strip() if filename else value
    if len(token) < 32 or not token.isascii() or any(c.isspace() for c in token):
        raise SystemExit('Token must be ASCII without whitespace, at least 32 characters')
    return token


def accepted_pairs(record, identity, boot_id, profiles, preflight):
    """boot_id is the Linux boot, not a Python process start. Fail closed."""
    if not (preflight and boot_id and record.get('passed') is True
            and record.get('httpVerified') is True
            and record.get('deploymentDigest') == identity.get('deploymentDigest')
            and record.get('bootId') == boot_id):
        return set()
    pairs = {(p['baseId'], p['ornamentStyle'], p['profileDigest'])
             for p in record.get('completedProfiles', [])}
    known = {(p['baseId'], p['ornamentStyle'], digest(p)) for p in profiles.values()}
    return pairs if pairs.issubset(known) else set()


def main():
    global CFG, STORE, TOKEN, READY, PREFLIGHT, QUALIFICATION, IDENTITY, DB, DRAIN_AT, QUALIFIED_PAIRS, QUALIFIED_JOB_IDS, BOOT_ID
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--state', type=Path, default=STORE)
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--qualification-mode', action='store_true', help='Owner-only HTTP smoke; health stays 503')
    args = ap.parse_args()
    TOKEN = secret()
    CFG = json.loads(args.config.read_text())
    STORE = args.state.resolve()
    STORE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STORE, 0o700)
    lock = (STORE / 'service.lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('This state directory already has a service process')
    os.umask(0o077)
    DB = STORE / 'jobs.sqlite'
    (STORE / 'config.json').write_text(canonical(CFG))
    QUALIFICATION = args.qualification_mode
    with connect() as db:
        db.execute('create table if not exists jobs(id text primary key,request_key text unique,payload_sha text,status text,created real,finished real,error text,elapsed real,metadata text)')
        if 'metadata' not in {row[1] for row in db.execute('pragma table_info(jobs)')}:
            db.execute('alter table jobs add column metadata text')
        db.execute("update jobs set status='failed',error='INFERENCE_INTERRUPTED',finished=? where status='running'", (time.time(),))
    try:
        IDENTITY = deployment(CFG)
        BOOT_ID = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        import torch
        PREFLIGHT = (sys.version_info[:2] in ((3, 11), (3, 12)) and torch.cuda.is_available()
                     and torch.version.cuda == '12.8' and torch.cuda.device_count() == 1
                     and all(importlib.metadata.version(n).split('+')[0] == v for n, v in VERSIONS.items()))
        record = json.loads(Path(CFG['gpu_smoke_path']).read_text())
        _, _, profiles = registry(CFG)
        QUALIFIED_PAIRS = accepted_pairs(record, IDENTITY, BOOT_ID, profiles, PREFLIGHT)
        if QUALIFIED_PAIRS:
            QUALIFIED_JOB_IDS = {str(uuid.UUID(p['jobId'])) for p in record['completedProfiles']}
        READY = not QUALIFICATION and bool(QUALIFIED_PAIRS)
    except Exception as error:
        READY = False
        QUALIFIED_PAIRS = set()
        QUALIFIED_JOB_IDS = set()
        print('Readiness preflight/record unavailable: ' + str(error), file=sys.stderr, flush=True)
    if PREFLIGHT and (READY or QUALIFICATION):
        threading.Thread(target=worker, daemon=True).start()
    else:
        with connect() as db:
            db.execute("update jobs set status='failed',error='GPU_UNAVAILABLE',finished=? where status='queued'", (time.time(),))
    threading.Thread(target=maintenance, daemon=True).start()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.daemon_threads = True

    def drain(signum, frame):
        global DRAIN_AT
        if not DRAIN.is_set():
            DRAIN_AT = time.time()
            DRAIN.set()

    signal.signal(signal.SIGTERM, drain)
    signal.signal(signal.SIGINT, drain)
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    serving.start()
    while not DRAIN.wait(.5):
        pass
    while depth() and time.time() < DRAIN_AT + 915:
        time.sleep(.5)
    STOP.set()
    with connect() as db:
        db.execute("update jobs set status='failed',error='INFERENCE_INTERRUPTED',finished=? where status in ('queued','running')", (time.time(),))
    server.shutdown()
    server.server_close()


if __name__ == '__main__':
    main()
