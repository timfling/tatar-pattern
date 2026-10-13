# Backend TATAR PATTERN — рабочая версия 0

FastAPI + PostgreSQL 16 + Pillow. Алгоритмическая генерация синхронная: ответ
приходит после создания PNG и JPG и записи истории. Авторизация — Argon2id и
серверные сессии с HttpOnly cookie; в БД хранится SHA-256 случайного токена.

## Установка и запуск

Нужны Python 3.12+, `uv`, запущенный PostgreSQL 16 и `pg_dump` версии 16+.
Рабочая папка:

```bash
cd "/Users/timfling/Desktop/Стартапы/ТАТАР ПАТТЕРН/Разработка/tatar-pattern/backend"
uv sync --frozen
cp .env.example .env
```

Заполните `DATABASE_URL` своими значениями из `db/.env`; URL-кодируйте специальные
символы в пароле. `STORAGE_ROOT` — отдельное хранилище PNG, исходных кадров и
результатов, пути в БД относительные от этого каталога. Для локальной проверки
`COOKIE_SECURE=false`; `ALLOW_FIXTURES=false` для рабочего каталога. Не публикуйте
`.env`, backups и storage. Можно передавать все переменные окружением.

```bash
# На Mac с PostgreSQL из Homebrew, если pg_dump не найден:
export PG_BIN=/opt/homebrew/opt/postgresql@16/bin
.venv/bin/python -m scripts.migrate
.venv/bin/uvicorn app.main:create_app --factory --env-file .env --host 127.0.0.1 --port 8000
```

