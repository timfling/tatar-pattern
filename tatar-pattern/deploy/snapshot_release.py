#!/usr/bin/env python3
"""Freeze current allowlisted working files, not merely HEAD; never reads .env."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent
AI = ROOT.parent/'ИИ'

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--release', required=True)
    p.add_argument('--date', required=True)
    args = p.parse_args()
    output = args.output.resolve()
    git_root = Path(subprocess.check_output(['git','-C',str(ROOT),'rev-parse','--show-toplevel']).decode().strip())
    if output.is_relative_to(git_root):
        raise SystemExit('Output must be outside source Git tree')
    output.mkdir(parents=True, exist_ok=False)
    files = {}
    def add(source, name):
        if source.is_symlink():
            raise RuntimeError('Symlink forbidden: '+str(source))
        if source.name in ('.DS_Store',) or source.name.startswith('._') or '__pycache__' in source.parts or source.suffix == '.pyc':
            return
        if source.name.startswith('.env') and source.name != '.env.example':
            raise RuntimeError('Environment forbidden')
        files[name] = source
    for folder in ('backend/app', 'backend/scripts', 'frontend/src', 'frontend/public', 'db/migrations'):
        for source in (ROOT/folder).rglob('*'):
            if source.is_file():
                add(source, source.relative_to(ROOT).as_posix())
    for name in ('backend/pyproject.toml', 'backend/uv.lock', 'backend/README.md', 'frontend/package.json',
                 'frontend/package-lock.json', 'frontend/next.config.ts', 'frontend/tsconfig.json',
                 'frontend/next-env.d.ts', 'frontend/postcss.config.mjs', 'API-CONTRACT.md'):
        add(ROOT/name, name)
    for source in (ROOT/'deploy').iterdir():
        if source.is_file() and (source.suffix in ('.py', '.yml') or source.name.startswith(('Dockerfile', 'Caddyfile')) or
                                source.name in ('.env.example', '.gitignore', 'README.md', 'HANDOFF.md', 'BEGET.md', 'rsyslog.conf', 'qualification-jobs.json')):
            add(source, 'deploy/'+source.name)
    for source in (ROOT/'deploy/systemd').iterdir():
        if source.is_file():
            add(source, 'deploy/systemd/'+source.name)
    catalog = ROOT/'backend/local-test/production-catalog-2026-10-19'
    for name in ('catalog110.tgz', 'catalog110.tgz.sha256', 'validation.json', 'release-decision.pending.json'):
        add(catalog/name, 'payload/catalog/'+name)
    for name in ('server.py','workflow.py','render_one.py','qualify.py','profiles.json','config.example.json','README.md',
                 'backend-profile-handoff.json','qualification-plan.json','qualification-pairs.txt','cloud-http-handoff.json'):
        add(AI/'service'/name, 'payload/gpu/service/'+name)
    for name in ('GPU-HANDOFF.md','GPU-INTEGRATION.md'):
        add(AI/name, 'payload/gpu/'+name)
    for source in (ROOT/'backend/app/ai-assets').rglob('*'):
        if source.is_file():
            add(source, 'payload/gpu/ai-assets/'+source.relative_to(ROOT/'backend/app/ai-assets').as_posix())
    model = AI/'gpu-runtime/immers-smoke-2026-10-17/unpacked'
    add(model/'tp_dualstyle_diffusers_peft.safetensors', 'payload/gpu/model/adapter.safetensors')
    add(model/'base-inventory.json', 'payload/gpu/model/base-inventory.json')
    add(AI/'scripts/gpu/sdxl_smoke/requirements.txt', 'payload/gpu/requirements.txt')
    add(AI/'scripts/gpu/tatar-inference.service.example', 'payload/gpu/tatar-inference.service.example')
    evidence = AI/'gpu-runtime/img2img-http-2026-10-19'
    for name in ('verified-host-ed25519.pub','verified-known-hosts','worker-probe-command.txt','owner-cloud-selection.json','cloud-27-audit.json'):
        add(evidence/name, 'payload/gpu/evidence/'+name)
    for name, source in sorted(files.items()):
        target = output/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if sha(source) != sha(target):
            raise RuntimeError('Concurrent change while copying '+name)
    # Verify source stability across the whole copy operation.
    for name, source in files.items():
        if sha(source) != sha(output/name):
            raise RuntimeError('Source changed during snapshot: '+name)
    manifest = {'schemaVersion': 2, 'release': args.release, 'date': args.date,
                'createdAt': datetime.now(timezone.utc).isoformat(), 'archiveEpoch': int(datetime.fromisoformat(args.date).replace(tzinfo=timezone.utc).timestamp()),
                'platform': 'linux/amd64', 'status': 'SOURCE_FROZEN_IMAGES_PENDING',
                'baseCommit': subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD']).decode().strip(),
                'workingTreeStatus': subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain=v1']).decode().splitlines(),
                'sourceCommitNote': 'Dirty working snapshot: SHA manifest identifies exact release beyond baseCommit',
                'locks': {n: sha(output/n) for n in ('backend/uv.lock','frontend/package-lock.json','payload/gpu/requirements.txt')},
                'gpuAdapterSHA256': sha(output/'payload/gpu/model/adapter.safetensors'),
                'baseSnapshot': {'included': False, 'inventory': 'payload/gpu/model/base-inventory.json', 'location': 'existing GPU VM cache; preserve before shelve'},
                'transfer': 'Beget runtime and catalog separately from GPU payload; do not replace live qualified GPU deployment',
                'gates': {'AI_MVP_ENABLED': False, 'GUEST_GPU_BUDGET': 0, 'publicDeploy': False, 'workerProof': False},
                'excluded': ['.env/secrets/private keys','working DB/storage/backups/QA','node_modules/.next/.venv/.git',
                             'museum frames outside catalog110 allowlist', 'old pilot images/release reports']}
    (output/'deploy/RELEASE-MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    hashes = {p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob('*')) if p.is_file()}
    (output/'deploy/SOURCE-SHA256.json').write_text(json.dumps(hashes, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(output), 'files': len(hashes), 'bytes': sum(p.stat().st_size for p in output.rglob('*') if p.is_file())}))

if __name__ == '__main__':
    main()
