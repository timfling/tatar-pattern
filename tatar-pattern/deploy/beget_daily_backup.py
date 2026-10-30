#!/usr/bin/env python3
"""Owner-started daily backup: VPS snapshot -> verified Mac copy -> age cleanup."""
import argparse,json,re,subprocess,sys
from pathlib import Path
import mac_manual_backup as download
import mac_backup_retention as retention
HERE=Path(__file__).resolve().parent
SSH=['/usr/bin/ssh','-T','-i',str(Path.home()/'.ssh/tatar_pattern_beget_ed25519'),'-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=30','-o','ServerAliveCountMax=3','root@159.194.210.167']
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true',help='Create+download; after success remove ordinary backup sets older than 6 days on both devices');a=p.parse_args()
 if not a.run:p.print_help();return
 print('1/4 Создаём свежую копию на Beget.',flush=True)
 result=subprocess.run(SSH+['python3 -B /etc/tatar-pattern/staging-maintenance.py backup'],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 print(result.stdout,flush=True);result.check_returncode()
 match=re.search(r'LOCAL BACKUP PASS: /srv/tatar-pattern/staging-data/backups/(\d{8}T\d{6}Z-[a-f0-9]{6})',result.stdout)
 if not match:raise RuntimeError('Не подтверждено имя свежей копии; старые копии сохранены')
 print('2/4 Скачиваем и проверяем копию на Mac.',flush=True)
 sys.argv=[str(HERE/'mac_manual_backup.py')];rc=download.main()
 if rc:raise RuntimeError('Копия не подтверждена; очистка отменена')
 marker=json.loads((download.DESTINATION/'MANUAL-BACKUP-STATUS.json').read_text())
 if Path(marker['backup']).name!=match.group(1):raise RuntimeError('Имена копий отличаются; очистка отменена')
 print('3/4 Удаляем обычные копии старше 6 суток на Mac.',flush=True)
 sys.argv=[str(HERE/'mac_backup_retention.py'),'--apply'];retention.main()
 print('4/4 Очищаем старые обычные копии и журналы на Beget.',flush=True)
 subprocess.run(SSH+['python3 -B /etc/tatar-pattern/staging-maintenance.py retention && python3 -B /etc/tatar-pattern/runtime-retention.py cleanup && python3 -B /etc/tatar-pattern/staging-maintenance.py status'],check=True)
 print('DAILY BACKUP PASS — свежая копия на Beget и Mac проверена; очистка завершена.',flush=True)
if __name__=='__main__':
 try:main()
 except Exception as e:print('STOP:',e,'Не закрывайте окно до сохранения вывода.',file=sys.stderr);sys.exit(1)
