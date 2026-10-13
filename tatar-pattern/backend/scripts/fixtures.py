"""Synthetic fixtures only. Deliberately impossible to count as real catalog."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw
from app.catalog import MOTIFS
from .catalog_import import import_reviewed, validate
from .db_admin import backup, connect


def build_fixture(root: Path):
    key='fixture-'+uuid4().hex[:12]
    relative=f'fixtures/{key}'
    directory=root/relative
    directory.mkdir(parents=True)
    source=Image.new('RGB',(128,128),'white')
    source.save(directory/'source.png')
    data={'version':1,'humanApproved':True,'reviewedBy':'SYNTHETIC TEST FIXTURE','reviewedAt':datetime.now(timezone.utc).isoformat(),
          'sources':[{'key':key,'sourceType':'иное','location':'Synthetic test, no museum provenance','legalBasis':'Generated test shapes only'}],
          'artifacts':[{'code':key,'sourceKey':key,'titleRu':'Синтетическая тестовая фигура','origin':'татарское','usageScope':'рид_и_обучение','rights':'некоммерческое_mvp','reviewStatus':'проверено','sourcePath':f'{relative}/source.png','sourceFrame':key,'sourceFileType':'proxy'}],
          'elements':[]}
    for i,(motif,ru) in enumerate(MOTIFS.items()):
        im=Image.new('RGBA',(128,128),(0,0,0,0))
        draw=ImageDraw.Draw(im)
        draw.polygon([(64,8),(18+i*2,35),(32,76),(64,106-i*2),(96,76),(110-i*2,35)],fill=(30+i*20,100,160,255))
        draw.rectangle((58,70,70,120-i),fill='white')
        path=f'{relative}/{motif}.png'
        im.save(root/path)
        data['elements'].append({'code':f'{key}-{motif}','nameRu':f'TEST {ru}','motifClass':ru,'artifactCode':key,'motifIdentity':motif,'path':path,'verifiedBy':'SYNTHETIC TEST FIXTURE','reviewStatus':'проверено'})
    manifest=directory/'reviewed-fixture.json'
    manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2))
    return manifest


def load_fixture(conn,root):
    manifest=build_fixture(root)
    data,report=validate(manifest,root)
    if not report['valid']:
        raise RuntimeError(report)
    import_reviewed(conn,data,report)
    conn.execute('UPDATE elements SET is_fixture=true WHERE artifact_id=(SELECT id FROM artifacts WHERE code=%s)',(data['artifacts'][0]['code'],))
    return data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage-root',required=True,type=Path)
    parser.add_argument('--confirm-test-fixtures',action='store_true',required=True)
    args=parser.parse_args()
    if os.getenv('ALLOW_FIXTURES','false').lower()!='true':
        parser.error('Нужно явное ALLOW_FIXTURES=true; fixtures всегда имеют is_fixture=true')
    backup()
    with connect() as conn:
        data=load_fixture(conn,args.storage_root.resolve())
    print(f"Loaded {len(data['elements'])} synthetic fixtures. Real catalog count unchanged.")

if __name__=='__main__':
    main()
