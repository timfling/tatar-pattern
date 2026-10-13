-- =============================================================================
-- Миграция 002. ОПЕРАЦИОННАЯ БАЗА (работа сайта: пользователи и генерации)
-- -----------------------------------------------------------------------------
-- Эти таблицы обслуживают сам сервис (не РИД):
--   users        — пользователи сайта
--   generations  — задания на генерацию паттернов и их результаты
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Таблица USERS — пользователи сервиса.
-- Что это и зачем: аккаунты людей, которые заходят на сайт. Пароль храним
-- ТОЛЬКО в виде хэша (необратимо зашифрованная строка) — сам пароль в базе
-- держать нельзя по требованиям безопасности.
-- -----------------------------------------------------------------------------
CREATE TABLE users (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    email          TEXT NOT NULL UNIQUE,   -- логин; UNIQUE = один email = один аккаунт
    password_hash  TEXT NOT NULL,          -- хэш пароля, НЕ сам пароль

    -- Тариф. free — бесплатный, paid — платный.
    plan           TEXT NOT NULL DEFAULT 'free'
                   CHECK (plan IN ('free', 'paid')),

    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  users               IS 'Пользователи сервиса TATAR PATTERN';
COMMENT ON COLUMN users.password_hash IS 'Хэш пароля (никогда не храним пароль в открытом виде)';
COMMENT ON COLUMN users.plan          IS 'Тариф: free (бесплатный) или paid (платный)';


-- -----------------------------------------------------------------------------
-- Таблица GENERATIONS — задания на генерацию паттернов.
-- Что это и зачем: каждый раз, когда пользователь просит сгенерировать паттерн,
-- сюда пишется строка: с какими параметрами, каким промптом, что получилось.
-- Параметры конструктора храним в JSONB (гибкий JSON), т.к. их набор меняется.
-- -----------------------------------------------------------------------------
CREATE TABLE generations (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Чья генерация. ON DELETE CASCADE: удалили пользователя — удалятся и его генерации.
    user_id        BIGINT REFERENCES users(id) ON DELETE CASCADE,

    -- Статус задания.
    status         TEXT NOT NULL DEFAULT 'queued'
                   CHECK (status IN ('queued', 'processing', 'done', 'failed')),

    params         JSONB,          -- параметры конструктора (палитра, схема, элементы, seed...)
    prompt         TEXT,           -- итоговый промпт, ушедший в модель
    user_prompt    TEXT,           -- что ввёл пользователь своими словами
    skeleton_path  TEXT,           -- путь к «скелету»/каркасу композиции
    result_path    TEXT,           -- путь к готовому изображению
    model_version  TEXT,           -- версия модели/алгоритма (для воспроизводимости)

    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ     -- когда генерация завершилась (может быть пусто, пока идёт)
);

COMMENT ON TABLE  generations               IS 'Задания на генерацию паттернов и их результаты';
COMMENT ON COLUMN generations.params        IS 'Параметры конструктора в JSONB';
COMMENT ON COLUMN generations.model_version IS 'Версия модели/алгоритма — для воспроизводимости результата';

-- Индексы под частые запросы: «все генерации пользователя» и «по статусу».
CREATE INDEX idx_generations_user_id ON generations (user_id);
CREATE INDEX idx_generations_status  ON generations (status);
