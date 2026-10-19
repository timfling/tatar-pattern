"""Immutable img2img contract and local deployment checks. No torch/network imports."""
import hashlib
import json
from pathlib import Path

CONTRACT = 'tp-gpu-img2img/1.0'
WORKFLOW = 'tp-sdxl-composition-img2img/1.0.0'
MODEL = '378c08ff157660a3399573e1cd5918ad8f3aec344646c5336b027d63fe50ca42'
BASE_REPO = 'stabilityai/stable-diffusion-xl-base-1.0'
BASE_REVISION = '462165984030d82259a11f4367a4eed129e94a7b'
VERSIONS = {'torch': '2.8.0', 'diffusers': '0.35.1', 'transformers': '4.56.2',
            'peft': '0.17.1', 'accelerate': '1.10.1', 'safetensors': '0.6.2',
            'huggingface-hub': '0.34.4', 'Pillow': '11.3.0', 'numpy': '2.2.6'}
HERE = Path(__file__).resolve().parent


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def inside(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Asset path outside allowlist root')
    return path


def base_file(snapshot, relative):
    """Permit pinned HF snapshot links only into this repository's blob cache."""
    root = Path(snapshot).resolve()
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Base path outside pinned snapshot')
    path = (root / relative).resolve()
    if path.is_relative_to(root):
        return path
    if (root.name == BASE_REVISION and root.parent.name == 'snapshots'
            and root.parent.parent.name == 'models--stabilityai--stable-diffusion-xl-base-1.0'):
        blobs = root.parent.parent / 'blobs'
        # Do not let a symlink replacing the blob directory expand the boundary.
        if not blobs.is_symlink() and path.is_relative_to(blobs):
            return path
    raise ValueError('Base link outside pinned repository cache')


def registry(config):
    assets = Path(config['assets_dir'])
    index = json.loads((assets / 'index.json').read_text())
    profiles = json.loads(Path(config['profiles_path']).read_text())
    if index['schemaVersion'] != 'tp-ai-bases/1.0.0' or profiles['schemaVersion'] != 'tp-gpu-profiles/1.0':
        raise ValueError('Registry schema mismatch')
    bases = {b['id']: b for b in index['bases']}
    if len(bases) != len(index['bases']):
        raise ValueError('Duplicate base ID')
    pairs = {}
    for p in profiles['profiles']:
        key = (p['baseId'], p['ornamentStyle'])
        if key in pairs or p['ornamentStyle'] not in ('graphic', 'textured'):
            raise ValueError('Duplicate/invalid profile')
        if bases[p['baseId']]['sha256'] != p['baseSha256']:
            raise ValueError('Profile asset mismatch')
        # Strength belongs to the pinned per-pair profile, never the HTTP client.
        # SDXL needs at least one effective denoising step for this schedule.
        strength, steps = p['strength'], p['steps']
        if (type(steps) is not int or steps not in (30, 100)
                or type(strength) not in (int, float) or not 0 < strength <= 1
                or int(steps * strength) < 1):
            raise ValueError('Invalid server recipe settings')
        if not p['prompt'].startswith('tptrx, ') or not p['promptVersion']:
            raise ValueError('Missing system prompt')
        pairs[key] = p
    return index, bases, pairs


def validate(request, config):
    required = {'contractVersion', 'workflowVersion', 'modelVersion', 'catalogVersion',
                'baseId', 'baseSha256', 'ornamentStyle', 'profileVersion', 'seed'}
    if not isinstance(request, dict) or set(request) != required:
        return 'INVALID_PARAMETERS'
    if any(type(request[k]) is not str for k in required - {'seed'}):
        return 'INVALID_PARAMETERS'
    if type(request['seed']) is not int or not 0 <= request['seed'] <= 2147483647:
        return 'INVALID_PARAMETERS'
    if (request['contractVersion'], request['workflowVersion'], request['modelVersion']) != (CONTRACT, WORKFLOW, MODEL):
        return 'VERSION_MISMATCH'
    index, bases, profiles = registry(config)
    if request['catalogVersion'] != index['catalogVersion']:
        return 'VERSION_MISMATCH'
    if request['baseId'] not in bases:
        return 'AI_BASE_UNKNOWN'
    profile = profiles.get((request['baseId'], request['ornamentStyle']))
    if profile is None:
        return 'AI_COMBINATION_UNAVAILABLE'
    if request['baseSha256'] != profile['baseSha256'] or request['profileVersion'] != profile['version']:
        return 'VERSION_MISMATCH'
    return None


def resolved(request, config):
    error = validate(request, config)
    if error:
        raise ValueError(error)
    index, bases, profiles = registry(config)
    base = bases[request['baseId']]
    profile = profiles[request['baseId'], request['ornamentStyle']]
    return dict(contractVersion=CONTRACT, workflowVersion=WORKFLOW, modelVersion=MODEL,
                catalogVersion=index['catalogVersion'], baseId=base['id'],
                baseSha256=base['sha256'], recipeSha256=base['recipeSha256'],
                ornamentStyle=request['ornamentStyle'], profileVersion=profile['version'],
                profileDigest=digest(profile), promptVersion=profile['promptVersion'],
                prompt=profile['prompt'], seed=request['seed'], strength=profile['strength'],
                steps=profile['steps'], width=1024, height=1024, guidanceScale=5.0,
                loraScale=1.0, scheduler='EulerAncestralDiscreteScheduler',
                negativePrompt=None, forceZerosForEmptyPrompt=True, clipSkip=None,
                control=False, refiner=False, seamless=False)


def deployment(config, verify_files=True):
    """Fingerprint code/weights/base inventory/assets/profiles, never secrets or smoke record."""
    from PIL import Image
    index, bases, profiles = registry(config)
    inventory = json.loads(Path(config['base_inventory_path']).read_text())
    if inventory['repo'] != BASE_REPO or inventory['revision'] != BASE_REVISION or not inventory['files']:
        raise ValueError('Base inventory mismatch')
    if config['workflow_version'] != WORKFLOW or config['adapter_sha256'] != MODEL:
        raise ValueError('Deployment version mismatch')
    if verify_files:
        if sha(config['adapter_path']) != MODEL:
            raise ValueError('Adapter SHA mismatch')
        for item in inventory['files']:
            if sha(base_file(inventory['snapshot_path'], item['path'])) != item['sha256']:
                raise ValueError('Base file SHA mismatch')
        for base in bases.values():
            path = inside(config['assets_dir'], base['image'])
            if sha(path) != base['sha256'] or sha(inside(config['assets_dir'], base['recipe'])) != base['recipeSha256']:
                raise ValueError('Asset SHA mismatch')
            with Image.open(path) as im:
                im.load()
                if im.format != 'PNG' or im.mode != 'RGB' or im.size != (1024, 1024):
                    raise ValueError('Expected opaque RGB PNG1024')
    identity = dict(contractVersion=CONTRACT, workflowVersion=WORKFLOW, modelVersion=MODEL,
                    catalogVersion=index['catalogVersion'], registryDigest=digest(index),
                    profilesDigest=digest(list(profiles.values())), baseInventoryDigest=digest(inventory),
                    code={name: sha(HERE / name) for name in ('workflow.py', 'server.py', 'render_one.py')},
                    runtimeVersions=VERSIONS)
    return identity | {'deploymentDigest': digest(identity)}
