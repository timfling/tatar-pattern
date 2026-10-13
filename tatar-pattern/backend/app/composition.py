"""Three explicitly scoped contemporary layouts using accepted RGBA assets."""
import hashlib
import math
import random
from pathlib import Path
from PIL import __version__ as PILLOW_VERSION
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageStat
from .composition_metadata import metadata, pilot_for, compatibility, review
from .errors import APIError
from .generator import SIZES

VERSION = 'composition-pillow/1.1.0-pilot'
REPLAY_VERSIONS = {VERSION, 'composition-pillow/1.0.0-pilot'}
SCHEMA = 'tp-composition-recipe/1.0.0'


def transformed(row, long_side, target_axis=None):
    item = metadata(row)
    floor = item['readability']['recommended_min_long_side_px']
    long_side = max(floor, round(long_side))
    with Image.open(row['local_path']) as src:
        rgba = src.convert('RGBA')
        crop_box = rgba.getchannel('A').getbbox()
        rgba = rgba.crop(crop_box)
    dims = [max(1,round(v*long_side/max(rgba.size))) for v in rgba.size]
    sprite = rgba.resize(dims, Image.Resampling.LANCZOS)
    base = item['orientation']['angle_deg']
    delta = 0 if base is None or target_axis is None else (target_axis-base+180)%360-180
    if delta and item['transforms']['rotation']['policy'] != 'continuous_angles_allowed_for_new_design':
        raise APIError(422,'ROTATION_UNSUPPORTED','Метаданные не разрешают выбранный поворот.', {'code':row['code']})
    before = sprite.size
    sprite = sprite.rotate(-delta, resample=Image.Resampling.BICUBIC, expand=True) if delta else sprite
    co, si = math.cos(math.radians(delta)), math.sin(math.radians(delta))
    sx, sy = dims[0]/rgba.width, dims[1]/rgba.height
    # Crop coordinates -> uniform resize (integer raster rounding) -> rotation
    # about image center -> expand translation. Same map for both named points.
    a,b,c,d = co*sx,-si*sy,si*sx,co*sy
    tx = sprite.width/2-co*before[0]/2+si*before[1]/2
    ty = sprite.height/2-si*before[0]/2-co*before[1]/2
    def point(uv):
        if uv is None: return None
        x,y=uv[0]*rgba.width,uv[1]*rgba.height
        return [a*x+b*y+tx,c*x+d*y+ty]
    working=sprite.getchannel('A').point(lambda v:255 if v>=16 else 0).getbbox()
    info = {'workingBoundsSprite':list(working),'code':row['code'], 'sha256':row['content_sha256'], 'metadataVersion':item['metadata_version'],
            'alphaCrop':list(crop_box), 'cropSize':list(rgba.size), 'resizedSize':dims, 'spriteSize':list(sprite.size),
            'longSideBeforeRotation':long_side, 'recommendedMinLongSide':floor, 'baseAxis':base,
            'targetAxis':target_axis, 'clockwiseDegrees':delta, 'reflected':False,
            'cropToSpriteMatrix':[[a,b,tx],[c,d,ty],[0,0,1]],
            'attachmentSprite':point(item['attachment']['uv']), 'visualCenterSprite':point(item['visual_center']['uv']),
            'evidence':['OBS-'+row['code'],'D01']}
    return sprite, info


