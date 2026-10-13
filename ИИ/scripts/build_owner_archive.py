"""Local preparation only: selects a minimal owner-run upload archive."""
from pathlib import Path
import hashlib,json,zipfile
AI=Path(__file__).resolve().parents[1]
files=[]
for name in ['START-HERE.md','MODEL-AND-PILOT.md','SELECTEL-INTEGRATION.md','SELECTEL-HANDOFF.md','DSLAB-INTEGRATION.md','OWNER-DECISIONS.md','OWNER-DECLARATION-2026-10-11.json']:
    files.append(AI/name)
for folder in ['dataset/texture-v1/train','dataset/texture-v1/validation']:
    files.extend(sorted((AI/folder).iterdir()))
for name in ['training_manifest.csv','checks.json','structure_reference.png','structure_alpha.png','structure_reference.json']:
    files.append(AI/'dataset/texture-v1'/name)
files.extend(sorted((AI/'pilot').glob('*.py')))
files.extend(sorted((AI/'pilot').glob('*.json')))
files.extend(sorted((AI/'pilot').glob('*.csv')))
files.append(AI/'pilot/requirements-gpu.txt')
for name in ['server.py','render_one.py','config.example.json','README.md','local-http-checks.json']:
    files.append(AI/'service'/name)
for name in ['train_text_to_image_lora_sdxl.py','model_revisions.json','sdxl-license.md','sdxl-card.md','controlnet-card.md','flux-card-public.md']:
    files.append(AI/'research'/name)
files.extend(sorted(p for p in (AI/'selectel').iterdir() if p.is_file() and p.name!='local-migration-checks.json'))
inventory=[]
archive=AI/'owner-upload.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(set(files)):
        data=p.read_bytes();rel=str(p.relative_to(AI));z.writestr('tatar-lora-kit/'+rel,data)
        inventory.append({'path':rel,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    kit={'provider':'Selectel','date':'2026-10-11','entries':inventory}
    z.writestr('tatar-lora-kit/kit-manifest.json',json.dumps(kit,ensure_ascii=False,indent=2)+'\n')
(AI/'kit-manifest.json').write_text(json.dumps(kit,ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert sum(n.endswith('.png') and '/train/' in n for n in z.namelist())==39
    assert sum(n.endswith('.png') and '/validation/' in n for n in z.namelist())==7
    assert not any('/all_rgb/' in n or '/local-test/' in n or '/state/' in n for n in z.namelist())
report={'date':'2026-10-11','provider':'Selectel','archive':'owner-upload.zip','bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'entries':inventory,'training_pngs':39,'validation_pngs':7,'templates_pngs':2,'archive_crc_verified':True,'external_upload_performed':False}
(AI/'owner-upload.inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='entries'},ensure_ascii=False))
