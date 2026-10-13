"""Real catalog + actual renderer, DB read-only, outputs only frontend/qa.
Not an HTTP generation/job/history test. No fixture substitutions.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
import psycopg
from psycopg.rows import dict_row
from PIL import Image
from app.config import Settings
from app.catalog import catalog
from app.generator import render
settings=Settings.from_env()
root=Path(__file__).resolve().parent/'downloads'/'real-flat-2026-10-08'
root.mkdir(exist_ok=True)
with psycopg.connect(settings.database_url,row_factory=dict_row) as conn:
    conn.execute('SET TRANSACTION READ ONLY')
    items=catalog(conn,settings)
    rows=[next(r for r in items if r['motif_class']=='угол рамки'),next(r for r in items if r['motif_class']=='цветок')]
    palette=conn.execute('SELECT colors FROM palettes LIMIT 1').fetchone()
results=[]
for label,transparent,color_mode,composition in [('original-alpha',True,'original','rapport'),('silhouette-solid',False,'silhouette','medallion')]:
    selection={'style':'heritage' if color_mode=='original' else 'modern','composition':composition,'parameters':'default','motifs':[], 'elementCodes':[r['code'] for r in rows],'scale':1,'transparentBackground':transparent,'backgroundColor':'#f1eff0','colorMode':color_mode,'palette':'emerald','usage':'web'}
    png=root/f'{label}.png';jpg=root/f'{label}.jpg'
    recipe,warnings=render(rows,selection,palette['colors'],{},png,jpg)
    with Image.open(png) as im:
        im.load(); alpha=im.getchannel('A').getextrema()
        assert im.mode=='RGBA' and (alpha[0]==0 if transparent else alpha==(255,255))
        png_size=list(im.size)
    with Image.open(jpg) as im:
        im.load();assert im.mode=='RGB' and list(im.size)==png_size
    results.append({'case':label,'pngSize':png_size,'alpha':alpha,'elements':[r['code'] for r in rows],'recipe':recipe,'warnings':warnings})
report={'environment':'local_project; PostgreSQL read-only; direct actual renderer; NOT HTTP generation','catalogTotal':len(items),'fixtures':sum(r['is_fixture'] for r in items),'results':results}
(root.parent.parent/'real-flat-readonly-2026-10-08.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'catalogTotal':len(items),'cases':[{'case':r['case'],'size':r['pngSize'],'alpha':r['alpha']} for r in results]},ensure_ascii=False))
