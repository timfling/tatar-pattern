"""Каркасы композиций. Каждая функция получает сцену, подборщик мотивов, rng,
рабочую область box=(x0,y0,x1,y1) и насыщенность D (1..3)."""
import math
from .core import ELEMENTS, at, bezier, dir_of, spiral, vec

COMPOSITIONS = {
    'bouquet': {'title': 'Букет', 'hint': 'Симметричный куст из одной точки', 'prefer': ['embroidery', 'gold', 'shamail'],
                'note': 'Симметричный куст-букет, растущий из одной точки, — одна из главных схем татарской вышивки и золотного шитья (калфаки, намазлыки, нагрудники).'},
    'rosette': {'title': 'Розетка', 'hint': 'Медальон с кольцами вокруг центра', 'prefer': ['ceramics', 'jewelry', 'embroidery', 'gold'],
                'note': 'Розетка-медальон с лучевым построением встречается в керамике, ювелирном деле, на тюбетейках и в вышивке.'},
    'vine': {'title': 'Кайма-лоза', 'hint': 'Вьющийся стебель, цветы по очереди', 'prefer': ['embroidery', 'gold'],
             'note': 'Волнистый стебель с цветами, чередующимися сверху и снизу, — классическая кайма полотенец, подолов, поясов и рукавов.'},
    'towel': {'title': 'Полотенце', 'hint': 'Полосы: широкая и узкие каймы', 'prefer': ['weaving'],
              'note': 'Чередование широкой узорной полосы и узких кайм — принцип оформления концов тканых браных полотенец.'},
    'corner': {'title': 'Платок', 'hint': 'Центр и ветви из углов', 'prefer': ['shamail', 'embroidery', 'gold'],
               'note': 'Центральный медальон и ветви, растущие из углов, — схема платков, покрывал и рамок шамаилей.'},
    'pattern': {'title': 'Бесшовный узор', 'hint': 'Плитка, которая стыкуется без шва', 'prefer': ['embroidery', 'gold', 'ceramics', 'weaving'],
                'note': 'Сетка из волнистых стеблей (ячейки-«луковицы») с мотивами в центре ячеек — принцип узорных тканей. Плитка стыкуется без шва.'},
}

FLOWERS = ['flower', 'rosette']


def directional(code):
    """У мотива есть «ось роста» (тюльпан, пальметта, лист) — его можно направлять по стеблю."""
    e = ELEMENTS[code]
    return e['angle'] is not None and e['symmetry'] != 'approx_radial'


def place_flower(sc, code, size, pos, grow, **kw):
    sc.sprite(code, size, pos, d=grow if directional(code) else None, **kw)


def leaf_on(sc, code, size, pos, d, **kw):
    """Лист крепится основанием к стеблю и растёт в направлении d."""
    sc.sprite(code, size, pos, d=d, anchor='attach', **kw)


# ------------------------------------------------------------ Букет