Мигратор всегда сначала делает бэкап, затем применяет только новые миграции.
Сиды не загружаются. На сервере используется один worker: лимиты авторизации
(20 попыток/IP/минуту) и двух одновременных генераций действуют внутри процесса.
Документация API: [localhost:8000/docs](http://localhost:8000/docs).
Проверка готовности: [localhost:8000/api/health](http://localhost:8000/api/health).

Для Next.js задается адрес API `http://localhost:8000`. Клиент отправляет
`credentials: "include"`, относительные `imageUrl` разрешает относительно API.
Используйте одинаковое имя хоста (`localhost` на обеих сторонах). В публикации
рекомендуется один origin через reverse proxy `/api`, HTTPS,
`COOKIE_SECURE=true` и точный `CORS_ORIGINS`. Настройте proxy timeout для синхронной
генерации и регулярное копирование БД **и** STORAGE_ROOT.

## Маршруты

| Метод | Путь | Назначение |
| --- | --- | --- |
| POST | /api/auth/register, /api/auth/login, /api/auth/logout | Аккаунт и сессия |
| GET | /api/auth/me | Текущий пользователь |
| GET | /api/elements | Только проверенные разрешенные элементы с файлами |
| GET | /api/elements/{code}/file | Исходный проверенный PNG |
| POST / GET | /api/generations | Создать результат / история с limit, offset, projectId |
| GET / PATCH | /api/generations/{id} | Открыть / переименовать, оценить, перенести в проект |
| GET | /api/generations/{id}/file?format=png\|jpg&download=true | Настоящий файл владельцу |
| POST / GET | /api/projects | Создать / список проектов |
| PATCH / DELETE | /api/projects/{id} | Переименовать / удалить проект, сохраняя историю |
| GET | /api/health, /api/capabilities | Готовность и поддерживаемые параметры |

Названия полей версии 0 сохранены в [API-CONTRACT.md](../API-CONTRACT.md).
История сохраняется автоматически, идентификаторы — строки. PATCH принимает
`rating: "like" | "dislike" | null`, `projectId: string | null`, `title: string`.
Чужие объекты возвращают 404. Ошибки имеют `error.code` и `error.message`.

## Что меняют параметры

- Композиция: медальон — радиальная раскладка, бордюр — три ленты повторов,
  раппорт — периодическая плитка с переносом мотивов через ее границы.
- Палитра и правила композиции читаются из PostgreSQL. Мотивы — только из
  разрешенных PNG в PostgreSQL; все выбранные мотивы входят в результат.
- `heritage`: мягкая исходная маска; `modern`: крупный одноцветный силуэт;
  `porcelain-sign`: синий контур; `leather-mosaic`: заливка и пунктирный шов;
  `festive`: чередование акцентных цветов. Названия — условные графические режимы.
- `parameters`: default / sparse / dense меняют плотность повторов.
- `usage`: architecture/textile 1024×1024, packaging/interior 1200×900,
  web 800×600. Раппорт квадратный, изменение размера сопровождается предупреждением.
- `prompt` сохраняется, но не интерпретируется; ответ имеет `PROMPT_UNSUPPORTED`.
  AI-редактирование и остановка уже начавшейся генерации не поддерживаются.

Рабочий пустой каталог дает 409 `CATALOG_EMPTY`, отсутствующий выбранный мотив —
422 `MOTIFS_UNAVAILABLE`. Синхронный запрос показывает неопределенный индикатор;
`progress=100` отдается только после сохранения настоящих файлов. Искусственного
прогресса или подмены отсутствующих мотивов нет.

## Тесты на отдельной чистой БД

Запустить из `db` отдельную PostgreSQL (Docker Desktop должен работать):

```bash
docker compose -p tatar-backend-check -f docker-compose.test.yml up -d --wait
```

Из backend:

```bash
export TP_TEST_DATABASE_URL=postgresql://tp_test@127.0.0.1:55432/tatar_pattern_backend_test
export PG_BIN=/opt/homebrew/opt/postgresql@16/bin
.venv/bin/pytest -q
```

Тесты делают бэкап, создают новую изолированную схему, применяют миграции дважды,
проверяют пароли/истечение и выход из сессии, права владельца, проекты и историю,
файлы PNG/JPG, сохранение после нового экземпляра сервера, влияние параметров,
периодичность раппорта, пустой каталог и валидацию/дубли/происхождение импорта.
БД с именем без `_test` не принимается. Рабочий каталог не используется.

Для ручной проверки на том же отдельном сервере (явно тестовые элементы):

```bash
export DATABASE_URL=postgresql://tp_test@127.0.0.1:55432/tatar_pattern_backend_test
export STORAGE_ROOT=./local-test/storage
export ALLOW_FIXTURES=true
.venv/bin/python -m scripts.migrate
.venv/bin/python -m scripts.fixtures --storage-root ./local-test/storage --confirm-test-fixtures
.venv/bin/uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Fixture-команда создает 8 синтетических прозрачных тестовых масок, отмечает все
`is_fixture=true`. Каждый результат имеет `TEST_FIXTURE`; доказательный SQL-счет
остается нулевым. Этот режим нельзя считать рабочим наполнением каталога.
Повторный запуск fixture-команды добавляет отдельный тестовый набор.

Для повторения сквозной проверки работающего сервера:

```bash
.venv/bin/python -m scripts.smoke --url http://127.0.0.1:8000 \
  --output-dir ./local-test/smoke
```

Команда регистрирует временный проверочный аккаунт, создает проект/результат,
переименовывает и оценивает, получает PNG/JPG, выходит и входит снова,
открывает сохраненный результат, удаляет проект и проверяет сохранность истории.
Пароль и сессионный токен в вывод не попадают.

Проверено 02.10.2026 на отдельной чистой PostgreSQL 16 в Docker:
**11 passed** (один deprecation warning от TestClient/httpx), включая обновление
legacy-схемы 001–004 с сохранением всех пяти сидов, пользователя и генерации.
Сквозная HTTP-проверка прошла; PNG и JPG декодированы как настоящие 800×600
изображения. Аудит тестового каталога: `real_unique_elements_with_files_and_provenance=0`.
Это проверка кода и тестового окружения, а не подтверждение готовности 100+.

## Безопасная загрузка после проверки человеком

1. Человек проверяет атрибуцию, права, исходный кадр, выделенный мотив и PNG.
   Для каждого самостоятельного мотива назначает постоянный `motifIdentity`
   внутри предмета; ракурсы и перекраски сохраняют ту же идентичность.
   ИИ-ретушь отдельно сверяет с исходным кадром.
2. Подготовьте JSON по [reviewed-manifest.example.json](reviewed-manifest.example.json).
   Пример специально имеет `humanApproved=false` и не пройдет импорт.
   После реальной проверки укажите проверившего, дату с часовым поясом,
   `humanApproved=true`, `reviewStatus=проверено`, `verifiedBy` для элементов.
3. Файлы уже должны лежать в выбранном STORAGE_ROOT, в БД записываются только
   относительные пути. PNG — прозрачный фон с видимым мотивом, 16–4096 px.
   Переходы за пределы хранилища и внешние symlink запрещены.
4. Валидация ничего не импортирует. Для проверки дублей в существующей БД
   добавьте `--with-db`; перед подключением автоматически создается бэкап:

```bash
.venv/bin/python -m scripts.catalog_import validate ./reviewed.json \
  --storage-root ./storage --report ./local-test/validation.json --with-db
```

Проверьте `valid`, `errors`, `duplicates`, количество записей, хэши файлов и
`approvalDigest` в отчете. Пропуски, неподтвержденные права/проверка, измененные
файлы и дубли блокируют импорт. Без `--with-db` проверка полностью локальная.

5. После просмотра отчета выполните явную команду с его digest:

```bash
.venv/bin/python -m scripts.catalog_import import ./reviewed.json \
  --storage-root ./storage --report ./local-test/import-result.json \
  --approval-digest DIGEST_FROM_VALIDATION_REPORT
```

Перед записью повторяются валидация, бэкап и проверка конфликтов с БД; реестр и
файлы должны соответствовать digest. Загрузка атомарная, существующие строки
не перезаписываются, в `catalog_imports` остается журнал. Непроверенные
annotations.csv и SQL разметки этим инструментом не принимаются.

6. Обновите факт наличия файлов и выполните доказательный подсчет:

```bash
.venv/bin/python -m scripts.catalog_audit --storage-root ./storage \
  --report ./local-test/catalog-audit.json
```

SQL: [count_real_elements.sql](../db/queries/count_real_elements.sql). Он исключает
fixtures и дубли и требует связанные файлы/происхождение. Наличие файлов
проверяется на момент аудита; смысловую уникальность подтверждает человек.

## Ограничения перед публикацией

Нужен реальный проверенный каталог с выделенными файлами и происхождением.
Тестовые фигуры и пять демонстрационных сидов не засчитываются в 100+.
Нужна интеграция frontend по контракту, настройка HTTPS/reverse proxy и
резервного копирования. Обученной модели, Redis/ARQ и AI-редактирования в v0 нет.

## Актуальное продолжение 08.10: настоящий каталог, локальная БД

Пакет и решения: [catalog-input/README.md](catalog-input/README.md).
110 реальных мотивов, 65 классов. Приемка качества владельцем отделена от
экспертного происхождения и прав. Защищенные RAW/PNG/annotations не меняются.
Плоский режим original сохраняет цвета PNG; silhouette использует alpha.
Независимой внутренней перекраски нет. RGBA PNG может быть прозрачным;
JPG складывается на backgroundColor/фон палитры. Подробности в API-CONTRACT.md.

Явный launcher читает только существующие параметры проекта db/.env, не печатает
пароль и не подставляет неизвестное внешнее окружение:

```sh
.venv/bin/python -m scripts.local_environment isolated_test .venv/bin/pytest -q
.venv/bin/python -m scripts.local_environment local_project .venv/bin/python -m scripts.install_local_catalog
.venv/bin/python -m scripts.local_environment local_project .venv/bin/python -m scripts.catalog_audit --storage-root catalog-input --report local-test/local-catalog-audit.json
.venv/bin/python -m scripts.local_environment local_project .venv/bin/python -m scripts.real_http_smoke
.venv/bin/python -m scripts.local_environment local_project .venv/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

install_local_catalog — однократный импорт: существующие записи не перезаписывает,
повтор останавливается как дубль. Перед миграциями/импортом создаются custom-format
БД backup и tar.gz файлов catalog-input, storage и прежнего local-test/storage
(включая отсутствие каталога). Все backup — db/backups, 0600. Не удалять volume.
В production локальная ветвь реестра не отображается без подтвержденных прав.

### AI подготовка

`app/ai_provider.py` — Protocol без предположений о DSLab API; конфигурация пока
возвращает None, AI отвечает 503. `ai_jobs` в PostgreSQL и отдельный worker
сохраняют задания/идентификаторы облака при перезапуске; дополнительный Redis
для единственного воркера не нужен. Worker запускается отдельно от HTTP после
подтвержденной реализации адаптера: `python -m scripts.ai_worker`.
Тестовый адаптер в tests/test_ai_jobs.py явно синтетический.
Нужны ИИ/DSLAB-INTEGRATION.md, версия модели и сценарий, серверные секреты,
подтвержденные входные материалы/правила передачи и бюджет. Подробные состояния,
timeout, ограничения и отсутствие отмены GPU описаны в контракте.
