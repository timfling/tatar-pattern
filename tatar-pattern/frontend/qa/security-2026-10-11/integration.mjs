import assert from 'node:assert/strict';
import {randomUUID,randomBytes,createHash} from 'node:crypto';
import {writeFileSync} from 'node:fs';
import {createApi,exportUrl} from '../../src/lib/api.ts';
const origin='http://127.0.0.1:3011'; let cookie=''; const checks=[];
const transport=async(path,init={})=>{const r=await fetch(origin+path,{...init,headers:{...init.headers,Origin:origin,...(cookie?{Cookie:cookie}:{})}});const c=r.headers.get('set-cookie');if(c)cookie=c.split(';')[0];return r;};
const api=createApi(transport);const check=(name,value)=>{assert.ok(value,name);checks.push(name);};
check('health via production Next rewrite',(await api.health()).ok);
const email='security-'+randomUUID()+'@example.com',password=randomBytes(24).toString('hex');
const user=(await api.register(email,password,{firstName:'QA',lastName:'Security',occupation:'',avatar:null})).user;
check('register and session',(await api.me()).user.id===user.id);await api.logout();await assert.rejects(api.me(),e=>e.status===401);await assert.rejects(api.login(email,'incorrect-password'),e=>e.status===401);await api.login(email,password);check('login after logout',(await api.me()).user.id===user.id);
const catalog=await api.elements();check('real catalog',catalog.items.length>0&&!catalog.items[0].isFixture);
const selections={style:'heritage',composition:'rapport',parameters:'default',elementCodes:['TP-E-008','TP-E-010'],motifs:[],palette:'emerald',usage:'web',colorMode:'original',outputSize:[900,1200]};
const g=(await api.generate(selections,'',undefined,undefined,'flat')).generation;
check('real generation',g.status==='done'&&g.imageUrl&&!g.recipe.isFixture);check('history',(await api.generations()).items.some(x=>x.id===g.id));check('reopen',(await api.generation(g.id)).generation.id===g.id);
const files=[];for(const fmt of ['png','jpg']){const r=await transport(exportUrl(g.id,fmt));check(fmt+' export',r.ok&&r.headers.get('content-type').startsWith(fmt==='png'?'image/png':'image/jpeg')&&r.headers.get('content-disposition').includes('attachment'));const bytes=Buffer.from(await r.arrayBuffer());writeFileSync(new URL('result.'+fmt,import.meta.url),bytes);files.push({format:fmt,sha256:createHash('sha256').update(bytes).digest('hex')});}
check('image endpoint',(await transport(g.imageUrl)).ok);await api.logout();check('image denied after logout',(await transport(g.imageUrl)).status===401);
for(const route of ['/','/login','/register','/constructor','/library'])check('production page '+route,(await fetch(origin+route)).ok);
writeFileSync(new URL('integration-result.json',import.meta.url),JSON.stringify({environment:'isolated PostgreSQL frontend_qa_20261009, copied storage, production Next 16.4.0 loopback',checks,files,result:'passed'},null,2)+'\n');console.log(checks.length+' checks passed');
