#!/usr/bin/env python3
"""Refresh dated review exports from manual assessments and the current manifests."""
import csv
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'Датасет/Элементы'


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    active = read_csv(OUT / 'manifest.csv')
    reserve = read_csv(OUT / 'reserve_manifest.csv')
    current = {r['code']: r for r in active + reserve}
    original = {r['code']: r for r in read_csv(OUT / 'audit/2026-10-02/before_manifest.csv')}
    assessed = json.loads((OUT / 'processed_assessments.json').read_text())['items']
    rows = []
    for item in assessed:
        p = ROOT / item['processed_file']
        same = p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == item['processed_sha256']
        rec = current[item['code']]
        rows.append({**item, 'assessment_state': 'соответствует файлу' if same else 'УСТАРЕЛА: файл изменен/отсутствует',
                     'current_frame': rec['frame'], 'selection_status': rec['selection_status'],
                     'selection_reason': rec['selection_reason'],
                     'parameter_controls': 'масштаб, поворот, размещение/повтор — растровый PNG; для независимых цветов нужны маски/SVG'})
    write_csv(OUT / 'processed_assessments.csv', rows)
    changes = []
    for rec in active:
        old = original.get(rec.get('replaces_code') or rec['code'])
        if not old:
            continue
        replacement = bool(rec['replaces_code'])
        if replacement or rec['frame'] != old['frame'] or rec['box_1000'] != old['box_1000'] or rec['description'] != old['description']:
            retired = current.get(rec['replaces_code'], {})
            changes.append({'change': 'новый мотив вместо слабого источника' if replacement else 'улучшена вырезка того же мотива',
                            'old_code': old['code'], 'new_code': rec['code'],
                            'old_frame': old['frame'], 'new_frame': rec['frame'],
                            'old_box_1000': old['box_1000'], 'new_box_1000': rec['box_1000'],
                            'reason': retired.get('selection_reason') or rec['place_description'],
                            'crop_file': rec['crop_file'], 'crop_size': rec['crop_size'],
                            'artifact_code': rec['artifact_code'], 'plate_frames': rec['plate_frames'],
                            'source_title_ru': rec['source_title_ru'], 'source_dating': rec['source_dating'],
                            'source_technique': rec['source_technique'], 'status': 'отобрано ИИ; требуется человек'})
    write_csv(OUT / 'replacement_log.csv', changes)
    picks = [r for r in active if r['replaces_code']]
    folder = OUT / 'replacement_review'
    folder.mkdir(exist_ok=True)
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 19)
    for start in range(0, len(picks), 8):
        sheet = Image.new('RGB', (1600, 1740), '#f4f4ef')
        draw = ImageDraw.Draw(sheet)
        draw.text((15, 8), 'Новые кандидаты на замену | фото-вырезки, требуется человек', font=font, fill='#111')
        for j, rec in enumerate(picks[start:start + 8]):
            x, y = (j % 2) * 800, 45 + (j // 2) * 420
            with Image.open(ROOT / rec['crop_file']) as im:
                im.thumbnail((760, 324))
                sheet.paste(im, (x + (800 - im.width) // 2, y + (324 - im.height) // 2))
            draw.text((x + 10, y + 328), f"{rec['code']} вместо {rec['replaces_code']} | {rec['frame']} | {rec['crop_size']}", font=font, fill='#111')
            draw.text((x + 10, y + 355), rec['description'][:63], font=font, fill='#333')
            draw.text((x + 10, y + 382), 'Табличка ' + rec['plate_frames'] + ' | ' + rec['source_title_ru'][:48], font=font, fill='#555')
        sheet.save(folder / f'sheet_{start // 8 + 1:02}.jpg', quality=94)
    count = lambda state: sum(r['decision_recommendation'] == state for r in assessed)
    lines = [
        '# Оценка пилота и обновление источников — 02.10.2026', '',
        'Критерий владельца: визуальное сходство формы на 90–100%, с допустимой коррекцией перспективы, складок и изгиба. Попиксельное совпадение не требуется. Процент сходства не измерен; ниже качественные рекомендации ИИ, не человеческая верификация.', '',
        '## Уже обработанные файлы', '',
        f"Всего 14 PNG. {count('usable_raster') + count('usable_raster_conditional') + count('usable_auxiliary')} пригодны/условно пригодны для растрового MVP после ручного решения; один (TP-E-106) рекомендовано поправить; два (TP-E-046, TP-E-050) пересоздать из-за другого числа лепестков.", '',
        'TP-E-001 и TP-E-002 технически подходят для визуального MVP, но конкретная культурная атрибуция их источника не установлена; они вынесены в резерв. TP-E-083 условно подходит при критерии владельца; мелкий ажур следует отдельно сверить с крупной вырезкой. Поворот TP-E-114 выполнен владельцем и учтен.', '',
        '**Конструктор.** RGBA позволяет размещение, масштаб, поворот и повтор. Для независимой смены цветов и чистого масштабирования нужны цветовые маски либо SVG. Раппорты и бордюры требуют отдельной проверки стыков. Прозрачность у всех 14 настоящая; старый скрипт неверно показывал скрытые RGB как черный фон/свечение, это исправлено.', '',
        '**LoRA.** Для выбранной в логе БД единой модели плоских отрисовок текущие изображения нельзя смешивать без подготовки: в них разные фактуры нитей, кожи, керамики и металла. Подготовлен следующий проход в плоском стиле. В обучение не включены никакие файлы автоматически. lora_preparation.csv содержит 110 черновых нейтральных подписей и музейные поля с ссылкой на исходную разметку. Разделять train/validation следует по split_group_artifact, чтобы ракурсы/мотивы одного предмета не попадали в обе части. Белый фон делать в отдельной обучающей копии; альфа остается в мастере.', '',
        '| Код | Конструктор | Что видно / следующий шаг |', '| --- | --- | --- |'
    ]
    for item in assessed:
        lines.append(f"| {item['code']} | {item['constructor_assessment']} | {item['visual_evidence']} {item['next_action']} |")
    lines += ['', '## Замены и улучшение вырезок', '',
              f"В основной очереди {len(active)} кандидатов; {len(reserve)} прежних строк сохранены в reserve_manifest.csv. Добавлено {len(picks)} новых мотивов TP-E-120…TP-E-135 вместо слабых/неатрибутированных источников. У старых кодов и 14 пользовательских файлов сохранена история; ни один код не присвоен другому мотиву.", '',
              'Все новые мотивы имеют привязанную музейную табличку в исходном CSV. Техника, автор, дата и название относятся к предмету, а не к автоматически придуманной атрибуции отдельного мотива. Современные авторские образцы KS-9455 помечены датой 2013 и автором Р. Шамсутдинов; крымские источники сохраняют указание Крыма. Происхождение конкретного узора по месту экспонирования не выводилось.', '',
              'Native camera JPEG извлечен непосредственно из ARW без ИИ и увеличения; размер исходного JPEG 7008×4672. Ориентация сопоставлена с неизмененным EXIF-ориентированным прокси. Это техническое сопоставление источников, а не требование попиксельного совпадения с генерацией.', '',
              'Крупнее переснятые ракурсы того же предмета использованы для TP-E-041/042 (DSC9559), TP-E-043/044 (DSC9565), TP-E-072 (DSC9627). TP-E-034/046/050/083/085/106 получили уточненные границы. TP-E-114/115 приведены к общей системе координат EXIF. Полная история — replacement_log.csv.', '',
              'DSC9556/9562 остаются отложенными: владелец атрибуцию не уточнял; соседние таблички описывают другие предметы. Кадры DSC9680/81/82/88/89 и DSC9707/08 не повышены из только_обучение в рид_и_обучение. Результаты просмотра всех 11 кадров записаны в replacement_shortlist.csv.', '',
              '## Следующий проход Higgsfield', '',
              'higgsfield_prompts.csv: 110 основных строк и 2 вспомогательных KS-9448. Загружать актуальный input_crop; сохранение строго по save_as в processed_flat/. Эта отдельная папка сохраняет предыдущие 14 пользовательских файлов. Для всех строк указаны плоский стиль, разрешенная коррекция геометрии и запрет новых частей. Индивидуальные ограничения стоят в конце промпта.', '',
              'Сначала TP-E-046 и TP-E-050; затем TP-E-106 и несколько новых замен. После ручной сверки можно продолжить оставшийся проход. SVG и фактическая тренировочная выборка этим обновлением не созданы.', '',
              'Исходная разметка, STATUS, RAW, прокси, миграции и БД не редактировались. Ничего не помечено верифицированным от имени человека. Условия прав из owner_reviews.json сохранены.']
    (OUT / 'REVIEW-2026-10-02.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'processed_assessments': len(rows), 'replacement_log_rows': len(changes), 'new_motifs': len(picks)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
