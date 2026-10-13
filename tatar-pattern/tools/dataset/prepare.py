#!/usr/bin/env python3
"""
prepare.py — подготовка съёмочной локации к ИИ-разметке.

Что делает (для одной локации или для всех):
  1. RAW/JPG -> лёгкие JPG-прокси (sips, встроен в macOS; ничего ставить не нужно).
  2. Экспорт таблицы «<Локация> — Список обьектов.numbers» в CSV (через Numbers.app).
  3. manifest.csv — все кадры локации по порядку + kind (work/plate) по списку из Numbers.
  4. annotations.csv — заготовка для ИИ: уже заполнены кадр, kind и то, что ты
     вписал руками в Numbers. ИИ дозаполняет остальное.
  5. Контактные листы 3x3 (sheets/) — чтобы ИИ смотрел 9 кадров за один раз.

Запуск (из корня «Разработка»):
  python3 tatar-pattern/tools/dataset/prepare.py --location "01.09.2026/Кул шариф"
  python3 tatar-pattern/tools/dataset/prepare.py --all
  python3 tatar-pattern/tools/dataset/prepare.py --location "01.09.2026/Хазинэ" --limit 12

Пути (по умолчанию):
  Датасет/Исходные изображения/<дата>/<локация>/   — вход
  Датасет/Прокси/<дата>/<локация>/                  — прокси + sheets/
  Датасет/Разметка/<дата>/<локация>/                — worklist.csv, manifest.csv, annotations.csv
Только стандартная библиотека + Pillow (уже есть на этом Mac).
"""
import argparse
import csv
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    print("Нужен Pillow: pip3 install pillow", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[3]          # папка «Разработка»
SRC_ROOT = ROOT / "Датасет" / "Исходные изображения"
PROXY_ROOT = ROOT / "Датасет" / "Прокси"
ANNOT_ROOT = ROOT / "Датасет" / "Разметка"

IMAGE_EXT = {".arw", ".jpg", ".jpeg"}

# Колонки annotations.csv — ровно их ждёт import_annotations.py.
ANNOT_COLUMNS = [
    "frame", "file", "kind", "artifact_code", "plate_frames",
    "title_ru", "title_tt", "title_en", "dating", "dimensions", "technique",
    "author", "description", "artifact_type", "origin", "authenticity",
    "usage_scope", "quality_flags", "confidence", "notes",
]

# Соответствие колонок ручной таблицы Numbers -> наши поля.
NUMBERS_MAP = {
    "Название работы": "title_ru",
    "Время работы": "dating",
    "Размер работы": "dimensions",
    "Дополнительное описание": "description",
}


def frame_id(path: Path) -> str:
    """'_DSC9240.ARW' -> 'DSC9240'."""
    return path.stem.lstrip("_")


def list_frames(loc_dir: Path):
    files = [p for p in loc_dir.iterdir() if p.suffix.lower() in IMAGE_EXT]
    return sorted(files, key=lambda p: (frame_id(p), p.suffix.lower()))


# ---------------------------------------------------------------- 1. прокси
def make_proxy(src: Path, dst: Path, size: int) -> str:
    if dst.exists():
        return "skip"
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85",
         "-Z", str(size), str(src), "--out", str(dst)],
        capture_output=True, text=True,
    )
    return "ok" if r.returncode == 0 and dst.exists() else f"fail: {r.stderr.strip()[:80]}"


def build_proxies(frames, proxy_dir: Path, size: int, workers: int):
    jobs = [(p, proxy_dir / f"{frame_id(p)}.jpg") for p in frames]
    done = {"ok": 0, "skip": 0, "fail": 0}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for (src, dst), res in zip(jobs, ex.map(lambda j: make_proxy(j[0], j[1], size), jobs)):
            key = res.split(":")[0]
            done[key] = done.get(key, 0) + 1
            if key == "fail":
                print(f"   ! {src.name}: {res}")
    print(f"   прокси: новых {done['ok']}, уже были {done['skip']}, ошибок {done['fail']}")


# ---------------------------------------------------------------- 2. Numbers -> CSV
def export_numbers(numbers_file: Path, out_csv: Path) -> bool:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    if out_csv.exists() and out_csv.stat().st_mtime >= numbers_file.stat().st_mtime:
        return True
    script = f'''
    set f to POSIX file "{numbers_file}"
    set outStr to (POSIX file "{out_csv}") as string
    tell application "Numbers"
        set d to open f
        export d to file outStr as CSV
        close d saving no
    end tell
    '''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"   ! экспорт Numbers не удался: {r.stderr.strip()[:200]}")
        return False
    return out_csv.exists()


def read_worklist(csv_path: Path):
    """Возвращает {frame: {поля из Numbers}} . Разделитель определяем сами (Numbers даёт ';' или ',')."""
    text = csv_path.read_text(encoding="utf-8-sig")
    delim = ";" if text.splitlines()[0].count(";") >= text.splitlines()[0].count(",") else ","
    rows = list(csv.DictReader(text.splitlines(), delimiter=delim))
    result = {}
    for row in rows:
        fid = (row.get("Имя файла") or "").strip().lstrip("_")
        if not fid or fid.lower().startswith("итого"):
            continue
        mapped = {v: (row.get(k) or "").strip() for k, v in NUMBERS_MAP.items()}
        mapped["type_manual"] = (row.get("Тип работы") or "").strip()
        if fid in result:
            print(f"   ! дубль в Numbers: {fid}")
        result[fid] = mapped
    return result


