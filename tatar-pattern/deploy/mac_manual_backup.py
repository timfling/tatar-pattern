#!/usr/bin/env python3
"""Manually fetch the latest completed Beget staging backup and verify its SHA.

Python 3.9+ standard library only. SSH prompts for the key passphrase normally.
No scheduler installation, secrets export, or existing-backup deletion.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

REQUIRED = {'manifest.json', 'database.dump', 'storage.tar.gz'}
OPTIONAL = {'ISOLATED-RESTORE-PASS.json'}
TRANSFER = 'MAC-TRANSFER.json'
NAME = re.compile(r'\d{8}T\d{6}Z-[a-f0-9]{6}')
HOST = 'root@159.194.210.167'
DESTINATION = Path('/Users/timfling/TATAR PATTERN backups')

# The same VPS lock used by backup, cleanup and retention remains held until the
# stream is sent. Only the last *successful* backup marker can select a directory.
REMOTE = r'''
import fcntl,hashlib,json,re,sys,tarfile
from pathlib import Path
root=Path('/srv/tatar-pattern/staging-data')
with (root/'.maintenance.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    base=root/'backups'
    marker=json.loads((base/'.local-backup-ok.json').read_text())
    source=Path(marker['backup'])
    assert source.is_absolute() and source.parent==base,'Unexpected backup directory'
    assert re.fullmatch(r'\d{8}T\d{6}Z-[a-f0-9]{6}',source.name),'Unexpected backup name'
    assert not source.is_symlink() and source.is_dir(),'Backup directory missing or symlink'
    names=['manifest.json','database.dump','storage.tar.gz']
    for name in names:
        p=source/name
        assert p.is_file() and not p.is_symlink(),'Backup file missing or symlink'
    m=json.loads((source/'manifest.json').read_text())
    assert m['version']==1 and m['release'] in ('guest-20261020-1','guest-20261026-1','guest-20261026-2'),'Wrong backup release'
    assert m['createdAt']==source.name,'Backup identity mismatch'
    assert set(m['sha256'])=={'database.dump','storage.tar.gz'},'Unexpected checksum set'
    for name,expected in m['sha256'].items():
        h=hashlib.sha256()
        with (source/name).open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
        assert h.hexdigest()==expected,'VPS backup checksum mismatch'
    optional=source/'ISOLATED-RESTORE-PASS.json'
    if optional.is_file() and not optional.is_symlink():names.append(optional.name)
    import io
    transfer=json.dumps(dict(backup=source.name,completedAt=marker['completedAt']),indent=2).encode()
    with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as tar:
        for name in names:tar.add(source/name,arcname=name,recursive=False)
        info=tarfile.TarInfo('MAC-TRANSFER.json');info.size=len(transfer);info.mode=0o600
        tar.addfile(info,io.BytesIO(transfer))
'''


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def validate(directory):
    require(not directory.is_symlink(), 'Папка копии является ссылкой')
    manifest = json.loads((directory / 'manifest.json').read_text())
    require(manifest.get('version') == 1 and manifest.get('release') in ('guest-20261020-1','guest-20261026-1','guest-20261026-2'),
            'Неожиданная версия резервной копии')
    require(NAME.fullmatch(manifest['createdAt']), 'Неверное имя резервной копии')
    require(set(manifest['sha256']) == REQUIRED - {'manifest.json'}, 'Неверный список SHA-256')
    for name, expected in manifest['sha256'].items():
        p = directory / name
        require(p.is_file() and not p.is_symlink(), 'Отсутствует обычный файл: ' + name)
        require(digest(p) == expected, 'SHA-256 не совпала: ' + name)
    return manifest


def receive_archive(archive, directory):
    """Extract only a small allowlist of regular files, without trusting tar paths."""
    seen = set()
    with tarfile.open(archive, 'r:') as tar:
        for member in tar:
            require(member.name in REQUIRED | OPTIONAL | {TRANSFER}, 'Лишний файл в передаче')
            require(member.name not in seen and member.isfile(), 'Повтор или ссылка в передаче')
            require(0 <= member.size <= 20 * 2**30, 'Недопустимый размер файла')
            seen.add(member.name)
            with tar.extractfile(member) as source, (directory / member.name).open('xb') as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
    require(REQUIRED | {TRANSFER} <= seen, 'Неполная передача')


def store_verified(incoming, destination):
    manifest = validate(incoming)
    transfer = json.loads((incoming / TRANSFER).read_text())
    require(transfer['backup'] == manifest['createdAt'], 'Имя передачи не совпало с manifest')
    completed = datetime.fromisoformat(transfer['completedAt'])
    require(completed.tzinfo is not None, 'Время копии без часового пояса')
    now = datetime.now(timezone.utc)
    age = (now - completed).total_seconds()
    require(age >= -300, 'Время копии находится в будущем; проверь часы Mac/VPS')
    target = destination / manifest['createdAt']
    if target.exists() or target.is_symlink():
        require(target.is_dir() and not target.is_symlink(), 'Конфликт пути существующей копии')
        existing = validate(target)
        require(existing == manifest, 'Существующий manifest отличается; существующая копия не перезаписана')
        state = 'ALREADY VERIFIED'
    else:
        incoming.rename(target)
        state = 'SAVED'
    report = dict(checkedAt=now.isoformat(), backup=str(target), completedAt=transfer['completedAt'],
                  sha256=manifest['sha256'], ageHours=round(age / 3600, 2), stale=age > 26 * 3600)
    # Atomic replace of only the script's own status marker.
    marker = destination / '.manual-backup-status.tmp'
    marker.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    marker.replace(destination / 'MANUAL-BACKUP-STATUS.json')
    return target, state, report


def main():
    require(sys.platform == 'darwin', 'Запусти скрипт на Mac, в локальной вкладке timfling@…')
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, help="Folder outside cloud synchronization")
    args = parser.parse_args()
    destination = args.destination.expanduser().absolute() if args.destination else DESTINATION
    require(not destination.is_symlink(), 'Каталог копий не должен быть ссылкой')
    destination.mkdir(parents=True, mode=0o700, exist_ok=True)
    lock = (destination / '.manual-download.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Другое скачивание уже выполняется')
    require(shutil.disk_usage(destination).free >= 2 * 2**30, 'Нужно минимум 2 ГиБ свободного места на Mac')
    key = Path.home() / '.ssh/tatar_pattern_beget_ed25519'
    require(key.is_file(), 'SSH-ключ не найден по ожидаемому пути')
    command = ['/usr/bin/ssh', '-T', '-i', str(key), '-o', 'IdentitiesOnly=yes',
               '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=15',
               '-o', 'ServerAliveInterval=30', '-o', 'ServerAliveCountMax=3',
               '-o', 'PreferredAuthentications=publickey', '-o', 'PasswordAuthentication=no',
               '-o', 'KbdInteractiveAuthentication=no', HOST, 'python3 -B -']
    print('Скачивание последней успешной копии с Beget. При запросе введи парольную фразу SSH-ключа.', flush=True)
    print('Проверка и передача могут занять несколько минут. При включении/отключении VPN соединение может оборваться.', flush=True)
    # Temporary data remains on the destination filesystem for an atomic rename.
    with tempfile.TemporaryDirectory(prefix='.download-', dir=destination) as scratch:
        scratch = Path(scratch)
        archive = scratch / 'transfer.tar'
        with archive.open('xb') as output:
            subprocess.run(command, input=REMOTE.encode(), stdout=output, check=True, timeout=1800)
        incoming = scratch / 'verified'
        incoming.mkdir(mode=0o700)
        receive_archive(archive, incoming)
        archive.unlink()
        target, state, report = store_verified(incoming, destination)
    print('\nOFFSERVER BACKUP PASS — ' + state, flush=True)
    print('database.dump: SHA-256 OK\nstorage.tar.gz: SHA-256 OK', flush=True)
    print('Папка: ' + str(target), flush=True)
    print('Возраст завершённой копии: ' + str(report['ageHours']) + ' ч.', flush=True)
    if report['stale']:
        print('ВНИМАНИЕ: копия старше 26 часов. Скачивание проверено; ежедневный backup на VPS требует проверки.', flush=True)
        return 2
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\nСкачивание прервано. Запусти снова, когда будет удобно.', file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print('STOP: ' + str(exc), file=sys.stderr)
        print('Пришли вывод в чат Beget. Завершённые резервные копии сохранены.', file=sys.stderr)
        sys.exit(1)
