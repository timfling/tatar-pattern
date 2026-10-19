"""Generate API examples from real renderer, choosing a readable example background."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw
from app.generator_v2 import render
from app.scheme_catalog import registry, ASSETS
from app.composition_metadata import review
from app.models import Selections
from app.catalog import motif_key
BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'local-test/expansion-2026-10-13/previews'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,default=OUT);args=parser.parse_args()
    output=args.output_dir
    accepted=json.loads((BASE/'catalog-input/owner-accepted-2026-10-08.json').read_text())
    classes={e['code']:motif_key(e['motifClass']) for e in accepted['elements']}
    rows={i['code']:{'code':i['code'],'content_sha256':i['flat_sha256'],'local_path':BASE/'catalog-input/flat'/(i['code']+'.png'),
                     'artifact_code':i['cultural_attribution']['artifact_code'],'frame':i['cultural_attribution']['frame'],'motif_key':classes[i['code']]} for i in review()[0]['metadata.json']['items']}
    output.mkdir(parents=True,exist_ok=True);ASSETS.mkdir(parents=True,exist_ok=True);records=[]
    for scheme in registry()['schemes']:
        sid=scheme['id'];chosen=[rows[c] for c in scheme['defaultElementCodes']]
        selections=Selections(renderer='composition-v2',schemeId=sid,registryVersion=registry()['registryVersion'],style='heritage',
            composition=scheme['composition'],elementCodes=scheme['defaultElementCodes'],palette='emerald',usage='textile',
            outputSize=[1200,900] if scheme['composition']=='border' else [1024,1024]).model_dump()
        variants=[]
        for name,bg in [('paper','#f3ebdb'),('dark','#172d24')]:
            sel={**selections,'backgroundColor':bg};png=output/(sid+'-'+name+'.png');jpg=png.with_suffix('.jpg')
            recipe,warnings=render(chosen,sel,{'bg':bg},png,jpg,42)
            variants.append((min(x['meanRgbDistance'] for x in recipe['diagnostics']['contrast']),name,sel,recipe,warnings))
        _,name,sel,recipe,warnings=max(variants,key=lambda v:v[0]);full=output/(sid+'-'+name+'.png')
        preview=Image.open(full).convert('RGBA');transform={'kind':'reduced_full_output'}
        if scheme.get('design'):
            if scheme['composition']=='rapport':
                module=preview;preview=Image.new('RGBA',(1200,900))
                for y in range(0,900,module.height):
                    for x in range(0,1200,module.width):preview.paste(module,(x,y))
                transform={'kind':'repeat_field','size':[1200,900],'periodPx':list(module.size),'seamlessView':1200%module.width==900%module.height==0}
            else:
                bounds=[[p['topLeft'][0]+p['workingBoundsSprite'][0],p['topLeft'][1]+p['workingBoundsSprite'][1],p['topLeft'][0]+p['workingBoundsSprite'][2],p['topLeft'][1]+p['workingBoundsSprite'][3]] for p in recipe['placements']]
                crop=[0,max(0,min(b[1] for b in bounds)-20),preview.width,min(preview.height,max(b[3] for b in bounds)+20)]
                preview=preview.crop(crop);transform={'kind':'visible_band','crop':crop,'alphaThresholdForView':16,'fullExportUnchanged':True}
        preview.thumbnail((600,600));path=ASSETS/(sid+'.png');preview.save(path)
        record={'previewTransform':transform,'reviewStatus':scheme['reviewStatus'],'id':sid,'backgroundChoice':name,'request':{'selections':sel,'seed':42},'recipe':recipe,'warnings':warnings,
                'fullImage':full.name,'fullSha256':hashlib.sha256(full.read_bytes()).hexdigest(),'previewSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'previewSize':list(preview.size)}
        (output/(sid+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2));records.append(record)
    (ASSETS/'provenance.json').write_text(json.dumps({'registryVersion':registry()['registryVersion'],'registrySha256':registry()['sha256'],'examples':records,'label':'actual_reduced_renderer_examples_not_current_selection'},ensure_ascii=False,indent=2))
    for batch in range(0,len(records),12):
        group=records[batch:batch+12];sheet=Image.new('RGB',(1600,400*((len(group)+3)//4)),'#eee8dc');draw=ImageDraw.Draw(sheet)
        for j,r in enumerate(group):
            im=Image.open(ASSETS/(r['id']+'.png')).convert('RGBA');im.thumbnail((380,340));x=j%4*400;y=j//4*400
            sheet.paste(im,(x+(400-im.width)//2,y+30),im);draw.text((x+12,y+5),r['id']+' / '+r['backgroundChoice'],fill='#18392d')
        sheet.save(output/f'overview-{batch//12+1}.jpg',quality=94)
    print(f"Prepared {len(records)} versioned API examples with source/request/SHA")

if __name__=='__main__':main()
