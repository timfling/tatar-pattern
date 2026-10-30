#!/usr/bin/env python3
"""Age limit only for verified ordinary Beget backup sets in two known Mac folders."""
import argparse,fcntl,hashlib,json,os,re,shutil,sys
from pathlib import Path
from datetime import datetime,timezone
BASES=(Path('/Users/timfling/TATAR PATTERN backups'),Path('/Users/timfling/Desktop/Стартапы/ТАТАР ПАТТЕРН/Разработка/Резервные копии с Beget'))
RELEASES={'guest-20261020-1','guest-20261026-1','guest-20261026-2'}
ALLOW={'manifest.json','database.dump','storage.tar.gz','MAC-TRANSFER.json','ISOLATED-RESTORE-PASS.json','.DS_Store'}
def candidates(base,now):
 if base.is_symlink():raise RuntimeError('Backup folder symlink')
 for p in sorted(base.iterdir() if base.exists() else []):
  if not re.fullmatch(r'\d{8}T\d{6}Z-[a-f0-9]{6}',p.name):continue
  if p.is_symlink() or not p.is_dir():raise RuntimeError('Unexpected backup path')
  m=json.loads((p/'manifest.json').read_text())
  if m['release'] not in RELEASES or m['createdAt']!=p.name:raise RuntimeError('Unknown backup identity')
  created=datetime.strptime(p.name[:16],'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
  if (now-created).total_seconds()<6*86400:continue
  if set(x.name for x in p.iterdir())-ALLOW:raise RuntimeError('Extra files; do not delete backup')
  if set(m['sha256'])!={'database.dump','storage.tar.gz'}:raise RuntimeError('Unknown manifest')
  for n,expected in m['sha256'].items():
   q=p/n
   if q.is_symlink() or not q.is_file():raise RuntimeError('Unsafe backup member')
   with q.open('rb') as f:
    h=hashlib.sha256()
    for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    actual=h.hexdigest()
   if actual!=expected:raise RuntimeError('Unverified backup; preserve for review')
  yield p

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');a=parser.parse_args()
 if sys.platform!='darwin':raise RuntimeError('Mac only')
 os.umask(0o077);now=datetime.now(timezone.utc);deleted=[];planned=[]
 for b in BASES:
  if not b.exists():continue
  with (b/'.manual-download.lock').open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX)
   for p in candidates(b,now):
    planned.append(str(p))
    if a.apply:shutil.rmtree(p);deleted.append(str(p))
 if a.apply:
  marker=BASES[0]/'RETENTION-STATUS.json';marker.write_text(json.dumps({'checkedAt':now.isoformat(),'thresholdDays':6,'deleted':deleted},indent=2)+'\n')
 print(json.dumps({'mode':'APPLY' if a.apply else 'PLAN','thresholdDays':6,'candidates':planned,'deleted':deleted},ensure_ascii=False))
if __name__=='__main__':main()