def bouquet(sc, m, rng, box, D, mirror='x'):
    x0, y0, x1, y1 = box; cw, ch = x1 - x0, y1 - y0
    ax = (x0 + x1) / 2; sc.ax = ax
    Hb = min(ch, cw * 1.25) * 0.96
    top = y0 + (ch - Hb) / 2; bottom = top + Hb
    hw = min(cw * 0.47, Hb * 0.56)
    w = Hb * 0.009
    hero = m.hero(['flower', 'rosette', 'palmette'])
    flowers = m.pool(FLOWERS, 3, avoid=(hero,))
    tulips = m.pool(['palmette'], 2, avoid=(hero,))
    leaves = m.pool(['leaf'], 3)
    hs = Hb * {1: 0.30, 2: 0.28, 3: 0.26}[D]
    hy = top + hs * 0.55
    root = (ax, bottom - Hb * 0.07)
    stem = bezier(root, (ax, root[1] - Hb * 0.25), (ax, hy + Hb * 0.25), (ax, hy))
    sc.stem(stem, w * 1.6, w * 1.1)
    place_flower(sc, hero, hs, (ax, hy), 0, z=7)
    # основание — пальметта-«чаша»; из неё расходятся прикорневые листья
    base_el = tulips[1]
    sc.sprite(base_el, Hb * 0.13, (ax, bottom), d=0, anchor='attach' if ELEMENTS[base_el]['attach'] else 'center', z=6, coff=2)
    leaf_on(sc, leaves[0], Hb * 0.13, (ax - Hb * 0.015, root[1]), -55, z=2, mirror=mirror, coff=1)
    # боковые ветви — по овалу вокруг центра
    n = {1: 2, 2: 3, 3: 4}[D]
    O = (ax, top + Hb * 0.47); rx, ry = hw * 0.80, Hb * 0.36
    for i in range(n):
        th = 40 + 80 * i / max(1, n - 1) + rng.uniform(-3, 3)
        E = (O[0] - math.sin(math.radians(th)) * rx, O[1] - math.cos(math.radians(th)) * ry)
        fs = hs * (0.66 if i % 2 == 0 else 0.56) * (0.88 if D == 3 else 1)
        S, _ = at(stem, 0.18 + 0.55 * (n - 1 - i) / max(1, n - 1))
        dx = abs(S[0] - E[0])
        pts = bezier(S, (S[0] - dx * 0.30, S[1] - Hb * 0.05), (E[0] + dx * 0.25, E[1] + Hb * 0.12), E)
        sc.stem(pts, w * 1.15, w * 0.75, mirror=mirror)
        _, td = at(pts, 0.96)
        fl = tulips[0] if (i == n - 1 and D >= 2) else flowers[i % len(flowers)]
        place_flower(sc, fl, fs, E, td, z=6, mirror=mirror, coff=1 + i)
        P, pd = at(pts, 0.40)
        leaf_on(sc, leaves[0], fs * 0.48, P, pd + 75, z=2, mirror=mirror, coff=i)
        if D >= 2:
            Q, qd = at(pts, 0.62)
            leaf_on(sc, leaves[1 if D == 3 else 0], fs * 0.40, Q, qd - 70, z=2, mirror=mirror, coff=i + 1)
        if D >= 2:
            Q, qd = at(pts, 0.78)
            sc.stem(spiral(Q, qd - 50, fs * 0.20, sign=-1), w * 0.7, w * 0.35, mirror=mirror)
    # бутоны на коротких отводках
    if D >= 2:
        buds = m.pool(FLOWERS, 2, avoid=(hero,))
        for j in range(D - 1):
            S, _ = at(stem, 0.42 + 0.22 * j)
            E = (S[0] - hw * (0.22 - 0.05 * j), S[1] - Hb * 0.05)
            pts = bezier(S, (S[0] - hw * 0.04, S[1]), (E[0] + hw * 0.06, E[1] + Hb * 0.03), E)
            sc.stem(pts, w * 0.8, w * 0.5, mirror=mirror)
            place_flower(sc, buds[j % 2], hs * 0.27, E, at(pts, .95)[1], z=5, mirror=mirror, coff=3 + j)
    # навершие: три «зерна» над главным цветком
    for k, dd in enumerate((-30, 0, 30)):
        px, py = vec(dd, hs * 0.62)
        sc.dot((ax + px, hy + py), Hb * (0.007 if dd else 0.009), z=4)
    if D == 3:
        for k in range(4):
            px, py = vec(-118 + k * 22, 1)
            sc.dot((O[0] + px * rx * 1.18, O[1] + py * ry * 1.18), Hb * 0.005, z=4, mirror=mirror)
    for k, code in enumerate(m.extras()[:3]):
        sc.sprite(code, hs * 0.38, (ax - hw * (0.92 - 0.14 * k), bottom - Hb * (0.22 + 0.13 * k)), z=4, mirror=mirror, coff=k)


# ------------------------------------------------------------ Розетка

