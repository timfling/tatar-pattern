"""Конструктор v3: каталог для интерфейса, превью и рендер результата в файлы generations.

Мотивы берутся только из принятого каталога (approved_element_files); разметка категорий —
elements.json (prototype-v3/build_cache.py). Генератор не отказывает: недостающие роли
добираются из той же традиции, затем из всего каталога.
"""
import hashlib
import io
import threading
from pathlib import Path
from PIL import Image
from . import core
from .compositions import COMPOSITIONS
from .core import BACKGROUNDS, CATEGORY_LABELS, ELEMENTS, FORMATS, PALETTES, TRADITIONS, rgb
from .engine import generate, normalize
from .frames import FRAMES

VERSION = 'composition-v3/1.0.0'
_lock = threading.Lock()
_previews: dict = {}

DENSITY = [
    {'id': 1, 'title': 'Лаконично', 'hint': 'Главные мотивы и воздух вокруг них'},
    {'id': 2, 'title': 'Сбалансированно', 'hint': 'Ветви, листья, бутоны и завитки'},
    {'id': 3, 'title': 'Богато', 'hint': 'Дополнительные ярусы, кольца и детали'},
]
PALETTE_HINTS = {
    'original': 'Мотивы сохраняют цвета музейных предметов, с которых они сняты.',
    'tambour': 'Красный, зелёный, синий и охра на светлом холсте — гамма тамбурной вышивки.',
    'kalfak': 'Золотое шитьё на малиновом бархате, как на праздничных калфаках.',
    'towel': 'Красный узор на белёном холсте — гамма браных полотенец.',
    'ceramics': 'Кобальтовая роспись на светлом черепке.',
    'emerald': 'Золото и коралл на глубоком зелёном.',
    'shamail': 'Золото и яркие акценты на тёмном фоне, как на стеклянных шамаилях.',
    'terracotta': 'Тёплые глиняные оттенки с оливковым акцентом.',
}
BG_TITLES = {'palette': 'Как в палитре', 'light': 'Светлый', 'white': 'Белый', 'green': 'Зелёный',
             'burgundy': 'Бордовый', 'dark': 'Тёмный', 'transparent': 'Прозрачный (PNG)'}


def bind(rows):
    """rows — принятые элементы из catalog(); только они доступны генератору."""
    core.set_sources({r['code']: str(r['local_path']) for r in rows if r['code'] in ELEMENTS})


def available():
    return [c for c in ELEMENTS if c in core.SOURCES]


def catalog():
    codes = set(available())
    return {
        'version': VERSION,
        'compositions': [{'id': k, 'title': v['title'], 'hint': v['hint'], 'note': v['note'],
                          'preview': f'/api/v3/previews/comp-{k}.jpg'} for k, v in COMPOSITIONS.items()],
        'previewPatterns': {'density': '/api/v3/previews/den-{composition}-{density}.jpg',
                            'palette': '/api/v3/previews/pal-{palette}-{composition}.jpg'},
        'density': DENSITY,
        'traditions': [{'id': k, 'title': v} for k, v in TRADITIONS.items()],
        'categories': [{'id': k, 'title': v} for k, v in CATEGORY_LABELS.items()],
        'motifs': [{'code': c, 'name': e['name'], 'source': e['source'], 'technique': e['technique'],
                    'categories': e['categories'], 'traditions': e['traditions'],
                    'thumb': f'/api/v3/thumbs/{c}.png'} for c, e in ELEMENTS.items() if c in codes],
        'palettes': [{'id': k, 'title': v['name'], 'bg': v['bg'], 'colors': v.get('colors', []),
                      'hint': PALETTE_HINTS.get(k, '')} for k, v in PALETTES.items()],
        'backgrounds': [{'id': k, 'title': BG_TITLES[k], 'color': v if str(v).startswith('#') else None} for k, v in BACKGROUNDS.items()],
        'formats': [{'id': k, 'title': v[0], 'w': v[1], 'h': v[2]} for k, v in FORMATS.items()],
        'frames': [{'id': k, 'title': v} for k, v in FRAMES.items()],
        'maxMotifs': 6,
    }


def _jpg(img, bg=(241, 233, 218, 255), quality=86):
    base = Image.new('RGBA', img.size, bg); base.alpha_composite(img.convert('RGBA'))
    buf = io.BytesIO(); base.convert('RGB').save(buf, 'JPEG', quality=quality); return buf.getvalue()


