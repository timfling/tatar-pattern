"""Revision gallery with exact owner-reviewed before files and comparable after fields."""
import hashlib,html,json
from pathlib import Path
from PIL import Image,ImageDraw
from app.scheme_catalog import registry,ASSETS
from app.composition_metadata import review
from app.catalog import motif_key
from app.generator_v2 import render,replay
from app.models import Selections
from app.descriptions import describe
BASE=Path(__file__).resolve().parents[1];OUT=BASE/'local-test/design-revision-2026-10-13'

def field(im):
    im=im.convert('RGBA');out=Image.new('RGBA',(im.width*3,im.height*3))
    for y in range(3):
        for x in range(3):out.paste(im,(x*im.width,y*im.height))
    return out

def window(im,size=(1200,900)):
    im=im.convert('RGBA');out=Image.new('RGBA',size)
    for y in range(0,size[1],im.height):
        for x in range(0,size[0],im.width):out.paste(im,(x,y))
    return out

def border_crop(im,recipe):
    b=[[p['topLeft'][0]+p['workingBoundsSprite'][0],p['topLeft'][1]+p['workingBoundsSprite'][1],p['topLeft'][0]+p['workingBoundsSprite'][2],p['topLeft'][1]+p['workingBoundsSprite'][3]] for p in recipe['placements']];y1=max(0,min(v[1] for v in b)-20);y2=min(im.height,max(v[3] for v in b)+20)
    return im.crop((0,y1,im.width,y2))

