#!/usr/bin/env python3
"""
import_annotations.py — превращает annotations.csv (заполненный ИИ и проверенный
тобой) в SQL-файл для загрузки в Postgres.

Почему через SQL-файл, а не напрямую в базу: так можно открыть файл глазами,
а загрузка — одной командой `make import FILE=...` из папки db/. Повторный
импорт безопасен: строки с тем же artifact_code обновляются, а не дублируются.

Запуск (из корня «Разработка»):
  python3 tatar-pattern/tools/dataset/import_annotations.py \
      "Датасет/Разметка/01.09.2026/Кул шариф/annotations.csv"
  -> рядом появится annotations.sql

Правила:
  * kind = work   -> предмет (artifacts) + файл raw + proxy
  * kind = plate  -> прикрепляется к предметам, у которых он указан в plate_frames
  * kind = reject -> пропускается
  * несколько кадров с одним artifact_code = один предмет, несколько файлов
Только стандартная библиотека.
"""
import argparse
import csv
import json
import re
import sys
from collections import OrderedDict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

ARTIFACT_TYPES = {"архитектура", "плитка", "витраж", "текстиль", "вышивка", "кожа", "ювелирное",
                  "керамика", "резьба", "рукопись", "каллиграфия", "шамаиль", "иное"}
ORIGINS = {"татарское", "общеисламское", "иное", "неизвестно"}
AUTH = {"оригинал", "реплика", "новодел", "неизвестно"}
SCOPES = {"рид_и_обучение", "только_обучение", "контекст", "исключить"}
QUALITY_KEYS = {"reflection", "angle", "blur", "partial", "lowlight", "colorcast", "ok"}


def q(s):
    """SQL-строка в кавычках; пустое -> NULL."""
    if s is None or str(s).strip() == "":
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def enum_or_default(value, allowed, default, field, frame, warns):
    v = (value or "").strip()
    if not v:
        return default
    if v not in allowed:
        warns.append(f"{frame}: {field}='{v}' не из словаря, поставлено '{default}'")
        return default
    return v


def parse_quality(value, frame, warns):
    """'reflection, angle' -> {"reflection": true, "angle": true}"""
    v = (value or "").strip()
    if not v or v.lower() == "ok":
        return "{}"
    flags = {}
    for tok in re.split(r"[,\s;]+", v):
        if not tok:
            continue
        if tok not in QUALITY_KEYS:
            warns.append(f"{frame}: неизвестный флаг качества '{tok}' (допустимо: {', '.join(sorted(QUALITY_KEYS))})")
            continue
        flags[tok] = True
    return json.dumps(flags, ensure_ascii=False)


def parse_conf(value, frame, warns):
    v = (value or "").strip().replace(",", ".")
    if not v:
        return "NULL"
    try:
        f = float(v)
        if 0 <= f <= 1:
            return f"{f:.2f}"
    except ValueError:
        pass
    warns.append(f"{frame}: confidence='{v}' не число 0..1, пропущено")
    return "NULL"


def location_from_path(csv_path: Path):
    """.../Разметка/01.09.2026/Кул шариф/annotations.csv -> ('01.09.2026', 'Кул шариф')"""
    parts = csv_path.resolve().parts
    try:
        i = parts.index("Разметка")
        return parts[i + 1], parts[i + 2]
    except (ValueError, IndexError):
        return None, csv_path.parent.name


