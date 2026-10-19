"""Local visual review of exported images; no DB or external publication."""
import html
import json
from pathlib import Path
from PIL import Image, ImageDraw
BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'local-test/expansion-2026-10-13'

def main():
    manifest=json.loads((OUT/'manifest.json').read_text())
    records=manifest['records'];cards=[]
    for r in records:
        sid=r['id'];title=html.escape(r['title']);codes=html.escape(', '.join(r['codes']))
        example=json.loads((OUT/'previews'/(sid+'.json')).read_text())
        full='previews/'+example['fullImage']
        cards.append(f'<article><h2>{title}</h2><p>{codes}</p><a href="{full}"><img src="{full}"></a><p>Предложенный набор · фон с лучшим средним контрастом</p><a href="{sid}-variant.png"><img src="{sid}-variant.png"></a><p>Прозрачный PNG · плотнее · scale 0.8; бордюр вертикального формата, раппорт как образец</p><a href="previews/{sid}.json">Запрос, рецепт и SHA примера</a> · <a href="{sid}.json">Запрос и recipe API-проверки</a></article>')
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Расширение генератора</title><style>body{font:16px system-ui;background:#eee8dc;color:#18392d;margin:30px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}article{background:white;padding:16px;border-radius:10px}img{width:100%;max-height:380px;object-fit:contain;background:#d8ddd0}h2{font-size:18px}</style><h1>61 схема · 25 семейств · 110 элементов</h1><p>Реальные экспорты API, современная расстановка. Визуальный обзор агента не является индивидуальной приёмкой владельца или культурной экспертизой. Уменьшенные обзоры; полные файлы доступны по нажатию.</p><div class="grid">'+''.join(cards)+'</div>')
    for batch in range(0,len(records),12):
        group=records[batch:batch+12];sheet=Image.new('RGB',(1600,420*((len(group)+3)//4)), '#eee8dc');draw=ImageDraw.Draw(sheet)
        for j,r in enumerate(group):
            im=Image.open(OUT/r['image']).convert('RGBA');im.thumbnail((380,350));x=(j%4)*400;y=(j//4)*420
            sheet.paste(im,(x+(400-im.width)//2,y+30),im);draw.text((x+12,y+6),r['id'],fill='#18392d');draw.text((x+12,y+385),', '.join(c.replace('TP-E-','') for c in r['codes']),fill='#18392d')
        sheet.save(OUT/f'overview-{batch//12+1}.jpg',quality=92)
    # Full-resolution fragments of all motifs not used in defaults are reviewed separately.
    defaults={c for r in records for c in r['codes']}
    extra=[c for c in manifest['coveredElementCodes'] if c not in defaults]
    for batch in range(0,len(extra),24):
        group=extra[batch:batch+24];sheet=Image.new('RGB',(1440,220*((len(group)+5)//6)), '#f3ebdb');draw=ImageDraw.Draw(sheet)
        for j,c in enumerate(group):
            im=Image.open(BASE/'catalog-input/flat'/f'{c}.png').convert('RGBA');im=im.crop(im.getchannel('A').getbbox());im.thumbnail((220,180));x=j%6*240;y=j//6*220
            sheet.paste(im,(x+(240-im.width)//2,y+24),im);draw.text((x+8,y+4),c,fill='#18392d')
        sheet.save(OUT/f'extra-motifs-{batch//24+1}.jpg',quality=94)

if __name__=='__main__':main()