def rosette(sc, m, rng, box, D, R=None, hero=None):
    x0, y0, x1, y1 = box; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    R = R or min(x1 - x0, y1 - y0) * 0.48
    w = R * 0.012
    hero = hero or m.hero(['rosette', 'flower', 'geo'])
    ray = m.one(['palmette', 'leaf'])
    ring_fl = m.pool(FLOWERS, 2, avoid=(hero,))
    leaf = m.one(['leaf'], avoid=(ray,))
    N = {1: 6, 2: 8, 3: 10}[D]
    sc.sprite(hero, R * 0.52, (cx, cy), z=7)
    # лучи — направлены наружу, основанием к центру
    for i in range(N):
        d = i * 360 / N
        px, py = vec(d, R * 0.25)
        sc.sprite(ray, R * 0.30, (cx + px, cy + py), d=d, anchor='attach' if ELEMENTS[ray]['attach'] else 'center', z=5, coff=1)
    rs = R * 0.66
    sc.ring((cx, cy), rs, w, z=1)
    for i in range(N):
        d = i * 360 / N + 180 / N
        px, py = vec(d, rs)
        fl = ring_fl[i % len(ring_fl)]
        place_flower(sc, fl, R * 0.24, (cx + px, cy + py), d, z=6, coff=2 + i % 2, spin=d if not directional(fl) else 0)
        for sgn in (-1, 1):
            dd = d + sgn * 180 / N * 0.62
            qx, qy = vec(dd, rs)
            leaf_on(sc, leaf, R * 0.17, (cx + qx, cy + qy), dd + 70 * sgn, z=3, coff=i)
    if D >= 2:
        sc.ring((cx, cy), R * 0.93, w * 0.9, z=1, dots=N * 7)
        sc.ring((cx, cy), R * 0.985, w * 0.8, z=1)
        small = m.one(FLOWERS, avoid=(hero,))
        for i in range(N):
            px, py = vec(i * 360 / N, R * 0.86)
            sc.sprite(small, R * 0.13, (cx + px, cy + py), z=4, coff=3)
    if D == 3:
        for i in range(N):
            d = i * 360 / N + 180 / N
            px, py = vec(d, R * 0.40)
            sc.stem(spiral((cx + px, cy + py), d + 70, R * 0.055, sign=1), w, w * 0.4, z=2)
            sc.stem(spiral((cx + px, cy + py), d - 70, R * 0.055, sign=-1), w, w * 0.4, z=2)
    for k, code in enumerate(m.extras()[:2]):
        for i in range(4):
            px, py = vec(45 + i * 90, R * (1.1 + 0.12 * k))
            sc.sprite(code, R * 0.16, (cx + px, cy + py), z=5, coff=k)


# ------------------------------------------------------------ Кайма-лоза

def vine_band(sc, m, rng, box, D, phase=0.0, flowers=None, leaves=None, coff=0):
    x0, y0, x1, y1 = box; bw, bh = x1 - x0, y1 - y0; cy = (y0 + y1) / 2
    w = bh * 0.028
    k = max(1, round(bw / (bh * 2.1)))
    P = bw / k; A = bh * 0.14
    f = lambda x: cy + A * math.sin(2 * math.pi * (x - x0) / P + phase)
    sc.stem([(x0 + bw * i / 300, f(x0 + bw * i / 300)) for i in range(301)], w, w)
    fs = bh * {1: 0.52, 2: 0.54, 3: 0.50}[D]
    for j in range(2 * k):
        xc = x0 + (j + 0.25) * P / 2 + (phase / (2 * math.pi)) * 0
        yc = f(xc)
        side = 1 if yc < cy else -1  # стебель вверху -> цветок в нижней «чаше»
        S = (xc, yc)
        F = (xc + P * 0.14, cy + side * bh * 0.20)
        pts = bezier(S, (S[0] + P * 0.06, S[1] + side * bh * 0.02), (F[0] - P * 0.04, F[1] - side * bh * 0.10), F)
        sc.stem(pts, w * 0.8, w * 0.6)
        fl = flowers[j % len(flowers)]
        place_flower(sc, fl, fs, F, 180 if side > 0 else 0, z=6, coff=coff + j % 3)
        # лист на противоположной стороне стебля
        Lx = xc + P * 0.30; Ly = f(Lx)
        ld = dir_of(1, (f(Lx + 1) - f(Lx - 1)) / 2)
        leaf_on(sc, leaves[j % len(leaves)], bh * 0.30, (Lx, Ly), ld - 60 * side, z=3, coff=coff + j)
        if D >= 2:
            sc.stem(spiral((xc - P * 0.06, f(xc - P * 0.06)), 0 if side > 0 else 180, bh * 0.07, sign=side), w * 0.6, w * 0.3)
        if D == 3:
            sc.dot((xc + P * 0.36, cy + side * bh * 0.30), bh * 0.018, z=4)
            sc.dot((xc + P * 0.40, cy + side * bh * 0.24), bh * 0.012, z=4)


