"""Татар Паттерн v3 — ядро: справочники, перекраска, сцена, подбор мотивов."""
import json
import math
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageColor, ImageDraw, ImageOps

HERE = Path(__file__).resolve().parent
ELEMENTS = {e['code']: e for e in json.loads((HERE / 'elements.json').read_text())}
MAX_SIDE = 640
# code -> путь к принятому PNG каталога (заполняет backend из approved_element_files).
SOURCES: dict = {}


def set_sources(mapping):
    if mapping != SOURCES:
        SOURCES.clear(); SOURCES.update(mapping)
        base_sprite.cache_clear(); colored.cache_clear(); transformed.cache_clear()
ALL = list(ELEMENTS)
SS = 2  # суперсэмплинг для линий

# Автоподбор не берёт фотофактурные/бледные элементы; вручную их выбрать можно.
EXCLUDE_AUTO = {'TP-E-030', 'TP-E-031', 'TP-E-053', 'TP-E-116', 'TP-E-119', 'TP-E-011', 'TP-E-072', 'TP-E-073', 'TP-E-097', 'TP-E-060', 'TP-E-044', 'TP-E-057'}

CATEGORY_LABELS = {
    'flower': 'Цветы', 'rosette': 'Розетки', 'palmette': 'Пальметты и тюльпаны', 'leaf': 'Листья',
    'branch': 'Ветви', 'curl': 'Завитки', 'strip': 'Каймы', 'geo': 'Геометрия', 'pendant': 'Подвески', 'corner': 'Угловые',
}
TRADITIONS = {
    'auto': 'Любая (подберём сами)', 'embroidery': 'Вышивка', 'gold': 'Золотное шитьё', 'ceramics': 'Керамика',
    'weaving': 'Браное ткачество', 'jewelry': 'Ювелирное искусство', 'shamail': 'Шамаиль и книга',
}
PALETTES = {
    'original': {'name': 'Исходные цвета', 'bg': '#f1e9da', 'stem': None},
    'tambour': {'name': 'Тамбурная вышивка', 'bg': '#f3ebdc', 'ink': '#2a2433', 'light': '#f8f2e7', 'stem': '#3d5a3a',
                'colors': ['#b3302d', '#3d7a4c', '#2f5b8f', '#d6a03c', '#c4587a']},
    'kalfak': {'name': 'Калфак: золото на бархате', 'bg': '#5b1122', 'ink': '#6e3f17', 'light': '#fbe7b0', 'stem': '#d9a443',
               'colors': ['#d9a443', '#f0cf7e', '#b8802e', '#e9b95c']},
    'towel': {'name': 'Браное полотенце', 'bg': '#f5f0e6', 'ink': '#4a0f12', 'light': '#fbf7ef', 'stem': '#9c1f26',
              'colors': ['#b2232b', '#7c1a1f', '#d9473f']},
    'ceramics': {'name': 'Синяя керамика', 'bg': '#f4f1ea', 'ink': '#14275e', 'light': '#fbfaf6', 'stem': '#1f45a0',
                 'colors': ['#1f45a0', '#4f7fc8', '#2c5fae', '#8fb0de']},
    'emerald': {'name': 'Изумруд и золото', 'bg': '#123d32', 'ink': '#0a2a22', 'light': '#f6ead0', 'stem': '#d8b25a',
                'colors': ['#d8b25a', '#e2725b', '#f1e2bf', '#c9893f']},
    'shamail': {'name': 'Шамаиль: ночь и золото', 'bg': '#17161d', 'ink': '#0b0a10', 'light': '#f3e6c4', 'stem': '#e0b456',
                'colors': ['#e0b456', '#3a78c9', '#cf4a3c', '#5aa06e']},
    'terracotta': {'name': 'Терракота', 'bg': '#efe3d3', 'ink': '#4a2a1c', 'light': '#fbf3e8', 'stem': '#6b4a33',
                   'colors': ['#c0603d', '#e0a35a', '#7a8f6a', '#a14a3a']},
}
BACKGROUNDS = {'palette': 'Как в палитре', 'light': '#f1e9da', 'white': '#ffffff', 'green': '#1f4a3c',
               'burgundy': '#5a1a24', 'dark': '#1d1b1a', 'transparent': 'Прозрачный'}
