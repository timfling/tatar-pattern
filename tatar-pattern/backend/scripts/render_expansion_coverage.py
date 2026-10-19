"""Render every reviewed motif in a compatible scheme, preserving the whole selection."""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw
from app.generator_v2 import render, replay
from app.scheme_catalog import registry
from app.composition_metadata import review
from app.models import Selections
from app.descriptions import describe
from app.errors import APIError
from app.catalog import motif_key
BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'local-test/expansion-2026-10-13/coverage'
PALETTE={'bg':'#f3ebdb','ink':'#152c23','gold':'#948861','red':'#9c3833','blue':'#23415c'}

def main():
    items=review()[0]['metadata.json']['items']
    accepted=json.loads((BASE/'catalog-input/owner-accepted-2026-10-08.json').read_text())
    classes={e['code']:motif_key(e['motifClass']) for e in accepted['elements']}
    rows={i['code']:{'code':i['code'],'content_sha256':i['flat_sha256'],'local_path':BASE/'catalog-input/flat'/(i['code']+'.png'),
                      'artifact_code':i['cultural_attribution']['artifact_code'],'frame':i['cultural_attribution']['frame'],'motif_key':classes[i['code']]} for i in items}
    for row in rows.values():assert hashlib.sha256(row['local_path'].read_bytes()).hexdigest()==row['content_sha256']
    OUT.mkdir(parents=True,exist_ok=True);records=[]
    for code in rows:
        schemes=[s for s in registry()['schemes'] if code in s['allowedElementCodes']]
        schemes.sort(key=lambda s:(s['layout']!='hanging_panel',s['layout']!='hierarchical_repeat',s['id']))
        for scheme in schemes:
            selected=list(dict.fromkeys(scheme['defaultElementCodes']+[code]))
            selections=Selections(renderer='composition-v2',schemeId=scheme['id'],style='heritage',composition=scheme['composition'],
                                  elementCodes=selected,palette='emerald',usage='textile',parameters='default',
                                  outputSize=[1200,900] if scheme['composition']=='border' else [1024,1024]).model_dump()
            try:recipe,warnings=render([rows[c] for c in selected],selections,PALETTE,OUT/(code+'.png'),OUT/(code+'.jpg'),42)
            except APIError:continue
            recipe['description']=describe(recipe,selections)
            assert set(recipe['usedElementCodes'])==set(selected) and recipe['diagnostics']['overlapPixels']==0
            replay([rows[c] for c in selected],recipe,OUT/'replay.png',OUT/'replay.jpg')
            assert (OUT/'replay.png').read_bytes()==(OUT/(code+'.png')).read_bytes()
            assert (OUT/'replay.jpg').read_bytes()==(OUT/(code+'.jpg')).read_bytes()
            (OUT/(code+'.json')).write_text(json.dumps({'request':{'selections':selections,'seed':42},'recipe':recipe,'warnings':warnings},ensure_ascii=False,indent=2))
            records.append({'code':code,'schemeId':scheme['id'],'selectedElementCodes':selected,'image':code+'.png','sha256':hashlib.sha256((OUT/(code+'.png')).read_bytes()).hexdigest()})
            break
        else:raise RuntimeError('No working scheme for '+code)
    for path in (OUT/'replay.png',OUT/'replay.jpg',OUT/'replay.module.png'):path.unlink(missing_ok=True)
    (OUT/'manifest.json').write_text(json.dumps({'count':len(records),'records':records,'factsBasis':'real_reviewed_assets_direct_renderer_no_database'},ensure_ascii=False,indent=2))
    for batch in range(0,len(records),20):
        group=records[batch:batch+20];sheet=Image.new('RGB',(1600,350*((len(group)+4)//5)),'#eee8dc');draw=ImageDraw.Draw(sheet)
        for j,r in enumerate(group):
            im=Image.open(OUT/r['image']).convert('RGBA');im.thumbnail((300,280));x=j%5*320;y=j//5*350
            sheet.paste(im,(x+(320-im.width)//2,y+30),im);draw.text((x+10,y+5),r['code']+' / '+r['schemeId'],fill='#18392d')
        sheet.save(OUT/f'overview-{batch//20+1}.jpg',quality=94)
    print(f"Rendered and byte-replayed {len(records)} reviewed motifs")

if __name__=='__main__':main()
