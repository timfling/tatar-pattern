"""Offline restore reset and periodic retry for the transient guest zone only."""
import argparse
import json
import os
from uuid import UUID
from app.config import Settings
from app import guest
from app.erasure import drain_files
from .db_admin import backup,backup_files,connect


def reset(settings):
    # Caller must hold the worker session lock and stop HTTP writers.
    guest.clean(settings,all_guests=True)
    root=settings.storage_root/'guest-results'
    with connect() as conn:
        if root.is_symlink():raise RuntimeError('Guest storage root must not be a symlink')
        if root.exists():
            for path in root.rglob('*'):
                if path.is_symlink():raise RuntimeError('Unexpected symlink in guest storage')
                if path.is_file():
                    conn.execute("INSERT INTO storage_deletions(path) VALUES(%s) ON CONFLICT(path) DO UPDATE SET state='pending'",(str(path.relative_to(settings.storage_root)),))
        conn.commit()
        drain_files(conn,settings.storage_root,limit=1000000,path_prefix="guest-results/")
        conn.execute("DELETE FROM storage_deletions WHERE state='done' AND path LIKE 'guest-results/%%'")
        conn.commit()
        pending=conn.execute("SELECT count(*) n FROM storage_deletions WHERE path LIKE 'guest-results/%%'").fetchone()['n']
        remaining=conn.execute('SELECT count(*) n FROM guest_processes').fetchone()['n']+conn.execute('SELECT count(*) n FROM generations WHERE guest_process_id IS NOT NULL').fetchone()['n']
        if pending or remaining:raise RuntimeError('Guest reset incomplete; keep API and worker stopped, retry')
    if root.exists() and any(p.is_file() or p.is_symlink() for p in root.rglob('*')):
        raise RuntimeError('Guest files remain; keep API and worker stopped')
    # gpu-total deliberately survives: restore/reset must not replenish paid budget.


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['cleanup','reset-restored','status','reconcile-list','confirm-external'])
    parser.add_argument('--offline-restore',action='store_true')
    parser.add_argument('--designated-operation')
    parser.add_argument('--provider-request-id',type=UUID)
    parser.add_argument('--confirmation-ref')
    args=parser.parse_args();settings=Settings.from_env()
    if args.command in ('reset-restored','confirm-external'):
        if not args.designated_operation or os.getenv('TP_ENVIRONMENT') not in ('production','isolated_test'):
            parser.error('Designated operation and explicit environment required')
        if args.command=='reset-restored' and not args.offline_restore:
            parser.error('Stop API and worker; --offline-restore required')
        backup_files(settings.storage_root);backup()
    with connect() as conn:
        if args.command=='reset-restored':
            if not conn.execute('SELECT pg_try_advisory_lock(107198011) locked').fetchone()['locked']:
                raise RuntimeError('Worker still active; stop writers first')
            conn.commit();reset(settings)
        elif args.command=='cleanup':guest.clean(settings)
        elif args.command=='confirm-external':
            if not args.provider_request_id or not args.confirmation_ref:parser.error('Actual verified confirmation reference required')
            conn.execute('DELETE FROM guest_reconciliations WHERE provider_request_id=%s',(args.provider_request_id,));conn.commit()
        if args.command=='reconcile-list':
            print(json.dumps(conn.execute('SELECT * FROM guest_reconciliations ORDER BY expires_at').fetchall(),default=str))
            return
        counts={
            'guestProcesses':conn.execute('SELECT count(*) n FROM guest_processes').fetchone()['n'],
            'guestGenerations':conn.execute('SELECT count(*) n FROM generations WHERE guest_process_id IS NOT NULL').fetchone()['n'],
            'pendingGuestFiles':conn.execute("SELECT count(*) n FROM storage_deletions WHERE state='pending' AND path LIKE 'guest-results/%%'").fetchone()['n'],
            'externalReconciliation':conn.execute('SELECT count(*) n FROM guest_reconciliations').fetchone()['n'],
            'gpuBudgetUsed':conn.execute("SELECT used FROM guest_budget WHERE key='gpu-total'").fetchone()}
        print(json.dumps(counts))

if __name__=='__main__':main()
