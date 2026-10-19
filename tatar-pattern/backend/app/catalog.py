import hashlib
from pathlib import Path
from PIL import Image
from .errors import APIError

MOTIFS = dict(tulip='тюльпан',bud='бутон',palmette='пальметта',vine='завиток',border='кайма',trefoil='трилистник',almond='миндаль',horn='бараний рог')


def motif_key(label):
    return next((k for k,v in MOTIFS.items() if v==label), 'class-'+hashlib.sha256(label.encode()).hexdigest()[:16])


def safe_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError('Путь выходит за пределы хранилища')
    return path


def inspect_png(path):
    try:
        opened=Image.open(path)
    except Image.DecompressionBombError as exc:
        raise ValueError('Размер изображения превышает безопасный предел') from exc
    with opened as im:
        if im.format != 'PNG' or im.width > 4096 or im.height > 4096 or min(im.size)<16:
            raise ValueError('Нужен PNG размером 16–4096 px')
        im.load()
        rgba = im.convert('RGBA')
        alpha = rgba.getchannel('A')
        low, high = alpha.getextrema()
        if low == 255 or high == 0:
            raise ValueError('Элемент должен иметь прозрачный фон и видимый мотив')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def catalog(conn, settings):
    rows = conn.execute('SELECT * FROM approved_element_files WHERE (%s OR NOT is_fixture) ORDER BY code,file_id', (settings.allow_fixtures,)).fetchall()
    items = {}
    for row in rows:
        if row.get('local_use_approved') and not settings.local_catalog and not row.get('public_use_approved'):
            continue
        if row['code'] in items:
            continue
        try:
            path = safe_path(settings.storage_root, row['path'])
            source = safe_path(settings.storage_root, row['source_path'])
            if not source.is_file() or inspect_png(path) != row['content_sha256']:
                continue
            if row.get('source_sha256'):
                with source.open('rb') as stream:
                    if hashlib.file_digest(stream,'sha256').hexdigest()!=row['source_sha256']:
                        continue
        except (OSError, ValueError):
            continue
        row['local_path'] = path
        row['motif_key'] = motif_key(row['motif_class'])
        if row['motif_key']:
            items[row['code']] = row
    return list(items.values())


def selected_elements(conn, settings, motifs, element_codes=None):
    rows = catalog(conn, settings)
    if not rows:
        raise APIError(409,'CATALOG_EMPTY','Каталог пуст: загрузите разрешенные элементы после человеческой проверки.')
    picked = []
    missing = []
    for motif in (element_codes or motifs):
        match = next((r for r in rows if (r['code'] if element_codes else r['motif_key'])==motif), None)
        if match is None:
            missing.append(motif)
        else:
            picked.append(match)
    if missing:
        raise APIError(422,'MOTIFS_UNAVAILABLE','Для выбранных мотивов нет проверенных файлов.', {'motifs':missing})
    return picked
