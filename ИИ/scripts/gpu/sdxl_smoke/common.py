"""Fixed experimental candidate. No provider API, training, or implicit conversion."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = 'stabilityai/stable-diffusion-xl-base-1.0'
REVISION = '462165984030d82259a11f4367a4eed129e94a7b'
SOURCE_SHA = '600293069a789ed8d8e1ff0b22b6d1dc301a75543fca4714102829224b622457'
REFERENCE_SHA = '537b1799a352dc104d62cbebb19c47337b5f0977dbbe29b52bf8222977de37b5'
CONFIG_SHA = '30ebc70750223e59006f7f2b4e1e6c102570aa19a9c4ae3e1fbe7591332dbae6'
COMPOSITION = ('a complete centered ornamental medallion, one pale green radial flower with a lavender circular center, '
               'a circular arrangement of brown pointed palmettes around the flower, a pair of green curling leaves below, '
               'balanced radial composition, clean colored outlines, pale cream background, generous empty margins')

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(chunk)
    return h.hexdigest()

def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def meta_unet():
    import torch
    from diffusers import UNet2DConditionModel
    if sha(HERE / 'unet-config.json') != CONFIG_SHA:
        raise ValueError('Pinned UNet config SHA mismatch')
    with torch.device('meta'):
        return UNet2DConditionModel.from_config(json.loads((HERE / 'unet-config.json').read_text()))

def adapter_metadata(mapping):
    # PEFT must retain alpha=32 on rank32 modules; inferred global alpha=16 would halve them.
    return {'unet.r': 16, 'unet.lora_alpha': 16,
            'unet.rank_pattern': {m['target']: m['rank'] for m in mapping if m['rank'] != 16},
            'unet.alpha_pattern': {m['target']: int(m['alpha']) for m in mapping if m['alpha'] != 16},
            'unet.target_modules': [m['target'] for m in mapping], 'unet.lora_dropout': 0.0,
            'unet.bias': 'none', 'unet.use_dora': False, 'unet.use_rslora': False}

def target_name(source, modules):
    """Resolve SGM SDXL names against real Diffusers modules; never guess a target."""
    s = source.removeprefix('lora_unet_')
    special = {'input_blocks_0_0': 'conv_in', 'out_2': 'conv_out',
               'time_embed_0': 'time_embedding.linear_1', 'time_embed_2': 'time_embedding.linear_2',
               'label_emb_0_0': 'add_embedding.linear_1', 'label_emb_0_2': 'add_embedding.linear_2'}
    if s in special:
        return special[s]
    match = re.fullmatch(r'(input_blocks|output_blocks)_(\d+)_(\d+)_(.+)', s)
    if match:
        kind, index, inner, tail = match.groups()
        index, inner = int(index), int(inner)
        if kind == 'input_blocks':
            block, layer = divmod(index - 1, 3)
            if layer == 2 and inner == 0 and tail == 'op':
                return f'down_blocks.{block}.downsamplers.0.conv'
            prefix = f'down_blocks.{block}'
        else:
            block, layer = divmod(index, 3)
            prefix = f'up_blocks.{block}'
            if inner == 2 and tail == 'conv':
                return f'{prefix}.upsamplers.0.conv'
        prefix += f'.{"resnets" if inner == 0 else "attentions"}.{layer}'
    else:
        match = re.fullmatch(r'middle_block_([012])_(.+)', s)
        if not match:
            raise ValueError('Unknown source module: ' + source)
        inner, tail = match.groups()
        prefix = 'mid_block.' + {'0': 'resnets.0', '1': 'attentions.0', '2': 'resnets.1'}[inner]
    tail = {'in_layers_2': 'conv1', 'out_layers_3': 'conv2',
            'emb_layers_1': 'time_emb_proj', 'skip_connection': 'conv_shortcut'}.get(tail, tail)
    matches = [n for n in modules if n.startswith(prefix + '.') and n[len(prefix) + 1:].replace('.', '_') == tail]
    if len(matches) != 1:
        raise ValueError(f'Unresolved/ambiguous module {source}: {matches}')
    return matches[0]

def prepare_state(path, unet):
    """In-memory proposal only. Keep all modules; reshape singleton conv factors only."""
    import torch
    from safetensors.torch import load_file
    if sha(path) != SOURCE_SHA:
        raise ValueError('Original candidate SHA mismatch')
    state = load_file(str(path), device='cpu')
    modules = dict(unet.named_modules())
    converted, mapping, consumed = {}, [], set()
    for key in sorted(state):
        if not key.endswith('.lora_down.weight'):
            continue
        stem = key.removesuffix('.lora_down.weight')
        up_key, alpha_key = stem + '.lora_up.weight', stem + '.alpha'
        a, b, alpha = state[key], state[up_key], float(state[alpha_key].item())
        rank = a.shape[0]
        if alpha != rank:
            raise ValueError(f'alpha/rank != 1 at {stem}; scaling requires a separately reviewed conversion')
        name = target_name(stem, modules)
        module = modules[name]
        if isinstance(module, torch.nn.Linear):
            a_shape, b_shape = (rank, module.in_features), (module.out_features, rank)
        elif isinstance(module, torch.nn.Conv2d) and module.groups == 1:
            a_shape = (rank, module.in_channels, *module.kernel_size)
            b_shape = (module.out_channels, rank, 1, 1)
        else:
            raise ValueError('Unsupported target type: ' + name)
        # Only missing/present trailing 1x1 dimensions can change, never tensor values/order.
        def reshape_factor(t, shape):
            if tuple(t.shape) != shape and not (tuple(t.shape[:2]) == shape[:2]
                    and all(v == 1 for v in t.shape[2:]) and all(v == 1 for v in shape[2:])):
                raise ValueError(f'{stem}: shape {tuple(t.shape)} incompatible with {shape}')
            if not torch.isfinite(t).all():
                raise ValueError('Nonfinite tensor: ' + stem)
            return t.reshape(shape).contiguous()
        for factor, tensor, shape in [('A', a, a_shape), ('B', b, b_shape)]:
            target = f'unet.{name}.lora_{factor}.weight'
            if target in converted:
                raise ValueError('Duplicate mapped target: ' + target)
            converted[target] = reshape_factor(tensor, shape)
        mapping.append(dict(source=stem, target=name, rank=rank, alpha=alpha,
                            original_shapes=[list(a.shape), list(b.shape)],
                            target_shapes=[list(a_shape), list(b_shape)]))
        consumed.update([key, up_key, alpha_key])
    if consumed != set(state) or len(mapping) != 794:
        raise ValueError('Unconsumed source tensors or unexpected module count')
    return converted, mapping
