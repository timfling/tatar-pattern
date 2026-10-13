"""Real CUDA evaluation, one variant per call; no synthetic outputs or uploads."""
import math, os
import argparse, csv, hashlib, json, time
from pathlib import Path

AI=Path(__file__).resolve().parents[1]
BASE='stabilityai/stable-diffusion-xl-base-1.0'
REV='462165984030d82259a11f4367a4eed129e94a7b'
NEG='text, watermark, photographic scene, objects in the background, cropped motif'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--adapter',type=Path);ap.add_argument('--scale',type=float,default=0.0);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--control',action='store_true');a=ap.parse_args()
    assert (a.adapter is not None)==(a.scale>0), 'baseline: no adapter, scale0; LoRA: adapter and positive scale'
    assert a.scale in [0.0,0.5,0.6,0.8]
    rate=float(os.environ['TP_GPU_HOURLY_RUB']) if os.environ.get('TP_GPU_HOURLY_RUB') else None
    assert rate is None or (math.isfinite(rate) and rate>0), 'hourly rate must be positive and finite'
    plan=json.loads((AI/'pilot/evaluation_plan.json').read_text())
    import torch
    import numpy as np
    import cv2
    from PIL import Image
    from diffusers import StableDiffusionXLPipeline, StableDiffusionXLControlNetPipeline, ControlNetModel, EulerDiscreteScheduler
    assert torch.cuda.is_available()
    kwargs=dict(revision=REV,variant='fp16',torch_dtype=torch.float16,use_safetensors=True)
    conditioning=None
    if a.control:
        control=ControlNetModel.from_pretrained('diffusers/controlnet-canny-sdxl-1.0',revision='eb115a19a10d14909256db740ed109532ab1483c',torch_dtype=torch.float16,use_safetensors=True)
        pipe=StableDiffusionXLControlNetPipeline.from_pretrained(BASE,controlnet=control,**kwargs)
        # Canny on true alpha silhouette, not texture edges. It excludes training images.
        silhouette=Image.open(AI/'dataset/texture-v1/structure_alpha.png').convert('L')
        edge=cv2.Canny(np.asarray(silhouette),100,200)
        conditioning=Image.fromarray(np.repeat(edge[:,:,None],3,axis=2))
        tasks=[plan['controlled_task']];seeds=plan['control_seeds']
    else:
        pipe=StableDiffusionXLPipeline.from_pretrained(BASE,**kwargs);tasks=plan['tasks'];seeds=plan['seeds']
    pipe.scheduler=EulerDiscreteScheduler.from_config(pipe.scheduler.config)
    pipe.to('cuda')
    if a.adapter:pipe.load_lora_weights(str(a.adapter.parent),weight_name=a.adapter.name)
    a.output.mkdir(parents=True,exist_ok=False)
    if conditioning:conditioning.save(a.output/'conditioning.png')
    rows=[]
    for task in tasks:
        for seed in seeds:
            torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();start=time.perf_counter()
            inputs=dict(prompt=task['prompt'],negative_prompt=NEG,num_inference_steps=30,guidance_scale=5.0,width=1024,height=1024,generator=torch.Generator('cuda').manual_seed(seed))
            if a.adapter:inputs['cross_attention_kwargs']={'scale':a.scale}
            if a.control:inputs.update(image=conditioning,controlnet_conditioning_scale=0.5)
            im=pipe(**inputs).images[0];torch.cuda.synchronize();elapsed=time.perf_counter()-start
            p=a.output/f"{task['id']}-{seed}.png";im.save(p)
            rows.append(dict(task_id=task['id'],prompt=task['prompt'],seed=seed,adapter_sha256=sha(a.adapter) if a.adapter else None,lora_scale=a.scale,base_revision=REV,control=a.control,elapsed_seconds=elapsed,peak_vram_bytes=torch.cuda.max_memory_allocated(),png_sha256=sha(p),active_generation_cost_estimate_rub=elapsed*rate/3600 if rate is not None else None))
            (a.output/'measurements.json').write_text(json.dumps(rows,indent=2))
    (a.output/'workflow.json').write_text(json.dumps(dict(base=BASE,revision=REV,scheduler='EulerDiscreteScheduler',steps=30,cfg=5.0,negative_prompt=NEG,width=1024,height=1024,adapter_sha256=sha(a.adapter) if a.adapter else None,plan_sha256=sha(AI/'pilot/evaluation_plan.json')),indent=2))
    print('Real generated images:',len(rows),'Rental setup/idle costs must be added separately.')

if __name__=='__main__':main()
