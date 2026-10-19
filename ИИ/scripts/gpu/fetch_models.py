"""Owner-run download of fixed HF revisions with upstream hash verification.

No immers.cloud API. No dataset upload. Only call on an owner-approved machine/window.
"""
from pathlib import Path
import argparse, hashlib, json, os
ROOT = Path(__file__).resolve().parents[2]

def file_hash(path, algorithm='sha256', prefix=b''):
    h=hashlib.new(algorithm);h.update(prefix)
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024**2),b''): h.update(chunk)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--owner-run',action='store_true')
    ap.add_argument('--cache-dir',type=Path,default=Path(os.environ.get('HF_HOME', str(ROOT/'gpu-runtime/model-cache')))/'hub');a=ap.parse_args()
    if not a.owner_run:raise SystemExit('Download requires --owner-run; no download performed')
    from huggingface_hub import HfApi, snapshot_download
    api=HfApi();records=[]
    for model in json.loads((ROOT/'research/model_revisions.json').read_text())[:2]:
        repo,revision=model['repo'],model['revision'];control='controlnet' in repo
        tree=list(api.list_repo_tree(repo,revision=revision,recursive=True))
        selected=[]
        for info in tree:
            name=info.path
            if not hasattr(info,'blob_id'):continue
            small=name.endswith(('.json','.txt','.model'))
            weight=name.endswith('.safetensors') and (control or '.fp16.' in name)
            if small or weight:selected.append(info)
        if not any(i.path.endswith('.safetensors') for i in selected):
            raise RuntimeError('Pinned revision has no selected safetensors')
        folder=Path(snapshot_download(repo_id=repo,revision=revision,cache_dir=a.cache_dir,
                                     allow_patterns=[i.path for i in selected]))
        for info in selected:
            p=folder/info.path
            if info.lfs is not None:
                expected=info.lfs.sha256
                actual=file_hash(p)
                assert actual==expected, 'LFS SHA256 mismatch: '+info.path
                method='upstream_lfs_sha256'
            else:
                expected=info.blob_id
                actual=file_hash(p,'sha1',f'blob {p.stat().st_size}\0'.encode())
                assert actual==expected, 'Git blob mismatch: '+info.path
                method='upstream_git_blob_sha1'
            records.append(dict(repo=repo,revision=revision,path=info.path,bytes=p.stat().st_size,
                                sha256=file_hash(p),upstream_hash=expected,verification=method))
    out=ROOT/'gpu-runtime';out.mkdir(parents=True,exist_ok=True)
    (out/'model-inventory.json').write_text(json.dumps(dict(entries=records,cache_dir=str(a.cache_dir.resolve())),indent=2)+'\n')
    print(f'Verified {len(records)} model files. No training or GPU generation performed.')

if __name__=='__main__':main()
