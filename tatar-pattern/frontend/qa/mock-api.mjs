// Local UI test adapter only. Never imported by the application or production backend.
// Every image is the existing synthetic test fixture; this does not prove catalog/DSLab.
import http from 'node:http';
import { readFile } from 'node:fs/promises';
const files = { png: await readFile(new URL('./downloads/test-fixture-result.png', import.meta.url)), jpg: await readFile(new URL('./downloads/test-fixture-result.jpg', import.meta.url)) };
const selections = {style:'heritage',composition:'rapport',parameters:'default',motifs:[],elementCodes:['test-corner'],palette:'emerald',usage:'web',scale:1,transparentBackground:false,colorMode:'original'};
const generations = new Map(); const projects = new Map(); const polls = new Map();
const fixture = (id,mode='flat') => ({id,mode,status:'done',title:`MOCK ${mode} ${id}`,createdAt:new Date().toISOString(),selections,prompt:'',rating:null,projectId:null,imageUrl:`/api/generations/${id}/file?format=png`,formats:['png','jpg'],recipe:{isFixture:true,size:[800,800]},warnings:[{code:'TEST_FIXTURE',message:'MOCK: синтетический результат. DSLab не вызывался.'}]});
generations.set('ai-history',fixture('ai-history','ai'));
const realCatalogOrigin = process.env.REAL_CATALOG_ORIGIN;
const server = http.createServer(async(req,res) => {
 const url = new URL(req.url,'http://127.0.0.1'); let input={};
 for await (const chunk of req) input._raw=(input._raw??'')+chunk;
 if(input._raw) input=JSON.parse(input._raw);
 const send=(data,status=200)=>{res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(data));};
 const error=(code,message,status)=>send({error:{code,message}},status);
 const path=url.pathname.replace(/^\/api/,'');
 if(realCatalogOrigin && (path==='/elements' || path==='/capabilities' || path.startsWith('/elements/'))) {
  try { const upstream=await fetch(realCatalogOrigin+url.pathname+url.search); res.writeHead(upstream.status,{'Content-Type':upstream.headers.get('Content-Type')??'application/json'}); return res.end(Buffer.from(await upstream.arrayBuffer())); }
  catch { return error('REAL_CATALOG_UNAVAILABLE','Настоящий каталог недоступен.',503); }
 }
 if(path==='/health') return send({ok:true,testAdapter:true});
 if(path==='/auth/login'||path==='/auth/register') {
  if(input.password==='wrong-password') return error('INVALID_CREDENTIALS','Неверный пароль.',401);
  res.setHeader('Set-Cookie','tp_mock_session=local-test; HttpOnly; SameSite=Lax; Path=/api');
  return send({user:{id:'mock-user',email:'mock-ui@example.test'}});
 }
 if(path==='/auth/logout'){res.setHeader('Set-Cookie','tp_mock_session=; Max-Age=0; Path=/api');return send({ok:true});}
 if(path==='/auth/me') return req.headers.cookie?.includes('tp_mock_session=local-test') ? send({user:{id:'mock-user',email:'mock-ui@example.test'}}) : error('UNAUTHORIZED','Войдите в аккаунт.',401);
 if(path==='/capabilities') return send({modes:{flat:{available:true},ai:{available:false,reason:'DSLab not connected'}},elementSelection:'elementCodes',maxSelectedElements:16,scaleRange:[0.3,2],transparentPng:true,colorModes:['original','silhouette'],compositions:['medallion','border','rapport'],parameters:['default','sparse','dense'],palettes:['emerald','porcelain','leather'],styles:{heritage:'Исходная маска',modern:'Силуэт','porcelain-sign':'Контур','leather-mosaic':'Заливка и шов',festive:'Чередование цветов'},usageSizes:{architecture:[1024,1024],textile:[1024,1024],packaging:[1200,900],interior:[1200,900],web:[800,600]},formats:['png','jpg']});
 if(path==='/elements') return send({items:[['test-corner','Угол рамки','Угол рамки','corner'],['test-flower','Цветок','Цветочные','flower'],['test-line','Линия','Геометрические','line']].map(([code,nameRu,motifClass,motifKey])=>({code,nameRu:`MOCK ${nameRu}`,motifClass,motifKey,imageUrl:`/api/elements/${code}/file`,isFixture:true})),total:3});
 if(path.match(/^\/elements\/[^/]+\/file$/)){res.writeHead(200,{'Content-Type':'image/png'});return res.end(files.png);}
 if(!req.headers.cookie?.includes('tp_mock_session=local-test')) return error('UNAUTHORIZED','Войдите в аккаунт.',401);
 if(path==='/projects') {
  if(req.method==='POST'){const project={id:String(projects.size+1),title:input.title,createdAt:new Date().toISOString()};projects.set(project.id,project);return send({project},201);}
  return send({items:[...projects.values()]});
 }
 const pm=path.match(/^\/projects\/([^/]+)$/);if(pm){const project=projects.get(pm[1]);if(!project)return error('NOT_FOUND','Проект не найден.',404);if(req.method==='DELETE'){projects.delete(pm[1]);return send({ok:true});}Object.assign(project,input);return send({project});}
 if(path==='/generations') {
  if(req.method==='POST') {
   if(input.mode==='ai')return error('AI_UNAVAILABLE','DSLab не подключён.',503);
   if(input.prompt==='[network-error]')return error('TEST_ERROR','MOCK: сервис временно недоступен. Повторите запрос.',503);
   const id=String(generations.size+1);const g={...fixture(id),selections:input.selections,prompt:input.prompt,projectId:input.projectId??null,status:'queued',imageUrl:null};
   if(input.prompt==='[empty-result]'){g.status='done';g.imageUrl=null;}
   if(input.prompt==='[broken-file]'){g.status='done';g.imageUrl='/api/generations/missing/file';}
   if(input.prompt==='[failed-job]'){g.status='failed';g.error={code:'TEST_ERROR',message:'MOCK: ошибка задания'};}
   generations.set(id,g);return send({generation:g},201);
  }
  const list=[...generations.values()].reverse();return send({items:list.slice(Number(url.searchParams.get('offset')??0)),total:list.length});
 }
 const gm=path.match(/^\/generations\/([^/]+)(\/file)?$/);if(gm){const g=generations.get(gm[1]);if(!g)return error('NOT_FOUND','Результат не найден.',404);
  if(gm[2]){const format=url.searchParams.get('format')==='jpg'?'jpg':'png';res.writeHead(200,{'Content-Type':format==='png'?'image/png':'image/jpeg',...(url.searchParams.get('download')?{'Content-Disposition':`attachment; filename="mock-result.${format}"`}:{})});return res.end(files[format]);}
  if(req.method==='PATCH') Object.assign(g,input);
  else if(['queued','processing'].includes(g.status)){const n=(polls.get(g.id)??0)+1;polls.set(g.id,n);g.status=n>=2?'done':'processing';g.progress=n>=2?100:undefined;if(n>=2)g.imageUrl=`/api/generations/${g.id}/file?format=png`;}
  return send({generation:g});
 }
 error('NOT_FOUND','Маршрут отсутствует.',404);
});
server.listen(8012,'127.0.0.1',()=>process.stdout.write('MOCK UI adapter http://127.0.0.1:8012; synthetic images only\n'));
