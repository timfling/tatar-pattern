#!/usr/bin/env python3
"""
extend_batch.py — дописать следующую пачку кадров в уже начатую разметку.

Не трогает существующие строки annotations.csv. Добавляет прокси, строки
заготовки и новые контактные листы (нумерация продолжается: sheet_05…).

Запуск из корня «Разработка»:
  python3 tatar-pattern/tools/dataset/extend_batch.py \
      --location "01.09.2026/Кул шариф" --offset 29 --count 15
"""
import argparse
import csv
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("prepare", HERE / "prepare.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def next_sheet_index(sheets_dir: Path) -> int:
    nums = []
    for p in sheets_dir.glob("sheet_*.jpg"):
        try:
            nums.append(int(p.stem.split("_")[1]))
        except (IndexError, ValueError):
            pass
    return max(nums) + 1 if nums else 1


def append_annotations(frames, worklist, annot_path: Path, loc_rel: Path):
    existing = set()
    rows = []
    if annot_path.exists():
        with annot_path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
            existing = {r["frame"] for r in rows}
    new_count = 0
    for p in frames:
        fid = prepare.frame_id(p)
        if fid in existing:
            continue
        row = {c: "" for c in prepare.ANNOT_COLUMNS}
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
        rows.append(row)
        new_count += 1
    with annot_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=prepare.ANNOT_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return new_count


def append_sheets(frames, worklist, proxy_dir: Path, start_n: int, per_sheet=9, cell=600):
    from PIL import Image, ImageDraw, ImageFont
    sheets_dir = proxy_dir / "sheets"
    sheets_dir.mkdir(exist_ok=True)
    cols = 3
    rows_n = (per_sheet + cols - 1) // cols
    label_h = 34
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except Exception:
        font = ImageFont.load_default()

    index_path = sheets_dir / "index.txt"
    index_lines = index_path.read_text(encoding="utf-8").splitlines() if index_path.exists() else []
    index_lines = [ln for ln in index_lines if ln.strip()]

    chunks = [frames[i:i + per_sheet] for i in range(0, len(frames), per_sheet)]
    made = []
    for i, chunk in enumerate(chunks):
        n = start_n + i
        sheet = Image.new("RGB", (cell * cols, (cell + label_h) * rows_n), "white")
        d = ImageDraw.Draw(sheet)
        names = []
        for j, p in enumerate(chunk):
            fid = prepare.frame_id(p)
            proxy = proxy_dir / f"{fid}.jpg"
            if not proxy.exists():
                continue
            im = Image.open(proxy)
            im.thumbnail((cell, cell))
            x, y = (j % cols) * cell, (j // cols) * (cell + label_h)
            kind = ("work" if fid in worklist else "plate?") if worklist else ""
            d.rectangle([x, y, x + cell, y + label_h], fill="#222")
            d.text((x + 8, y + 5), f"{fid}  {kind}", fill="white", font=font)
            sheet.paste(im, (x + (cell - im.width) // 2, y + label_h + (cell - im.height) // 2))
            names.append(fid)
        out = sheets_dir / f"sheet_{n:02d}.jpg"
        sheet.save(out, quality=82)
        line = f"sheet_{n:02d}.jpg: {', '.join(names)}"
        made.append(line)
        # replace if this sheet number already listed
        prefix = f"sheet_{n:02d}.jpg:"
        index_lines = [ln for ln in index_lines if not ln.startswith(prefix)]
        index_lines.append(line)
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    return made


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--location", required=True)
    ap.add_argument("--offset", type=int, required=True, help="сколько кадров уже в CSV (пропустить с начала)")
    ap.add_argument("--count", type=int, required=True, help="сколько новых кадров взять")
    ap.add_argument("--size", type=int, default=1600)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    loc_rel = Path(args.location)
    loc_dir = prepare.SRC_ROOT / loc_rel
    frames_all = prepare.list_frames(loc_dir)
    batch = frames_all[args.offset:args.offset + args.count]
    if not batch:
        print("Нечего добавлять.")
        return
    print(f"== {loc_rel}: кадры {args.offset}–{args.offset + len(batch) - 1} "
          f"({prepare.frame_id(batch[0])} … {prepare.frame_id(batch[-1])}), {len(batch)} шт.")

    proxy_dir = prepare.PROXY_ROOT / loc_rel
    annot_dir = prepare.ANNOT_ROOT / loc_rel
    prepare.build_proxies(batch, proxy_dir, args.size, args.workers)

    worklist = {}
    wl_csv = annot_dir / "worklist.csv"
    if wl_csv.exists():
        worklist = prepare.read_worklist(wl_csv)
        print(f"   рабочих кадров по Numbers: {len(worklist)}")

    added = append_annotations(batch, worklist, annot_dir / "annotations.csv", loc_rel)
    print(f"   в annotations.csv добавлено строк: {added}")

    # manifest — полный срез до конца этой пачки
    so_far = frames_all[: args.offset + len(batch)]
    prepare.write_manifest_and_annotations(so_far, worklist, proxy_dir, annot_dir, loc_rel)

    start_n = next_sheet_index(proxy_dir / "sheets")
    made = append_sheets(batch, worklist, proxy_dir, start_n)
    print(f"   новые листы: {len(made)}")
    for ln in made:
        print(f"     {ln}")
    print("Готово.")


if __name__ == "__main__":
    main()
