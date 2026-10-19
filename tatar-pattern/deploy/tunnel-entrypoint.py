"""Only a local forward; strict host verification, no shell or arbitrary targets."""
import os
import re
import stat
from pathlib import Path


def command(env):
    host = env.get('GPU_SSH_HOST', '')
    user = env.get('GPU_SSH_USER', '')
    if host == 'NOT_CONFIGURED.invalid' or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', host):
        raise ValueError('GPU SSH host is not configured')
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*', user):
        raise ValueError('Invalid SSH user')
    ports = [env.get('GPU_SSH_PORT', '22'), env.get('GPU_API_PORT', '8765')]
    if any(not p.isdigit() or not 1 <= int(p) <= 65535 for p in ports):
        raise ValueError('Invalid port')
    return ['ssh', '-N', '-T', '-g', '-p', ports[0], '-l', user,
            '-i', '/run/ssh/id_ed25519',
            '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UserKnownHostsFile=/run/ssh/known_hosts',
            '-o', 'GlobalKnownHostsFile=/dev/null',
            '-o', 'ExitOnForwardFailure=yes', '-o', 'ConnectTimeout=10',
            '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3',
            '-o', 'LogLevel=ERROR', '-L', '0.0.0.0:18765:127.0.0.1:' + ports[1], host]


if __name__ == '__main__':
    key = Path('/run/ssh/id_ed25519')
    if stat.S_IMODE(key.stat().st_mode) & 0o077:
        raise SystemExit('SSH key must have mode 0600 or stricter')
    if not Path('/run/ssh/known_hosts').is_file():
        raise SystemExit('Verified known_hosts required')
    args = command(os.environ)
    os.execvp(args[0], args)
