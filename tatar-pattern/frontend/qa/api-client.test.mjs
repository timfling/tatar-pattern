// Explicit test transport. No fixture responses are reachable from the production app.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createApi, ApiError, toApiSelections } from '../src/lib/api.ts';
const selections = {style:'heritage',composition:'rapport',parameters:'default',motifs:['tulip'],palette:'emerald',usage:'web'};
const fixture = { id:'test-fixture',status:'done',imageUrl:'/api/generations/test-fixture/file?format=png',title:'TEST RESPONSE',createdAt:'2026-10-02T00:00:00Z',selections,prompt:'',rating:null,projectId:null,recipe:{isFixture:true} };
test('all mutations use credentials and JSON, including empty logout and DELETE', async () => {
 const calls=[];
 const api=createApi(async (url,init)=>{ calls.push({url,init}); return Response.json({ok:true,user:{id:'fixture',email:'test@example.com'}}); });
 await api.login('test@example.com','test-password'); await api.logout(); await api.deleteProject('folder');
 for (const {init} of calls) { assert.equal(init.credentials,'include'); assert.equal(init.cache,'no-store'); assert.equal(init.headers['Content-Type'],'application/json'); }
 assert.deepEqual(calls.map(c=>c.init.method),['POST','POST','DELETE']);
});
test('PATCH preserves explicit null and omits unset fields', async () => {
 let input;
 const api=createApi(async (_url,init)=>{ input=JSON.parse(init.body);return Response.json({generation:fixture}); });
 await api.patchGeneration('test-fixture',{rating:null,projectId:null});
 assert.deepEqual(input,{rating:null,projectId:null});
});
test('queued, measured progress and done remain server values', async () => {
 const replies=[{...fixture,status:'queued',imageUrl:null,progress:undefined},{...fixture,status:'processing',imageUrl:null,progress:21},fixture];
 const api=createApi(async()=>Response.json({generation:replies.shift()}));
 assert.equal((await api.generate(selections)).generation.progress,undefined);
 assert.equal((await api.generation('test-fixture')).generation.progress,21);
 assert.equal((await api.generation('test-fixture')).generation.imageUrl,fixture.imageUrl);
});
test('server catalog errors and network failures never fall back to a fixture',async()=>{
 const api=createApi(async()=>Response.json({error:{code:'CATALOG_EMPTY',message:'Каталог пуст'}},{status:409}));
 await assert.rejects(api.generate(selections),(e)=>e instanceof ApiError&&e.code==='CATALOG_EMPTY'&&e.status===409);
 const offline=createApi(async()=>{throw new TypeError('network');});
 await assert.rejects(offline.projects(),(e)=>e.code==='NETWORK_ERROR');
});
test('abort stays abort and incomplete form does not submit null selections',async()=>{
 const api=createApi(async()=>{throw new DOMException('Stopped','AbortError');});
 await assert.rejects(api.generate(selections),(e)=>e.name==='AbortError');
 assert.throws(()=>toApiSelections({...selections,style:null}),/Настройте/);
});
