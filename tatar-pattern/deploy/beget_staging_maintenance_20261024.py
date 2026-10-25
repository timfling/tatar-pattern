#!/usr/bin/env python3
"""HTTPS staging maintenance v2; external to sealed guest-20261020-1.

No inference, worker start, env editing, VM control, or public deployment action.
AI runtime configuration is checked before every operation. Timers keep their paths.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tarfile

RELEASE = Path('/srv/tatar-pattern/releases/guest-20261020-1')
DATA = Path('/srv/tatar-pattern/staging-data')
ENVFILE = Path('/etc/tatar-pattern/staging.env')
INSTALLED = Path('/etc/tatar-pattern/staging-maintenance.py')
OLD_SHA = '7658e92e00337642e5b9a7990dc71baad206e52efe34efd2149d5dbe46310708'
UNITS = ('tatar-staging-backup', 'tatar-staging-cleanup', 'tatar-staging-retention')
BASE = {'db', 'backend', 'frontend', 'proxy'}
AI = {'ai-worker', 'gpu-tunnel'}
LEDGER = '.worker-drain-v2.json'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def atomic_json(path, value):
    temp = path.with_name(path.name + '.tmp-' + secrets.token_hex(4))
    try:
        with temp.open('x') as stream:
            os.chmod(temp, 0o600)
            json.dump(value, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def docker_json(*args):
    return json.loads(subprocess.check_output(['docker', *args], stderr=subprocess.DEVNULL))


def worker_info(dc):
    ids = dc('ps', '--all', '-q', 'ai-worker', capture=True).decode().split()
    require(len(ids) <= 1, 'Multiple worker containers; reconcile manually')
    if not ids:
        return None
    info = docker_json('inspect', ids[0])[0]
    require(info['Config']['Labels']['com.docker.compose.project'] == 'tp-staging-20261023',
            'Wrong worker project')
    return info


def identity(info):
    return {key: value for key, value in (
        ('containerId', info['Id']), ('startedAt', info['State']['StartedAt']),
        ('finishedAt', info['State']['FinishedAt']), ('exitCode', info['State']['ExitCode']))}


def stopped_worker_safe(dc, info, root=DATA):
    """A previous DRAINED from another container/run cannot authorize a snapshot."""
    if info is None:
        # Initial flat/adapter preparation: no worker has ever been created.
        raw = dc('exec', '-T', 'db', 'psql', '-U', 'tp', '-d', 'tatar_pattern', '-At', '-c',
                 "SELECT count(*) FROM ai_jobs WHERE state IN ('queued','submitting','polling')",
                 capture=True)
        require(int(raw.strip()) == 0, 'Missing worker with unfinished jobs; preserve DB/tunnel')
        return
    state = info['State']
    require(state['Status'] == 'exited' and state['ExitCode'] == 0 and not state.get('OOMKilled'),
            'Worker exit uncertain/nonzero; preserve DB/tunnel, no backup or automatic restart')
    path = root / LEDGER
    require(path.is_file() and not path.is_symlink(), 'No verified drain ledger for stopped worker')
    ledger = json.loads(path.read_text())
    require(ledger.get('confirmed') is True and ledger.get('identity') == identity(info),
            'Drain ledger does not match current worker run')


def drain(dc, info, root=DATA):
    require(info is not None and info['State']['Status'] == 'running', 'Worker is not running')
    since = datetime.now(timezone.utc).isoformat()
    atomic_json(root / LEDGER, {'confirmed': False, 'containerId': info['Id'], 'signalAfter': since})
    dc('stop', '-t', '960', 'ai-worker')
    after = worker_info(dc)
    require(after is not None and after['Id'] == info['Id'] and
            after['State']['StartedAt'] == info['State']['StartedAt'], 'Worker changed during drain')
    require(after['State']['Status'] == 'exited' and after['State']['ExitCode'] == 0 and
            not after['State'].get('OOMKilled'), 'Worker drain failed; keep DB/tunnel up')
    # Read exact immutable container ID, not aggregated/replaced Compose worker logs.
    logs = subprocess.check_output(['docker', 'logs', '--since', since, info['Id']],
                                   stderr=subprocess.STDOUT)
    require(b'AI_WORKER_DRAINED:' in logs, 'No fresh DRAINED; keep DB/tunnel up')
    atomic_json(root / LEDGER, {'confirmed': True, 'identity': identity(after), 'signalAfter': since,
                               'confirmedAt': datetime.now(timezone.utc).isoformat()})


def make_dc(values):
    require(values['COMPOSE_PROJECT_NAME'] == 'tp-staging-20261023', 'Wrong project')
    require(values['DATA_ROOT'] == str(DATA) and values['RELEASE'] == 'guest-20261020-1', 'Wrong data/release')
    require(values.get('STAGING_MODE') == 'true' and values.get('CALENDAR_LOGS') == 'false',
            'Expected closed staging with current Docker log driver')
    require(values.get('AI_API_CONFIG') in ('false', 'true'), 'Explicit AI_API_CONFIG required')
    cmd = ['docker', 'compose', '--env-file', str(ENVFILE), '-p', values['COMPOSE_PROJECT_NAME'],
           '-f', str(RELEASE / 'deploy/compose.yml')]
    if values['AI_API_CONFIG'] == 'true':
        cmd += ['-f', str(RELEASE / 'deploy/compose.ai-api.yml'), '--profile', 'ai']
    cmd += ['-f', str(RELEASE / 'deploy/compose.staging.yml'),
            '-f', '/etc/tatar-pattern/staging-https.yml', '--profile', 'public']
    # Optional final AI flags/budget override is external and inspected below.
    override = Path('/etc/tatar-pattern/staging-ai.yml')
    if values['AI_API_CONFIG'] == 'true' and override.exists():
        require(not override.is_symlink() and override.stat().st_uid == 0 and
                override.stat().st_mode & 0o077 == 0, 'AI override must be root-owned 0600')
        cmd += ['-f', str(override)]
    # Exclude ambient Compose controls and interpolation overrides.
    env = {key: os.environ[key] for key in ('PATH', 'HOME', 'LANG') if key in os.environ}
    env.update(values)

    def dc(*parts, capture=False, data=None, check=True):
        result = subprocess.run(cmd + list(parts), cwd=RELEASE, env=env, input=data,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        require(not check or result.returncode == 0, 'Staging Compose operation failed: ' + parts[0])
        if not capture and result.stdout:
            sys.stdout.buffer.write(result.stdout)
        return result.stdout if capture else None
    return dc


def validate_config(config, ai):
    services = config['services']
    for name, service in services.items():
        ports = service.get('ports', [])
        if name != 'proxy':
            require(not ports, 'Unexpected published service port')
        else:
            require(len(ports) == 1 and ports[0].get('host_ip') == '127.0.0.1' and
                    str(ports[0].get('published')) == '18080' and ports[0].get('target') == 443,
                    'HTTPS must bind only 127.0.0.1:18080 -> 443')
    api = services['backend']['environment']
    require(str(api.get('COOKIE_SECURE')).lower() == 'true' and
            api.get('CORS_ORIGINS') == 'https://localhost:18080' and
            str(api.get('ALLOW_FIXTURES')).lower() == 'false' and
            str(api.get('PUBLIC_GUEST_MODE')).lower() == 'true', 'HTTPS/guest configuration mismatch')
    require(str(api.get('GUEST_TTL_SECONDS')) == '86400', 'Guest TTL changed')
    if ai:
        worker = services['ai-worker']
        settings = worker['environment']
        for key in ('AI_MVP_ENABLED', 'GUEST_GPU_BUDGET', 'AI_GPU_BASE_URL', 'AI_GPU_TOKEN_FILE',
                    'AI_GPU_HTTP_PROOF_FILE', 'GPU_EXPECTED_WORKFLOW_VERSION', 'GPU_EXPECTED_MODEL_VERSION'):
            require(settings.get(key) == api.get(key), 'API/worker settings differ: ' + key)
        require(api['AI_GPU_BASE_URL'] == 'http://gpu-tunnel:18765' and
                not api.get('AI_GPU_TOKEN') and not settings.get('AI_GPU_TOKEN'), 'File-only Bearer required')
        require(worker.get('stop_grace_period') == '16m0s' or worker.get('stop_grace_period') == '960s',
                'Worker grace must be 960s')
        require(worker.get('restart') == 'no' and worker.get('stop_signal') == 'SIGTERM', 'Worker stop/restart mismatch')
        require(int(api['GUEST_GPU_BUDGET']) >= 0, 'Invalid GPU budget')
        require(str(api['AI_MVP_ENABLED']).lower() in ('true', 'false'), 'Invalid AI flag')


def snapshot(dc, values, ops, root=DATA):
    info = worker_info(dc)
    running = set(dc('ps', '--services', '--status', 'running', capture=True).decode().split())
    if info is None or info['State']['Status'] != 'running':
        stopped_worker_safe(dc, info, root)
    writers = [name for name in ('proxy', 'frontend', 'backend') if name in running]
    # This wrapper deliberately never starts worker; explicit resume is an owner step.
    # Flat services return after a verified drain. Tunnel remains up throughout backup.
    quiesced = False
    target = root / 'backups' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3))
    try:
        if writers:
            dc('stop', '-t', '120', *writers)
        if info is not None and info['State']['Status'] == 'running':
            drain(dc, info, root)
        else:
            stopped_worker_safe(dc, worker_info(dc), root)
        quiesced = True
        target.mkdir(parents=True, mode=0o700)
        dump = ops.pg(dc, 'pg_dump', '--format=custom', '--no-owner', '--no-acl')
        require(len(dump) >= 100, 'Empty DB dump')
        (target / 'database.dump').write_bytes(dump)
        hashes = ops.storage_hashes(root / 'storage')
        with tarfile.open(target / 'storage.tar.gz', 'w:gz') as archive:
            archive.add(root / 'storage', arcname='storage')
        manifest = {'version': 1, 'createdAt': target.name, 'release': values['RELEASE'],
                    'counts': ops.counts(dc), 'storageFiles': hashes,
                    'sha256': {name: ops.digest(target / name) for name in ('database.dump', 'storage.tar.gz')}}
        atomic_json(target / 'manifest.json', manifest)
        return target
    finally:
        if quiesced and writers:
            dc('start', '--wait', *writers)
        # Uncertain drain: leave admission closed, DB/tunnel intact. No dump/manifest.


def health(dc, ai):
    running = set(dc('ps', '--services', '--status', 'running', capture=True).decode().split())
    require(BASE <= running and running <= BASE | (AI if ai else set()), 'Unexpected running service set')
    info = worker_info(dc)
    if 'ai-worker' in running:
        require(ai and 'gpu-tunnel' in running, 'Running worker needs configured tunnel')
    else:
        stopped_worker_safe(dc, info)
    curl = ['curl', '--fail', '--silent', '--show-error', '--max-time', '30',
            '--cacert', '/etc/tatar-pattern/staging-root-ca.crt', '--resolve', 'localhost:18080:127.0.0.1']
    require(json.loads(subprocess.check_output(curl + ['https://localhost:18080/api/health'])).get('ok') is True,
            'HTTPS health failed')
    require(json.loads(subprocess.check_output(curl + ['https://localhost:18080/api/capabilities'])).get('realUniqueElements') == 110,
            'Catalog count changed')
    disk = shutil.disk_usage(DATA)
    require(disk.free >= 5 * 2**30 and disk.used / disk.total < .8, 'Disk warning')
    print('HTTPS/catalog110 OK; worker=' + ('running (not GPU readiness)' if 'ai-worker' in running else 'stopped/absent'))


def install():
    require(INSTALLED.is_file() and not INSTALLED.is_symlink(), 'Existing maintenance script required')
    current = INSTALLED.read_bytes()
    new = Path(__file__).read_bytes()
    require(hashlib.sha256(current).hexdigest() == OLD_SHA or current == new, 'Unknown installed script; no overwrite')
    if current == new:
        print('Maintenance v2 already installed')
        return
    for unit in UNITS:
        source = Path('/etc/systemd/system/' + unit + '.service').read_text()
        require('# Managed by beget_staging_maintenance_20261023.py' in source and
                str(INSTALLED) in source, 'Unexpected existing systemd unit')
        require(subprocess.run(['systemctl', 'is-active', '--quiet', unit + '.timer']).returncode == 0,
                'Existing timer must be active')
    old = INSTALLED.with_name('staging-maintenance.flat-20261023.py')
    if old.exists():
        require(old.read_bytes() == current, 'Rollback file conflict')
    else:
        with old.open('xb') as stream:
            stream.write(current)
        old.chmod(0o600)
    temp = INSTALLED.with_name('.staging-maintenance-v2.tmp')
    require(not temp.exists() and not temp.is_symlink(), 'Install temporary path exists')
    with temp.open('xb') as stream:
        stream.write(new)
        stream.flush()
        os.fsync(stream.fileno())
    temp.chmod(0o600)
    os.replace(temp, INSTALLED)
    print('MAINTENANCE V2 INSTALLED; schedules/env/containers unchanged; rollback script saved')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'install', 'status', 'backup', 'cleanup', 'retention', 'restore-check', 'stop-ai'))
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    require(os.geteuid() == 0, 'Run as root on Beget VPS')
    os.umask(0o077)
    sys.path.insert(0, str(RELEASE / 'deploy'))
    import ops
    import maintenance
    # Nonblocking lock: cleanup timer must not time out waiting behind a 960s drain.
    try:
        operation_lock = maintenance.lock(DATA, blocking=False)
    except BlockingIOError:
        if args.action in ('cleanup', 'retention'):
            print('SKIPPED: maintenance lock busy; retry on next timer tick')
            return
        raise RuntimeError('Maintenance lock busy; retry after current operation') from None
    with operation_lock:
        values = ops.read_env(ENVFILE)
        dc = make_dc(values)
        ai = values['AI_API_CONFIG'] == 'true'
        validate_config(json.loads(dc('config', '--format', 'json', capture=True)), ai)
        if args.action in ('check', 'install', 'status'):
            health(dc, ai)
            if args.action == 'install':
                install()
            elif args.action == 'status':
                for unit in UNITS:
                    require(subprocess.run(['systemctl', 'is-active', '--quiet', unit + '.timer']).returncode == 0,
                            'Inactive timer: ' + unit)
                    require(subprocess.check_output(['systemctl', 'show', '--value', '-p', 'Result', unit + '.service']).strip() == b'success',
                            'Service failed: ' + unit)
                marker = json.loads((DATA / 'backups/.local-backup-ok.json').read_text())
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(marker['completedAt'])).total_seconds()
                require(0 <= age <= 26 * 3600 and (Path(marker['backup']) / 'manifest.json').is_file(), 'Recent backup missing')
                print('LOCAL MAINTENANCE STATUS PASS; Mac download manual; GPU readiness not asserted')
            else:
                print('MAINTENANCE V2 CHECK PASS; no changes')
        elif args.action == 'cleanup':
            dc('run', '--rm', '--no-deps', '-T', 'backend', 'python', '-m', 'scripts.guest_maintenance', 'cleanup')
            status = json.loads(dc('run', '--rm', '--no-deps', '-T', 'backend', 'python', '-m', 'scripts.guest_maintenance', 'status', capture=True))
            require(status['pendingGuestFiles'] == 0, 'Pending guest file deletion')
            print(json.dumps(status))
        elif args.action == 'retention':
            print(json.dumps({'localRemoved': maintenance.local_retention(DATA)}))
        elif args.action == 'stop-ai':
            require(ai, 'AI adapter configuration required')
            dc('stop', '-t', '120', 'backend')
            info = worker_info(dc)
            if info is not None and info['State']['Status'] == 'running':
                drain(dc, info)
            else:
                stopped_worker_safe(dc, info)
            dc('stop', '-t', '15', 'gpu-tunnel')
            dc('start', '--wait', 'backend')
            print('AI STOPPED; flat API restored; DB kept; VM billing unchanged')
        elif args.action == 'backup':
            health(dc, ai)
            target = snapshot(dc, values, ops)
            health(dc, ai)
            atomic_json(DATA / 'backups/.local-backup-ok.json', {
                'completedAt': datetime.now(timezone.utc).isoformat(), 'backup': str(target), 'offsite': False})
            print('LOCAL BACKUP PASS: ' + str(target) + '; worker stays stopped; explicit resume required')
        else:
            require(args.source is not None, '--source required')
            source = args.source.resolve()
            require(source.parent == DATA / 'backups' and not args.source.is_symlink(), 'Use designated local backup set')
            # Sealed restore helper forces AI=false, private new project, reset before API.
            ops.restore_check(ENVFILE, values, source)
            health(dc, ai)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('STOP: ' + str(exc), file=sys.stderr)
        sys.exit(1)
