"""Owner-deployed SDXL img2img subprocess; offline pinned assets, no synthetic fallback."""
from pathlib import Path
import importlib.metadata
import json
import sys
import time

from workflow import VERSIONS, deployment, inside, registry, resolved, sha


def main():
    request_path, result_path, config_path = map(Path, sys.argv[1:4])
    request = json.loads(request_path.read_text())
    config = json.loads(config_path.read_text())
    identity = deployment(config)
    metadata = resolved(request, config)
    for name, version in VERSIONS.items():
        if importlib.metadata.version(name).split('+')[0] != version:
            raise ValueError('Runtime version mismatch: ' + name)
    import torch
    from PIL import Image, PngImagePlugin
    from safetensors.torch import load_file
    from diffusers import StableDiffusionXLImg2ImgPipeline, EulerAncestralDiscreteScheduler

    if sys.version_info[:2] not in ((3, 11), (3, 12)) or torch.version.cuda != '12.8' or not torch.cuda.is_available():
        raise ValueError('Requires pinned Python/CUDA runtime')
    if torch.cuda.device_count() != 1:
        raise ValueError('Expose exactly one GPU')
    inventory = json.loads(Path(config['base_inventory_path']).read_text())
    _, bases, _ = registry(config)
    base = bases[request['baseId']]
    reference = inside(config['assets_dir'], base['image'])
    if sha(reference) != metadata['baseSha256']:
        raise ValueError('Input changed')
    with Image.open(reference) as im:
        image = im.copy()
    start = time.perf_counter()
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    pipe = StableDiffusionXLImg2ImgPipeline.from_pretrained(
        inventory['snapshot_path'], variant='fp16', torch_dtype=torch.float16,
        use_safetensors=True, local_files_only=True, force_zeros_for_empty_prompt=True,
        add_watermarker=False)
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
    adapter = Path(config['adapter_path'])
    pipe.load_lora_weights(str(adapter.parent), weight_name=adapter.name, adapter_name='candidate',
                           local_files_only=True, use_safetensors=True)
    pipe.set_adapters(['candidate'], adapter_weights=[1.0])
    state = load_file(str(adapter))
    modules = {n: m for n, m in pipe.unet.named_modules() if hasattr(m, 'lora_A') and 'candidate' in m.lora_A}
    names = {k.removeprefix('unet.').removesuffix('.lora_A.weight') for k in state if '.lora_A.' in k}
    if set(modules) != names or len(modules) != 794 or pipe.get_active_adapters() != ['candidate']:
        raise ValueError('Adapter module coverage mismatch')
    for name, module in modules.items():
        for factor in ('A', 'B'):
            actual = getattr(module, 'lora_' + factor)['candidate'].weight
            if not torch.equal(actual.cpu(), state[f'unet.{name}.lora_{factor}.weight'].to(actual.dtype)):
                raise ValueError('Loaded adapter differs')
        if float(module.scaling['candidate']) != 1.0 or module.disable_adapters:
            raise ValueError('Adapter scale mismatch')
    del state
    pipe.to('cuda')
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - start
    torch.cuda.reset_peak_memory_stats()
    prompt = metadata['prompt']
    tokens = []
    for tokenizer in (pipe.tokenizer, pipe.tokenizer_2):
        ids = tokenizer(prompt, truncation=False).input_ids
        tokens.append(dict(count=len(ids), maxLength=tokenizer.model_max_length,
                           truncated=len(ids) > tokenizer.model_max_length))
    timesteps = []

    def callback(pipeline, step, timestep, kwargs):
        timesteps.append(float(timestep.item()))
        return kwargs

    inference_start = time.perf_counter()
    result = pipe(prompt=prompt, image=image, strength=metadata['strength'],
                  num_inference_steps=metadata['steps'], guidance_scale=5.0,
                  negative_prompt=None, clip_skip=None,
                  generator=torch.Generator('cuda').manual_seed(request['seed']),
                  original_size=(1024, 1024), target_size=(1024, 1024),
                  crops_coords_top_left=(0, 0), callback_on_step_end=callback).images[0].convert('RGB')
    torch.cuda.synchronize()
    metrics = dict(elapsedSeconds=time.perf_counter() - start,
                   inferenceSeconds=time.perf_counter() - inference_start, loadSeconds=load_seconds,
                   includesColdModelLoad=True, peakAllocatedBytes=torch.cuda.max_memory_allocated(),
                   peakReservedBytes=torch.cuda.max_memory_reserved(), timesteps=timesteps,
                   denoisingSteps=len(timesteps), tokenization=tokens,
                   schedulerConfig=dict(pipe.scheduler.config), metadata=metadata, deployment=identity)
    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text('tp_img2img', json.dumps(metrics, ensure_ascii=False))
    temporary = result_path.with_suffix('.part')
    result.save(temporary, format='PNG', pnginfo=pnginfo)
    temporary.replace(result_path)
    metrics['outputSha256'] = sha(result_path)
    result_path.with_suffix('.metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    main()
