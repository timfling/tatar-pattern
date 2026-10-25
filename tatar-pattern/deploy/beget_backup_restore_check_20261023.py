#!/usr/bin/env python3
"""Back up designated staging, then verify restore in a new private project."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

RELEASE = Path('/srv/tatar-pattern/releases/guest-20261020-1')
DATA = Path('/srv/tatar-pattern/staging-data')
ENVFILE = Path('/etc/tatar-pattern/staging.env')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    require(os.geteuid() == 0, 'Run as root on the VPS')
    os.umask(0o077)
    sys.path.insert(0, str(RELEASE / 'deploy'))
    import ops

    values = ops.read_env(ENVFILE)
    require(values['COMPOSE_PROJECT_NAME'] == 'tp-staging-20261023', 'Wrong project')
    require(values['DATA_ROOT'] == str(DATA), 'Wrong data root')
    require(values['RELEASE'] == 'guest-20261020-1', 'Wrong release')
    require(values.get('STAGING_MODE') == 'true', 'Staging required')
    require(values.get('AI_API_CONFIG') == 'false', 'AI must be disabled')
    require(values.get('CALENDAR_LOGS') == 'false', 'Unexpected log configuration')
    require(shutil.disk_usage(DATA).free >= 5 * 2**30, 'Need at least 5 GiB free before backup/restore')
    env = os.environ.copy()
    env.update(values)
    command = ['docker', 'compose', '--env-file', str(ENVFILE), '-p', values['COMPOSE_PROJECT_NAME'],
               '-f', str(RELEASE / 'deploy/compose.yml'),
               '-f', str(RELEASE / 'deploy/compose.staging.yml'),
               '-f', '/etc/tatar-pattern/staging-https.yml', '--profile', 'public']

    def dc(*args, capture=False, data=None, check=True):
        result = subprocess.run(command + list(args), cwd=RELEASE, env=env, input=data,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.stderr:
            sys.stderr.buffer.write(result.stderr)
            sys.stderr.buffer.flush()
        if not capture and result.stdout:
            sys.stdout.buffer.write(result.stdout)
            sys.stdout.buffer.flush()
        if check and result.returncode:
            raise RuntimeError('Staging Compose command failed; stop and send the output')
        return result.stdout if capture else None

    dc.calendar_logs = False
    dc.ai_expected_online = False
    with (DATA / '.maintenance.lock').open('a') as operation_lock:
        fcntl.flock(operation_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        dc('config', '--quiet')
        running = set(dc('ps', '--services', '--status', 'running', capture=True).decode().split())
        require(running == {'db', 'backend', 'frontend', 'proxy'}, 'Unexpected staging service set')
        print('BACKUP: briefly stopping writers for a consistent DB and storage copy', flush=True)
        source = ops.backup(dc, values)
        # backup() restarts the same containers. Wait for actual health with TLS config.
        dc('up', '-d', '--wait', '--no-build', 'db', 'backend', 'frontend', 'proxy')
        manifest = json.loads((source / 'manifest.json').read_text())
        require(manifest['counts']['users'] == 0, 'Legacy accounts require an independent erasure ledger')
        require(manifest['release'] == values['RELEASE'], 'Backup release mismatch')
        print('BACKUP COMPLETE: ' + str(source), flush=True)
        print('RESTORE CHECK: new private project, original hashes/counts, guest reset before API', flush=True)
        ops.restore_check(ENVFILE, values, source)
        curl = ['curl', '--fail', '--silent', '--show-error', '--max-time', '30',
                '--cacert', '/etc/tatar-pattern/staging-root-ca.crt',
                '--resolve', 'localhost:18080:127.0.0.1']
        health = subprocess.check_output(curl + ['https://localhost:18080/api/health'])
        require(json.loads(health).get('ok') is True, 'Main staging health failed')
        capabilities = subprocess.check_output(curl + ['https://localhost:18080/api/capabilities'])
        require(json.loads(capabilities).get('realUniqueElements') == 110, 'Main catalog count changed')
        (source / 'ISOLATED-RESTORE-PASS.json').write_text(json.dumps({
            'backup': str(source), 'mainStagingHealthy': True, 'mainCatalogElements': 110,
            'independentOffsiteBackup': 'NOT_YET_CONFIGURED',
        }, indent=2) + '\n')
        print('BACKUP + ISOLATED RESTORE PASS; main staging HTTPS/catalog110 OK', flush=True)
        print('Backup: ' + str(source), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('STOP: ' + str(exc), file=sys.stderr)
        print('Send the output to the deployment chat; do not reset or restore into staging.', file=sys.stderr)
        sys.exit(1)
