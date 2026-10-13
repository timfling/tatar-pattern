-- =============================================================================
-- Миграция 001. КАТАЛОГ ОРНАМЕНТОВ (это будущий РИД для Роспатента)
-- -----------------------------------------------------------------------------
-- «Миграция» = SQL-файл, который создаёт таблицы. Мы храним их отдельными
-- пронумерованными файлами, чтобы базу можно было собрать с нуля по шагам.
--
-- Здесь пять таблиц, описывающих сами орнаменты и всё, что к ним относится:
--   sources             — откуда взят орнамент (фото, музей, книга)
--   elements            — сам элемент орнамента (главная таблица каталога)
--   element_files       — файлы элемента (сырое фото, вектор, png) — ТОЛЬКО пути
--   palettes            — цветовые палитры
--   composition_schemes — схемы раскладки (медальон / бордюр / раппорт)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Таблица SOURCES — источники орнаментов.
-- Что это и зачем: фиксируем, откуда физически взят каждый орнамент. Для РИД и
-- для этнографической достоверности важно доказать происхождение (где сняли,
-- когда, на каком основании).
-- -----------------------------------------------------------------------------
CREATE TABLE sources (
    -- id — внутренний числовой номер строки. GENERATED ... AS IDENTITY — это
    -- современный способ автонумерации (Postgres сам подставит 1, 2, 3, ...).
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Тип источника. CHECK разрешает только значения из списка — защита от опечаток.
    source_type  TEXT NOT NULL
                 CHECK (source_type IN ('фото', 'музей', 'архив', 'книга', 'иное')),

    object_name  TEXT,          -- что именно снято: дверь, ворота, ичиги, книга и т.п.
    location     TEXT,          -- где: адрес, город, музей
    shot_date    DATE,          -- дата съёмки/фиксации
    legal_basis  TEXT,          -- основание съёмки (публичное место, разрешение музея и т.п.)
    note         TEXT,          -- свободный комментарий

    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  sources             IS 'Источники орнаментов: откуда физически взят каждый элемент';
COMMENT ON COLUMN sources.source_type IS 'Тип источника: фото/музей/архив/книга/иное';
COMMENT ON COLUMN sources.legal_basis IS 'Основание съёмки — важно для РИД и авторских прав';


-- -----------------------------------------------------------------------------
-- Таблица ELEMENTS — сами элементы орнамента. Это ядро каталога (РИД).
-- Что это и зачем: одна строка = один орнаментальный элемент с описанием,
-- символикой и статусом обработки. Именно этих строк по договору нужно 100+.
-- -----------------------------------------------------------------------------
CREATE TABLE elements (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- code — человекочитаемый артикул, напр. 'TP-TULIP-001'. UNIQUE = не повторяется.
    -- Зачем: удобно ссылаться на элемент в файлах, отчётах и коде, не зная числового id.
    code         TEXT NOT NULL UNIQUE,

    name_ru      TEXT NOT NULL,     -- название по-русски
    name_tt      TEXT,              -- название по-татарски

    -- Класс мотива (тюльпан, бутон, пальметта...). Держим текстом, чтобы легко
    -- добавлять новые классы без переделки базы.
    motif_class  TEXT NOT NULL,

    semantics    TEXT,              -- символика/значение мотива
    description  TEXT,              -- искусствоведческое описание
    typical_use  TEXT,              -- где традиционно применялся (кайма, центр, ткань...)
    region       TEXT,              -- регион бытования
    epoch        TEXT,              -- эпоха/период

    -- Статус готовности элемента в нашем производственном конвейере.
    -- Порядок: снято -> обработано -> отрисовано -> верифицировано.
    status       TEXT NOT NULL DEFAULT 'снято'
                 CHECK (status IN ('снято', 'обработано', 'отрисовано', 'верифицировано')),

    verified_by  TEXT,              -- кто верифицировал (эксперт/искусствовед)

    -- Ссылка на источник. ON DELETE SET NULL: если источник удалят, элемент
    -- останется, но поле источника станет пустым (элемент не пропадёт).
    source_id    BIGINT REFERENCES sources(id) ON DELETE SET NULL,

    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  elements             IS 'Каталог элементов татарского орнамента (ядро РИД)';
COMMENT ON COLUMN elements.code        IS 'Человекочитаемый артикул, напр. TP-TULIP-001';
COMMENT ON COLUMN elements.motif_class IS 'Класс мотива: тюльпан, бутон, пальметта, завиток и т.д.';
COMMENT ON COLUMN elements.status      IS 'Этап конвейера: снято->обработано->отрисовано->верифицировано';

-- Индексы ускоряют поиск по частым фильтрам (по классу мотива и по статусу).
CREATE INDEX idx_elements_motif_class ON elements (motif_class);
CREATE INDEX idx_elements_status      ON elements (status);


-- -----------------------------------------------------------------------------
-- Таблица ELEMENT_FILES — файлы, относящиеся к элементу.
-- Что это и зачем: у одного элемента бывает несколько файлов на разных стадиях
-- (сырое фото, обработанное фото, вектор, плоский png). В базе храним ТОЛЬКО
-- ПУТИ к файлам, а не сами картинки — так база остаётся лёгкой и быстрой.
-- -----------------------------------------------------------------------------
CREATE TABLE element_files (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- К какому элементу относится файл. ON DELETE CASCADE: удалили элемент —
    -- автоматически удалятся и записи о его файлах (чтобы не было «висячих» строк).
    element_id   BIGINT NOT NULL REFERENCES elements(id) ON DELETE CASCADE,

    -- Тип файла по стадии обработки.
    file_type    TEXT NOT NULL
                 CHECK (file_type IN ('raw', 'photo_processed', 'vector_svg', 'flat_png')),

    path         TEXT NOT NULL,     -- путь к файлу (относительный от корня хранилища)
    note         TEXT,

    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Один и тот же путь не должен встречаться дважды.
    UNIQUE (path)
);

COMMENT ON TABLE  element_files           IS 'Файлы элемента (в базе только пути, не сами изображения)';
COMMENT ON COLUMN element_files.file_type IS 'Стадия файла: raw / photo_processed / vector_svg / flat_png';

CREATE INDEX idx_element_files_element_id ON element_files (element_id);


-- -----------------------------------------------------------------------------
-- Таблица PALETTES — цветовые палитры.
-- Что это и зачем: набор согласованных цветов для генерации паттернов. Цвета
-- храним в JSONB — это «умный» тип для JSON: гибко (любой набор ключей) и по нему
-- можно искать. Например: {"bg": "#123f34", "gold": "#c99a4a", ...}.
-- -----------------------------------------------------------------------------
CREATE TABLE palettes (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,   -- короткий код палитры, напр. 'emerald'
    name         TEXT NOT NULL,          -- человекочитаемое имя
    colors       JSONB NOT NULL,         -- набор цветов в формате JSON
    note         TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  palettes        IS 'Цветовые палитры для генерации паттернов';
COMMENT ON COLUMN palettes.colors IS 'Цвета в JSONB, напр. {"bg":"#123f34","gold":"#c99a4a"}';


-- -----------------------------------------------------------------------------
-- Таблица COMPOSITION_SCHEMES — схемы построения композиции.
-- Что это и зачем: правила раскладки элементов (медальон, бордюр, раппорт).
-- Правила держим в JSONB, потому что у разных схем разный набор параметров.
-- -----------------------------------------------------------------------------
CREATE TABLE composition_schemes (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,   -- напр. 'medallion'
    name         TEXT NOT NULL,          -- человекочитаемое имя

    scheme_type  TEXT NOT NULL
                 CHECK (scheme_type IN ('медальон', 'бордюр', 'раппорт')),

    rules        JSONB NOT NULL,         -- параметры раскладки в JSON
    note         TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  composition_schemes       IS 'Схемы раскладки: медальон / бордюр / раппорт';
COMMENT ON COLUMN composition_schemes.rules IS 'Параметры раскладки в JSONB (симметрия, шаг, повтор и т.д.)';


-- -----------------------------------------------------------------------------
-- Автообновление поля updated_at у elements.
-- Что это и зачем: чтобы поле «когда изменяли» само проставлялось при любом
-- UPDATE. Это «триггер» — маленькая функция, которую база запускает автоматически.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_elements_updated_at
    BEFORE UPDATE ON elements
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
