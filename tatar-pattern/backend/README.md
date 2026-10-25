# Гостевой первый релиз — актуальное продолжение19.10.2026

**LOCAL IMPLEMENTED; production/облачная приёмка не выполнены, legal DRAFT сохранён.**
Приоритет этого раздела над исторической аккаунтной README ниже.
Точный браузерный контракт/JSON/ошибки — верх [API-CONTRACT](../API-CONTRACT.md).
Нет users для гостей; миграция **013_guest_transient.sql** additive,001–012 не изменены.
Рабочая5432/production/SSH/GPU/frontend/deploy/чужие summary в этой работе не менялись.

## Запуск и конфигурация

Перед изменениями существующего окружения — принятый backup/storage/drain порядок.
Мигратор сам делает pg_dump **до** SQL. Образ должен содержать013 и новые app/scripts.
Не запускать новый worker/API со старой схемой012. QA schema без полного migration
ledger требует отдельной проверенной patch процедуры; общий migrate поверх неё
вслепую не использовать. Локальные тесты создают новую schema в отдельной55432.

```bash
# Из backend, с заранее безопасно настроенными DATABASE_URL/STORAGE_ROOT/PG_BIN:
.venv/bin/python -m scripts.migrate
# Для публичного HTTPS окружения:
export PUBLIC_GUEST_MODE=true
export COOKIE_SECURE=true
export GUEST_TTL_SECONDS=86400
export GUEST_CONCURRENT_JOBS=2
export GUEST_CREATES_PER_MINUTE=20
export GUEST_GPU_BUDGET=0
.venv/bin/uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

В production `TP_ENVIRONMENT=production`, HTTPS и правильный CORS_ORIGINS/один origin.
В изолированном local HTTP COOKIE_SECURE=false; это не проверка production HTTPS.
Старые account пути возвращают404 даже с действительной tp_session, cookie удаляется
при обращении к API. Закрытый прежний режим допускается только явно
PUBLIC_GUEST_MODE=false и вне публичного релиза. Это не команда удаления старых users.

GUEST_GPU_BUDGET — cumulative cap **принятых задач**, default0, не рубли.
Счётчик guest_budget/gpu-total увеличивается атомарно с durable enqueue и не
обнуляется очисткой. Значение потолка увеличивают только для разрешённого окна;
replay/failed/uncertain не возвращает израсходованный слот. Учесть худшую стоимость
профилей/существующие GPU admission ограничения до выбора числа. Release/transfer/
AI_MVP_ENABLED/proof не меняются этим env. При выключенных gates AI_UNAVAILABLE,
при исчерпанном cap AI_BUDGET_EXHAUSTED; fallback отсутствует.

## Что и где хранится

- PostgreSQL: guest_processes UUID/hash/created/expiry, generations с user_id=NULL и
  guest owner/expiry/requestId/fingerprint/строгими параметрами/recipe/status/error;
  ai_jobs — прежний durable payload/deadline/externalID и случайный server UUID provider_request_id (GPU Idempotency-Key). Он не зависит от числовой sequence, client requestId или cookie и не попадает в браузер. Аккаунтные таблицы/FK и
  прежние ownership проверки сохранены. Никаких email/password/profile/visitor ID.
- Files: только STORAGE_ROOT/**guest-results/**, PNG/JPG/module/tmp. Этот каталог
  не раздавать через nginx/static/alias. Отдельные каталог/source/AI qualification
  evidence остаются на прежних путях и не являются transient results.
- Browser: tp_guest256бит HttpOnly SameSite=Strict Path=/api/guest, production Secure;
  сервер хранит SHA256. Fixed до24ч от bootstrap, задачи могут жить меньше24ч.
  Poll/download/replay не продлевают. requestId не секрет/не авторизация; UI может
  держать только текущий запрос/ID/expiry в sessionStorage до срока, очищая свои
  старые аккаунтные keys. Backend не создаёт localStorage/долгий visitor ID.
- IP: request.client.host используется только для rate buckets в RAM API (20/min,
  ≤10000 адресов; удаление без активности при минутном sweep, обычно≤120сек).
  В БД гостевых IP/UA/Referer нет. За proxy фактический client.host зависит от
  доверенных proxy headers: проверить на Beget; без этого bucket может быть общим
  IP proxy. Не доверять произвольным внешним X-Forwarded-For.
- App ошибки логируют тип исключения/фиксированный код, без cookie/Bearer/JSON/URL
  секретов. Uvicorn по умолчанию может писать IP/path/status; команда выше выключает
  access-log, reverse proxy/provider logs остаются инфраструктурным фактом. Их14дней
  календарной ротации этим кодом **не реализованы**; Docker size rotation не срок.
- guest_budget содержит только агрегаты: минутные удаляются спустя1–2мин, gpu-total
  сохраняется без персональных данных, чтобы restart/reset не восстанавливал бюджет.

## Expiry и регулярная очистка

HTTP проверяет clock_timestamp при каждом допуске/status/file. Файлы не выдаются
после expiry даже если unlink ещё pending. Передача, начатая до срока, может
закончиться позже. Worker проверяет срок до submit, после poll/download и перед
commit; поздние ответы не воскрешают доступ/строки/файлы. Истёкшая queued не submit.
Deadline15мин/reconcile/неповторяемый uncertain submit и930/950/960сек drain сохранены.

API lifespan и worker sweep60сек: expired поколения →durable file queue →DELETE
ai_jobs/generations/process hash →commit→unlink. Обычная физическая задержка≤60с;
ошибки FS сохраняют pending/attempts/error-type для retry и требуют контроля оператора.
Orphan/temp без committed строки имеют исходный expiry в серверном имени и
удаляются по нему, даже с новым mtime; старые неформатные orphan — по mtime≤TTL. Успешные
гостевые file queue entries удаляются. Гостевой sweep не трогает account file queue.
При остановленных сервисах организовать внешний минутный запуск этой **готовой CLI**:

```bash
.venv/bin/python -m scripts.guest_maintenance cleanup
.venv/bin/python -m scripts.guest_maintenance status
# Только оператору: минимальные внешние reference, без ключей/изображений
.venv/bin/python -m scripts.guest_maintenance reconcile-list
```

`pendingGuestFiles>0` — устранить права/диск/FS, повторить cleanup и убедиться в0.
CLI ошибки/ненулевой exit нельзя считать удалением. Настройку cron/systemd делает
Beget в своей зоне. Простой API/worker не означает исполнение фоновой очистки.

Только pending/failed/неопределённая внешняя операция может оставить минимальный
`guest_reconciliations`: generation_id и отдельный server UUID provider_request_id, provider,
provider_job_id или uncertain, expiry от создания≤7дней. Полного payload/PNG/key нет.
Late ack дописывает jobId в этот след, не создаёт новую generation. Cleanup удаляет
просроченный след; это окно сверки, а не очередь нового submit/скачивания картинки.

### GPU cleanup: реальная ручная процедура, ещё не приёмка на ВМ

GPU API cancel/delete отсутствуют — никакие такие HTTP вызовы не реализованы.
До7дней оператор по provider_request_id и известному jobId сверяет
существующий state/log с LoRA/Beget, фиксирует фактическое состояние и время expiry.
Uncertain без jobId ищется по **тому же provider request reference**, без нового POST.
Если штатный TTL GPU подтвердился, получить фактическое отсутствие обычного PNG и
записи после соответствующего срока (GET image404 сам по себе не доказывает удаление
SQLite/logs/snapshot). При адресном досрочном удалении оператор сначала корректно
останавливает/дренирует сервис, применяет проверенную LoRA процедуру к конкретному
обычному job/PNG/state, проверяет отсутствие после restart; qualification не удаляет.
Точные SQL/path команды не выдумываются без фактической GPU схемы/согласованного
исполнения. Подтверждение хранится в защищённом операционном протоколе отдельно от
transient zone; не записывать там cookie/Bearer/изображение.

Только после фактической проверки, с reference на этот протокол:

```bash
.venv/bin/python -m scripts.guest_maintenance confirm-external \
  --provider-request-id 'server-uuid-from-reconcile-list' --confirmation-ref 'ops-verified-reference' \
  --designated-operation 'assigned-operation'
