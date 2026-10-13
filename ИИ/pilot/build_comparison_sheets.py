"""Build paired sheets from already generated images; no model calls."""
from pathlib import Path
import json
from PIL import Image, ImageDraw
AI=Path(__file__).resolve().parents[1]
plan=json.loads((AI/'pilot/evaluation_plan.json').read_text())
variants=['baseline']+[f'step{step}_scale{scale}' for step in [200,400,600] for scale in [0.5,0.8]]
cases=[(t['id'],s) for t in plan['tasks'] for s in plan['seeds']]
out=AI/'pilot/results/comparison';out.mkdir(parents=True,exist_ok=True)
for start in range(0,len(cases),3):
    sheet=Image.new('RGB',(7*260,3*300),'#eeeeee');draw=ImageDraw.Draw(sheet)
    for row,(task,seed) in enumerate(cases[start:start+3]):
        for col,v in enumerate(variants):
            p=AI/'pilot/results'/v/f'{task}-{seed}.png'
            x=col*260;y=row*300
            if p.exists():
                im=Image.open(p).convert('RGB');im.thumbnail((256,256));sheet.paste(im,(x,y+40))
            draw.text((x+4,y+4),v,fill='black');draw.text((x+4,y+20),f'{task} / {seed}',fill='black')
    sheet.save(out/f'comparison-{start//3+1}.jpg',quality=95)
