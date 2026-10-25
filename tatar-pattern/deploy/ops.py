#!/usr/bin/env python3
"""Deploy operations. No source .env loading, no passwords in argv/output."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import ipaddress
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
MIN_NEXT_VERSION = (16, 3, 8)

def validate_next_version(version, expected):
    # Only exact stable versions are reviewed; ranges/prereleases fail closed.
    for label, value in (('runtime', version), ('source', expected)):
        if not isinstance(value, str) or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', value):
            raise RuntimeError(f'Invalid {label} Next version: exact stable version required')
    if tuple(map(int, version.split('.'))) < MIN_NEXT_VERSION:
        raise RuntimeError('Publication blocked: Next must be >=16.3.8; repeat audit/build')
    if version != expected:
        raise RuntimeError('Built Next version differs from source; use reviewed exact release image')

def check_frontend(release, platform='linux/amd64'):
    image = 'tatar-pattern-frontend:' + release
    metadata = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image]))[0]
    actual = metadata['Os'] + '/' + metadata['Architecture']
    if actual != platform:
        raise RuntimeError(f'Frontend platform {actual} differs from required {platform}')
    # Use the inspected immutable ID for both the check and its evidence.
    version = subprocess.check_output(['docker', 'run', '--rm', '--network', 'none',
                                      '--platform', platform, metadata['Id'], 'node', '-p',
                                      "require('next/package.json').version"]).decode().strip()
    expected = json.loads((HERE.parent/'frontend/package.json').read_text())['dependencies']['next']
    validate_next_version(version, expected)
    result = dict(image=image, imageId=metadata['Id'], platform=actual,
                  sourceNext=expected, runtimeNext=version, minimumNext='16.3.8')
    print(json.dumps(result))
    return result

def read_env(path):
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, value = line.split('=', 1)
        if not re.fullmatch(r'[A-Z_]+', key) or any(x in value for x in '\n\r$\"\''):
            raise ValueError('Use simple unquoted env values, no interpolation')
        values[key] = value
    if not re.fullmatch(r'[a-f0-9]{64}', values.get('POSTGRES_PASSWORD', '')):
        raise ValueError('POSTGRES_PASSWORD must be 64 random hex characters')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,60}', values['COMPOSE_PROJECT_NAME']):
        raise ValueError('Invalid project name')
    if not Path(values['DATA_ROOT']).is_absolute():
        raise ValueError('DATA_ROOT must be absolute')
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+', values['RELEASE']):
        raise ValueError('Invalid release')
    return values

def compose(envfile, values, local=False, public=False):
    # Ambient variables must not override the selected isolated/prod config.
    env = os.environ.copy()
    for k in read_env(envfile):
        env.pop(k, None)
    env.update(values)
    cmd = ['docker', 'compose', '--env-file', str(envfile), '-p', values['COMPOSE_PROJECT_NAME'], '-f', str(HERE/'compose.yml')]
    if values.get('AI_API_CONFIG') == 'true':
        cmd += ['-f', str(HERE/'compose.ai-api.yml'), '--profile', 'ai']
    if values.get('CALENDAR_LOGS') == 'true':
        cmd += ['-f', str(HERE/'compose.logs.yml')]
    if values.get('STAGING_MODE') == 'true':
        if public or not values['COMPOSE_PROJECT_NAME'].startswith('tp-staging-'):
            raise ValueError('Staging must use a separate tp-staging project and no public override')
        cmd += ['-f', str(HERE/'compose.staging.yml'), '--profile', 'public']
    elif local:
        cmd += ['-f', str(HERE/'compose.local.yml'), '--profile', 'public']
    elif public:
        cmd += ['-f', str(HERE/'compose.public.yml'), '--profile', 'public']
    def run(*args, capture=False, data=None, check=True):
        return subprocess.run(cmd + list(args), env=env, input=data, stdout=subprocess.PIPE if capture else None,
                              check=check).stdout
    run.calendar_logs = values.get('CALENDAR_LOGS') == 'true'
    run.ai_expected_online = values.get('AI_EXPECTED_ONLINE') == 'true'
    return run

def pg(dc, tool, *args, data=None):
    # Password expands inside the db container, never on the host or in argv.
    return dc('exec', '-T', 'db', 'sh', '-c', 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec "$@"',
              'sh', tool, '-U', 'tp', '-d', 'tatar_pattern', *args, capture=True, data=data)

def counts(dc):
    return json.loads(pg(dc, 'psql', '-At', '-c', "SELECT json_build_object('users',(SELECT count(*) FROM users),'generations',(SELECT count(*) FROM generations),'elements',(SELECT count(*) FROM elements),'migrations',(SELECT count(*) FROM schema_migrations))"))

def storage_hashes(root):
    files = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise ValueError('Storage symlinks not allowed in backup')
        if p.is_file():
            with p.open('rb') as f:
                files[str(p.relative_to(root))] = hashlib.file_digest(f, 'sha256').hexdigest()
    return files

def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def stop_ai_worker(dc):
    """Tunnel and PostgreSQL must stay up. Refuse further shutdown on uncertain exit."""
    since = datetime.now(timezone.utc).isoformat()
    dc('stop', '-t', '960', 'ai-worker')
    raw = dc('ps', '--all', '--format', 'json', 'ai-worker', capture=True).decode().strip()
    try:
        try:
            rows = json.loads(raw)
            rows = rows if isinstance(rows, list) else [rows]
        except json.JSONDecodeError:
            rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
        if len(rows) != 1 or rows[0]['State'] != 'exited' or rows[0]['ExitCode'] != 0:
            raise ValueError('Unclean worker exit')
        if getattr(dc, 'calendar_logs', False) is True:
            logs = calendar_worker_logs(rows[0]['Name'], since)
        else:
            logs = dc('logs', '--no-color', '--since', since, 'ai-worker', capture=True)
        if b'AI_WORKER_DRAINED:' not in logs:
            raise ValueError('No current drain acknowledgement')
    except (ValueError, KeyError, TypeError):
        raise RuntimeError('Worker drain unconfirmed; keep tunnel/DB up, reconcile ai_jobs before proceeding') from None

def calendar_worker_logs(container_name, since, log_root=Path('/var/log/tatar-pattern')):
    """Read only this worker's fresh records; syslog Docker cache is disabled."""
    cutoff = datetime.fromisoformat(since)
    result = []
    for path in sorted(log_root.glob('runtime-????-??-??.log')):
        if path.name[8:18] < cutoff.astimezone(timezone.utc).date().isoformat():
            continue
        if path.is_symlink():
            raise RuntimeError('Unexpected log symlink')
        with path.open() as stream:
            for line in stream:
                parts = line.split(' ', 2)
                if len(parts) != 3 or parts[1] != 'tp-'+container_name:
                    continue
                try:
                    if datetime.fromisoformat(parts[0].replace('Z', '+00:00')) >= cutoff:
                        result.append(parts[2])
                except ValueError:
                    continue
    return ''.join(result).encode()


