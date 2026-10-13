#!/usr/bin/env python3
"""Read-only image audit and source/flat/texture contact sheets for the completed batch."""
import csv, hashlib, json
from collections import Counter, defaultdict
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'Датасет/Элементы'
AUDIT=OUT/'audit/2026-10-06'
REVIEW=OUT/'processed_batch_review'
AUDIT.mkdir(parents=True,exist_ok=True); REVIEW.mkdir(exist_ok=True)
def rows(name): return list(csv.DictReader((OUT/name).open(encoding='utf-8-sig')))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=rows('manifest.csv'); supp=rows('supplemental_references.csv')
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf',19)
small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf',15)
records=[]
for style in ['flat','texture']:
 expected={r['code'] for r in manifest+(supp if style=='flat' else [])}
 actual={p.stem:p for p in (OUT/f'processed_{style}').glob('*.png')}
 for code,p in sorted(actual.items()):
  with Image.open(p) as im:
   im.load(); a=im.convert('RGBA').getchannel('A'); h=a.histogram(); box=a.point(lambda v:255 if v>=16 else 0).getbbox(); n=im.width*im.height
   records.append(dict(code=code,style=style,file=str(p.relative_to(ROOT)),sha256=sha(p),size=list(im.size),mode=im.mode,alpha_bbox=box,transparent_fraction=h[0]/n,semi_fraction=sum(h[1:250])/n,edge_contact=bool(box and (box[0]==0 or box[1]==0 or box[2]==im.width or box[3]==im.height)),expected=code in expected))
 print(style,'expected',len(expected),'present',len(actual),'missing',sorted(expected-set(actual)),'extra',sorted(set(actual)-expected))
def paste(canvas,p,x,y,w=282,h=278,bg='white'):
 if not p.exists():
  ImageDraw.Draw(canvas).text((x+30,y+100),'MISSING',fill='red',font=font); return
 with Image.open(p) as im:
  im=ImageOps.exif_transpose(im).convert('RGBA'); base=Image.new('RGBA',im.size,bg); base.alpha_composite(im); im=base.convert('RGB'); im.thumbnail((w,h)); canvas.paste(im,(x+(w-im.width)//2,y+(h-im.height)//2))
allrows=manifest+supp
for start in range(0,len(allrows),10):
 canvas=Image.new('RGB',(1800,1860),'#eeeee9'); d=ImageDraw.Draw(canvas)
 d.text((15,10),f'2026-10-06 | SOURCE / FLAT / TEXTURE | Sheet {start//10+1}',font=font,fill='black')
 for j,r in enumerate(allrows[start:start+10]):
  x=(j%2)*900+12; y=45+(j//2)*360
  d.text((x,y),r['code']+' | '+r.get('description','')[:66],font=small,fill='black')
  for k,p in enumerate([ROOT/r['crop_file'],OUT/'processed_flat'/f"{r['code']}.png",OUT/'processed_texture'/f"{r['code']}.png"]):
   paste(canvas,p,x+292*k,y+25)
   d.text((x+292*k,y+307),['source','flat','texture'][k],font=small,fill='black')
 canvas.save(REVIEW/f'compare_{start//10+1:02}.jpg',quality=94)
# Every processed image also shown correctly composited on a dark green background.
for start in range(0,len(records),40):
 canvas=Image.new('RGB',(1800,1600),'#eeeeea'); d=ImageDraw.Draw(canvas)
 for j,r in enumerate(records[start:start+40]):
  x=(j%8)*225;y=(j//8)*320
  paste(canvas,ROOT/r['file'],x,y,w=225,h=290,bg='#214f40')
  d.text((x+5,y+294),r['code']+' '+r['style'],font=small,fill='black')
 canvas.save(REVIEW/f'alpha_{start//40+1:02}.jpg',quality=94)
groups=defaultdict(list)
for r in records:groups[r['sha256']].append(r['style']+':'+r['code'])
report=dict(date='2026-10-06',files=records,exact_duplicate_groups=[v for v in groups.values() if len(v)>1],source_hash_mismatches=[r['code'] for r in manifest if sha(ROOT/r['crop_file'])!=r['crop_sha256']],counts=dict(Counter(r['style'] for r in records)))
(AUDIT/'batch_inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('sizes',Counter((r['style'],tuple(r['size'])) for r in records))
print('no transparency',[r['style']+':'+r['code'] for r in records if r['transparent_fraction']==0])
print('edge contacts',[r['style']+':'+r['code'] for r in records if r['edge_contact']])
print('duplicates',report['exact_duplicate_groups'])
