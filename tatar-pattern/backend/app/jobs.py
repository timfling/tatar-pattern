"""Persist AI requests before returning; a separate worker owns GPU polling."""
from datetime import datetime, timedelta, timezone
from psycopg.types.json import Jsonb
from .ai_provider import configured_provider
from .catalog import selected_elements
from .errors import APIError
from .descriptions import describe


def enqueue_ai(conn,settings,user,body):
    provider=configured_provider()
    if provider is None:
        raise APIError(503,'AI_PROVIDER_UNCONFIGURED','Нужны подтвержденная спецификация DSLab, модель и серверный доступ.')
    rows=selected_elements(conn,settings,body.selections.motifs,body.selections.elementCodes)
    blocked=[r['code'] for r in rows if not r['provenance'].get('externalTransferAllowed')]
    if blocked:
        raise APIError(422,'MATERIAL_TRANSFER_NOT_AUTHORIZED','Не подтверждена передача выбранных материалов во внешний ИИ.',{'elementCodes':blocked})
    # Model compatibility and specific allowed asset serialization belong to the
    # factual provider adapter. These are references, never emails/session data.
    payload={'prompt':body.prompt,'seed':body.seed,'selections':body.selections.model_dump(),'elements':[{'code':r['code'],'sha256':r['content_sha256']} for r in rows]}
    params={'mode':'ai','seed':body.seed,'selections':body.selections.model_dump(),'recipe':{'provider':provider.name,'modelVersion':provider.model_version,'seed':body.seed,'input':payload},'warnings':[]}
    params['recipe'].update(outputKind='ai_image',seamless=None,selectedElementCodes=body.selections.elementCodes,selectedMotifKeys=body.selections.motifs,requestedElementCodes=[r['code'] for r in rows],usedElementCodes=None)
    params['recipe']['description']=describe(params['recipe'],params['selections'],mode='ai')
    conn.execute('SELECT pg_advisory_xact_lock(107198010)')
    if conn.execute("SELECT count(*) AS n FROM ai_jobs WHERE state IN ('queued','submitting','polling')").fetchone()['n']>=20:
        raise APIError(503,'AI_QUEUE_FULL','Очередь ИИ заполнена. Повторите позже.')
    row=conn.execute("INSERT INTO generations(user_id,project_id,status,params,user_prompt,model_version,progress) VALUES(%s,%s,'queued',%s,%s,%s,NULL) RETURNING *",(user['id'],body.projectId,Jsonb(params),body.prompt,provider.model_version)).fetchone()
    conn.execute("INSERT INTO ai_jobs(generation_id,state,provider,model_version,payload,deadline) VALUES(%s,'queued',%s,%s,%s,%s)",(row['id'],provider.name,provider.model_version,Jsonb(payload),datetime.now(timezone.utc)+timedelta(minutes=15)))
    conn.commit()
    return {'generation':{'id':str(row['id']),'status':'queued','mode':'ai','progress':None,'imageUrl':None,'modelVersion':provider.model_version,'seed':body.seed,'recipe':params['recipe'],'createdAt':row['created_at'].isoformat(),'selections':params['selections'],'prompt':body.prompt,'projectId':body.projectId,'description':params['recipe']['description']['text'],'descriptionDetails':params['recipe']['description'],'culturalNote':None,'outputKind':'ai_image','seamless':None,'compatibility':{'status':'not_evaluated','cultural':'unknown'},'repeat':None,'moduleUrl':None,'warnings':[],'error':None}}
