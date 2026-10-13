"""Version 2: owner visual acceptance + documented, unverified source evidence.

All protected masters are read only. This grants local constructor use only.
"""
import hashlib
import json
from pathlib import Path
from psycopg.types.json import Jsonb
from app.catalog import inspect_png, safe_path


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def validate(manifest,root):
    raw=manifest.read_bytes(); data=json.loads(raw); errors=[]; duplicates=[]; hashes={}
    def error(label,condition):
        if not condition: errors.append(label)
    def text(obj,key): return isinstance(obj.get(key),str) and bool(obj[key].strip())
    error('version must be 2',data.get('version')==2)
    error('local use decision missing',data.get('localUseDecision')=={'allowed':True,'scope':'local_constructor','decidedBy':'project_owner','decidedOn':'2026-10-08','authority':'direct_owner_instruction_2026-10-08'})
    error('external transfer / training must remain false',data.get('externalTransferAllowed') is False and data.get('trainingAllowed') is False)
    for section in ('sources','artifacts','frames','elements'):
        error(section+': nonempty list required',isinstance(data.get(section),list) and bool(data[section]))
    if errors: return data,{'valid':False,'errors':errors,'duplicates':[]}
    seen={}
    def unique(kind,value):
        values=seen.setdefault(kind,set())
        if value in values: duplicates.append(f'{kind}: {value}')
        values.add(value)
    def file(obj,key,digest_key,png=False):
        try:
            p=safe_path(root,obj[key]); digest=inspect_png(p) if png else sha(p)
            error(f'{obj.get("code",obj.get("key"))}: changed {key}',digest==obj.get(digest_key))
            hashes[obj[key]]=digest
        except (OSError,ValueError,KeyError) as exc: errors.append(str(exc))
    for s in data['sources']:
        error('source fields',all(text(s,k) for k in ('key','location','rightsEvidence')) and s.get('sourceType')=='музей' and s.get('legalBasis') is None)
        unique('source',s['key'])
    for a in data['artifacts']:
        error(a['code']+': artifact traceability',all(text(a,k) for k in ('code','sourceKey','titleRu')) and a['sourceKey'] in seen['source'])
        error(a['code']+': expert fields must remain unverified',a.get('reviewStatus')=='авто' and a.get('verifiedBy') is None and a.get('usageScope')=='контекст' and a.get('rights')=='неясно')
        unique('artifact',a['code'])
    frames={}
    for f in data['frames']:
        error('frame traceability',all(text(f,k) for k in ('key','artifactCode','frame','path','originalRawPath','originalRawSha256')) and f['artifactCode'] in seen['artifact'])
        unique('frame',f['key']); unique('framePath',f['path']); file(f,'path','sha256')
        frames[f['key']]=f
    for e in data['elements']:
        code=e['code']; unique('code',code)
        error(code+': element fields',all(text(e,k) for k in ('nameRu','motifClass','motifIdentity','frameKey','artifactCode','description','box1000')))
        f=frames.get(e['frameKey'])
        error(code+': frame/artifact mismatch',bool(f) and f['artifactCode']==e['artifactCode'])
        error(code+': expert not asserted',e.get('verifiedBy') is None)
        qa=e.get('qualityAcceptance',{})
        error(code+': owner quality decision missing',qa=={'decision':'accepted_current_quality','acceptedBy':'project_owner','acceptedOn':'2026-10-08','sha256':e.get('sha256')})
        error(code+': identity must identify source region',e['motifIdentity']==f"{e['artifactCode']}:{f['frame'] if f else ''}:{e['box1000']}")
        unique('identity',(e['artifactCode'],e['motifIdentity'])); unique('path',e['path']); unique('sha',e['sha256']); file(e,'path','sha256',True)
        file(e,'texturePath','textureSha256',True)
        error(code+': texture owner decision missing',e.get('textureQualityAcceptance')=={'decision':'accepted_current_quality','acceptedBy':'project_owner','acceptedOn':'2026-10-08','sha256':e.get('textureSha256')})
    report={'valid':not(errors or duplicates),'errors':errors,'duplicates':duplicates,'files':hashes,'manifestSha256':hashlib.sha256(raw).hexdigest(),'counts':{k:len(data[k]) for k in ('sources','artifacts','frames','elements')},'evidenceStatus':'documented_unverified','externalTransferAllowed':False,'trainingAllowed':False}
    report['approvalDigest']=hashlib.sha256(json.dumps(report,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return data,report


def db_conflicts(conn,data,report):
    for s in data['sources']:
        row=conn.execute('SELECT * FROM sources WHERE import_key=%s',(s['key'],)).fetchone()
        if row and (row['location'],row['legal_basis'],row['note'])!=(s['location'],None,s['rightsEvidence']): report['duplicates'].append('source conflict: '+s['key'])
    for a in data['artifacts']:
        if conn.execute('SELECT 1 FROM artifacts WHERE code=%s',(a['code'],)).fetchone(): report['duplicates'].append('artifact exists: '+a['code'])
    for f in data['frames']:
        if conn.execute('SELECT 1 FROM artifact_files WHERE path=%s',(f['path'],)).fetchone(): report['duplicates'].append('frame exists: '+f['path'])
    for e in data['elements']:
        if conn.execute('SELECT 1 FROM elements e LEFT JOIN element_files f ON f.element_id=e.id WHERE e.code=%s OR f.path=%s OR f.content_sha256=%s OR e.motif_identity=%s',(e['code'],e['path'],e['sha256'],e['motifIdentity'])).fetchone(): report['duplicates'].append('element exists: '+e['code'])
    report['valid']=not(report['errors'] or report['duplicates'])


def import_reviewed(conn,data,report):
    for s in data['sources']:
        conn.execute('INSERT INTO sources(import_key,source_type,location,legal_basis,note,shot_date) VALUES(%s,%s,%s,NULL,%s,%s) ON CONFLICT(import_key) DO NOTHING',(s['key'],s['sourceType'],s['location'],s['rightsEvidence'],'2026-09-01'))
    for a in data['artifacts']:
        sid=conn.execute('SELECT id FROM sources WHERE import_key=%s',(a['sourceKey'],)).fetchone()['id']
        conn.execute("INSERT INTO artifacts(code,source_id,title_ru,origin,authenticity,usage_scope,rights,review_status,notes) VALUES(%s,%s,%s,%s,%s,'контекст','неясно','авто',%s)",(a['code'],sid,a['titleRu'],a['origin'],a['authenticity'],json.dumps(a,ensure_ascii=False)))
    for f in data['frames']:
        aid=conn.execute('SELECT id FROM artifacts WHERE code=%s',(f['artifactCode'],)).fetchone()['id']
        conn.execute("INSERT INTO artifact_files(artifact_id,file_type,path,frame,content_sha256,note) VALUES(%s,'proxy',%s,%s,%s,%s)",(aid,f['path'],f['frame'],f['sha256'],json.dumps(f,ensure_ascii=False)))
    frames={f['key']:f for f in data['frames']}
    for e in data['elements']:
        a=conn.execute('SELECT id,source_id FROM artifacts WHERE code=%s',(e['artifactCode'],)).fetchone()
        f=frames[e['frameKey']]; fid=conn.execute('SELECT id FROM artifact_files WHERE path=%s',(f['path'],)).fetchone()['id']
        provenance={**e,'sourceFrame':f,'evidenceStatus':'documented_unverified','externalTransferAllowed':False,'trainingAllowed':False,'manifestSha256':data['upstreamManifestSha256']}
        eid=conn.execute("INSERT INTO elements(code,name_ru,motif_class,motif_identity,status,verified_by,artifact_id,source_id,description,provenance,local_use_approved) VALUES(%s,%s,%s,%s,'отрисовано',NULL,%s,%s,%s,%s,true) RETURNING id",(e['code'],e['nameRu'],e['motifClass'],e['motifIdentity'],a['id'],a['source_id'],e['description'],Jsonb(provenance))).fetchone()['id']
        conn.execute("INSERT INTO element_files(element_id,file_type,path,content_sha256,ai_retouched,source_file_id,quality_acceptance,file_available,file_checked_at) VALUES(%s,'flat_png',%s,%s,true,%s,%s,true,now())",(eid,e['path'],e['sha256'],fid,Jsonb(e['qualityAcceptance'])))
    conn.execute('INSERT INTO catalog_imports(manifest_sha256,reviewed_by,report) VALUES(%s,%s,%s)',(report['manifestSha256'],'project_owner:visual_quality_only',Jsonb(report)))