def stop_ai(dc):
    """Maintenance stop: close API admission, worker drain, then tunnel."""
    dc('stop', '-t', '120', 'backend')
    running = dc('ps', '--services', '--status', 'running', capture=True).decode().split()
    if 'ai-worker' not in running:
        raise RuntimeError('Worker not running: inspect persisted state before stopping tunnel')
    stop_ai_worker(dc)
    dc('stop', '-t', '15', 'gpu-tunnel')


def backup(dc, values):
    root = Path(values['DATA_ROOT'])
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3)
    target = root/'backups'/stamp
    target.mkdir(parents=True, mode=0o700)
    # Save only services that were actually running, including optional proxy.
    running = dc('ps', '--services', '--status', 'running', capture=True).decode().split()
    writers = [x for x in ('proxy', 'frontend', 'backend', 'ai-worker') if x in running]
    quiesced = False
    try:
        admission = [x for x in writers if x != 'ai-worker']
        if admission:
            dc('stop', '-t', '120', *admission)
        if 'ai-worker' in writers:
            stop_ai_worker(dc)
        quiesced = True
        dump = pg(dc, 'pg_dump', '--format=custom', '--no-owner', '--no-acl')
        (target/'database.dump').write_bytes(dump)
        if len(dump) < 100:
            raise RuntimeError('Empty database dump')
        file_hashes = storage_hashes(root/'storage')
        with tarfile.open(target/'storage.tar.gz', 'w:gz') as archive:
            archive.add(root/'storage', arcname='storage')
        manifest = {'version': 1, 'createdAt': stamp, 'release': values['RELEASE'],
                    'counts': counts(dc), 'storageFiles': file_hashes,
                    'sha256': {p.name: digest(p) for p in (target/'database.dump', target/'storage.tar.gz')}}
        (target/'manifest.json').write_text(json.dumps(manifest, indent=2))
        for p in target.iterdir():
            p.chmod(0o600)
        print(target)
        return target
    finally:
        if quiesced and writers:
            dc('start', *writers)
        # No automatic restart after an unconfirmed stop/drain. Tunnel and DB remain up.
        # An incomplete set has no manifest and is never eligible for restore/offsite.

