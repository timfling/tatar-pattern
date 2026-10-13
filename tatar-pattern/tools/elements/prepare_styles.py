#!/usr/bin/env python3
"""Create a separate texture-preserving pass and preparation manifests.

This script reads the existing flat prompt table but never rewrites it. Both
style variants use the same source crop and have different output directories.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from prompt_scope import selection_instruction

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "Датасет/Элементы"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows):
    if not rows:
        raise ValueError(f"Refusing to create empty output: {path.name}")
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def texture_preservation_note(rec):
    technique = (rec.get("source_technique", "") + " " + rec.get("owner_technique", "")).lower()
    if any(word in technique for word in ("бумага", "акварел", "тушь", "рисунок")):
        return ("Это рисунок на бумаге: сохрани именно видимые мазки краски, линии туши, "
                "штриховку и зерно бумаги. Не превращай их в нитки, рельефную вышивку или металл.")
    if any(word in technique for word in ("ткан", "вышив", "шить", "нит", "парч", "бархат")):
        return ("Сохрани реальный материал текстиля: направление нитей, рисунок и рельеф видимых "
                "стежков, плетение и характер блеска металлической нити. Не добавляй стежки в "
                "гладких участках и не выпрямляй стежки в геометрическую линию, если на фото они неровные.")
    if any(word in technique for word in ("серебр", "металл", "скань", "чеканк", "гравир", "фольг")):
        return ("Сохрани реальную фактуру металла, видимую скань или гравировку, тонкие блики и "
                "тени рельефа, а также число камней и их цвет. Не создавай новые отверстия, гравированные линии или вставки.")
    if any(word in technique for word in ("керамик", "глазур", "глин", "рельеф")):
        return ("Сохрани фактуру глазури/материала и только действительно видимый рельеф и его тени. "
                "Не делай неглубокую линию объемным валиком и не добавляй кракелюр или зерно по догадке.")
    if any(word in technique for word in ("кож", "мозаик")):
        return ("Сохрани реальную фактуру кожи и стык видимых кожаных деталей; исправлять изгиб "
                "предмета допустимо, менять форму шва или добавлять прострочку нельзя.")
    return ("Сохрани фактуру, материал, блеск, зерно, рельеф и тональные переходы, только если они "
            "действительно видны в вырезке; не выдумывай материал или микродетали.")


def make_texture_prompt(rec):
    caution = ("Если мотив стерт, перекрыт бликом, закрыт соседней деталью или обрезан, "
               "оставь фрагмент неполным; не дорисовывай скрытое.")
    technique_note = texture_preservation_note(rec)
    prompt = (
        f"Используй вырезку как единственный визуальный источник. "
        f"{selection_instruction(rec)} "
        "Подготовь отдельную текстуросохраняющую версию для будущей LoRA: сохраняй вид фактически "
        "сфотографированного материала, а не перерисовывай его в новый стиль. " + technique_note + " "
        "Сохрани реальные цвет, освещение, мелкие неровности, фактурные переходы и видимые мягкие тени. "
        "Не добавляй искусственное зерно, резкость, микродетали, объем, блеск или материал, которых "
        "нет на фотографии. Не превращай мотив в плоскую векторную графику, живопись, CGI или вышивку, "
        "если исходник не показывает именно такую технику. "
        "Допускается исправить перспективу, отражения и искажения от изгиба поверхности и складок только там, "
        "где форма мотива однозначно видна. Характерные контуры, число лепестков, вставок, "
        "стежков/составных деталей, их относительные размеры и размещение должны оставаться "
        "визуально похожими на источник на 90–100%; попиксельное совпадение не требуется. "
        "Сохрани фотографическую фактуру самого мотива; удаляй фон предмета, соседние мотивы, "
        "раму/витрину и отражения только за границами мотива. Внутри настоящих отверстий оставь "
        "прозрачность, а неотверстые участки ткани или основы сохрани как часть исходного материала. "
        + caution + " Не зеркаль и не поворачивай мотив. "
        "Сохрани исходное разрешение, если сервис его поддерживает; не увеличивай изображение "
        "искусственно. Верни PNG с прозрачностью вокруг мотива; если альфа недоступна, используй "
        "однотонный белый фон без шахматной сетки, свечения, виньетки, рамки и подписи."
    )
    return prompt


def main():
    manifest = read_csv(OUT / "manifest.csv")
    flat_rows = read_csv(OUT / "higgsfield_prompts.csv")
    if len(manifest) != len({r["code"] for r in manifest}):
        raise ValueError("Duplicate active motif code")
    flat = {r["code"]: r for r in flat_rows}
    missing_flat = sorted({r["code"] for r in manifest} - set(flat))
    if missing_flat:
        raise ValueError("Missing corresponding flat prompt(s): " + ", ".join(missing_flat))
    pilot = {"TP-E-013", "TP-E-034", "TP-E-037", "TP-E-046", "TP-E-050", "TP-E-053",
             "TP-E-061", "TP-E-072", "TP-E-083", "TP-E-093", "TP-E-106", "TP-E-114"}
    texture, constructor, lora = [], [], []
    for rec in manifest:
        previous = flat[rec["code"]]
        textured_path = f"Датасет/Элементы/processed_texture/{rec['code']}.png"
        flat_path = f"Датасет/Элементы/processed_flat/{rec['code']}.png"
        if rec["crop_file"] != previous["input_crop"]:
            raise ValueError(f"Style passes do not share the same source crop for {rec['code']}")
        if (ROOT / rec["crop_file"]).is_file() is False:
            raise FileNotFoundError(ROOT / rec["crop_file"])
        blocked = rec.get("source_gate", "").startswith("ПРОВЕРИТЬ")
        batch = "ПАУЗА — проверить допуск источника" if blocked else (
            "пилот текстуры 1" if rec["code"] in pilot else "основной проход")
        texture.append({
            "code": rec["code"], "artifact_code": rec["artifact_code"], "frame": rec["frame"],
            "input_crop": rec["crop_file"], "input_size": rec["crop_size"],
            "source_raw": rec["source_raw"], "source_title_ru": rec["source_title_ru"],
            "source_dating": rec["source_dating"], "source_technique": rec["source_technique"],
            "source_author": rec["source_author"], "owner_title_ru": rec["owner_title_ru"],
            "owner_technique": rec["owner_technique"], "plate_frames": rec["plate_frames"],
            "origin": rec["source_origin"], "authenticity": rec["source_authenticity"],
            "usage_scope": rec["source_usage_scope"], "source_gate": rec.get("source_gate", ""),
            "quality_limitations": rec["quality_limitations"], "batch": batch,
            "replaces_code": rec["replaces_code"], "style": "texture-preserving; separate from flat dataset",
            "prompt_version": "texture-v2-2026-10-04", "prompt": make_texture_prompt(rec),
            "processing_action": "не запускать до проверки атрибуции/допуска источника" if blocked else "текстуросохраняющая версия; сверить с источником; требуется человек",
            "save_as": textured_path, "flat_save_as": flat_path,
            "previous_flat_prompt": previous["save_as"],
            "review_after": "Сверить форму, число деталей и реальную фактуру с native source crop; затем вручную принять; caption должен соответствовать результату.",
        })
        constructor.append({
            "code": rec["code"], "artifact_code": rec["artifact_code"], "frame": rec["frame"],
            "flat_file": flat_path, "file_present": "да" if (ROOT / flat_path).is_file() else "нет",
            "motif_class": rec["motif_class"], "description": rec["description"],
            "split_group_artifact": rec["artifact_code"], "human_decision": rec["human_decision"],
            "status": "требуется плоская версия и ручная приёмка",
            "parameter_limits": "масштаб, поворот, позиционирование/повтор; отдельная перекраска требует масок/SVG",
        })
        lora.append({
            "code": rec["code"], "artifact_code": rec["artifact_code"],
            "image_file": textured_path, "file_present": "да" if (ROOT / textured_path).is_file() else "нет",
            "neutral_caption_ru_draft": rec.get("caption_override") or "Орнаментальный мотив: " + rec["description"] + ".",
            "caption_status": "черновик; сверить с принятой texture-preserving версией",
            "split_group_artifact": rec["artifact_code"], "frame": rec["frame"],
            "source_title_ru": rec["source_title_ru"], "source_dating": rec["source_dating"],
            "source_technique": rec["source_technique"], "source_author": rec["source_author"],
            "owner_title_ru": rec["owner_title_ru"], "owner_technique": rec["owner_technique"],
            "source_description": rec["source_description"], "plate_frames": rec["plate_frames"],
            "source_annotation": rec["annotation_file"], "source_authenticity": rec["source_authenticity"],
            "source_usage_scope": rec["source_usage_scope"], "human_decision": rec["human_decision"],
            "ai_retouched": "true" if (ROOT / textured_path).is_file() else "false",
            "training_ready": "нет; требуется texture-файл и решение человека",
            "rights_limitations": rec["rights_limitations"],
        })
    (OUT / "processed_texture").mkdir(exist_ok=True)
    (OUT / "processed_flat").mkdir(exist_ok=True)
    write_csv(OUT / "higgsfield_prompts_texture.csv", texture)
    write_csv(OUT / "constructor_preparation.csv", constructor)
    write_csv(OUT / "lora_preparation.csv", lora)
    report = {"textured_prompts": len(texture), "texture_pilot_prompts": sum(r["batch"] == "пилот текстуры 1" for r in texture),
              "texture_paused_for_source_gate": sum(r["batch"].startswith("ПАУЗА") for r in texture),
              "constructor_rows": len(constructor), "lora_rows": len(lora),
              "texture_output_dir": "processed_texture", "flat_output_dir": "processed_flat",
              "texture_files_present": sum(r["file_present"] == "да" for r in lora),
              "flat_files_present": sum(r["file_present"] == "да" for r in constructor),
              "same_source_crop_per_code": True, "flat_prompt_csv_rewritten": False,
              "supplemental_or_reserve_in_lora_prompts": False,
              "loRA_training_started": False, "human_accepted": 0,
              "note": "Две производные формируются из одного атрибутированного источника. Не смешивать стили в одной LoRA-выборке."}
    (OUT / "style_preparation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
