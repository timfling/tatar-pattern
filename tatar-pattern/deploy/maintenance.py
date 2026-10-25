#!/usr/bin/env python3
"""Project-scoped maintenance; never inspect/delete unrelated container data."""
import argparse
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from uuid import UUID
from ops import HERE, compose, read_env

TAG = 'tatar-pattern-guest-v1'

def lock(root, blocking=True):
    handle = (Path(root)/'.maintenance.lock').open('a')
    fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
    return handle

def local_retention(root, now=None, logs=Path('/var/log/tatar-pattern')):
    now = now or datetime.now(timezone.utc)
    cutoff = now.timestamp() - 7*86400
    removed = 0
    # Excludes postgres, live storage, keys, catalogue, GPU evidence and release trees.
    for base in (root/'backups', root/'migration-backups'):
        if base.is_symlink():
            raise RuntimeError('Symlink in retention root')
        for entry in base.iterdir() if base.exists() else []:
            if entry.is_symlink():
                raise RuntimeError('Symlink in backups')
            if entry.name.startswith('.'):
                continue
            # Directories are named by ops.backup; files by backend db_admin/migrate.
            allowed = (entry.is_dir() and re.fullmatch(r'\d{8}T\d{6}Z-[a-f0-9]{6}', entry.name)) or (
                entry.is_file() and entry.suffix in ('.dump', '.gz', '.sql'))
            if allowed and entry.stat().st_mtime < cutoff:
                shutil.rmtree(entry) if entry.is_dir() else entry.unlink()
                removed += 1
    # UTC daily buckets: discard at 13d, hourly run => oldest message <14d.
    if logs.is_symlink():
        raise RuntimeError('Symlink in log root')
    for entry in logs.glob('runtime-????-??-??.log'):
        if entry.is_symlink():
            raise RuntimeError('Symlink in logs')
        day = datetime.strptime(entry.name, 'runtime-%Y-%m-%d.log').replace(tzinfo=timezone.utc)
        if day <= (now - timedelta(days=13)).replace(hour=0, minute=0, second=0, microsecond=0):
            entry.unlink()
            removed += 1
    for entry in (root/'restore-checks').glob('restore-*'):
        marker = entry/'CLEANUP-ALLOWED'
        if entry.is_symlink() or marker.is_symlink():
            raise RuntimeError('Symlink in restore check data')
        if marker.is_file() and marker.stat().st_mtime < cutoff:
            shutil.rmtree(entry)
            removed += 1
    return removed

def remote_retention(now=None):
    if not os.getenv('RESTIC_REPOSITORY') or not os.getenv('RESTIC_PASSWORD_FILE'):
        raise RuntimeError('Protected restic environment required')
    now = now or datetime.now(timezone.utc)
    snapshots = json.loads(subprocess.check_output(['restic', 'snapshots', '--json', '--tag', TAG])) or []
    old = [s['id'] for s in snapshots if datetime.fromisoformat(s['time'].replace('Z', '+00:00')) < now-timedelta(days=7)]
    if old:
        subprocess.run(['restic', 'forget', *old, '--prune'], check=True)
    # A dedicated repository is mandatory; old untagged/legacy copies must be resolved.
    all_snapshots = json.loads(subprocess.check_output(['restic', 'snapshots', '--json'])) or []
    if any(TAG not in (s.get('tags') or []) for s in all_snapshots):
        raise RuntimeError('Unexpected snapshots in dedicated repository: review legacy retention; no foreign deletion attempted')
    print(json.dumps({'expiredIndependentSnapshots': len(old)}))

def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--env', type=Path, required=True)
    p.add_argument('action', choices=['cleanup', 'retention', 'proof'])
    args = p.parse_args()
    values = read_env(args.env)
    with lock(values['DATA_ROOT']):
        if args.action == 'cleanup':
            dc = compose(args.env, values)
            dc('run', '--rm', '--no-deps', '-T', 'backend', 'python', '-m', 'scripts.guest_maintenance', 'cleanup')
            status = json.loads(dc('run', '--rm', '--no-deps', '-T', 'backend', 'python', '-m', 'scripts.guest_maintenance', 'status', capture=True))
            if status['pendingGuestFiles']:
                raise RuntimeError('Guest files pending deletion: inspect permissions/disk and retry')
            print(json.dumps(status))
        elif args.action == 'proof':
            if values.get('AI_API_CONFIG') != 'true':
                raise RuntimeError('API and worker must share actual adapter configuration')
            jobs = json.loads((HERE/'qualification-jobs.json').read_text())['jobIds']
            if len(jobs) != 25 or len(set(jobs)) != 25:
                raise RuntimeError('Expected 25 retained owner-accepted qualification UUIDs')
            command = ['python', '-m', 'scripts.ai_gpu_probe', '--owner-run', '--worker-namespace']
            for job in jobs:
                command.extend(['--job-id', str(UUID(job))])
            dc = compose(args.env, values)
            dc('exec', '-T', 'ai-worker', *command)
            dc('exec', '-T', 'ai-worker', 'python', '-m', 'scripts.gpu_proof_status')
        else:
            print(json.dumps({'localRemoved': local_retention(Path(values['DATA_ROOT']))}))
            remote_retention()

if __name__ == '__main__':
    main()
