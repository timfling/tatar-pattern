"""Validate an explicitly human-reviewed registry, then import without overwrites.

Never accepts annotations.csv or generated annotation SQL.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from psycopg.types.json import Jsonb
from app.catalog import MOTIFS, inspect_png, safe_path
from .db_admin import backup, connect

SCOPES={'некоммерческое_mvp','разрешение_получено','публичное_место'}


def validate(manifest: Path, root: Path):
    errors=[]
    duplicates=[]
    try:
        raw=manifest.read_bytes()
        data=json.loads(raw)
        if isinstance(data,dict) and data.get('version')==2:
            from .catalog_v2 import validate as validate_v2
            return validate_v2(manifest,root)
        if not isinstance(data,dict) or data.get('version')!=1:
            raise ValueError('Нужен реестр JSON version=1, не annotations.csv')
    except (OSError,ValueError) as exc:
        return None, {'valid':False,'errors':[str(exc)],'duplicates':[]}
    hashes={}
    seen={'source':set(),'artifact':set(),'code':set(),'identity':set(),'path':set(),'sha':set()}
    def require(obj,keys,label):
        valid=True
        for k in keys:
            if not isinstance(obj.get(k),str) or not obj[k].strip():
                errors.append(f'{label}: отсутствует {k}')
                valid=False
        return valid
    def unique(kind,value,label):
        if value in seen[kind]:
            duplicates.append(f'{label}: повтор {kind} {value}')
        seen[kind].add(value)
    require(data,['reviewedBy','reviewedAt'],'реестр')
    if data.get('humanApproved') is not True:
        errors.append('humanApproved должен быть true после проверки человеком')
    try:
        reviewed=datetime.fromisoformat(data.get('reviewedAt',''))
        if reviewed.tzinfo is None or reviewed>datetime.now(timezone.utc):
            raise ValueError()
    except (ValueError,TypeError):
        errors.append('reviewedAt: нужна дата ISO 8601 с часовым поясом, не в будущем')
    for section in ('sources','artifacts','elements'):
        if not isinstance(data.get(section),list) or not data[section]:
            errors.append(f'{section}: нужен непустой массив')
            data[section]=[]
        if any(not isinstance(r,dict) for r in data[section]):
            errors.append(f'{section}: записи должны быть объектами')
            data[section]=[r for r in data[section] if isinstance(r,dict)]
    for s in data['sources']:
        if not require(s,['key','sourceType','location','legalBasis'],'источник'):
            continue
        unique('source',s.get('key'),'источник')
        if s.get('sourceType') not in ('фото','музей','архив','книга','иное'):
            errors.append('sourceType: неверное значение')
    for a in data['artifacts']:
        if not require(a,['code','sourceKey','titleRu','origin','usageScope','rights','reviewStatus','sourcePath','sourceFrame'],'предмет'):
            continue
        unique('artifact',a.get('code'),'предмет')
        if a.get('sourceKey') not in seen['source']:
            errors.append(f"{a.get('code')}: отсутствует источник")
        if (a.get('origin'),a.get('usageScope'),a.get('reviewStatus'))!=('татарское','рид_и_обучение','проверено') or a.get('rights') not in SCOPES:
            errors.append(f"{a.get('code')}: предмет не разрешен/не проверен")
        if a.get('sourceFileType','raw') not in ('raw','proxy'):
            errors.append(f"{a.get('code')}: sourceFileType должен быть raw/proxy")
        try:
            path=safe_path(root,a.get('sourcePath',''))
            if not path.is_file():
                raise ValueError('исходный кадр отсутствует')
            hashes[a['sourcePath']]=hashlib.sha256(path.read_bytes()).hexdigest()
            unique('path',a['sourcePath'],'исходник')
        except (OSError,ValueError,KeyError) as exc:
            errors.append(f"{a.get('code')}: {exc}")
    for e in data['elements']:
        if not require(e,['code','nameRu','motifClass','artifactCode','motifIdentity','path','verifiedBy','reviewStatus'],'элемент'):
            continue
        unique('code',e.get('code'),'элемент')
        unique('identity',(e.get('artifactCode'),e.get('motifIdentity')),'элемент')
        if e.get('artifactCode') not in seen['artifact']:
            errors.append(f"{e.get('code')}: отсутствует предмет")
        if e.get('motifClass') not in MOTIFS.values() or e.get('reviewStatus')!='проверено':
            errors.append(f"{e.get('code')}: неизвестный мотив или отсутствует человеческая проверка")
        if not isinstance(e.get('aiRetouched',False),bool):
            errors.append(f"{e.get('code')}: aiRetouched должен быть boolean")
        if e.get('aiRetouched') and e.get('retouchComparedWithSource') is not True:
            errors.append(f"{e.get('code')}: ИИ-ретушь требует ручного сравнения с исходным кадром")
        try:
            path=safe_path(root,e.get('path',''))
            digest=inspect_png(path)
            hashes[e['path']]=digest
            unique('path',e['path'],'элемент')
            unique('sha',digest,'элемент')
        except (OSError,ValueError,KeyError) as exc:
            errors.append(f"{e.get('code')}: {exc}")
    report={'valid':not(errors or duplicates),'errors':errors,'duplicates':duplicates,
            'manifestSha256':hashlib.sha256(raw).hexdigest(),'files':hashes,
            'counts':{key:len(data[key]) for key in ('sources','artifacts','elements')}}
    canonical=json.dumps(report,sort_keys=True,ensure_ascii=False).encode()
    report['approvalDigest']=hashlib.sha256(canonical).hexdigest()
    return data,report


def db_conflicts(conn,data,report):
    if data.get('version')==2:
        from .catalog_v2 import db_conflicts as conflicts_v2
        return conflicts_v2(conn,data,report)
    # A shared source/artifact may be reused only if provenance and rights agree.
    duplicates=report['duplicates']
    for s in data['sources']:
        row=conn.execute('SELECT * FROM sources WHERE import_key=%s',(s['key'],)).fetchone()
        if row and (row['source_type'],row['location'],row['legal_basis'])!=(s['sourceType'],s['location'],s['legalBasis']):
            duplicates.append(f"Источник {s['key']}: несовместимое происхождение в БД")
    for a in data['artifacts']:
        row=conn.execute('SELECT a.*,s.import_key FROM artifacts a LEFT JOIN sources s ON s.id=a.source_id WHERE a.code=%s',(a['code'],)).fetchone()
        if row and (row['import_key'],row['origin'],row['usage_scope'],row['rights'],row['review_status'],row['title_ru'])!=(a['sourceKey'],a['origin'],a['usageScope'],a['rights'],a['reviewStatus'],a['titleRu']):
            duplicates.append(f"Предмет {a['code']}: несовместимые данные в БД")
        f=conn.execute('SELECT f.*,a.code FROM artifact_files f JOIN artifacts a ON a.id=f.artifact_id WHERE f.path=%s',(a['sourcePath'],)).fetchone()
        if f and (f['code'],f['frame'],f['file_type'])!=(a['code'],a['sourceFrame'],a.get('sourceFileType','raw')):
            duplicates.append(f"Кадр {a['sourcePath']}: уже привязан к другому предмету/ракурсу")
    for e in data['elements']:
        rows=conn.execute('SELECT e.code FROM elements e LEFT JOIN artifacts a ON a.id=e.artifact_id LEFT JOIN element_files f ON f.element_id=e.id WHERE e.code=%s OR f.path=%s OR f.content_sha256=%s OR (a.code=%s AND e.motif_identity=%s)',(e['code'],e['path'],report['files'][e['path']],e['artifactCode'],e['motifIdentity'])).fetchall()
        if rows:
            duplicates.append(f"{e['code']}: дубль в БД ({','.join(sorted({r['code'] for r in rows}))})")
    report['valid']=not(report['errors'] or duplicates)


def import_reviewed(conn,data,report):
    if data.get('version')==2:
        from .catalog_v2 import import_reviewed as import_v2
        return import_v2(conn,data,report)
    reviewed=datetime.fromisoformat(data['reviewedAt'])
    for s in data['sources']:
        conn.execute('INSERT INTO sources(import_key,source_type,location,legal_basis,object_name) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(import_key) DO NOTHING',(s['key'],s['sourceType'],s['location'],s['legalBasis'],s.get('objectName')))
    for a in data['artifacts']:
        sid=conn.execute('SELECT id FROM sources WHERE import_key=%s',(a['sourceKey'],)).fetchone()['id']
        conn.execute('INSERT INTO artifacts(code,source_id,title_ru,origin,usage_scope,rights,review_status,reviewed_by,reviewed_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(code) DO NOTHING',(a['code'],sid,a['titleRu'],a['origin'],a['usageScope'],a['rights'],a['reviewStatus'],data['reviewedBy'],reviewed))
        aid=conn.execute('SELECT id FROM artifacts WHERE code=%s',(a['code'],)).fetchone()['id']
        conn.execute('INSERT INTO artifact_files(artifact_id,file_type,path,frame) VALUES(%s,%s,%s,%s) ON CONFLICT(path) DO NOTHING',(aid,a.get('sourceFileType','raw'),a['sourcePath'],a['sourceFrame']))
    for e in data['elements']:
        a=conn.execute('SELECT id,source_id FROM artifacts WHERE code=%s',(e['artifactCode'],)).fetchone()
        manifest_a=next(x for x in data['artifacts'] if x['code']==e['artifactCode'])
        source_file=conn.execute('SELECT id FROM artifact_files WHERE path=%s',(manifest_a['sourcePath'],)).fetchone()['id']
        eid=conn.execute("INSERT INTO elements(code,name_ru,motif_class,status,verified_by,artifact_id,source_id,motif_identity) VALUES(%s,%s,%s,'верифицировано',%s,%s,%s,%s) RETURNING id",(e['code'],e['nameRu'],e['motifClass'],e['verifiedBy'],a['id'],a['source_id'],e['motifIdentity'])).fetchone()['id']
        conn.execute("INSERT INTO element_files(element_id,file_type,path,ai_retouched,content_sha256,reviewed_by,reviewed_at,source_file_id,file_available,file_checked_at) VALUES(%s,'flat_png',%s,%s,%s,%s,%s,%s,true,now())",(eid,e['path'],e.get('aiRetouched',False),report['files'][e['path']],e['verifiedBy'],reviewed,source_file))
    conn.execute('INSERT INTO catalog_imports(manifest_sha256,reviewed_by,report) VALUES(%s,%s,%s)',(report['manifestSha256'],data['reviewedBy'],Jsonb(report)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['validate','import'])
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--storage-root',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--approval-digest',help='Digest из отчета после ручного просмотра')
    parser.add_argument('--with-db',action='store_true',help='Проверить дубли в БД; сначала бэкап')
    args=parser.parse_args()
    if args.report.resolve()==args.manifest.resolve():
        parser.error('Отчет должен быть отдельным файлом, чтобы не перезаписать реестр')
    data,report=validate(args.manifest,args.storage_root.resolve())
    if args.command=='import' and (not args.approval_digest or args.approval_digest!=report.get('approvalDigest')):
        parser.error('Сначала validate и просмотр отчета; нужен соответствующий --approval-digest')
    if report['valid'] and (args.with_db or args.command=='import'):
        from .db_admin import backup_files, require_local_environment
        require_local_environment()
        backup_files(args.storage_root.resolve())
        backup()
        with connect() as conn:
            conn.execute('SELECT pg_advisory_xact_lock(107198006)')
            db_conflicts(conn,data,report)
            if args.command=='import' and report['valid']:
                # Recheck physical files under the same DB transaction immediately before write.
                _,fresh=validate(args.manifest,args.storage_root.resolve())
                if fresh.get('approvalDigest')!=args.approval_digest or not fresh['valid']:
                    raise RuntimeError('Файлы/реестр изменились после проверки')
                import_reviewed(conn,data,report)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'valid':report['valid'],'counts':report.get('counts'),'approvalDigest':report.get('approvalDigest'),'report':str(args.report)},ensure_ascii=False))
    if not report['valid']:
        raise SystemExit(1)

if __name__=='__main__':
    main()