def main():
    accepted=json.loads((BASE/'catalog-input/owner-accepted-2026-10-08.json').read_text());classes={e['code']:motif_key(e['motifClass']) for e in accepted['elements']}
    rows={i['code']:{'code':i['code'],'content_sha256':i['flat_sha256'],'local_path':BASE/'catalog-input/flat'/(i['code']+'.png'),
                     'artifact_code':i['cultural_attribution']['artifact_code'],'frame':i['cultural_attribution']['frame'],'motif_key':classes[i['code']]} for i in review()[0]['metadata.json']['items']}
    owner=json.loads((BASE/'docs/OWNER-SCHEME-REVIEW-2026-10-13.json').read_text());records=[]
    for sid in owner['needsRedesign']+owner['needsPolish']:
        scheme=next(s for s in registry()['schemes'] if s['id']==sid);old=json.loads((OUT/'original'/(sid+'.json')).read_text());sel={**old['request']['selections'],'registryVersion':registry()['registryVersion'],'elementCodes':scheme['defaultElementCodes']};sel=Selections(**sel).model_dump()
        chosen=[rows[c] for c in sel['elementCodes']]
        recipe,warnings=render(chosen,sel,{'bg':sel['backgroundColor']},OUT/(sid+'.png'),OUT/(sid+'.jpg'),42)
        recipe['description']=describe(recipe,sel)
        replay(chosen,recipe,OUT/'replay.png',OUT/'replay.jpg')
        assert (OUT/'replay.png').read_bytes()==(OUT/(sid+'.png')).read_bytes() and (OUT/'replay.jpg').read_bytes()==(OUT/(sid+'.jpg')).read_bytes()
        oldim=Image.open(OUT/'original'/(sid+'.png'));newim=Image.open(OUT/(sid+'.png'))
        if scheme['composition']=='rapport':
            before=window(oldim);after=window(newim)
            for label,source in [('before',oldim),('after',newim)]:
                repeated=field(source);repeated.thumbnail((1600,1600));repeated.save(OUT/(sid+'-'+label+'-3x3.png'))
        else:before=border_crop(oldim,old['recipe']);after=border_crop(newim,recipe)
        for name,im in [('before',before),('after',after)]:
            im.thumbnail((1000,1000));im.save(OUT/(sid+'-'+name+'.png'))
        result={'id':sid,'title':scheme['titleRu'],'group':scheme['design']['ownerFeedbackGroup'],'request':{'selections':sel,'seed':42},'recipe':recipe,'warnings':warnings,
                'oldCodes':old['request']['selections']['elementCodes'],'newCodes':sel['elementCodes'],'oldSha256':old['fullSha256'],'newSha256':hashlib.sha256((OUT/(sid+'.png')).read_bytes()).hexdigest(),
                'display':'same_native_pixel_scale_1200x900_window_separate_3x3' if scheme['composition']=='rapport' else 'full_width_visible_band_crop_alpha16_review_only'}
        (OUT/(sid+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2));records.append(result)
        print(sid,'ok',newim.size,flush=True)
    for p in (OUT/'replay.png',OUT/'replay.jpg',OUT/'replay.module.png'):p.unlink(missing_ok=True)
    for group in ('needs_redesign','needs_polish'):
        selected=[r for r in records if r['group']==group]
        for batch in range(0,len(selected),6):
            chunk=selected[batch:batch+6];sheet=Image.new('RGB',(1800,440*len(chunk)),'#eee8dc');draw=ImageDraw.Draw(sheet)
            for j,r in enumerate(chunk):
                for col,name in enumerate(('before','after')):
                    im=Image.open(OUT/(r['id']+'-'+name+'.png')).convert('RGBA');im.thumbnail((860,380));x=col*900;y=j*440
                    sheet.paste(im,(x+(900-im.width)//2,y+40+(380-im.height)//2),im);draw.text((x+12,y+8),r['id']+' / '+name,fill='#18392d')
            sheet.save(OUT/f'{group}-{batch//6+1}.jpg',quality=94)
    (OUT/'manifest.json').write_text(json.dumps({'registryVersion':registry()['registryVersion'],'registrySha256':registry()['sha256'],'records':records,'ownerAccepted':owner['accepted'],'status':'awaiting_owner_visual_review'},ensure_ascii=False,indent=2))
    content=[]
    for group,title in [('needs_redesign','1. Заметно сомнительные — переработаны'),('needs_polish','2. Возможно удовлетворительные — доработаны')]:
        content.append('<h2>'+title+'</h2>')
        for number,r in enumerate([r for r in records if r['group']==group],1):
            sid=r['id'];s=next(s for s in registry()['schemes'] if s['id']==sid)
            changed=r['oldCodes']!=r['newCodes'];codes=', '.join(r['newCodes'])
            content.append(f'<article id="{sid}"><h3>{number}. {html.escape(r["title"])}</h3><p>{html.escape(s["design"]["intentRu"])} {"Предложенный набор изменён явно." if changed else "Выбранный набор сохранён."} {codes}</p><p><strong>Возможное применение:</strong> {html.escape(s["applicationRu"])}</p><div class="pair"><figure><figcaption>До</figcaption><img src="{sid}-before.png"></figure><figure><figcaption>После</figcaption><img src="{sid}-after.png"></figure></div><p>{"Одинаковое поле1200×900 и одинаковый экранный масштаб обеих версий; края этого обзорного окна не обязаны совпадать с периодом модуля." if s["composition"]=="rapport" else "Рабочая область всей полосы; полные поля и слабые края PNG сохраняются в экспорте."}</p><a href="{sid}.png">Полный новый PNG / модуль</a> · {'<a href='+chr(34)+sid+'-after-3x3.png'+chr(34)+'>Новый повтор3×3</a> · ' if s['composition']=='rapport' else ''} · <a href="{sid}.json">Запрос, рецепт и SHA</a></article>')
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Доработка37 схем</title><style>body{font:16px system-ui;color:#18392d;background:#eee8dc;margin:30px;max-width:1600px}article{background:white;padding:20px;margin:24px 0;border-radius:12px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}figure{margin:0}img{width:100%;height:420px;object-fit:contain;background:#eee8dc}h2{margin-top:60px}@media(max-width:700px){.pair{grid-template-columns:1fr}img{height:340px}}</style><h1>37 доработанных схем · сравнение до/после</h1><p>21 схема переработана первой;16 доработаны. Остальные24 приняты владельцем и сохранены. Новые варианты ожидают оценки. Раппорты сравниваются в одинаковом окне1200×900 без изменения масштаба мотивов. Отдельно доступен повтор3×3. Бордюры показаны целой полосой без пустых полей. Полные PNG и рецепты доступны отдельно. Современная расстановка, культурная экспертиза не заявляется.</p>'+''.join(content))

if __name__=='__main__':main()
