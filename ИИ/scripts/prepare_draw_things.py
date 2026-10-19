"""Create/verify the Draw Things pilot pack without changing approved data. No network."""
from pathlib import Path
import csv
import hashlib
import json
import shutil
from PIL import Image

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parent
OUT = AI / 'draw-things'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    source = AI / 'dataset/texture-v1'
    rows = list(csv.DictReader((source / 'training_manifest.csv').open(encoding='utf-8')))
    acceptance = json.loads((source / 'owner_acceptance.json').read_text())
    for r in acceptance:
        assert sha(ROOT / r['source_path']) == r['sha256'], r['source_path']
    checks = json.loads((source / 'checks.json').read_text())
    for path, digest in checks['input_csv_sha256'].items():
        assert sha(Path(path)) == digest, path
    assert sha(source/'training_manifest.csv') == checks['manifest_sha256']
    for key in ['artifact_code', 'similarity_group']:
        train={r[key] for r in rows if r['split']=='train'}
        val={r[key] for r in rows if r['split']=='validation'}
        assert not train & val, key
    files=[]
    for split, expected in [('train',39),('validation',7)]:
        dest=OUT / ('pilot-train' if split=='train' else 'validation-DO-NOT-TRAIN')
        dest.mkdir(parents=True,exist_ok=True)
        selected=[r for r in rows if r['split']==split]
        assert len(selected)==expected
        expected_names={r['code']+ext for r in selected for ext in ['.png','.txt']}
        assert not {p.name for p in dest.iterdir()}-expected_names, 'Unexpected file in '+str(dest)
        for r in selected:
            code=r['code']; png=source/split/(code+'.png'); txt=png.with_suffix('.txt')
            assert sha(png)==r['rgb_sha256'] and sha(txt)==r['caption_sha256'], code
            with Image.open(png) as im:
                assert im.mode=='RGB' and im.size==(1024,1024), code
                assert all(im.getpixel(p)==(255,255,255) for p in [(0,0),(1023,0),(0,1023),(1023,1023)]), code
            assert txt.read_text().strip()==r['caption'] and r['caption'].startswith('tptrx,')
            for p in [png,txt]:
                target=dest/p.name
                if target.exists():
                    assert sha(target)==sha(p), 'Edited output: '+str(target)
                else:
                    shutil.copy2(p,target)
                files.append({'path':str(target.relative_to(AI)),'sha256':sha(target),'split':split})
    OUT.mkdir(exist_ok=True)
    (OUT/'dataset-checks.json').write_text(json.dumps({'status':'PASSED','train':39,'validation':7,'masters_verified':len(acceptance),'artifact_and_similarity_leakage':False,'training_status':'NOT_RUN','files':files},ensure_ascii=False,indent=2)+'\n')
    print('PASSED: 39 train + 7 validation PNG/TXT pairs; 220 masters and source CSV verified; no split leakage.')

if __name__=='__main__':
    main()
