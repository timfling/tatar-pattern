#!/usr/bin/env python3
"""Nightly coordinated backup, then encrypted independent copy. Run as root."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
from ops import HERE, read_env, compose, backup
from maintenance import TAG, lock, local_retention, remote_retention

def main():
    os.umask(0o077)
    p = argparse.ArgumentParser()
    p.add_argument('--env', type=Path, default=HERE/'.env')
    args = p.parse_args()
    for name in ('RESTIC_REPOSITORY', 'RESTIC_PASSWORD_FILE'):
        if not os.getenv(name):
            raise RuntimeError(name + ' must be in protected systemd environment')
    values = read_env(args.env)
    operation_lock = lock(values['DATA_ROOT'])
    local_retention(Path(values['DATA_ROOT']))
    remote_retention()
    target = backup(compose(args.env, values, public=values.get('STAGING_MODE') != 'true'), values)
    # No credentials in command arguments. Credentials live in env/protected files.
    subprocess.run(['restic','backup',str(target),'--tag',TAG], check=True)
    (target.parent/'.offsite-ok').write_text(datetime.now(timezone.utc).isoformat())
    # Keep two complete local sets only after successful independent copy.
    complete = sorted(x.parent for x in target.parent.glob('*/manifest.json'))
    for old in complete[:-2]:
        shutil.rmtree(old)
    print('OFFSITE PASS; local retention 2 complete sets')

if __name__ == '__main__':
    main()