```

Команда удаляет минимальный след, не вызывает GPU delete и не подтверждает его
сама; перед изменением делает существующие storage+DB backups. Если за7дней нельзя
закончить сверку/подтвердить GPU TTL, это конкретный блокер владельцу/юристу до окна,
не основание оставить весь guest payload/изображение бессрочно. Обычный GPU current
TTL24ч от finished/7д state, qualification исключение и snapshots — подтвердить отдельно.

## Restore: обязательный полный сброс guest зоны до public start/worker

Обычные ops full dump/storage backup **пока включают guest rows/files/hash/payload**.
Исключение transient из штатных copies/сроки/география/ротация backup/WAL — задача
Beget/владельца. Старые dumps не раздавать, не импортировать users/QA в production.
Этот backend даёт реальное удаление восстановленной guest зоны без аккаунтного ledger.

1. Закрыть внешний доступ и остановить API→worker по существующему порядку
   (930/950/960сек не менять), получить exit0+новый DRAINED; при nonzero сохранить
   DB/tunnel, следовать прежнему failure handling. Backup по существующему ops.
2. Восстановить DB+storage **офлайн** в выделенное окружение. Включить в образ013;
   применить миграции через существующий мигратор с backup, если их нет.
   Выставить GUEST_GPU_BUDGET=0. Не запускать worker/public API даже «для проверки».
3. Из backend с DB/storage именно восстановленной копии выполнить:

```bash
export TP_ENVIRONMENT=production   # isolated_test только для отдельной тестовой БД
export PUBLIC_GUEST_MODE=true
export COOKIE_SECURE=true
export GUEST_GPU_BUDGET=0
.venv/bin/python -m scripts.guest_maintenance reset-restored \
  --offline-restore --designated-operation 'assigned-restore-operation'