def render_composition(rows, selections, palette, png:Path, jpg:Path, seed=0):
    pilot = pilot_for(rows,selections['composition'])
    if selections.get('colorMode','original') != 'original':
        raise APIError(422,'PILOT_REQUIRES_ORIGINAL','Для пилота сохраняются внутренние цветовые поля; выберите original.', {'selectedElementCodes':[r['code'] for r in rows]})
    density = selections['parameters']
    requested = tuple(selections.get('outputSize') or SIZES[selections['usage']])
    palette = {**palette,'bg':selections.get('backgroundColor') or palette['bg']}
    bg = (0,0,0,0) if selections.get('transparentBackground') else palette['bg']
    composition = selections['composition']
    rng = random.Random(seed)
    warnings = []
    placements = []
    by_code = {r['code']:r for r in rows}
    sprites = {}
    size_factor = {'sparse':0.94,'default':1.0,'dense':1.06}[density]*selections.get('scale',1.0)
    gap_ratio = {'sparse':0.35,'default':0.24,'dense':0.18}[density]
    def get(code,length,target=None):
        key=(code,round(length),target)
        if key not in sprites: sprites[key]=transformed(by_code[code],length,target)
        return sprites[key]
    periodic = composition == 'rapport'
    if periodic:
        lengths = {c:max(metadata(by_code[c])['readability']['recommended_min_long_side_px'],round(n*size_factor)) for c,n in pilot['suggested_long_sides_px'].items()}
        m,mi=get('TP-E-092',lengths['TP-E-092'],0)
        a,ai=get('TP-E-091',lengths['TP-E-091'],0)
        band,bi=get('TP-E-090',lengths['TP-E-090'],90)
        gap = math.ceil(gap_ratio*max(m.size+band.size+a.size))
        def working_size(info):
            b=info['workingBoundsSprite'];return b[2]-b[0],b[3]-b[1]
        mw,mh=working_size(mi);aw,ah=working_size(ai);bw,bh=working_size(bi)
        minimum=(max(bw+2*gap,mw+aw+2*gap),mh+bh+2*gap)
        natural=max({'sparse':480,'default':420,'dense':380}[density],*minimum)
        module_size=tuple(selections.get('moduleSize') or (natural,natural))
        if module_size[0]<minimum[0] or module_size[1]<minimum[1]:
            raise APIError(422,'MODULE_TOO_SMALL','Модуль не вмещает мотивы с читаемыми деталями и интервалами.', {'minimumSize':list(minimum),'requestedSize':list(module_size)})
        target=Image.new('RGBA',module_size,bg)
    else:
        module_size=None
        target=Image.new('RGBA',requested,bg)
    masks=[]
    def place(code,length,position,axis=None,anchor='visual_center',role=None,wrap=False):
        sprite,info=get(code,length,axis)
        info={**info}
        point=info['attachmentSprite'] if anchor=='attachment' else info['visualCenterSprite']
        if anchor=='working_center':
            b=info['workingBoundsSprite'];point=[(b[0]+b[2])/2,(b[1]+b[3])/2]
        if point is None:
            if anchor=='attachment':
                raise APIError(422,'ATTACHMENT_UNKNOWN','Неизвестное основание не заменяется нижней серединой.', {'code':code})
            point=[sprite.width/2,sprite.height/2]
        x,y=round(position[0]-point[0]),round(position[1]-point[1])
        occupancy=Image.new('L',target.size,0)
        shifts=[(dx,dy) for dx in (-target.width,0,target.width) for dy in (-target.height,0,target.height)] if wrap else [(0,0)]
        for dx,dy in shifts:
            target.alpha_composite(sprite,(x+dx,y+dy))
            occupancy.paste(sprite.getchannel('A'),(x+dx,y+dy))
        info.update({'role':role,'anchor':anchor,'anchorPosition':list(position),'topLeft':[x,y], 'wrap':wrap,
                     'bounds':[x,y,x+sprite.width,y+sprite.height],
                     'attachmentOutput':([x+info['attachmentSprite'][0],y+info['attachmentSprite'][1]] if info['attachmentSprite'] else None)})
        info['cropToOutputMatrix']=[info['cropToSpriteMatrix'][0][:],info['cropToSpriteMatrix'][1][:],[0,0,1]]
        info['cropToOutputMatrix'][0][2]+=x;info['cropToOutputMatrix'][1][2]+=y
        if not wrap and (x<0 or y<0 or x+sprite.width>target.width or y+sprite.height>target.height):
            raise APIError(422,'COMPOSITION_TOO_LARGE','Мотив выходит за поля при этом масштабе.', {'code':code,'bounds':info['bounds'],'size':list(target.size)})
        placements.append(info);masks.append(occupancy.point(lambda v:255 if v>=16 else 0))
    additions=[]
    if composition=='medallion':
        w,h=requested; unit=min(w,h); cx,cy=w/2,h/2
        center=max(96,unit*0.1875*size_factor)
        accent=max(72,center*0.62)
        support=max(112,center*0.95)
        radius=unit*{'sparse':0.28,'default':0.27,'dense':0.265}[density]
        count={'sparse':7,'default':9,'dense':11}[density]
        # Leave an open lower arc for one intact framing pair (never a radial ray).
        angles=[-140+i*280/(count-1) for i in range(count)]
        phase=rng.choice([-2,0,2])
        # A modern open guide is drawn before the actual PNG motifs.
        guide=Image.new('RGBA',target.size,0)
        draw=ImageDraw.Draw(guide)
        ink=ImageColor.getrgb(palette.get('gold',palette['ink']))+(90,)
        draw.arc((cx-radius,cy-radius,cx+radius,cy+radius),-230,50,fill=ink,width=1)
        target=Image.alpha_composite(target,guide)
        for angle in angles:
            angle+=phase
            pos=(cx+radius*math.sin(math.radians(angle)),cy-radius*math.cos(math.radians(angle)))
            place('TP-E-051',accent,pos,angle,'attachment','outer_axial_accent')
        place('TP-E-050',center,(cx,cy),0,role='center')
        place('TP-E-052',support,(cx,cy+radius),180,'attachment','lower_framing_pair')
        additions=[{'kind':'open_circle_guide','radius':radius,'center':[cx,cy],'claimType':'contemporary_design','evidence':['D01']}]
        layout={'rays':count,'radius':radius,'centerLongSide':round(center),'gapRatio':gap_ratio,'phaseDegrees':phase}
    elif composition=='border':
        w,h=requested
        # Three registers reflect the observed object hierarchy, without
        # claiming reconstruction of the original garment or invisible joins.
        factor={'sparse':1.08,'default':1.0,'dense':0.9}[density]*selections.get('scale',1.0)
        main_len=168*factor;link_len=main_len*0.8;small_len=main_len*0.4
        main,main_info=get('TP-E-061',main_len)
        link,link_info=get('TP-E-063',link_len,90)
        small,small_info=get('TP-E-066',small_len)
        def footprint(info):
            box=info['workingBoundsSprite'];return box[2]-box[0],box[3]-box[1]
        mw,mh=footprint(main_info);lw,lh=footprint(link_info);sw,sh=footprint(small_info)
        margin=max(32,round(min(w,h)*0.07))
        gap=math.ceil(gap_ratio*max(main.size+link.size))
        width=max(mw,lw,2*sw+gap)
        count=math.floor((w-2*margin+gap)/(width+gap))
        if count<2:
            raise APIError(422,'BORDER_TOO_NARROW','Для ритма нужны два читаемых повтора; уменьшите масштаб или выберите более широкий формат.', {'minimumWidth':math.ceil(2*width+gap+2*margin)})
        step=(w-2*margin)/count
        band_height=mh+lh+sh+2*gap
        top=(h-band_height)/2
        centers=[margin+(i+0.5)*step for i in range(count)]
        primary_y=top+mh/2
        connector_y=top+mh+gap+lh/2
        small_y=top+mh+gap+lh+gap+sh/2
        for x in centers:
            place('TP-E-061',main_len,(x,primary_y),anchor='working_center',role='primary_flower')
            place('TP-E-063',link_len,(x,connector_y),90,'working_center',role='horizontal_connector_accent')
        small_centers=[centers[0]+i*step/2 for i in range(2*count-1)]
        for x in small_centers:
            place('TP-E-066',small_len,(x,small_y),anchor='working_center',role='small_accent')
        # Modern framing gives the three registers a common boundary. Lines
        # sit outside the occupied band and do not fabricate attachment ports.
        frame_gap=max(12,round(gap*0.55))
        frame_top,frame_bottom=round(top-frame_gap),round(top+band_height+frame_gap)
        if frame_top<margin or frame_bottom>h-margin:
            raise APIError(422,'BORDER_TOO_TALL','Три яруса не помещаются с полями; уменьшите масштаб.', {'minimumHeight':math.ceil(band_height+2*(margin+frame_gap))})
        frame_color=ImageColor.getrgb('#355646')+(130,)
        frame=Image.new('RGBA',target.size,0);draw=ImageDraw.Draw(frame)
        for y in (frame_top,frame_bottom):draw.line((margin,y,w-margin,y),fill=frame_color,width=1)
        target=Image.alpha_composite(target,frame)
        additions=[{'kind':'horizontal_border_rules','xRange':[margin,w-margin],'yPositions':[frame_top,frame_bottom],
                    'rgba':list(frame_color),'width':1,'claimType':'contemporary_design','evidence':['D01']}]
        layout={'repeatCount':count,'rows':3,'registers':[
                    {'role':'primary_flower','y':primary_y,'count':count},
                    {'role':'horizontal_connector_accent','y':connector_y,'count':count},
                    {'role':'small_accent','y':small_y,'count':2*count-1}],
                'step':step,'gapRatio':gap_ratio,'minimumPlannedGapPx':gap,'margin':margin,
                'bandHeight':band_height,'centered':True,'direction':'left_to_right_unmirrored',
                'designBasis':'observed_three_register_hierarchy_reinterpreted',
                'historicalReconstruction':False,'continuousJoinedRepeat':False}
    else:
        w,h=module_size
        place('TP-E-092',lengths['TP-E-092'],(w/2,h/2),0,role='large_primary_module',wrap=True)
        place('TP-E-091',lengths['TP-E-091'],(0,h/2),0,role='small_secondary_module',wrap=True)
        place('TP-E-090',lengths['TP-E-090'],(w/2,0),90,'working_center',role='framing_band',wrap=True)
        layout={'moduleSize':list(module_size),'gapRatio':gap_ratio,'continuousJoinedRepeat':False}
    # Pixel-mask diagnostic, not a blanket artistic ban. These layouts choose air.
    overlaps=0
    for i,mask in enumerate(masks):
        for other in masks[:i]:
            overlaps+=ImageChops.multiply(mask,other).histogram()[255]
    if overlaps:
        raise APIError(422,'LAYOUT_CLEARANCE_FAILED','При этом масштабе выбранная схема теряет просветы.', {'overlapPixels':overlaps,'suggestion':'Уменьшите масштаб; элементы не заменены.'})
    solid_bg=ImageColor.getrgb(palette['bg'])
    contrast=[]
    for sprite,info in sprites.values():
        alpha=sprite.getchannel('A'); rgb=sprite.convert('RGB')
        mean=ImageStat.Stat(rgb,alpha.point(lambda v:255 if v>=128 else 0)).mean
        delta=sum(abs(mean[i]-solid_bg[i]) for i in range(3))/3
        contrast.append({'code':info['code'],'meanRgbDistance':round(delta,2),'background':palette['bg'],'empiricalReadability':'unknown'})
    if any(v['meanRgbDistance']<45 for v in contrast):
        warnings.append({'code':'LOW_AVERAGE_CONTRAST','severity':'recommendation','scope':'readability','message':'Некоторые мотивы близки к фону по среднему цвету; проверьте детали при 100% или выберите другой фон.','evidence':['RULE-03','D01']})
    if selections.get('transparentBackground'):
        warnings.append({'code':'TRANSPARENT_CONTRAST_UNKNOWN','severity':'unknown','scope':'readability','message':'Контраст PNG зависит от поверхности размещения; диагностирован только фон JPG.','evidence':['D01']})
    output_kind='composition_image'
    seamless=False
    module_sha=None
    if periodic:
        module_path=png.with_name(png.stem+'.module.png')
        module_path.parent.mkdir(parents=True,exist_ok=True);target.save(module_path)
        module_sha=hashlib.sha256(module_path.read_bytes()).hexdigest()
        output_kind='repeat_module' if selections.get('rapportOutput','module')=='module' else 'pattern_sample'
        if output_kind=='pattern_sample':
            canvas=Image.new('RGBA',requested,bg)
            for y in range(0,requested[1],target.height):
                for x in range(0,requested[0],target.width): canvas.paste(target,(x,y))
            target=canvas
            seamless=requested[0]%module_size[0]==0 and requested[1]%module_size[1]==0
            if not seamless:
                warnings.append({'code':'SAMPLE_NOT_SEAMLESS','severity':'prohibition','scope':'seamless_claim','message':'Размеры образца не кратны модулю; экспорт образца не является бесшовной плиткой.','evidence':['RULE-04']})
        else:
            seamless=True
            if target.size!=requested:
                warnings.append({'code':'MODULE_EXPORT_SIZE','message':'Экспортирован самостоятельный модуль; outputSize задаёт размер только образца.','moduleSize':list(target.size)})
    png.parent.mkdir(parents=True,exist_ok=True);target.save(png)
    solid=Image.new('RGBA',target.size,palette['bg']);solid.alpha_composite(target)
    solid.convert('RGB').save(jpg,quality=95,subsampling=0)
    compat=compatibility(rows,composition)
    recipe={'pillowVersion':PILLOW_VERSION,'rendererSourceSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'schemaVersion':SCHEMA,'algorithmVersion':VERSION,'seed':seed,'pilotId':pilot['id'], 'size':list(target.size),
            'requestedSize':list(requested),'layout':layout,'palette':palette,'roles':pilot['roles'],'placements':placements,
            'selectedElementCodes':selections.get('elementCodes',[]),'selectedMotifKeys':selections.get('motifs',[]),
            'usedElementCodes':sorted({p['code'] for p in placements}),
            'elements':[{'code':r['code'],'sha256':r['content_sha256'],'motif':r['motif_key'],'artifactCode':r['artifact_code'],'sourceFrame':r['frame']} for r in rows],
            'compatibility':compat,'colorMode':'original','transparentBackground':selections.get('transparentBackground',False),'isFixture':False,
            'outputKind':output_kind,'seamless':seamless,'repeat':({'periodPx':list(module_size),'moduleSha256':module_sha,'moduleFileSuffix':'.module.png'} if periodic else None),
            'modernAdditions':additions,'diagnostics':{'overlapPixels':overlaps,'contrast':contrast,'readability':'recommended_floor_applied_empirical_threshold_unknown'},
            'descriptionEvidence':['D01']+['OBS-'+r['code'] for r in rows], 'culturalNote':None}
    if pilot['id']=='P2':
        entries={e['id']:e for e in review()[0]['evidence.json']['entries']}
        ids=['OBS-TP-E-061','OBS-TP-E-063','OBS-TP-E-066','CAT-NM-9585']
        recipe['culturalNote']={'text':'На исходном кадре DSC9585 видны отдельные ярусы крупных цветов, завитковых блоков и малых цветов. Здесь их иерархия использована в современной полосовой композиции; точное расположение костюма не реконструируется.',
                                'claimType':'single_object_visual_observation','evidence':[entries[i] for i in ids],
                                'appliesTo':'source_object_hierarchy_only_not_general_cultural_rule'}
        compat['contextEvidence']=ids
        compat['historicalLayout']='not_verified'
        compat['symbolicMeaning']='unknown'
    if pilot['id']=='P3':
        entries={e['id']:e for e in review()[0]['evidence.json']['entries']}
        recipe['culturalNote']={'text':'В справках о татарских тканых полотенцах описаны широкая основная полоса и меньшие мотивы бордюров. Здесь этот принцип использован в современной композиции; исторический период и символика конкретных ромбов не установлены.',
                                'claimType':'documented_general_principle','evidence':[entries['C03'],entries['C04']], 'appliesTo':'hierarchy_only_not_authenticity'}
    warnings.extend(compat['reasons'])
    if selections['style']!='heritage': warnings.append({'code':'ORIGINAL_COLORS','message':'Сохранены исходные цветовые области; выбранный стиль не перекрашивает пилот.'})
    return recipe,warnings


