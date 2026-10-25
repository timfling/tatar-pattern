import hashlib
import threading
import time
from collections import OrderedDict
from pathlib import Path
from PIL import Image
from .errors import APIError

MOTIFS = dict(tulip='тюльпан',bud='бутон',palmette='пальметта',vine='завиток',border='кайма',trefoil='трилистник',almond='миндаль',horn='бараний рог')

# Only file validation is cached. SQL approval/provenance is read on every call.
# stat identity + expected SHA invalidates a changed file/DB hash immediately;
# TTL bounds revalidation even for an unchanged stat. Restart or this function
# explicitly invalidates all entries after an operator catalog replacement.
_verified=OrderedDict()
_cache_lock=threading.Lock()
_verification_slots=threading.BoundedSemaphore(2)
_cache_epoch=0
CACHE_SECONDS=60
CACHE_ENTRIES=512
MAX_CATALOG_FILE_BYTES=32*1024*1024


def invalidate_catalog_cache():
    global _cache_epoch
    with _cache_lock:
        _cache_epoch+=1
        _verified.clear()


def _identity(path):
    stat=path.stat()
    if not path.is_file() or stat.st_size>MAX_CATALOG_FILE_BYTES:
        raise ValueError('Catalog file unavailable or too large')
    return (stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)


def _verify(path,expected,kind):
    identity=_identity(path)
    key=(path,identity,expected,kind)
    with _cache_lock:
        epoch=_cache_epoch
        cached=_verified.get(key)
        if cached and time.monotonic()-cached[0]<CACHE_SECONDS:
            _verified.move_to_end(key)
            return cached[1]
    if not _verification_slots.acquire(blocking=False):
        raise APIError(503,'CATALOG_BUSY','Проверка каталога занята. Повторите позже.')
    try:
        try:
            if kind=='png':
                digest=inspect_png(path)
            else:
                with path.open('rb') as stream:
                    digest=hashlib.file_digest(stream,'sha256').hexdigest()
            valid=(not expected or digest==expected) and _identity(path)==identity
        except (OSError,ValueError):
            valid=False
        with _cache_lock:
            if epoch==_cache_epoch:
                _verified[key]=(time.monotonic(),valid)
                _verified.move_to_end(key)
                while len(_verified)>CACHE_ENTRIES:
                    _verified.popitem(last=False)
        return valid
    finally:
        _verification_slots.release()


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


def catalog(conn, settings, element_codes=None):
    query='SELECT * FROM approved_element_files WHERE (%s OR NOT is_fixture)'
    params=[settings.allow_fixtures]
    if element_codes is not None:
        query+=' AND code = ANY(%s)'
        params.append(list(element_codes))
    rows = conn.execute(query+' ORDER BY code,file_id',params).fetchall()
    items = {}
    for row in rows:
        if row.get('local_use_approved') and not settings.local_catalog and not row.get('public_use_approved'):
            continue
        if row['code'] in items:
            continue
        try:
            path = safe_path(settings.storage_root, row['path'])
            source = safe_path(settings.storage_root, row['source_path'])
            if not _verify(path,row['content_sha256'],'png'):
                continue
            if not _verify(source,row.get('source_sha256'),'source'):
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