def preview(name):
    """Превью для карточек выбора: comp-<композиция>, den-<композиция>-<1..3>, pal-<палитра>-<композиция>.
    Строятся по требованию и кэшируются в памяти процесса."""
    with _lock:
        if name in _previews:
            return _previews[name]
    parts = name.removesuffix('.jpg').split('-')
    kind = parts[0]
    if kind == 'comp' and len(parts) == 2 and parts[1] in COMPOSITIONS:
        img, _, _ = generate({'composition': parts[1], 'density': 2, 'seed': 11, 'preview': 0.3})
        data = _jpg(img)
    elif kind == 'den' and len(parts) == 3 and parts[1] in COMPOSITIONS and parts[2] in ('1', '2', '3'):
        img, _, _ = generate({'composition': parts[1], 'density': int(parts[2]), 'seed': 11, 'preview': 0.3})
        data = _jpg(img)
    elif kind == 'pal' and len(parts) == 3 and parts[1] in PALETTES and parts[2] in COMPOSITIONS:
        img, _, _ = generate({'composition': parts[2], 'density': 2, 'seed': 11, 'palette': parts[1], 'preview': 0.3})
        data = _jpg(img, rgb(PALETTES[parts[1]]['bg']) + (255,))
    else:
        return None
    with _lock:
        _previews[name] = data
    return data


def variant(params, seed, scale=0.5):
    """Быстрое превью одного варианта (без сохранения): data URL + сведения о составе."""
    import base64
    p = normalize({**params, 'seed': seed, 'preview': scale})
    img, info, _ = generate(p)
    if p['background'] == 'transparent':
        buf = io.BytesIO(); img.save(buf, 'PNG'); data, mime = buf.getvalue(), 'image/png'
    else:
        data, mime = _jpg(img, rgb(PALETTES[p['palette']]['bg']) + (255,), 88), 'image/jpeg'
    return {'seed': seed, 'image': f'data:{mime};base64,' + base64.b64encode(data).decode(), 'size': list(img.size),
            'fullSize': [round(v / scale) for v in img.size],
            'info': {'composition': info['composition'], 'compositionId': p['composition'], 'note': info['note'],
                     'tradition': info['tradition'], 'traditionTitle': info['traditionTitle'], 'used': info['used']}}


def thumb(code):
    if code not in core.SOURCES:
        return None
    key = 'thumb-' + code
    with _lock:
        if key in _previews:
            return _previews[key]
    im = core.base_sprite(code).copy(); im.thumbnail((160, 160), Image.Resampling.LANCZOS)
    buf = io.BytesIO(); im.save(buf, 'PNG'); data = buf.getvalue()
    with _lock:
        _previews[key] = data
    return data


def render(v3, seed, png: Path, jpg: Path):
    """Полноразмерный рендер; PNG (с прозрачностью, если выбрана) + JPG на сплошном фоне."""
    params = normalize({**(v3 or {}), 'seed': seed, 'preview': 1.0})
    img, info, tile = generate(params)
    png.parent.mkdir(parents=True, exist_ok=True)
    img.save(png)
    bg = rgb(PALETTES[params['palette']]['bg']) + (255,)
    jpg.write_bytes(_jpg(img, bg, 92))
    repeat = None
    if tile is not None:
        module = png.with_name(png.stem + '.module.png'); tile.save(module)
        repeat = {'periodPx': list(tile.size), 'moduleSha256': hashlib.sha256(module.read_bytes()).hexdigest(), 'moduleFileSuffix': '.module.png'}
    used = [u['code'] for u in info['used']]
    recipe = {
        'algorithmVersion': VERSION, 'renderer': 'composition-v3', 'v3': params, 'seed': seed,
        'size': list(img.size), 'outputKind': 'repeat_module' if tile is not None else 'composition_image',
        'seamless': tile is not None, 'repeat': repeat, 'isFixture': False,
        'usedElementCodes': used, 'selectedElementCodes': params['motifs'],
        'v3Info': {'composition': info['composition'], 'compositionId': params['composition'], 'note': info['note'],
                   'tradition': info['tradition'], 'traditionTitle': info['traditionTitle'], 'used': info['used']},
        'transparentBackground': params['background'] == 'transparent',
        'culturalNote': {'text': info['note'] + ' Каркас основан на традиционной схеме; конкретная расстановка — современное дизайнерское решение.',
                         'claimType': 'composition_scheme_basis', 'appliesTo': 'scheme_only_not_layout_authenticity'},
    }
    return recipe, []


def describe(recipe):
    i = recipe.get('v3Info') or {}
    text = f"{i.get('note', '')} Мотивы: {i.get('traditionTitle', '').lower()}; использовано {len(i.get('used', []))} элементов датасета."
    return {'text': text.strip(), 'basis': 'saved_recipe', 'claimType': 'render_recipe_fact', 'schemaVersion': 'tp-description-schema/1.0.0',
            'templateVersion': VERSION, 'facts': {'v3': recipe.get('v3'), 'used': i.get('used', [])}, 'evidence': [],
            'culturalNote': recipe.get('culturalNote')}