def replay(rows, recipe, png:Path, jpg:Path):
    """Replay recorded placements, without current templates or role inference."""
    if recipe['algorithmVersion'] not in REPLAY_VERSIONS:
        raise APIError(422,'REPLAY_VERSION_UNAVAILABLE','Нужна сохранённая версия renderer.')
    by_code={r['code']:r for r in rows}
    palette=recipe['palette']
    bg=(0,0,0,0) if recipe['transparentBackground'] else palette['bg']
    period=(recipe.get('repeat') or {}).get('periodPx')
    canvas=Image.new('RGBA',tuple(period or recipe['size']),bg)
    for addition in recipe['modernAdditions']:
        if addition['kind']=='open_circle_guide':
            cx,cy=addition['center'];radius=addition['radius']
            guide=Image.new('RGBA',canvas.size,0)
            ImageDraw.Draw(guide).arc((cx-radius,cy-radius,cx+radius,cy+radius),-230,50,fill=ImageColor.getrgb(palette.get('gold',palette['ink']))+(90,),width=1)
            canvas=Image.alpha_composite(canvas,guide)
    for placement in recipe['placements']:
        row=by_code[placement['code']]
        if hashlib.sha256(Path(row['local_path']).read_bytes()).hexdigest()!=placement['sha256']:
            raise APIError(422,'REPLAY_ASSET_CHANGED','SHA элемента изменился.',{'code':row['code']})
        with Image.open(row['local_path']) as src:
            sprite=src.convert('RGBA').crop(placement['alphaCrop']).resize(placement['resizedSize'],Image.Resampling.LANCZOS)
        delta=placement['clockwiseDegrees']
        if delta: sprite=sprite.rotate(-delta,resample=Image.Resampling.BICUBIC,expand=True)
        x,y=placement['topLeft']
        shifts=[(dx,dy) for dx in (-canvas.width,0,canvas.width) for dy in (-canvas.height,0,canvas.height)] if placement['wrap'] else [(0,0)]
        for dx,dy in shifts: canvas.alpha_composite(sprite,(x+dx,y+dy))
    for addition in recipe['modernAdditions']:
        if addition['kind']=='horizontal_border_rules':
            frame=Image.new('RGBA',canvas.size,0);draw=ImageDraw.Draw(frame)
            x0,x1=addition['xRange']
            for y in addition['yPositions']:draw.line((x0,y,x1,y),fill=tuple(addition['rgba']),width=addition['width'])
            canvas=Image.alpha_composite(canvas,frame)
    png.parent.mkdir(parents=True,exist_ok=True)
    if period:
        canvas.save(png.with_name(png.stem+'.module.png'))
    if recipe['outputKind']=='pattern_sample':
        sample=Image.new('RGBA',tuple(recipe['size']),bg)
        for y in range(0,sample.height,canvas.height):
            for x in range(0,sample.width,canvas.width):sample.paste(canvas,(x,y))
        canvas=sample
    canvas.save(png)
    solid=Image.new('RGBA',canvas.size,palette['bg']);solid.alpha_composite(canvas)
    solid.convert('RGB').save(jpg,quality=95,subsampling=0)
