-- =============================================================================
-- Миграция 003. САЙТ: проекты пользователя + служебные поля генераций
-- -----------------------------------------------------------------------------
-- Что добавляем и зачем:
--   projects          — «папки» пользователя в Библиотеке (по макету Figma)
--   generations       — новые колонки для работы сайта:
--                       project_id      — к какому проекту относится генерация
--                       title           — имя паттерна («Паттерн без имени»)
--                       progress        — прогресс 0..100 для шкалы на фронте
--                       progress_stage  — текстовая стадия («Шаг 13 из 20…»)
--                       rating          — оценка пользователя: like / dislike
-- Поля progress/progress_stage нужны, чтобы фронтенд показывал честную шкалу
-- прогресса и название текущей стадии, если генерация «зависла».
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Таблица PROJECTS — папки (проекты) пользователя в Библиотеке.
-- -----------------------------------------------------------------------------
CREATE TABLE projects (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Чей проект. ON DELETE CASCADE: удалили пользователя — удалятся его проекты.
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    title       TEXT NOT NULL DEFAULT 'Без названия',

    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE projects IS 'Папки (проекты) пользователя в Библиотеке';

CREATE INDEX idx_projects_user_id ON projects (user_id);

-- Автообновление updated_at (функция set_updated_at создана в миграции 001).
CREATE TRIGGER trg_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- -----------------------------------------------------------------------------
-- Новые колонки у GENERATIONS.
-- -----------------------------------------------------------------------------
ALTER TABLE generations
    -- К какому проекту относится. SET NULL: удаление проекта не удаляет генерации.
    ADD COLUMN project_id      BIGINT REFERENCES projects(id) ON DELETE SET NULL,
    -- Имя паттерна, которое видит пользователь (можно переименовать).
    ADD COLUMN title           TEXT NOT NULL DEFAULT 'Паттерн без имени',
    -- Прогресс 0..100. Обновляет воркер во время генерации.
    ADD COLUMN progress        SMALLINT NOT NULL DEFAULT 0
               CHECK (progress BETWEEN 0 AND 100),
    -- Текущая стадия текстом — показываем, если прогресс «застрял».
    ADD COLUMN progress_stage  TEXT,
    -- Оценка результата пользователем (кнопки лайк/дизлайк в макете).
    ADD COLUMN rating          TEXT CHECK (rating IN ('like', 'dislike'));

CREATE INDEX idx_generations_project_id ON generations (project_id);

-- -----------------------------------------------------------------------------
-- Статус 'cancelling' у GENERATIONS.
-- Когда пользователь подтверждает остановку, API переводит задачу в
-- 'cancelling' — воркер замечает это и аккуратно прерывает провайдера,
-- после чего задача становится 'failed' с пометкой «Прервано пользователем».
-- CHECK-ограничение из миграции 002 пересоздаём с расширенным списком.
-- -----------------------------------------------------------------------------
ALTER TABLE generations DROP CONSTRAINT generations_status_check;
ALTER TABLE generations ADD CONSTRAINT generations_status_check
    CHECK (status IN ('queued', 'processing', 'cancelling', 'done', 'failed'));
