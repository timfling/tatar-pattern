"""Refresh filesystem evidence before using the SQL proof count."""
import argparse
import hashlib
import json
from pathlib import Path
from app.catalog import inspect_png, safe_path
from .db_admin import backup, connect,require_local_environment


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--storage-root',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    args=p.parse_args()
    root=args.storage_root.resolve()
    require_local_environment()
    backup()
    report=[]
    with connect() as conn:
        rows=conn.execute('SELECT v.*,f.file_available FROM approved_element_files v JOIN element_files f ON f.id=v.file_id').fetchall()
        # Fail closed for records no longer eligible in the approval view.
        conn.execute("UPDATE element_files SET file_available=false,file_checked_at=now() WHERE file_type='flat_png'")
        for r in rows:
            available=False
            reason=None
            try:
                source=safe_path(root,r['source_path'])
                available=source.is_file() and inspect_png(safe_path(root,r['path']))==r['content_sha256']
                if available and r.get('source_sha256'):
                    with source.open('rb') as stream:
                        available=hashlib.file_digest(stream,'sha256').hexdigest()==r['source_sha256']
                if not available:
                    reason='Missing source or changed/missing PNG'
            except (ValueError,OSError) as exc:
                reason=str(exc)
            conn.execute('UPDATE element_files SET file_available=%s,file_checked_at=now() WHERE id=%s',(available,r['file_id']))
            report.append({'code':r['code'],'available':available,'reason':reason,'isFixture':r['is_fixture']})
        count=conn.execute((Path(__file__).resolve().parents[2]/'db/queries/count_real_elements.sql').read_text().split(';')[0]+';').fetchone()
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps({'items':report,'count':count},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(count,ensure_ascii=False))

if __name__=='__main__':
    main()