def restore_check(envfile, values, source):
    manifest = json.loads((source/'manifest.json').read_text())
    for name, sha in manifest['sha256'].items():
        if name not in ('database.dump', 'storage.tar.gz') or digest(source/name) != sha:
            raise ValueError('Backup checksum mismatch')
    # Always new project and new paths; no public override, no ports.
    scratch = Path(values['DATA_ROOT'])/'restore-checks'
    scratch.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='restore-', dir=scratch))
    isolated = dict(values, COMPOSE_PROJECT_NAME='tp-restore-'+secrets.token_hex(4),
                    DATA_ROOT=str(root), POSTGRES_PASSWORD=secrets.token_hex(32),
                    AI_API_CONFIG='false', CALENDAR_LOGS='false', STAGING_MODE='false')
    network_ids = subprocess.check_output(['docker', 'network', 'ls', '-q']).decode().split()
    existing = json.loads(subprocess.check_output(['docker', 'network', 'inspect', *network_ids]))
    used = [ipaddress.ip_network(c['Subnet']) for n in existing for c in (n.get('IPAM', {}).get('Config') or []) if c.get('Subnet')]
    for octet in range(100, 250):
        subnet = ipaddress.ip_network(f'172.30.{octet}.0/24')
        if not any(subnet.overlaps(x) for x in used if x.version == 4):
            isolated.update(EDGE_SUBNET=str(subnet), PROXY_IP=f'172.30.{octet}.10')
            break
    else:
        raise RuntimeError('No free isolated restore subnet; choose manually')
    dc = compose(envfile, isolated)
    for name in ('storage', 'migration-backups'):
        (root/name).mkdir()
    try:
        with tarfile.open(source/'storage.tar.gz') as archive:
            archive.extractall(root, filter='data')
        if storage_hashes(root/'storage') != manifest['storageFiles']:
            raise ValueError('Restored storage hash mismatch')
        if os.geteuid() == 0:
            for p in [root/'storage', *list((root/'storage').rglob('*')), root/'migration-backups']:
                os.chown(p, 10001, 10001)
        dc('up', '-d', '--wait', 'db')
        pg(dc, 'pg_restore', '--exit-on-error', '--no-owner', '--no-acl', data=(source/'database.dump').read_bytes())
        if counts(dc) != manifest['counts']:
            raise ValueError('Restored row counts mismatch')
        if manifest['counts']['users']:
            raise RuntimeError('Legacy accounts found: latest independent erasure ledger must be replayed offline; keep restored copy closed')
        dc('run', '--rm', '--no-deps', 'backend', 'python', '-m', 'scripts.migrate')
        dc('run', '--rm', '--no-deps', 'backend', 'python', '-m', 'scripts.guest_maintenance',
           'reset-restored', '--offline-restore', '--designated-operation', isolated['COMPOSE_PROJECT_NAME'])
        status = json.loads(dc('run', '--rm', '--no-deps', '-T', 'backend', 'python', '-m',
                              'scripts.guest_maintenance', 'status', capture=True))
        if any(status[k] for k in ('guestProcesses', 'guestGenerations', 'pendingGuestFiles')):
            raise RuntimeError('Restored guest zone not empty; keep offline')
        dc('up', '-d', '--wait', 'backend')
        print('RESTORE PASS: original bytes/counts verified, guest reset before API, no worker or published ports')
        (root/'RESTORE-PASS.json').write_text(json.dumps({'backup':source.name,'checks':manifest['counts'], 'guestAfterReset':status}))
    finally:
        dc('down', '--remove-orphans')  # bind directories preserved; never -v
        (root/'CLEANUP-ALLOWED').write_text(datetime.now(timezone.utc).isoformat())
        print('Isolated restore evidence/data preserved:', root)