def vine(sc, m, rng, box, D):
    x0, y0, x1, y1 = box; cw, ch = x1 - x0, y1 - y0
    rows = max(1, round(ch / (cw / 2.6)))
    flowers = m.pool(FLOWERS + ['palmette'], 3)
    leaves = m.pool(['leaf'], 2)
    edge = m.one(['strip'])
    rh = ch / rows
    for r in range(rows):
        by0 = y0 + r * rh; by1 = by0 + rh
        bh = rh * 0.92
        band = (x0, by0 + (rh - bh) / 2, x1, by0 + (rh + bh) / 2)
        fl = flowers if r % 2 == 0 else flowers[1:] + flowers[:1]
        vine_band(sc, m, rng, band, D, phase=math.pi * (r % 2), flowers=fl, leaves=leaves, coff=r)
        if r > 0 and D >= 2:
            tile = rh * 0.08
            from .frames import tile_strip
            tile_strip(sc, edge, (x0, by0), (x1, by0), tile, z=4)
        elif r > 0:
            sc.rect((x0, by0 - 1, x1, by0 + 1), rh * 0.004, z=1)
    for k, code in enumerate(m.extras()[:2]):
        for r in range(rows):
            sc.sprite(code, rh * 0.18, (x0 + cw * (0.25 + 0.5 * k), y0 + r * rh + rh * 0.5), z=7, coff=k)


# ------------------------------------------------------------ Полотенце

def towel(sc, m, rng, box, D):
    from .frames import tile_strip
    x0, y0, x1, y1 = box; cw, ch = x1 - x0, y1 - y0
    geo = m.pool(['geo'], 3)
    strips = m.pool(['strip'], 3)
    small = m.one(['geo', 'rosette'], avoid=tuple(geo[:1]))
    cy = (y0 + y1) / 2
    main_h = min(ch * {1: 0.30, 2: 0.26, 3: 0.22}[D], cw / 3.2)
    n = max(2, round(cw / (main_h * 1.25)))
    step = cw / n
    for i in range(n):
        code = geo[0] if i % 2 == 0 or D == 1 else geo[1]
        sc.sprite(code, main_h * 0.92, (x0 + (i + 0.5) * step, cy), z=5, coff=i % 2)
        if D >= 2 and i < n - 1:
            sc.sprite(small, main_h * 0.30, (x0 + (i + 1) * step, cy), z=5, coff=2)
    sc.rect((x0, cy - main_h * 0.58, x1, cy + main_h * 0.58), main_h * 0.012, z=1)
    y = main_h * 0.58
    layers = {1: 1, 2: 2, 3: 3}[D]
    for L in range(layers):
        th = main_h * (0.22 if L == 0 else 0.15)
        gap = main_h * 0.10
        y += gap + th / 2
        for sgn in (-1, 1):
            yy = cy + sgn * y
            if yy - th / 2 < y0 or yy + th / 2 > y1:
                continue
            tile_strip(sc, strips[L % len(strips)], (x0, yy), (x1, yy), th, z=4, coff=L)
        y += th / 2
        if L == layers - 1 and D >= 2:
            row = m.one(['geo', 'flower', 'rosette'], avoid=tuple(geo))
            yrow = y + main_h * 0.30
            cnt = max(3, round(cw / (main_h * 0.55)))
            for sgn in (-1, 1):
                yy = cy + sgn * yrow
                if yy - main_h * 0.2 < y0 or yy + main_h * 0.2 > y1:
                    continue
                for i in range(cnt):
                    sc.sprite(row, main_h * 0.34, (x0 + (i + 0.5) * cw / cnt, yy), z=4, coff=1)
    for k, code in enumerate(m.extras()[:2]):
        sc.sprite(code, main_h * 0.5, (x0 + cw * (0.2 + 0.6 * k), cy), z=6)


# ------------------------------------------------------------ Платок