.venv/bin/python -m scripts.guest_maintenance status
```

Команда сначала делает storage+pg_dump backup по прежнему порядку, проверяет отсутствие
живого worker через advisory lock, полностью удаляет guest generations/ai_jobs/process
hashes, все guest-results файлы (включая незарегистрированные/restored tmp), повторяет
file queue и отказывает при остатке. API должен быть остановлен оператором;
`--offline-restore` — обязательное утверждение этого условия, не автоматический stop.
Каталог, источники, release decisions, qualification, миграции и старые account rows
не стираются. gpu-total не обнуляется. Минимальные внешние reference сохраняются≤7д;
восстановленную queued не submit, submitting/knownId только передаются для ручной сверки.
Повтор безопасен. При FS/symlink/error — **оставить offline**, устранить и повторить.

4. Успех: guestProcesses=0, guestGenerations=0, pendingGuestFiles=0, guest-results
   не содержит файлов; externalReconciliation может быть>0 и требует сверки.
   Старые cookie/ID дают401/404, ai_jobs гостевых нет, provider submissions=0.
   Только после этого открывать сайт/worker. Устаревший gpu-total из backup может не
   знать более поздние расходы: новый ненулевой потолок требует сверки оператора,
   автоматическое пополнение cap после restore запрещено.

Backup перед reset тоже содержит старые transient данные: держать его закрытым по
операционному порядку; **любое** его последующее восстановление повторяет этот reset.
Уничтожение файлов сайта не означает уничтожения всех инфраструктурных копий.

## Адресная локальная проверка

```bash
.venv/bin/python -m scripts.local_environment isolated_test .venv/bin/pytest -q \
  tests/test_guest.py tests/test_gpu_worker.py tests/test_worker_signal_deadline.py
