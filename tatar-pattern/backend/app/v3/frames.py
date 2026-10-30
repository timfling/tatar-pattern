"""Рамки и выкладка полосовых мотивов."""
import math
from .core import ELEMENTS, dir_of

FRAMES = {'none': 'Без рамки', 'line': 'Тонкая рамка', 'kaima': 'Орнаментальная кайма'}


def tile_strip(sc, code, a, b, thickness, z=3, coff=0):
    """Выкладывает полосовой мотив вдоль отрезка a→b; thickness — толщина полосы."""
    e = ELEMENTS[code]; w, h = e['size']
    horizontal_src = w >= h
    long_, short = max(w, h), min(w, h)
    length = math.dist(a, b)
    seg = thickness * long_ / short
    count = max(1, math.ceil(length / seg))
    size = length / count * 1.01
    d_line = dir_of(b[0] - a[0], b[1] - a[1])
    src_axis = 90 if horizontal_src else 0
    base = e['angle'] if e['angle'] is not None else src_axis
    for i in range(count):
        t = (i + 0.5) / count
        p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        sc.sprite(code, size, p, d=d_line + (base - src_axis), z=z, coff=coff)


def draw_frame(sc, kind, m, box, D):
    """Рисует рамку и возвращает внутреннюю рабочую область."""
    x0, y0, x1, y1 = box; u = min(x1 - x0, y1 - y0)
    if kind == 'line':
        g = u * 0.03
        sc.rect((x0 + g, y0 + g, x1 - g, y1 - g), u * 0.004)
        sc.rect((x0 + g * 1.5, y0 + g * 1.5, x1 - g * 1.5, y1 - g * 1.5), u * 0.0018)
        for cx, cy in ((x0 + g, y0 + g), (x1 - g, y0 + g), (x0 + g, y1 - g), (x1 - g, y1 - g)):
            sc.dot((cx, cy), u * 0.008, z=4)
        return (x0 + g * 2.4, y0 + g * 2.4, x1 - g * 2.4, y1 - g * 2.4)
    if kind == 'kaima':
        g = u * 0.025; bw = u * 0.07
        strip = m.one(['strip'])
        cornr = m.one(['rosette', 'geo', 'flower'])
        ox0, oy0, ox1, oy1 = x0 + g, y0 + g, x1 - g, y1 - g
        ix0, iy0, ix1, iy1 = ox0 + bw, oy0 + bw, ox1 - bw, oy1 - bw
        sc.rect((ox0, oy0, ox1, oy1), u * 0.003)
        sc.rect((ix0, iy0, ix1, iy1), u * 0.003)
        th = bw * 0.60
        tile_strip(sc, strip, (ix0, oy0 + bw / 2), (ix1, oy0 + bw / 2), th)
        tile_strip(sc, strip, (ix0, oy1 - bw / 2), (ix1, oy1 - bw / 2), th)
        tile_strip(sc, strip, (ox0 + bw / 2, iy0), (ox0 + bw / 2, iy1), th)
        tile_strip(sc, strip, (ox1 - bw / 2, iy0), (ox1 - bw / 2, iy1), th)
        for cx, cy in ((ox0 + bw / 2, oy0 + bw / 2), (ox1 - bw / 2, oy0 + bw / 2), (ox0 + bw / 2, oy1 - bw / 2), (ox1 - bw / 2, oy1 - bw / 2)):
            sc.sprite(cornr, bw * 0.95, (cx, cy), z=5)
        gi = u * 0.03
        return (ix0 + gi, iy0 + gi, ix1 - gi, iy1 - gi)
    return box
