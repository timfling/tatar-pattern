#!/usr/bin/env python3
"""Owner-run HTTPS staging check: expire only a newly created test guest.

Uses the installed cleanup timer, never invokes cleanup/reset itself. Cookies stay
in memory. This accelerates a deadline; it is not a 24-hour wall-clock test.
"""
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from uuid import uuid4

RELEASE = Path('/srv/tatar-pattern/releases/guest-20261020-1')
DATA = Path('/srv/tatar-pattern/staging-data')
ENVFILE = Path('/etc/tatar-pattern/staging.env')

# This code runs in the existing backend container. No cookie or password is
# passed through argv or printed. SQL writes target one freshly made guest only.
DB_CODE = r'''
import hashlib,json,sys
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from app.config import Settings
from app.catalog import safe_path
s=Settings.from_env();a=json.load(sys.stdin)
def require(ok,message):
    if not ok:raise RuntimeError(message)
def files(relative):
    p=Path(relative)
    return [str(p),str(p.with_suffix('.jpg')),str(p.with_name(p.stem+'.module.png')),str(p.with_suffix('.tmp'))]
def hashes(paths):
    return {p:hashlib.sha256(safe_path(s.storage_root,p).read_bytes()).hexdigest()
            for p in paths if safe_path(s.storage_root,p).is_file()}
with psycopg.connect(s.database_url,row_factory=dict_row,connect_timeout=5) as c:
    c.execute('SET statement_timeout=10000')
    if a['action']=='baseline':
        rows=c.execute("SELECT id,result_path FROM generations WHERE guest_process_id IS NOT NULL AND status='done' AND result_path IS NOT NULL AND guest_expires_at>clock_timestamp()+interval '10 minutes'").fetchall()
        print(json.dumps({str(r['id']):hashes(files(r['result_path'])) for r in rows}))
    elif a['action']=='inspect':
        r=c.execute('SELECT g.*,p.token_hash FROM generations g JOIN guest_processes p ON p.id=g.guest_process_id WHERE g.id=%s AND g.guest_request_id=%s',(a['gid'],a['requestId'])).fetchone()
        require(r is not None,'New test generation not found')
        require(r['token_hash']==a['tokenHash'],'Test guest ownership mismatch')
        require(r['status']=='done' and r['user_id'] is None,'Unexpected test generation')
        require(not c.execute('SELECT 1 FROM ai_jobs WHERE generation_id=%s',(a['gid'],)).fetchone(),'Unexpected AI job')
        paths=files(r['result_path'])
        require(all(p.startswith('guest-results/') for p in paths),'Path outside guest zone')
        h=hashes(paths);require(len(h)>=2,'Test result files missing')
        print(json.dumps(dict(guestId=str(r['guest_process_id']),paths=paths,hashes=h)))
    elif a['action']=='expire':
        c.execute('SELECT pg_advisory_xact_lock(107198013)')
        p=c.execute('SELECT * FROM guest_processes WHERE id=%s FOR UPDATE',(a['guestId'],)).fetchone()
        require(p is not None and p['token_hash']==a['tokenHash'],'Guest ownership mismatch')
        rows=c.execute('SELECT * FROM generations WHERE guest_process_id=%s FOR UPDATE',(a['guestId'],)).fetchall()
        require(len(rows)==1 and str(rows[0]['id'])==str(a['gid']) and str(rows[0]['guest_request_id'])==a['requestId'],'Refusing to expire a guest with other work')
        require(not c.execute('SELECT 1 FROM ai_jobs WHERE generation_id=%s',(a['gid'],)).fetchone(),'AI job appeared')
        c.execute("UPDATE generations SET guest_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s AND guest_process_id=%s",(a['gid'],a['guestId']))
        c.execute("UPDATE guest_processes SET created_at=clock_timestamp()-interval '1 hour',expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",(a['guestId'],))
        c.commit();print('{}')
    elif a['action']=='deleted':
        generation=bool(c.execute('SELECT 1 FROM generations WHERE id=%s',(a['gid'],)).fetchone())
        process=bool(c.execute('SELECT 1 FROM guest_processes WHERE id=%s',(a['guestId'],)).fetchone())
        remaining=[p for p in a['paths'] if safe_path(s.storage_root,p).exists()]
        pending=c.execute("SELECT count(*) n FROM storage_deletions WHERE path=ANY(%s) AND state='pending'",(a['paths'],)).fetchone()['n']
        print(json.dumps(dict(deleted=not generation and not process and not remaining and pending==0)))
    elif a['action']=='preserved':
        for gid,expected in a['baseline'].items():
            require(c.execute('SELECT 1 FROM generations WHERE id=%s',(gid,)).fetchone(),'Existing work missing')
            require(hashes(expected)==expected,'Existing file changed or missing')
        print(json.dumps(dict(preserved=len(a['baseline']))))
'''


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def main():
    require(os.geteuid() == 0, 'Run in the VPS root session')
    os.umask(0o077)
    sys.path.insert(0, str(RELEASE / 'deploy'))
    import ops
    import maintenance
    values = ops.read_env(ENVFILE)
    require(values['COMPOSE_PROJECT_NAME'] == 'tp-staging-20261023', 'Wrong project')
    require(values['DATA_ROOT'] == str(DATA), 'Wrong data root')
    require(values['RELEASE'] == RELEASE.name, 'Wrong release')
    require(values.get('STAGING_MODE') == 'true' and values.get('AI_API_CONFIG') == 'false', 'Staging with AI disabled required')
    env = os.environ.copy()
    env.update(values)
    dc = ['docker', 'compose', '--env-file', str(ENVFILE), '-p', values['COMPOSE_PROJECT_NAME'],
          '-f', str(RELEASE / 'deploy/compose.yml'), '-f', str(RELEASE / 'deploy/compose.staging.yml'),
          '-f', '/etc/tatar-pattern/staging-https.yml', '--profile', 'public']

    def run(parts, data=None):
        return subprocess.check_output(parts, input=data, env=env, cwd=RELEASE, timeout=45)

    def db(action, **parts):
        return json.loads(run(dc + ['exec', '-T', 'backend', 'python', '-c', DB_CODE],
                              json.dumps(dict(action=action, **parts)).encode()))

    cookies = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(cookies),
        urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile='/etc/tatar-pattern/staging-root-ca.crt')))

    def request_http(path, body=None, expected=200):
        request = urllib.request.Request('https://localhost:18080' + path,
                    data=None if body is None else json.dumps(body).encode(),
                    headers={} if body is None else {'Content-Type': 'application/json'})
        try:
            with opener.open(request, timeout=40) as response:
                code, content = response.status, response.read()
        except urllib.error.HTTPError as exc:
            code, content = exc.code, exc.read()
        require(code == expected, f'HTTP check failed: expected {expected}, received {code}')
        return content

    for name in ('cleanup', 'retention', 'backup'):
        run(['systemctl', 'is-active', '--quiet', f'tatar-staging-{name}.timer'])
    require(set(run(dc + ['ps', '--services', '--status', 'running']).decode().split()) == {'db', 'backend', 'frontend', 'proxy'}, 'Unexpected services')
    require(json.loads(request_http('/api/health')).get('ok') is True, 'Health failed')
    require(json.loads(request_http('/api/capabilities')).get('realUniqueElements') == 110, 'Catalog mismatch')

    # Hold the shared lock during setup only; release it for the real timer.
    with maintenance.lock(str(DATA)):
        baseline = db('baseline')
        request_id = str(uuid4())
        body = json.loads((RELEASE / 'backend/app/ai-assets/f10-wreath.recipe.json').read_text())['request']
        body.update(mode='flat', requestId=request_id)
        expires = json.loads(request_http('/api/guest/session', {}))['expiresAt']
        cookie = next(c for c in cookies if c.name == 'tp_guest')
        require(cookie.secure and len(cookie.value) == 43, 'Secure guest cookie missing')
        token_hash = hashlib.sha256(cookie.value.encode()).hexdigest()
        g = json.loads(request_http('/api/guest/generations', body, expected=201))['generation']
        gid = str(g['id'])
        require(g['status'] == 'done' and g['expiresAt'] == expires, 'Unexpected result or expiry')
        info = db('inspect', gid=gid, requestId=request_id, tokenHash=token_hash)
        for fmt in ('png', 'jpg'):
            content = request_http(f'/api/guest/generations/{gid}/file?format={fmt}')
            require(hashlib.sha256(content).hexdigest() == g['recipe']['outputSha256'][fmt], 'Export SHA mismatch')
        require(json.loads(request_http('/api/guest/session', {}))['expiresAt'] == expires, 'Session deadline extended')
        db('expire', gid=gid, guestId=info['guestId'], requestId=request_id, tokenHash=token_hash)
        request_http(f'/api/guest/generations/{gid}', expected=401)
        for fmt in ('png', 'jpg'):
            request_http(f'/api/guest/generations/{gid}/file?format={fmt}', expected=401)
        print('TEST GUEST EXPIRED: metadata/PNG/JPG denied; waiting for cleanup timer (up to 150s)', flush=True)

    deadline = time.monotonic() + 150
    while True:
        if db('deleted', gid=gid, guestId=info['guestId'], paths=info['paths'])['deleted']:
            break
        require(time.monotonic() < deadline, 'Timer did not remove test guest/files within 150 seconds')
        time.sleep(5)
    result = run(['systemctl', 'show', '--value', '-p', 'Result', 'tatar-staging-cleanup.service']).decode().strip()
    require(result == 'success', 'Cleanup service did not report success')
    preserved = db('preserved', baseline=baseline)['preserved']
    require(json.loads(request_http('/api/health')).get('ok') is True, 'Final health failed')
    require(json.loads(request_http('/api/capabilities')).get('realUniqueElements') == 110, 'Final catalog mismatch')
    evidence = dict(testGeneration=gid, timerDeletedRowsAndFiles=True, exportSha=True,
                    expiredHttpStatus=401, existingWorksPreserved=preserved,
                    acceleratedDeadline=True, real24HourWait=False, aiCalls=0)
    out = DATA / 'checks' / ('guest-expiry-' + request_id + '.json')
    out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2) + '\n')
    print('GUEST EXPIRY + TIMER CLEANUP PASS; HTTPS/catalog110 OK', flush=True)
    print('Evidence: ' + str(out), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('STOP: ' + str(exc), file=sys.stderr)
        print('Do not reset guests. Inspect: journalctl -u tatar-staging-cleanup -n 40 --no-pager', file=sys.stderr)
        sys.exit(1)
