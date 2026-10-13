#!/usr/bin/env python3
"""Revise marked Higgsfield prompts without increasing any original prompt length."""
import csv, hashlib, json
from collections import Counter
from pathlib import Path
from PIL import Image, ImageOps
ROOT=Path(__file__).resolve().parents[3]; OUT=ROOT/'Датасет/Элементы'
FLAT_STYLE=set('019 020 035 036 037 039 040 041 042 055 056 059 060 067 071 073 074 075 076 077 078 079 080 081 082 083 084 085 086 087 088 089 094 102 106 107 108 109 128 129 131 132 134'.split())
# The formerly misnamed file TP-E-035 was visually the fan TP-E-034; its flat-style flag follows the image.
FLAT_STYLE.remove('035'); FLAT_STYLE.add('034')
FLAT_FIX={
'008':'Выдели только угловой фрагмент; не заменяй его центральной розеткой.',
'032':'Сохрани пальметту, две боковые волюты и исходные вырезы; не превращай их в широкие лепестки.',
'043':'Точно сохрани порядок пересечений переплетения, петли и окончания полос.',
'054':'Оставь тонкую ветку с округлыми почками; не добавляй крупный лист.',
'056':'Не включай соседний крупный перистый мотив; границу веди по выбранной ветке с малым цветком.',
'080':'Сохрани видимые ажурные подвески и их окончания; не заменяй бусинами и не достраивай скрытое.',
'081':'Сохрани все четыре малые цветочные подвески, не сокращай их число.',
'099':'Сохрани цвета источника: тёмный центр и золотистый внешний узор; не меняй их местами.',
'102':'Оставь ряд отдельных разноцветных бутонов; не объединяй их в один цветок.',
'108':'Сохрани один наклонный лист исходной формы; не превращай его в типовое перо или ветку.',
'115':'Сохрани отдельные границы двухцветной волны; не сливай внутреннюю каплю с основой кожи.',
'127':'Сохрани положение зубчатого ответвления сверху, как в источнике; не переноси его вниз.'}
TEXTURE_FIX={
'008':'Выдели исходный угловой мотив, не медальон; сохрани исходную асимметрию боковых частей.',
'031':'Сохрани два гравированных листа и завитки; не заменяй гравировку объёмным литым орнаментом.',
'032':'Сохрани видимый контур и гравировку пальметты; не добавляй лопасти, отверстия или рельеф.',
'043':'Сохрани видимое исходное переплетение и его окончания; не перестраивай петли и пересечения.',
'058':'Не добавляй соседнюю верхнюю ветку; оставь только мотив внутри заданной границы.',
'073':'Сохрани асимметричный контур лепестков и исходный центр; не делай цветок радиально правильным.',
'076':'Сохрани зигзагообразную кайму и отдельные цветочки; не замыкай их в медальоны.',
'080':'Не достраивай невидимые подвески; сохрани только показанные ажурные формы и окончания.',
'082':'Сохрани ажурные нижние подвески; не упрощай их до круглых бусин.',
'084':'Сохрани боковые шарики и соединители в составе модуля.',
'086':'Сохрани прямоугольную пластину и её края; не заменяй овальной оправой.',
'102':'Сохрани ряд отдельных бутонов и промежутки между ними; не своди в один цветок.',
'108':'Выдели один наклонный лист; не добавляй к нему ветки или другие листья.',
'115':'Сохрани просвет/внутреннюю деталь и её границу; не заполняй его сплошной кожей.',
'116':'Сохрани исходную неглубокую гравировку и контур цепи; не заменяй их объёмными белыми деталями.',
'117':'Сохрани верхние золотистые продолжения волют; не обрезай их и не заменяй нижней формой.',
'119':'Сохрани рисунок и бумажные мазки/линии; не превращай их в вышивальные нити.'}
FLAT_REPLACES=[
('Подготовь плоскую графическую отрисовку для орнаментального конструктора: четкие контуры, сплошные цветовые области и читаемые внутренние линии.','Подготовь строгую плоскую графику: чистые контуры, ровные заливки и смысловые линии узора.'),
('Сохрани число лепестков, вставок, завитков, отверстий и соединений и характерные соотношения размеров.','Сохрани исходный состав, число и пропорции частей.'),
('Допустима коррекция перспективы, складок и изгиба поверхности, умеренное выравнивание линий; попиксельное совпадение не требуется.','Исправляй перспективу и складки только при ясном контуре; не меняй геометрию узора.'),
('Цель — сходство с исходным мотивом на 90–100%, без новых деталей и другой схемы узора. Не заменяй его стандартной розеткой.','Сходство формы — 90–100%; не добавляй и не заменяй части.'),
('Удали фон предмета и соседние мотивы. Убери фотографическую фактуру ткани, волокон, кожи, металла и керамики, тени, объем, блеск и свечение; сохрани видимые границы деталей, рисунок и исходные цвета.','Удали фон и соседние мотивы. Без фактуры материала, нитей, стежков, рельефа, теней, бликов и объёма; сохрани значимые линии узора и исходные цвета.')]
TEXTURE_REPLACES=[
('Сохрани реальные цвет, освещение, мелкие неровности, фактурные переходы и видимые мягкие тени.','Сохрани видимые цвет, свет, фактуру, неровности и мягкие тени.'),
('Допускается исправить перспективу, отражения и искажения от изгиба поверхности и складок только там, где форма мотива однозначно видна.','Исправляй перспективу и складки только там, где контур однозначно виден.'),
('Характерные контуры, число лепестков, вставок, стежков/составных деталей, их относительные размеры и размещение должны оставаться визуально похожими на источник на 90–100%; попиксельное совпадение не требуется.','Сохрани исходные контур, состав, числа и пропорции; сходство формы — 90–100%.'),
('Сохрани фотографическую фактуру самого мотива; удаляй фон предмета, соседние мотивы, раму/витрину и отражения только за границами мотива.','Сохрани фактуру мотива; фон и соседние детали удаляй только за его границей.')]
def read(name):
 with (OUT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(name,rows):
 with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def apply_replacements(prompt,pairs,style,code):
 for old,new in pairs:
  if old not in prompt:raise ValueError(f'Missing expected {style} text for {code}: {old[:65]}')
  prompt=prompt.replace(old,new,1)
 return prompt
changed={}
for filename,style,fixes,styled,replacements,version in [
 ('higgsfield_prompts.csv','flat',FLAT_FIX,FLAT_STYLE,FLAT_REPLACES,'flat-v4-2026-10-07'),
 ('higgsfield_prompts_texture.csv','texture',TEXTURE_FIX,set(),TEXTURE_REPLACES,'texture-v3-2026-10-07')]:
 rows=read(filename)
 if any('revision_status' in r for r in rows):raise ValueError(f'{filename} already revised; refusing duplicate run')
 for r in rows:
  code=r['code'];short=code[-3:];fix=fixes.get(short,'');isstyle=short in styled and style=='flat'
  if not fix and not isstyle:continue
  original=r['prompt'];prompt=apply_replacements(original,replacements,style,code)
  notes=[]
  if fix:
   prompt+=(' Уточнение: ' if style=='texture' else ' Уточнение формы: ')+fix
   notes.append(fix)
  if isstyle:
   notes.append('Строгий плоский стиль: чистые контуры и ровные заливки без фактуры, бликов и объёма.')
  if len(prompt)>len(original):raise ValueError(f'Prompt became longer: {code} {style} {len(original)}->{len(prompt)}')
  r['prompt']=prompt;r['prompt_version']=version
  r['revision_status']='ПОВТОРИТЬ — '+('форма и плоский стиль' if fix and isstyle else 'форма' if fix else 'плоский стиль')
  r['revision_note']=' '.join(notes)
  r['prompt_chars_before']=str(len(original));r['prompt_chars_after']=str(len(prompt))
  changed[(code,style)]=r
 write(filename,rows)
# Refresh exact file-presence flags for all planned outputs.
for filename in ['higgsfield_prompts.csv','higgsfield_prompts_texture.csv']:
 rows=read(filename)
 for r in rows:r['file_present']='да' if (ROOT/r['save_as']).is_file() else 'нет'
 write(filename,rows)
# Current audit of user-added/renamed outputs. Preserve old comments, update only changed rows and reviewed files.
assessment=read('processed_batch_assessments.csv')
current={('TP-E-034','flat'):('candidate','TP-E-034 is now correctly named; motif composition matches. Flat result still retains visible woven surface texture.'),
 ('TP-E-035','flat'):('manual_review','Newly generated leaf cluster is plausible; compare the count and boundary with the source before accepting.'),
 ('TP-E-035','texture'):('manual_review','Texture result includes an extra small leaf at left; verify whether it belongs to the selected motif.'),
 ('TP-E-070','texture'):('candidate','New result follows the red repeating zigzag/diamond band; confirm repeat count and textile detail on the source.'),
 ('TP-E-097','texture'):('manual_review','New texture output has two joined diamond units; verify the selected unit and repeat against the source.'),
 ('TP-R-002','flat'):('candidate','New auxiliary result follows the pointed upper composition; supplemental reference only.')}
review_paths={('TP-E-034','flat'):'processed_batch_review/new_files_2026-10-07.jpg',('TP-E-035','flat'):'processed_batch_review/new_files_2026-10-07.jpg',('TP-E-035','texture'):'processed_batch_review/new_files_2026-10-07.jpg',('TP-E-070','texture'):'processed_batch_review/new_files_2026-10-07.jpg',('TP-E-097','texture'):'processed_batch_review/new_files_2026-10-07.jpg',('TP-R-002','flat'):'processed_batch_review/new_files_2026-10-07.jpg'}
manifest={r['code']:r for r in read('manifest.csv')}; supplemental={r['code']:r for r in read('supplemental_references.csv')}
for a in assessment:
 key=(a['code'],a['style'])
 if key==('TP-E-035','flat'):
  a['flat_style_issue']='False'
 if key not in current:continue
 rating,note=current[key];rec=(manifest|supplemental)[a['code']];path=ROOT/'Датасет/Элементы'/f"processed_{a['style']}"/f"{a['code']}.png"
 with Image.open(path) as im:im.verify()
 a['present']='True';a['processed_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();a['ai_recommendation']=rating;a['visual_note']=note;a['comparison_sheet']=review_paths[key];a['ai_retouched']='True' if key[1]=='texture' else a['ai_retouched']
 a['scope']='supplemental_only' if a['code'].startswith('TP-R-') else 'primary'
write('processed_batch_assessments.csv',assessment)
# Add the audited supplemental TP-R-002 row to the JSON/source of truth as well as CSV.
jsonpath=OUT/'processed_batch_assessments.json';j=json.loads(jsonpath.read_text());jitems=j['items'];by={(r['code'],r['style']):r for r in jitems}
for key,(rating,note) in current.items():
 code,style=key
 if key not in by:
  if code!='TP-R-002':continue
  rec=supplemental[code];f=next(r for r in assessment if (r['code'],r['style'])==key)
  item={k:f.get(k,'') for k in ['code','style','artifact_code','scope','present','file','processed_sha256','source_file','source_sha256','ai_recommendation','visual_note','flat_style_issue','edge_contact','source_description_correction','comparison_sheet','human_decision','training_ready','ai_retouched']}
  item.update(file=f['file'],source_file=f['source_file'],source_sha256=hashlib.sha256((ROOT/f['source_file']).read_bytes()).hexdigest(),present=True,training_ready=False,ai_retouched=False)
  jitems.append(item);continue
 item=by[key];f=next(r for r in assessment if (r['code'],r['style'])==key)
 item.update(present=True,processed_sha256=f['processed_sha256'],ai_recommendation=rating,visual_note=note,comparison_sheet=review_paths[key],flat_style_issue=(False if key==('TP-E-035','flat') else item.get('flat_style_issue',False)))
 if style=='texture':item['ai_retouched']=True
j['items']=jitems;j['date']='2026-10-07';j['followup']='Владелец добавил недостающие файлы и переименовал/создал TP-E-034/035. Новые файлы просмотрены в new_files_2026-10-07.jpg.';j['counts']={s:dict(Counter(x['ai_recommendation'] for x in jitems if x['style']==s and x['scope']=='primary')) for s in ['flat','texture']};jsonpath.write_text(json.dumps(j,ensure_ascii=False,indent=2))
# Keep preparation matrices synchronized with now-present files and current recommendations.
byassessment={(r['code'],r['style']):r for r in assessment}
for filename,style,key in [('constructor_preparation.csv','flat','flat_file'),('lora_preparation.csv','texture','image_file')]:
 rows=read(filename)
 for r in rows:
  a=byassessment[(r['code'],style)];r['file_present']='да' if a['present']=='True' else 'нет';r['ai_review_2026_10_07']=a['ai_recommendation'];r['processed_sha256']=a['processed_sha256'];r['ai_review_note']=a['visual_note']
  if style=='texture':r['ai_retouched']='true' if a['present']=='True' else 'false';r['training_ready']='нет; требуется отбор, решение владельца, captions и разделение по предметам'
  else:r['status']='файл есть; см. актуальную оценку ИИ, требуется решение владельца' if a['present']=='True' else 'файл отсутствует'
 write(filename,rows)
# Candidate lists are review queues, not accepted datasets.
for filename,style in [('constructor_candidate_shortlist.csv','flat'),('lora_candidate_shortlist.csv','texture')]:
 candidates=[r for r in jitems if r['scope']=='primary' and r['style']==style and r['ai_recommendation']=='candidate' and not (style=='flat' and r.get('flat_style_issue'))]
 with (OUT/filename).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(candidates[0]));w.writeheader();w.writerows(candidates)
# Refresh structured validation, including both supplemental flat references.
statepath=OUT/'style_preparation.json';state=json.loads(statepath.read_text());state.update(flat_files_present=sum(1 for a in assessment if a['style']=='flat' and a['scope']=='primary' and a['present']=='True'),flat_supplemental_files_present=sum(1 for a in assessment if a['style']=='flat' and a['scope']=='supplemental_only' and a['present']=='True'),texture_files_present=sum(1 for a in assessment if a['style']=='texture' and a['scope']=='primary' and a['present']=='True'),missing_flat_primary=[],missing_flat_supplemental=[],missing_texture_primary=[],last_audit='2026-10-07',prompt_revision_date='2026-10-07',prompt_revision_flat_count=sum(1 for r in changed.values() if r['prompt_version'].startswith('flat')),prompt_revision_texture_count=sum(1 for r in changed.values() if r['prompt_version'].startswith('texture')),ready_for_full_lora_training=False,human_accepted=0);statepath.write_text(json.dumps(state,ensure_ascii=False,indent=2))
ledger={'date':'2026-10-07','reason':'Владелец добавил четыре отсутствовавших файла, переименовал результат TP-E-034 и сгенерировал TP-E-035.','review_sheet':'processed_batch_review/new_files_2026-10-07.jpg','new_or_renamed_files':[{ 'code':c,'style':s,'sha256':next(x['processed_sha256'] for x in assessment if x['code']==c and x['style']==s)} for c,s in current], 'prompt_updates':{style:{'count':sum(1 for (_,st) in changed if st==style),'items':[{'code':c,'before':int(r['prompt_chars_before']),'after':int(r['prompt_chars_after']),'status':r['revision_status'],'note':r['revision_note']} for (c,st),r in changed.items() if st==style]} for style in ['flat','texture']},'flat_style_codes':sorted(f'TP-E-{x}' for x in FLAT_STYLE),'resolved_previous_flat_rework':'TP-E-035 was the TP-E-034 image; the replacement TP-E-035 has been added. No further rework prompt for TP-E-035 based on the old filename finding.','notes':'Промпты не длиннее исходных версий. Human decisions remain empty. Prompt text is edited directly in these CSVs; do not regenerate the CSVs from older prompt-generation scripts until they support revision_status/revision_note.'}
(OUT/'audit/2026-10-07').mkdir(parents=True,exist_ok=True);(OUT/'audit/2026-10-07/prompt_revision_ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2))
print(json.dumps({'flat_marked':sum(1 for r in changed.values() if r['prompt_version'].startswith('flat')),'flat_style_codes':len(FLAT_STYLE),'flat_specific_fixes':len(FLAT_FIX),'flat_union':sum(1 for r in changed.values() if r['prompt_version'].startswith('flat')),'texture_fixes':sum(1 for r in changed.values() if r['prompt_version'].startswith('texture')),'flat_lengths_ok':all(int(r['prompt_chars_after'])<=int(r['prompt_chars_before']) for r in changed.values()),'shortlists':{n:len(read(n)) for n in ['constructor_candidate_shortlist.csv','lora_candidate_shortlist.csv']}},ensure_ascii=False,indent=2))
