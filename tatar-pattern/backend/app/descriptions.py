"""Deterministic Russian prose from saved facts. No inference of symbolism."""
VERSION = 'tp-description/1.1.0'
SCHEMA = 'tp-description-schema/1.0.0'

USE = {'architecture':'Проверьте масштаб деталей на пробном фрагменте поверхности.',
       'textile':'Для текстиля сначала проверьте масштаб деталей на пробной печати.',
       'packaging':'Композицию можно примерить к лицевой стороне упаковки.',
       'interior':'Композицию можно использовать как акцент интерьерной панели.',
       'web':'Композицию можно примерить к обложке или декоративному блоку сайта.'}


def describe(recipe, selections, mode='flat', legacy=False):
    if mode == 'ai':
        chosen = selections.get('elementCodes') or selections.get('motifs') or []
        names = {'medallion':'медальон', 'border':'бордюр', 'rapport':'повторяющийся орнамент'}
        n=len(chosen)
        noun='элемента или класса мотивов' if n%10==1 and n%100!=11 else 'элементов или классов мотивов'
        text = f"Для генерации выбраны {names.get(selections.get('composition'), 'орнамент')} и набор из {n} {noun}. Это описание задания; состав и геометрия итогового изображения пока не проверены."
        return {'text':text, 'basis':'requested_only', 'claimType':'request', 'schemaVersion':SCHEMA, 'templateVersion':VERSION,
                'facts':{'requested':{'selections':selections,'elements':recipe.get('input',{}).get('elements',[])}, 'observed':None, 'verified':None},
                'evidence':[], 'culturalNote':None}
    composition = selections.get('composition')
    pilot = recipe.get('pilotId')
    if pilot == 'P1':
        first = 'Небольшую розетку окружает венок из направленных пальметт, а парные листовые спирали образуют нижнюю опору.'
    elif pilot == 'P2':
        if recipe.get('layout',{}).get('rows')==3:
            first = 'Бордюр построен в три яруса: крупные округлые цветы, зелёные завитковые блоки и более частый ряд малых петлевых цветов.'
        else:
            first = 'Крупные округлые цветы задают направленный ритм бордюра; между ними размещены зелёные связки и малые петлевые цветы.'
    elif pilot == 'P3':
        first = 'Крупные ромбы чередуются с меньшими ступенчатыми мотивами, а отдельные узкие полосы организуют поле повтора.'
    else:
        first = {'medallion':'Мотивы размещены вокруг центра медальона.', 'border':'Мотивы повторяются в рядах бордюра.', 'rapport':'Мотивы размещены в периодической сетке.'}.get(composition,'Композиция собрана из выбранных мотивов.')
    original = recipe.get('colorMode', selections.get('colorMode','original')) == 'original'
    color = 'Сохранены внутренние цветовые области исходных PNG' if original else 'Использовано силуэтное цветовое исполнение'
    bg = 'на прозрачном фоне' if recipe.get('transparentBackground') else 'на сплошном фоне'
    density = {'sparse':'с широкими интервалами', 'default':'с умеренными интервалами', 'dense':'с более частым повтором'}.get(selections.get('parameters'),'')
    # Legacy layout supports only its saved arrangement, not a new aesthetic diagnosis.
    if legacy: density = ''
    second = f'{color} {bg}{(" " + density) if density else ""}.'
    application = USE.get(selections.get('usage'), USE['web'])
    if recipe.get('outputKind') == 'pattern_sample' and not recipe.get('seamless'):
        application = 'Для бесшовного повтора экспортируйте модуль: края этого образца не согласованы с периодом.'
    note = recipe.get('culturalNote') if not legacy else None
    return {'text':' '.join((first,second,application)), 'basis':'legacy_recipe' if legacy else 'saved_recipe',
            'claimType':'render_recipe_fact', 'schemaVersion':SCHEMA, 'templateVersion':VERSION,
            'facts':{'composition':composition, 'pilotId':pilot, 'roles':recipe.get('roles'), 'elements':recipe.get('elements',[]),
                     'layout':recipe.get('layout'), 'colorMode':recipe.get('colorMode'), 'background':recipe.get('palette',{}).get('bg'),
                     'outputKind':recipe.get('outputKind'), 'seamless':recipe.get('seamless')},
            'evidence':recipe.get('descriptionEvidence',[]), 'culturalNote':note}


def saved_or_fallback(params):
    recipe = params.get('recipe') or {}
    if recipe.get('description'):
        return recipe['description']
    return describe(recipe, params.get('selections') or {}, params.get('mode','flat'), legacy=True)
