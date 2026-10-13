"""Compose approved raster masks; never invent replacement motifs."""
import math
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

VERSION = 'algorithmic-pillow-v0.3'
SIZES = dict(architecture=(1024,1024),textile=(1024,1024),packaging=(1200,900),interior=(1200,900),web=(800,600))


def bounded(rules, key, default, low, high):
    return max(low, min(high, int(rules.get(key, default))))


def render(rows, selections, palette, rules, png: Path, jpg: Path):
    size = tuple(selections.get('outputSize') or SIZES[selections['usage']])
    composition = selections['composition']
    warnings = []
    if composition == 'rapport' and size[0] != size[1] and not selections.get('outputSize'):
        size = (size[0], size[0])
        warnings.append({'code':'RAPPORT_SQUARE','message':'Раппорт экспортирован квадратным для бесшовного повтора.'})
    palette={**palette,'bg':selections.get('backgroundColor') or palette['bg']}
    background=(0,0,0,0) if selections.get('transparentBackground') else palette['bg']
    canvas = Image.new('RGBA', size, background)
    masks = []
    for row in rows:
        with Image.open(row['local_path']) as src:
            src.load()
            rgba = src.convert('RGBA')
            rgba = rgba.crop(rgba.getchannel('A').getbbox())
            masks.append((rgba.getchannel('A'), ImageOps.grayscale(rgba), rgba))
    style = selections['style']
    original = selections.get('colorMode','original')=='original'
    if original and style!='heritage':
        warnings.append({'code':'ORIGINAL_COLORS','message':'Сохранены исходные цвета PNG; графический стиль применяется только в режиме силуэта.'})
    density = {'sparse':0.65,'default':1.0,'dense':1.4}[selections['parameters']]
    accents = [palette.get(k, palette['ink']) for k in ('gold','red','ink','blue')]

    def stamp(target, i, center, max_size, angle=0, wrap=False):
        alpha, luminance, rgba = masks[i % len(masks)]
        factor = 1.2 if style=='modern' and not original else 1.0
        max_size=max_size*selections.get('scale',1.0)
        width = max(20, int(max_size*factor))
        height = max(20, round(width*alpha.height/alpha.width))
        if height>width:
            width=max(1, round(width*width/height))
            height=max(20, int(max_size*factor))
        alpha = alpha.resize((width,height), Image.Resampling.LANCZOS)
        lum = luminance.resize(alpha.size, Image.Resampling.LANCZOS)
        color = accents[i%len(accents)] if style=='festive' else palette.get('gold',palette['ink'])
        if style=='modern':
            alpha=alpha.point(lambda v:255 if v>=128 else 0)
            color=palette['ink']
        if style=='heritage':
            shade=lum.point(lambda v:170+v//3)
            alpha=ImageChops.multiply(alpha,shade)
        if style=='porcelain-sign':
            alpha=ImageChops.subtract(alpha.filter(ImageFilter.MaxFilter(5)), alpha.filter(ImageFilter.MinFilter(5)))
            color=palette.get('blue',palette['ink'])
        sprite=Image.new('RGBA',alpha.size,color)
        sprite.putalpha(alpha)
        if style=='leather-mosaic':
            outline=ImageChops.subtract(alpha, alpha.filter(ImageFilter.MinFilter(5)))
            dash=Image.new('L',alpha.size,0)
            draw=ImageDraw.Draw(dash)
            for x in range(-height,width,10):
                draw.line((x,0,x+height,height),fill=255,width=4)
            thread=Image.new('RGBA',alpha.size,palette['ink'])
            thread.putalpha(ImageChops.multiply(outline,dash))
            sprite=Image.alpha_composite(sprite,thread)
        if original:
            sprite=rgba.resize((width,height),Image.Resampling.LANCZOS)
        if angle:
            sprite=sprite.rotate(angle, resample=Image.Resampling.BICUBIC,expand=True)
        x=round(center[0]-sprite.width/2)
        y=round(center[1]-sprite.height/2)
        if wrap:
            for dx in (-target.width,0,target.width):
                for dy in (-target.height,0,target.height):
                    target.alpha_composite(sprite,(x+dx,y+dy))
        else:
            target.alpha_composite(sprite,(x,y))

    if composition=='medallion':
        rays=max(len(rows),round(bounded(rules,'rays',8,4,24)*density))
        radius=min(size)*0.29
        for i in range(rays):
            angle=2*math.pi*i/rays
            stamp(canvas,i,(size[0]/2+radius*math.sin(angle),size[1]/2-radius*math.cos(angle)),min(size)*0.21,-math.degrees(angle))
        stamp(canvas,0,(size[0]/2,size[1]/2),min(size)*0.21)
        layout={'rays':rays,'radius':radius}
    elif composition=='border':
        count=max(len(rows),round(bounded(rules,'repeat_count',6,3,20)*density))
        step=size[0]/count
        for j in range(3):
            for i in range(count):
                stamp(canvas,i,((i+0.5)*step,size[1]*(j+1)/4),min(step*0.75,size[1]*0.22),180 if j==1 else 0)
        layout={'repeatCount':count,'rows':3}
    else:
        repeats=round(bounded(rules,'repeats',4,2,8)*density)
        # Independent axis periods preserve the seamless legacy export promise.
        # Do not couple motif scale to gcd(width,height).
        desired = min(size)/repeats
        def axis_period(length):
            counts = [n for n in range(1,9) if length % n == 0]
            return length//min(counts,key=lambda n:abs(length/n-desired))
        tile_width,tile_height = axis_period(size[0]),axis_period(size[1])
        tile=Image.new('RGBA',(tile_width,tile_height),background)
        grid=math.ceil(math.sqrt(len(rows)))
        cell_width,cell_height=tile_width/grid,tile_height/grid
        for i in range(len(rows)):
            stamp(tile,i,((i%grid)*cell_width,(i//grid)*cell_height),min(cell_width,cell_height)*0.75,wrap=True)
        for y in range(0,size[1],tile_height):
            for x in range(0,size[0],tile_width):
                canvas.paste(tile,(x,y))
        layout={'tileSize':tile_width if tile_width==tile_height else None,'moduleSize':[tile_width,tile_height],'repeats':repeats}
    png.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(png,format='PNG')
    solid=Image.new('RGBA',size,palette['bg'])
    solid.alpha_composite(canvas)
    solid.convert('RGB').save(jpg,format='JPEG',quality=95,subsampling=0)
    return {
        'outputKind':'repeat_module' if composition=='rapport' else 'composition_image','seamless':composition=='rapport',
        'repeat':{'periodPx':layout.get('moduleSize')} if composition=='rapport' else None,
        'algorithmVersion':VERSION,'size':list(size),'layout':layout,'palette':palette,
        'elements':[{'code':r['code'],'sha256':r['content_sha256'],'motif':r['motif_key'],'artifactCode':r['artifact_code'],'sourceFrame':r['frame']} for r in rows],
        'colorMode':selections.get('colorMode','original'),'transparentBackground':selections.get('transparentBackground',False),
        'isFixture':any(r['is_fixture'] for r in rows),
    }, warnings
