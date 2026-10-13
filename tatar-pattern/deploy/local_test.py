#!/usr/bin/env python3
"""Exercise only a dedicated compose.local stack; no existing DB/colleague ports."""
import argparse
import hashlib
import http.cookiejar
import json
from pathlib import Path
import secrets
import urllib.error
import urllib.request
from ops import read_env, compose, backup, restore_check

p = argparse.ArgumentParser()
p.add_argument('--env', type=Path, required=True)
a = p.parse_args()
envfile = a.env.resolve()
values = read_env(envfile)
if not values['COMPOSE_PROJECT_NAME'].startswith('tp-deploy-check-') or not Path(values['DATA_ROOT']).is_relative_to(Path(__file__).resolve().parent/'local-check'):
    raise ValueError('Refuse non-isolated project/data root')
dc = compose(envfile, values, local=True)
port = dc('port', 'proxy', '80', capture=True).decode().strip()
if not port.startswith('127.0.0.1:'):
    raise ValueError('Proxy must bind localhost only')
url = 'http://' + port
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def req(path, body=None, method=None, origin=None, opener=client):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url+path, data=data, method=method,
                               headers={'Content-Type':'application/json','Origin':origin or url})
    try:
        with opener.open(r, timeout=120) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()

def obj(path, body=None, method=None):
    status, headers, data = req(path, body, method)
    assert status in (200,201), (path,status,data[:200])
    return json.loads(data), headers

report = {'project':values['COMPOSE_PROJECT_NAME'],'release':values['RELEASE'],'url':url, 'fixtureOnly':True}
assert req('/')[0] == 200
assert obj('/api/health')[0]['ok']
assert obj('/api/capabilities')[0]['realUniqueElements'] == 0
assert not obj('/api/capabilities')[0]['modes']['ai']['available']
password=secrets.token_urlsafe(24)
email='deploy-'+secrets.token_hex(8)+'@example.com'
_, headers = obj('/api/auth/register', {'email':email,'password':password})
cookie = headers['Set-Cookie']
assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie and 'Path=/api' in cookie
assert req('/api/projects',{'title':'bad-origin'},origin='https://evil.invalid')[0] == 403
project = obj('/api/projects',{'title':'deploy isolated'})[0]['project']['id']
gen = obj('/api/generations',{'projectId':project,'selections':{'style':'heritage','composition':'rapport','parameters':'default','motifs':['tulip'],'palette':'emerald','usage':'web'}})[0]['generation']
assert gen['status']=='done' and gen['recipe']['isFixture']
gid=gen['id']
hashes={}
for fmt,magic in [('png',b'\x89PNG'),('jpg',b'\xff\xd8')]:
    status,h,b=req(f'/api/generations/{gid}/file?format={fmt}&download=true')
    assert status==200 and b.startswith(magic) and 'attachment' in h['Content-Disposition']
    hashes[fmt]=hashlib.sha256(b).hexdigest()
assert obj('/api/generations')[0]['total'] >= 1
obj('/api/auth/logout',{})
assert req('/api/auth/me')[0]==401
obj('/api/auth/login',{'email':email,'password':password})
other=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
assert req('/api/auth/register',{'email':'other-'+secrets.token_hex(8)+'@example.com','password':secrets.token_urlsafe(24)},opener=other)[0]==201
assert req(f'/api/generations/{gid}',opener=other)[0]==404
assert req(f'/api/generations/{gid}/file?format=png',opener=other)[0]==404
# Record only assertions/image hashes, not cookies/accounts/passwords.
dc('restart','backend','frontend','proxy')
dc('up','-d','--wait','--no-build')
# Docker may reassign an ephemeral host port after restart. Cookies are host-scoped.
url = 'http://' + dc('port','proxy','80',capture=True).decode().strip()
obj('/api/auth/me')
for fmt,sha in hashes.items():
    status,_,b=req(f'/api/generations/{gid}/file?format={fmt}')
    assert status==200 and hashlib.sha256(b).hexdigest()==sha
snapshot=backup(dc, values)
restore_check(envfile, values, snapshot)
report.update(resultHashes=hashes, generationId=gid, backup=snapshot.name,
              checks=['home/API health','AI unavailable','fixture count0 real','HttpOnly/Lax/Path cookie','foreign Origin403','ownership404','PNG/JPG real bytes','logout/login/history','restart same session/files SHA','DB+storage backup','isolated pg_restore/checksums/rowcounts/API health'])
(Path(values['DATA_ROOT']).parent/'RESULT.json').write_text(json.dumps(report,indent=2))
print('LOCAL PASS: production processes, /api proxy, ownership, restart persistence, coordinated backup and isolated restore')
