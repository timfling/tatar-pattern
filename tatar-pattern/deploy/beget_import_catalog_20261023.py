#!/usr/bin/env python3
"""Owner-authorized catalog110 import into the designated closed Beget staging."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

RELEASE = Path('/srv/tatar-pattern/releases/guest-20261020-1')
DATA = Path('/srv/tatar-pattern/staging-data')
OPERATION = 'beget-staging-catalog110-20261023'
OP = Path('/srv/tatar-pattern/operations') / OPERATION
MANIFEST_SHA = 'ea30581958a83d5df4f362a1274c7cf868fc7c1548a30e79cae4bb044a87f3aa'
ARCHIVE_SHA = 'cf37ded31f833ef353bd1eb16ede20251c5eab10d614e2e4c5e14410bae023c2'
PENDING_SHA = 'ed7451c59a7392b7f87f971617183cb4344ccae88511f1e0a6f8a0452b764ff6'
APPROVAL_AT = '2026-10-23T17:03:18+00:00'
APPROVAL_TEXT = ('Да, подтверждаю. Сейчас важно загрузить все и полноценно '
                 'протестировать работоспособность, потому что времени до конца '
                 'отчетности не так много.')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    require(os.geteuid() == 0, 'Run in the VPS root SSH session')
    os.umask(0o077)
    sys.path.insert(0, str(RELEASE / 'deploy'))
    from ops import read_env

    envfile = Path('/etc/tatar-pattern/staging.env')
    values = read_env(envfile)
    require(values['COMPOSE_PROJECT_NAME'] == 'tp-staging-20261023', 'Wrong project')
    require(values['DATA_ROOT'] == str(DATA), 'Wrong DATA_ROOT')
    require(values['RELEASE'] == 'guest-20261020-1', 'Wrong release')
    require(values.get('STAGING_MODE') == 'true', 'Staging mode required')
    require(values.get('AI_API_CONFIG') == 'false', 'AI must remain disabled')
    require(values.get('CALENDAR_LOGS') == 'false', 'Unexpected logging override')
    env = os.environ.copy()
    env.update(values)
    compose = ['docker', 'compose', '--env-file', str(envfile), '-p', values['COMPOSE_PROJECT_NAME'],
               '-f', str(RELEASE / 'deploy/compose.yml'),
               '-f', str(RELEASE / 'deploy/compose.staging.yml'),
               '-f', '/etc/tatar-pattern/staging-https.yml', '--profile', 'public']

    # Same lock as project ops/maintenance. Keep DB running throughout the operation.
    with (DATA / '.maintenance.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        OP.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (OP / 'operation.log').open('a', buffering=1) as log:
            def say(message):
                print(message, flush=True)
                log.write(message + '\n')

            def run(command):
                result = subprocess.run(command, env=env, cwd=RELEASE,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                if result.stdout:
                    say(result.stdout.rstrip())
                require(result.returncode == 0, 'Command failed; inspect operation.log; no automatic retry')
                return result.stdout

            def dc(*args):
                return run(compose + list(args))

            say('PREFLIGHT ' + OPERATION)
            package = RELEASE / 'payload/catalog'
            require(sha(package / 'catalog110.tgz') == ARCHIVE_SHA, 'Catalog archive SHA mismatch')
            require(sha(package / 'release-decision.pending.json') == PENDING_SHA, 'Pending decision SHA mismatch')
            decision = json.loads((package / 'release-decision.pending.json').read_text())
            require(decision['manifestSha256'] == MANIFEST_SHA and len(decision['elementCodes']) == 110,
                    'Unexpected catalog membership')
            decision.update(approved=True,
                            approvedBy='Владелец проекта Татар паттерн (прямое подтверждение в чате)',
                            approvedAt=APPROVAL_AT,
                            evidence='Прямой ответ владельца на предложение public_flat_catalog, '
                                     'зафиксирован 23.10.2026: ' + APPROVAL_TEXT)
            decision_path = OP / 'release-decision.approved.json'
            if decision_path.exists():
                require(json.loads(decision_path.read_text()) == decision, 'Existing decision differs; stop')
            else:
                with decision_path.open('x') as stream:
                    stream.write(json.dumps(decision, ensure_ascii=False, indent=2) + '\n')
            decision_path.chmod(0o644)  # Direct readonly bind for application UID10001.
            say('Approved decision file SHA256: ' + sha(decision_path))

            stage = OP / 'catalog-input'
            if not stage.exists():
                with tempfile.TemporaryDirectory(prefix='catalog-extract-', dir=OP) as temporary:
                    extracted = Path(temporary)
                    with tarfile.open(package / 'catalog110.tgz', 'r:gz') as archive:
                        members = archive.getmembers()
                        require(all(m.isfile() and not Path(m.name).is_absolute()
                                    and '..' not in Path(m.name).parts for m in members),
                                'Unexpected archive entry')
                        archive.extractall(extracted, members=members, filter='data')
                    require(sha(extracted / 'owner-accepted-2026-10-08.json') == MANIFEST_SHA,
                            'Extracted manifest SHA mismatch')
                    extracted.chmod(0o755)
                    for item in extracted.rglob('*'):
                        item.chmod(0o755 if item.is_dir() else 0o644)
                    extracted.rename(stage)
            require(sha(stage / 'owner-accepted-2026-10-08.json') == MANIFEST_SHA, 'Stage manifest mismatch')
            dc('config', '--quiet')
            running = set(dc('ps', '--services', '--status', 'running').split())
            require(running <= {'db', 'backend', 'frontend', 'proxy'}, 'Unexpected running service; stop')
            require('db' in running, 'Database must be running')
            say('QUIESCE: stopping proxy/frontend/backend; DB remains running')
            dc('stop', '-t', '120', 'proxy', 'frontend', 'backend')
            require(set(dc('ps', '--services', '--status', 'running').split()) == {'db'},
                    'Writers still running; import cancelled')

            say('APPLY: importer creates storage and DB backups before writes')
            dc('run', '--rm', '--no-deps', '-T',
               '-v', str(stage) + ':/catalog-input:ro',
               '-v', str(decision_path) + ':/release-decision.json:ro',
               'backend', 'python', '-m', 'scripts.production_catalog', 'apply',
               '--input', '/catalog-input', '--storage-root', '/data/storage',
               '--decision', '/release-decision.json', '--designated-operation', OPERATION)
            say('VERIFY: independent read-only catalog/file/provenance check')
            result = dc('run', '--rm', '--no-deps', '-T',
                        '-v', str(decision_path) + ':/release-decision.json:ro',
                        'backend', 'python', '-m', 'scripts.production_catalog', 'verify',
                        '--input', '/data/storage', '--storage-root', '/data/storage',
                        '--decision', '/release-decision.json')
            reports = [json.loads(line) for line in result.splitlines() if line.startswith('{')]
            require(reports and reports[-1].get('publicRealUniqueElements') == 110,
                    'Catalog verify did not confirm 110 elements')
            say('RESTART: launching the four staging services with HTTPS override')
            dc('up', '-d', '--wait', '--no-build', 'db', 'backend', 'frontend', 'proxy')
            dc('ps')
            common = ['curl', '--fail', '--silent', '--show-error', '--max-time', '30',
                      '--cacert', '/etc/tatar-pattern/staging-root-ca.crt',
                      '--resolve', 'localhost:18080:127.0.0.1']
            require(json.loads(run(common + ['https://localhost:18080/api/health'])).get('ok') is True,
                    'API health failed')
            capabilities = json.loads(run(common + ['https://localhost:18080/api/capabilities']))
            require(capabilities.get('realUniqueElements') == 110, 'HTTP catalog count differs from 110')
            (OP / 'IMPORT-PASS.json').write_text(json.dumps({
                'operation': OPERATION, 'publicRealUniqueElements': 110,
                'manifestSha256': MANIFEST_SHA, 'approvedDecisionFileSha256': sha(decision_path),
                'browserGenerationAndDownload': 'NOT_YET_TESTED'}, indent=2) + '\n')
            say('CATALOG IMPORT PASS: 110 real elements; HTTPS/API OK')
            say('Evidence: ' + str(OP))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('STOP: ' + str(exc), file=sys.stderr)
        print('Send the last output to the deployment chat. Do not reset the database.', file=sys.stderr)
        sys.exit(1)
