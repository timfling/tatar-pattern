#!/usr/bin/env python3
"""Commit the frozen source in an isolated repository; never modify shared Git."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    args=p.parse_args();root=args.root.resolve();deploy=root/'deploy'
    manifest=json.loads((deploy/'RELEASE-MANIFEST.json').read_text())
    selected=[];inputs={}
    for path in sorted(root.rglob('*')):
        if not path.is_file():continue
        name=path.relative_to(root).as_posix()
        if name in ('deploy/SOURCE-SHA256.json','deploy/RELEASE-MANIFEST.json','deploy/IMAGES.json','deploy/INPUT-SHA256.json') or name.startswith(('deploy/images/','deploy/release-evidence/')) or name.endswith('.bundle'):
            continue
        if path.is_symlink() or path.name=='.env' or path.suffix=='.pyc':
            raise RuntimeError('Forbidden input: '+name)
        inputs[name]=sha(path)
        # Large external transfer artifacts are authenticated by INPUT-SHA256.json.
        # Runtime assets (including PNG/recipes) are present directly in the Git tree.
        if path.suffix not in ('.tgz','.safetensors'):
            selected.append(name)
    (deploy/'INPUT-SHA256.json').write_text(json.dumps(inputs,ensure_ascii=False,indent=2)+'\n')
    selected.append('deploy/INPUT-SHA256.json')
    with tempfile.TemporaryDirectory(prefix='tp-release-source-git-') as temp:
        gitdir=Path(temp)/'git'
        subprocess.run(['git','init','--bare','--initial-branch=release',str(gitdir)],check=True,stdout=subprocess.DEVNULL)
        env=os.environ.copy()
        # All Git state is in temp, with an explicit index. No hooks/config from shared repo.
        env.update(GIT_DIR=str(gitdir),GIT_WORK_TREE=str(root),GIT_INDEX_FILE=str(Path(temp)/'index'),
                   GIT_AUTHOR_NAME='Tatar Pattern release snapshot',GIT_AUTHOR_EMAIL='release@example.invalid',
                   GIT_COMMITTER_NAME='Tatar Pattern release snapshot',GIT_COMMITTER_EMAIL='release@example.invalid',
                   GIT_AUTHOR_DATE=manifest['date']+'T00:00:00+00:00',GIT_COMMITTER_DATE=manifest['date']+'T00:00:00+00:00')
        subprocess.run(['git','-c','core.excludesFile=/dev/null','add','--force','--',*selected],env=env,check=True)
        tree=subprocess.check_output(['git','write-tree'],env=env).decode().strip()
        commit=subprocess.check_output(['git','commit-tree',tree],input=(manifest['release']+' frozen working sources; external artifact SHA manifest\n').encode(),env=env).decode().strip()
        subprocess.run(['git','update-ref','refs/heads/release',commit],env=env,check=True)
        bundle=deploy/(manifest['release']+'-source.bundle')
        subprocess.run(['git','bundle','create',str(bundle),'refs/heads/release'],env=env,check=True)
        subprocess.run(['git','bundle','verify',str(bundle)],env=env,check=True,stdout=subprocess.DEVNULL)
    manifest.update(sourceCommit=commit,sourceTree=tree,sourceBundle=bundle.relative_to(root).as_posix(),
                    sourceCommitCoverage='Exact runtime source/assets plus GPU source/assets; large catalogue tgz and LoRA weights are separately included and authenticated by committed deploy/INPUT-SHA256.json. Images/evidence/manifests are sealed by SOURCE-SHA256.json.',
                    sourceBundleSHA256=sha(bundle))
    (deploy/'RELEASE-MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'sourceCommit':commit,'sourceTree':tree,'bundleBytes':bundle.stat().st_size}))

if __name__=='__main__':main()
