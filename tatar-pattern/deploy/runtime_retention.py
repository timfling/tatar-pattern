#!/usr/bin/env python3
"""Calendar retention for ordinary VPS runtime journals. No application data deletion."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,sys
from datetime import datetime,timezone
ROOT=Path('/etc/tatar-pattern')
LOGS=('/var/log/syslog','/var/log/mail.log','/var/log/kern.log','/var/log/auth.log','/var/log/user.log','/var/log/cron.log','/var/log/ufw.log','/var/log/fail2ban.log','/var/log/cloud-init.log','/var/log/cloud-init-output.log','/var/log/wtmp','/var/log/btmp')
def run(*a):subprocess.run(a,check=True)
def put(p,text):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists() and p.read_text()!=text:
  if not (p.name=='runtime-logrotate.conf' and p.read_text()==text.replace(' su root root\n','')):raise RuntimeError('Existing different config: '+str(p))
 p.write_text(text);p.chmod(0o600)
def cleanup():
 run('journalctl','--rotate');run('journalctl','--vacuum-time=12d')
 run('/usr/sbin/logrotate','--wait-for-state-lock','/etc/tatar-pattern/runtime-logrotate.conf')
 now=datetime.now(timezone.utc).timestamp();removed=[]
 for name in LOGS:
  p=Path(name)
  for q in p.parent.glob(p.name+'*'):
   if re.fullmatch(re.escape(p.name)+r'(?:(?:\.\d+|-\d{8})(?:\.gz)?|\.\d+-\d{10}\.backup)',q.name):
    if q.is_symlink():raise RuntimeError('Symlink in log rotations')
    if q.stat().st_mtime < now-11*86400:q.unlink();removed.append(q.name)
 print(json.dumps({'checkedAt':datetime.now(timezone.utc).isoformat(),'journalMaxAgeDays':12,'rotatedLogsDeleted':removed}))
def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['install','cleanup','status']);a=p.parse_args()
 if os.geteuid()!=0:raise RuntimeError('Root required')
 os.umask(0o077)
 if a.action=='install':
  config='[Journal]\nStorage=persistent\nMaxRetentionSec=12day\nMaxFileSec=1h\nSystemMaxUse=256M\nRuntimeMaxUse=64M\nForwardToSyslog=no\n'
  put('/etc/systemd/journald.conf.d/95-tatar-retention.conf',config)
  put(ROOT/'runtime-logrotate.conf','\n'.join(LOGS)+'\n{\n su root root\n daily\n dateext\n dateformat -%Y%m%d\n rotate 10\n maxage 10\n missingok\n notifempty\n compress\n copytruncate\n}\n')
  installed=ROOT/'runtime-retention.py';raw=Path(__file__).read_bytes()
  if installed.exists() and installed.read_bytes()!=raw and hashlib.sha256(installed.read_bytes()).hexdigest()!='a9afb77e13ec85701d8bf1572ade4f6abec5a5840df8b80b7b1eec1a1770e8f8':raise RuntimeError('Unknown installed retention')
  installed.write_bytes(raw);installed.chmod(0o600)
  run('/usr/sbin/logrotate','--debug',str(ROOT/'runtime-logrotate.conf'))
  run('systemctl','restart','systemd-journald');run('journalctl','--flush')
  print('JOURNAL LIMIT CONFIGURED; text log cleanup is manual through daily backup button')
 elif a.action=='cleanup':cleanup()
 else:
  run('systemctl','is-active','systemd-journald')
  if not Path('/etc/systemd/journald.conf.d/95-tatar-retention.conf').is_file() or not (ROOT/'runtime-logrotate.conf').is_file():raise RuntimeError('Retention config missing')
  print('RUNTIME RETENTION CONFIG PASS: journal12d; daily button rotates ordinary text logs; historical evidence excluded')
if __name__=='__main__':main()
