"""Build a local review page from the actual API test artifacts, no new generation."""
import html
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

BASE=Path(__file__).resolve().parents[1]
ROOT=BASE/'local-test/composition-2026-10-12/gallery'


def main():
    data=json.loads((ROOT/'manifest.json').read_text())
    cards=[]
    names={'P1':'Венок','P2':'Направленный бордюр','P3':'Раппорт'}
    preview=Image.new('RGB',(1380,1710),'#f4f1e9');draw=ImageDraw.Draw(preview)
    try:font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',20)
    except OSError:font=ImageFont.load_default()
    details=Image.new('RGB',(1080,960),'#f3ebdb');dd=ImageDraw.Draw(details)
    for n,record in enumerate(data['records']):
        name=record['name'];short=name[:2]
        title=names[short]+(' · v0.2' if name.endswith('old') else ' · '+('бумажный фон' if name.endswith('paper') else ('светлый зелёный фон' if name.endswith('sage') else 'тёмный фон')))
        doc=json.loads((ROOT/record['recipe']).read_text());recipe=doc.get('generation',{}).get('recipe') or doc['recipe']
        label='Старый renderer · сравнение' if name.endswith('old') else ('Плотность: '+{'default':'обычная','sparse':'разреженная','dense':'плотная'}[recipe['selections']['parameters']])
        size='×'.join(map(str,record['size']))
        semantics='Бесшовный полный экспорт v0.2' if name=='P3-old' else 'Композиционное изображение'
        if record.get('outputKind')=='pattern_sample': semantics='Образец; края не кратны модулю '+str(recipe['repeat']['periodPx'])
        codes=', '.join(record['elementCodes'])
        extras=''
        if name.startswith('P3') and not name.endswith('old'):
            extras=f'<a href="{name}-module.png">Модуль PNG</a> · <a href="{name}-3x3.png">3×3 в натуральном размере</a>'
        review_status=record.get('visualReview','awaiting_owner_visual_review')
        review_label={'accepted':'Принято владельцем','accepted_with_density_controls_condition':'Приемлемо владельцу при настройке заполнения','revised_awaiting_owner_visual_review':'Исправленная версия после замечаний','acceptable_with_semantic_question':'Удовлетворительно; историческая семантика не подтверждена'}.get(review_status,review_status)
        cards.append(f'<article><p class="meta">{html.escape(review_label)}</p><h2>{html.escape(title)}</h2><p class="meta">{html.escape(label)} · {size}</p><a href="{record["image"]}"><img src="{record["image"]}" alt="{html.escape(title)}" loading="lazy"></a><p>{html.escape(record["description"])}</p><p class="meta">{codes}<br>{html.escape(semantics)}</p><p><a href="{record["recipe"]}">Recipe JSON</a> · <a href="{name}.jpg">JPG</a> · {extras}</p><details><summary>SHA256 PNG</summary><code>{record["pngSha256"]}</code></details></article>')
        im=Image.open(ROOT/record['image']).convert('RGBA');im.thumbnail((420,475))
        x=(n%3)*460+20;y=(n//3)*570+65
        draw.text((x,y-45),title,fill='#253b30',font=font)
        draw.text((x,y-20),size+' · '+label,fill='#61615a',font=font)
        preview.paste(im,(x+(420-im.width)//2,y+(475-im.height)//2),im)
        if name.endswith('paper'):
            codes={'P1':['TP-E-050','TP-E-051','TP-E-052'],'P2':['TP-E-061','TP-E-063','TP-E-066'],'P3':['TP-E-092','TP-E-091','TP-E-090']}[short]
            original=Image.open(ROOT/(name+'-3x3.png' if short=='P3' else record['image']))
            for col,code in enumerate(codes):
                placement=next(p for p in recipe['placements'] if p['code']==code)
                x0,y0,x1,y1=placement['bounds']
                if short=='P3':
                    w,h=recipe['repeat']['periodPx'];x0+=w;x1+=w;y0+=h;y1+=h
                crop=original.crop((x0-12,y0-12,x1+12,y1+12))
                dx=col*360+20;dy=(int(short[1])-1)*320
                dd.text((dx,dy+12),code+' · 100% crop',fill='#152c23',font=font)
                details.paste(crop,(dx,dy+50),crop)
    preview.save(ROOT/'overview.jpg',quality=95)
    details.save(ROOT/'detail-crops.jpg',quality=95)
    page='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TATAR PATTERN · визуальный пилот</title><style>
    *{box-sizing:border-box}body{margin:0;background:#f4f1e9;color:#20372b;font:16px/1.55 system-ui,sans-serif}header,main{max-width:1560px;margin:auto;padding:32px}h1{font:42px/1.1 Georgia,serif;margin:8px 0 20px}h2{font:25px Georgia,serif}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}article{background:#fffdf8;padding:20px;border:1px solid #ded8ca;border-radius:6px}img{width:100%;height:460px;object-fit:contain}a{color:#436746}.meta,summary{font-size:14px;color:#62675b}code{word-break:break-all;font-size:12px}.notice{padding:16px;background:#e8e1d1}.foot{padding:32px} @media(max-width:1000px){.grid{grid-template-columns:1fr}header,main{padding:20px}img{height:auto;max-height:650px}}</style>
    <header><p>TATAR PATTERN · 12.10.2026</p><h1>Три композиции на реальных TP-E</h1><div class="notice">Венки и раппорты оценены владельцем; бордюры исправлены после замечаний. Каждый ряд: новый бумажный вариант, вариант на другом фоне и сравнение со старым renderer v0.2. Нажмите изображение для просмотра при 100%.</div><p>Роли и интервалы — современные дизайнерские решения по ревизии tp-composition-review/1.0.0. Прохождение тестов не доказывает красоту или экспертную аутентичность.</p><p><a href="../border-revision/index.html">Исправленные бордюры и настройки</a> · <a href="manifest.json">Manifest и SHA</a> · <a href="overview.jpg">Общий лист</a> · <a href="detail-crops.jpg">Детали в конечном размере</a></p></header><main><section class="grid">'''+''.join(cards)+'''</section><p class="foot">Оценка владельца сохранена с SHA. Принятые P1/P3 и их рецепты не перезаписаны; прежние отклонённые P2 сохранены в previous-border-v1.0. Новая версия P2 не объявляется принятой автоматически. Default остаётся legacy.</p></main></html>'''
    (ROOT/'index.html').write_text(page)
    print(ROOT/'index.html')

if __name__=='__main__':main()