def corner(sc, m, rng, box, D):
    x0, y0, x1, y1 = box; cw, ch = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; sc.ax, sc.ay = cx, cy
    u = min(cw, ch); w = u * 0.006
    hero = m.hero(['rosette', 'flower'])
    rosette(sc, m, rng, (cx - u * 0.2, cy - u * 0.2, cx + u * 0.2, cy + u * 0.2), max(1, D - 1), R=u * 0.19, hero=hero)
    flowers = m.pool(FLOWERS + ['palmette'], 3, avoid=(hero,))
    leaves = m.pool(['leaf'], 2)
    # угловая ветвь (верхний левый угол) — растёт по диагонали к центру; зеркалится на все 4 угла
    C = (x0 + u * 0.03, y0 + u * 0.03)
    T = (x0 + cw * 0.30, y0 + ch * 0.30)
    main = bezier(C, (C[0] + u * 0.16, C[1] + u * 0.02), (T[0] - u * 0.04, T[1] - u * 0.14), T)
    sc.stem(main, w * 1.6, w, mirror='xy')
    place_flower(sc, flowers[0], u * 0.15, T, 135, z=6, mirror='xy', coff=1)
    sc.sprite(m.one(['corner', 'palmette']), u * 0.13, C, d=135, anchor='attach', z=6, mirror='xy', coff=2)
    nb = {1: 1, 2: 2, 3: 3}[D]
    for j in range(nb):
        t = 0.35 + 0.22 * j
        S, sd = at(main, t)
        for sgn in (-1, 1):
            E = (S[0] + vec(sd + sgn * 55)[0] * u * 0.10, S[1] + vec(sd + sgn * 55)[1] * u * 0.10)
            pts = bezier(S, (S[0] + vec(sd)[0] * u * 0.03, S[1] + vec(sd)[1] * u * 0.03), E, E)
            sc.stem(pts, w, w * 0.6, mirror='xy')
            if (j + (sgn > 0)) % 2 == 0:
                place_flower(sc, flowers[1 + (j % 2)], u * 0.075, E, sd + sgn * 55, z=5, mirror='xy', coff=2 + j)
            else:
                leaf_on(sc, leaves[j % 2], u * 0.085, S, sd + sgn * 60, z=3, mirror='xy', coff=j)
    # средины сторон — малые пальметты, растущие к центру
    if D >= 2:
        mid = m.one(['palmette', 'flower'], avoid=(hero,))
        for pos, d in (((cx, y0 + u * 0.06), 180), ((cx, y1 - u * 0.06), 0), ((x0 + u * 0.06, cy), 90), ((x1 - u * 0.06, cy), -90)):
            sc.sprite(mid, u * 0.09, pos, d=d if directional(mid) else None, z=5, coff=3)
    if D == 3:
        sc.ring((cx, cy), u * 0.27, w * 0.8, z=1, dots=72)
    for k, code in enumerate(m.extras()[:2]):
        sc.sprite(code, u * 0.08, (x0 + cw * 0.22, cy - u * 0.12 * (1 - 2 * k)), z=5, mirror='x', coff=k)


# ------------------------------------------------------------ Бесшовный узор (плитка)

def pattern(sc, m, rng, box, D):
    """Ячейки-«луковицы» из двух волнистых стеблей. Плитка W×H стыкуется без шва (sc.wrap=True)."""
    W, H = sc.W, sc.H; u = min(W, H); w = u * 0.010
    A = m.hero(FLOWERS + ['palmette', 'geo'])
    B = m.one(FLOWERS + ['palmette'], avoid=(A,))
    knot = m.one(['rosette', 'flower', 'geo'], avoid=(A, B))
    leaves = m.pool(['leaf'], 2)
    amp = W / 4
    for c, s in ((W / 4, 1), (3 * W / 4, -1)):
        pts = [(c + s * amp * math.sin(2 * math.pi * i / 200), H * i / 200) for i in range(201)]
        sc.stem(pts, w, w)
        if D >= 2:
            for t in (0.12, 0.38, 0.62, 0.88):
                P, pd = at(pts, t)
                leaf_on(sc, leaves[int(t * 4) % 2], u * 0.13, P, pd + (70 if (t < 0.5) == (s > 0) else -70), z=3, coff=1)
    big = u * {1: 0.40, 2: 0.36, 3: 0.33}[D]
    place_flower(sc, A, big, (W / 2, 3 * H / 4), 0, z=6)
    place_flower(sc, B, big * 0.86, (0, H / 4), 0, z=6, coff=1)
    for pos in ((W / 2, H / 4), (0, 3 * H / 4)):
        sc.sprite(knot, u * 0.13, pos, z=7, coff=2)
    if D == 3:
        for pos in ((W / 4, H / 2), (3 * W / 4, H / 2), (W / 4, 0), (3 * W / 4, 0)):
            sc.dot(pos, u * 0.012, z=4)
    for k, code in enumerate(m.extras()[:2]):
        sc.sprite(code, u * 0.12, (W / 4 + k * W / 2, H / 2 if k == 0 else 0), z=6, coff=k)


BUILDERS = {'bouquet': bouquet, 'rosette': rosette, 'vine': vine, 'towel': towel, 'corner': corner, 'pattern': pattern}
