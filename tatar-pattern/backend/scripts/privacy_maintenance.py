"""Internal operator tools. No public self-service or approved legal calendar implied.

Export ledger to independently protected storage before backup rotation. Replay the
LATEST ledger into an offline restored database/storage before opening any access.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
from app.config import Settings
from app.erasure import erase_generation, drain_files, block_account, erase_account_local
from .db_admin import backup, backup_files, connect


def export_ledger(conn,path):
    data={'schemaVersion':'tp-erasure-ledger/1',
          'generations':conn.execute('SELECT generation_id,user_id,reason,occurred_at FROM erasure_tombstones ORDER BY generation_id').fetchall(),
          'accounts':conn.execute('SELECT operation_ref,user_id,state,decision_ref FROM privacy_operations ORDER BY operation_ref').fetchall(),
          'files':conn.execute('SELECT path FROM storage_deletions ORDER BY path').fetchall()}
    raw=json.dumps(data,ensure_ascii=False,sort_keys=True,default=str).encode()
    temporary=path.with_name(path.name+'.'+uuid4().hex+'.tmp')
    with temporary.open('xb') as stream:
        temporary.chmod(0o600);stream.write(raw)
    temporary.replace(path)
    return hashlib.sha256(raw).hexdigest()

def replay(conn,ledger):
    if ledger.get('schemaVersion')!='tp-erasure-ledger/1':raise RuntimeError('Invalid ledger')
    for item in ledger['accounts']:
        uid=item['user_id']
        restored=conn.execute('SELECT id FROM users WHERE id=%s FOR UPDATE',(uid,)).fetchone()
        if restored:
            # Force replay even if a restored workflow already has a completed local stage.
            conn.execute('DELETE FROM privacy_operations WHERE operation_ref=%s',(item['operation_ref'],))
            block_account(conn,uid,item['operation_ref'],item['decision_ref'])
            if item['state']!='blocked':erase_account_local(conn,item['operation_ref'])
        else:
            conn.execute('INSERT INTO privacy_operations(operation_ref,user_id,state,decision_ref) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                         (item['operation_ref'],uid,item['state'],item['decision_ref']))
    for item in ledger['generations']:
        row=conn.execute('SELECT * FROM generations WHERE id=%s FOR UPDATE',(item['generation_id'],)).fetchone()
        if row:
            if row['user_id']!=item['user_id']:raise RuntimeError('Wrong restore lineage: user differs')
            erase_generation(conn,row,'restore_replay')
        else:
            conn.execute('INSERT INTO erasure_tombstones(generation_id,user_id,reason) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',
                         (item['generation_id'],item['user_id'],'restore_replay'))
    for item in ledger['files']:
        conn.execute("INSERT INTO storage_deletions(path) VALUES(%s) ON CONFLICT(path) DO UPDATE SET state='pending',updated_at=now()",(item['path'],))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['status','retry','export-ledger','replay-ledger'])
    p.add_argument('--ledger',type=Path);p.add_argument('--sha256');p.add_argument('--offline-restore',action='store_true')
    p.add_argument('--designated-operation');args=p.parse_args();settings=Settings.from_env()
    if args.command in ('retry','replay-ledger'):
        if not args.designated_operation or os.getenv('TP_ENVIRONMENT') not in ('production','isolated_test'):
            p.error('Explicit designated operation/environment required')
        backup_files(settings.storage_root);backup()
    with connect() as conn:
        if args.command=='export-ledger':
            if not args.ledger:p.error('--ledger required')
            print('Ledger SHA256:',export_ledger(conn,args.ledger))
        elif args.command=='replay-ledger':
            if not args.offline_restore or not args.ledger or not args.sha256:p.error('Offline restore, ledger and verified SHA required')
            raw=args.ledger.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=args.sha256:raise RuntimeError('Ledger SHA differs')
            replay(conn,json.loads(raw));conn.commit();drain_files(conn,settings.storage_root)
        elif args.command=='retry':drain_files(conn,settings.storage_root)
        counts={}
        for table,state in [('storage_deletions','pending'),('provider_deletions','manual_required')]:
            counts[table]=conn.execute(f'SELECT count(*) n FROM {table} WHERE state=%s',(state,)).fetchone()['n']
        counts['expiredSessions']=conn.execute('SELECT count(*) n FROM sessions WHERE expires_at<=now()').fetchone()['n']
        counts['restoredTombstonedRows']=conn.execute('SELECT count(*) n FROM generations g JOIN erasure_tombstones t ON t.generation_id=g.id').fetchone()['n']
        counts['localQueuesClear']=not any(counts.values())
        print(json.dumps(counts))

if __name__=='__main__':main()
