"""Persist requests, deduplicate user retries, never silently fall back to flat."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from psycopg.types.json import Jsonb
from .ai_provider import configured_provider
from .ai_catalog import select_profile, unavailable_reasons, task_payload
from .errors import APIError
from . import guest


def enqueue_ai(conn,settings,user,body):
    intent={'ai':body.ai.model_dump(),'seed':body.seed,'projectId':body.projectId}
    fingerprint=hashlib.sha256(json.dumps(intent,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    request_id=str(body.requestId)
    # Same durable lock as queue capacity: concurrent identical retries cannot submit twice.
    conn.execute('SELECT pg_advisory_xact_lock(107198010)')
    prior=None if user.get("guest_id") else conn.execute("SELECT * FROM generations WHERE user_id=%s AND params->>'clientRequestId'=%s ORDER BY id LIMIT 1",(user['id'],request_id)).fetchone()
    if prior:
        if prior['params'].get('requestFingerprint')!=fingerprint:
            raise APIError(409,'AI_IDEMPOTENCY_CONFLICT','requestId уже использован для другого запроса.')
        conn.commit()
        return prior
    base,profile=select_profile(body.ai.baseId,body.ai.ornamentStyle,body.ai.profileVersion)
    provider=configured_provider()
    reasons=unavailable_reasons(base,profile,provider,settings)
    if reasons:
        raise APIError(503,'AI_UNAVAILABLE','AI-сочетание пока недоступно.',{'reasons':reasons})
    if conn.execute("SELECT count(*) AS n FROM ai_jobs WHERE state IN ('queued','submitting','polling')").fetchone()['n']>=20:
        raise APIError(503,'AI_QUEUE_FULL','Очередь ИИ заполнена. Повторите позже.')
    if user.get('guest_id'):guest.charge_gpu(conn,settings)
    payload=task_payload(base,profile,body.seed)
    # Snapshot is independent of future catalogue/profile edits and provider readiness.
    recipe={'schemaVersion':'tp-ai-composition-recipe/1.0','provider':provider.name,'modelVersion':provider.model_version,'seed':body.seed,'input':payload,'base':base,'profile':profile,'outputKind':'ai_image','seamless':False,'requestedElementCodes':base['elementCodes'],'usedElementCodes':None,
            'description':{'text':f"Декоративный вариант основы «{base['titleRu']}». Оформление: {'Графический стиль' if body.ai.ornamentStyle=='graphic' else 'Фактурный стиль'}. Состав и геометрия AI-результата отдельно не проверены.",'basis':'requested_only','claimType':'request','schemaVersion':'tp-description-schema/1.0.0','templateVersion':'tp-ai-description/1.0','facts':{'requested':{'baseId':base['id'],'elementCodes':base['elementCodes'],'ornamentStyle':body.ai.ornamentStyle,'profileVersion':profile['version']},'observed':None,'verified':None},'evidence':[],'culturalNote':None}}
    params={'mode':'ai','seed':body.seed,'ai':body.ai.model_dump(),'clientRequestId':request_id,'requestFingerprint':fingerprint,'recipe':recipe,'warnings':[]}
    row=conn.execute("INSERT INTO generations(user_id,project_id,status,params,user_prompt,model_version,progress,guest_process_id,guest_expires_at,guest_request_id,guest_fingerprint) VALUES(%s,%s,'queued',%s,'',%s,NULL,%s,%s,%s,%s) RETURNING *",(user['id'],body.projectId,Jsonb(params),provider.model_version,*guest.metadata(user))).fetchone()
    conn.execute("INSERT INTO ai_jobs(generation_id,state,provider,model_version,payload,deadline) VALUES(%s,'queued',%s,%s,%s,%s)",(row['id'],provider.name,provider.model_version,Jsonb(payload),datetime.now(timezone.utc)+timedelta(minutes=15)))
    conn.commit()
    return row
