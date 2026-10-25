#!/usr/bin/env python3
"""Offline historical GPU evidence snapshot, excluding Bearer/SSH keys.

Requires inactive GPU HTTP service and its state lock. Does not stop/start it.
Run on GPU only in an agreed paid window, before qualification/runtime changes.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import tarfile

RUNTIME = Path('/srv/tatar-lora-kit')
DEST = Path('/srv/tatar-gpu-evidence')
NAMES = ('http-record.json', 'normal-health.json', 'post-restart-health.json',
         'post-renewal-health.json', 'config.json', 'state', 'proof-first', 'proof-remaining26')


def require(ok, msg):
    if not ok:
        raise RuntimeError(msg)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def collect(service):
    files = []
    missing = []
    for name in NAMES:
        path = service / name
        require(not path.is_symlink(), 'Symlink in evidence root')
        if not path.exists():
            missing.append(name)
            continue
        candidates = sorted(path.rglob('*')) if path.is_dir() else [path]
        for entry in candidates:
            require(not entry.is_symlink(), 'Symlink in evidence tree')
            if entry.is_dir():
                continue
            require(entry.is_file() and entry.name not in ('token', 'bearer', 'id_ed25519'),
                    'Unexpected nonregular/secret evidence file')
            files.append(entry)
    return files, missing


def snapshot(service, dest, final_window=False):
    lock_path = service / 'state/service.lock'
    require(lock_path.is_file() and not lock_path.is_symlink(), 'Existing service state lock required')
    with lock_path.open('rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        files, missing = collect(service)
        require(service / 'state/jobs.sqlite' in files, 'GPU SQLite missing; no complete state snapshot')
        before = {p.relative_to(service).as_posix(): sha(p) for p in files}
        dest.mkdir(parents=True, exist_ok=True, mode=0o700)
        require(not dest.is_symlink(), 'Destination symlink')
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        target = Path(tempfile.mkdtemp(prefix=stamp + '-', dir=dest))
        for name, expected in before.items():
            output = target / 'raw' / name
            output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copyfile(service / name, output)
            output.chmod(0o600)
            require(sha(output) == expected, 'Source changed while copying; snapshot incomplete')
        consistent = target / 'sqlite-consistent'
        consistent.mkdir(mode=0o700)
        with sqlite3.connect((service / 'state/jobs.sqlite').resolve().as_uri() + '?mode=ro', uri=True) as source:
            with sqlite3.connect(consistent / 'jobs.sqlite') as backup:
                source.backup(backup)
                require(backup.execute('pragma quick_check').fetchone()[0] == 'ok', 'SQLite quick_check failed')
                rows = backup.execute('select status,count(*) from jobs group by status').fetchall()
                if final_window:
                    require(not any(status in ('queued', 'running') and count for status, count in rows),
                            'Unfinished GPU jobs; preserve state and do not shelve')
        after, _ = collect(service)
        require(before == {p.relative_to(service).as_posix(): sha(p) for p in after},
                'Evidence changed; do not use incomplete snapshot')
        manifest = {'createdAt': datetime.now(timezone.utc).isoformat(),
                    'currentBootId': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                    'source': str(service), 'missingRequested': missing,
                    'jobStatusCounts': dict(rows), 'sqliteQuickCheck': 'ok',
                    'sha256': {p.relative_to(target).as_posix(): sha(p) for p in sorted(target.rglob('*')) if p.is_file()},
                    'historicalEvidence': True, 'currentQualification': False, 'finalWindowSnapshot': final_window}
        (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        print('GPU EVIDENCE SNAPSHOT SAVED: ' + str(target))
        print('Missing requested evidence: ' + json.dumps(missing))
        print('SQLite quick_check OK; jobs by status: ' + json.dumps(dict(rows)))
        print('Snapshot only; download to Mac and verify manifest SHA separately')
        if final_window:
            archive_path = dest / 'final-window-20261024.tgz'
            require(not archive_path.exists(), 'Final archive exists; reuse it, do not overwrite')
            with archive_path.open('xb') as output:
                os.chmod(archive_path, 0o600)
                with tarfile.open(fileobj=output, mode='w:gz') as archive:
                    archive.add(target, arcname=target.name)
            print('FINAL GPU ARCHIVE: ' + str(archive_path))
            print('ARCHIVE SHA256: ' + sha(archive_path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--final-window', action='store_true')
    args = parser.parse_args()
    global NAMES
    if args.final_window:
        NAMES += ('http-record-20261024.json', 'health-normal-20261024.json',
                  'health-qualification-20261024.json', 'config-window-20261024.json',
                  'proof-window-20261024')
    require(os.geteuid() == 0, 'Run sudo python3 on GPU VM')
    os.umask(0o077)
    state = subprocess.check_output(['systemctl', 'show', '--value', '-p', 'ActiveState', 'tatar-inference.service']).decode().strip()
    require(state in ('inactive', 'failed'), 'GPU HTTP service must be inactive; preserve evidence before new qualification')
    require(not RUNTIME.is_symlink() and not (RUNTIME / 'service').is_symlink(), 'Unexpected runtime symlink')
    if args.final_window:
        for name in ('http-record-20261024.json', 'proof-window-20261024'):
            require((RUNTIME / 'service' / name).exists(), 'Final window evidence missing: ' + name)
    snapshot(RUNTIME / 'service', DEST, final_window=args.final_window)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit('STOP: ' + str(exc))