FORMATS = {
    'square': ('Квадрат 1:1', 1600, 1600), 'portrait': ('Постер 3:4', 1200, 1600), 'landscape': ('Альбом 4:3', 1600, 1200),
    'story': ('Сторис 9:16', 1080, 1920), 'wide': ('Обложка 16:9', 1920, 1080), 'band': ('Лента 3:1', 2400, 800),
}


# ------------------------------------------------------------ geometry helpers

def rgb(c):
    return ImageColor.getrgb(c)[:3] if isinstance(c, str) else tuple(c[:3])


def lum(c):
    r, g, b = rgb(c)
    return (0.3 * r + 0.59 * g + 0.11 * b) / 255


def dir_of(dx, dy):
    """Направление в градусах: 0 — вверх, по часовой стрелке."""
    return math.degrees(math.atan2(dx, -dy))


def vec(d, r=1.0):
    a = math.radians(d)
    return (math.sin(a) * r, -math.cos(a) * r)


def bezier(p0, p1, p2, p3, n=48):
    out = []
    for i in range(n + 1):
        t = i / n; u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return out


def at(pts, t):
    """Точка и направление касательной на ломаной (t — доля индекса)."""
    i = min(len(pts) - 2, max(0, int(t * (len(pts) - 1))))
    p, q = pts[i], pts[i + 1]
    return p, dir_of(q[0] - p[0], q[1] - p[1])


def spiral(start, d, size, turns=1.2, sign=1, n=56):
    """Завиток: выходит по направлению d и закручивается внутрь."""
    pts = [start]; x, y = start; step = size * 2.4 / n
    for i in range(n):
        t = i / n
        d += sign * turns * 360 / n * (0.6 + 1.8 * t)
        dx, dy = vec(d, step * (1 - 0.7 * t))
        x += dx; y += dy; pts.append((x, y))
    return pts


def paste(canvas, img, x, y):
    W, H = canvas.size; w, h = img.size
    l, t = max(0, x), max(0, y); r, b = min(W, x + w), min(H, y + h)
    if r > l and b > t:
        canvas.alpha_composite(img.crop((l - x, t - y, r - x, b - y)), (l, t))


# ------------------------------------------------------------ sprites

@lru_cache(maxsize=256)
def base_sprite(code):
    """Тот же способ, что в prototype-v3/build_cache.py: обрезка по альфе и сторона 640px."""
    path = SOURCES.get(code)
    if not path:
        raise KeyError(f'Нет файла элемента {code} в каталоге')
    with Image.open(path) as src:
        im = src.convert('RGBA')
    im = im.crop(im.getchannel('A').getbbox())
    im.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    return im


@lru_cache(maxsize=512)
def colored(code, pal_key, coff):
    """Перекраска: цвета мотива упорядочиваются по светлоте и заменяются цветами палитры.
    Самый тёмный -> контур, самый светлый -> светлое поле, остальные -> акценты."""
    im = base_sprite(code)
    if pal_key == 'original':
        return im
    pal = PALETTES[pal_key]
    alpha = im.getchannel('A')
    flat = Image.new('RGB', im.size, tuple(ELEMENTS[code]['ink']))
    flat.paste(im.convert('RGB'), mask=alpha.point(lambda v: 255 if v > 100 else 0))
    q = flat.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
    raw = q.getpalette()[:18]
    used = sorted({i for _, i in q.getcolors()})
    order = sorted(used, key=lambda i: lum(raw[3 * i:3 * i + 3]))
    new = list(raw) + [0] * (768 - len(raw))
    cols = pal['colors']
    for rank, idx in enumerate(order):
        if rank == 0 and len(order) > 1:
            c = rgb(pal['ink'])
        elif rank == len(order) - 1 and lum(raw[3 * idx:3 * idx + 3]) > 0.72:
            c = rgb(pal['light'])
        else:
            c = rgb(cols[(rank - 1 + coff) % len(cols)])
        new[3 * idx:3 * idx + 3] = c
    q.putpalette(new)
    out = q.convert('RGB'); out.putalpha(alpha)
    return out


