#!/usr/bin/env python3
"""Dedicated GPU tunnel account. Default is plan only; apply in agreed GPU window."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess

USER = 'tp-gpu-tunnel'
PUBLIC = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKxEPgIzEMNeFEdX0FX1HJZvDpjRpYlCM3wgVBde45lF tp-beget-tunnel-20261024'
CLIENT_FP = 'SHA256:9rfANttjzdEGuC93eSPMalQRvvv7KoJNXAfBhSVxH5c'
HOST_FP = 'SHA256:2uI6K/NhT8SghAVz0mgX3QBGgF1nQmV7yrqS4p2s2pk'
DROPIN = Path('/etc/ssh/sshd_config.d/90-tp-gpu-tunnel.conf')
USER_HOME = Path('/home/tp-gpu-tunnel')
KEYLINE = 'from="159.194.210.167",restrict,port-forwarding,command="/bin/false",permitopen="127.0.0.1:8765" ' + PUBLIC + '\n'
CONFIG = '''# Managed by gpu_tunnel_account_20261024.py
Match User tp-gpu-tunnel
    AuthenticationMethods publickey
    PubkeyAuthentication yes
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    AllowTcpForwarding local
    AllowStreamLocalForwarding no
    PermitOpen 127.0.0.1:8765
    PermitListen none
    AllowAgentForwarding no
    X11Forwarding no
    PermitTTY no
    PermitTunnel no
    GatewayPorts no
    MaxSessions 0
    ForceCommand /bin/false
Match all
'''


def require(ok, msg):
    if not ok:
        raise RuntimeError(msg)


def fingerprint(public):
    return 'SHA256:' + base64.b64encode(hashlib.sha256(base64.b64decode(public.split()[1], validate=True)).digest()).decode().rstrip('=')


def effective():
    text = subprocess.check_output(['/usr/sbin/sshd', '-T', '-C',
            'user=tp-gpu-tunnel,host=beget,addr=159.194.210.167']).decode()
    values = dict(line.split(' ', 1) for line in text.splitlines() if ' ' in line)
    expected = {'authenticationmethods': 'publickey', 'pubkeyauthentication': 'yes',
        'passwordauthentication': 'no', 'kbdinteractiveauthentication': 'no',
        'allowtcpforwarding': 'local', 'allowstreamlocalforwarding': 'no',
        'permitopen': '127.0.0.1:8765', 'permitlisten': 'none', 'allowagentforwarding': 'no',
        'x11forwarding': 'no', 'permittty': 'no', 'permittunnel': 'no', 'gatewayports': 'no',
        'maxsessions': '0', 'forcecommand': '/bin/false'}
    require(all(values.get(k) == v for k, v in expected.items()),
            'Effective sshd restrictions differ; no authorization key will be installed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--repair-public-directory', action='store_true')
    args = parser.parse_args()
    require(fingerprint(PUBLIC) == CLIENT_FP, 'Client public key mismatch')
    if not args.apply and not args.repair_public_directory:
        print('PLAN ONLY: create tp-gpu-tunnel; source159.194.210.167; local forward127.0.0.1:8765; no shell/password/remote forward')
        print('No changes; --apply only in agreed GPU window with a second owner SSH session open')
        return
    require(os.geteuid() == 0, 'Run sudo python3 on GPU VM')
    os.umask(0o077)
    require(fingerprint(Path('/etc/ssh/ssh_host_ed25519_key.pub').read_text()) == HOST_FP,
            'GPU host key changed; verify with owner before any installation')
    require(DROPIN.parent.is_dir() and not DROPIN.parent.is_symlink(), 'Unexpected sshd dropin directory')
    if args.repair_public_directory:
        ssh = USER_HOME / '.ssh'
        auth = ssh / 'authorized_keys'
        require(USER_HOME.is_dir() and not USER_HOME.is_symlink() and USER_HOME.stat().st_uid == 0,
                'Unexpected managed home')
        require(ssh.is_dir() and not ssh.is_symlink() and ssh.stat().st_uid == 0 and
                ssh.stat().st_mode & 0o777 in (0o700, 0o755), 'Unexpected public .ssh directory')
        require(set(p.name for p in ssh.iterdir()) == {'authorized_keys'} and
                auth.is_file() and not auth.is_symlink() and auth.stat().st_uid == 0 and
                auth.stat().st_mode & 0o777 == 0o644 and auth.read_text() == KEYLINE,
                'Unexpected authorized_keys; no repair')
        require(DROPIN.is_file() and not DROPIN.is_symlink() and DROPIN.read_text() == CONFIG,
                'Unexpected managed sshd policy')
        effective()
        before = oct(ssh.stat().st_mode & 0o777)
        ssh.chmod(0o755)
        print('PUBLIC AUTH DIRECTORY REPAIRED: ' + before + ' -> 0o755; root owner preserved')
        print('authorized_keys and all forwarding/shell/source restrictions unchanged')
        return
    require(not DROPIN.exists() and not DROPIN.is_symlink() and not USER_HOME.exists() and not USER_HOME.is_symlink(),
            'Account/config path already exists; no overwrite')
    try:
        pwd.getpwnam(USER)
    except KeyError:
        pass
    else:
        raise RuntimeError('Account already exists; no overwrite')
    # No key exists until syntax, effective restrictions and reload have succeeded.
    subprocess.run(['useradd', '--create-home', '--home-dir', str(USER_HOME), '--shell', '/usr/sbin/nologin',
                    '--password', '*', USER], check=True)
    os.chown(USER_HOME, 0, 0)
    USER_HOME.chmod(0o755)
    try:
        with DROPIN.open('x') as stream:
            stream.write(CONFIG)
        DROPIN.chmod(0o644)
        subprocess.run(['/usr/sbin/sshd', '-t'], check=True)
        effective()
        subprocess.run(['systemctl', 'reload', 'ssh.service'], check=True)
    except Exception:
        if DROPIN.is_file() and not DROPIN.is_symlink() and DROPIN.read_text() == CONFIG:
            DROPIN.unlink()
            subprocess.run(['/usr/sbin/sshd', '-t'], check=False)
            subprocess.run(['systemctl', 'reload', 'ssh.service'], check=False)
        raise RuntimeError('sshd validation/reload failed; account has no key; inspect before retry') from None
    ssh = USER_HOME / '.ssh'
    ssh.mkdir(mode=0o755)
    ssh.chmod(0o755)  # Override process umask: the account must read its public authorized_keys.
    with (ssh / 'authorized_keys').open('x') as stream:
        stream.write(KEYLINE)
    (ssh / 'authorized_keys').chmod(0o644)
    print('GPU TUNNEL ACCOUNT INSTALLED; effective sshd restrictions verified')
    print('Client fingerprint: ' + CLIENT_FP)
    print('Live Beget transport/login and HTTP are NOT VERIFIED; owner SSH session must remain open')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit('STOP: ' + str(exc))
