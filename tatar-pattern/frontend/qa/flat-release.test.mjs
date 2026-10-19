// Pure request/transport checks, not browser or real GPU evidence.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const moduleUrl=s=>'data:text/javascript;base64,'+Buffer.from(ts.transpileModule(s,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText).toString('base64');
const url=moduleUrl(readFileSync(new URL('../src/lib/api.ts',import.meta.url),'utf8'));
const {createApi}=await import(url);
const {flatSelections}=await import(moduleUrl(readFileSync(new URL('../src/lib/flat-request.ts',import.meta.url),'utf8').replace('"./api"',JSON.stringify(url))));
const scheme={id:'accepted',composition:'medallion',reviewStatus:'owner_accepted_2026_10_13',available:true,minimumSelected:1,maximumSelected:2,allowedElementCodes:['A','B','missing'],availableElementCodes:['A','B'],centerCandidates:['A']};
const catalog={registryVersion:'test-registry',schemes:[scheme]};
const settings={parameters:'dense',palette:'porcelain',scale:.8,transparentBackground:true,outputSize:[1024,1024],backgroundColor:null,rapportOutput:'module',moduleSize:[1024,1024]};
test('flat rejects unaccepted, unavailable, stale or unsupported selections without substituting motifs',()=>{
 for(const reviewStatus of ['revised_awaiting_owner_review','polished_awaiting_owner_review','designer_proposal']) {const s={...scheme,reviewStatus};assert.throws(()=>flatSelections({...catalog,schemes:[s]},s,['A'],settings));}
 const absent={...scheme,available:false};assert.throws(()=>flatSelections({...catalog,schemes:[absent]},absent,['A'],settings));
 assert.throws(()=>flatSelections(catalog,{...scheme},['A'],settings));
 for(const codes of [[],['unknown'],['missing'],['A','A'],['A','B','missing']]) assert.throws(()=>flatSelections(catalog,scheme,codes,settings));
 assert.throws(()=>flatSelections(catalog,scheme,['B'],{...settings,primaryElementCode:'A'}));
});
test('flat projects supported fields and calls real endpoint shape with same preflight seed',async()=>{
 const codes=['A','B'];const selections=flatSelections(catalog,scheme,codes,{...settings,primaryElementCode:'A'});
 assert.deepEqual(selections.elementCodes,codes);assert.equal(selections.colorMode,'original');assert.equal(selections.registryVersion,'test-registry');assert.equal(selections.primaryElementCode,'A');assert.ok(!('moduleSize' in selections));assert.ok(!('rapportOutput' in selections));
 const calls=[];const api=createApi(async(path,init)=>{calls.push({path,body:JSON.parse(init.body)});return Response.json({generation:{id:'transport-only'}});});
 await api.preflight(selections,19);await api.generate(selections,'',undefined,undefined,'flat',19);
 assert.deepEqual(calls.map(c=>c.path),['/api/composition-preflight','/api/generations']);
 for(const c of calls){assert.equal(c.body.mode,'flat');assert.equal(c.body.seed,19);assert.deepEqual(c.body.selections,selections);assert.ok(!('ai' in c.body));assert.ok(!('requestId' in c.body));}
});
test('email/password registration omits optional profile',async()=>{
 let body;const api=createApi(async(path,init)=>{body=JSON.parse(init.body);assert.equal(path,'/api/auth/register');return Response.json({user:{id:'transport-only'}});});
 await api.register('qa@example.com','test-password-only');assert.deepEqual(Object.keys(body).sort(),['email','password']);
});