def to_iso(d):
    m = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", d or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def code_prefix(location: str) -> str:
    """Кул шариф -> KS, Национальный музей РТ -> NM и т.д. Заглавные первые буквы слов (латиницей)."""
    lat = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "z", "з": "z",
           "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
           "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "c", "ш": "s", "щ": "s",
           "э": "e", "ю": "u", "я": "a", "ы": "y", "ә": "a", "ө": "o", "ү": "u", "ң": "n", "һ": "h", "җ": "j"}
    words = [w for w in re.split(r"[\s\-—]+", location.lower()) if w]
    letters = [lat.get(w[0], w[0]) for w in words if w[0].isalpha()]
    return "".join(letters).upper()[:4] or "ART"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="путь к annotations.csv")
    ap.add_argument("--city", default="Казань", help="город для поля sources.location (по умолчанию Казань)")
    ap.add_argument("--source-type", default="музей", choices=["фото", "музей", "архив", "книга", "иное"])
    ap.add_argument("--out", help="куда писать SQL (по умолчанию рядом: annotations.sql)")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        sys.exit(f"Нет файла: {csv_path}")
    shot_date_raw, location = location_from_path(csv_path)
    shot_date = to_iso(shot_date_raw)
    source_location = f"{location}, {args.city}"
    prefix = code_prefix(location)

    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
    warns = []

    # Сгруппировать work-кадры по artifact_code (пустой code -> code из кадра).
    artifacts = OrderedDict()
    plates = {}   # frame -> file (для plate-кадров)
    for r in rows:
        kind = (r.get("kind") or "").strip().lower()
        frame = (r.get("frame") or "").strip()
        if kind == "plate":
            plates[frame] = r.get("file", "")
            continue
        if kind != "work":
            if kind not in ("reject", ""):
                warns.append(f"{frame}: kind='{kind}' неизвестен, пропущен")
            continue
        code = (r.get("artifact_code") or "").strip() or f"{prefix}-{frame.replace('DSC', '')}"
        a = artifacts.setdefault(code, {"rows": [], "frames": []})
        a["rows"].append(r)
        a["frames"].append((frame, r.get("file", "")))

    out = []
    out.append(f"-- Сгенерировано import_annotations.py из {csv_path.name}")
    out.append(f"-- Локация: {location} | дата съёмки: {shot_date_raw or '—'} | предметов: {len(artifacts)}")
    out.append("BEGIN;")
    out.append("")
    out.append("-- Источник (создаётся, если ещё нет)")
    out.append(
        f"INSERT INTO sources (source_type, object_name, location, shot_date, legal_basis)\n"
        f"SELECT {q(args.source_type)}, {q(location)}, {q(source_location)}, "
        f"{q(shot_date) if shot_date else 'NULL'}::date, 'Некоммерческий MVP по гранту ФСИ; разрешение на коммерческую съёмку не оформлялось'\n"
        f"WHERE NOT EXISTS (SELECT 1 FROM sources WHERE location = {q(source_location)});"
    )
    out.append("")

    for code, a in artifacts.items():
        # Берём поля из первой строки, где они заполнены (у детальных кадров они могут быть пустыми).
        def pick(field):
            for r in a["rows"]:
                v = (r.get(field) or "").strip()
                if v:
                    return v
            return ""

        frame0 = a["frames"][0][0]
        atype = enum_or_default(pick("artifact_type"), ARTIFACT_TYPES, "иное", "artifact_type", frame0, warns)
        origin = enum_or_default(pick("origin"), ORIGINS, "неизвестно", "origin", frame0, warns)
        auth = enum_or_default(pick("authenticity"), AUTH, "неизвестно", "authenticity", frame0, warns)
        scope = enum_or_default(pick("usage_scope"), SCOPES, "контекст", "usage_scope", frame0, warns)
        quality = parse_quality(pick("quality_flags"), frame0, warns)
        conf = parse_conf(pick("confidence"), frame0, warns)

        # Табличка(и): список кадров через запятую/пробел.
        plate_frames = [p for p in re.split(r"[,\s;]+", pick("plate_frames")) if p]
        plate_files = []
        for pf in plate_frames:
            pf = pf.lstrip("_")
            if pf in plates:
                plate_files.append((pf, plates[pf]))
            else:
                warns.append(f"{code}: табличка {pf} не найдена среди plate-кадров")

        out.append(f"-- {code}: {pick('title_ru') or '(без названия)'}")
        out.append(
            "INSERT INTO artifacts (code, source_id, title_ru, title_tt, title_en, dating, dimensions, technique,\n"
            "    author, description, artifact_type, origin, authenticity, usage_scope, rights,\n"
            "    quality_flags, plate_text, review_status, confidence, notes)\n"
            f"VALUES ({q(code)}, (SELECT id FROM sources WHERE location = {q(source_location)} LIMIT 1),\n"
            f"    {q(pick('title_ru'))}, {q(pick('title_tt'))}, {q(pick('title_en'))}, {q(pick('dating'))}, "
            f"{q(pick('dimensions'))}, {q(pick('technique'))},\n"
            f"    {q(pick('author'))}, {q(pick('description'))}, {q(atype)}, {q(origin)}, {q(auth)}, {q(scope)}, "
            f"'некоммерческое_mvp',\n"
            f"    {q(quality)}::jsonb, NULL, 'авто', {conf}, {q(pick('notes'))})\n"
            "ON CONFLICT (code) DO UPDATE SET\n"
            "    title_ru = EXCLUDED.title_ru, title_tt = EXCLUDED.title_tt, title_en = EXCLUDED.title_en,\n"
            "    dating = EXCLUDED.dating, dimensions = EXCLUDED.dimensions, technique = EXCLUDED.technique,\n"
            "    author = EXCLUDED.author, description = EXCLUDED.description, artifact_type = EXCLUDED.artifact_type,\n"
            "    origin = EXCLUDED.origin, authenticity = EXCLUDED.authenticity, usage_scope = EXCLUDED.usage_scope,\n"
            "    quality_flags = EXCLUDED.quality_flags, confidence = EXCLUDED.confidence, notes = EXCLUDED.notes\n"
            "  WHERE artifacts.review_status = 'авто';   -- проверенные вручную строки не перезаписываем"
        )
        for frame, file in a["frames"]:
            proxy = f"Датасет/Прокси/{shot_date_raw}/{location}/{frame}.jpg" if shot_date_raw else ""
            raw = f"Датасет/Исходные изображения/{file}"
            out.append(
                f"INSERT INTO artifact_files (artifact_id, file_type, path, frame) VALUES\n"
                f"    ((SELECT id FROM artifacts WHERE code = {q(code)}), 'raw', {q(raw)}, {q(frame)})\n"
                f"ON CONFLICT (path) DO NOTHING;"
            )
            if proxy:
                out.append(
                    f"INSERT INTO artifact_files (artifact_id, file_type, path, frame) VALUES\n"
                    f"    ((SELECT id FROM artifacts WHERE code = {q(code)}), 'proxy', {q(proxy)}, {q(frame)})\n"
                    f"ON CONFLICT (path) DO NOTHING;"
                )
        for pf, pfile in plate_files:
            raw = f"Датасет/Исходные изображения/{pfile}"
            # Одна табличка может относиться к нескольким предметам, а path UNIQUE —
            # поэтому в путь добавляем код предмета через '#'.
            out.append(
                f"INSERT INTO artifact_files (artifact_id, file_type, path, frame) VALUES\n"
                f"    ((SELECT id FROM artifacts WHERE code = {q(code)}), 'plate_raw', {q(raw + '#' + code)}, {q(pf)})\n"
                f"ON CONFLICT (path) DO NOTHING;"
            )
        out.append("")

    out.append("COMMIT;")
    out.append("")
    out.append("-- Проверка:")
    out.append(f"SELECT code, title_ru, artifact_type, origin, usage_scope, review_status FROM artifacts "
               f"WHERE code LIKE {q(prefix + '-%')} ORDER BY code;")

    out_path = Path(args.out) if args.out else csv_path.with_suffix(".sql")
    out_path.write_text("\n".join(out), encoding="utf-8")

    print(f"Предметов: {len(artifacts)}, табличек: {len(plates)}, SQL: {out_path}")
    if warns:
        print(f"\nПредупреждения ({len(warns)}):")
        for w in warns:
            print("  -", w)


if __name__ == "__main__":
    main()
