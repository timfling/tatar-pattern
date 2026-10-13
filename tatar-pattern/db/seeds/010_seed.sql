-- =============================================================================
-- Сиды (тестовые данные) для проверки, что база работает.
-- -----------------------------------------------------------------------------
-- «Сиды» = стартовый набор данных. Здесь 5 демонстрационных элементов орнамента,
-- источник, палитры, схемы композиции, файлы и один тестовый пользователь с
-- генерацией. Это НЕ финальный каталог — просто пример для запуска и обучения.
--
-- Приём: мы вставляем строки и ссылаемся на них НЕ по числовому id (его база
-- назначает сама), а по уникальным полям (code) через подзапросы. Так файл можно
-- запускать целиком, не подставляя id вручную.
-- =============================================================================

BEGIN;   -- всё внутри выполнится «одним куском»: либо целиком, либо никак

-- -----------------------------------------------------------------------------
-- 1. Источник (откуда сняты орнаменты). Реальная точка сбора датасета.
-- -----------------------------------------------------------------------------
INSERT INTO sources (source_type, object_name, location, shot_date, legal_basis, note)
VALUES
    ('фото', 'Резные наличники и ворота', 'Старо-татарская слобода, Казань',
     DATE '2026-07-13', 'Съёмка в общественном месте', 'Первый выезд на сбор датасета');

-- -----------------------------------------------------------------------------
-- 2. Палитры (взяты из демо-конструктора). Цвета — в JSONB.
-- -----------------------------------------------------------------------------
INSERT INTO palettes (code, name, colors, note) VALUES
    ('emerald', 'Казанский изумруд',
     '{"bg":"#123f34","bg2":"#0c241f","ink":"#f2e5ca","gold":"#c99a4a","red":"#9d302b","coral":"#c96a52","teal":"#6fae99","blue":"#1f5069","dark":"#0a1110"}',
     'Глубокий фон, медь, киноварь'),
    ('porcelain', 'Фарфор и киноварь',
     '{"bg":"#efe7d7","bg2":"#d9ceb9","ink":"#172b34","gold":"#bb8740","red":"#a33635","coral":"#d77950","teal":"#327c79","blue":"#1d4f68","dark":"#0c1417"}',
     'Светлая база, синий контур'),
    ('leather', 'Казанская кожа',
     '{"bg":"#3b251a","bg2":"#1b100c","ink":"#f1dec0","gold":"#d2a15d","red":"#7f2c24","coral":"#ba744b","teal":"#7ca489","blue":"#455e64","dark":"#120b08"}',
     'Тёплая кожа, кремовый шов');

-- -----------------------------------------------------------------------------
-- 3. Схемы композиции. Правила — в JSONB.
-- -----------------------------------------------------------------------------
INSERT INTO composition_schemes (code, name, scheme_type, rules, note) VALUES
    ('medallion', 'Медальон', 'медальон',
     '{"symmetry":"radial","rays":8,"center":true}',
     'Центрально-симметричная розетка'),
    ('border', 'Бордюр', 'бордюр',
     '{"direction":"horizontal","repeat":"linear","step":120}',
     'Ленточный повтор вдоль линии'),
    ('rapport', 'Раппорт', 'раппорт',
     '{"grid":"square","tile":256,"offset":0.5}',
     'Бесшовное замощение плоскости');

-- -----------------------------------------------------------------------------
-- 3b. Предмет (артефакт) — пример того, что даёт разметка табличек.
-- -----------------------------------------------------------------------------
INSERT INTO artifacts
    (code, source_id, title_ru, title_tt, title_en, dating, technique, artifact_type,
     origin, authenticity, usage_scope, rights, quality_flags, review_status, confidence, notes)
VALUES
    ('SL-7633',
     (SELECT id FROM sources WHERE location = 'Старо-татарская слобода, Казань' LIMIT 1),
     'Резной наличник с тюльпанами', 'Лалә бизәкле тәрәзә йөзлеге', 'Carved window frame with tulips',
     'Конец XIX — начало XX века', 'Дерево, пропильная резьба, окраска', 'резьба',
     'татарское', 'оригинал', 'рид_и_обучение', 'публичное_место',
     '{"reflection": false, "angle": true, "blur": false}', 'проверено', 0.95,
     'Демо-пример; снято с улицы под углом');

INSERT INTO artifact_files (artifact_id, file_type, path, frame) VALUES
    ((SELECT id FROM artifacts WHERE code = 'SL-7633'), 'raw',
     'dataset/raw/2026-07-13/staro-tatarskaya-sloboda/_DSC7633.ARW', 'DSC7633'),
    ((SELECT id FROM artifacts WHERE code = 'SL-7633'), 'proxy',
     'dataset/proxy/2026-07-13/staro-tatarskaya-sloboda/DSC7633.jpg', 'DSC7633');

-- -----------------------------------------------------------------------------
-- 4. Элементы орнамента (5 штук). source_id берём подзапросом по адресу источника.
--    Первый элемент дополнительно привязан к предмету SL-7633.
-- -----------------------------------------------------------------------------
INSERT INTO elements
    (code, name_ru, name_tt, motif_class, semantics, description, typical_use, region, epoch, status, verified_by, source_id, artifact_id)