def health(dc, root, repair=False):
    services = dc('ps', '--services', '--status', 'running', capture=True).decode().split()
    errors = []
    if getattr(dc, 'ai_expected_online', False) is True:
        for name in ('ai-worker', 'gpu-tunnel'):
            if name not in services:
                errors.append(name + ' unavailable during the agreed GPU availability window')
        if 'ai-worker' in services:
            for command in (('python', '/opt/deploy/ai-readiness.py'),
                            ('python', '-m', 'scripts.gpu_proof_status')):
                try:
                    dc('exec', '-T', 'ai-worker', *command)
                except subprocess.CalledProcessError:
                    errors.append('GPU readiness/proof failed; new AI unavailable, no inference retry')
        if subprocess.run(['systemctl', 'is-active', '--quiet', 'tatar-proof.timer']).returncode:
            errors.append('tatar-proof.timer inactive during expected AI availability')
        result = subprocess.check_output(['systemctl', 'show', '--value', '-p', 'Result', 'tatar-proof.service']).decode().strip()
        if result != 'success':
            errors.append('GPU proof renewal failed: ' + result)
    # Size rotation alone has no calendar guarantee; check the actual timer pipeline.
    if getattr(dc, 'calendar_logs', False) is True:
        for unit in ('tatar-logs.service', 'tatar-guest-cleanup.timer', 'tatar-retention.timer', 'tatar-backup.timer'):
            if subprocess.run(['systemctl', 'is-active', '--quiet', unit]).returncode:
                errors.append(unit + ' inactive')
        for unit in ('tatar-guest-cleanup.service', 'tatar-retention.service', 'tatar-backup.service'):
            result = subprocess.check_output(['systemctl', 'show', '--value', '-p', 'Result', unit]).decode().strip()
            if result != 'success':
                errors.append(unit + ': ' + result)
    for name in ('db', 'backend', 'frontend'):
        if name not in services:
            errors.append(name + ' not running')
    for name in services:
        cid = dc('ps', '-q', name, capture=True).decode().strip()
        status = subprocess.check_output(['docker','inspect','--format','{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}',cid]).decode().strip()
        if status != 'healthy':
            errors.append(name + ': ' + status)
            if repair and status == 'unhealthy' and name in ('backend','frontend','proxy'):
                dc('restart', name)  # once per 5-minute monitor run; DB never auto-restarted
    disk = shutil.disk_usage(root)
    used = 100 * (1 - disk.free/disk.total)
    print(f'Disk used {used:.1f}%, free {disk.free//2**20} MiB')
    if used >= 80 or disk.free < 5*2**30:
        errors.append('Disk warning: >=80% or <5 GiB free; stop imports/builds, investigate')
    completed = sorted((root/'backups').glob('*/manifest.json'))
    if not completed or datetime.now(timezone.utc).timestamp() - completed[-1].stat().st_mtime > 26*3600:
        errors.append('No local completed backup in last 26h')
    marker = root/'backups'/'.offsite-ok'
    if not marker.exists() or datetime.now(timezone.utc).timestamp() - marker.stat().st_mtime > 26*3600:
        errors.append('No successful independent backup in last 26h')
    if errors:
        raise RuntimeError('; '.join(errors))
    print('HEALTH PASS')

