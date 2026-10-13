"""Read-only, hash-bound snapshot of the dataset review. No DB attribution upgrade."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from .errors import APIError

DATA = Path(__file__).with_name('composition-data')

@lru_cache(maxsize=1)
def review():
    lock = json.loads((DATA/'lock.json').read_text())
    documents = {}
    for name, digest in lock.items():
        raw = (DATA/name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise APIError(503, 'REVIEW_SNAPSHOT_CHANGED', 'SHA пакета ревизии не совпадает с закреплённой версией.')
        documents[name] = json.loads(raw)
    return documents, lock


def metadata(row):
    documents, _ = review()
    item = next((i for i in documents['metadata.json']['items'] if i['code'] == row['code']), None)
    if item is None:
        return None
    if item['flat_sha256'] != row['content_sha256']:
        raise APIError(422, 'REVIEW_ASSET_MISMATCH', 'Ревизия относится к другой версии PNG.', {'elementCodes':[row['code']]})
    return item


def pilot_for(rows, composition):
    documents, _ = review()
    codes = {r['code'] for r in rows}
    pilot = next((p for p in documents['families.json']['pilot_recipes'] if p['composition'] == composition and set(p['codes']) == codes), None)
    if not pilot:
        diagnostics = []
        for row in rows:
            item = metadata(row)
            usage = item['usage'].get(composition, {}) if item else {}
            diagnostics.append({'code':row['code'], 'state':usage.get('state','unknown'), 'reason':usage.get('reason','Нет метаданных для данной роли.')})
        raise APIError(422, 'COMPOSITION_SELECTION_UNSUPPORTED', 'Пилот поддерживает только явные тройки ролей; выбранные элементы сохранены в запросе и не заменены.',
                       {'selectedElementCodes':[r['code'] for r in rows], 'diagnostics':diagnostics,
                        'alternatives':[p for p in documents['families.json']['pilot_recipes'] if p['composition'] == composition], 'requiresExplicitSelection':True})
    for row in rows:
        item = metadata(row)
        if item['usage'][composition]['state'] != 'ready_with_transform':
            raise APIError(422, 'COMPOSITION_USE_UNSUPPORTED', 'Элемент не готов для этой схемы.', {'code':row['code'], 'usage':item['usage'][composition]})
    return pilot


def compatibility(rows, composition):
    documents, lock = review()
    items = [metadata(r) for r in rows]
    codes = {r['code'] for r in rows}
    reasons = [{'code':'CULTURAL_PAIR_UNKNOWN','severity':'unknown','scope':'cultural', 'evidence':['RULE-05'],
                'message':'Культурная совместимость новой композиции не подтверждена; схема является современным дизайнерским предложением.'}]
    for rule in documents['compatibility-rules.json']['rules']:
        matched = codes.intersection(rule.get('codes', []))
        if len(matched) >= 2:
            reasons.append({'code':rule['id'], 'severity':rule['severity'], 'scope':rule['scope'], 'evidence':[rule['basis']], 'message':rule['reason']})
    return {'status':'supported_pilot', 'geometry':'checked_for_saved_layout', 'aesthetic':'designer_proposal', 'cultural':'unknown',
            'metadataVersion':documents['metadata.json']['schema_version'], 'snapshotSha256':lock,
            'reasons':reasons, 'items':[{'code':r['code'], 'usage':i['usage'][composition], 'orientation':i['orientation'],
                                       'attachment':i['attachment'], 'readability':i['readability']} for r,i in zip(rows,items)]}
