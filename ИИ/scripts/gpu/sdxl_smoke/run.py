"""Owner-run CUDA compatibility/inference experiment, isolated from service and site."""
import argparse
import datetime
import importlib.metadata
import itertools
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback
from common import REPO, REVISION, SOURCE_SHA, REFERENCE_SHA, CONFIG_SHA, COMPOSITION, sha, write_json

def cases(suite):
    if suite == 'pair':
        return [('img2img', 'textured', v) for v in [False, True]]
    if suite == 'efg':
        return [('img2img', 'textured', True), ('img2img', 'textured', False), ('img2img', 'flat', True)]
    return list(itertools.product(['text2img', 'img2img'], ['flat', 'textured'], [False, True]))

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--owner-run', action='store_true')
    ap.add_argument('--lora', type=Path, required=True, help='Explicitly converted derivative')
    ap.add_argument('--compat-report', type=Path, required=True)
    ap.add_argument('--reference', type=Path, required=True)
    ap.add_argument('--base-inventory', type=Path, required=True)
    ap.add_argument('--suite', choices=['pair', 'efg', 'matrix'], default='pair')
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if not args.owner_run:
        raise SystemExit('Requires --owner-run on your GPU machine')
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(status='RUNNING', suite=args.suite, started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  base_repo=REPO, base_revision=REVISION, source_lora_sha256=SOURCE_SHA,
                  cases=[], quality='NOT_REVIEWED', http='NOT_RUN', site='UNCHANGED')
    start = time.perf_counter()
    try:
        import torch
        import numpy as np
        from PIL import Image, PngImagePlugin
        from safetensors.torch import load_file
        from diffusers import StableDiffusionXLPipeline, StableDiffusionXLImg2ImgPipeline, EulerAncestralDiscreteScheduler
        expected = {'torch': '2.8.0', 'diffusers': '0.35.1', 'transformers': '4.56.2', 'peft': '0.17.1',
                    'accelerate': '1.10.1', 'safetensors': '0.6.2', 'huggingface-hub': '0.34.4'}
        versions = {n: importlib.metadata.version(n) for n in expected}
        if any(versions[n].split('+')[0] != v for n, v in expected.items()):
            raise ValueError('Unexpected inference versions: ' + str(versions))
        if sys.version_info[:2] not in [(3, 11), (3, 12)] or torch.version.cuda != '12.8' or not torch.cuda.is_available():
            raise ValueError('Requires Python 3.11/3.12, torch CUDA12.8 and working NVIDIA GPU')
        if torch.cuda.device_count() != 1:
            raise ValueError('Expose exactly one GPU via CUDA_VISIBLE_DEVICES')
        compatibility = json.loads(args.compat_report.read_text())
        if (compatibility['status'] != 'CPU_COMPATIBILITY_PASS_CONVERSION_REQUIRED'
                or compatibility['source_sha256'] != SOURCE_SHA
                or compatibility.get('converted_sha256') != sha(args.lora)):
            raise ValueError('Converted adapter does not match successful explicit compatibility report')
        if sha(args.reference) != REFERENCE_SHA:
            raise ValueError('Reference SHA mismatch')
        reference = Image.open(args.reference).convert('RGB')
        if reference.size != (1024, 1024):
            raise ValueError('Expected original 1024x1024 reference; do not silently resize')
        inventory = json.loads(args.base_inventory.read_text())
        if inventory['repo'] != REPO or inventory['revision'] != REVISION:
            raise ValueError('Base revision mismatch')
        base = Path(inventory['snapshot_path'])
        if not inventory['files'] or sha(base / 'unet/config.json') != CONFIG_SHA:
            raise ValueError('Base UNet config differs from pinned architecture')
        for f in inventory['files']:
            if sha(base / f['path']) != f['sha256']:
                raise ValueError('Base inventory SHA mismatch: ' + f['path'])
        report.update(versions=versions, python=sys.version, cuda_runtime=torch.version.cuda,
                      gpu=torch.cuda.get_device_name(0), reference_sha256=sha(args.reference),
                      converted_lora_sha256=sha(args.lora), base_inventory=inventory,
                      compatibility_report_sha256=sha(args.compat_report))
        report['nvidia_smi'] = subprocess.check_output(['nvidia-smi'], text=True)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        torch.cuda.synchronize(); torch.cuda.reset_peak_memory_stats()
        load_start = time.perf_counter()
        pipe = StableDiffusionXLPipeline.from_pretrained(str(base), variant='fp16', torch_dtype=torch.float16,
                     use_safetensors=True, local_files_only=True, force_zeros_for_empty_prompt=True,
                     add_watermarker=False)
        pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
        pipe.load_lora_weights(str(args.lora.resolve().parent), weight_name=args.lora.name,
                               adapter_name='candidate', local_files_only=True, use_safetensors=True)
        pipe.set_adapters(['candidate'], adapter_weights=[1.0])
        # Reject partial loading even if Diffusers only emitted a warning.
        state = load_file(str(args.lora))
        attached = {n: m for n, m in pipe.unet.named_modules() if hasattr(m, 'lora_A') and 'candidate' in m.lora_A}
        expected_names = {k.removeprefix('unet.').removesuffix('.lora_A.weight') for k in state if '.lora_A.' in k}
        if set(attached) != expected_names or len(attached) != 794:
            raise ValueError('Adapter module coverage mismatch')
        for name, module in attached.items():
            for factor in ['A', 'B']:
                actual = getattr(module, 'lora_' + factor)['candidate'].weight
                expected_tensor = state[f'unet.{name}.lora_{factor}.weight'].to(actual.dtype)
                if not torch.equal(actual.cpu(), expected_tensor):
                    raise ValueError('Loaded weights differ: ' + name)
            if float(module.scaling['candidate']) != 1.0:
                raise ValueError('Adapter scale mismatch: ' + name)
        del state
        pipe.to('cuda')
        # Shared components avoid loading a second copy of SDXL. New scheduler for every case.
        img = StableDiffusionXLImg2ImgPipeline(**pipe.components, add_watermarker=False)
        torch.cuda.synchronize()
        report.update(load_seconds=time.perf_counter() - load_start,
                      load_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                      load_peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                      adapter_modules=len(attached), active_adapters=pipe.get_active_adapters(),
                      scheduler_class='EulerAncestralDiscreteScheduler', scheduler_config=dict(pipe.scheduler.config))
        if pipe.get_active_adapters() != ['candidate']:
            raise ValueError('Candidate adapter not active')
        write_json(args.output / 'run.json', report)
        for mode, style, enabled in cases(args.suite):
            name = f'{mode}_{style}_{"on" if enabled else "off"}'
            current = pipe if mode == 'text2img' else img
            current.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
            current.set_adapters(['candidate'], adapter_weights=[1.0])
            (current.enable_lora if enabled else current.disable_lora)()
            if any(bool(m.disable_adapters) == enabled for m in attached.values()):
                raise ValueError('Adapter enable/disable state mismatch')
            prompt = f'tptrx, {"flat illustration" if style == "flat" else "textured ornament"}, '
            prompt += (COMPOSITION if mode == 'img2img' else 'one isolated blue lobed flower, centered on a white background, generous empty margins')
            tokenization = {}
            for label, tokenizer in [('clip_l', current.tokenizer), ('clip_g', current.tokenizer_2)]:
                ids = tokenizer(prompt, truncation=False).input_ids
                tokenization[label] = dict(input_ids=ids, length=len(ids), model_max_length=tokenizer.model_max_length,
                                           truncated=len(ids) > tokenizer.model_max_length)
            params = dict(prompt=prompt, negative_prompt=None, num_inference_steps=30, guidance_scale=5.0,
                          width=1024, height=1024, clip_skip=None, original_size=(1024, 1024),
                          target_size=(1024, 1024), crops_coords_top_left=(0, 0))
            if mode == 'img2img':
                params['strength'] = 0.45
                del params['width'], params['height']
            entry = dict(name=name, mode=mode, style=style, lora_enabled=enabled, lora_scale=1.0 if enabled else 0.0,
                         seed=20261008, parameters=params.copy(), tokenization=tokenization, png=name + '.png', status='RUNNING')
            report['cases'].append(entry)
            write_json(args.output / 'run.json', report)
            # Fresh generator resets image VAE sampling, initial noise and Euler ancestral noise for every case.
            params['generator'] = torch.Generator(device='cuda').manual_seed(20261008)
            if mode == 'img2img':
                params['image'] = reference.copy()
            callback_steps = []
            def callback(pipeline, step, timestep, callback_kwargs):
                callback_steps.append(float(timestep))
                return callback_kwargs
            torch.cuda.synchronize(); torch.cuda.reset_peak_memory_stats()
            t = time.perf_counter()
            result = current(**params, callback_on_step_end=callback).images[0].convert('RGB')
            torch.cuda.synchronize()
            entry.update(inference_seconds=time.perf_counter() - t,
                         peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                         peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                         denoising_steps=len(callback_steps), timesteps=callback_steps)
            pixels = np.asarray(result)
            if result.size != (1024, 1024) or not np.isfinite(pixels).all() or pixels.std() < 0.5:
                raise ValueError('Invalid/near-constant PNG; inspect numerical stability')
            info = PngImagePlugin.PngInfo(); info.add_text('tp_smoke', json.dumps(entry))
            result.save(args.output / entry['png'], pnginfo=info)
            entry.update(status='SAVED', sha256=sha(args.output / entry['png']),
                         pixel_sha256=__import__('hashlib').sha256(result.tobytes()).hexdigest())
            write_json(args.output / 'run.json', report)
        report['status'] = 'INFERENCE_COMPLETE_REVIEW_REQUIRED'
    except BaseException:
        report['status'] = 'FAILED_OR_INTERRUPTED'
        report['error'] = traceback.format_exc()
        raise
    finally:
        report['wall_seconds_including_checks_and_load'] = time.perf_counter() - start
        write_json(args.output / 'run.json', report)
    print(report['status'], args.output)

if __name__ == '__main__':
    main()
