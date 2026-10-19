"""Local synthetic layout references for a separate ControlNet test; never training data."""
from pathlib import Path
import hashlib,json
from PIL import Image,ImageOps
AI=Path(__file__).resolve().parents[1];ROOT=AI.parent
OUT=AI/'draw-things/composition-test'

def main():
    OUT.mkdir(exist_ok=True);plans={
      'center': [('TP-E-066',300,512,430,False),('TP-E-054',270,300,710,False),('TP-E-054',270,724,710,True)],
      'border': [(('TP-E-066' if i%2==0 else 'TP-E-063'),145,112+i*160,512,bool(i%2)) for i in range(6)]}
    manifest=[]
    for name,items in plans.items():
        canvas=Image.new('RGBA',(1024,1024),'white');mask=Image.new('L',(1024,1024),0);placements=[]
        for code,length,x,y,mirror in items:
            p=ROOT/'Датасет/Элементы/processed_flat'/(code+'.png');im=Image.open(p).convert('RGBA');im=im.crop(im.getchannel('A').getbbox());im.thumbnail((length,length),Image.Resampling.LANCZOS)
            if mirror:im=ImageOps.mirror(im)
            pos=(round(x-im.width/2),round(y-im.height/2));canvas.alpha_composite(im,pos)
            # Max alpha union retains each motif's inner holes; placements do not overlap here.
            layer=Image.new('L',mask.size);layer.paste(im.getchannel('A'),pos)
            from PIL import ImageChops
            mask=ImageChops.lighter(mask,layer)
            placements.append({'code':code,'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'max_extent':length,'center':[x,y],'mirror':mirror})
        ref=OUT/(name+'-reference.png');canvas.convert('RGB').save(ref)
        silhouette=Image.new('RGB',(1024,1024),'white');silhouette.paste((0,0,0),mask=mask);silhouette.save(OUT/(name+'-silhouette.png'))
        manifest.append({'layout':name,'reference':ref.name,'placements':placements,'reference_sha256':hashlib.sha256(ref.read_bytes()).hexdigest(),'status':'SYNTHETIC_MODERN_TEST_LAYOUT_NOT_AUTHENTICITY_CLAIM','not_training_data':True})
    (OUT/'references.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print('Prepared two RGB references + two black-on-white silhouettes, not Canny maps or AI outputs.')
if __name__=='__main__':main()
