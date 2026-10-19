"""Registered immutable whole-composition inputs. No prompt from the browser."""
import hashlib
import json
from pathlib import Path
from .errors import APIError

ASSETS=Path(__file__).with_name('ai-assets')
PROFILES=Path(__file__).with_name('ai-profiles.json')
STYLES={'graphic':'Графический стиль','textured':'Фактурный стиль'}
TASK_SCHEMA='tp-ai-task/1.0'


def document():
    return json.loads((ASSETS/'index.json').read_text())


def asset_file(base,kind='image'):
    path=(ASSETS/base[kind]).resolve()
    if not path.is_relative_to(ASSETS.resolve()) or not path.is_file():
        raise APIError(503,'AI_ASSET_UNAVAILABLE','Файл основы недоступен.')
    expected=base['sha256' if kind=='image' else 'recipeSha256']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        raise APIError(503,'AI_ASSET_CHANGED','SHA основы или recipe изменился.')
    return path


def find_base(base_id):
    base=next((b for b in document()['bases'] if b['id']==base_id),None)
    if base is None:raise APIError(422,'AI_BASE_UNKNOWN','Неизвестная композиционная основа.')
    return base


def profiles():return json.loads(PROFILES.read_text())['profiles']


def select_profile(base_id,style,version):
    base=find_base(base_id)
    profile=next((p for p in profiles() if p['baseId']==base_id and p['ornamentStyle']==style),None)
    if profile is None:raise APIError(422,'AI_COMBINATION_UNAVAILABLE','Сочетание основы и оформления ещё не проверено.')
    if profile['version']!=version:raise APIError(409,'AI_PROFILE_CHANGED','Профиль изменился; обновите каталог.',{'expected':profile['version']})
    asset_file(base);asset_file(base,'recipe')
    if profile['baseSha256']!=base['sha256']:raise APIError(503,'AI_PROFILE_ASSET_MISMATCH','Профиль относится к другой версии основы.')
    return base,profile


def unavailable_reasons(base,profile,provider,settings):
    reasons=[]
    if not settings.ai_mvp_enabled:reasons.append('AI_DISABLED')
    if provider is None or not getattr(provider,'ready',False) or getattr(provider,'contract_version',None)!=TASK_SCHEMA:
        reasons.append('AI_PROVIDER_UNVERIFIED')
    if provider is not None and hasattr(provider,'ready_for') and not provider.ready_for(base,profile):
        reasons.append('AI_GPU_PAIR_UNVERIFIED')
    if profile is None or not profile.get('releaseApproved'):reasons.append('AI_PROFILE_NOT_RELEASED')
    if profile and profile.get('qualityStatus') in ('owner_rejected_cloud_2026_10_19','excluded_from_cloud_qualification'):reasons.append('AI_PAIR_NOT_ACCEPTED')
    if not base.get('externalTransferApproved',False):reasons.append('MATERIAL_TRANSFER_NOT_AUTHORIZED')
    return reasons


def catalog_response(settings,provider):
    doc=document();configured=profiles();bases=[]
    for base in doc['bases']:
        styles=[]
        try:asset_file(base);asset_file(base,'recipe');integrity=True
        except APIError:integrity=False
        for style,label in STYLES.items():
            p=next((p for p in configured if p['baseId']==base['id'] and p['ornamentStyle']==style),None)
            reasons=unavailable_reasons(base,p,provider,settings)
            if not integrity:reasons.append('AI_ASSET_UNAVAILABLE')
            if p and p['baseSha256']!=base['sha256']:reasons.append('AI_PROFILE_ASSET_MISMATCH')
            styles.append({'id':style,'labelRu':label,'profileVersion':p['version'] if p else None,'qualityStatus':p['qualityStatus'] if p else 'pending_artistic_tests','available':not reasons,'unavailableReasons':reasons})
        bases.append({**{k:v for k,v in base.items() if k not in ('image','recipe')},'previewUrl':f"/api/ai-bases/{base['id']}/preview",'styles':styles})
    return {'schemaVersion':doc['schemaVersion'],'catalogVersion':doc['catalogVersion'],'palettePolicy':'source','freePrompt':False,'outputSize':[1024,1024],'bases':bases,'available':any(s['available'] for b in bases for s in b['styles'])}


def task_payload(base,profile,seed):
    """Internal queue contract, not an invented GPU HTTP payload."""
    return {'schemaVersion':TASK_SCHEMA,'baseId':base['id'],'inputArtifact':{'sha256':base['sha256'],'size':[1024,1024],'mode':'RGB'},'ornamentStyle':profile['ornamentStyle'],'profileVersion':profile['version'],'profile':profile,'seed':seed,'palette':base['palette'],'output':{'format':'png','size':[1024,1024],'background':True,'seamless':False}}


def validate_task(payload):
    if payload.get('schemaVersion')!=TASK_SCHEMA:raise APIError(422,'AI_TASK_VERSION_UNAVAILABLE','Нужен отдельный адаптер старой задачи.')
    try:
        profile=payload['profile']
        valid=(payload['ornamentStyle'] in STYLES and isinstance(payload['seed'],int)
               and not isinstance(payload['seed'],bool) and 0<=payload['seed']<=2147483647
               and payload['inputArtifact']['size']==[1024,1024]
               and payload['inputArtifact']['mode']=='RGB'
               and profile['baseId']==payload['baseId']
               and profile['ornamentStyle']==payload['ornamentStyle']
               and profile['version']==payload['profileVersion'])
    except (KeyError,TypeError):valid=False
    if not valid:raise APIError(422,'AI_TASK_INVALID','Сохранённая задача не соответствует внутреннему контракту.')
    base=find_base(payload['baseId']);asset_file(base);asset_file(base,'recipe')
    if base['sha256']!=payload['inputArtifact']['sha256'] or payload['profile']['baseSha256']!=base['sha256']:
        raise APIError(422,'AI_ASSET_CHANGED','Сохранённая задача относится к другой основе.')
    # The queued profile is immutable; never replace it with the current registry.
    return base
