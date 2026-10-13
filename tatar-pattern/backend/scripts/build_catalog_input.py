"""Read current masters, create backend-owned immutable import copies. No retouch."""
import csv
import json
import shutil
from collections import Counter
from pathlib import Path
from .catalog_v2 import sha

BASE=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parents[1]/'catalog-input'

def main():
    upstream=BASE/'Датасет/Элементы/manifest.csv'
    rows=list(csv.DictReader(upstream.open(encoding='utf-8-sig')))
    assert len(rows)==110 and len({r['code'] for r in rows})==110
    main_codes={r['code'] for r in rows}
    flat_codes={p.stem for p in (BASE/'Датасет/Элементы/processed_flat').glob('*.png')}
    texture_codes={p.stem for p in (BASE/'Датасет/Элементы/processed_texture').glob('*.png')}
    assert flat_codes-main_codes=={'TP-R-001','TP-R-002'} and main_codes-flat_codes==set()
    assert texture_codes==main_codes
    OUT.mkdir(exist_ok=True)
    def copy(original,relative):
        source=BASE/original; target=OUT/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            if sha(target)!=sha(source): raise RuntimeError('Existing import copy differs: '+relative)
        else: shutil.copyfile(source,target)
        return sha(target)
    sources={}; artifacts={}; frames={}; elements=[]
    for r in rows:
        location=Path(r['source_raw']).parent.name
        source_key='owner-catalog-20261008:'+location
        sources[source_key]={'key':source_key,'sourceType':'музей','location':location,'legalBasis':None,'rightsEvidence':r['rights_limitations']}
        artifact=r['artifact_code']; frame_key=artifact+':'+r['frame']
        a={'code':artifact,'sourceKey':source_key,'titleRu':r['owner_title_ru'] or r['source_title_ru'],'origin':r['source_origin'],'authenticity':r['source_authenticity'],'usageScope':'контекст','rights':'неясно','reviewStatus':'авто','verifiedBy':None,'metadata':{k:v for k,v in r.items() if k.startswith(('source_','owner_'))}}
        if artifact not in artifacts: artifacts[artifact]=a
        proxy=f"sources/{artifact}/{r['frame']}.jpg"
        if frame_key not in frames:
            frames[frame_key]={'key':frame_key,'artifactCode':artifact,'frame':r['frame'],'path':proxy,'sha256':copy(r['source_proxy'],proxy),'originalRawPath':r['source_raw'],'originalRawSha256':sha(BASE/r['source_raw']),'originalProxyPath':r['source_proxy'],'originalProxySha256':sha(BASE/r['source_proxy'])}
        code=r['code']; flat=f'flat/{code}.png'; texture=f'texture/{code}.png'
        flat_sha=copy(f'Датасет/Элементы/processed_flat/{code}.png',flat)
        texture_sha=copy(f'Датасет/Элементы/processed_texture/{code}.png',texture)
        elements.append({'code':code,'nameRu':r['description'],'description':r['description'],'motifClass':r['motif_class'],'motifIdentity':f"{artifact}:{r['frame']}:{r['box_1000']}",'artifactCode':artifact,'frameKey':frame_key,'box1000':r['box_1000'],'placeDescription':r['place_description'],'path':flat,'sha256':flat_sha,'texturePath':texture,'textureSha256':texture_sha,'verifiedBy':None,'qualityAcceptance':{'decision':'accepted_current_quality','acceptedBy':'project_owner','acceptedOn':'2026-10-08','sha256':flat_sha},'textureQualityAcceptance':{'decision':'accepted_current_quality','acceptedBy':'project_owner','acceptedOn':'2026-10-08','sha256':texture_sha},'upstreamRow':r,'annotationPath':r['annotation_file'],'annotationSha256':sha(BASE/r['annotation_file'])})
    aux=[]
    for p in sorted((BASE/'Датасет/Элементы/processed_flat').glob('*.png')):
        if p.stem not in {e['code'] for e in elements}: aux.append({'code':p.stem,'path':str(p.relative_to(BASE)),'sha256':sha(p),'includedInCount':False,'qualityAcceptance':{'acceptedBy':'project_owner','acceptedOn':'2026-10-08','decision':'accepted_current_quality'}})
    data={'version':2,'upstreamManifestPath':str(upstream.relative_to(BASE)),'upstreamManifestSha256':sha(upstream),'localUseDecision':{'allowed':True,'scope':'local_constructor','decidedBy':'project_owner','decidedOn':'2026-10-08','authority':'direct_owner_instruction_2026-10-08'},'externalTransferAllowed':False,'trainingAllowed':False,'sources':list(sources.values()),'artifacts':list(artifacts.values()),'frames':list(frames.values()),'elements':elements,'auxiliaryExcluded':aux}
    (OUT/'owner-accepted-2026-10-08.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    groups={}
    for e in elements: groups.setdefault(e['sha256'],[]).append(e['code'])
    report={'mainManifestRows':len(rows),'flatMain':len(elements),'textureMain':len(elements),'auxiliaryExcluded':aux,'uniqueFileSha256':len(groups),'uniqueSourceRegions':len({e['motifIdentity'] for e in elements}),'byteDuplicates':[v for v in groups.values() if len(v)>1],'classes':dict(Counter(e['motifClass'] for e in elements)),'semanticIdentityBasis':'artifact + source frame + annotation region, not an expert claim of uniqueness across artifacts','semanticDuplicatesConfirmed':[],'evidenceStatus':'documented_unverified','missingFields':{'allSources':['legalBasis (independent confirmed basis; current oral-consent report preserved in rightsEvidence)','externalTransfer authorization scope','training authorization scope','public distribution/commercial use scope'],'allElements':['verifiedBy / expert provenance conclusion (unknown; not required for owner-authorized local constructor)']}}
    (OUT/'reconciliation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('mainManifestRows','flatMain','textureMain','uniqueFileSha256','uniqueSourceRegions')},ensure_ascii=False))

if __name__=='__main__': main()
