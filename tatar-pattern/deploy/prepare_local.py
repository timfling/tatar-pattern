#!/usr/bin/env python3
"""Create a NEW protected local config, never read project/backend/db .env."""
import ipaddress
import json
import os
from pathlib import Path
import secrets
import subprocess
from ops import HERE
os.umask(0o077)
label='tp-deploy-check-'+secrets.token_hex(5)
root=HERE/'local-check'/label
root.mkdir(parents=True)
ids=subprocess.check_output(['docker','network','ls','-q']).decode().split()
networks=json.loads(subprocess.check_output(['docker','network','inspect',*ids]))
used=[ipaddress.ip_network(c['Subnet']) for n in networks for c in (n.get('IPAM',{}).get('Config') or []) if c.get('Subnet')]
for octet in range(100,250):
    subnet=ipaddress.ip_network(f'172.30.{octet}.0/24')
    if not any(subnet.overlaps(x) for x in used if x.version==4):
        break
else:
    raise RuntimeError('No free local subnet')
s=(HERE/'.env.example').read_text().replace('tp-production',label).replace('REPLACE_WITH_64_HEX',secrets.token_hex(32)).replace('/srv/tatar-pattern/data',str(root/'data'))
s+=f'\nEDGE_SUBNET={subnet}\nPROXY_IP=172.30.{octet}.10\n'
env=root/'test.env'
env.write_text(s);env.chmod(0o600)
for name in ('storage','migration-backups'):
    directory=root/'data'/name;directory.mkdir(parents=True)
    if os.geteuid()==0:
        os.chown(directory,10001,10001)
print(env)
