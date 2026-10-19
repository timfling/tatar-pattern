"""Versioned, data driven design schemes bound to the immutable 110-item review."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from .composition_metadata import review, metadata
from .errors import APIError

SCHEMA='tp-composition-catalog/2.0.0'
VERSION='tp-schemes/2.1.0'
ASSETS=Path(__file__).resolve().parent/'composition-assets/v2'
ROLE_LABELS={'center':'Центр','primary':'Главный мотив','support':'Вспомогательный мотив','branch':'Направленная ветвь','leaf':'Листовой акцент','frame':'Рамочный фрагмент','pendant':'Подвесная форма'}
TEMPLATES={
 'directed':{'composition':'border','scope':'border','title':'Направленный ритм','layout':'directed_cadence'},
 'repeat':{'composition':'rapport','scope':'rapport','title':'Иерархический повтор','layout':'hierarchical_repeat'},
 'wreath':{'composition':'medallion','scope':'medallion','title':'Центр и обрамление','layout':'center_wreath'},
 'panel':{'composition':'medallion','scope':'medallion','title':'Геометрическое поле','layout':'framed_panel'},
 'hanging':{'composition':'border','scope':'hanging_border','title':'Подвесные формы','layout':'hanging_panel'},
}

@lru_cache(maxsize=1)
def registry():
    docs,lock=review();items={i['code']:i for i in docs['metadata.json']['items']};families=[];schemes=[]
    designs=json.loads((Path(__file__).parent/'scheme-data/designs.json').read_text())
    for family in docs['families.json']['families']:
        family_id=family['id'];members=family['members']
        subgroups={}
        for c in members:subgroups.setdefault(items[c]['cultural_attribution']['artifact_code'],[]).append(c)
        families.append({'id':family_id,'titleRu':family['title_ru'],'elementCodes':members,'subgroups':[{'artifactCode':k,'elementCodes':v} for k,v in subgroups.items()],
                         'basis':family['basis'],'mixingPolicy':family['mixing_policy'],'evidence':family['basis'].get('cultural_principle_evidence',[])})
        for key,template in TEMPLATES.items():
            allowed=[c for c in members if items[c]['usage'].get(template['scope'],{}).get('state')=='ready_with_transform']
            if key=='panel':allowed=[c for c in allowed if 'geometric_module' in items[c]['roles']]
            if key=='wreath':
                allowed=[c for c in allowed if not set(items[c]['roles']).intersection({'border_segment','hanging_accent','vertical_panel','corner_accent','directed_branch'})]
                centers=[c for c in allowed if 'medallion_center' in items[c]['roles']]
                if not centers:continue
            if not allowed:continue
            # Same-object defaults preserve source affinity. Every allowed member
            # remains manually selectable; omitted defaults are never a hidden filter.
            groups={}
            for c in allowed:groups.setdefault(items[c]['cultural_attribution']['artifact_code'],[]).append(c)
            preferred=max(groups.values(),key=lambda g:(len(g),-members.index(g[0])))
            defaults=preferred[:4]
            if key=='wreath':
                center=centers[0];companions=groups[items[center]['cultural_attribution']['artifact_code']];defaults=[center]+[c for c in companions if c!=center][:3]
            sid=f'{family_id.lower()}-{key}'
            schemes.append({'id':sid,'registryVersion':VERSION,'familyId':family_id,'composition':template['composition'],'layout':template['layout'],'useScope':template['scope'],
                            'titleRu':family['title_ru']+' · '+template['title'],'descriptionRu':'Современная композиционная схема по ролям и метаданным ревизии.',
                            'allowedElementCodes':allowed,'defaultElementCodes':defaults,'minimumSelected':1,'maximumSelected':16,
                            'requiredRoles':['center'] if key=='wreath' else [],'centerCandidates':centers if key=='wreath' else [],
                            'roleOptions':{c:role_options(items[c],key) for c in allowed},
                            'constraints':{'colorModes':['original'],'reflection':False,'continuousJoinedRepeat':False,'minimumSizeBasis':'recommended_not_empirically_verified'},
                            'previewUrl':f'/api/composition-schemes/{sid}/preview','previewIsExample':True,
                            'reviewStatus':'designer_proposal_owner_not_individually_reviewed','evidence':['D01']+family['basis'].get('cultural_principle_evidence',[])})
    for scheme in schemes:
        sid=scheme['id']
        if sid in designs['profiles']:
            design=designs['profiles'][sid]
            scheme['design']=design
            scheme['defaultElementCodes']=design.get('defaultElementCodes',scheme['defaultElementCodes'])
            scheme['reviewStatus']=design['status']
            scheme['descriptionRu']=design['intentRu']
            scheme['applicationRu']=design['applicationRu']
            scheme['previewKind']='repeat_field' if scheme['composition']=='rapport' else 'visible_band'
            scheme['previewDescriptionRu']='Обзорное окно повторяемого поля1200×900; края обзора могут быть некратны модулю' if scheme['composition']=='rapport' else 'Обзор рабочей области полосы; полный PNG сохраняет поля'
        elif sid in designs['ownerAccepted']:
            scheme['reviewStatus']='owner_accepted_2026_10_13'
    coverage={c:[s['id'] for s in schemes if c in s['allowedElementCodes']] for c in items}
    if any(not ids for ids in coverage.values()):raise RuntimeError('Scheme registry does not cover every accepted item')
    fingerprint=hashlib.sha256(json.dumps({'families':families,'schemes':schemes,'review':lock},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return {'schemaVersion':SCHEMA,'registryVersion':VERSION,'sha256':fingerprint,'metadataVersion':docs['metadata.json']['schema_version'],
            'roleLabelsRu':ROLE_LABELS,'families':families,'schemes':schemes,'coverage':coverage,'totalElements':len(items),'totalFamilies':len(families),'totalSchemes':len(schemes)}


def role_options(item,key):
    roles=item['roles']
    if key=='hanging':return ['pendant']
    out=[]
    if key=='wreath' and 'medallion_center' in roles:out.append('center')
    if 'border_segment' in roles or key=='wreath' and 'framing_pair' in roles:out.append('frame')
    elif 'directed_branch' in roles:out.append('branch')
    elif 'supporting_leaf' in roles or 'supporting_foliage' in roles:out.append('leaf')
    else:out.append('support')
    if key!='wreath':out.insert(0,'primary')
    return out


def resolve(rows,selections):
    reg=registry();sid=selections.get('schemeId')
    if selections.get('registryVersion') not in (None,VERSION):
        raise APIError(409,'SCHEME_REGISTRY_CHANGED','Версия схем изменилась; обновите список и проверьте выбор.',{'expected':VERSION,'requested':selections['registryVersion']})
    scheme=next((s for s in reg['schemes'] if s['id']==sid),None)
    if scheme is None:
        raise APIError(422,'SCHEME_REQUIRED','Выберите доступную согласованную схему.',{'schemeId':sid,'availableSchemeIds':[s['id'] for s in reg['schemes'] if s['composition']==selections['composition']]})
    if scheme['composition']!=selections['composition']:
        raise APIError(422,'SCHEME_COMPOSITION_MISMATCH','Тип композиции не соответствует выбранной схеме.',{'schemeId':sid,'composition':scheme['composition']})
    rejected=[]
    for row in rows:
        item=metadata(row)
        if row['code'] not in scheme['allowedElementCodes']:
            rejected.append({'code':row['code'],'familyId':item['compatibility']['family_id'] if item else None,'usage':item['usage'].get(scheme['useScope']) if item else None,
                             'reason':'Элемент не поддерживается в этой роли/семействе данной схемы; это не универсальный культурный запрет.'})
    if rejected:
        raise APIError(422,'SCHEME_ELEMENTS_UNSUPPORTED','Выбор не изменён: есть элементы, не поддерживаемые этой схемой.',{'schemeId':sid,'selectedElementCodes':[r['code'] for r in rows],'diagnostics':rejected,'alternatives':{r['code']:reg['coverage'].get(r['code'],[]) for r in rows},'requiresExplicitSelection':True})
    if not rows:raise APIError(422,'ELEMENTS_REQUIRED','Выберите хотя бы один элемент; набор схемы не применяется скрыто.')
    if not scheme['minimumSelected'] <= len(rows) <= scheme['maximumSelected']:
        raise APIError(422,'SCHEME_SELECTION_COUNT','Выберите от 1 до 16 элементов.')
    requested_primary=selections.get('primaryElementCode')
    codes={r['code'] for r in rows}
    if requested_primary and requested_primary not in codes:
        raise APIError(422,'PRIMARY_NOT_SELECTED','Главный элемент должен присутствовать в выбранном наборе.',{'primaryElementCode':requested_primary,'selectedElementCodes':sorted(codes)})
    if scheme['layout']=='center_wreath':
        candidates=[r for r in rows if r['code'] in scheme['centerCandidates']]
        if not candidates or requested_primary and requested_primary not in scheme['centerCandidates']:
            raise APIError(422,'CENTER_ROLE_REQUIRED','Для венка выберите элемент, рекомендованный как центр.',{'centerCandidates':scheme['centerCandidates'],'selectedElementCodes':sorted(codes)})
    else:candidates=rows
    def priority(row):
        item=metadata(row);roles=item['roles']
        preferred=any(r in roles for r in ['medallion_center','primary_flower','geometric_module','primary_repeat'])
        return (preferred,item['readability']['recommended_min_long_side_px'],row['code'])
    preferred_primary=scheme.get('design',{}).get('defaultPrimaryElementCode')
    primary=next((r for r in candidates if r['code']==requested_primary),None) or next((r for r in candidates if r['code']==preferred_primary),None) or max(candidates,key=priority)
    assignments={r['code']:('center' if scheme['layout']=='center_wreath' else 'pendant' if scheme['layout']=='hanging_panel' else 'primary') if r['code']==primary['code'] else next((role for role in scheme['roleOptions'][r['code']] if role not in ['center','primary']),'support') for r in rows}
    if scheme['layout']=='hanging_panel':assignments={r['code']:'pendant' for r in rows}
    reasons=[{'code':'CONTEMPORARY_LAYOUT','severity':'unknown','scope':'cultural','evidence':['D01','RULE-05'],'message':'Расстановка современная; культурная валидность новой пары и символика не подтверждены.'}]
    if len({r['artifact_code'] for r in rows})>1:
        reasons.append({'code':'MULTIPLE_SOURCE_OBJECTS','severity':'recommendation','scope':'aesthetic','evidence':['RULE-02'],'message':'В наборе мотивы разных предметов; единство цвета и детализации нужно оценить на результате.'})
    for rule in review()[0]['compatibility-rules.json']['rules']:
        if len(codes.intersection(rule.get('codes',[])))>=2:
            reasons.append({'code':rule['id'],'severity':rule['severity'],'scope':rule['scope'],'evidence':[rule['basis']], 'message':rule['reason']})
    return scheme,assignments,primary['code'],reasons


def release_catalog(settings):
    """Existing catalog shape, restricted public subset; local proposals remain inspectable."""
    reg=registry()
    accepted=[s for s in reg['schemes'] if s['reviewStatus']=='owner_accepted_2026_10_13']
    covered=sorted({c for s in accepted for c in s['allowedElementCodes']})
    schemes=reg['schemes'] if settings.local_catalog else accepted
    coverage={c:[s['id'] for s in schemes if c in s['allowedElementCodes']] for c in reg['coverage']}
    return {**reg,'schemes':schemes,'coverage':coverage,'totalSchemes':len(schemes),
            'registeredSchemeCount':len(reg['schemes']),'acceptedSchemeCount':len(accepted),
            'acceptedCoveredElementCount':len(covered),'acceptedCoveredElementCodes':covered,
            'elementsWithoutAcceptedScheme':sorted(set(reg['coverage'])-set(covered))}
