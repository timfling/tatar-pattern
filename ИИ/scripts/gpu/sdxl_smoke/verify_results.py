"""Verify technical outputs and controlled pairs; this never accepts visual quality."""
import argparse
import hashlib
import json
from pathlib import Path
from common import sha, write_json
from run import cases

def verify(folder):
    import numpy as np
    from PIL import Image
    record = json.loads((folder / 'run.json').read_text())
    if record['status'] != 'INFERENCE_COMPLETE_REVIEW_REQUIRED':
        raise ValueError('Run incomplete/failed; inspect run.json and console.log')
    expected = {f'{m}_{s}_{"on" if enabled else "off"}' for m, s, enabled in cases(record['suite'])}
    entries = {r['name']: r for r in record['cases']}
    if set(entries) != expected or len(entries) != len(record['cases']):
        raise ValueError('Unexpected/missing case set')
    pixels = {}
    for name, r in entries.items():
        p = folder / r['png']
        if r['status'] != 'SAVED' or sha(p) != r['sha256']:
            raise ValueError('PNG status/SHA mismatch: ' + name)
        with Image.open(p) as im:
            im.load()
            if im.format != 'PNG' or im.size != (1024, 1024) or im.mode != 'RGB':
                raise ValueError('Invalid PNG: ' + name)
            if hashlib.sha256(im.tobytes()).hexdigest() != r['pixel_sha256']:
                raise ValueError('Pixel SHA mismatch: ' + name)
            pixels[name] = np.asarray(im).copy()
        if not r['denoising_steps'] or r['inference_seconds'] <= 0 or r['peak_allocated_bytes'] <= 0:
            raise ValueError('Missing inference metrics: ' + name)
    pairs = []
    for name, off in entries.items():
        if not name.endswith('_off'):
            continue
        on_name = name.removesuffix('_off') + '_on'
        if on_name not in entries:
            continue
        on = entries[on_name]
        if off['parameters'] != on['parameters'] or off['seed'] != on['seed'] or off['timesteps'] != on['timesteps']:
            raise ValueError('Controlled off/on settings differ: ' + name)
        a, b = pixels[name], pixels[on_name]
        pairs.append(dict(off=name, on=on_name, identical=bool(np.array_equal(a, b)),
                          mean_abs_channel_difference_0_255=float(np.abs(a.astype(float) - b).mean())))
    if not pairs:
        raise ValueError('No LoRA off/on pair found')
    if any(p['identical'] for p in pairs):
        raise ValueError('Identical off/on pixels: adapter effect NOT ESTABLISHED; inspect activation')
    # E/G share source/settings and differ only by the style phrase.
    e, g = entries.get('img2img_textured_on'), entries.get('img2img_flat_on')
    if e and g:
        ep, gp = e['parameters'].copy(), g['parameters'].copy()
        ep['prompt'] = ep['prompt'].replace('textured ornament', 'STYLE')
        gp['prompt'] = gp['prompt'].replace('flat illustration', 'STYLE')
        if ep != gp or e['seed'] != g['seed'] or e['timesteps'] != g['timesteps']:
            raise ValueError('E/G differ beyond style phrase')
    return dict(status='TECHNICAL_CHECKS_PASS', suite=record['suite'], images=len(entries), pairs=pairs,
                quality='REQUIRES_HUMAN_REVIEW', http='NOT_RUN', production='NOT_ACCEPTED',
                limitation='Pixel difference shows a changed result, not useful style or quality. CUDA allocator peaks are process measurements, not total board usage.')

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('folder', type=Path)
    args = ap.parse_args()
    output = args.folder / 'verification.json'
    try:
        result = verify(args.folder)
    except Exception as exc:
        write_json(output, dict(status='FAILED', error=f'{type(exc).__name__}: {exc}'))
        raise
    write_json(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