def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', type=Path, default=HERE/'.env')
    parser.add_argument('--local', action='store_true')
    parser.add_argument('action', choices=['init','config','build','check-frontend','up-internal','up-staging','migrate','publish','status','backup','restore-check','health','monitor','fixtures','up-local','down-local','stop-ai'])
    parser.add_argument('--platform', choices=['linux/amd64', 'linux/arm64'], default='linux/amd64', help='Build/check platform; publication always requires linux/amd64')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--confirm-public', action='store_true')
    args = parser.parse_args()
    envfile = args.env.resolve()
    if args.action == 'init':
        values = (HERE/'.env.example').read_text().replace('REPLACE_WITH_64_HEX', secrets.token_hex(32))
        with envfile.open('x') as f:
            f.write(values)
        envfile.chmod(0o600)
        print('Created protected config; fill DOMAIN, ACME_EMAIL, DATA_ROOT, RELEASE before use')
        return
    values = read_env(envfile)
    # Timers and manual mutations share one project lock. Lock released on exit.
    if args.action in ('migrate', 'backup', 'restore-check', 'stop-ai', 'publish'):
        from maintenance import lock
        operation_lock = lock(values['DATA_ROOT'])
    if args.action == 'build':
        values['DOCKER_DEFAULT_PLATFORM'] = args.platform
    if args.local and (not values['COMPOSE_PROJECT_NAME'].startswith('tp-deploy-check-') or not Path(values['DATA_ROOT']).is_relative_to(HERE/'local-check')):
        raise ValueError('Local override requires dedicated tp-deploy-check project and deploy/local-check data')
    if not args.local and args.action == 'publish':
        if not args.confirm_public or values['DOMAIN'] == 'replace.example':
            raise ValueError('Owner authorization, real domain, budget and legal gate required before publish')
    dc = compose(envfile, values, local=args.local, public=args.action == 'publish' and not args.local)
    action = args.action
    if action in ('fixtures','up-local','down-local') and not args.local:
        raise ValueError('Test actions require --local')
    if action == 'fixtures':
        dc('run','--rm','--no-deps','backend','python','-m','scripts.fixtures','--storage-root','/data/storage','--confirm-test-fixtures')
    elif action == 'up-local':
        dc('up','-d','--wait')
    elif action == 'down-local':
        dc('down','--remove-orphans')
    elif action == 'config':
        dc('config', '--quiet')  # never print fully interpolated secrets
    elif action == 'build':
        dc('build', 'backend')
        dc('build', 'frontend')  # serial builds on small pilot VPS
        check_frontend(values['RELEASE'], args.platform)
    elif action == 'check-frontend':
        check_frontend(values['RELEASE'], args.platform)
    elif action == 'up-internal':
        dc('up', '-d', '--wait', 'db')
    elif action == 'up-staging':
        if values.get('STAGING_MODE') != 'true':
            raise ValueError('up-staging requires STAGING_MODE=true')
        dc('up', '-d', '--wait', '--no-build', 'db', 'backend', 'frontend', 'proxy')
    elif action == 'migrate':
        dc('run', '--rm', '--no-deps', 'backend', 'python', '-m', 'scripts.migrate')
    elif action == 'publish':
        if not args.local:
            check_frontend(values['RELEASE'])
        dc('up', '-d', '--wait', '--no-build')
    elif action == 'status':
        dc('ps')
    elif action == 'stop-ai':
        stop_ai(dc)
    elif action == 'backup':
        backup(dc, values)
    elif action == 'restore-check':
        if not args.source:
            parser.error('--source is required')
        restore_check(envfile, values, args.source.resolve())
    else:
        health(dc, Path(values['DATA_ROOT']), repair=action == 'monitor')

if __name__ == '__main__':
    main()
