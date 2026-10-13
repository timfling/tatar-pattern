"""Seed one private QA session in the dedicated test API, never production."""
import json, secrets, urllib.request, http.cookiejar
from pathlib import Path
jar=http.cookiejar.CookieJar(); client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
email='ui-'+secrets.token_hex(5)+'@example.com'
body={'email':email,'password':secrets.token_urlsafe(24),'firstName':'Тест','lastName':'Интерфейса','occupation':'designer','avatar':None}
req=urllib.request.Request('http://127.0.0.1:8014/api/auth/register',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
user=json.load(client.open(req))['user']
selectors={'style':'heritage','composition':'medallion','parameters':'default','elementCodes':['TP-E-008','TP-E-010'],'motifs':[],'palette':'emerald','usage':'web','colorMode':'original','outputSize':[900,1200]}
req=urllib.request.Request('http://127.0.0.1:8014/api/generations',data=json.dumps({'selections':selectors}).encode(),headers={'Content-Type':'application/json'})
generation=json.load(client.open(req))['generation']
cookie=next(iter(jar)).value
page=Path('.qa/browser-session.html');page.parent.mkdir(exist_ok=True);page.write_text('<!doctype html><meta charset="utf-8"><script>document.cookie='+json.dumps('tp_session='+cookie+'; Path=/api; SameSite=Lax')+';location.replace("/constructor?pattern='+generation['id']+'");</script>');page.chmod(0o600)
Path('.qa/ui-proof.json').write_text(json.dumps({'generation':generation['id'],'user':user['id'],'isFixture':generation['recipe']['isFixture'],'size':generation['recipe']['size']}))
print('Private QA session prepared; real image size:',generation['recipe']['size'],'fixture:',generation['recipe']['isFixture'])
