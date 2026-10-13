"""Local review page: actual saved P2 API results, previews from the same pixels."""
import html
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
BASE=Path(__file__).resolve().parents[1]
ROOT=BASE/'local-test/composition-2026-10-12/border-revision'


def main():
    manifest=json.loads((ROOT/'manifest.json').read_text())
    cards=[];previews=[]
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',20)
    titles={'paper-default':'Бумажный фон · обычная плотность','sage-sparse':'Светлый зелёный фон · разреженный',
            'paper-dense':'Бумажный фон · плотный','portrait-default':'Вертикальный образец · обычная плотность'}
    for record in manifest['records']:
        doc=json.loads((ROOT/record['recipe']).read_text());recipe=doc['generation']['recipe']
        lines=recipe['modernAdditions'][0]['yPositions'];im=Image.open(ROOT/record['image'])
        crop=(0,max(0,lines[0]-20),im.width,min(im.height,lines[-1]+21))
        preview=im.crop(crop);preview.save(ROOT/(record['name']+'-strip.png'))
        preview.thumbnail((1120,450));previews.append((titles[record['name']],preview))
        record['previewCrop']=list(crop)
        n=recipe['layout']['repeatCount'];sub=' / '.join(str(reg['count']) for reg in recipe['layout']['registers'])
        title=html.escape(titles[record['name']])
        cards.append(f'<article><h2>{title}</h2><a href="{record["image"]}"><img src="{record["name"]}-strip.png" alt="{title}"></a><p class="meta">Фрагмент полного изображения {im.width}×{im.height}. Ряды: {sub} элементов. Нажмите, чтобы открыть полный PNG.</p><p>{html.escape(record["description"])}</p><p><a href="{record["recipe"]}">Recipe и evidence</a> · <a href="{record["name"]}.jpg">JPG</a></p></article>')
    sheet=Image.new('RGB',(1200,sum(im.height+65 for _,im in previews[:3])),'#f4f1e9');draw=ImageDraw.Draw(sheet);y=0
    for title,im in previews[:3]:
        draw.text((40,y+15),title,fill='#253b30',font=font);sheet.paste(im,((1200-im.width)//2,y+50),im);y+=im.height+65
    sheet.save(ROOT/'overview.jpg',quality=95)
    page='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TATAR PATTERN · исправленный бордюр</title><style>
    *{box-sizing:border-box}body{margin:0;background:#f4f1e9;color:#20372b;font:16px/1.55 system-ui,sans-serif}header,main{max-width:1440px;margin:auto;padding:28px}h1{font:40px Georgia,serif}h2{font:25px Georgia,serif}.grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}article{background:#fffdf8;padding:20px;border:1px solid #ded8ca}img{width:100%;height:350px;object-fit:contain}.meta{font-size:14px;color:#62675b}a{color:#436746}.notice{padding:16px;background:#e8e1d1}@media(max-width:900px){.grid{grid-template-columns:1fr}img{height:auto}}</style>
    <header><p>13.10.2026 · composition-pillow/1.1.0-pilot</p><h1>Бордюр с тремя согласованными ярусами</h1><div class="notice">Крупные цветы сверху, завитковые блоки посередине, малые цветы снизу. Ровный ритм и общие поля вместо отдельных подвешенных акцентов. Новая версия подготовлена после замечаний владельца; её визуальная приёмка ещё не записана.</div><p><strong>Основание:</strong> наблюдаемое расположение мотивов одного костюма NM-9585, кадр DSC9585. Такое распределение ролей опирается на источник. Повтор, интервалы и тонкие рамочные линии — современные решения. Историческая реконструкция и символика не утверждаются.</p><p><a href="manifest.json">Manifest</a> · <a href="../gallery/previous-border-v1.0/P2-sage.png">Прежний отклонённый вариант</a> · <a href="../gallery/index.html">Вся галерея</a></p></header><main><section class="grid">'''+''.join(cards)+'''</section><article><h2>Венок: настройка заполнения</h2><p>Существующие параметры dense и scale=1.2: 11 направленных акцентов, центр 244 px. Это дополнительный пример настройки; принятые изображения не перезаписаны.</p><a href="wreath-denser.png"><img src="wreath-denser.png" alt="Венок с увеличенным масштабом"></a><p><a href="wreath-denser.json">Запрос и recipe</a></p></article></main></html>'''
    (ROOT/'index.html').write_text(page)
    (ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(ROOT/'index.html')

if __name__=='__main__':main()
