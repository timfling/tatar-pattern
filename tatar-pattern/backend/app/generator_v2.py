"""Role-driven finite layouts. No master alteration, cultural inference or hidden subset."""
import hashlib
import math
import random
from pathlib import Path
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageStat, __version__ as PILLOW_VERSION
from .composition import transformed
from .composition_metadata import metadata,review
from .generator import SIZES
from .scheme_catalog import resolve,registry
from .errors import APIError

VERSION='composition-pillow/2.1.0'
SCHEMA='tp-composition-recipe/2.0.0'

class Scene:
    def __init__(self,rows,size):
        self.rows={r['code']:r for r in rows};self.size=tuple(size);self.placements=[];self.sprites={};self.additions=[]
    def sprite(self,code,length,axis=None):
        key=(code,round(length),axis)
        if key not in self.sprites:self.sprites[key]=transformed(self.rows[code],length,axis)
        return self.sprites[key]
    def add(self,code,length,x,y,role,axis=None,wrap=False,anchor='working_center'):
        sprite,original=self.sprite(code,length,axis);info={**original}
        if anchor=='sprite_center':point=[sprite.width/2,sprite.height/2]
        elif anchor=='attachment':point=info['attachmentSprite']
        elif anchor=='visual_center':point=info['visualCenterSprite']
        else:
            b=info['workingBoundsSprite'];point=[(b[0]+b[2])/2,(b[1]+b[3])/2]
        if point is None:raise APIError(422,'ATTACHMENT_UNKNOWN','Основание неизвестно; соединение не выдумано.',{'code':code})
        left,top=round(x-point[0]),round(y-point[1]);bounds=[left,top,left+sprite.width,top+sprite.height]
        if not wrap and (left<12 or top<12 or bounds[2]>self.size[0]-12 or bounds[3]>self.size[1]-12):
            raise APIError(422,'COMPOSITION_TOO_LARGE','Размер мотива и поля не помещаются в формат.',{'code':code,'bounds':bounds,'size':list(self.size),'suggestion':'Уменьшите масштаб или выберите больший формат.'})
        matrix=[info['cropToSpriteMatrix'][0][:],info['cropToSpriteMatrix'][1][:],[0,0,1]];matrix[0][2]+=left;matrix[1][2]+=top
        info.update(role=role,anchor=anchor,anchorPosition=[x,y],topLeft=[left,top],bounds=bounds,wrap=wrap,cropToOutputMatrix=matrix,
                    attachmentOutput=([left+info['attachmentSprite'][0],top+info['attachmentSprite'][1]] if info['attachmentSprite'] else None))
        self.placements.append(info)
    def pixels(self,bg,diagnose=True):
        canvas=Image.new('RGBA',self.size,bg)
        # Modern guides are always independently recorded, before motif stamps.
        for a in self.additions:
            layer=Image.new('RGBA',self.size,0);draw=ImageDraw.Draw(layer)
            if a['kind']=='circle_guide':draw.ellipse(a['bounds'],outline=tuple(a['rgba']),width=a['width'])
            elif a['kind']=='horizontal_border_rules':
                for y in a['yPositions']:draw.line((a['xRange'][0],y,a['xRange'][1],y),fill=tuple(a['rgba']),width=a['width'])
            canvas=Image.alpha_composite(canvas,layer)
        occupancy=Image.new('L',self.size,0);overlap=0
        for p in self.placements:
            key=(p['code'],p['longSideBeforeRotation'],p['targetAxis']);sprite,_=self.sprites[key]
            x,y=p['topLeft'];shifts=[(dx,dy) for dx in (-self.size[0],0,self.size[0]) for dy in (-self.size[1],0,self.size[1])] if p['wrap'] else [(0,0)]
            mask=Image.new('L',self.size,0)
            for dx,dy in shifts:
                canvas.alpha_composite(sprite,(x+dx,y+dy))
                if diagnose:mask.paste(sprite.getchannel('A').point(lambda v:255 if v>=16 else 0),(x+dx,y+dy))
            if diagnose:
                overlap+=ImageChops.multiply(occupancy,mask).histogram()[255];occupancy=ImageChops.lighter(occupancy,mask)
        return canvas,overlap


def _axis(row,role,hanging=False):
    item=metadata(row);base=item['orientation']['angle_deg']
    if base is None:return None
    if hanging:return 180
    if role=='frame' and 'border_segment' in item['roles']:return 90
    return base # Preserve current directed/asymmetric presentation by default.


