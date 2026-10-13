#!/usr/bin/env python3
"""Build a review-only motif catalogue from hand selected rectangles and September CSVs.

Writes only to Датасет/Элементы. No database or source annotation writes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from prompt_scope import selection_instruction


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "Датасет" / "Элементы"
ANN = ROOT / "Датасет" / "Разметка" / "01.09.2026"
PROXY = ROOT / "Датасет" / "Прокси" / "01.09.2026"
RAW = ROOT / "Датасет" / "Исходные изображения"
MANUAL = OUT / "manual_candidates.tsv"
REVIEWS = OUT / "owner_reviews.json"
SUPPLEMENTAL = OUT / "supplemental_references.tsv"
REPLACEMENTS = OUT / "replacement_shortlist.tsv"
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
PREVIEW_INDEX = OUT / "source_previews/index.json"
ASSESSMENTS = OUT / "processed_assessments.json"


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def crop_source(frame, proxy, previews):
    preview = previews.get(frame)
    if not preview:
        return ImageOps.exif_transpose(Image.open(proxy)).convert("RGB"), str(proxy.relative_to(ROOT)), "proxy", 0
    path = ROOT / preview["preview_file"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != preview["preview_sha256"]:
        raise ValueError(f"Embedded preview changed: {frame}; rerun source_previews.py")
    im = Image.open(path).convert("RGB").rotate(preview["rotation_ccw"], expand=True)
    return im, preview["preview_file"], "native embedded camera JPEG, no upscale", preview["rotation_ccw"]


def source_metadata(source, by_artifact):
    """Inherit non-empty label fields only within the same original artifact code."""
    peers = by_artifact[source["artifact_code"]]
    return {key: source.get(key) or next((p[key] for p in peers if p.get(key)), "")
            for key in ("title_ru", "dating", "technique", "author", "description", "plate_frames")}


def read_annotations(root: Path):
    by_frame, by_artifact, rows = {}, defaultdict(list), []
    for path in sorted(root.glob("*/annotations.csv")):
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                row = dict(row)
                row["annotation_path"] = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
                row["location"] = path.parent.name
                if row["frame"] in by_frame:
                    raise ValueError(f"Duplicate source frame: {row['frame']}")
                by_frame[row["frame"]] = row
                if row["kind"] == "work" and row["artifact_code"]:
                    by_artifact[row["artifact_code"]].append(row)
                rows.append(row)
    return by_frame, by_artifact, rows


def read_manual(path: Path):
    with path.open(encoding="utf-8", newline="") as fh:
        entries = list(csv.DictReader(fh, delimiter="\t"))
    needed = {"code", "artifact_code", "frame", "box_1000", "motif_class", "description", "motif_confidence", "crop_limitations", "manual_note"}
    if not entries or not needed.issubset(entries[0]):
        raise ValueError("Manual TSV missing required fields")
    codes = [e["code"] for e in entries]
    if len(codes) != len(set(codes)):
        raise ValueError("Duplicate candidate code")
    return entries


def read_reviews(path: Path, by_frame):
    data = json.loads(path.read_text(encoding="utf-8"))
    mapped = {}
    for entry in data["entries"]:
        for frame in entry["frames"]:
            if frame not in by_frame or frame in mapped:
                raise ValueError(f"Missing or duplicate owner review frame: {frame}")
            mapped[frame] = entry
    rights = data["rights"]
    rights_note = f"{rights['statement']} Условие: {rights['condition']}. Письменного подтверждения нет. {rights['unclear_scope']}"
    return mapped, rights_note


def font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default()


def check_box(value):
    xy = tuple(int(v) for v in value.split(","))
    if len(xy) != 4 or not (0 <= xy[0] < xy[2] <= 1000 and 0 <= xy[1] < xy[3] <= 1000):
        raise ValueError(f"Invalid box: {value}")
    return xy


def dhash(im):
    pixels = list(im.convert("L").resize((9, 8)).get_flattened_data())
    val = 0
    for y in range(8):
        for x in range(8):
            val = (val << 1) | int(pixels[y * 9 + x] > pixels[y * 9 + x + 1])
    return val


def make_contact_sheets(records, out):
    paths = []
    sheetdir = out / "contact_sheets"
    sheetdir.mkdir(exist_ok=True)
    for start in range(0, len(records), 20):
        page = start // 20 + 1
        canvas = Image.new("RGB", (1800, 1440), "#f4f4ef")
        draw = ImageDraw.Draw(canvas)
        draw.text((22, 10), f"TATAR PATTERN | кандидаты {start+1}–{min(start+20,len(records))} | лист {page}", fill="#202020", font=font(24))
        for j, rec in enumerate(records[start:start + 20]):
            x, y = (j % 5) * 360, 48 + (j // 5) * 348
            im = Image.open(out / "crops" / f"{rec['code']}.png")
            im.thumbnail((334, 274))
            canvas.paste(im, (x + (360 - im.width) // 2, y + (274 - im.height) // 2))
            draw.text((x + 8, y + 278), f"{rec['code']}  {rec['artifact_code']}  {rec['frame']}", fill="#111", font=font(17))
            label = rec["description"][:37]
            draw.text((x + 8, y + 302), label, fill="#303030", font=font(16))
            draw.text((x + 8, y + 323), f"{rec['motif_class']} | {rec['confidence']}", fill="#555", font=font(15))
        path = sheetdir / f"sheet_{page:02}.jpg"
        canvas.save(path, quality=89)
        paths.append(path)
    return paths


def make_supplemental(by_frame, out, rights_note, previews):
    with SUPPLEMENTAL.open(encoding="utf-8", newline="") as fh:
        entries = list(csv.DictReader(fh, delimiter="\t"))
    codes = [e["code"] for e in entries]
    if len(codes) != len(set(codes)):
        raise ValueError("Duplicate supplemental code")
    target = out / "reference_crops"
    target.mkdir(exist_ok=True)
    records = []
    for e in entries:
        source = by_frame.get(e["frame"])
        if not source or source["artifact_code"] != e["artifact_code"]:
            raise ValueError(f"Supplemental source mismatch: {e['code']}")
        raw = RAW / source["file"]
        proxy = PROXY / source["location"] / f"{e['frame']}.jpg"
        if not raw.is_file() or not proxy.is_file():
            raise FileNotFoundError(e["code"])
        im, source_file, source_kind, rotation = crop_source(e["frame"], proxy, previews)
        box = check_box(e["box_1000"])
        pixels = tuple(round(v * dim / 1000) for v, dim in zip(box, (im.width, im.height, im.width, im.height)))
        cropped = im.crop(pixels)
        path = target / f"{e['code']}.png"
        cropped.save(path, optimize=True)
        records.append({**e, "source_raw": str(raw.relative_to(ROOT)),
                        "crop_file": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                        "crop_source_file": source_file, "crop_source_kind": source_kind,
                        "crop_source_rotation_ccw": rotation, "crop_size": f"{cropped.width}x{cropped.height}",
                        "source_title_ru": source["title_ru"], "source_dating": source["dating"],
                        "source_technique": source["technique"], "source_author": source["author"],
                        "plate_frames": source["plate_frames"],
                        "rights_limitations": rights_note,
                        "status": "вспомогательный кандидат, требуется человек"})
    with (out / "supplemental_references.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(records[0]))
        writer.writeheader(); writer.writerows(records)
    return records


def make_frame_pool(source_rows, reviews, records, out):
    motif_counts = defaultdict(int)
    for rec in records:
        motif_counts[rec["frame"]] += 1
    pool = []
    for row in source_rows:
        if row["kind"] != "work":
            continue
        review = reviews.get(row["frame"], {})
        if review.get("decision", "").startswith("исключить") or review.get("decision", "").startswith("пропустить"):
            continue
        if row["usage_scope"] != "рид_и_обучение" and row["frame"] != "DSC9449":
            continue
        canonical = review.get("canonical_artifact_code", row["artifact_code"])
        category = "вспомогательный, культурная атрибуция не установлена" if canonical == "KS-9448" else "предварительный кадр"
        if review.get("cultural_scope", "").startswith("современное оформление"):
            category = "современный интерьер; проверить пригодность мотива"
        pool.append({"frame": row["frame"], "artifact_code": canonical,
                     "source_artifact_code": row["artifact_code"], "location": row["location"],
                     "source_raw": str((RAW / row["file"]).relative_to(ROOT)),
                     "source_proxy": str((PROXY / row["location"] / f"{row['frame']}.jpg").relative_to(ROOT)),
                     "source_confidence": row["confidence"], "quality_flags": row["quality_flags"],
                     "owner_title_ru": review.get("title_ru", ""),
                     "owner_decision": review.get("decision", ""),
                     "category": category,
                     "motif_crops_now": motif_counts[row["frame"]],
                     "processing_status": "предварительный отбор; визуальная проверка обязательна"})
    with (out / "frame_pool.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(pool[0]))
        writer.writeheader(); writer.writerows(pool)
    return pool


def make_prompts(records, out):
    (out / "processed_flat").mkdir(exist_ok=True)
    prompts = []
    pilot_codes = {"TP-E-013", "TP-E-034", "TP-E-037", "TP-E-046", "TP-E-050", "TP-E-053",
                   "TP-E-061", "TP-E-072", "TP-E-083", "TP-E-093", "TP-E-106", "TP-E-114"}
    for rec in records:
        caution = "Если линия стерта, закрыта бликом или обрезана, оставь видимый фрагмент; не достраивай по симметрии или догадке."
        role = "основной кандидат" if rec["code"].startswith("TP-E-") else "вспомогательный образец; не считать подтверждённо татарским"
        prompt = (f"Используй приложенную вырезку как единственный визуальный источник. "
                  f"{selection_instruction(rec)} "
                  "Подготовь плоскую графическую отрисовку для орнаментального конструктора: четкие контуры, "
                  "сплошные цветовые области и читаемые внутренние линии. Сохрани число лепестков, вставок, "
                  "завитков, отверстий и соединений и характерные соотношения размеров. Допустима коррекция "
                  "перспективы, складок и изгиба поверхности, умеренное выравнивание линий; попиксельное совпадение "
                  "не требуется. Цель — сходство с исходным мотивом на 90–100%, без новых деталей и другой "
                  "схемы узора. Не заменяй его стандартной розеткой. Удали фон предмета и соседние мотивы. "
                  "Убери фотографическую фактуру ткани, волокон, кожи, металла и керамики, тени, объем, "
                  "блеск и свечение; сохрани видимые границы деталей, рисунок и исходные цвета. "
                  f"{caution} Не добавляй новые цветы, завитки, текст, рамки, подписи и стилизацию. "
                  "Сделай PNG 1024×1024 на настоящем прозрачном фоне (без нарисованной шахматной сетки); "
                  "если альфа недоступна, используй ровный белый фон. Вне мотива и внутри сквозных отверстий "
                  "прозрачность, внутри окрашенных деталей непрозрачная заливка. Плавная альфа только вдоль кромки. "
                  "Мотив по центру, поля не меньше 8% по длинной стороне; не растягивай длинный бордюр в квадрат. "
                  "Сохрани ориентацию входной вырезки, без поворота и отражения. Не добавляй обводку там, где ее нет. ")
        if rec["code"].startswith("TP-R-"):
            prompt += " Это вспомогательный образец с неустановленной культурной атрибуцией; не добавляй этнических признаков по догадке."
        output = out / "processed_flat" / f"{rec['code']}.png"
        previous = out / "processed" / f"{rec['code']}.png"
        batch = "замены — пилот 2" if rec.get("replaces_code") else ("пилот 2 — исправление/плоская версия" if previous.is_file() else ("вспомогательный" if rec["code"].startswith("TP-R-") else "основной проход"))
        blocked = rec.get("source_gate", "").startswith("ПРОВЕРИТЬ")
        if blocked:
            batch = "ПАУЗА — проверить допуск источника"
        prompts.append({"code": rec["code"], "artifact_code": rec["artifact_code"],
                        "frame": rec["frame"], "input_crop": rec["crop_file"],
                        "catalog_role": role,
                        "batch": batch, "original_batch": "пилот 1" if rec["code"] in pilot_codes else "основной проход",
                        "replaces_code": rec.get("replaces_code", ""),
                        "source_title_ru": rec.get("source_title_ru", ""),
                        "source_dating": rec.get("source_dating", ""),
                        "source_technique": rec.get("source_technique", ""),
                        "source_author": rec.get("source_author", ""),
                        "owner_title_ru": rec.get("owner_title_ru", ""),
                        "owner_dating": rec.get("owner_dating", ""),
                        "owner_technique": rec.get("owner_technique", ""),
                        "plate_frames": rec.get("plate_frames", ""),
                        "input_size": rec.get("crop_size", ""),
                        "prompt_version": "flat-v3-2026-10-04",
                        "processing_action": "не запускать до проверки атрибуции/допуска источника" if blocked else ("подготовить плоскую версию; сверить с источником; требуется человек" if rec["code"].startswith("TP-E-") else "вспомогательный образец для MVP; вне татарской LoRA"),
                        "quality_limitations": rec.get("quality_limitations", ""),
                        "prompt": prompt,
                        "save_as": str(output.relative_to(ROOT)) if output.is_relative_to(ROOT) else str(output),
                        "file_present": "да" if output.is_file() else "нет",
                        "previous_processed": str(previous.relative_to(ROOT)) if previous.is_file() and previous.is_relative_to(ROOT) else "",
                        "review_after": "наложить на источник; пересчитать детали; проверить альфа на белом/цветном фоне; решение человека"})
    with (out / "higgsfield_prompts.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(prompts[0]))
        writer.writeheader(); writer.writerows(prompts)
    return prompts


def make_replacement_shortlist(by_frame, out):
    with REPLACEMENTS.open(encoding="utf-8", newline="") as fh:
        picks = list(csv.DictReader(fh, delimiter="\t"))
    if len({p["frame"] for p in picks}) != len(picks):
        raise ValueError("Duplicate replacement frame")
    rows = []
    for pick in picks:
        src = by_frame.get(pick["frame"])
        if not src or src["kind"] != "work":
            raise ValueError(f"Missing replacement work frame: {pick['frame']}")
        proxy = PROXY / src["location"] / f"{pick['frame']}.jpg"
        raw = RAW / src["file"]
        if not proxy.is_file() or not raw.is_file():
            raise FileNotFoundError(pick["frame"])
        rows.append({**pick, "artifact_code": src["artifact_code"], "source_origin": src["origin"],
                     "source_usage_scope": src["usage_scope"], "quality_flags": src["quality_flags"],
                     "source_proxy": str(proxy.relative_to(ROOT)), "source_raw": str(raw.relative_to(ROOT)),
                     "status": pick.get("review_decision") or "только следующий просмотр, не добавлен в основной каталог"})
    with (out / "replacement_shortlist.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    canvas = Image.new("RGB", (1500, 1700), "#f4f4ef")
    draw = ImageDraw.Draw(canvas)
    draw.text((20, 8), "Кадры для возможной замены | НЕ атрибутированы автоматически", fill="#111", font=font(24))
    for i, row in enumerate(rows):
        x, y = (i % 3) * 500, 54 + (i // 3) * 410
        im = ImageOps.exif_transpose(Image.open(ROOT / row["source_proxy"])).convert("RGB")
        im.thumbnail((470, 345))
        canvas.paste(im, (x + (500 - im.width) // 2, y + (345 - im.height) // 2))
        draw.text((x + 9, y + 351), f"{row['frame']}  {row['artifact_code']}  P{row['priority']}", fill="#111", font=font(20))
        draw.text((x + 9, y + 375), row["source_origin"] + " | " + row["source_usage_scope"], fill="#555", font=font(17))
    canvas.save(out / "replacement_sheet_01.jpg", quality=89)
    return rows


def make_lora_plan(records, out):
    rows = []
    for rec in records:
        path = out / "processed_flat" / (rec["code"] + ".png")
        rows.append({"code": rec["code"], "image_file": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                     "file_present": "да" if path.is_file() else "нет",
                     "neutral_caption_ru_draft": rec.get("caption_override") or "Плоский орнаментальный мотив: " + rec["description"] + ".",
                     "caption_status": "черновик; сверить с реально принятой плоской версией",
                     "split_group_artifact": rec["artifact_code"],
                     "frame": rec["frame"], "source_title_ru": rec["source_title_ru"],
                     "source_dating": rec["source_dating"], "source_technique": rec["source_technique"],
                     "source_author": rec["source_author"], "source_description": rec["source_description"],
                     "owner_title_ru": rec["owner_title_ru"], "owner_dating": rec["owner_dating"],
                     "owner_technique": rec["owner_technique"], "owner_author": rec["owner_author"],
                     "plate_frames": rec["plate_frames"], "source_annotation": rec["annotation_file"],
                     "source_authenticity": rec["source_authenticity"], "source_usage_scope": rec["source_usage_scope"],
                     "human_decision": rec["human_decision"], "ai_retouched": "true",
                     "training_ready": "нет; требуется плоский файл и решение человека",
                     "rights_limitations": rec["rights_limitations"]})
    write_csv(out / "lora_preparation.csv", rows)


def build_queue(by_artifact, records, reviews, out):
    by_code = defaultdict(list)
    for rec in records:
        by_code[rec["artifact_code"]].append(rec["code"])
    queue = []
    low_source_codes = []
    grouped = defaultdict(list)
    for code, frames in sorted(by_artifact.items()):
        eligible = [r for r in frames if r["usage_scope"] == "рид_и_обучение"]
        if eligible and min(float(r["confidence"] or 0) for r in eligible) < 0.7:
            low_source_codes.append(code)
        for row in eligible:
            canonical = reviews.get(row["frame"], {}).get("canonical_artifact_code", code)
            grouped[canonical].append(row)
    low_count = 0
    for code, frames in sorted(grouped.items()):
        if min(float(r["confidence"] or 0) for r in frames) < 0.7:
            low_count += 1
            reviewed = [reviews[r["frame"]] for r in frames if r["frame"] in reviews]
            owner_note = " | ".join(dict.fromkeys(x.get("decision", "") for x in reviewed if x.get("decision")))
            queue.append({"priority": "1", "issue": "confidence<0.7", "artifact_code": code,
                          "frames": ",".join(r["frame"] for r in frames),
                          "reason": "Исходная уверенность хотя бы одного кадра ниже 0.7",
                          "action": "Проверить самостоятельность и качество мотива" if reviewed else "Сверить предмет, табличку и пригодность мотива",
                          "owner_resolution": owner_note,
                          "candidate_codes": ",".join(by_code[code])})
    extra = [
        ("KS-9448", "DSC9448,DSC9449", "культурная атрибуция", "Завод в Твери; владелец допускает узор как визуальный образец для некоммерческого MVP", "Не считать подтвержденным татарским мотивом; вести отдельно от доказательного счёта"),
        ("KS-9441", "DSC9441,DSC9445", "нет отдельной таблички", "Владелец опознал фрагмент ковра из сундука для приданного", "Проверить происхождение конкретного мотива"),
        ("KS-9446", "DSC9446", "нет отдельной таблички", "Владелец опознал фрагмент отделки сундука для приданного", "Проверить происхождение конкретного мотива"),
        ("ALL", "", "объём устного согласия", "Администраторы трёх музеев устно согласились на некоммерческое использование, по сообщению владельца", "Для внешнего сервиса и обучения зафиксировать допустимый объём использования; это не блокирует внутренний отбор"),
    ]
    for code, frames, issue, reason, action in extra:
        queue.append({"priority": "2", "issue": issue, "artifact_code": code, "frames": frames,
                      "reason": reason, "action": action, "owner_resolution": "см. owner_reviews.json",
                      "candidate_codes": ",".join(by_code[code])})
    with (out / "review_queue.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(queue[0]))
        writer.writeheader(); writer.writerows(queue)
    return queue, low_count, len(low_source_codes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations-dir", type=Path, default=ANN, help="For a dry refresh test with copied CSVs")
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument("--manual-file", type=Path, default=MANUAL)
    parser.add_argument("--owner-reviews", type=Path, default=REVIEWS)
    args = parser.parse_args()
    by_frame, by_artifact, source_rows = read_annotations(args.annotations_dir)
    entries = read_manual(args.manual_file)
    reviews, rights_note = read_reviews(args.owner_reviews, by_frame)
    previews = json.loads(PREVIEW_INDEX.read_text(encoding="utf-8")) if PREVIEW_INDEX.exists() else {}
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "crops").mkdir(exist_ok=True)
    active = {entry["code"] for entry in entries}
    for stale in (out / "crops").glob("TP-E-*.png"):
        if stale.stem not in active:
            stale.unlink()
    records, hashes = [], []
    for entry in entries:
        code, artifact, frame = entry["code"], entry["artifact_code"], entry["frame"]
        source = by_frame.get(frame)
        if not source or source["artifact_code"] != artifact or source["kind"] != "work":
            raise ValueError(f"Missing/mismatched source: {code} {artifact} {frame}")
        raw = RAW / source["file"]
        proxy = PROXY / source["location"] / f"{frame}.jpg"
        if not raw.is_file() or not proxy.is_file():
            raise FileNotFoundError(f"{code}: {raw} / {proxy}")
        box = check_box(entry["box_1000"])
        im, crop_source_file, crop_source_kind, crop_source_rotation = crop_source(frame, proxy, previews)
        pixels = tuple(round(v * dim / 1000) for v, dim in zip(box, (im.width, im.height, im.width, im.height)))
        crop = im.crop(pixels)
        if crop.width < 35 or crop.height < 35:
            raise ValueError(f"Too small crop {code}: {crop.size}")
        crop_rel = Path("Датасет/Элементы/crops") / f"{code}.png" if out.resolve() == OUT.resolve() else out.resolve() / "crops" / f"{code}.png"
        crop_path = out / "crops" / f"{code}.png"
        crop.save(crop_path, optimize=True)
        hashes.append((code, dhash(crop), hashlib.sha256(crop.tobytes()).hexdigest()))
        confidence = min(float(source["confidence"] or 0), float(entry["motif_confidence"]))
        gate = "источник подходит предварительно" if source["origin"] == "татарское" and source["usage_scope"] == "рид_и_обучение" and source["authenticity"] in ("оригинал", "новодел") else "ПРОВЕРИТЬ: разметка источника вне основного отбора"
        review = reviews.get(frame, {})
        canonical = review.get("canonical_artifact_code", artifact)
        cultural_scope = review.get("cultural_scope", "")
        if cultural_scope and ("не установлен" in cultural_scope or "современное оформление" in cultural_scope):
            gate = "ПРОВЕРИТЬ: " + cultural_scope
        metadata = source_metadata(source, by_artifact)
        record = {
            "code": code, "artifact_code": canonical, "source_artifact_code": artifact, "frame": frame,
            "source_raw": str(raw.relative_to(ROOT)), "source_proxy": str(proxy.relative_to(ROOT)),
            "annotation_file": source["annotation_path"], "box_1000": entry["box_1000"],
            "place_description": "прямоугольник x1,y1,x2,y2 в тысячных долях кадра; " + entry["manual_note"],
            "motif_class": entry["motif_class"], "description": entry["description"],
            "confidence": f"{confidence:.2f}", "source_confidence": source["confidence"],
            "crop_file": str(crop_rel), "crop_source_file": crop_source_file,
            "crop_source_kind": crop_source_kind, "crop_source_rotation_ccw": crop_source_rotation,
            "crop_size": f"{crop.width}x{crop.height}",
            "crop_sha256": hashlib.sha256(crop_path.read_bytes()).hexdigest(),
            "source_title_ru": metadata["title_ru"], "source_dating": metadata["dating"],
            "source_technique": metadata["technique"], "source_author": metadata["author"],
            "source_description": metadata["description"], "plate_frames": metadata["plate_frames"],
            "quality_limitations": "; ".join(x for x in [source["quality_flags"], entry["crop_limitations"], "фото-вырезка, не плоская отрисовка"] if x),
            "rights_limitations": rights_note, "source_origin": source["origin"],
            "source_authenticity": source["authenticity"], "source_usage_scope": source["usage_scope"],
            "source_gate": gate, "status": "кандидат, требуется человек",
            "owner_title_ru": review.get("title_ru", ""), "owner_dating": review.get("dating", ""),
            "owner_technique": review.get("technique", ""), "owner_author": review.get("author", ""),
            "owner_object_note": review.get("object_note", ""),
            "owner_review_decision": review.get("decision", ""),
            "owner_cultural_scope": cultural_scope,
            "human_decision": entry.get("human_decision", ""),
            "reviewer_note": entry.get("reviewer_note", ""),
            "selection_status": entry.get("selection_status") or "active",
            "selection_reason": entry.get("selection_reason", ""),
            "replaces_code": entry.get("replaces_code", ""),
            "processing_note": entry.get("processing_note", ""),
            "caption_override": entry.get("caption_override", ""),
            "lora_ready": "нет; нужна принятая человеком плоская отрисовка",
        }
        records.append(record)
    exact = defaultdict(list)
    for code, h, digest in hashes: exact[digest].append(code)
    exact_dupes = [v for v in exact.values() if len(v) > 1]
    if exact_dupes:
        raise ValueError(f"Exact duplicate crops: {exact_dupes}")
    near = []
    for i, (a, ah, _) in enumerate(hashes):
        for b, bh, _ in hashes[i + 1:]:
            distance = (ah ^ bh).bit_count()
            if distance <= 3:
                near.append({"a": a, "b": b, "dhash_distance": distance})
    reserve = [r for r in records if r["selection_status"] != "active"]
    records = [r for r in records if r["selection_status"] == "active"]
    write_csv(out / "reserve_manifest.csv", reserve)
    write_csv(out / "manifest.csv", records)
    sheets = make_contact_sheets(records, out)
    supplemental = make_supplemental(by_frame, out, rights_note, previews)
    pool = make_frame_pool(source_rows, reviews, records, out)
    prompts = make_prompts(records + supplemental, out)
    make_lora_plan(records, out)
    replacements = make_replacement_shortlist(by_frame, out)
    queue, low_count, low_source_count = build_queue(by_artifact, records, reviews, out)
    for r in records:
        if not (ROOT / r["source_raw"]).is_file() or not (ROOT / r["crop_file"]).is_file():
            raise ValueError(f"Missing result/source for {r['code']}")
    report = {"source_rows": len(source_rows), "unique_source_artifacts": len(by_artifact),
              "candidate_count": len(records), "candidate_artifacts": len(set(r["artifact_code"] for r in records)),
              "candidate_frames": len(set(r["frame"] for r in records)), "queue_items": len(queue),
              "low_confidence_unique_artifacts": low_count, "contact_sheets": len(sheets),
              "supplemental_references": len(supplemental),
              "preliminary_frame_pool": len(pool),
              "preliminary_frame_pool_artifacts": len({r["artifact_code"] for r in pool}),
              "higgsfield_prompts": len(prompts),
              "replacement_frames_to_review": len(replacements),
              "reserve_candidates": len(reserve),
              "new_replacement_candidates": sum(bool(r["replaces_code"]) for r in records),
              "native_preview_crops": sum(r["crop_source_kind"].startswith("native") for r in records),
              "short_side_below_256": sum(min(map(int, r["crop_size"].split("x"))) < 256 for r in records),
              "flat_files_present": sum(p["file_present"] == "да" for p in prompts),
              "legacy_processed_files_present": len(list((out / "processed").glob("*.png"))),
              "low_confidence_source_artifact_codes": low_source_count,
              "owner_reviewed_frames": len(reviews),
              "owner_reviews_sha256": hashlib.sha256(args.owner_reviews.read_bytes()).hexdigest(),
              "manual_sha256": hashlib.sha256(args.manual_file.read_bytes()).hexdigest(),
              "annotation_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(args.annotations_dir.glob("*/annotations.csv"))},
              "source_gate_warnings": [r["code"] for r in records if r["source_gate"].startswith("ПРОВЕРИТЬ")],
              "near_crop_pairs_dhash_le_3": near,
              "checks": {"unique_codes": True, "all_raw_present": True, "all_proxy_present": True,
                         "all_crops_present": True, "exact_duplicate_crops": 0}}
    (out / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "near_crop_pairs_dhash_le_3"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
