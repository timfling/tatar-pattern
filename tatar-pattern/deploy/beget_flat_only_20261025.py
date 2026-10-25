#!/usr/bin/env python3
"""Close the existing HTTPS staging AI switch; default is read-only plan.

Preserves sealed release, hotfix, registries, database, usage and drain ledger.
Never starts worker/tunnel. Requires the exact installed maintenance v2.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

MAINTENANCE_SHA = '8b588705e5ec8593c53ee252eff35ecdc5ad4da0e394bed466c386074b1a4615'
HOTFIX_SHA = '7776b706ed864472d89f48bd9eed346a871c8e5f4eb5263d0027b76e39607546'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def closed_override(raw):
    """Accept only the exact generated site-window override, or its closed form."""
    prefix = '# Owner approved closed f10-wreath:graphic window; totalguestbudget2\nservices:\n'
    original = prefix
    for service in ('backend', 'ai-worker'):
        original += f'  {service}:\n    environment:\n      AI_MVP_ENABLED: "true"\n      GUEST_GPU_BUDGET: "2"\n    volumes:\n'
        for src, dst in (
            ('/etc/tatar-pattern/runtime-hotfix/ai_provider.py', '/app/backend/app/ai_provider.py'),
            ('/etc/tatar-pattern/ai-window/ai-profiles.json', '/app/backend/app/ai-profiles.json'),
            ('/etc/tatar-pattern/ai-window/ai-bases-index.json', '/app/backend/app/ai-assets/index.json'),
        ):
            original += '      - type: bind\n        source: ' + src + '\n        target: ' + dst + '\n        read_only: true\n        bind: {create_host_path: false}\n'
    closed = original.replace(prefix, '# Explicit flat-only mode 2026-10-25; AI window closed\nservices:\n')
    closed = closed.replace('AI_MVP_ENABLED: "true"', 'AI_MVP_ENABLED: "false"').replace('GUEST_GPU_BUDGET: "2"', 'GUEST_GPU_BUDGET: "0"')
    require(raw in (original, closed), 'Unknown staging-ai.yml; inspect manually, no overwrite')
    return closed


def replace_file(path, data):
    temp = path.with_name('.' + path.name + '.flat-tmp')
    require(not temp.exists() and not temp.is_symlink(), 'Temporary file already exists')
    with temp.open('x') as stream:
        os.chmod(temp, 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    require(os.geteuid() == 0, 'Run as root on the existing Beget VPS')
    os.umask(0o077)
    installed = Path('/etc/tatar-pattern/staging-maintenance.py')
    require(not installed.is_symlink() and hashlib.sha256(installed.read_bytes()).hexdigest() == MAINTENANCE_SHA,
            'Unknown maintenance version')
    spec = importlib.util.spec_from_file_location('staging_v2', installed)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sys.path.insert(0, str(m.RELEASE / 'deploy'))
    import ops
    import maintenance
    with maintenance.lock(m.DATA, blocking=False):
        values = ops.read_env(m.ENVFILE)
        require(values.get('AI_API_CONFIG') == 'true', 'Expected existing AI adapter configuration')
        dc = m.make_dc(values)
        m.validate_config(json.loads(dc('config', '--format', 'json', capture=True)), True)
        running = set(dc('ps', '--services', '--status', 'running', capture=True).decode().split())
        require(running == m.BASE, 'Expected flat services only; no worker/tunnel start or drain attempted')
        m.stopped_worker_safe(dc, m.worker_info(dc))
        query = "SELECT count(*) FROM ai_jobs WHERE state IN ('queued','submitting','polling')"
        require(int(ops.pg(dc, 'psql', '-At', '-c', query).strip()) == 0, 'Unfinished AI jobs; reconcile first')
        override = Path('/etc/tatar-pattern/staging-ai.yml')
        require(not override.is_symlink() and override.stat().st_uid == 0 and override.stat().st_mode & 0o077 == 0,
                'Override must be root-owned 0600')
        original = override.read_text()
        closed = closed_override(original)
        hotfix = Path('/etc/tatar-pattern/runtime-hotfix/ai_provider.py')
        require(hashlib.sha256(hotfix.read_bytes()).hexdigest() == HOTFIX_SHA, 'Hotfix SHA changed')
        if not args.apply:
            print('PLAN PASS: backend AI=false, budget=0; preserve mounts/data/drain ledger; recreate backend only. NOT APPLIED.')
            return
        marker = json.loads((m.DATA / 'backups/.local-backup-ok.json').read_text())
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(marker['completedAt'])).total_seconds()
        backup_set = Path(marker['backup'])
        require(backup_set.parent == m.DATA / 'backups' and 0 <= age <= 26 * 3600 and
                (backup_set / 'manifest.json').is_file(), 'Recent successful backup required')
        previous = override.with_name('staging-ai.before-flat-20261025.yml')
        if original != closed:
            if previous.exists():
                require(not previous.is_symlink() and previous.read_text() == original, 'Rollback file conflict')
            else:
                with previous.open('x') as stream:
                    os.chmod(previous, 0o600)
                    stream.write(original)
        dc('stop', '-t', '120', 'backend')
        # On any subsequent failure leave AI admission closed; never auto-restore true.
        replace_file(override, closed)
        dc = m.make_dc(values)
        config = json.loads(dc('config', '--format', 'json', capture=True))
        m.validate_config(config, True)
        for name in ('backend', 'ai-worker'):
            env = config['services'][name]['environment']
            require(env['AI_MVP_ENABLED'] == 'false' and str(env['GUEST_GPU_BUDGET']) == '0', 'AI override not effective')
        dc('up', '-d', '--wait', '--no-build', '--no-deps', 'backend')
        curl = ['curl', '--fail', '--silent', '--show-error', '--max-time', '30', '--cacert',
                '/etc/tatar-pattern/staging-root-ca.crt', '--resolve', 'localhost:18080:127.0.0.1']
        caps = json.loads(subprocess.check_output(curl + ['https://localhost:18080/api/capabilities']))
        catalog = json.loads(subprocess.check_output(curl + ['https://localhost:18080/api/ai-bases']))
        require(caps['modes']['flat']['available'] is True and caps['modes']['ai']['available'] is False and
                caps['realUniqueElements'] == 110 and catalog['available'] is False and
                all(not s['available'] and 'AI_DISABLED' in s['unavailableReasons'] for b in catalog['bases'] for s in b['styles']),
                'Flat/AI catalog verification failed')
        m.health(dc, True)
        m.atomic_json(m.DATA / 'checks/flat-only-20261025.json', {
            'checkedAt': datetime.now(timezone.utc).isoformat(), 'aiEnabled': False,
            'guestGpuBudget': 0, 'realUniqueElements': 110, 'workerTunnelStarted': False,
            'sealedChanged': False, 'hotfixSha256': HOTFIX_SHA,
            'overrideSha256': hashlib.sha256(override.read_bytes()).hexdigest(),
            'scope': 'configuration + capabilities only; browser flat/export not rerun',
        })
        print('FLAT CONFIG PASS: AI_DISABLED, catalog110; worker/tunnel remain stopped; usage unchanged. Browser checks pending.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('STOP: ' + str(exc) + '; do not start worker/tunnel or restore AI=true', file=sys.stderr)
        sys.exit(1)