def plan(rows,selections,seed=0):
    scheme,roles,primary,reasons=resolve(rows,selections)
    if selections.get('colorMode','original')!='original':
        raise APIError(422,'SCHEME_REQUIRES_ORIGINAL','Согласованные схемы сохраняют внутренние цветовые поля; выберите original.')
    density=selections['parameters'];scale=selections.get('scale',1)
    gap_ratio={'sparse':0.35,'default':0.26,'dense':0.18}[density]
    factor={'sparse':1.04,'default':1.0,'dense':0.92}[density]*scale
    size=tuple(selections.get('outputSize') or SIZES[selections['usage']])
    layout=scheme['layout'];ordered=sorted(rows,key=lambda r:(r['code']!=primary,r['code']))
    lengths={r['code']:max(metadata(r)['readability']['recommended_min_long_side_px'],round((200 if r['code']==primary else 256 if roles[r['code']]=='frame' else 160)*factor)) for r in rows}
    scene=Scene(rows,size);info={'variant':layout,'schemeId':scheme['id'],'useScope':scheme['useScope'],'gapRatio':gap_ratio,'historicalReconstruction':False,'continuousJoinedRepeat':False}
    periodic=layout=='hierarchical_repeat'
    if scheme.get('design'):
        from .scheme_design import plan_design
        scene,info=plan_design(rows,roles,primary,selections,scheme,Scene)
    elif periodic:
        grid=max(1,math.ceil(math.sqrt(len(rows))));groups=[ordered[i:i+grid] for i in range(0,len(rows),grid)]
        dims={r['code']:scene.sprite(r['code'],lengths[r['code']],_axis(r,roles[r['code']]))[0].size for r in rows}
        gap=math.ceil(max(lengths.values())*gap_ratio)
        widths=[max([dims[g[i]['code']][0] for g in groups if i<len(g)])+2*gap for i in range(grid)]
        heights=[max(dims[r['code']][1] for r in g)+2*gap for g in groups]
        minimum=[max(256,sum(widths)),max(256,sum(heights))]
        module=tuple(selections.get('moduleSize') or minimum)
        if any(module[i]<minimum[i] for i in (0,1)):
            raise APIError(422,'MODULE_TOO_SMALL','Выбранные мотивы не помещаются в модуле с рекомендованной детализацией.',{'minimumSize':minimum,'requestedSize':list(module)})
        if max(module)>2048:raise APIError(422,'MODULE_LIMIT','Для такого масштаба нужен модуль больше2048px; уменьшите масштаб/набор.',{'minimumSize':minimum})
        scene=Scene(rows,module)
        y=0
        for j,g in enumerate(groups):
            x=0
            for i,row in enumerate(g):
                cx=(x+widths[i]/2)*module[0]/sum(widths);cy=(y+heights[j]/2)*module[1]/sum(heights)
                scene.add(row['code'],lengths[row['code']],cx,cy,roles[row['code']],_axis(row,roles[row['code']]),True)
                x+=widths[i]
            y+=heights[j]
        info.update(moduleSize=list(module),grid=[grid,len(groups)],minimumPlannedGapPx=gap)
    elif layout in ('directed_cadence','hanging_panel'):
        w,h=size;margin=max(32,round(min(size)*0.06));usable=w-2*margin
        hanging=layout=='hanging_panel';gap=math.ceil(max(lengths.values())*gap_ratio)
        sprites={r['code']:scene.sprite(r['code'],lengths[r['code']],_axis(r,roles[r['code']],hanging))[0] for r in rows}
        # Pack finite discrete fragments; no endpoint welding or hidden clipping.
        capacity=usable if hanging else (usable-gap)/2
        lanes=[];lane=[];width=0
        for row in ordered:
            sw=sprites[row['code']].width
            if sw>capacity:raise APIError(422,'BORDER_TOO_NARROW','Дискретный мотив не помещается с повтором и полями.',{'code':row['code'],'minimumWidth':math.ceil((sw+gap)*(1 if hanging else 2)+2*margin)})
            extra=sw+(gap if lane else 0)
            if lane and width+extra>capacity:lanes.append(lane);lane=[];width=0;extra=sw
            lane.append(row);width+=extra
        if lane:lanes.append(lane)
        lane_heights=[max(sprites[r['code']].height for r in g) for g in lanes]
        block=sum(lane_heights)+gap*(len(lanes)-1)
        if block>h-2*margin:raise APIError(422,'BORDER_TOO_TALL','Набор не помещается по высоте без потери деталей.',{'minimumHeight':math.ceil(block+2*margin),'suggestion':'Уменьшите масштаб или выберите более высокий формат.'})
        y=(h-block)/2;cycles=[]
        for group,lh in zip(lanes,lane_heights):
            width=sum(sprites[r['code']].width for r in group)+gap*(len(group)-1)
            count=max(1 if hanging else 2, min(6,math.floor((usable+gap)/(width+gap))))
            actual=count*width+(count-1)*gap;x=(w-actual)/2
            for _ in range(count):
                for row in group:
                    sw,sh=sprites[row['code']].size
                    # Center the entire sprite, preserve all alpha>0 feathers.
                    scene.add(row['code'],lengths[row['code']],x+sw/2,y+lh/2,roles[row['code']],_axis(row,roles[row['code']],hanging),anchor='sprite_center')
                    x+=sw+gap
            cycles.append(count);y+=lh+gap
        frame_top=max(16,round((h-block)/2-gap/2));frame_bottom=min(h-16,round((h+block)/2+gap/2))
        scene.additions=[{'kind':'horizontal_border_rules','xRange':[margin,w-margin],'yPositions':[frame_top,frame_bottom],'rgba':[53,86,70,95],'width':1,'claimType':'contemporary_design','evidence':['D01']}]
        info.update(rows=len(lanes),cycleCounts=cycles,minimumPlannedGapPx=gap,margin=margin,bandHeight=block,direction='down_preserved' if hanging else 'source_directions_preserved')
    elif layout in ('center_wreath','framed_panel'):
        unit=min(size);cx,cy=size[0]/2,size[1]/2
        lengths[primary]=max(metadata(scene.rows[primary])['readability']['recommended_min_long_side_px'],round(unit*0.22*factor))
        others=[r for r in ordered if r['code']!=primary]
        frames=[r for r in others if 'framing_pair' in metadata(r)['roles']] if layout=='center_wreath' else []
        accents=[r for r in others if r not in frames]
        if not accents:accents=[scene.rows[primary]]
        target_count=max(len(accents),{'sparse':6,'default':8,'dense':10}[density]) if layout=='center_wreath' else max(len(accents),4)
        errors=[];winner=None
        # Bounded geometry search: changes count/radius, never selected assets.
        for count in dict.fromkeys([target_count,max(len(accents),6),len(accents)]):
            for radius_ratio in (0.30,0.34,0.37):
                candidate=Scene(rows,size);radius=unit*radius_ratio
                try:
                    candidate.add(primary,lengths[primary],cx,cy,'center' if layout=='center_wreath' else 'primary',_axis(scene.rows[primary],roles[primary]))
                    phase=random.Random(seed).choice([-2,0,2])
                    for j in range(count):
                        row=accents[j%len(accents)]
                        frame_span=min(160,60*len(frames))
                        accent_limit=180-frame_span/2-15
                        angle=(-accent_limit+j*2*accent_limit/max(1,count-1)) if frames else j*360/count+phase
                        length=max(metadata(row)['readability']['recommended_min_long_side_px'],round(lengths[primary]*0.60))
                        base=metadata(row)['orientation']['angle_deg']
                        # Only axial/leaf motifs get a new radial direction. Unknown stays PNG.
                        axis=angle if base is not None and set(metadata(row)['roles']).intersection({'axial_apex','supporting_leaf','primary_flower'}) else _axis(row,roles[row['code']])
                        candidate.add(row['code'],length,cx+radius*math.sin(math.radians(angle)),cy-radius*math.cos(math.radians(angle)),roles.get(row['code'],'support'),axis)
                    for j,row in enumerate(frames):
                        span=min(160,60*len(frames))
                        angle=180-span/2+(j+0.5)*span/len(frames)
                        candidate.add(row['code'],max(lengths[row['code']],lengths[primary]*0.70),cx+radius*math.sin(math.radians(angle)),cy-radius*math.cos(math.radians(angle)),'frame',_axis(row,'frame'))
                    candidate.additions=[{'kind':'circle_guide','bounds':[cx-radius,cy-radius,cx+radius,cy+radius],'rgba':[53,86,70,65],'width':1,'claimType':'contemporary_design','evidence':['D01']}]
                    _,overlap=candidate.pixels((0,0,0,0))
                    if overlap:continue
                    winner=(candidate,count,radius);break
                except APIError as exc:errors.append(exc.payload['error'])
            if winner:break
        if not winner:raise APIError(422,'LAYOUT_CLEARANCE_FAILED','Набор не помещается в обрамление с заданными деталями и масштабом.',{'diagnostics':errors[:3],'selectedElementCodes':[r['code'] for r in rows],'suggestion':'Уменьшите масштаб или выберите другой формат/схему.'})
        scene,count,radius=winner;info.update(rays=count,radius=radius,centerLongSide=lengths[primary],candidatesBound=9)
        if count!=target_count:reasons.append({'code':'DENSITY_FIT','severity':'recommendation','scope':'geometry','message':'Число акцентов согласовано с габаритами; выбранные элементы сохранены.','requestedRays':target_count,'effectiveRays':count,'evidence':['D01']})
    else:raise RuntimeError('Unsupported registry layout')
    _,overlap=scene.pixels((0,0,0,0))
    if overlap:raise APIError(422,'LAYOUT_CLEARANCE_FAILED','Геометрия этой схемы теряет просветы; элементы не удалены.',{'overlapPixels':overlap,'selectedElementCodes':[r['code'] for r in rows]})
    return scene,scheme,roles,primary,reasons,info


