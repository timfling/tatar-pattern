-- =============================================================================
-- Миграция 004. АРТЕФАКТЫ — предметы, снятые на фото (уровень между
-- источником и элементом орнамента).
-- -----------------------------------------------------------------------------
-- Зачем: одна музейная табличка описывает ПРЕДМЕТ (полотенце, ичиги, наличник),
-- а из одного предмета потом вырезают 3–5 ЭЛЕМЕНТОВ орнамента. Раньше данным
-- с табличек было некуда ложиться. Теперь цепочка такая:
--
--   sources (место съёмки) -> artifacts (предмет + атрибуция) -> elements (мотив)
--
-- Таблицы:
--   artifacts       — предмет: название, датировка, техника, происхождение, права
--   artifact_files  — файлы предмета (RAW, прокси, фото таблички) — только пути
-- Плюс: elements.artifact_id и element_files.ai_retouched.
-- =============================================================================

CREATE TABLE artifacts (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Код предмета, напр. 'KS-9240' (Кул Шариф, кадр 9240). UNIQUE.
    code            TEXT NOT NULL UNIQUE,

    -- Где снято. ON DELETE SET NULL — удалили источник, предмет остался.
    source_id       BIGINT REFERENCES sources(id) ON DELETE SET NULL,

    -- Атрибуция с музейной таблички (как есть, на трёх языках, если были).
    title_ru        TEXT,
    title_tt        TEXT,
    title_en        TEXT,
    dating          TEXT,           -- «Первая четверть XX века», «XIII в. от хиджры / XIX в.»
    dimensions      TEXT,           -- «28,3 x 37,5 см»
    technique       TEXT,           -- «холст домотканый, ткачество браное»
    author          TEXT,           -- автор/мастер/автор реплики, если указан
    description     TEXT,           -- развёрнутый текст с таблички

    -- Тип предмета — фиксированный словарь, чтобы не расползались написания.
    artifact_type   TEXT NOT NULL DEFAULT 'иное'
                    CHECK (artifact_type IN (
                        'архитектура', 'плитка', 'витраж', 'текстиль', 'вышивка',
                        'кожа', 'ювелирное', 'керамика', 'резьба', 'рукопись',
                        'каллиграфия', 'шамаиль', 'иное')),

    -- Происхождение: что это культурно. Только 'татарское' идёт в РИД и обучение.
    origin          TEXT NOT NULL DEFAULT 'неизвестно'
                    CHECK (origin IN ('татарское', 'общеисламское', 'иное', 'неизвестно')),

    -- Оригинал или современная копия. Реплики — риск чужого авторского права.
    authenticity    TEXT NOT NULL DEFAULT 'неизвестно'
                    CHECK (authenticity IN ('оригинал', 'реплика', 'новодел', 'неизвестно')),

    -- Куда предмет допускается использовать. Главный «рубильник» для РИД и LoRA.
    --   рид_и_обучение — полноценный член каталога
    --   только_обучение — учим модель, но в реестр РИД не включаем
    --   контекст        — храним для справки/отчёта, никуда не включаем
    --   исключить       — брак или чужое, не используем
    usage_scope     TEXT NOT NULL DEFAULT 'контекст'
                    CHECK (usage_scope IN ('рид_и_обучение', 'только_обучение', 'контекст', 'исключить')),

    -- Права на использование съёмки. Для MVP по гранту — 'некоммерческое_mvp'.
    rights          TEXT NOT NULL DEFAULT 'некоммерческое_mvp'
                    CHECK (rights IN ('некоммерческое_mvp', 'разрешение_получено', 'публичное_место', 'неясно')),

    -- Флаги качества кадра в JSONB, напр. {"reflection":true,"angle":true,"blur":false}
    quality_flags   JSONB NOT NULL DEFAULT '{}',

    -- Сырой распознанный текст таблички — на случай, если поля разложены неверно.
    plate_text      TEXT,

    -- Статус проверки человеком. Автоматика пишет 'авто', ты переводишь в 'проверено'.
    review_status   TEXT NOT NULL DEFAULT 'авто'
                    CHECK (review_status IN ('авто', 'проверено', 'отклонено')),
    confidence      NUMERIC(3,2) CHECK (confidence BETWEEN 0 AND 1),  -- уверенность ИИ 0..1
    notes           TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  artifacts               IS 'Предметы (артефакты) с фото: атрибуция с табличек, происхождение, права';
COMMENT ON COLUMN artifacts.usage_scope   IS 'Куда допускается: рид_и_обучение / только_обучение / контекст / исключить';
COMMENT ON COLUMN artifacts.origin        IS 'Культурное происхождение; в РИД и обучение идёт только татарское';
COMMENT ON COLUMN artifacts.review_status IS 'авто — заполнено ИИ, проверено — подтверждено человеком';

CREATE INDEX idx_artifacts_source_id   ON artifacts (source_id);
CREATE INDEX idx_artifacts_usage_scope ON artifacts (usage_scope);
CREATE INDEX idx_artifacts_review      ON artifacts (review_status);

CREATE TRIGGER trg_artifacts_updated_at
    BEFORE UPDATE ON artifacts
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();


-- -----------------------------------------------------------------------------
-- Файлы предмета. Один предмет = несколько кадров (общий план, детали) + табличка.
-- -----------------------------------------------------------------------------
CREATE TABLE artifact_files (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    artifact_id  BIGINT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,

    file_type    TEXT NOT NULL
                 CHECK (file_type IN ('raw', 'proxy', 'plate_raw', 'plate_proxy')),

    path         TEXT NOT NULL UNIQUE,   -- путь к файлу (только путь!)
    frame        TEXT,                   -- номер кадра, напр. 'DSC9240'
    note         TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  artifact_files           IS 'Файлы предмета: RAW, прокси-JPG, фото таблички (только пути)';
COMMENT ON COLUMN artifact_files.file_type IS 'raw / proxy (лёгкий JPG) / plate_raw / plate_proxy (табличка)';

CREATE INDEX idx_artifact_files_artifact_id ON artifact_files (artifact_id);


-- -----------------------------------------------------------------------------
-- Связываем элементы орнамента с предметом, из которого они вырезаны.
-- -----------------------------------------------------------------------------
ALTER TABLE elements
    ADD COLUMN artifact_id BIGINT REFERENCES artifacts(id) ON DELETE SET NULL;

COMMENT ON COLUMN elements.artifact_id IS 'Предмет, из которого вырезан элемент';
CREATE INDEX idx_elements_artifact_id ON elements (artifact_id);


-- -----------------------------------------------------------------------------
-- Признак ИИ-ретуши файла. Зачем: если картинку чистила нейросеть, она могла
-- дорисовать детали — для РИД это надо знать и проверять отдельно.
-- -----------------------------------------------------------------------------
ALTER TABLE element_files
    ADD COLUMN ai_retouched BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN element_files.ai_retouched IS 'true — файл обработан нейросетью, требует ручной сверки с RAW';