```

Только PostgreSQL55432/новая schema/temp storage; обязательный backup до миграций.
Real110 flat PNG/JPG/module и real loopback HTTP; AI только явные isolated mocks,
release flags меняются только в tmp JSON тестов. HTTP smoke без cookie/секретов:
`local-test/guest-release-2026-10-19/http-smoke.json`. Итог и ограничения в backend summary.
Никакие local mocks не являются cloud/site E2E или готовностью публичного релиза.

---

# Историческая README аккаунтного режима

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

## Подготовка релиза 19.10.2026: каталог110 и Beget

Основной manifest остаётся v2 `catalog-input/owner-accepted-2026-10-08.json`.
Декларация владельца 11.10 учитывается ссылкой `direct_owner_declaration_2026-10-11`;
повторная декларация для подготовки не нужна. `verifiedBy=null`, `отрисовано`,
`documented_unverified`, source legal_basis=NULL/rights=неясно сохраняются.
Это не экспертная культурная приёмка. Public scope хранится отдельно от local rights.

Подготовленный комплект: `local-test/production-catalog-2026-10-19/`:

- `catalog110.tgz` + `.sha256`: **110 flat +110 texture +49 исходных кадров +manifest**;
  3 источника,46 предметов,110 уникальных SHA/областей источников. Только allowlist файлов;
  users, sessions, QA, results, рабочая БД и дампы в пакет не входят.
- `validation.json`: целостность всех269 файлов и approvalDigest.
- `release-decision.pending.json`: точные110 codes + manifestSHA + отдельный public scope.
  `approved=false` — конкретная реестровая запись публичного использования ещё не утверждена.
  Владелец/ответственный фиксирует approvedBy/approvedAt/evidence и approved=true для
  `public_flat_catalog`, не меняя список/SHA. Это подтверждение объёма записи релиза,
  не повторная декларация и не повышение verifiedBy. Transfer/training остаются false.

Воспроизведение пакета из backend (не БД):

```bash
.venv/bin/python -m scripts.production_catalog prepare --input catalog-input --output local-test/production-catalog-2026-10-19
```

### Назначенная серверная операция — выполняет Beget после решения владельца

Команды ниже подготовлены, **на сервере не выполнялись**. Нужен новый backend image
с миграциями011/012 и scripts. Текущие старые images этих изменений не содержат.
Сначала согласованный maintenance: закрыть API admission, штатно drain worker/tunnel
через действующий `ops.py stop-ai`; при exit75/ненормальном exit сохранить DB/tunnel
и сверить persisted состояния. Публичный доступ во время миграций закрыт.
Не создавать production восстановлением рабочей локальной БД/QA backup.

Из каталога deploy выбранного server release, рядом с его `.env`, после защищённой
передачи комплекта (НЕ публикации в webroot):

```bash
sha256sum -c catalog110.tgz.sha256
mkdir catalog-stage
tar -xzf catalog110.tgz -C catalog-stage --no-same-owner
```

Права каталогов/файлов должны позволять UID10001 читать staging и подписанное
`release-decision.approved.json`; storage и migration-backups доступны UID10001 на запись.
Staging на диске хоста: пакет около277MiB, не помещать его в контейнерный tmpfs128MiB.
Замените значение operation_ref на реально назначенную владельцем операцию:

```python
# python3 из deploy выбранного релиза; не печатает/не передаёт пароль в argv.
from pathlib import Path
from ops import read_env, compose

envfile = Path('.env').resolve()
values = read_env(envfile)
dc = compose(envfile, values)
stage = Path('catalog-stage').resolve()
decision = Path('release-decision.approved.json').resolve()
operation_ref = 'OWNER_ASSIGNED_OPERATION_REQUIRED'
assert operation_ref != 'OWNER_ASSIGNED_OPERATION_REQUIRED'
dc('run', '--rm', '--no-deps', '-T',
   '-v', f'{stage}:/catalog-input:ro',
   '-v', f'{decision}:/release-decision.json:ro',
   'backend', 'python', '-m', 'scripts.production_catalog', 'apply',
   '--input', '/catalog-input', '--storage-root', '/data/storage',
   '--decision', '/release-decision.json', '--designated-operation', operation_ref)
dc('run', '--rm', '--no-deps', '-T',
   '-v', f'{decision}:/release-decision.json:ro',
   'backend', 'python', '-m', 'scripts.production_catalog', 'verify',
   '--input', '/data/storage', '--storage-root', '/data/storage',
   '--decision', '/release-decision.json')
