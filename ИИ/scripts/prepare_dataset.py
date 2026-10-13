"""Local-only immutable-source preparation. Run from any directory; Pillow required."""
from pathlib import Path
import csv, hashlib, json, collections
from PIL import Image, ImageDraw, ImageFilter

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parent
SRC = ROOT / 'Датасет/Элементы'
OUT = AI / 'dataset/texture-v1'
SEED = 20261008

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(name):
    return list(csv.DictReader((SRC / name).open(encoding='utf-8-sig')))

def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = read('manifest.csv')
    prep = {r['code']: r for r in read('lora_preparation.csv')}
    edits = json.loads((AI / 'dataset/captions_selection.json').read_text())
    before = {str(SRC / name): sha(SRC / name) for name in ['manifest.csv', 'lora_preparation.csv']}
    acceptance, records = [], []
    for m in manifest:
        code = m['code']
        for style in ['flat', 'texture']:
            p = SRC / f'processed_{style}' / f'{code}.png'
            acceptance.append(dict(code=code, style=style, source_path=str(p.relative_to(ROOT)),
                sha256=sha(p), accepted_version_date='2026-10-08', decision_recorded='2026-10-11',
                quality_decision='owner_accepted_for_continuation',
                basis='owner instruction and docs/ПЛАН-ДЕЛЕГИРОВАНИЯ-2026-10-08.md',
                expert_authenticity_confirmed=False, agent_external_transfer_authorized=False,
                owner_declared_material_use_allowed=True, written_rights_document=False,
                historical_lora_row=prep[code] if style == 'texture' else None))
        p = SRC / 'processed_texture' / f'{code}.png'
        im = Image.open(p)
        assert im.mode == 'RGBA', (code, im.mode)
        bbox = im.getchannel('A').getbbox()
        assert bbox, code
        # Alpha composite before RGB conversion; transparent pixels become white.
        # Uniform scaling and white padding: never stretch or crop the silhouette.
        crop = im.crop(bbox)
        scale = min(840 / crop.width, 840 / crop.height)
        size = (max(1, round(crop.width*scale)), max(1, round(crop.height*scale)))
        crop = crop.resize(size, Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (1024, 1024), (255,255,255,255))
        pos = ((1024-size[0])//2, (1024-size[1])//2)
        canvas.alpha_composite(crop, pos)
        rgb = canvas.convert('RGB')
        assert rgb.getpixel((0,0)) == (255,255,255)
        target = OUT / 'all_rgb' / f'{code}.png'
        target.parent.mkdir(exist_ok=True)
        rgb.save(target)
        entry = edits[code]
        caption = 'tptrx, isolated ornamental motif, ' + entry['visual'] + ', centered on a white background.'
        target.with_suffix('.txt').write_text(caption + '\n')
        split = entry['split']
        if split in ['train', 'validation']:
            folder = OUT / split
            folder.mkdir(exist_ok=True)
            (folder / target.name).write_bytes(target.read_bytes())
            (folder / target.with_suffix('.txt').name).write_text(caption+'\n')
        records.append(dict(code=code, artifact_code=m['artifact_code'], frame=m['frame'],
            similarity_group=entry.get('group',m['artifact_code']), split=split,
            selection_reason=entry['reason'], texture_source=str(p.relative_to(ROOT)),
            texture_sha256=sha(p), rgb_file=str(target.relative_to(AI)), rgb_sha256=sha(target),
            alpha_bbox=list(bbox), resize=list(size), offset=list(pos), background='#FFFFFF',
            caption=caption, caption_sha256=sha(target.with_suffix('.txt')),
            caption_review='visual review of final texture contact sheets 2026-10-11; neutral visible features',
            source_technique_history=m['source_technique'], ai_review_history=prep[code]['ai_review_note'],
            quality_accepted=True, agent_external_transfer_authorized=False,
            owner_declared_material_use_allowed=True, written_rights_document=False,
            seed=SEED))
    # Detect leakage across artifacts and manually merged similar-object clusters.
    for key in ['artifact_code','similarity_group']:
        groups=collections.defaultdict(set)
        for r in records:
            if r['split'] in ['train','validation']: groups[r[key]].add(r['split'])
        assert all(len(v)==1 for v in groups.values()), (key, groups)
    save_json(OUT / 'owner_acceptance.json', acceptance)
    # Snapshot old assessments as history, including flat remarks. Never change source.
    (OUT/'historical_batch_assessments.json').write_bytes((SRC/'processed_batch_assessments.json').read_bytes())
    with (OUT / 'training_manifest.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    for split in ['train','validation']:
        with (OUT / split / 'metadata.jsonl').open('w') as f:
            for r in records:
                if r['split']==split: f.write(json.dumps({'file_name':r['code']+'.png','text':r['caption']})+'\n')
    after = {p:sha(Path(p)) for p in before}
    assert before == after
    assert all(sha(ROOT/r['source_path'])==r['sha256'] for r in acceptance)
    counts={s:dict(files=sum(r['split']==s for r in records), artifacts=len({r['artifact_code'] for r in records if r['split']==s})) for s in ['train','validation','reserve','out_of_scope']}
    save_json(OUT/'checks.json',dict(version='texture-v1',seed=SEED,counts=counts,
        source_files=110,source_artifacts=len({r['artifact_code'] for r in records}),
        acceptance_rows=len(acceptance),masters_unchanged=True,input_csv_sha256=before,
        manifest_sha256=sha(OUT/'training_manifest.csv'),
        artifact_and_similarity_split_leakage=False, background_check='white corner all 110',
        rights_status='owner_declares_all_materials_allowed_2026-10-11_no_written_document',
        external_operator='owner_only; agent has no permission to create/upload/pay/run on Selectel',
        training_executed=False))
    # Structural reference from an actual validation motif; output is a template, not AI.
    ref='TP-E-020'
    p=SRC/'processed_texture'/f'{ref}.png'
    im=Image.open(p).convert('RGBA');a=im.getchannel('A');box=a.getbbox();im=im.crop(box);im.thumbnail((640,640),Image.Resampling.LANCZOS)
    template=Image.new('RGBA',(1024,1024),'white');template.alpha_composite(im,((1024-im.width)//2,(1024-im.height)//2));template.convert('RGB').save(OUT/'structure_reference.png')
    silhouette=Image.new('L',(1024,1024),0)
    silhouette.paste(im.getchannel('A'),((1024-im.width)//2,(1024-im.height)//2))
    silhouette.point(lambda p:255 if p>=128 else 0).save(OUT/'structure_alpha.png')
    save_json(OUT/'structure_reference.json',dict(code=ref,source_sha256=sha(p),purpose='validation-only structural conditioning',not_training_data=True,render='alpha composite on white, centered, maximum 640 px'))
    print(json.dumps(counts,ensure_ascii=False))

if __name__ == '__main__': main()