def preflight(rows,selections,seed=0):
    scene,scheme,roles,primary,reasons,layout=plan(rows,selections,seed)
    return {'schemaVersion':'tp-preflight/2.0.0','supported':True,'engineVersion':VERSION,'registryVersion':registry()['registryVersion'],'registrySha256':registry()['sha256'],
            'schemeId':scheme['id'],'selectedElementCodes':[r['code'] for r in rows],'usedElementCodes':sorted({p['code'] for p in scene.placements}),
            'assignments':[{'code':r['code'],'role':roles[r['code']],'recommendedMinLongSidePx':metadata(r)['readability']['recommended_min_long_side_px']} for r in rows],
            'primaryElementCode':primary,'layout':layout,'size':list(scene.size),'reasons':reasons,'factsBasis':'deterministic_geometry_plan_not_visual_or_cultural_verification'}


def render(rows,selections,palette,png,jpg,seed=0):
    scene,scheme,roles,primary,reasons,layout=plan(rows,selections,seed)
    palette={**palette,'bg':selections.get('backgroundColor') or palette['bg']};bg=(0,0,0,0) if selections.get('transparentBackground') else palette['bg']
    canvas,overlap=scene.pixels(bg);module_sha=None
    png.parent.mkdir(parents=True,exist_ok=True)
    periodic=scheme['layout']=='hierarchical_repeat';seamless=False;kind='composition_image'
    repeat=None
    if periodic:
        module=png.with_name(png.stem+'.module.png');canvas.save(module);module_sha=hashlib.sha256(module.read_bytes()).hexdigest()
        repeat={'periodPx':list(scene.size),'moduleSha256':module_sha,'moduleFileSuffix':'.module.png'}
        kind='repeat_module';seamless=True
        if selections.get('rapportOutput')=='sample':
            requested=tuple(selections.get('outputSize') or SIZES[selections['usage']]);sample=Image.new('RGBA',requested,bg)
            for y in range(0,requested[1],canvas.height):
                for x in range(0,requested[0],canvas.width):sample.paste(canvas,(x,y))
            seamless=requested[0]%canvas.width==requested[1]%canvas.height==0;canvas=sample;kind='pattern_sample'
            if not seamless:reasons.append({'code':'SAMPLE_NOT_SEAMLESS','severity':'prohibition','scope':'seamless_claim','evidence':['RULE-04'],'message':'Размеры образца не кратны модулю; экспортируйте модуль для повтора.'})
    canvas.save(png);solid=Image.new('RGBA',canvas.size,palette['bg']);solid.alpha_composite(canvas);solid.convert('RGB').save(jpg,quality=95,subsampling=0)
    contrast=[];background=ImageColor.getrgb(palette['bg'])
    for (sprite,info) in scene.sprites.values():
        mask=sprite.getchannel('A').point(lambda v:255 if v>=128 else 0);mean=ImageStat.Stat(sprite.convert('RGB'),mask).mean
        contrast.append({'code':info['code'],'meanRgbDistance':round(sum(abs(mean[i]-background[i]) for i in range(3))/3,2),'empiricalReadability':'unknown'})
    if any(c['meanRgbDistance']<45 for c in contrast):reasons.append({'code':'LOW_AVERAGE_CONTRAST','severity':'recommendation','scope':'readability','evidence':['RULE-03'],'message':'Некоторые детали близки к фону; проверьте изображение при100% или смените фон.'})
    if selections.get('transparentBackground'):reasons.append({'code':'TRANSPARENT_CONTRAST_UNKNOWN','severity':'unknown','scope':'readability','evidence':['D01'],'message':'Контраст прозрачного PNG зависит от поверхности размещения.'})
    if selections['style']!='heritage':reasons.append({'code':'ORIGINAL_COLORS','message':'Схема сохраняет исходные внутренние цвета.'})
    evidence={e['id']:e for e in review()[0]['evidence.json']['entries']}
    source_ids=sorted({metadata(r)['cultural_attribution']['evidence'] for r in rows})
    note={'text':'Схема использует мотивы из каталогизированных источников выбранного семейства. Расстановка современная; точная историческая композиция и символика не установлены.',
          'claimType':'catalogue_context','appliesTo':'selected_source_objects_only_not_layout_authenticity','evidence':[evidence[e] for e in source_ids]}
    recipe={'designSourceSha256':hashlib.sha256(Path(__file__).with_name('scheme_design.py').read_bytes()).hexdigest(),'schemaVersion':SCHEMA,'algorithmVersion':VERSION,'registryVersion':registry()['registryVersion'],'registrySha256':registry()['sha256'],'schemeId':scheme['id'],
            'schemeDefinition':scheme,'familyId':scheme['familyId'],'seed':seed,'roles':roles,'primaryElementCode':primary,'layout':layout,'size':list(canvas.size),
            'requestedSize':list(selections.get('outputSize') or SIZES[selections['usage']]),'palette':palette,'placements':scene.placements,'modernAdditions':scene.additions,
            'colorMode':'original','transparentBackground':selections.get('transparentBackground',False),'selectedElementCodes':selections.get('elementCodes',[]),
            'selectedMotifKeys':selections.get('motifs',[]),'usedElementCodes':sorted({p['code'] for p in scene.placements}),
            'elements':[{'code':r['code'],'sha256':r['content_sha256'],'motif':r['motif_key'],'artifactCode':r['artifact_code'],'sourceFrame':r['frame']} for r in rows],
            'compatibility':{'status':'supported_scheme','geometry':'checked_for_saved_layout','aesthetic':'designer_proposal','cultural':'unknown','reasons':reasons,'metadataVersion':registry()['metadataVersion'],'snapshotSha256':review()[1]},
            'descriptionEvidence':['D01']+['OBS-'+r['code'] for r in rows],'culturalNote':note,'diagnostics':{'overlapPixels':overlap,'contrast':contrast,'empiricalReadability':'unknown'},
            'outputKind':kind,'seamless':seamless,'repeat':repeat,'isFixture':False,'pillowVersion':PILLOW_VERSION,'rendererSourceSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    return recipe,reasons


def replay(rows,recipe,png,jpg):
    if recipe['algorithmVersion'] not in (VERSION,'composition-pillow/2.0.0'):raise APIError(422,'REPLAY_VERSION_UNAVAILABLE','Требуется сохранённая версия renderer.')
    period=(recipe.get('repeat') or {}).get('periodPx');scene=Scene(rows,period or recipe['size'])
    for p in recipe['placements']:
        row=scene.rows[p['code']]
        if hashlib.sha256(Path(row['local_path']).read_bytes()).hexdigest()!=p['sha256']:raise APIError(422,'REPLAY_ASSET_CHANGED','SHA элемента изменился.',{'code':p['code']})
        with Image.open(row['local_path']) as src:im=src.convert('RGBA').crop(p['alphaCrop']).resize(p['resizedSize'],Image.Resampling.LANCZOS)
        if p['clockwiseDegrees']:im=im.rotate(-p['clockwiseDegrees'],resample=Image.Resampling.BICUBIC,expand=True)
        scene.sprites[(p['code'],p['longSideBeforeRotation'],p['targetAxis'])]=(im,p)
    scene.placements=recipe['placements'];scene.additions=recipe['modernAdditions'];bg=(0,0,0,0) if recipe['transparentBackground'] else recipe['palette']['bg']
    canvas,_=scene.pixels(bg,False);png.parent.mkdir(parents=True,exist_ok=True)
    if period:canvas.save(png.with_name(png.stem+'.module.png'))
    if recipe['outputKind']=='pattern_sample':
        sample=Image.new('RGBA',recipe['size'],bg)
        for y in range(0,sample.height,canvas.height):
            for x in range(0,sample.width,canvas.width):sample.paste(canvas,(x,y))
        canvas=sample
    canvas.save(png);solid=Image.new('RGBA',canvas.size,recipe['palette']['bg']);solid.alpha_composite(canvas);solid.convert('RGB').save(jpg,quality=95,subsampling=0)