VALUES
    ('TP-TULIP-001', 'Тюльпан', 'Лалә', 'тюльпан',
     'Символ возрождения и процветания',
     'Классический татарский тюльпан с тремя лепестками и симметричным силуэтом.',
     'Центральный мотив, медальоны', 'Казань', 'XIX век', 'верифицировано', 'Эксперт-этнограф',
     (SELECT id FROM sources WHERE location = 'Старо-татарская слобода, Казань' LIMIT 1),
     (SELECT id FROM artifacts WHERE code = 'SL-7633')),

    ('TP-BUD-001', 'Бутон', 'Бөре', 'бутон',
     'Символ зарождающейся жизни, юности',
     'Полураскрытый бутон, часто соседствует с тюльпаном.',
     'Заполнение поля, парные композиции', 'Казань', 'XIX век', 'отрисовано', NULL,
     (SELECT id FROM sources WHERE location = 'Старо-татарская слобода, Казань' LIMIT 1),
     NULL),

    ('TP-PALMETTE-001', 'Пальметта', 'Пальметта', 'пальметта',
     'Символ древа жизни, изобилия',
     'Веерообразный лиственный мотив с загнутыми краями.',
     'Углы, завершения бордюров', 'Поволжье', 'XVIII–XIX век', 'обработано', NULL,
     (SELECT id FROM sources WHERE location = 'Старо-татарская слобода, Казань' LIMIT 1),
     NULL),

    ('TP-VINE-001', 'Завиток', 'Бөтерелмә', 'завиток',
     'Символ непрерывности, вечного движения',
     'S-образный побег, связывающий крупные мотивы в единую композицию.',
     'Связующие линии, бордюры', 'Казань', 'XIX век', 'снято', NULL,
     (SELECT id FROM sources WHERE location = 'Старо-татарская слобода, Казань' LIMIT 1),
     NULL),

    ('TP-BORDER-001', 'Кайма', 'Чигү', 'кайма',
     'Оберег, граница-защита',
     'Ленточный краевой мотив с ритмичным повтором.',
     'Обрамление изделия, края платка', 'Казань', 'XIX–XX век', 'снято', NULL,
     (SELECT id FROM sources WHERE location = 'Старо-татарская слобода, Казань' LIMIT 1),
     NULL);

-- -----------------------------------------------------------------------------
-- 5. Файлы элементов (только пути!). element_id берём подзапросом по code.
--    Пути даны в единой логической схеме хранилища:
--      dataset/<стадия>/<дата>/<объект>/<файл>
-- -----------------------------------------------------------------------------
INSERT INTO element_files (element_id, file_type, path, note) VALUES
    ((SELECT id FROM elements WHERE code = 'TP-TULIP-001'),
     'raw', 'dataset/raw/2026-07-13/staro-tatarskaya-sloboda/_DSC7633.JPG', 'Исходное фото'),
    ((SELECT id FROM elements WHERE code = 'TP-TULIP-001'),
     'vector_svg', 'dataset/vector/tp-tulip-001.svg', 'Отрисованный вектор'),
    ((SELECT id FROM elements WHERE code = 'TP-TULIP-001'),
     'flat_png', 'dataset/png/tp-tulip-001.png', 'Плоский PNG для конструктора'),

    ((SELECT id FROM elements WHERE code = 'TP-BUD-001'),
     'raw', 'dataset/raw/2026-07-13/staro-tatarskaya-sloboda/_DSC7636.JPG', 'Исходное фото'),
    ((SELECT id FROM elements WHERE code = 'TP-BUD-001'),
     'vector_svg', 'dataset/vector/tp-bud-001.svg', 'Отрисованный вектор'),

    ((SELECT id FROM elements WHERE code = 'TP-PALMETTE-001'),
     'photo_processed', 'dataset/processed/2026-07-13/tp-palmette-001.png', 'Обработанное фото'),

    ((SELECT id FROM elements WHERE code = 'TP-VINE-001'),
     'raw', 'dataset/raw/2026-07-13/staro-tatarskaya-sloboda/_DSC7648.JPG', 'Исходное фото'),

    ((SELECT id FROM elements WHERE code = 'TP-BORDER-001'),
     'raw', 'dataset/raw/2026-07-13/staro-tatarskaya-sloboda/_DSC7660.JPG', 'Исходное фото');

-- -----------------------------------------------------------------------------
-- 6. Тестовый пользователь и одна генерация (операционная база).
--    password_hash здесь — просто заглушка для примера, не настоящий пароль.
-- -----------------------------------------------------------------------------
INSERT INTO users (email, password_hash, plan) VALUES
    ('demo@tatarpattern.ru', 'demo-hash-not-a-real-password', 'free');

INSERT INTO generations
    (user_id, status, params, prompt, user_prompt, skeleton_path, result_path, model_version, finished_at)
VALUES
    ((SELECT id FROM users WHERE email = 'demo@tatarpattern.ru'),
     'done',
     '{"palette":"emerald","scheme":"medallion","elements":["TP-TULIP-001","TP-BUD-001"],"scale":104,"seed":107198}',
     'tatar tulip medallion, emerald palette, symmetric',
     'Хочу изумрудный медальон с тюльпанами',
     'dataset/skeletons/gen-0001-skeleton.svg',
     'dataset/results/gen-0001.png',
     'constructor-v0.1',
     now());

COMMIT;   -- фиксируем все вставки

-- Быстрая проверка после заливки: сколько чего вставилось.
SELECT 'sources'  AS table, count(*) FROM sources
UNION ALL SELECT 'elements', count(*) FROM elements
UNION ALL SELECT 'element_files', count(*) FROM element_files
UNION ALL SELECT 'palettes', count(*) FROM palettes
UNION ALL SELECT 'composition_schemes', count(*) FROM composition_schemes
UNION ALL SELECT 'users', count(*) FROM users
UNION ALL SELECT 'generations', count(*) FROM generations;
