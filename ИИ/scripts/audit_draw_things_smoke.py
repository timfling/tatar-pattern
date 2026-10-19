"""Read-only audit of a safetensors export and Draw Things PNG pairs. No torch/load/pickle/network."""
from pathlib import Path
import argparse,collections,hashlib,json,math,struct,xml.etree.ElementTree as ET
import numpy as np
from PIL import Image,ImageDraw
AI=Path(__file__).resolve().parents[1]
DT=AI/'draw-things'
OUT=DT/'smoke-audit'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def metadata(im):
    root=ET.fromstring(im.info['xmp'])
    return json.loads(''.join(root.find('.//{http://ns.adobe.com/exif/1.0/}UserComment').itertext()).strip())
def main():
    global OUT
    ap=argparse.ArgumentParser()
    ap.add_argument('--adapter',type=Path,default=DT/'safetensor/smoke test/tp_fiber_dt_smoke_r8_v1_50_lora_f32.safetensors')
    ap.add_argument('--output',type=Path,default=OUT)
    ap.add_argument('--tensor-only',action='store_true')
    args=ap.parse_args(); OUT=args.output; OUT.mkdir(parents=True,exist_ok=True)
    p=args.adapter.resolve()
    with p.open('rb') as f:
        n=struct.unpack('<Q',f.read(8))[0]
        assert n<=p.stat().st_size-8
        header=json.loads(f.read(n)); data=f.read()
    stats=[]; arrays={}; intervals=[]
    for k,v in header.items():
        if k=='__metadata__':continue
        assert v['dtype']=='F32',(k,v['dtype'])
        start,end=v['data_offsets']; shape=v['shape']
        assert 0<=start<=end<=len(data) and end-start==4*math.prod(shape),k
        intervals.append((start,end))
        a=np.frombuffer(data,dtype='<f4',offset=start,count=(end-start)//4).reshape(shape)
        arrays[k]=a
        stats.append(dict(name=k,shape=shape,dtype=v['dtype'],elements=a.size,nonzero=int(np.count_nonzero(a)),finite=bool(np.isfinite(a).all()),max_abs=float(np.max(np.abs(a))),rms=float(np.sqrt(np.mean(a.astype(np.float64)**2)))))
    intervals.sort();assert intervals[0][0]==0 and intervals[-1][1]==len(data)
    assert all(a[1]==b[0] for a,b in zip(intervals,intervals[1:]))
    summaries={}
    for suffix in ['lora_up.weight','lora_down.weight','.alpha']:
        subset=[r for r in stats if r['name'].endswith(suffix)]
        summaries[suffix]={'count':len(subset),'all_zero_count':sum(r['nonzero']==0 for r in subset),'nonfinite_count':sum(not r['finite'] for r in subset)}
    # Compute at least one effective B@A update, not merely nonzero individual factors.
    first=next(k for k,a in arrays.items() if k.endswith('lora_up.weight') and np.any(a))
    base=first.removesuffix('lora_up.weight')
    u=arrays[first];d=arrays[base+'lora_down.weight'];alpha=float(arrays[base+'alpha'])
    delta=(u.reshape(u.shape[0],-1).astype(np.float64)@d.reshape(d.shape[0],-1).astype(np.float64))*(alpha/d.shape[0])
    zero=[r['name'] for r in stats if r['name'].endswith('lora_up.weight') and r['nonzero']==0]
    rank_counts=collections.Counter(str(a.shape[1]) for k,a in arrays.items() if k.endswith('lora_up.weight'))
    alpha_counts=collections.Counter(str(float(a)) for k,a in arrays.items() if k.endswith('.alpha'))
    report={'adapter':str(p.relative_to(AI)) if p.is_relative_to(AI) else str(p),'bytes':p.stat().st_size,'sha256':sha(p),'metadata':header.get('__metadata__'),'tensor_count':len(stats),'offsets_shapes_dtypes_valid':True,'tensor_groups':summaries,'rank_counts':dict(rank_counts),'alpha_counts':dict(alpha_counts),'all_zero_up_issue_reproduced':summaries['lora_up.weight']['all_zero_count']==summaries['lora_up.weight']['count'],'zero_up_names':zero,'zero_up_all_cross_attention_kv':all('_attn2_to_k.' in k or '_attn2_to_v.' in k for k in zero),'effective_update_example':{'up_key':first,'alpha':alpha,'rank':d.shape[0],'max_abs_delta':float(np.max(np.abs(delta))),'nonzero':int(np.count_nonzero(delta))},'tensor_stats':stats,'cloud_load_status':'NOT_RUN'}
    (OUT/'tensor-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    if args.tensor_only:
        print(json.dumps({k:v for k,v in report.items() if k not in ['tensor_stats','zero_up_names']},indent=2))
        return
    tasks=['flower','branch','spirals','diamond','rosette','composition']; pairs=[]
    sheet=Image.new('RGB',(1000,len(tasks)*375+45),'#eeeeee');draw=ImageDraw.Draw(sheet)
    draw.text((10,10),'SMOKE 50 steps | left: baseline WITHOUT tptrx | right: LoRA 0.8 WITH tptrx',fill='black')
    for i,task in enumerate(tasks):
        paths=[next((DT/'results/SDXL no lora').glob(task+'_*.png'),None),next((DT/'results/tp_fiber_dt_smoke_r8_v1').glob(task+'_*.png'),None)]
        entry={'task':task}; meta=[];imgs=[]
        for col,path in enumerate(paths):
            x=col*500;y=45+i*375
            if path is None:
                draw.text((x+20,y+30),task+' MISSING',fill='red'); meta.append(None);imgs.append(None);continue
            with Image.open(path) as im:
                m=metadata(im);rgb=im.convert('RGB');imgs.append(np.array(rgb));meta.append(m)
                entry[['baseline','lora'][col]]={'path':str(path.relative_to(AI)),'sha256':sha(path),'pixel_sha256':hashlib.sha256(rgb.tobytes()).hexdigest(),'metadata':m}
                thumb=rgb.resize((340,340));sheet.paste(thumb,(x+80,y+25));draw.text((x+10,y+5),task,fill='black')
        if all(m is not None for m in meta):
            a,b=imgs
            entry['pixel_comparison']={'identical':bool(np.array_equal(a,b)),'mean_abs_channel_difference_0_255':float(np.abs(a.astype(float)-b).mean()),'changed_pixel_fraction':float(np.any(a!=b,axis=2).mean())}
            entry['prompt_equal']=meta[0]['c']==meta[1]['c']
            entry['v2_differences']={k:[meta[0]['v2'].get(k),meta[1]['v2'].get(k)] for k in set(meta[0]['v2'])|set(meta[1]['v2']) if meta[0]['v2'].get(k)!=meta[1]['v2'].get(k)}
        pairs.append(entry)
    (OUT/'generation-audit.json').write_text(json.dumps({'pairs':pairs,'limitation':'Prompts differ: baseline omits tptrx. Not a controlled adapter-only comparison.'},ensure_ascii=False,indent=2)+'\n')
    sheet.save(OUT/'smoke-comparison.jpg',quality=92)
    print(json.dumps({k:v for k,v in report.items() if k not in ['tensor_stats','zero_up_names']},indent=2))
    print('PAIRS',[(r['task'],r.get('pixel_comparison'),r.get('v2_differences')) for r in pairs])
if __name__=='__main__':main()
