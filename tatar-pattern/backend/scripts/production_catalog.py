"""Build catalog-only bundle; explicitly approved import into a designated database.

No users, QA accounts, results, DB dump, expert status or GPU transfer grants are copied.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
from uuid import uuid4
from datetime import datetime, timezone
from psycopg.types.json import Jsonb
from app.catalog import catalog, safe_path
from app.config import Settings
from .catalog_import import validate, db_conflicts, import_reviewed
from .db_admin import backup, backup_files, connect
from .migrate import main as migrate

MANIFEST='owner-accepted-2026-10-08.json'

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()

def checked(root):
    data, report=validate(root/MANIFEST,root)
    if not report['valid'] or report['counts']['elements']!=110:
        raise RuntimeError('Catalog must validate as exactly 110 main elements')
    return data,report

def decision_template(data,report):
    return dict(schemaVersion='tp-public-catalog-decision/1',approved=False,
                scope='public_flat_catalog',manifestSha256=report['manifestSha256'],
                elementCodes=sorted(e['code'] for e in data['elements']),
                ownerDeclaration='direct_owner_declaration_2026-10-11',
                approvedBy=None,approvedAt=None,evidence=None,
                expertVerificationGranted=False,externalTransferGranted=False,trainingGranted=False)

def check_decision(decision,data,report):
    expected=decision_template(data,report)
    for key in ('schemaVersion','scope','manifestSha256','elementCodes','ownerDeclaration',
                'expertVerificationGranted','externalTransferGranted','trainingGranted'):
        if decision.get(key)!=expected[key]:raise RuntimeError('Release scope mismatch: '+key)
    if decision.get('approved') is not True:raise RuntimeError('Explicit public catalog registry decision pending')
    if not all(isinstance(decision.get(k),str) and decision[k].strip() for k in ('approvedBy','approvedAt','evidence')):
        raise RuntimeError('Release decision needs accountable reviewer, time and evidence reference')
    at=datetime.fromisoformat(decision['approvedAt'])
    if at.tzinfo is None or at>datetime.now(timezone.utc):raise RuntimeError('Invalid release decision time')

def snapshot(conn,codes):
    # Includes every persisted provenance/quality/source field; ignore generated IDs/timestamps.
    query="""SELECT e.code,e.name_ru,e.motif_class,e.motif_identity,e.status,e.verified_by,
      e.provenance,e.local_use_approved,e.description,e.is_fixture,
      a.code artifact_code,a.title_ru,a.origin,a.authenticity,a.usage_scope,a.rights,a.review_status,a.notes,
      s.import_key,s.source_type,s.location,s.legal_basis,s.note,s.shot_date,
      f.file_type,f.path,f.content_sha256,f.ai_retouched,f.quality_acceptance,
      af.file_type source_type_file,af.path source_path,af.frame,af.content_sha256 source_sha256,af.note source_note
      FROM elements e JOIN artifacts a ON a.id=e.artifact_id JOIN sources s ON s.id=a.source_id AND s.id=e.source_id
      JOIN element_files f ON f.element_id=e.id JOIN artifact_files af ON af.id=f.source_file_id AND af.artifact_id=a.id
      WHERE e.code=ANY(%s) ORDER BY e.code,f.path"""
    rows=conn.execute(query,(codes,)).fetchall()
    if len(rows)!=110 or len({r['content_sha256'] for r in rows})!=110 or len({(r['artifact_code'],r['motif_identity']) for r in rows})!=110:
        raise RuntimeError('Unique real catalog count differs from 110')
    if any(r['verified_by'] is not None or r['status']!='отрисовано' or r['is_fixture'] for r in rows):
        raise RuntimeError('Unexpected expert/fixture status')
    return digest(rows)

def install(conn,root,decision):
    data,report=checked(root);check_decision(decision,data,report)
    codes=decision['elementCodes'];sha=report['manifestSha256']
    conn.execute('SELECT pg_advisory_xact_lock(107198006)')
    receipt=conn.execute('SELECT * FROM catalog_releases WHERE manifest_sha256=%s',(sha,)).fetchone()
    if receipt:
        if receipt['decision']!=decision or receipt['snapshot_sha256']!=snapshot(conn,codes):
            raise RuntimeError('Existing release changed; no overwrite')
    else:
        db_conflicts(conn,data,report)
        if not report['valid']:raise RuntimeError('Conflicting/partial catalog; reconcile without overwrite')
        import_reviewed(conn,data,report)
        conn.execute('INSERT INTO catalog_releases(manifest_sha256,decision,snapshot_sha256) VALUES(%s,%s,%s)',
                     (sha,Jsonb(decision),snapshot(conn,codes)))
        conn.execute('UPDATE elements SET public_release_sha256=%s WHERE code=ANY(%s)',(sha,codes))
    linked=conn.execute('SELECT code FROM elements WHERE public_release_sha256=%s ORDER BY code',(sha,)).fetchall()
    if [r['code'] for r in linked]!=codes:raise RuntimeError('Release membership changed')
    settings=Settings(os.environ['DATABASE_URL'],root,local_catalog=False,allow_fixtures=False)
    public=catalog(conn,settings)
    actual=sorted(r['code'] for r in public if r['code'] in codes)
    if actual!=codes:raise RuntimeError('Public physical/provenance counter is not 110')
    return dict(publicRealUniqueElements=len(actual),manifestSha256=sha,decisionSha256=digest(decision),
                replay=bool(receipt),snapshotSha256=snapshot(conn,codes),verifiedBy=None)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','apply','verify'])
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path)
    p.add_argument('--decision',type=Path)
    p.add_argument('--storage-root',type=Path)
    p.add_argument('--designated-operation',help='Owner assigned operation reference, required for writes')
    args=p.parse_args();root=args.input.resolve();data,report=checked(root)
    if args.command=='prepare':
        if not args.output: p.error('--output required')
        out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
        (out/'release-decision.pending.json').write_text(json.dumps(decision_template(data,report),ensure_ascii=False,indent=2)+'\n')
        (out/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        target=out/'catalog110.tgz'
        with tarfile.open(target,'w:gz') as bundle:
            for name in sorted([MANIFEST,*report['files']]):
                bundle.add(safe_path(root,name),arcname=name,recursive=False)
        (out/'catalog110.tgz.sha256').write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  catalog110.tgz\n')
        print(json.dumps({'counts':report['counts'],'files':len(report['files']),'approvalDigest':report['approvalDigest'],'bundle':str(target),'publicRegistryDecision':'pending'},ensure_ascii=False));return
    if not args.decision or not args.storage_root:p.error('--decision and --storage-root required')
    decision=json.loads(args.decision.read_text());check_decision(decision,data,report)
    storage=args.storage_root.resolve()
    if args.command=='apply':
        if not args.designated_operation or os.getenv('TP_ENVIRONMENT') not in ('production','isolated_test'):
            p.error('Explicit designated operation and production/isolated_test environment required')
        # Both backups complete before migrations, file staging or SQL writes.
        backup_files(storage);backup();migrate()
        for name in sorted([MANIFEST,*report['files']]):
            src=safe_path(root,name);dst=safe_path(storage,name)
            if dst.exists():
                if hashlib.sha256(dst.read_bytes()).digest()!=hashlib.sha256(src.read_bytes()).digest():
                    raise RuntimeError('Storage conflict; no overwrite: '+name)
                continue
            dst.parent.mkdir(parents=True,exist_ok=True)
            temporary=dst.with_name(dst.name+'.'+uuid4().hex+'.catalog-stage')
            try:
                with temporary.open('xb') as stream,src.open('rb') as source:shutil.copyfileobj(source,stream)
                # Hardlink is atomic and refuses to clobber a concurrent destination.
                os.link(temporary,dst)
            finally:temporary.unlink(missing_ok=True)
        with connect() as conn:
            result=install(conn,storage,decision)
    else:
        # No schema migration/import under verify; a missing receipt is an error.
        with connect() as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            receipt=conn.execute('SELECT * FROM catalog_releases WHERE manifest_sha256=%s',(report['manifestSha256'],)).fetchone()
            if not receipt or receipt['decision']!=decision or receipt['snapshot_sha256']!=snapshot(conn,decision['elementCodes']):
                raise RuntimeError('Release missing or drifted')
            linked=conn.execute('SELECT code FROM elements WHERE public_release_sha256=%s ORDER BY code',(report['manifestSha256'],)).fetchall()
            settings=Settings(os.environ['DATABASE_URL'],storage,local_catalog=False)
            actual=sorted(r['code'] for r in catalog(conn,settings) if r['code'] in decision['elementCodes'])
            if actual!=decision['elementCodes'] or [r['code'] for r in linked]!=actual:raise RuntimeError('Public catalog count/links mismatch')
            result=dict(publicRealUniqueElements=len(actual),manifestSha256=report['manifestSha256'],snapshotSha256=receipt['snapshot_sha256'])
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
