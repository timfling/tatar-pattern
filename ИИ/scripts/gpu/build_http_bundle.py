"""Build the local offline HTTP transfer bundle; no SSH, GPU or network operations."""
import hashlib,io,json,tarfile
from pathlib import Path
root=Path(__file__).resolve().parents[3]; ai=root/'ИИ'; out=ai/'gpu-runtime/img2img-http-2026-10-19';out.mkdir(parents=True,exist_ok=True)
files={}
for name in ['server.py','workflow.py','render_one.py','qualify.py','profiles.json','config.example.json','README.md','backend-profile-handoff.json','qualification-plan.json','qualification-pairs.txt']:
 files['service/'+name]=ai/'service'/name
assets=root/'tatar-pattern/backend/app/ai-assets';index=json.loads((assets/'index.json').read_text());files['ai-assets/index.json']=assets/'index.json'
for b in index['bases']:
 for k in ['image','recipe']:files['ai-assets/'+b[k]]=assets/b[k]
files['model/adapter.safetensors']=ai/'gpu-runtime/immers-smoke-2026-10-17/unpacked/tp_dualstyle_diffusers_peft.safetensors'
files['model/base-inventory.json']=ai/'gpu-runtime/immers-smoke-2026-10-17/unpacked/base-inventory.json'
files['requirements.txt']=ai/'scripts/gpu/sdxl_smoke/requirements.txt'
files['tatar-inference.service.example']=ai/'scripts/gpu/tatar-inference.service.example'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
manifest=''.join(f'{sha(p)}  {name}\n' for name,p in sorted(files.items()))
assert sha(files['model/adapter.safetensors'])=='378c08ff157660a3399573e1cd5918ad8f3aec344646c5336b027d63fe50ca42'
archive=out/'tp-img2img-http.tgz'
with tarfile.open(archive,'w:gz') as tf:
 for name,p in sorted(files.items()):tf.add(p,arcname=name,recursive=False)
 data=manifest.encode();info=tarfile.TarInfo('bundle-files.sha256');info.size=len(data);info.mode=0o644;tf.addfile(info,io.BytesIO(data))
archive_sha=sha(archive);archive.with_suffix('.tgz.sha256').write_text(archive_sha+'  '+archive.name+'\n')
(out/'bundle-files.sha256').write_text(manifest)
(out/'bundle-info.json').write_text(json.dumps(dict(date='2026-10-19',status='STAGED_NOT_FOR_QUALIFICATION_UNTIL_PENDING_LOCAL_CORRECTIONS_REVIEWED' if json.loads((ai/'service/qualification-plan.json').read_text()).get('pendingLocalCorrections') else 'LOCAL_PACKAGE_NOT_DEPLOYED',filename=archive.name,sha256=archive_sha,bytes=archive.stat().st_size,files=len(files)+1,profiles=len(json.loads((ai/'service/profiles.json').read_text())['profiles']),actualQualifiedPairs=[],includesBaseSnapshot=False),indent=2)+'\n')
print(archive,archive.stat().st_size,archive_sha)
