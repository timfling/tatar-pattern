#!/usr/bin/env python3
"""Read-only reproducible checks of catalog provenance, files and protected inputs."""
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'Датасет/Элементы'


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as fh:
        return list(csv.DictReader(fh))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    active = csv_rows(OUT / 'manifest.csv')
    reserve = csv_rows(OUT / 'reserve_manifest.csv')
    refs = csv_rows(OUT / 'supplemental_references.csv')
    all_rows = active + reserve + refs
    codes = [r['code'] for r in all_rows]
    assert len(codes) == len(set(codes)), 'Duplicate IDs'
    expected_crops = {r['crop_file'] for r in all_rows}
    missing, exact = [], defaultdict(list)
    for r in all_rows:
        for field in ('source_raw', 'crop_file', 'crop_source_file'):
            if not (ROOT / r[field]).is_file():
                missing.append((r['code'], field))
        with Image.open(ROOT / r['crop_file']) as im:
            exact[hashlib.sha256(im.convert('RGB').tobytes()).hexdigest()].append(r['code'])
    assert not missing, missing
    duplicates = [group for group in exact.values() if len(group) > 1]
    assert not duplicates, duplicates
    by_frame = {}
    for path in (ROOT / 'Датасет/Разметка/01.09.2026').glob('*/annotations.csv'):
        for r in csv_rows(path):
            by_frame[r['frame']] = (r, path.parent.name)
    new = [r for r in active if r['replaces_code']]
    old_ids = {r['code'] for r in reserve}
    assert len({r['replaces_code'] for r in new}) == len(new), 'Re-used replacement target'
    for r in new:
        assert r['replaces_code'] in old_ids
        assert r['plate_frames'] and r['source_title_ru']
        assert r['source_origin'] == 'татарское' and r['source_usage_scope'] == 'рид_и_обучение'
        for plate in r['plate_frames'].split(','):
            _, location = by_frame[plate]
            assert (ROOT / 'Датасет/Прокси/01.09.2026' / location / (plate + '.jpg')).is_file()
    for r in active + reserve:
        assert r['source_artifact_code'] == by_frame[r['frame']][0]['artifact_code']
        assert (ROOT / r['source_proxy']).is_file()
    baseline = json.loads((OUT / 'audit/2026-10-02/protected_sha256_before.json').read_text())
    changed = [p for p, digest in baseline.items() if not (ROOT / p).is_file() or sha(ROOT / p) != digest]
    assert not changed, ('Protected files changed', changed)
    index = json.loads((OUT / 'source_previews/index.json').read_text())
    for frame, info in index.items():
        assert sha(ROOT / info['source_raw']) == info['source_raw_sha256'], frame
        assert sha(ROOT / info['preview_file']) == info['preview_sha256'], frame
    provenance = json.loads((OUT / 'processed_provenance.json').read_text())
    for r in provenance:
        assert sha(ROOT / r['processed_file']) == r['processed_sha256'], r['code']
        assert sha(ROOT / r['reference_crop']) == r['reference_sha256'], r['code']
    prompts = csv_rows(OUT / 'higgsfield_prompts.csv')
    assert {r['code'] for r in prompts} == {r['code'] for r in active + refs}
    assert len({r['save_as'] for r in prompts}) == len(prompts)
    for r in prompts:
        assert (ROOT / r['input_crop']).is_file()
        assert Path(r['save_as']).parent == Path('Датасет/Элементы/processed_flat')
    validation = json.loads((OUT / 'processed_validation.json').read_text())
    assert not validation['unexpected_files']
    assert all(r.get('assessment_state', '').startswith('оценка ИИ соответствует') for r in validation['files'] if r['present'])
    report = {'primary_candidates': len(active), 'primary_frames': len({r['frame'] for r in active}),
              'primary_artifacts': len({r['artifact_code'] for r in active}), 'reserve': len(reserve),
              'supplemental': len(refs), 'total_known_crop_files': len(expected_crops),
              'new_replacements': len(new), 'new_replacements_with_plates': len(new),
              'prompt_rows': len(prompts), 'legacy_processed_preserved': len(provenance),
              'technical_processed_valid': validation['readable_and_min_size'],
              'short_primary_crop_side_below_256': sum(min(map(int, r['crop_size'].split('x'))) < 256 for r in active),
              'unique_codes': True, 'exact_duplicate_crop_pixels': 0,
              'protected_snapshot_files_unchanged': len(baseline), 'raw_previews_hash_verified': len(index),
              'protected_input_changes': changed,
              'all_candidates_require_human': all(r['status'] == 'кандидат, требуется человек' for r in active),
              'human_decisions_present': sum(bool(r['human_decision']) for r in active),
              'note': 'Техническая проверка не доказывает этническую атрибуцию или человеческую приёмку.'}
    (OUT / 'audit/2026-10-02/final_checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
