"""CPU audit; explicit opt-in writes a NEW converted file, never the source."""
import argparse
import collections
import importlib.metadata
import json
from pathlib import Path
import traceback
from common import HERE, SOURCE_SHA, REPO, REVISION, CONFIG_SHA, sha, meta_unet, prepare_state, adapter_metadata, write_json

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--lora', type=Path, required=True)
    ap.add_argument('--report', type=Path, required=True)
    ap.add_argument('--write-converted', type=Path)
    ap.add_argument('--acknowledge-format-change', action='store_true')
    args = ap.parse_args()
    if args.report.exists():
        raise SystemExit('Report exists; use a new report filename')
    if args.write_converted and (not args.acknowledge_format_change or args.write_converted.exists()
                                or args.write_converted.resolve() == args.lora.resolve()):
        raise SystemExit('Conversion needs acknowledgement and a NEW output filename')
    report = dict(source_sha256=sha(args.lora), expected_source_sha256=SOURCE_SHA,
                  base_repo=REPO, base_revision=REVISION, unet_config_sha256=CONFIG_SHA,
                  environment={n: importlib.metadata.version(n) for n in ['torch', 'diffusers', 'peft', 'safetensors']},
                  gpu_inference='NOT_RUN', conversion_file_written=False)
    try:
        if report['source_sha256'] != SOURCE_SHA:
            raise ValueError('Candidate SHA mismatch')
        from diffusers import StableDiffusionXLPipeline
        from safetensors.torch import save_file
        unet = meta_unet()
        try:
            StableDiffusionXLPipeline.lora_state_dict(str(args.lora.resolve().parent), weight_name=args.lora.name,
                                                     unet_config=unet.config, local_files_only=True, use_safetensors=True)
            report['original_loader'] = 'PARSED_NOT_ATTACHED'
        except Exception as exc:
            report['original_loader'] = 'INCOMPATIBLE'
            report['original_loader_error'] = f'{type(exc).__name__}: {exc}'
        state, mapping = prepare_state(args.lora, unet)
        report.update(source_modules=len(mapping), mapped_tensors=len(state),
                      ranks=dict(collections.Counter(str(m['rank']) for m in mapping)),
                      shape_changes=[m for m in mapping if m['original_shapes'] != m['target_shapes']], mapping=mapping)
        # Broadcast scalar placeholders give the base CPU devices with negligible storage.
        # No forward pass is possible/meaningful with this base; only adapter loading is tested.
        import torch
        for module in unet.modules():
            for name, param in list(module.named_parameters(recurse=False)):
                setattr(module, name, torch.nn.Parameter(torch.zeros(1, dtype=param.dtype).expand(param.shape),
                                                        requires_grad=False))
            for name, buf in list(module.named_buffers(recurse=False)):
                setattr(module, name, torch.zeros(1, dtype=buf.dtype).expand(buf.shape))
        report['base_for_cpu_loader'] = 'shape-only CPU broadcast placeholders; no base weights/no forward pass'
        # Actual supported pipeline loader, no base checkpoint download.
        pipe = StableDiffusionXLPipeline(vae=None, text_encoder=None, text_encoder_2=None,
                                        tokenizer=None, tokenizer_2=None, unet=unet, scheduler=None)
        metadata = adapter_metadata(mapping)
        # Dict load_lora_weights in 0.35.1 drops explicit metadata; file loading reads it.
        # Exercise the same supported UNet loader here without writing a derivative file.
        pipe.load_lora_into_unet(state, network_alphas=None, unet=unet, adapter_name='candidate',
                                 low_cpu_mem_usage=True, metadata=metadata, _pipeline=pipe)
        pipe.set_adapters(['candidate'], adapter_weights=[1.0])
        attached = {n: m for n, m in unet.named_modules() if hasattr(m, 'lora_A') and 'candidate' in m.lora_A}
        if set(attached) != {m['target'] for m in mapping}:
            raise ValueError('Attached module set differs from mapping')
        for name, module in attached.items():
            for factor in ['A', 'B']:
                actual = getattr(module, 'lora_' + factor)['candidate'].weight
                expected = state[f'unet.{name}.lora_{factor}.weight']
                if actual.is_meta or not torch.equal(actual.cpu(), expected):
                    raise ValueError('Loaded adapter values differ: ' + name)
            if float(module.scaling['candidate']) != 1.0:
                raise ValueError('Adapter scaling changed: ' + name)
        report.update(proposed_state_loader='PASS_ALL_VALUES_AND_MODULES', active_adapters=pipe.get_active_adapters(),
                      attached_modules=len(attached), alpha_over_rank=1.0,
                      cpu_loader_method='load_lora_into_unet with explicit metadata; file load_lora_weights deferred to GPU run')
        if args.write_converted:
            save_file(state, str(args.write_converted), metadata=dict(source_sha256=SOURCE_SHA,
                      base_revision=REVISION, conversion='explicit SGM to Diffusers PEFT; singleton reshape; alpha/rank=1',
                      lora_adapter_metadata=json.dumps(metadata)))
            report.update(conversion_file_written=True, converted_path=str(args.write_converted.resolve()),
                          converted_sha256=sha(args.write_converted))
        report['status'] = 'CPU_COMPATIBILITY_PASS_CONVERSION_REQUIRED'
    except Exception:
        report['status'] = 'FAILED'
        report['error'] = traceback.format_exc()
        raise
    finally:
        write_json(args.report, report)
    print(report['status'], args.report)

if __name__ == '__main__':
    main()