@lru_cache(maxsize=4096)
def transformed(code, pal_key, coff, size, flip, rot):
    im = colored(code, pal_key, coff)
    w, h = im.size; k = size / max(w, h)
    im = im.resize((max(1, round(w * k)), max(1, round(h * k))), Image.Resampling.LANCZOS)
    if flip:
        im = ImageOps.mirror(im)
    if rot % 360:
        im = im.rotate(-rot, resample=Image.Resampling.BICUBIC, expand=True)
    return im


# ------------------------------------------------------------ scene

class Scene:
    """Список операций рисования с z-слоями и зеркалированием."""

    def __init__(self, W, H, pal_key, stem_color, wrap=False):
        self.W, self.H = W, H; self.pal_key = pal_key; self.stem_color = rgb(stem_color)
        self.ops = []; self.wrap = wrap; self.ax = W / 2; self.ay = H / 2; self.used = []

    def _mirrors(self, x, y, d, mirror):
        out = [(x, y, d, False)]
        if mirror in ('x', 'xy'):
            out += [(2 * self.ax - x, y, -d, not f) for x, y, d, f in out]
        if mirror in ('y', 'xy'):
            out += [(x, 2 * self.ay - y, 180 - d, not f) for x, y, d, f in out]
        return out

    def sprite(self, code, size, pos, d=None, anchor='center', z=3, mirror=None, coff=0, spin=0):
        """d — куда должна смотреть «ось роста» мотива (0 — вверх). None — как в исходнике."""
        e = ELEMENTS[code]
        if code not in self.used:
            self.used.append(code)
        base = e['angle'] if e['angle'] is not None else 0
        want = d if d is not None else base + spin
        for x, y, dd, flip in self._mirrors(pos[0], pos[1], want, mirror):
            a = -base if flip else base
            rot = round((dd - a) / 2) * 2
            self.ops.append((z, 'sprite', (code, max(8, round(size)), flip, rot, x, y, anchor, coff)))

    def stem(self, pts, w0, w1=None, color=None, z=1, mirror=None):
        w1 = w0 * 0.55 if w1 is None else w1
        c = rgb(color) if color else self.stem_color
        variants = [pts]
        if mirror in ('x', 'xy'):
            variants += [[(2 * self.ax - x, y) for x, y in p] for p in variants]
        if mirror in ('y', 'xy'):
            variants += [[(x, 2 * self.ay - y) for x, y in p] for p in variants]
        for p in variants:
            self.ops.append((z, 'stem', (p, w0, w1, c)))

    def dot(self, pos, r, color=None, z=4, mirror=None):
        c = rgb(color) if color else self.stem_color
        for x, y, _, _ in self._mirrors(pos[0], pos[1], 0, mirror):
            self.ops.append((z, 'dot', (x, y, r, c)))

    def ring(self, center, r, width, color=None, z=0, dots=0):
        self.ops.append((z, 'ring', (center, r, width, rgb(color) if color else self.stem_color, dots)))

    def rect(self, box, width, color=None, z=0):
        self.ops.append((z, 'rect', (box, width, rgb(color) if color else self.stem_color)))

    def _offsets(self):
        if not self.wrap:
            return [(0, 0)]
        return [(dx, dy) for dx in (-self.W, 0, self.W) for dy in (-self.H, 0, self.H)]

    def render(self, bg):
        canvas = Image.new('RGBA', (self.W, self.H), bg)
        layer = None

        def flush():
            nonlocal layer
            if layer is not None:
                canvas.alpha_composite(layer.resize((self.W, self.H), Image.Resampling.LANCZOS))
                layer = None

        for z, kind, data in sorted(self.ops, key=lambda o: o[0]):
            if kind == 'sprite':
                flush()
                code, size, flip, rot, x, y, anchor, coff = data
                im = transformed(code, self.pal_key, coff, size, flip, rot)
                e = ELEMENTS[code]
                uv = e['attach'] if anchor == 'attach' and e['attach'] else (0.5, 0.5)
                bw, bh = e['size']; k = size / max(bw, bh); w, h = bw * k, bh * k
                u = 1 - uv[0] if flip else uv[0]
                px, py = u * w - w / 2, uv[1] * h - h / 2
                ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
                qx, qy = px * ca - py * sa, px * sa + py * ca
                left, top = round(x - im.width / 2 - qx), round(y - im.height / 2 - qy)
                for dx, dy in self._offsets():
                    paste(canvas, im, left + dx, top + dy)
                continue
            if layer is None:
                layer = Image.new('RGBA', (self.W * SS, self.H * SS), (0, 0, 0, 0))
            dr = ImageDraw.Draw(layer)
            for ox, oy in self._offsets():
                if kind == 'stem':
                    pts, w0, w1, c = data
                    sp = [((x + ox) * SS, (y + oy) * SS) for x, y in pts]
                    n = len(sp); chunks = max(1, min(10, n // 4))
                    for k in range(chunks):
                        a, b = k * (n - 1) // chunks, (k + 1) * (n - 1) // chunks
                        w = (w0 + (w1 - w0) * (k + 0.5) / chunks) * SS
                        dr.line(sp[a:b + 1], fill=c + (255,), width=max(1, round(w)), joint='curve')
                        r = w / 2; xx, yy = sp[b]
                        dr.ellipse((xx - r, yy - r, xx + r, yy + r), fill=c + (255,))
                elif kind == 'dot':
                    x, y, r, c = data
                    x, y, r = (x + ox) * SS, (y + oy) * SS, r * SS
                    dr.ellipse((x - r, y - r, x + r, y + r), fill=c + (255,))
                elif kind == 'ring' and (ox, oy) == (0, 0):
                    (cx, cy), r, w, c, dots = data
                    cx, cy, r = cx * SS, cy * SS, r * SS
                    if dots:
                        rr = w * SS * 0.9
                        for i in range(dots):
                            a = 2 * math.pi * i / dots
                            px, py = cx + r * math.cos(a), cy + r * math.sin(a)
                            dr.ellipse((px - rr, py - rr, px + rr, py + rr), fill=c + (255,))
                    else:
                        dr.ellipse((cx - r, cy - r, cx + r, cy + r), outline=c + (255,), width=max(1, round(w * SS)))
                elif kind == 'rect' and (ox, oy) == (0, 0):
                    box, w, c = data
                    dr.rectangle([v * SS for v in box], outline=c + (255,), width=max(1, round(w * SS)))
        flush()
        return canvas


# ------------------------------------------------------------ motif picking

class Motifs:
    """Подбор по ролям: сначала выбор пользователя, затем мотивы традиции, затем весь датасет.
    Никогда не отказывает."""

    def __init__(self, codes, tradition, rng, prefer):
        self.rng = rng
        self.chosen = [c for c in codes if c in ELEMENTS]
        if tradition not in TRADITIONS or tradition == 'auto':
            tradition = rng.choice(prefer)
        self.tradition = tradition
        self.trad = [c for c in ALL if tradition in ELEMENTS[c]['traditions'] and c not in EXCLUDE_AUTO]
        self.any = [c for c in ALL if c not in EXCLUDE_AUTO]
        self.taken = set()

    def pool(self, cats, n=1, avoid=()):
        cats = set(cats)
        for source, shuffle in ((self.chosen, False), (self.trad, True), (self.any, True)):
            p = [c for c in source if cats.intersection(ELEMENTS[c]['categories']) and c not in avoid]
            if p:
                if shuffle:
                    p = p[:]; self.rng.shuffle(p)
                out = [p[i % len(p)] for i in range(n)]
                self.taken.update(out)
                return out
        return [self.rng.choice(self.any) for _ in range(n)]

    def one(self, cats, avoid=()):
        return self.pool(cats, 1, avoid)[0]

    def hero(self, cats):
        """Главный мотив: первый выбранный пользователем, иначе — из традиции."""
        h = self.chosen[0] if self.chosen else self.one(cats)
        self.taken.add(h)
        return h

    def extras(self):
        return [c for c in self.chosen if c not in self.taken]
