"""Finite ornament bands and offset repeat fields, from explicit designer profiles."""
import math
from .composition_metadata import metadata
from .errors import APIError


def plan_design(rows,roles,primary,selections,scheme,scene_class):
    design=scheme['design'];density=selections['parameters'];scale=selections.get('scale',1)
    factor={'sparse':1.04,'default':1,'dense':.92}[density]*scale
    gap_rate=design['gapRatio']*{'sparse':1.7,'default':1,'dense':.65}[density]
    def length(row):
        raw=(design['primaryLongSide'] if row['code']==primary else design['supportLongSide'])*factor
        ratio=design.get('longSideRatios',{}).get(row['code'])
        if ratio is not None:raw=design['primaryLongSide']*factor*ratio
        return max(metadata(row)['readability']['recommended_min_long_side_px'],round(raw))
    # Orientation of a complete strip is explicit, without welding its unknown endpoints.
    def axis(row):
        base=metadata(row)['orientation']['angle_deg']
        if base is None:return None
        if row['code'] in design.get('railCodes',[]) or design.get('horizontalSegments') and 'border_segment' in metadata(row)['roles']:return 90
        return base
    lengths={r['code']:length(r) for r in rows}
    ordered=sorted(rows,key=lambda r:(r['code']!=primary,r['code']))
    rails=[r for r in ordered if r['code'] in design.get('railCodes',[])]
    core=[r for r in ordered if r not in rails]
    probe=scene_class(rows,(2048,2048))
    sprites={r['code']:probe.sprite(r['code'],lengths[r['code']],axis(r))[0] for r in rows}
    working={c:probe.sprite(c,lengths[c],axis(next(r for r in rows if r['code']==c)))[1]['workingBoundsSprite'] for c in sprites}
    dims={c:(b[2]-b[0],b[3]-b[1]) for c,b in working.items()}
    gap=max(12,round(max(lengths.values())*gap_rate))
    core_width=sum(dims[r['code']][0] for r in core)+gap*len(core)
    rail_unit=max((dims[r['code']][0]+gap for r in rails),default=0)
    unit=max(core_width,rail_unit,256 if scheme['composition']=='rapport' else 1)
    core_h=max((dims[r['code']][1] for r in core),default=0)
    wave=round(core_h*design['wave'])
    band_h=core_h+2*wave
    rail_h=[dims[r['code']][1] for r in rails]
    periodic=scheme['composition']=='rapport'
    from .generator import SIZES
    requested=tuple(selections.get('outputSize') or SIZES[selections['usage']])
    # Whole rows are distinct bands. Every seam has a complete period and clear spacing.
    heights=([band_h]+rail_h)*2 if core and periodic else rail_h*2 if periodic else ([band_h] if core else [])+rail_h
    native_h=sum(heights)+gap*len(heights)
    minimum=(max(256,unit*design['repeatCycles']),max(256,native_h))
    if periodic:
        size=tuple(selections.get('moduleSize') or minimum)
        if any(size[i]<minimum[i] for i in (0,1)):
            raise APIError(422,'MODULE_TOO_SMALL','Ритм выбранных мотивов требует более крупного модуля.',{'minimumSize':list(minimum),'requestedSize':list(size)})
        if max(size)>2048:
            raise APIError(422,'MODULE_LIMIT','Модуль превышает2048px; уменьшите масштаб или количество мотивов.',{'minimumSize':list(minimum)})
        cycles=design['repeatCycles'];space_w=minimum[0];start_x=0;start_y=(minimum[1]-native_h)/2;space_h=minimum[1]
    else:
        size=requested
        feather=max(max((b[0]+b[2])/2,sprites[c].width-(b[0]+b[2])/2)-dims[c][0]/2 for c,b in working.items())
        margin=max(24,round(min(size)*.05),math.ceil(feather+12));usable=size[0]-2*margin
        cycles=math.floor(usable/unit)
        if cycles<1:
            raise APIError(422,'BORDER_TOO_NARROW','Все выбранные мотивы не помещаются в одном ритме с просветами.',{'minimumWidth':math.ceil(unit+2*margin),'selectedElementCodes':[r['code'] for r in rows]})
        if native_h>size[1]-2*margin:
            raise APIError(422,'BORDER_TOO_TALL','Полоса не помещается с сохранением деталей.',{'minimumHeight':math.ceil(native_h+2*margin),'selectedElementCodes':[r['code'] for r in rows]})
        space_w=cycles*unit;space_h=native_h;start_x=(size[0]-space_w)/2;start_y=(size[1]-space_h)/2
    scene=scene_class(rows,size)
    def stamp(row,x,y):
        if periodic:x=x*size[0]/minimum[0];y=y*size[1]/minimum[1]
        scene.add(row['code'],lengths[row['code']],x,y,roles[row['code']],axis(row),wrap=periodic,anchor='working_center')
    y=start_y+gap/2;row_index=0;bands=[]
    for repeat_row in range(2 if periodic else 1):
        offset=unit/2 if periodic and repeat_row%2 else 0
        if core:
            for cycle in range(cycles):
                x=start_x+cycle*unit+offset+(unit-core_width)/2+gap/2
                for index,row in enumerate(core):
                    sw,sh=dims[row['code']]
                    dy=wave*math.sin(2*math.pi*index/max(2,len(core)))
                    stamp(row,x+sw/2,y+band_h/2+dy);x+=sw+gap
            bands.append({'kind':'motif_cadence','centerY':y+band_h/2,'offsetX':offset,'waveAmplitude':wave})
            y+=band_h+gap;row_index+=1
        for row,rh in zip(rails,rail_h):
            width=dims[row['code']][0]
            count=max(1,math.floor(space_w/(width+gap)))
            step=space_w/count
            for j in range(count):stamp(row,start_x+(j+.5)*step+offset,y+rh/2)
            bands.append({'kind':'discrete_strip','code':row['code'],'centerY':y+rh/2,'count':count,'step':step})
            y+=rh+gap;row_index+=1
    info={'variant':scheme['layout'],'schemeId':scheme['id'],'designProfile':design['mode'],'designVersion':'tp-designs/1.0.0',
          'useScope':scheme['useScope'],'historicalReconstruction':False,'continuousJoinedRepeat':False,
          'bands':bands,'rows':row_index,'cycleCounts':[cycles],'minimumPlannedGapPx':gap,'minimumSize':list(minimum),
          'offsetRepeat':periodic,'preservedSelectedElements':True}
    if periodic:info['moduleSize']=list(size)
    else:info.update(bandHeight=native_h,margin=margin)
    return scene,info
