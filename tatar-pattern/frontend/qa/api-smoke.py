"""Real HTTP test against the explicitly isolated fixture API; no production data."""
from pathlib import Path
import hashlib, io, json, os, secrets, uuid
from urllib.parse import urlparse
import httpx
from PIL import Image

origin = os.environ.get('TP_QA_API_URL', 'http://127.0.0.1:8001').rstrip('/')
assert urlparse(origin).hostname in ('127.0.0.1', 'localhost'), 'Local test environment required'
root = Path(__file__).resolve().parent
checks = []
def check(label, condition):
    assert condition, label
    checks.append(label)

session = httpx.Client()
session.headers.update({'Origin': origin, 'Content-Type': 'application/json'})
def request(method, path, body=None, expected=200):
    r = session.request(method, origin+'/api'+path, json=body, timeout=30)
    assert r.status_code == expected, f'{method} {path}: HTTP {r.status_code}: {r.text[:400]}'
    return r

health = request('GET', '/health').json()
assert health.get('allowFixtures') is True, 'Fixture test API required; refusing production'
email = 'frontend-http-'+uuid.uuid4().hex+'@example.com'
password = secrets.token_urlsafe(24)
request('POST', '/auth/register', {'email': email, 'password': password}, 201)
check('HttpOnly session cookie', any(c.has_nonstandard_attr('HttpOnly') for c in session.cookies.jar))
check('Server user', request('GET', '/auth/me').json()['user']['email'] == email)
elements = request('GET', '/elements').json()['items']
check('Explicit test catalog', bool(elements) and all(e.get('isFixture') for e in elements))
project = request('POST', '/projects', {'title':'Frontend HTTP QA'}, 201).json()['project']
selections = {'style':'heritage','composition':'rapport','parameters':'sparse','motifs':['tulip','bud'], 'palette':'porcelain','usage':'web'}
g = request('POST', '/generations', {'selections':selections,'prompt':'Test note, not an AI edit','projectId':project['id']}, 201).json()['generation']
check('Done only after image persistence', g['status']=='done' and g['imageUrl'] and g['progress']==100)
check('Fixture and unsupported prompt are explicit', g['recipe']['isFixture'] and {'TEST_FIXTURE','PROMPT_UNSUPPORTED'} <= {w['code'] for w in g['warnings']})
request('PATCH','/generations/'+g['id'],{'title':'Frontend HTTP QA result','rating':'like'})
exports = []
(root/'downloads').mkdir(exist_ok=True)
for fmt,mime in [('png','image/png'),('jpg','image/jpeg')]:
    r = request('GET', f"/generations/{g['id']}/file?format={fmt}&download=true")
    check(fmt.upper()+' MIME and filename', r.headers['Content-Type'].startswith(mime) and 'attachment' in r.headers['Content-Disposition'])
    im=Image.open(io.BytesIO(r.content));im.load()
    check(fmt.upper()+' decoded image', im.size == (800,800) and im.format == ('PNG' if fmt=='png' else 'JPEG'))
    dest=root/'downloads'/('test-fixture-result.'+fmt);dest.write_bytes(r.content)
    exports.append({'format':fmt,'dimensions':list(im.size),'bytes':len(r.content),'sha256':hashlib.sha256(r.content).hexdigest()})
request('POST','/auth/logout')
request('GET','/auth/me',expected=401)
request('POST','/auth/login',{'email':email,'password':password})
found=request('GET','/generations/'+g['id']).json()['generation']
check('Re-login preserves title, rating, selections, project and note',found['title']=='Frontend HTTP QA result' and found['rating']=='like' and found['selections']==selections and found['projectId']==project['id'] and found['prompt']=='Test note, not an AI edit')
check('History contains persisted result', any(x['id']==g['id'] for x in request('GET','/generations').json()['items']))
request('PATCH','/generations/'+g['id'],{'rating':None,'projectId':None})
cleared=request('GET','/generations/'+g['id']).json()['generation']
check('Explicit null clears rating and project',cleared['rating'] is None and cleared['projectId'] is None)
request('PATCH','/generations/'+g['id'],{'projectId':project['id']})
request('DELETE','/projects/'+project['id'])
check('Deleting project retains generation',request('GET','/generations/'+g['id']).json()['generation']['projectId'] is None)
request('POST','/auth/logout')
request('GET',f"/generations/{g['id']}/file?format=png",expected=401)
check('Files require session',True)
summary={'environment':'isolated PostgreSQL test DB / synthetic fixtures / real FastAPI via HTTP','apiOrigin':origin,'checks':checks,'exports':exports,'generationId':g['id'],'productionVerified':False}
(root/'api-smoke-result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
