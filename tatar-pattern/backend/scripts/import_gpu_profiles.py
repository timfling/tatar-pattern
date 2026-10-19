"""Offline registry synchronization; cloud evidence is not worker proof or release permission."""
import argparse
import hashlib
import json
from pathlib import Path
from app import ai_catalog


def main():
    p=argparse.ArgumentParser();p.add_argument('--handoff',type=Path,required=True);p.add_argument('--cloud',type=Path,required=True);p.add_argument('--gpu-profiles',type=Path,required=True);p.add_argument('--apply',action='store_true');args=p.parse_args()
    target=ai_catalog.PROFILES;doc=json.loads(target.read_text())
    old={(r['baseId'],r['ornamentStyle']):r for r in doc['profiles']}
    additions=json.loads(args.handoff.read_text())['profiles']
    gpu=json.loads(args.gpu_profiles.read_text())['profiles']
    cloud=json.loads(args.cloud.read_text());evidence={}
    project=Path(__file__).resolve().parents[3]
    for result in cloud['results']:
        key=result['baseId']+':'+result['ornamentStyle'];meta=result['metadata']
        raw=(project/result['evidence']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=result['evidenceSha256']:raise RuntimeError('Evidence SHA mismatch')
        if meta['deploymentDigest']!=cloud['deploymentDigest'] or result['bootId']!=cloud['bootId']:raise RuntimeError('Cloud identity mismatch')
        if result['ownerAccepted']!=(key in cloud['acceptedPairs']):raise RuntimeError('Owner acceptance mismatch')
        evidence[key]=result
    added=sum((r['baseId'],r['ornamentStyle']) not in old for r in additions)
    for row in additions:
        key=(row['baseId'],row['ornamentStyle'])
        if key in old and any(old[key].get(k)!=row.get(k) for k in ('baseSha256','version','strength','steps','gpuProfileDigest','gpuPromptSha256','promptVersion')):
            raise RuntimeError('Existing profile differs; no overwrite')
        old.setdefault(key,row)
    for (base,style),row in old.items():
        ai_catalog.asset_file(ai_catalog.find_base(base));ai_catalog.asset_file(ai_catalog.find_base(base),'recipe')
        canonical=next(r for r in gpu if r['baseId']==base and r['ornamentStyle']==style and r['version']==row['version'])
        if hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()!=row['gpuProfileDigest']:raise RuntimeError('GPU canonical digest mismatch')
        if row['baseSha256']!=ai_catalog.find_base(base)['sha256'] or hashlib.sha256(canonical['prompt'].encode()).hexdigest()!=row['gpuPromptSha256']:raise RuntimeError('Profile pin mismatch')
        for k in ('strength','steps','promptVersion'):
            if row[k]!=canonical[k]:raise RuntimeError('Profile setting mismatch')
        # Never open grants, including on a repeat after activation.
        if row.get('releaseApproved') is not False:raise RuntimeError('Registry already activated; explicit review required')
        result=evidence.get(base+':'+style)
        if result:
            meta=result['metadata']
            if any(meta[k]!=row[v] for k,v in [('baseSha256','baseSha256'),('profileVersion','version'),('profileDigest','gpuProfileDigest'),('promptVersion','promptVersion'),('strength','strength'),('steps','steps')]):raise RuntimeError('Cloud metadata mismatch')
            row.update(qualityStatus='owner_accepted_cloud_2026_10_19' if result['ownerAccepted'] else 'owner_rejected_cloud_2026_10_19',
                       gpuRecipeStatus='cloud_http_evidence_worker_proof_pending',
                       cloudEvidence={k:result[k] for k in ('jobId','pngSha256','ownerAccepted','evidence','evidenceSha256','deploymentDigest','bootId')})
        else:
            row['qualityStatus']='excluded_from_cloud_qualification'
    doc['profiles']=list(old.values())
    if len(old)!=28 or len(cloud['acceptedPairs'])!=25:raise RuntimeError('Unexpected release scope')
    if args.apply:target.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(profiles=len(old),newRows=added,handoffRows=len(additions),ownerAcceptedCloud=len(cloud['acceptedPairs']),releaseApproved=0,applied=args.apply)))

if __name__=='__main__':main()