```

Apply сначала полностью создаёт backup storage и pg_dump, затем миграции (мигратор
повторно делает pg_dump), staging без перезаписи, транзакционное связывание public scope.
Результат обязан содержать `publicRealUniqueElements:110`. Проверка читает реальные
файлы/PNG/SHA/источники, а не только старый SQL file_available. Snapshot фиксирует
provenance/status/источники/пути/качество; повтор с тем же решением = replay=true,
изменённое решение/БД/файл/частичный конфликт → отказ без overwrite. Apply можно
повторить той же командой; verify read-only, не импортирует и не мигрирует.
Сохранить stdout+backup filenames+SHA approved decision в закрытом release evidence.

При ошибке не применять reset/force и не подменять prod дампом с Mac. Сохранить backup,
проверить конфликт; добавленные до SQL файлы могут оставаться несвязанными, повтор их
проверяет побайтно. Для аварийного rollback использовать согласованный offline restore
Beget **и latest erasure ledger**, описанный ниже; не открывать restored сайт до проверки.

### Правовые зависимости: что пока НЕ утверждено

В доступном handoff07 всё ещё v0.2 от11.10, предлагаемый контракт, а не действующий
регламент. До решения владельца/юриста/front не включать публичную регистрацию:
нужны опубликованные неизменяемые versions/SHA/effectiveAt, termsAcceptance,
выбранное основание optional profile/hosting/AI, точный набор отдельных согласий,
канал/ответственный/сроки обращений и сроки legal_events/logs/backup/WAL/provider copies.
Имена уже допускают пустые строки, обязательны email/password. Отдельные grants,
terms acceptance и их immutable archive/event journal **ещё не реализованы**: поля
и опубликованные версии требуют согласования. Историческим users ничего не приписано.

Независимая подготовка в012/erasure.py: access_blocked и отзыв всех sessions,
транзакционные block_account/erase_account_local, provider reconciliation,
file queue с retry, tombstone и offline replay. Эти внутренние функции проверены
с синтетической операцией; публичного REST закрытия аккаунта/готового операторского
регламента пока нет. `privacy_operations` — техническая стадия, не журнал legal acceptance
и не подтверждение исполнения всех юридических обязанностей. Для ручного минимального
релиза юрист/владелец должны принять процедуру и канал; потом подключается operator entrypoint.
Не обещать пользователю самообслуживание или «всё уничтожено» после локального SQL.

Корзина7дней — существующее продуктовое поведение, не вновь утверждённый юридический
срок уничтожения аккаунта. Рекомендации7/14/30дней не введены как обязательный регламент.
Sessions с истекшим expires_at удаляются в hourly cleanup/при library access;
при blocked account вход запрещён и sessions отозваны. Это календарь исполнения
имеющейся технической уборки, не обещание точного удаления в ту же секунду при downtime.

### Файлы, AI и restore: исполнимая техническая часть

Trash expiry записывает tombstone, provider reference и storage_deletions, явно удаляет
ai_jobs ДО generations, коммитит; затем удаляет PNG/JPG/module/tmp. OSError/ValueError
оставляют durable pending+attempts+тип ошибки; повтор проверяет отсутствие. Пути/секреты
не пишутся в лог. Удаление аккаунта использует ту же инфраструктуру.
Worker повторно блокирует строку generation перед submit и перед output commit;
поздний done после удаления не скачивается/не сохраняется, acknowledgement после удаления
остаётся в provider_deletions. Удаление/timeout не означает GPU cancel/delete.
GPU API не имеет согласованного DELETE/cancel: provider_deletions=manual_required,
оператор обязан фактически подтвердить удаление state/PNG/logs/idempotency у провайдера.
Автоматически ставить confirmed нельзя. Это остаётся release-зависимостью.

После миграций оператор может выполнить из backend service с теми же DB/storage:

```bash
python -m scripts.privacy_maintenance status
# retry — только в назначенной операции, с backup до изменений:
python -m scripts.privacy_maintenance retry --designated-operation OWNER_OPERATION_REF
python -m scripts.privacy_maintenance export-ledger --ledger /data/storage/erasure-ledger.json
```

Экспортированный latest ledger+SHA нужно независимо сохранить в защищённом операторском
хранилище, которое НЕ откатывается вместе с DB/storage backup. Содержит минимальные
ID/пути/технические операции, без email/профиля/prompts. Срок/доступ/ответственный ещё
утверждаются. Сам файл в storage без независимой копии restore protection не обеспечивает.
Перед открытием offline restored экземпляра (той же DB lineage), после его backup:

```bash
python -m scripts.privacy_maintenance replay-ledger --offline-restore --ledger /data/storage/latest-erasure-ledger.json --sha256 ACTUAL_VERIFIED_SHA256 --designated-operation OWNER_RESTORE_OPERATION
python -m scripts.privacy_maintenance status
```

Повтор replay идемпотентен; удаляет восстановленные users/generations, снова очередит
пути и отзывает sessions. Local queues/status не доказывают удаление provider/logs/backups.
Доступ к tombstoned generation скрыт из history/file/restore; ledger должен быть применён
до public start, поскольку старый backup сам не знает о более поздних удалениях.
Runtime offsite ledger/backup restore и provider cleanup с Beget ещё не выполнены.
