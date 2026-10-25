#!/usr/bin/env python3
"""Export already-built amd64 images and seal the frozen release SHA manifest."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    args=p.parse_args();root=args.root.resolve();deploy=root/'deploy'
    manifest=json.loads((deploy/'RELEASE-MANIFEST.json').read_text())
    release=manifest['release']
    if any(p.is_dir() and p.name in ('__pycache__','node_modules','.next','.venv','local-check') for p in root.rglob('*')) or any(p.is_file() and (p.name in ('.env','.DS_Store') or p.name.startswith('._') or p.name.endswith('.pyc')) for p in root.rglob('*')):
        raise SystemExit('Release must not contain local data/config')
    images=[]
    for name in ('backend','frontend','tunnel','postgres','caddy'):
        tag=f'tatar-pattern-{name}:{release}'
        info=json.loads(subprocess.check_output(['docker','image','inspect',tag]))[0]
        if info['Os']+'/'+info['Architecture']!='linux/amd64':
            raise SystemExit('Wrong platform: '+tag)
        images.append({'tag':tag,'sourceImageId':info['Id'],'configDigest':None,
                       'platformManifestDigest':None,'rootfsDiffIds':info['RootFS']['Layers'],
                       'repoDigests':info.get('RepoDigests',[]),'sizeBytes':info['Size']})
    directory=deploy/'images';directory.mkdir(exist_ok=True)
    archive=directory/(release+'-amd64.tar.gz')
    if not archive.exists():
        with archive.open('xb') as raw, gzip.GzipFile(filename='',fileobj=raw,mode='wb',compresslevel=1,mtime=0) as zipped:
            proc=subprocess.Popen(['docker','image','save','--platform','linux/amd64',*[i['tag'] for i in images]],stdout=subprocess.PIPE)
            shutil.copyfileobj(proc.stdout,zipped,1024*1024)
            if proc.wait():
                raise RuntimeError('Docker save failed; remove incomplete archive before retry')
    # A saved config digest is stable across classic/containerd image stores.
    with tarfile.open(archive,'r:gz') as tf:
        records=json.load(tf.extractfile('manifest.json'))
        for item in images:
            record=next(r for r in records if item['tag'] in (r.get('RepoTags') or []))
            config=json.load(tf.extractfile(record['Config']))
            if config['architecture']!='amd64' or config['os']!='linux':
                raise RuntimeError('Saved image is not amd64')
            item['configDigest']='sha256:'+Path(record['Config']).stem if '/' not in record['Config'] else 'sha256:'+record['Config'].split('/')[-1].removesuffix('.json')
        for member in tf.getmembers():
            if not member.isfile() or not member.name.startswith('blobs/sha256/') or member.size > 2*1024*1024:
                continue
            try:
                obj=json.load(tf.extractfile(member))
            except (ValueError, UnicodeDecodeError):
                continue
            if not isinstance(obj,dict) or 'config' not in obj or not isinstance(obj['config'],dict):
                continue
            for item in images:
                if obj['config'].get('digest')==item['configDigest']:
                    item['platformManifestDigest']='sha256:'+member.name.split('/')[-1]
    (deploy/'IMAGES.json').write_text(json.dumps({'platform':'linux/amd64','images':images},indent=2)+'\n')
    manifest.update(status='OFFLINE_IMAGES_READY_SERVER_ACCEPTANCE_PENDING',
                    sealedAt=datetime.now(timezone.utc).isoformat(),
                    images={'list':'deploy/IMAGES.json','archive':{'path':archive.relative_to(root).as_posix(),'sha256':sha(archive),'sizeBytes':archive.stat().st_size}},
                    sources={'next':json.loads((root/'frontend/package.json').read_text())['dependencies']['next'],
                             'migrations':[p.name for p in sorted((root/'db/migrations').glob('*.sql'))]},
                    rebuildLimitations='Exact runnable images included; uv/npm locks and pinned base digests. External APT repositories are not snapshotted; a future source rebuild is not promised byte-identical.',
                    provider='portable Ubuntu x86_64 VPS; Beget unavailable, owner choosing alternative',
                    budgetRUBPerMonth={'vpsAndIndependentBackup':2500,'gpuAndDomain':'separate'},
                    serverAcceptance={'performed':False,'workerProof':False,'realCatalogImport110':False,'publicHTTPS':False})
    (deploy/'RELEASE-MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    hashes={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file() and p!=deploy/'SOURCE-SHA256.json'}
    (deploy/'SOURCE-SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'release':release,'images':len(images),'files':len(hashes),'imageArchiveBytes':archive.stat().st_size}))

if __name__=='__main__':main()
