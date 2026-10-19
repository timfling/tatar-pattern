"""Saved API outputs comparing grouped registers with interleaved weights."""
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
BASE=Path(__file__).resolve().parents[1]
ROOT=BASE/'local-test/composition-2026-10-12/border-weights'


def main():
    data=json.loads((ROOT/'manifest.json').read_text())
    names=['registers']+[r['name'] for r in data['records']]
    titles={'registers':'Три яруса · предыдущая схема','interwoven-default':'Смешение весов · обычная плотность','interwoven-dense':'Смешение весов · плотный','interwoven-sage':'Смешение весов · зелёный фон'}
    cards=[];images=[]
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',20)
    for name in names:
        doc=json.loads((ROOT/(name+'.json')).read_text());r=doc['generation']['recipe']
        frame=next(a for a in r['modernAdditions'] if a['kind']=='horizontal_border_rules')
        im=Image.open(ROOT/(name+'.png'));a,b=frame['yPositions']
        crop=im.crop((0,max(0,a-20),im.width,min(im.height,b+21)));crop.save(ROOT/(name+'-preview.png'))
        crop.thumbnail((1120,440));images.append((titles[name],crop))
        cards.append(f'<article><h2>{titles[name]}</h2><a href="{name}.png"><img src="{name}-preview.png" alt="{titles[name]}"></a><p>{doc["generation"]["description"]}</p><p><a href="{name}.json">Запрос, recipe и SHA</a> · <a href="{name}.png">Полный PNG</a></p></article>')
    sheet=Image.new('RGB',(1200,sum(im.height+65 for _,im in images)), '#f4f1e9');draw=ImageDraw.Draw(sheet);y=0
    for title,im in images:
        draw.text((40,y+12),title,fill='#253b30',font=font);sheet.paste(im,((1200-im.width)//2,y+45),im);y+=im.height+65
    sheet.save(ROOT/'overview.jpg',quality=95)
    (ROOT/'index.html').write_text('''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TATAR PATTERN · смешение визуальных весов</title><style>body{margin:0;background:#f4f1e9;color:#20372b;font:16px/1.55 system-ui}header,main{max-width:1400px;margin:auto;padding:24px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}article{padding:20px;background:#fffdf8;border:1px solid #ded8ca}h1,h2{font-family:Georgia,serif}img{width:100%;height:350px;object-fit:contain}a{color:#436746}@media(max-width:900px){.grid{grid-template-columns:1fr}}</style><header><p>13.10.2026 · composition-pillow/1.2.0-pilot</p><h1>Вес мотивов меняется внутри ритма</h1><p>Те же TP-E-061,063,066: крупные цветы и зелёные блоки чередуются по высоте, малые цветы образуют локальные группы вокруг них. Тонкая направляющая — современное композиционное добавление, не восстановленный стебель.</p><p>«Тяжёлый / средний / лёгкий» — относительная дизайнерская оценка размера, заполненности и деталей, а не культурная классификация. Схема interwoven принята владельцем 13.10.2026 как современная композиция с опорой на источник. Явно принятый показанный пример — плотный вариант; остальные карточки демонстрируют параметры той же схемы. Предыдущая registers сохранена отдельно.</p><p>Показаны фрагменты полных экспортов. Нажмите изображение для полного PNG.</p></header><main><section class="grid">'''+''.join(cards)+'''</section></main></html>''')
    print(ROOT/'index.html')

if __name__=='__main__':main()
