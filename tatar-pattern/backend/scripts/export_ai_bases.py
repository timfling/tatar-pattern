"""Export accepted existing compositions; never invoke renderer, DB or GPU."""
import hashlib
import json
from pathlib import Path
from PIL import Image, __version__ as PILLOW_VERSION

BACKEND=Path(__file__).resolve().parents[1]
ROOT=BACKEND.parents[1]
IDS=['f10-wreath','f14-directed','f08-directed','f03-wreath','f16-wreath','f17-wreath','f24-wreath','f14-panel','f21-panel','f25-panel','f07-hanging','f18-hanging','f07-repeat','f10-directed','f25-directed']
NAMES=['Пестречинский медальон','Полотенечный бордюр','Цветочные ветви','Керамический цветок','Медальон мужского костюма','Медальон застёжки','Обрамление шамаиля','Геометрия полотенца','Многоцветное поле','Праздничная панель','Подвесы учкура','Подвесные украшения','Декоративное поле учкура','Керамический бордюр','Праздничная рамка']

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    output=BACKEND/'app/ai-assets';output.mkdir(exist_ok=True)
    provenance=json.loads((BACKEND/'app/composition-assets/v2/provenance.json').read_text())
    review=json.loads((BACKEND/'docs/OWNER-SCHEME-REVIEW-2026-10-13.json').read_text())
    families=json.loads((BACKEND/'app/composition-data/families.json').read_text())['families']
    entries=[]
    for index,sid in enumerate(IDS):
        example=next(v for v in provenance['examples'] if v['id']==sid)
        accepted=next(v for v in review['originalExamples'] if v['id']==sid)
        assert sid in review['accepted']
        original=BACKEND/'local-test/design-revision-2026-10-13/runtime-examples'/example['fullImage']
        assert sha(original)==example['fullSha256']==accepted['fullSha256']
        recipe=example['recipe'];background=recipe['palette']['bg']
        png=output/f'{sid}.png';rp=output/f'{sid}.recipe.json'
        if index<3:
            previous=BACKEND/'local-test/ai-composition-pilot-2026-10-17'/f'{sid}-img2img-base-rgb-1024.png'
            previous_recipe=previous.with_name(f'{sid}-img2img-base.recipe.json')
            png.write_bytes(previous.read_bytes());rp.write_bytes(previous_recipe.read_bytes())
        else:
            with Image.open(original) as image:
                rgba=image.convert('RGBA');assert rgba.getchannel('A').getextrema()==(255,255)
                ratio=min(1024/image.width,1024/image.height)
                size=tuple(round(v*ratio) for v in image.size)
                offset=((1024-size[0])//2,(1024-size[1])//2)
                result=Image.new('RGB',(1024,1024),background)
                result.paste(image.convert('RGB').resize(size,Image.Resampling.LANCZOS),offset)
                result.save(png)
                export={'size':[1024,1024],'mode':'RGB','background':background,'resizedSize':list(size),'offset':list(offset),'paddingLTRB':[offset[0],offset[1],1024-size[0]-offset[0],1024-size[1]-offset[1]],'sourceToOutputMatrix':[[size[0]/image.width,0,offset[0]],[0,size[1]/image.height,offset[1]],[0,0,1]],'resampler':'LANCZOS','pillowVersion':PILLOW_VERSION,'sha256':sha(png),'operation':'proportional fit and background padding; no crop/recolor/rearrangement'}
            rp.write_text(json.dumps({'schema':'tp-local-composition-base-export/1.0','source':{'path':str(original.relative_to(ROOT)),'sha256':sha(original),'ownerStatus':'owner_accepted_2026_10_13','acceptanceScope':'original composition; export not separately reviewed'},'request':example['request'],'recipe':recipe,'export':export},ensure_ascii=False,indent=2)+'\n')
        with Image.open(png) as im:
            assert im.mode=='RGB' and im.size==(1024,1024)
            # Descriptive swatches only; never recolor an input or generation.
            reduced=im.resize((128,128)).quantize(colors=7).convert('RGB')
            colors=sorted(reduced.getcolors(128*128),reverse=True)
            swatches=['#%02x%02x%02x'%rgb for _,rgb in colors[:6]]
        family=next(f for f in families if f['id']==recipe['familyId'])
        entries.append({'id':sid,'titleRu':NAMES[index],'schemeId':sid,'familyId':family['id'],'familyTitleRu':family['title_ru'],'elementCodes':recipe['selectedElementCodes'],'sources':recipe['elements'],'roles':recipe['roles'],'modernAdditions':recipe['modernAdditions'],'image':png.name,'sha256':sha(png),'recipe':rp.name,'recipeSha256':sha(rp),'size':[1024,1024],'mode':'RGB','palette':{'policy':'source','background':background,'swatches':swatches},'ownerStatus':'owner_accepted_2026_10_13','acceptanceScope':'original composition SHA; proportional export not separately reviewed','originalPath':str(original.relative_to(ROOT)),'originalSha256':sha(original),'externalTransferApproved':False,'aiSeamless':False,'aiQualityStatus':'local_candidates' if index<3 else 'pending_artistic_tests'})
    (output/'index.json').write_text(json.dumps({'schemaVersion':'tp-ai-bases/1.0.0','catalogVersion':'2026-10-18.1','bases':entries},ensure_ascii=False,indent=2)+'\n')
    print('Exported',len(entries),'registered bases (3 preserved + 12 new):',output/'index.json')

if __name__=='__main__':main()
