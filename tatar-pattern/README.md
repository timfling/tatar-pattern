# TATAR PATTERN — сайт

Next.js 16.4 / React 19 / TypeScript + FastAPI / Python 3.12+ / PostgreSQL 16.

## Локальный запуск

Нужны Docker, Node.js 20.9+ и Python 3.12+ с `uv`.
Команды выполняются из папки `tatar-pattern` в отдельных терминалах.

### 1. PostgreSQL

```sh
cd db
cp .env.example .env
# Задайте свой POSTGRES_PASSWORD в .env.
docker compose up -d
```

Подробнее: [db/README.md](db/README.md).

### 2. API

```sh
cd backend
uv sync --frozen
cp .env.example .env
# Заполните DATABASE_URL данными db/.env; задайте STORAGE_ROOT.
# Для мигратора нужен pg_dump версии 16+.
.venv/bin/python -m scripts.migrate
.venv/bin/uvicorn app.main:create_app --factory --env-file .env --host 127.0.0.1 --port 8000
```

Миграции не импортируют рабочий каталог. Изображения каталога публикуются
отдельно от кода; порядок импорта и тестовых фикстур:
[backend/README.md](backend/README.md).

### 3. Интерфейс

```sh
cd frontend
npm ci
API_ORIGIN=http://127.0.0.1:8000 npm run dev
```

Сайт: http://localhost:3000. API: http://127.0.0.1:8000/docs.
Подробнее: [frontend/README.md](frontend/README.md).

## Документация

- [API-CONTRACT.md](API-CONTRACT.md) — контракт API.
- [deploy/README.md](deploy/README.md) — развёртывание.
- [../GITHUB.md](../GITHUB.md) — обновление GitHub.

`.env`, storage, бэкапы, зависимости и локальные артефакты исключены из Git.
