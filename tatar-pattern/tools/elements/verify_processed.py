#!/usr/bin/env python3
"""Validate PNGs and composite real alpha correctly. No automatic motif acceptance."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageStat

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'Датасет/Элементы'
FONT_PATH = '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'


def font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default()


def composite(im, background):
    # RGB conversion alone exposes hidden RGB in transparent pixels as a fake glow.
    rgba = ImageOps.exif_transpose(im).convert('RGBA')
    base = Image.new('RGBA', rgba.size, background)
    base.alpha_composite(rgba)
    return base.convert('RGB')


def read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding='utf-8-sig', newline='') as fh:
        return list(csv.DictReader(fh))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=OUT)
    parser.add_argument('--results-dir', choices=('processed', 'processed_flat', 'processed_texture'), default='processed')
    args = parser.parse_args()
    out = args.output_dir
    primary = read_csv(out / 'manifest.csv')
    supplemental = read_csv(out / 'supplemental_references.csv') if args.results_dir != 'processed_texture' else []
    reserve = read_csv(out / 'reserve_manifest.csv') if args.results_dir == 'processed' else []
    manifest = primary + supplemental + reserve
    codes = [r['code'] for r in manifest]
    if len(codes) != len(set(codes)):
        raise ValueError('Duplicate result code across inventories')
    provenance_path = out / 'processed_provenance.json'
    provenance = {r['code']: r for r in json.loads(provenance_path.read_text())} if provenance_path.exists() else {}
    assessment_path = out / 'processed_assessments.json'
    assessments = {r['code']: r for r in json.loads(assessment_path.read_text()).get('items', [])} if assessment_path.exists() else {}
    result_dir = out / args.results_dir
    review_dir_name = {'processed': 'processed_review',
                       'processed_flat': 'processed_flat_review',
                       'processed_texture': 'processed_texture_review'}[args.results_dir]
    review_dir = out / review_dir_name
    review_dir.mkdir(exist_ok=True)
    results, valid = [], []
    for item in manifest:
        code = item['code']
        path = result_dir / (code + '.png')
        result = {'code': code, 'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                  'selection_status': item.get('selection_status', 'active'),
                  'present': path.is_file(), 'valid_image': False, 'size': '', 'mode': '',
                  'alpha_present': False, 'transparent_fraction': None, 'near_opaque_fraction': None,
                  'semi_transparent_fraction': None, 'alpha_bbox': None, 'issues': []}
        if path.is_file():
            try:
                with Image.open(path) as im:
                    im.verify()
                with Image.open(path) as im:
                    rgba = ImageOps.exif_transpose(im).convert('RGBA')
                    rgb = composite(im, 'white')
                    result.update(size=f'{rgba.width}x{rgba.height}', mode=im.mode,
                                  alpha_present='A' in im.getbands() or 'transparency' in im.info)
                    alpha = rgba.getchannel('A')
                    hist = alpha.histogram()
                    n = rgba.width * rgba.height
                    result.update(transparent_fraction=round(hist[0] / n, 4),
                                  near_opaque_fraction=round(sum(hist[250:]) / n, 4),
                                  semi_transparent_fraction=round(sum(hist[1:250]) / n, 4),
                                  alpha_bbox=alpha.point(lambda value: 255 if value >= 16 else 0).getbbox())
                    if rgba.width < 256 or rgba.height < 256:
                        result['issues'].append('короткая сторона меньше 256 px')
                    if hist[0] == n:
                        result['issues'].append('изображение полностью прозрачное')
                    if max(ImageStat.Stat(rgb).stddev) < 3:
                        result['issues'].append('почти однородное изображение')
                    result['valid_image'] = not result['issues']
                    result['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                    if not result['alpha_present']:
                        result['issues'].append('нет альфа-канала; проверить сплошной фон вручную')
                    old = provenance.get(code, {}) if args.results_dir == 'processed' else {}
                    source = ROOT / item['crop_file']
                    pilot_reference = ROOT / old.get('reference_crop', item['crop_file'])
                    if not source.is_file() or not pilot_reference.is_file():
                        raise FileNotFoundError('нет исходной вырезки')
                    if old and hashlib.sha256(pilot_reference.read_bytes()).hexdigest() != old['reference_sha256']:
                        raise ValueError('изменен сохраненный вход пилота')
                    result['original_pilot_reference'] = old.get('reference_crop', '')
                    assessment = assessments.get(code, {}) if args.results_dir == 'processed' else {}
                    result['assessment_state'] = 'требуется новый визуальный просмотр'
                    if assessment:
                        if result['sha256'] == assessment['processed_sha256']:
                            result['assessment_state'] = 'оценка ИИ соответствует этому файлу; требуется человек'
                            result['constructor_assessment'] = assessment['constructor_assessment']
                        else:
                            result['assessment_state'] = 'оценка устарела: файл обработки изменился'
                    if result['sha256'] == hashlib.sha256(source.read_bytes()).hexdigest():
                        result['issues'].append('файл совпадает с исходной вырезкой')
                    result['comparison_source'] = str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else str(source)
                    if result['valid_image']:
                        valid.append((item, path, source))
            except Exception as exc:
                result['valid_image'] = False
                result['issues'].append(f'ошибка изображения/источника: {exc}')
        results.append(result)
    sheets = []
    for start in range(0, len(valid), 4):
        page = start // 4 + 1
        canvas = Image.new('RGB', (1800, 1650), '#f4f4ef')
        draw = ImageDraw.Draw(canvas)
        draw.text((18, 8), f'Источник / PNG на белом / PNG на зелёном | {args.results_dir} | лист {page}', fill='#111', font=font(23))
        for j, (item, path, source) in enumerate(valid[start:start + 4]):
            y = 48 + j * 397
            for col, (file, background) in enumerate(((source, 'white'), (path, 'white'), (path, '#214f40'))):
                with Image.open(file) as im:
                    im = composite(im, background)
                    im.thumbnail((578, 338))
                    x = col * 600 + (600 - im.width) // 2
                    canvas.paste(im, (x, y + (338 - im.height) // 2))
            draw.text((12, y + 344), f"{item['code']} | {item['description'][:87]}", fill='#222', font=font(17))
            draw.text((12, y + 370), 'Сходство формы 90–100%; перспектива/складки могут быть исправлены. Приёмка человеком.', fill='#555', font=font(16))
        sheet = review_dir / f'sheet_{page:02}.jpg'
        canvas.save(sheet, quality=92)
        sheets.append(sheet.name)
    unexpected = sorted(p.name for p in result_dir.glob('*') if p.is_file() and not p.name.startswith('.') and p.name not in {code + '.png' for code in codes})
    primary_codes = {r['code'] for r in primary}
    supplemental_codes = {r['code'] for r in supplemental}
    report = {'results_dir': args.results_dir, 'expected_active': len(primary),
              'expected_supplemental': len(supplemental),
              'expected_active_and_supplemental': len(primary) + len(supplemental),
              'known_reserve_candidates': len(reserve), 'present': sum(x['present'] for x in results),
              'present_active': sum(x['present'] and x['code'] in primary_codes for x in results),
              'present_supplemental': sum(x['present'] and x['code'] in supplemental_codes for x in results),
              'missing_active': [x['code'] for x in results if not x['present'] and x['code'] in primary_codes],
              'missing_supplemental': [x['code'] for x in results if not x['present'] and x['code'] in supplemental_codes],
              'readable_and_min_size': sum(x['valid_image'] for x in results), 'review_sheets': sheets,
              'unexpected_files': unexpected, 'human_motif_acceptance': 'не выполнена; техническая проверка и рекомендации ИИ не являются приёмкой',
              'files': results}
    name = {'processed': 'processed_validation.json',
            'processed_flat': 'processed_flat_validation.json',
            'processed_texture': 'processed_texture_validation.json'}[args.results_dir]
    (out / name).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'files'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
