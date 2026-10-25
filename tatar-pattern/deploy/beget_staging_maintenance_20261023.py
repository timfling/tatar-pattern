#!/usr/bin/env python3
"""Install/run project-specific local maintenance for the verified HTTPS staging."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

RELEASE = Path('/srv/tatar-pattern/releases/guest-20261020-1')
DATA = Path('/srv/tatar-pattern/staging-data')
ENVFILE = Path('/etc/tatar-pattern/staging.env')
INSTALLED = Path('/etc/tatar-pattern/staging-maintenance.py')
MARKER = '# Managed by beget_staging_maintenance_20261023.py'
UNITS = ('tatar-staging-backup', 'tatar-staging-cleanup', 'tatar-staging-retention')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'backup', 'cleanup', 'retention', 'status'))
    args = parser.parse_args()
    require(os.geteuid() == 0, 'Run in the VPS root session')
    os.umask(0o077)
    sys.path.insert(0, str(RELEASE / 'deploy'))
    import ops
    import maintenance

    values = ops.read_env(ENVFILE)
    require(values['COMPOSE_PROJECT_NAME'] == 'tp-staging-20261023', 'Wrong project')
    require(values['DATA_ROOT'] == str(DATA), 'Wrong data root')
    require(values['RELEASE'] == 'guest-20261020-1', 'Wrong release')
    require(values.get('STAGING_MODE') == 'true', 'Staging mode required')
    require(values.get('AI_API_CONFIG') == 'false', 'AI must remain disabled')
    require(values.get('CALENDAR_LOGS') == 'false', 'Unexpected logging configuration')
    env = os.environ.copy()
    env.update(values)
    command = ['docker', 'compose', '--env-file', str(ENVFILE), '-p', values['COMPOSE_PROJECT_NAME'],
               '-f', str(RELEASE / 'deploy/compose.yml'),
               '-f', str(RELEASE / 'deploy/compose.staging.yml'),
               '-f', '/etc/tatar-pattern/staging-https.yml', '--profile', 'public']

    def dc(*parts, capture=False, data=None, check=True):
        result = subprocess.run(command + list(parts), env=env, cwd=RELEASE, input=data,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.stderr:
            sys.stderr.buffer.write(result.stderr)
            sys.stderr.buffer.flush()
        if not capture and result.stdout:
            sys.stdout.buffer.write(result.stdout)
            sys.stdout.buffer.flush()
        require(not check or result.returncode == 0, 'Staging Compose command failed')
        return result.stdout if capture else None

    dc.calendar_logs = False
    dc.ai_expected_online = False

    def health():
        require(set(dc('ps', '--services', '--status', 'running', capture=True).decode().split())
                == {'db', 'backend', 'frontend', 'proxy'}, 'Unexpected running service set')
        common = ['curl', '--fail', '--silent', '--show-error', '--max-time', '30',
                  '--cacert', '/etc/tatar-pattern/staging-root-ca.crt',
                  '--resolve', 'localhost:18080:127.0.0.1']
        info = json.loads(subprocess.check_output(common + ['https://localhost:18080/api/health']))
        require(info.get('ok') is True, 'HTTPS API health failed')
        caps = json.loads(subprocess.check_output(common + ['https://localhost:18080/api/capabilities']))
        require(caps.get('realUniqueElements') == 110, 'Catalog count changed')
        disk = shutil.disk_usage(DATA)
        require(disk.free >= 5 * 2**30 and disk.used / disk.total < .8,
                'Disk warning: less than 5 GiB free or at least 80% used')
        print(f'HTTPS/catalog110 OK; disk free {disk.free // 2**20} MiB', flush=True)

    if args.action == 'install':
        dc('config', '--quiet')
        health()
        schedules = {
            'backup': 'OnCalendar=*-*-* 03:15:00 Europe/Moscow\nPersistent=true',
            'cleanup': 'OnBootSec=60s\nOnUnitActiveSec=60s',
            'retention': 'OnBootSec=2min\nOnUnitActiveSec=1h',
        }
        files = {}
        for action, schedule in schedules.items():
            unit = 'tatar-staging-' + action
            timeout = '120' if action == 'cleanup' else '1h'
            files[Path('/etc/systemd/system') / (unit + '.service')] = (
                f'{MARKER}\n[Unit]\nDescription=Tatar Pattern staging {action} (local VPS)\n'
                'Requires=docker.service\nAfter=docker.service\n'
                f'[Service]\nType=oneshot\nUMask=0077\nExecStart=/usr/bin/python3 -B {INSTALLED} {action}\n'
                f'TimeoutStartSec={timeout}\n')
            files[Path('/etc/systemd/system') / (unit + '.timer')] = (
                f'{MARKER}\n[Unit]\nDescription=Tatar Pattern staging {action} schedule\n'
                f'[Timer]\n{schedule}\nAccuracySec=1s\n'
                '[Install]\nWantedBy=timers.target\n')
        # Refuse to overwrite units installed by a different administrator/workflow.
        for path in files:
            require(not path.exists() or MARKER in path.read_text(), 'Unmanaged unit already exists: ' + str(path))
        if INSTALLED.exists():
            require(INSTALLED.read_bytes() == Path(__file__).read_bytes(), 'Different maintenance script already installed')
        else:
            shutil.copyfile(__file__, INSTALLED)
        INSTALLED.chmod(0o600)
        for path, source in files.items():
            path.write_text(source)
            path.chmod(0o644)
        subprocess.run(['systemd-analyze', 'verify', *map(str, files)], check=True)
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        # Execute actual service units once before enabling their timers.
        for unit in ('tatar-staging-cleanup', 'tatar-staging-retention', 'tatar-staging-backup'):
            print('TEST SERVICE: ' + unit, flush=True)
            subprocess.run(['systemctl', 'start', unit + '.service'], check=True)
            result = subprocess.check_output(['systemctl', 'show', '--value', '-p', 'Result', unit + '.service']).decode().strip()
            require(result == 'success', unit + ': ' + result)
        subprocess.run(['systemctl', 'enable', '--now', *[unit + '.timer' for unit in UNITS]], check=True)
        subprocess.run(['systemctl', 'list-timers', '--all', 'tatar-staging-*', '--no-pager'], check=True)
        for unit in UNITS:
            subprocess.run(['systemctl', 'is-active', '--quiet', unit + '.timer'], check=True)
        health()
        subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{.Name}}  {{.MemUsage}}  {{.CPUPerc}}',
                        *['tp-staging-20261023-' + name + '-1' for name in ('db', 'backend', 'frontend', 'proxy')]], check=True)
        print('STAGING LOCAL TIMERS PASS; automatic offsite transfer is NOT configured', flush=True)
        return

    # Same advisory file lock as ops, import and restore-check scripts.
    with maintenance.lock(str(DATA)):
        if args.action == 'cleanup':
            dc('run', '--rm', '--no-deps', '-T', 'backend', 'python', '-m', 'scripts.guest_maintenance', 'cleanup')
            status = json.loads(dc('run', '--rm', '--no-deps', '-T', 'backend', 'python', '-m',
                                   'scripts.guest_maintenance', 'status', capture=True))
            require(status['pendingGuestFiles'] == 0, 'Guest files pending deletion; inspect cleanup service journal')
            print(json.dumps(status), flush=True)
        elif args.action == 'retention':
            print(json.dumps({'localRemoved': maintenance.local_retention(DATA),
                              'scope': 'VPS project backups and completed restore copies; 7 days'}), flush=True)
        elif args.action == 'backup':
            health()
            target = ops.backup(dc, values)
            dc('up', '-d', '--wait', '--no-build', 'db', 'backend', 'frontend', 'proxy')
            health()
            (DATA / 'backups/.local-backup-ok.json').write_text(json.dumps({
                'completedAt': datetime.now(timezone.utc).isoformat(), 'backup': str(target),
                'offsite': False}, indent=2) + '\n')
            print('LOCAL BACKUP PASS: ' + str(target), flush=True)
        else:
            health()
            for unit in UNITS:
                subprocess.run(['systemctl', 'is-active', '--quiet', unit + '.timer'], check=True)
                result = subprocess.check_output(['systemctl', 'show', '--value', '-p', 'Result', unit + '.service']).decode().strip()
                require(result == 'success', unit + ': ' + result)
            marker = json.loads((DATA / 'backups/.local-backup-ok.json').read_text())
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(marker['completedAt'])).total_seconds()
            require(0 <= age <= 26 * 3600, 'No local backup success in last 26 hours')
            require((Path(marker['backup']) / 'manifest.json').is_file(), 'Last completed backup missing')
            print('LOCAL MAINTENANCE STATUS PASS; offsite copy still manual', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('STOP: ' + str(exc), file=sys.stderr)
        print('Inspect: journalctl -u tatar-staging-backup -u tatar-staging-cleanup -u tatar-staging-retention -n 60 --no-pager', file=sys.stderr)
        sys.exit(1)
