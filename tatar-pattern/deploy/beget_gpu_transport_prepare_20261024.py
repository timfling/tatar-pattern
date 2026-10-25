#!/usr/bin/env python3
"""Prepare a dedicated Beget tunnel key and historical host-key pin, offline.

Does not connect to GPU, edit env/sshd, create Bearer, or start containers.
"""
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path('/etc/tatar-pattern/gpu')
PIN = Path('/srv/tatar-pattern/releases/guest-20261020-1/payload/gpu/evidence/verified-known-hosts')
EXPECTED = 'SHA256:2uI6K/NhT8SghAVz0mgX3QBGgF1nQmV7yrqS4p2s2pk'
COMMENT = 'tp-beget-tunnel-20261024'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def fingerprint(public):
    fields = public.split()
    require(len(fields) >= 2 and fields[0] == 'ssh-ed25519', 'Expected ED25519 public key')
    return 'SHA256:' + base64.b64encode(hashlib.sha256(base64.b64decode(fields[1], validate=True)).digest()).decode().rstrip('=')


def prepare(root, pin):
    require(not root.is_symlink() and not pin.is_symlink(), 'Unexpected symlink')
    line = pin.read_text().strip()
    host, algorithm, blob = line.split()
    require(host == '195.209.221.75' and fingerprint(algorithm + ' ' + blob) == EXPECTED,
            'Historical GPU host key mismatch')
    if not root.exists():
        root.mkdir(mode=0o700)
    require(root.is_dir() and root.stat().st_uid == 0 and root.stat().st_mode & 0o077 == 0,
            'Secret directory must be root-owned 0700')
    names = ('id_ed25519', 'id_ed25519.pub', 'known_hosts', 'transport-prepared.json')
    paths = [root / name for name in names]
    require(all(not p.is_symlink() for p in paths), 'Unexpected secret symlink')
    exists = [p.exists() for p in paths]
    if any(exists):
        require(all(exists), 'Existing/partial GPU files; no overwrite, inspect metadata first')
        marker = json.loads(paths[3].read_text())
        require(marker.get('purpose') == COMMENT and marker.get('hostFingerprint') == EXPECTED,
                'Existing files are not this transport preparation; no overwrite')
        public = paths[1].read_text().strip()
        derived = subprocess.check_output(['ssh-keygen', '-y', '-P', '', '-f', str(paths[0])],
                                          stderr=subprocess.DEVNULL).decode().strip()
        require(public.split()[:2] == derived.split()[:2] and fingerprint(public) == marker['clientFingerprint'],
                'Tunnel key pair mismatch')
        require(paths[2].read_text() == line + '\n', 'known_hosts changed; no overwrite')
        require(paths[0].stat().st_uid == 10001 and paths[0].stat().st_mode & 0o077 == 0,
                'Private key owner/mode mismatch')
        print('Existing dedicated transport files verified; reused')
    else:
        with tempfile.TemporaryDirectory(prefix='.prepare-', dir=root) as tmp:
            key = Path(tmp) / 'id_ed25519'
            subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', COMMENT, '-f', str(key)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            public = key.with_suffix('.pub').read_text().strip()
            marker = {'purpose': COMMENT, 'clientFingerprint': fingerprint(public),
                      'hostFingerprint': EXPECTED, 'hostVerification': 'historical 2026-10-19; live check pending',
                      'restrictedGpuAccountInstalled': False}
            (Path(tmp) / 'known_hosts').write_text(line + '\n')
            (Path(tmp) / 'transport-prepared.json').write_text(json.dumps(marker, indent=2) + '\n')
            for name, uid, mode in [('id_ed25519', 10001, 0o600), ('id_ed25519.pub', 0, 0o644),
                                    ('known_hosts', 0, 0o444), ('transport-prepared.json', 0, 0o600)]:
                source = Path(tmp) / name
                os.chown(source, uid, 10001 if uid == 10001 else 0)
                source.chmod(mode)
                # No overwrite if a competing/manual preparation appeared.
                os.link(source, root / name)
        print('Dedicated transport files created')
    print('Client public key (safe to share): ' + public)
    print('Client fingerprint: ' + fingerprint(public))
    print('Historical GPU host fingerprint: ' + EXPECTED)
    print('TRANSPORT FILES PREPARED; live GPU host/account/SSH restrictions NOT VERIFIED')


def main():
    require(os.geteuid() == 0, 'Run as root on Beget VPS')
    os.umask(0o077)
    require(ROOT.parent.is_dir() and not ROOT.parent.is_symlink() and ROOT.parent.stat().st_uid == 0,
            'Expected root-owned /etc/tatar-pattern')
    with Path('/srv/tatar-pattern/staging-data/.maintenance.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prepare(ROOT, PIN)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit('STOP: ' + str(exc))
