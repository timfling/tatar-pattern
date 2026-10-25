import asyncio
from contextlib import asynccontextmanager, suppress
import hashlib
import logging
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, FastAPI, Path, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException

from .catalog import MOTIFS, catalog, safe_path, selected_elements
from .config import Settings
from .errors import APIError
from .generator import VERSION, render
from .jobs import enqueue_ai
from .ai_provider import configured_provider
from .ai_catalog import catalog_response, find_base, asset_file
from .composition import render_composition, VERSION as COMPOSITION_VERSION
from .composition_metadata import metadata, review
from . import generator_v2
from .scheme_catalog import registry, ASSETS, release_catalog
from .descriptions import describe, saved_or_fallback
from .trash import purge
from . import guest
from .models import GuestGenerate, GuestSession, Credentials, Registration, Profile, Generate, PatchGeneration, Project

COOKIE='tp_session'
ID=Annotated[str,Path(pattern=r'^[1-9][0-9]{0,17}$')]
logger=logging.getLogger(__name__)


def create_app(settings=None):
    settings=settings or Settings.from_env()
    if os.getenv('TP_ENVIRONMENT')=='production' and settings.public_guest_mode and not settings.cookie_secure:
        raise RuntimeError('Public guest production requires COOKIE_SECURE=true and HTTPS')
    settings.storage_root.mkdir(parents=True,exist_ok=True)
    @asynccontextmanager
    async def lifespan(app):
        async def cleanup():
            while True:
                try:
                    with attempts_lock:
                        for ip in list(attempts):
                            if not attempts[ip] or attempts[ip][-1]<time.monotonic()-60:
                                del attempts[ip]
                    await asyncio.to_thread(guest.clean, settings)
                    if not settings.public_guest_mode:
                        await asyncio.to_thread(purge, settings)
                except Exception as exc:
                    logger.warning('Trash cleanup deferred (%s)',type(exc).__name__)
                await asyncio.sleep(60)
        task=asyncio.create_task(cleanup())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
    app=FastAPI(title='TATAR PATTERN API',version='0.1.0',lifespan=lifespan)
    app.state.settings=settings
    app.add_middleware(CORSMiddleware,allow_origins=list(settings.origins),allow_credentials=True,allow_methods=['GET','POST','PATCH','DELETE'],allow_headers=['Content-Type'])
    hasher=PasswordHasher()
    dummy_hash=hasher.hash(secrets.token_urlsafe(24))
    attempts=defaultdict(deque)
    attempts_lock=threading.Lock()
    render_slots=threading.BoundedSemaphore(2)

    @app.middleware('http')
    async def guards(request, call_next):
        path=request.url.path
        if settings.public_guest_mode and (path.startswith(('/api/auth/','/api/projects','/api/generations','/api/profile','/api/history','/api/trash')) or path=='/api/composition-preflight'):
            response=JSONResponse({'error':{'code':'ACCOUNT_API_DISABLED','message':'Аккаунтные маршруты отключены.'}},status_code=404)
            response.headers['Cache-Control']='no-store'
            response.delete_cookie(COOKIE,path='/api')
            return response
        if request.method in ('POST','PATCH','DELETE'):
            origin=request.headers.get('origin')
            own_origin=f'{request.url.scheme}://{request.url.netloc}'
            if (origin is not None and origin not in settings.origins and origin!=own_origin) or (origin is None and request.headers.get('sec-fetch-site')=='cross-site'):
                return JSONResponse({'error':{'code':'ORIGIN_FORBIDDEN','message':'Недопустимый Origin запроса.'}},status_code=403)
            if request.method in ('POST','PATCH') and request.headers.get('content-type','').split(';')[0].lower()!='application/json':
                return JSONResponse({'error':{'code':'JSON_REQUIRED','message':'Нужен Content-Type: application/json.'}},status_code=415)
            try:
                content_length=int(request.headers.get('content-length','0') or '0')
            except ValueError:
                return JSONResponse({'error':{'code':'INVALID_CONTENT_LENGTH','message':'Неверная длина запроса.'}},status_code=400)
            if content_length>16384:
                return JSONResponse({'error':{'code':'REQUEST_TOO_LARGE','message':'Запрос слишком большой.'}},status_code=413)
            # Also bound chunked JSON requests without Content-Length.
            body=bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body)>16384:
                    return JSONResponse({'error':{'code':'REQUEST_TOO_LARGE','message':'Запрос слишком большой.'}},status_code=413)
            request._body=bytes(body)
        response=await call_next(request)
        response.headers['Referrer-Policy']='no-referrer'
        if settings.public_guest_mode and COOKIE in request.cookies:
            response.delete_cookie(COOKIE,path='/api')
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Cache-Control']='no-store'
        return response

    @app.exception_handler(APIError)
    async def api_error(request, exc):
        return JSONResponse(exc.payload,status_code=exc.status)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        code='NOT_FOUND' if exc.status_code==404 else 'HTTP_ERROR'
        return JSONResponse({'error':{'code':code,'message':str(exc.detail)}},status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Never echo passwords or request inputs into errors.
        details=[{'field':'.'.join(map(str,e['loc'])),'message':e['msg']} for e in exc.errors()]
        return JSONResponse({'error':{'code':'VALIDATION_ERROR','message':'Проверьте поля запроса.','details':details}},status_code=422)

    @app.exception_handler(psycopg.Error)
    async def db_error(request, exc):
        logger.error('Database operation failed (%s)',type(exc).__name__)
        return JSONResponse({'error':{'code':'DATABASE_UNAVAILABLE','message':'База недоступна или не подготовлена.'}},status_code=503)

    def db():
        with psycopg.connect(settings.database_url,row_factory=dict_row,connect_timeout=3) as conn:
            conn.execute('SET statement_timeout=10000')
            yield conn

    def current_user(request:Request,conn=Depends(db)):
        if settings.public_guest_mode:
            raise APIError(404,'ACCOUNT_API_DISABLED','Аккаунтные маршруты отключены.')
        token=request.cookies.get(COOKIE,'')
        if not token or len(token)>200:
            raise APIError(401,'UNAUTHENTICATED','Войдите в аккаунт.')
        row=conn.execute('SELECT u.id,u.email,u.profile FROM sessions s JOIN users u ON u.id=s.user_id WHERE NOT u.access_blocked AND s.token_hash=%s AND s.expires_at>now() FOR SHARE OF u', (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if row is None:
            raise APIError(401,'UNAUTHENTICATED','Сессия истекла. Войдите снова.')
        return row

    def auth_limit(request):
        key=request.client.host if request.client else 'local'
        now=time.monotonic()
        with attempts_lock:
            # Bound process memory even with many client addresses.
            for ip in list(attempts):
                if not attempts[ip] or attempts[ip][-1]<now-60:
                    del attempts[ip]
            if key not in attempts and len(attempts)>=10000:
                raise APIError(429,'REQUEST_RATE_LIMIT','Слишком много запросов.')
            queue=attempts[key]
            while queue and queue[0]<now-60:
                queue.popleft()
            if len(queue)>=20:
                raise APIError(429,'REQUEST_RATE_LIMIT','Слишком много запросов. Повторите через минуту.')
            queue.append(now)

    def issue_session(conn,row,response,request):
        # Serialize session creation against operator blocking/revocation.
        if not conn.execute('SELECT id FROM users WHERE id=%s AND NOT access_blocked FOR SHARE',(row['id'],)).fetchone():
            raise APIError(401,'UNAUTHENTICATED','Аккаунт недоступен.')
        old=request.cookies.get(COOKIE)
        if old:
            conn.execute('DELETE FROM sessions WHERE token_hash=%s',(hashlib.sha256(old.encode()).hexdigest(),))
        token=secrets.token_urlsafe(32)
        expires=datetime.now(timezone.utc)+timedelta(days=settings.session_days)
        conn.execute('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(%s,%s,%s)',(hashlib.sha256(token.encode()).hexdigest(),row['id'],expires))
        conn.commit()
        response.set_cookie(COOKIE,token,max_age=settings.session_days*86400,httponly=True,secure=settings.cookie_secure,samesite='lax',path='/api')
        return {'user':user_json(row)}

    def user_json(row):
        return {'id':str(row['id']), 'email':row['email'], **(row.get('profile') or {})}

    def purge_trash(conn, uid):
        purge(settings,uid)

    def owned_project(conn,pid,uid):
        row=conn.execute('SELECT * FROM projects WHERE id=%s AND user_id=%s',(pid,uid)).fetchone()
        if row is None:
            raise APIError(404,'NOT_FOUND','Проект не найден.')
        return row

    def owned_generation(conn,gid,uid):
        row=conn.execute('SELECT * FROM generations WHERE NOT EXISTS (SELECT 1 FROM erasure_tombstones t WHERE t.generation_id=generations.id) AND id=%s AND user_id=%s AND (deleted_at IS NULL OR deleted_at >= now()-interval \'7 days\')',(gid,uid)).fetchone()
        if row is None:
            raise APIError(404,'NOT_FOUND','Результат не найден.')
        return row

    def project_json(row):
        return {'id':str(row['id']),'title':row['title'],'createdAt':row['created_at'].isoformat()}

    def generation_json(row):
        params=row['params'] or {}
        present=False
        if row['result_path']:
            try:
                present=safe_path(settings.storage_root,row['result_path']).is_file()
            except ValueError:
                pass
        explanation=saved_or_fallback(params)
        recipe=params.get('recipe') or {}
        return {'description':explanation['text'],'descriptionDetails':explanation,'culturalNote':explanation.get('culturalNote'),
                'compatibility':recipe.get('compatibility',{'status':'not_evaluated','cultural':'unknown'}),
                'outputKind':recipe.get('outputKind','ai_image' if params.get('mode')=='ai' else 'legacy_image'),
                'seamless':recipe.get('seamless'), 'repeat':recipe.get('repeat'),
                'moduleUrl':f"/api/generations/{row['id']}/file?format=png&artifact=module" if row['status']=='done' and recipe.get('repeat',{} ) and recipe['repeat'].get('moduleSha256') else None,
                'id':str(row['id']),'title':row['title'],'status':row['status'],'progress':row['progress'],
                'imageUrl':f"/api/generations/{row['id']}/file?format=png" if row['status']=='done' and present else None,
                'deletedAt':row.get('deleted_at').isoformat() if row.get('deleted_at') else None,'createdAt':row['created_at'].isoformat(),'finishedAt':row['finished_at'].isoformat() if row['finished_at'] else None,
                'ai':params.get('ai'),'requestId':params.get('clientRequestId'),'mode':params.get('mode','flat'),'seed':params.get('seed'), 'modelVersion':row['model_version'],'selections':params.get('selections'),'prompt':row['user_prompt'] or '', 'rating':row['rating'],
                'projectId':str(row['project_id']) if row['project_id'] else None,'algorithmVersion':row['model_version'],
                'warnings':params.get('warnings',[]),'recipe':params.get('recipe'),'error':row['error']}

    @app.get('/api/health')
    def health(conn=Depends(db)):
        conn.execute('SELECT token_hash FROM sessions LIMIT 0')
        conn.execute('SELECT code FROM approved_element_files LIMIT 0')
        return {'ok':True,'algorithmVersion':VERSION,'allowFixtures':settings.allow_fixtures}

    @app.get('/api/capabilities')
    def capabilities(conn=Depends(db)):
        rows=catalog(conn,settings)
        return {'generationMode':'synchronous','formats':['png','jpg'],'motifs':{**MOTIFS,**{r['motif_key']:r['motif_class'] for r in rows}},'realUniqueElements':len({r['content_sha256'] for r in rows if not r['is_fixture']}),'modes':{'flat':{'available':True,'generationMode':'synchronous'},'ai':{'available':catalog_response(settings,configured_provider())['available'],'generationMode':'persistent_jobs','catalogUrl':'/api/ai-bases','reason':'Requires released base/style profile, material authorization and verified GPU provider'}},'elementSelection':'elementCodes','scaleRange':[0.3,2.0],'transparentPng':True,'colorModes':['original','silhouette'],
                'renderers':{'default':'legacy','legacy':VERSION,'composition-v2':{'version':generator_v2.VERSION,'status':'owner_accepted_subset' if not settings.local_catalog else 'catalog_expanded','registryVersion':registry()['registryVersion'],'catalogUrl':'/api/composition-schemes','preflightUrl':'/api/composition-preflight','colorModes':['original'],'rapportOutputs':['module','sample'],'moduleSizeRange':[256,2048]},'composition-v1':{'version':COMPOSITION_VERSION,'status':'owner_accepted_pilot','visualReview':{'medallion':'accepted_with_density_controls_condition','rapport':'accepted','border':'accepted_contemporary_design'},'borderLayouts':['registers','interwoven'],'borderVisualReview':{'registers':'satisfactory_owner_reviewed','interwoven':'owner_accepted'},'pilotRecipes':review()[0]['families.json']['pilot_recipes'],'rapportOutputs':['module','sample'],'moduleSizeRange':[256,2048],'colorModes':['original']}},
                'compositionCatalog':{'acceptedSchemes':release_catalog(settings)['acceptedSchemeCount'],'acceptedCoveredElements':release_catalog(settings)['acceptedCoveredElementCount'],'url':'/api/composition-schemes','preflightUrl':'/api/composition-preflight','registryVersion':registry()['registryVersion']},
                'outputSizes':[[1024,1024],[900,1200],[800,1200],[720,1280]],'publicGuestMode':settings.public_guest_mode,'guest':{'sessionUrl':'/api/guest/session','preflightUrl':'/api/guest/preflight','createUrl':'/api/guest/generations','ttlSeconds':settings.guest_ttl_seconds},'profile':not settings.public_guest_mode,'trash':not settings.public_guest_mode,'compositions':['medallion','border','rapport'],'palettes':['emerald','porcelain','leather'],
                'styles':{'heritage':'Исходные цвета PNG; силуэт по отдельному выбору','modern':'Крупный одноцветный силуэт','porcelain-sign':'Синий контур','leather-mosaic':'Заливка и пунктирный шов','festive':'Чередующиеся цвета'},
                'parameters':['default','sparse','dense'],'usageSizes':{'architecture':[1024,1024],'textile':[1024,1024],'packaging':[1200,900],'interior':[1200,900],'web':[800,600]},
                'unsupported':['prompt-driven-generation','ai-editing','cancellation'], 'allowFixtures':settings.allow_fixtures}

    @app.get('/api/ai-bases')
    def ai_bases():
        return catalog_response(settings,configured_provider())

    @app.get('/api/ai-bases/{base_id}/preview')
    def ai_base_preview(base_id:str):
        return FileResponse(asset_file(find_base(base_id)),media_type='image/png')

    @app.post('/api/auth/register',status_code=201)
    def register(body:Registration,request:Request,response:Response,conn=Depends(db)):
        auth_limit(request)
        # Account identity is case-insensitive, including rows from legacy data.
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(body.email,))
        if conn.execute('SELECT 1 FROM users WHERE lower(email)=%s',(body.email,)).fetchone():
            raise APIError(409,'EMAIL_EXISTS','Этот email уже зарегистрирован.')
        try:
            row=conn.execute('INSERT INTO users(email,password_hash,profile) VALUES(%s,%s,%s) RETURNING id,email,profile',(body.email,hasher.hash(body.password),Jsonb(body.model_dump(exclude={'email','password'})))).fetchone()
        except psycopg.errors.UniqueViolation:
            conn.rollback()
            raise APIError(409,'EMAIL_EXISTS','Этот email уже зарегистрирован.')
        return issue_session(conn,row,response,request)

    @app.post('/api/auth/login')
    def login(body:Credentials,request:Request,response:Response,conn=Depends(db)):
        auth_limit(request)
        row=conn.execute('SELECT id,email,password_hash,profile FROM users WHERE NOT access_blocked AND lower(email)=%s ORDER BY id LIMIT 1',(body.email,)).fetchone()
        try:
            valid=hasher.verify(row['password_hash'] if row else dummy_hash,body.password)
        except (VerificationError,InvalidHashError):
            valid=False
        if not row or not valid:
            raise APIError(401,'INVALID_CREDENTIALS','Неверная почта или пароль.')
        if hasher.check_needs_rehash(row['password_hash']):
            conn.execute('UPDATE users SET password_hash=%s WHERE id=%s',(hasher.hash(body.password),row['id']))
        return issue_session(conn,row,response,request)

    @app.post('/api/auth/logout')
    def logout(request:Request,response:Response,conn=Depends(db)):
        token=request.cookies.get(COOKIE,'')
        conn.execute('DELETE FROM sessions WHERE token_hash=%s',(hashlib.sha256(token.encode()).hexdigest(),))
        conn.commit()
        response.delete_cookie(COOKIE,path='/api',secure=settings.cookie_secure,httponly=True,samesite='lax')
        return {'ok':True}

    @app.get('/api/auth/me')
    def me(user=Depends(current_user)):
        return {'user':user_json(user)}

    @app.patch('/api/auth/profile')
    def update_profile(body:Profile,user=Depends(current_user),conn=Depends(db)):
        row=conn.execute('UPDATE users SET profile=%s WHERE id=%s RETURNING id,email,profile',(Jsonb(body.model_dump()),user['id'])).fetchone()
        conn.commit()
        return {'user':user_json(row)}

    @app.get('/api/elements')
    def elements(conn=Depends(db)):
        rows=catalog(conn,settings)
        return {'items':[{'code':r['code'],'nameRu':r['name_ru'],'motifClass':r['motif_class'],'motifKey':r['motif_key'],'imageUrl':f"/api/elements/{r['code']}/file",'isFixture':r['is_fixture'],'sha256':r['content_sha256'],'artifactCode':r['artifact_code'],'sourceFrame':r['frame'],'motifIdentity':r['motif_identity'],'provenanceStatus':r['provenance'].get('evidenceStatus','legacy_verified'),'qualityAcceptance':r['quality_acceptance'],'compositionMetadata':metadata(r),'externalTransferAllowed':r['provenance'].get('externalTransferAllowed',False)} for r in rows], 'total':len(rows)}

    @app.get('/api/elements/{code}/file')
    def element_file(code:str,conn=Depends(db)):
        row=next((r for r in catalog(conn,settings,[code]) if r['code']==code),None)
        if row is None:
            raise APIError(404,'NOT_FOUND','Проверенный файл не найден.')
        return FileResponse(row['local_path'],media_type='image/png')

    @app.get('/api/projects')
    def projects(user=Depends(current_user),conn=Depends(db)):
        return {'items':[project_json(r) for r in conn.execute('SELECT * FROM projects WHERE user_id=%s ORDER BY created_at DESC,id DESC',(user['id'],)).fetchall()]}

    @app.post('/api/projects',status_code=201)
    def create_project(body:Project,user=Depends(current_user),conn=Depends(db)):
        row=conn.execute('INSERT INTO projects(user_id,title) VALUES(%s,%s) RETURNING *',(user['id'],body.title)).fetchone()
        conn.commit()
        return {'project':project_json(row)}

    @app.patch('/api/projects/{pid}')
    def rename_project(pid:ID,body:Project,user=Depends(current_user),conn=Depends(db)):
        owned_project(conn,pid,user['id'])
        row=conn.execute('UPDATE projects SET title=%s WHERE id=%s AND user_id=%s RETURNING *',(body.title,pid,user['id'])).fetchone()
        conn.commit()
        return {'project':project_json(row)}

    @app.delete('/api/projects/{pid}')
    def delete_project(pid:ID,user=Depends(current_user),conn=Depends(db)):
        owned_project(conn,pid,user['id'])
        conn.execute('DELETE FROM projects WHERE id=%s AND user_id=%s',(pid,user['id']))
        conn.commit()
        return {'ok':True}

    @app.get('/api/composition-schemes')
    def composition_schemes(conn=Depends(db)):
        available={r['code'] for r in catalog(conn,settings)}
        reg=release_catalog(settings)
        return {**reg,'availableElementCodes':sorted(available),'schemes':[
            {**scheme,'availableElementCodes':[c for c in scheme['allowedElementCodes'] if c in available],
             'available':set(scheme['defaultElementCodes']).issubset(available)} for scheme in reg['schemes']]}

    @app.get('/api/composition-schemes/{sid}/preview')
    def composition_preview(sid:str,conn=Depends(db)):
        scheme=next((s for s in release_catalog(settings)['schemes'] if s['id']==sid),None)
        if not scheme or not set(scheme['defaultElementCodes']).issubset({r['code'] for r in catalog(conn,settings,scheme['defaultElementCodes'])}):
            raise APIError(404,'NOT_FOUND','Пример схемы недоступен для текущего каталога.')
        path=ASSETS/(sid+'.png')
        if not path.is_file():
            raise APIError(503,'SCHEME_PREVIEW_UNAVAILABLE','Пример схемы ещё не подготовлен.')
        return FileResponse(path,media_type='image/png')

    def validate_renderer(selections):
        renderer=selections['renderer']
        if renderer=='composition-v2' and not settings.local_catalog and selections.get('schemeId') not in {s['id'] for s in release_catalog(settings)['schemes']}:
            raise APIError(422,'SCHEME_NOT_RELEASED','Схема пока не принята для публичной версии.')
        composed=renderer in ('composition-v1','composition-v2')
        if renderer!='composition-v2' and any(selections.get(k) is not None for k in ('schemeId','registryVersion','primaryElementCode')):
            raise APIError(422,'SCHEME_FIELDS_REQUIRE_V2','Выбор схемы требует renderer=composition-v2.')
        if not composed and (selections['moduleSize'] is not None or selections['rapportOutput']!='module'):
            raise APIError(422,'OUTPUT_REQUIRES_COMPOSITION_RENDERER','Поля модуля требуют композиционного renderer.')
        if composed and selections['composition']!='rapport' and (selections['moduleSize'] is not None or selections['rapportOutput']!='module'):
            raise APIError(422,'RAPPORT_FIELDS_ONLY','Поля модуля применимы только к rapport.')
        if selections['borderLayout']!='registers' and (renderer!='composition-v1' or selections['composition']!='border'):
            raise APIError(422,'BORDER_LAYOUT_REQUIRES_COMPOSITION','Чередование визуальных весов доступно только для composition-v1/border.')

    @app.post('/api/composition-preflight')
    def composition_preflight(body:Generate,user=Depends(current_user),conn=Depends(db)):
        if body.mode!='flat':
            raise APIError(422,'PREFLIGHT_REQUIRES_V2','Проверка схемы доступна для flat/composition-v2.')
        selections=body.selections.model_dump()
        validate_renderer(selections)
        if body.mode!='flat' or selections['renderer']!='composition-v2':
            raise APIError(422,'PREFLIGHT_REQUIRES_V2','Проверка схемы доступна для flat/composition-v2.')
        rows=selected_elements(conn,settings,selections['motifs'],selections['elementCodes'])
        if not render_slots.acquire(blocking=False):
            raise APIError(503,'GENERATOR_BUSY','Генератор занят. Повторите запрос позже.')
        try:
            return generator_v2.preflight(rows,selections,body.seed)
        finally:
            render_slots.release()

    @app.post('/api/generations',status_code=201)
    def generate(body:Generate,user=Depends(current_user),conn=Depends(db)):
        if body.projectId:
            owned_project(conn,body.projectId,user['id'])
        if body.mode=='ai':
            return {'generation':generation_json(enqueue_ai(conn,settings,user,body))}
        if not body.selections.elementCodes and not body.selections.motifs:
            raise APIError(422,'ELEMENTS_REQUIRED','Выберите элементы или классы мотивов.')
        rows=selected_elements(conn,settings,body.selections.motifs,body.selections.elementCodes)
        selections=body.selections.model_dump()
        validate_renderer(selections)
        use_pilot=selections['renderer']=='composition-v1'
        use_v2=selections['renderer']=='composition-v2'
        version=generator_v2.VERSION if use_v2 else COMPOSITION_VERSION if use_pilot else VERSION
        palette=conn.execute('SELECT colors FROM palettes WHERE code=%s',(body.selections.palette,)).fetchone()
        scheme=conn.execute('SELECT rules FROM composition_schemes WHERE code=%s',(body.selections.composition,)).fetchone()
        if not palette or not scheme:
            raise APIError(503,'PRESETS_MISSING','Примените миграцию 006 с палитрами и композициями.')
        if not render_slots.acquire(blocking=False):
            raise APIError(503,'GENERATOR_BUSY','Генератор занят. Повторите запрос позже.')
        relative=f"guest-results/{int(user['expires_at'].timestamp()*1000000)}-{uuid4().hex}.png" if user.get('guest_id') else f'results/{uuid4().hex}.png'
        png=safe_path(settings.storage_root,relative)
        jpg=png.with_suffix('.jpg')
        row=None
        try:
            row=conn.execute("INSERT INTO generations(user_id,project_id,status,params,user_prompt,model_version,guest_process_id,guest_expires_at,guest_request_id,guest_fingerprint) VALUES(%s,%s,'processing',%s,%s,%s,%s,%s,%s,%s) RETURNING *",(user['id'],body.projectId,Jsonb({'selections':body.selections.model_dump()}),body.prompt,version,*guest.metadata(user))).fetchone()
            if use_v2:
                recipe,warnings=generator_v2.render(rows,selections,palette['colors'],png,jpg,body.seed)
            elif use_pilot:
                recipe,warnings=render_composition(rows,selections,palette['colors'],png,jpg,body.seed)
            else:
                recipe,warnings=render(rows,selections,palette['colors'],scheme['rules'],png,jpg)
            recipe['seed']=body.seed
            recipe['selections']=selections
            recipe.setdefault('selectedElementCodes',selections['elementCodes'])
            recipe.setdefault('selectedMotifKeys',selections['motifs'])
            recipe.setdefault('usedElementCodes',[r['code'] for r in rows])
            recipe['description']=describe(recipe,selections)
            recipe['outputSha256']={'png':hashlib.sha256(png.read_bytes()).hexdigest(),'jpg':hashlib.sha256(jpg.read_bytes()).hexdigest()}
            if body.prompt.strip():
                warnings.append({'code':'PROMPT_UNSUPPORTED','message':'Текст сохранен, но алгоритмическая генерация не интерпретирует запросы словами.'})
            if recipe['isFixture']:
                warnings.append({'code':'TEST_FIXTURE','message':'Использованы синтетические тестовые элементы; это не рабочий каталог и не подтверждение 100+.'})
            params={'mode':'flat','seed':body.seed,'selections':body.selections.model_dump(),'recipe':recipe,'warnings':warnings}
            row=conn.execute("UPDATE generations SET status='done',progress=100,finished_at=now(),result_path=%s,params=%s WHERE id=%s RETURNING *",(relative,Jsonb(params),row['id'])).fetchone()
            if user.get('expires_at') and datetime.now(timezone.utc)>=user['expires_at']:
                raise APIError(410,'GUEST_RESULT_EXPIRED','Срок результата истёк.')
            conn.commit()
        except Exception as exc:
            logger.error('Generation failed (%s)',type(exc).__name__)
            conn.rollback()
            if user.get('guest_id'):
                from .erasure import enqueue_files
                enqueue_files(conn,relative);conn.commit()
            else:
                for path in (png,jpg,png.with_name(png.stem+'.module.png')):
                    path.unlink(missing_ok=True)
            if isinstance(exc,APIError):
                raise
            error={'code':'GENERATION_FAILED','message':'Не удалось создать файл результата. Проверьте каталог и хранилище.'}
            if user.get('guest_id'):
                raise APIError(503,error['code'],error['message'])
            conn.execute("INSERT INTO generations(user_id,project_id,status,params,user_prompt,model_version,error,finished_at) VALUES(%s,%s,'failed',%s,%s,%s,%s,now())",(user['id'],body.projectId,Jsonb({'selections':body.selections.model_dump()}),body.prompt,version,Jsonb(error)))
            conn.commit()
            raise APIError(503,error['code'],error['message'])
        finally:
            render_slots.release()
        return {'generation':generation_json(row)}

    @app.get('/api/generations')
    def history(trash:bool=False,projectId:Annotated[str|None,Query(pattern=r'^[1-9][0-9]{0,17}$')]=None,limit:Annotated[int,Query(ge=1,le=100)]=50,offset:Annotated[int,Query(ge=0)]=0,user=Depends(current_user),conn=Depends(db)):
        if projectId:
            owned_project(conn,projectId,user['id'])
        purge_trash(conn,user['id'])
        where='NOT EXISTS (SELECT 1 FROM erasure_tombstones t WHERE t.generation_id=generations.id) AND user_id=%s AND deleted_at IS ' + ('NOT NULL' if trash else 'NULL')
        args=[user['id']]
        if projectId:
            where+=' AND project_id=%s'
            args.append(projectId)
        total=conn.execute(f'SELECT count(*) AS n FROM generations WHERE {where}',args).fetchone()['n']
        rows=conn.execute(f'SELECT * FROM generations WHERE {where} ORDER BY created_at DESC,id DESC LIMIT %s OFFSET %s',args+[limit,offset]).fetchall()
        return {'items':[generation_json(r) for r in rows],'total':total}

    @app.delete('/api/generations/{gid}')
    def trash_generation(gid:ID,user=Depends(current_user),conn=Depends(db)):
        row=owned_generation(conn,gid,user['id'])
        if row['status'] in ('queued','processing'):
            raise APIError(409,'JOB_RUNNING','Дождитесь завершения генерации.')
        conn.execute('UPDATE generations SET deleted_at=COALESCE(deleted_at,now()) WHERE id=%s AND user_id=%s',(gid,user['id']))
        conn.commit()
        return {'ok':True}

    @app.post('/api/generations/{gid}/restore')
    def restore_generation(gid:ID,user=Depends(current_user),conn=Depends(db)):
        purge_trash(conn,user['id'])
        owned_generation(conn,gid,user['id'])
        row=conn.execute('UPDATE generations SET deleted_at=NULL WHERE id=%s AND user_id=%s RETURNING *',(gid,user['id'])).fetchone()
        conn.commit()
        return {'generation':generation_json(row)}

    @app.get('/api/generations/{gid}')
    def generation(gid:ID,user=Depends(current_user),conn=Depends(db)):
        return {'generation':generation_json(owned_generation(conn,gid,user['id']))}

    @app.patch('/api/generations/{gid}')
    def update_generation(gid:ID,body:PatchGeneration,user=Depends(current_user),conn=Depends(db)):
        owned_generation(conn,gid,user['id'])
        patch=body.model_dump(exclude_unset=True)
        if patch.get('projectId'):
            owned_project(conn,patch['projectId'],user['id'])
        mapping={'title':'title','rating':'rating','projectId':'project_id'}
        if patch:
            sets=','.join(f'{mapping[k]}=%s' for k in patch)
            conn.execute(f'UPDATE generations SET {sets} WHERE id=%s AND user_id=%s',list(patch.values())+[gid,user['id']])
            conn.commit()
        return {'generation':generation_json(owned_generation(conn,gid,user['id']))}

    @app.get('/api/generations/{gid}/file')
    def result_file(gid:ID,format:Literal['png','jpg']='png',artifact:Literal['output','module']='output',download:bool=False,user=Depends(current_user),conn=Depends(db)):
        row=owned_generation(conn,gid,user['id'])
        return file_response(row,gid,format,artifact,download)

    def file_response(row,gid,format,artifact,download):
        if row['status']!='done' or not row['result_path']:
            raise APIError(404,'FILE_NOT_FOUND','Файл результата отсутствует.')
        try:
            path=safe_path(settings.storage_root,row['result_path']).with_suffix('.'+format)
            if artifact=='module':
                repeat=((row['params'] or {}).get('recipe') or {}).get('repeat') or {}
                if format!='png' or not repeat.get('moduleSha256'):
                    raise APIError(404,'FILE_NOT_FOUND','Модуль PNG отсутствует в этом рецепте.')
                path=path.with_name(path.stem+'.module.png')
        except ValueError:
            raise APIError(404,'FILE_NOT_FOUND','Файл результата отсутствует.')
        if not path.is_file():
            raise APIError(404,'FILE_NOT_FOUND','Файл результата отсутствует.')
        return FileResponse(path,media_type='image/png' if format=='png' else 'image/jpeg',filename=f'tatar-pattern-{gid}{"-module" if artifact=="module" else ""}.{format}',content_disposition_type='attachment' if download else 'inline')

    def guest_access(request:Request,conn=Depends(db)):
        token=request.cookies.get(guest.COOKIE,'')
        if len(token)!=43:
            raise APIError(401,'GUEST_ACCESS_REQUIRED','Начните временный гостевой процесс.')
        row=conn.execute('SELECT * FROM guest_processes WHERE token_hash=%s AND expires_at>clock_timestamp()', (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not row:
            raise APIError(401,'GUEST_ACCESS_EXPIRED','Временный доступ недействителен или истёк.')
        return {'id':None,'guest_id':row['id'],'expires_at':row['expires_at']}

    def guest_owned(conn,gid,access):
        row=conn.execute('SELECT * FROM generations WHERE id=%s AND guest_process_id=%s AND guest_expires_at>clock_timestamp() AND deleted_at IS NULL',(gid,access['guest_id'])).fetchone()
        if not row:
            raise APIError(404,'NOT_FOUND','Временный результат недоступен.')
        return row

    def guest_json(row):
        value=generation_json(row)
        for key in ('title','rating','projectId','prompt','deletedAt'):
            value.pop(key,None)
        for key in ('imageUrl','moduleUrl'):
            if value.get(key):value[key]=value[key].replace('/api/generations/','/api/guest/generations/')
        value['requestId']=str(row['guest_request_id'])
        value['expiresAt']=row['guest_expires_at'].isoformat()
        return value

    @app.post('/api/guest/session')
    def guest_session(body:GuestSession,request:Request,response:Response,conn=Depends(db)):
        auth_limit(request)
        token=request.cookies.get(guest.COOKIE,'')
        prior=conn.execute('SELECT * FROM guest_processes WHERE token_hash=%s AND expires_at>clock_timestamp()', (hashlib.sha256(token.encode()).hexdigest(),)).fetchone() if len(token)==43 else None
        if prior:
            return {'expiresAt':prior['expires_at'].isoformat()}
        conn.execute('SELECT pg_advisory_xact_lock(%s)',(guest.ADMISSION_LOCK,))
        key='minute:'+str(int(datetime.now(timezone.utc).timestamp())//60)
        count=conn.execute('INSERT INTO guest_budget(key,used) VALUES(%s,1) ON CONFLICT(key) DO UPDATE SET used=guest_budget.used+1 RETURNING used',(key,)).fetchone()['used']
        if count>settings.guest_creates_per_minute:
            raise APIError(429,'GUEST_RATE_LIMIT','Слишком много запросов. Повторите позже.')
        created=datetime.now(timezone.utc)
        expires=created+timedelta(seconds=settings.guest_ttl_seconds)
        token=secrets.token_urlsafe(32)
        conn.execute('INSERT INTO guest_processes(id,token_hash,created_at,expires_at) VALUES(%s,%s,%s,%s)',(uuid4(),hashlib.sha256(token.encode()).hexdigest(),created,expires))
        conn.commit()
        response.set_cookie(guest.COOKIE,token,max_age=settings.guest_ttl_seconds,expires=expires,httponly=True,secure=settings.cookie_secure,samesite='strict',path='/api/guest')
        return {'expiresAt':expires.isoformat()}

    @app.post('/api/guest/preflight')
    def guest_preflight(body:GuestGenerate,request:Request,access=Depends(guest_access),conn=Depends(db)):
        auth_limit(request)
        if body.mode=='ai':
            from .ai_catalog import select_profile,unavailable_reasons
            base,profile=select_profile(body.ai.baseId,body.ai.ornamentStyle,body.ai.profileVersion)
            reasons=unavailable_reasons(base,profile,configured_provider(),settings)
            if reasons:raise APIError(503,'AI_UNAVAILABLE','AI-сочетание пока недоступно.',{'reasons':reasons})
            used=conn.execute("SELECT used FROM guest_budget WHERE key='gpu-total'").fetchone()
            if (used['used'] if used else 0)>=settings.guest_gpu_budget:
                raise APIError(503,'AI_BUDGET_EXHAUSTED','Лимит AI исчерпан.')
            return {'available':True,'expiresAt':access['expires_at'].isoformat()}
        return {**composition_preflight(body.internal(),access,conn),'expiresAt':access['expires_at'].isoformat()}

    @app.post('/api/guest/generations',status_code=201)
    def guest_create(body:GuestGenerate,request:Request,access=Depends(guest_access),conn=Depends(db)):
        auth_limit(request)
        conn.execute('SELECT pg_advisory_xact_lock(%s)',(guest.ADMISSION_LOCK,))
        prior=conn.execute('SELECT * FROM generations WHERE guest_process_id=%s AND guest_request_id=%s',(access['guest_id'],body.requestId)).fetchone()
        digest=guest.fingerprint(body)
        if prior:
            if prior['guest_fingerprint']!=digest:
                raise APIError(409,'IDEMPOTENCY_CONFLICT','requestId уже использован с другими параметрами.')
            return {'generation':guest_json(guest_owned(conn,prior['id'],access))}
        guest.admit(conn,settings,access)
        internal={**access,'request_id':body.requestId,'fingerprint':digest}
        result=generate(body.internal(),internal,conn)
        row=guest_owned(conn,result['generation']['id'],access)
        return {'generation':guest_json(row)}

    @app.get('/api/guest/generations/{gid}')
    def guest_status(gid:ID,access=Depends(guest_access),conn=Depends(db)):
        return {'generation':guest_json(guest_owned(conn,gid,access))}

    @app.get('/api/guest/generations/{gid}/file')
    def guest_file(gid:ID,format:Literal['png','jpg']='png',artifact:Literal['output','module']='output',download:bool=False,access=Depends(guest_access),conn=Depends(db)):
        return file_response(guest_owned(conn,gid,access),gid,format,artifact,download)

    if settings.public_guest_mode:
        app.router.routes[:]=[route for route in app.router.routes if not (getattr(route,'path','').startswith(('/api/auth/','/api/projects','/api/generations')) or getattr(route,'path','')=='/api/composition-preflight')]
    return app
