"""Точка входа генератора v3: generate(params) -> (PIL.Image, info, tile|None)."""
import random
import zlib
from .core import BACKGROUNDS, ELEMENTS, FORMATS, PALETTES, TRADITIONS, Motifs, Scene, rgb
from .compositions import BUILDERS, COMPOSITIONS
from .frames import FRAMES, draw_frame

DEFAULTS = {'composition': 'bouquet', 'motifs': [], 'tradition': 'auto', 'density': 2, 'palette': 'original',
            'background': 'palette', 'format': 'square', 'frame': 'none', 'seed': 1, 'preview': 1.0}


def normalize(p):
    q = {**DEFAULTS, **{k: v for k, v in (p or {}).items() if v is not None}}
    if q['composition'] not in COMPOSITIONS: q['composition'] = 'bouquet'
    if q['palette'] not in PALETTES: q['palette'] = 'original'
    if q['background'] not in BACKGROUNDS: q['background'] = 'palette'
    if q['format'] not in FORMATS: q['format'] = 'square'
    if q['frame'] not in FRAMES: q['frame'] = 'none'
    if q['tradition'] not in TRADITIONS: q['tradition'] = 'auto'
    q['density'] = min(3, max(1, int(q['density'])))
    q['seed'] = int(q['seed']) % 2_147_483_648
    q['motifs'] = [c for c in q['motifs'] if c in ELEMENTS][:6]
    q['preview'] = min(1.0, max(0.2, float(q['preview'])))
    return q


def generate(params):
    p = normalize(params)
    rng = random.Random(p['seed'] * 7919 + zlib.crc32(p['composition'].encode()) % 1000)
    comp = COMPOSITIONS[p['composition']]
    m = Motifs(p['motifs'], p['tradition'], rng, comp['prefer'])
    pal = PALETTES[p['palette']]
    _, W, H = FORMATS[p['format']]
    W, H = round(W * p['preview']), round(H * p['preview'])
    if p['background'] == 'palette':
        bg = rgb(pal['bg']) + (255,)
    elif p['background'] == 'transparent':
        bg = (0, 0, 0, 0)
    else:
        bg = rgb(BACKGROUNDS[p['background']]) + (255,)
    # цвет стеблей: из палитры, иначе — тёмный цвет главного мотива
    tile = None
    if p['composition'] == 'pattern':
        T = round(min(W, H) / (2 if p['density'] < 3 else 2.5))
        T -= T % 2
        stem_c = pal.get('stem')
        sc = Scene(T, T, p['palette'], stem_c or '#3b3a30', wrap=True)
        BUILDERS['pattern'](sc, m, rng, (0, 0, T, T), p['density'])
        if not stem_c:
            sc.stem_color = tuple(ELEMENTS[sc.used[0]]['ink'])
            sc.ops = [(z, k, d if k not in ('stem', 'dot') else _recolor(k, d, sc.stem_color)) for z, k, d in sc.ops]
        tile = sc.render(bg)
        from PIL import Image
        img = Image.new('RGBA', (W, H), bg)
        ox, oy = (W % T) // 2 - T, (H % T) // 2 - T
        for y in range(oy, H, T):
            for x in range(ox, W, T):
                img.alpha_composite(tile, (x, y)) if x >= 0 and y >= 0 else _paste(img, tile, x, y)
        used = sc.used
    else:
        stem_c = pal.get('stem')
        sc = Scene(W, H, p['palette'], stem_c or '#3b3a30')
        mg = round(min(W, H) * 0.045)
        box = draw_frame(sc, p['frame'], m, (mg, mg, W - mg, H - mg), p['density']) if p['frame'] != 'none' else (mg, mg, W - mg, H - mg)
        if p['frame'] == 'none':
            g = round(min(W, H) * 0.01); box = (box[0] + g, box[1] + g, box[2] - g, box[3] - g)
        bw, bh = box[2] - box[0], box[3] - box[1]
        ratio = bw / bh
        n = 1
        if p['composition'] in ('bouquet', 'rosette', 'corner'):
            if ratio > 1.45: n = round(ratio * (1.15 if p['composition'] == 'bouquet' else 1))
            elif ratio < 0.69 and p['composition'] != 'bouquet': n = -round(1 / ratio)
        if abs(n) > 1:
            # Вытянутый формат: повторяем композицию ритмом (как на полотенце/подзоре).
            state = rng.getstate()
            for i in range(abs(n)):
                rng.setstate(state)
                m = Motifs(p['motifs'], m.tradition, rng, comp['prefer'])
                if n > 0:
                    sub = (box[0] + bw * i / n, box[1], box[0] + bw * (i + 1) / n, box[3])
                else:
                    sub = (box[0], box[1] + bh * i / -n, box[2], box[1] + bh * (i + 1) / -n)
                BUILDERS[p['composition']](sc, m, rng, sub, p['density'])
        else:
            BUILDERS[p['composition']](sc, m, rng, box, p['density'])
        if not stem_c:
            hero = next((c for c in sc.used if c in m.taken), sc.used[0])
            sc.stem_color = _stem_from(hero)
            sc.ops = [(z, k, d if k not in ('stem', 'dot', 'ring', 'rect') else _recolor(k, d, sc.stem_color)) for z, k, d in sc.ops]
        img = sc.render(bg)
        used = sc.used
    info = {
        'params': p, 'tradition': m.tradition, 'traditionTitle': TRADITIONS[m.tradition],
        'composition': comp['title'], 'note': comp['note'],
        'used': [{'code': c, 'name': ELEMENTS[c]['name'], 'source': ELEMENTS[c]['source'], 'technique': ELEMENTS[c]['technique']} for c in used],
        'size': [W, H], 'seamlessTile': tile.size if tile else None,
    }
    return img, info, tile


def _stem_from(code):
    r, g, b = ELEMENTS[code]['ink']
    return (r, g, b)


def _recolor(kind, data, c):
    d = list(data)
    idx = {'stem': 3, 'dot': 3, 'ring': 3, 'rect': 2}[kind]
    d[idx] = c
    return tuple(d)


def _paste(canvas, img, x, y):
    from .core import paste
    paste(canvas, img, x, y)
