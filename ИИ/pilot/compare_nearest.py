"""Local train copying triage. Pixel distance is a candidate finder, not proof."""
from pathlib import Path
import argparse, csv, math
from PIL import Image, ImageDraw, ImageChops, ImageStat

AI=Path(__file__).resolve().parents[1]
def thumb(p):
    im=Image.open(p).convert('RGBA');bg=Image.new('RGBA',im.size,'white');bg.alpha_composite(im)
    return bg.convert('RGB').resize((64,64),Image.Resampling.LANCZOS)
def distance(a,b):
    st=ImageStat.Stat(ImageChops.difference(a,b));return math.sqrt(sum(x*x for x in st.rms)/3)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('generated',type=Path);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    refs=[(p,thumb(p)) for p in (AI/'dataset/texture-v1/train').glob('*.png')]
    a.output.mkdir(parents=True,exist_ok=True);rows=[]
    for p in sorted(a.generated.glob('*.png')):
        if p.name=='conditioning.png':continue
        im=thumb(p);near=sorted([(distance(im,t),r) for r,t in refs],key=lambda x:x[0])[:3]
        sheet=Image.new('RGB',(1000,280),'white');d=ImageDraw.Draw(sheet)
        for i,q in enumerate([p]+[r for _,r in near]):
            v=Image.open(q).convert('RGB');v.thumbnail((240,240));sheet.paste(v,(i*250,0));d.text((i*250+5,246),q.name,fill='black')
        sheet.save(a.output/(p.stem+'-nearest.jpg'),quality=92)
        for rank,(v,r) in enumerate(near,1):rows.append([p.name,rank,r.name,round(v,3),'VISUAL_REVIEW_REQUIRED'])
    with (a.output/'nearest.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['generated','rank','train','rgb_rms_64px','status']);w.writerows(rows)
if __name__=='__main__':main()
