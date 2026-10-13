"""Real SDXL render subprocess. Requires approved weights and CUDA; no fallback."""
from pathlib import Path
import json, sys, time, hashlib
import torch
import numpy as np
from PIL import Image
from diffusers import StableDiffusionXLPipeline, StableDiffusionXLControlNetPipeline, ControlNetModel, EulerDiscreteScheduler

request_path, result_path, config_path = map(Path,sys.argv[1:4])
r=json.loads(request_path.read_text());c=json.loads(config_path.read_text())
assert r['workflowVersion']==c['workflow_version'] and r['modelVersion']==c['adapter_sha256'], 'immutable deployment mismatch'
adapter=Path(c['adapter_path'])
assert hashlib.sha256(adapter.read_bytes()).hexdigest()==c['adapter_sha256']
assert torch.cuda.is_available()
kwargs=dict(revision=c['base_revision'],variant='fp16',torch_dtype=torch.float16,use_safetensors=True)
start=time.perf_counter()
if r['scenario']=='central_controlled':
    import cv2
    control=ControlNetModel.from_pretrained(c['control_repo'],revision=c['control_revision'],torch_dtype=torch.float16,use_safetensors=True)
    pipe=StableDiffusionXLControlNetPipeline.from_pretrained(c['base_repo'],controlnet=control,**kwargs)
else:pipe=StableDiffusionXLPipeline.from_pretrained(c['base_repo'],**kwargs)
pipe.scheduler=EulerDiscreteScheduler.from_config(pipe.scheduler.config);pipe.to('cuda')
pipe.load_lora_weights(str(adapter.parent),weight_name=adapter.name)
torch.cuda.reset_peak_memory_stats()
inputs=dict(prompt=r['prompt'],negative_prompt='text, watermark, photographic scene, objects in the background, cropped motif',num_inference_steps=30,guidance_scale=5.0,width=1024,height=1024,generator=torch.Generator('cuda').manual_seed(r['seed']),cross_attention_kwargs={'scale':r['loraScale']})
if r['scenario']=='central_controlled':
    template=Path(c['templates'][r['templateId']])
    edge=cv2.Canny(np.asarray(Image.open(template).convert('L')),100,200)
    inputs.update(image=Image.fromarray(np.repeat(edge[:,:,None],3,axis=2)),controlnet_conditioning_scale=0.5)
im=pipe(**inputs).images[0].convert('RGB');torch.cuda.synchronize();im.save(result_path)
result_path.with_suffix('.metrics.json').write_text(json.dumps({'elapsedSeconds':time.perf_counter()-start,'peakVramBytes':torch.cuda.max_memory_allocated(),'includes_cold_model_load':True}))