# ---------------------------------------------------------------- 3-4. manifest / annotations
def write_manifest_and_annotations(frames, worklist, proxy_dir: Path, annot_dir: Path, loc_rel: Path):
    annot_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = annot_dir / "manifest.csv"
    annot_path = annot_dir / "annotations.csv"

    with manifest_path.open("w", newline="", encoding="utf-8") as fm:
        wm = csv.writer(fm)
        wm.writerow(["frame", "file", "proxy", "in_worklist", "kind_guess"])
        for p in frames:
            fid = frame_id(p)
            in_wl = fid in worklist if worklist else ""
            kind = ("work" if in_wl else "plate") if worklist else ""
            wm.writerow([fid, str(loc_rel / p.name), str(proxy_dir.relative_to(ROOT) / f"{fid}.jpg"), in_wl, kind])

    if annot_path.exists():
        print(f"   annotations.csv уже существует — не трогаю (чтобы не затереть разметку)")
        return
    with annot_path.open("w", newline="", encoding="utf-8") as fa:
        wa = csv.DictWriter(fa, fieldnames=ANNOT_COLUMNS)
        wa.writeheader()
        for p in frames:
            fid = frame_id(p)
            row = {c: "" for c in ANNOT_COLUMNS}
            row["frame"] = fid
            row["file"] = str(loc_rel / p.name)
            if worklist:
                row["kind"] = "work" if fid in worklist else "plate"
                if fid in worklist:
                    wl = worklist[fid]
                    for k in ("title_ru", "dating", "dimensions", "description"):
                        row[k] = wl.get(k, "")
                    if wl.get("type_manual"):
                        row["notes"] = f"Тип (ручной ввод): {wl['type_manual']}"
            wa.writerow(row)
    print(f"   manifest.csv и annotations.csv записаны ({len(frames)} кадров)")


# ---------------------------------------------------------------- 5. контактные листы
def build_sheets(frames, worklist, proxy_dir: Path, per_sheet=9, cell=600):
    sheets_dir = proxy_dir / "sheets"
    sheets_dir.mkdir(exist_ok=True)
    cols = 3
    rows_n = (per_sheet + cols - 1) // cols
    label_h = 34
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except Exception:
        font = ImageFont.load_default()

    chunks = [frames[i:i + per_sheet] for i in range(0, len(frames), per_sheet)]
    index_lines = []
    for n, chunk in enumerate(chunks, 1):
        sheet = Image.new("RGB", (cell * cols, (cell + label_h) * rows_n), "white")
        d = ImageDraw.Draw(sheet)
        names = []
        for i, p in enumerate(chunk):
            fid = frame_id(p)
            proxy = proxy_dir / f"{fid}.jpg"
            if not proxy.exists():
                continue
            im = Image.open(proxy)
            im.thumbnail((cell, cell))
            x, y = (i % cols) * cell, (i // cols) * (cell + label_h)
            kind = ("work" if fid in worklist else "plate?") if worklist else ""
            d.rectangle([x, y, x + cell, y + label_h], fill="#222")
            d.text((x + 8, y + 5), f"{fid}  {kind}", fill="white", font=font)
            sheet.paste(im, (x + (cell - im.width) // 2, y + label_h + (cell - im.height) // 2))
            names.append(fid)
        out = sheets_dir / f"sheet_{n:02d}.jpg"
        sheet.save(out, quality=82)
        index_lines.append(f"sheet_{n:02d}.jpg: {', '.join(names)}")
    (sheets_dir / "index.txt").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    print(f"   контактных листов: {len(chunks)} (см. sheets/index.txt)")


# ---------------------------------------------------------------- main
def process_location(loc_rel: Path, size: int, limit: int, workers: int, no_sheets: bool):
    loc_dir = SRC_ROOT / loc_rel
    if not loc_dir.is_dir():
        print(f"Нет папки: {loc_dir}")
        return
    print(f"\n== {loc_rel}")
    frames = list_frames(loc_dir)
    if limit:
        frames = frames[:limit]
    print(f"   кадров: {len(frames)}")

    proxy_dir = PROXY_ROOT / loc_rel
    annot_dir = ANNOT_ROOT / loc_rel

    build_proxies(frames, proxy_dir, size, workers)

    worklist = {}
    numbers = sorted(loc_dir.glob("*.numbers"))
    if numbers:
        wl_csv = annot_dir / "worklist.csv"
        if export_numbers(numbers[0], wl_csv):
            worklist = read_worklist(wl_csv)
            print(f"   рабочих кадров по Numbers: {len(worklist)}")
    else:
        print("   таблицы .numbers нет — kind оставлен пустым, ИИ определит сам")

    write_manifest_and_annotations(frames, worklist, proxy_dir, annot_dir, loc_rel)
    if not no_sheets:
        build_sheets(frames, worklist, proxy_dir)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--location", action="append", help='например "01.09.2026/Кул шариф" (можно несколько раз)')
    ap.add_argument("--all", action="store_true", help="все локации")
    ap.add_argument("--size", type=int, default=1600, help="длинная сторона прокси, px (по умолчанию 1600)")
    ap.add_argument("--limit", type=int, default=0, help="взять только первые N кадров (для теста)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-sheets", action="store_true", help="не строить контактные листы")
    args = ap.parse_args()

    if args.all:
        locs = sorted(p.relative_to(SRC_ROOT) for p in SRC_ROOT.glob("*/*") if p.is_dir())
    elif args.location:
        locs = [Path(l) for l in args.location]
    else:
        ap.error("укажи --location или --all")

    for loc in locs:
        process_location(loc, args.size, args.limit, args.workers, args.no_sheets)
    print("\nГотово.")


if __name__ == "__main__":
    main()
