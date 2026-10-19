# DEPLOY-PACK — pilot-20261011-2

Дата: 11.10.2026, Europe/Moscow. Статус: release-комплект подготовлен для переноса.

## Результат и способ развёртывания

Полный архив: `releases/pilot-20261011-2/tatar-pattern-pilot-20261011-2.tar.gz`
(относительно рабочей папки «Разработка»). Внутри один корень `tatar-pattern/`:
backend, frontend, миграции 001–010, deploy, исходные утилиты, инструкции,
текстовые отчёты и **четыре готовых linux/amd64 образа** в
`deploy/images/pilot-20261011-2-amd64.tar.gz`.

SHA-256 полного архива — в соседнем `tatar-pattern-pilot-20261011-2.tar.gz.sha256`.
Его собственный hash не помещается внутрь архива во избежание рекурсивной зависимости.
Manifest релиза: `deploy/RELEASE-MANIFEST.json`; список образов/digests: `deploy/IMAGES.json`.
`deploy/SOURCE-SHA256.json` покрывает **все передаваемые обычные файлы**,
включая инструкции, отчёты, manifests и внутренний архив образов, кроме самого
SOURCE-SHA256.json. Внешний SHA покрывает весь архив вместе с этим manifest.

Основной способ — `docker load` проверенных amd64 образов, **без сборки на Beget**.
При 4 ГБ RAM не выполнять там npm ci/next build и параллельные сборки.
В неизменённом production Compose лимиты: PostgreSQL 1024 MiB, backend 1024 MiB,
frontend 768 MiB, Caddy 128 MiB; сумма 2944 MiB. При физических 4 GiB остаётся
1152 MiB для ОС/Docker; фактический объём RAM и нагрузку проверить на сервере.
Это лимиты конфигурации, а не измеренная гарантия пикового потребления.
Один backend worker; AI worker в этот комплект не добавлен.

## Журнал всех действий этой задачи

1. Полностью прочитаны оба запрошенных summary: «Чат 2. Backend и PostgreSQL»
   и «Чат 3. Frontend и главная». Учтены обновления 08–11.10 и миграция 010.
   Прочитаны frontend/AGENTS.md, backend/pyproject.toml, Dockerfile/ignore,
   Compose, ops.py, test_ops.py, deployment HANDOFF и FRONTEND-COMPATIBILITY.
2. Инвентаризированы исходники, lock-файлы, локальные результаты и образы.
   243 файла SOURCE-SHA256-NEXT164-AMD64.json совпали с текущими исходниками.
   Старый SOURCE-SHA256.json содержал прежние версии и .DS_Store: заменён.
   Исторический snapshot и старые LOCAL-RESULT/PORTS-CHECK не включены в комплект.
3. Создан этот отдельный отчёт. Чужие отчёты и summary не редактировались.
   Нет Git-коммита общего проекта: фиксация — immutable archive и hashes.
4. Sandbox отказал обычному чтению Docker socket. Разрешённый локальный Docker-доступ
   использован для inspect/build/pull/run/save и изолированной приёмки.
   Не было действий с Beget, production или публичными портами.
5. Backend собран штатным Dockerfile под новым tag pilot-20261011-2 для linux/amd64.
   Frontend сначала собран из совпадающих исходников, затем **финально пересобран**
   после добавления `**/.DS_Store` в Dockerfile.frontend.dockerignore.
   Комплект содержит только последний frontend image; промежуточный образ не передаётся.
   npm ci, webpack build, TypeScript и prune прошли. Логи сохранены в release-evidence.
6. Загружены PostgreSQL 16-bookworm и Caddy 2.10.2 для amd64. Выявлено, что обычный
   inspect multi-platform tags на Mac показывает ARM. Попытка tag по внутреннему
   platform ID не сработала (No such image); исправлено pull по registry manifest
   конкретной amd64 платформы, затем создание отдельных release tags.
   Все четыре release tags проверены как linux/amd64. Старые контейнеры не менялись.
7. Изменён **только шаблон** deploy/.env.example: RELEASE=pilot-20261011-2,
   POSTGRES_IMAGE/CADDY_IMAGE — соответствующие локальные release tags.
   Реальные .env, production Compose/Caddyfile/systemd и бизнес-логика не изменены.
   ops.py не требовал правок: он читает RELEASE из выбранного env и использует
   его для build/check-frontend/migrate/backup/restore. init теперь получает новый
   RELEASE из обновлённого шаблона. 4 существующих unit tests ops повторно прошли. Дополнительно init с временным
   внешним .env проверен: новый release/image tags, случайный пароль, chmod0600;
   временный конфиг удалён без сохранения секретов (ops-init-check.json).
8. Проверены runtime frontend: Node22.23.3, Next16.4.0, React/ReactDOM19.2.8,
   пустые rewrites; eslint/eslint-config-next/braces физически отсутствуют.
   Свежий **npm audit --omit=dev внутри финального amd64 образа: exit0, 0 vulnerabilities**.
   Полный source audit коллег сохраняет 5 High dev-only braces; обоснование и границы
   исключения сохранены в frontend/qa/security-2026-10-11/VERIFICATION.md.
   Полный source audit не объявляется чистым. Его отчёт датирован 11.10, новый runtime audit выполнен этой задачей.
9. Backend runtime: Python3.12.15, FastAPI0.142.2, uvicorn0.54.0, psycopg3.3.6,
   Pillow12.3.0, argon2-cffi25.1.0; imports прошли без сети/БД.
   SHA всех 10 миграций внутри образа совпали с текущими SQL.
10. Дополнительно пройден **полный linux/amd64 стек** (эмуляция на Mac ARM64):
    tp-deploy-check-cbe8c110d2, новая отдельная PostgreSQL, отдельный bind storage,
    только 127.0.0.1 proxy. config/check-frontend/up-internal/migrate/fixtures/up-local
    и local_test.py прошли. 8 synthetic fixtures, 0 реальных production элементов,
    AI unavailable. Вход/выход/история, HttpOnly/Lax/Path cookie, foreign Origin403,
    ownership404, PNG/JPG/attachment, restart с прежней session и SHA прошли.
    Согласованный DB+storage backup 20261011T150301Z-bdd6fe и изолированный restore
    tp-restore-3637c5ce: hashes/rowcounts/API DB health PASS.
    Тестовые контейнеры/сети сняты **без -v**; данные/секретный test.env остались только
    в исключённом local-check, не передаются. Рабочая БД5432 не использовалась.
11. Сверены файлы реально сохранённого кода в образах: backend/scripts/migrations/locks
    — 36 SHA, без расхождений; frontend/src/public/config — 232 SHA.
    Единственное ожидаемое отличие — runtime package-lock.json после npm10.9.9 prune:
    из 38 записей удалено поле libc; набор пакетов, версии, resolved/integrity,
    dependency edges и root dependencies идентичны. Это доказано структурным сравнением,
    сохранено в image-source-match.json. Исходный lock передаётся без изменений.
12. Docker save выполнен **с --platform linux/amd64** для четырёх release tags;
    gzip -n исключает timestamp исходного имени. Проверены manifest.json и configs
    внутри Docker-архива: ровно 4 образа, os=linux/architecture=amd64, rootfsDiffIds
    совпадают с inspect. SHA внутреннего архива:
    `bb3a3aa164c17cbcef01825d501540ee312e30ea97988b5f62b89ae1c3738353`;
    размер 448675785 bytes. App images локальные, registry публикации не было.
    Docker load из передаваемого архива прошёл; verifier подтвердил все четыре
    загруженных образа по platform/ID/rootfs. Лог — docker-load-check.log.
    Различаются image index, platform manifest и portable config digests;
    IMAGES.json фиксирует все доступные значения и проверки после docker load.
13. Копии актуальных deployment JSON/log/restore proof вынесены из local-check
    в deploy/release-evidence. Прежний проверочный результат отмечен previous-*;
    результат этого release — release-amd64-*. Frontend QA текстовые отчёты/логи,
    advisories, результаты 5 клиентских тестов и 16 API проверок сохранены.
    QA-картинки/скриншоты исключены вместе с пользовательскими/рабочими изображениями.
    Публичные статические UI assets frontend/public необходимы сайту и включены.
14. Добавлены verify_release.py (точный состав+SHA, опционально Docker IDs/rootfs/platform)
    и package_release.py (сортировка, фиксированные tar uid/gid/mode/mtime и gzip header).
    Новый clean staging сформирован по allowlist. SOURCE-SHA256.json пересоздан по нему
    и скопирован обратно в исходный deploy; manifests относятся именно к передаче.
15. Упаковка и заключительная проверка прошли: **396 файлов в архиве, 395 SHA**
    плюс сам SOURCE-SHA256.json. Проверены точный состав, SHA каждого файла,
    отсутствие symlinks/запрещённых путей и сигнатур private keys/AWS/session/Bearer
    секретов. Docker-архив соответствует IMAGES.json. Drift итогового source tree нет.
    Повторная упаковка clean tree дала идентичный SHA-256; временный повтор удалён.
    Результат — PACK-VERIFICATION.json рядом с полным архивом; manifests и этот отчёт
    дополнительно скопированы туда для чтения без распаковки. После записи этой итоговой
    отметки архив пересоздан и проверен той же процедурой; финальный SHA указан только
    во внешнем .sha256 и PACK-VERIFICATION.json.

## Что исключено

deploy/local-check, backend/local-test, backend/catalog-input (рабочие изображения),
все test.env и реальные .env, БД/dumps/backups, .venv, node_modules, .next, .git,
.qa, storage/data, .figma-cache, caches, .DS_Store, pyc, tsbuildinfo, backup-файлы,
исторические source manifests/старые локальные result JSON, QA raster outputs.
.env.example — только проверенные placeholders/несекретные release tags, включены
для воспроизводимой настройки. Исходники тестов и test Compose — код, не тестовая БД.
Исходный датасет, рабочая локальная БД и личные данные не входят в release.

## Образы

Все теги имеют суффикс `:pilot-20261011-2`:

| Образ | Версия | amd64 platform manifest digest |
| --- | --- | --- |
| tatar-pattern-backend | Python3.12.15 / app0.1.0 | sha256:626f308505142710bbe5b511abd0d84ffd163caf284d609afde0d489bc940d18 |
| tatar-pattern-frontend | Node22.23.3 / Next16.4.0 / React19.2.8 | sha256:9f898f04d5bf4fee3a21683d50275ffbf3237a85bd24e8107ed1ab5c94c765e1 |
| tatar-pattern-postgres | PostgreSQL16.15 | sha256:ec9f656f17c8b4dfebf49e58cf5c46d493d4846d4ea6d8b85d0637f68ee33bfc |
| tatar-pattern-caddy | Caddy2.10.2 | sha256:d8c17a862962def15cde69863a3a463f25a2664942eafd7bdbf050e9c3116b83 |

Portable config digests, rootfs и registry provenance — в IMAGES.json.
После docker load классический Docker может показывать config digest в .Id,
а containerd — index/manifest digest; verifier учитывает эти представления.

## Краткая инструкция по переносу (выполняет владелец позже)

Требования: Linux amd64, Docker Engine и Compose v2, Python3.12+ для ops.py
(hashlib.file_digest, tarfile filter), gzip/tar/sha256sum. Проверить свободный диск:
образы в распакованном Docker-хранилище занимают больше сжатого архива; желательно
не менее 6 GiB свободно до загрузки, отдельно место под storage/backups.

1. Передать полный .tar.gz и его .sha256 в новую папку release на сервере.
   Не накладывать файлы поверх старого checkout и не переносить local-check/БД.
2. В папке с архивом выполнить:

```bash
sha256sum -c tatar-pattern-pilot-20261011-2.tar.gz.sha256
mkdir -p pilot-20261011-2
# Папка pilot-20261011-2 должна быть новой/пустой.
tar -xzf tatar-pattern-pilot-20261011-2.tar.gz -C pilot-20261011-2
cd pilot-20261011-2/tatar-pattern
python3 -B deploy/verify_release.py
docker load -i deploy/images/pilot-20261011-2-amd64.tar.gz
python3 -B deploy/verify_release.py --images
```

3. Создать новый серверный конфиг только на сервере:

```bash
python3 -B deploy/ops.py init
chmod 600 deploy/.env
```

Заполнить DOMAIN, ACME_EMAIL, DATA_ROOT (вне release), проверить проект
COMPOSE_PROJECT_NAME. RELEASE и четыре image tags оставить pilot-20261011-2.
Пароль уже случайно создан init; не отправлять его в чат/логи. Затем:

```bash
python3 -B deploy/verify_release.py --images --allow-local-config
python3 -B deploy/ops.py config
python3 -B deploy/ops.py check-frontend
```

Эти проверки не открывают публичные порты. Дальнейшие внутренние migrate/audit/import,
backup/offsite и native amd64/HTTPS/reboot приёмка — по BEGET.md/README и ограничениям
ниже. Эта задача не запускала сервер и не выполняла publish.

## Границы и воспроизводимость

Сохранены ранее проверенные результаты lint/TypeScript/5 API-client tests/16 API checks
и полный свежий изолированный amd64 Compose pass. Проверка Mac-эмуляции не заменяет
native Beget load/HTTPS/reboot/mobile приёмку. Production каталог отдельно импортируется
по фактическим правам/provenance и проверенным storage путям; переноса рабочей БД нет.
AI unavailable; интеграция реального provider/LoRA не входит в комплект.
Доменные/правовые/каталоговые пункты HANDOFF сохранены как исходные сведения,
не превращены в новые изменения бизнес-логики этой задачи.

Передаваемые готовые images фиксируют точные проверенные runnable артефакты.
npm/uv lock и digest баз Dockerfile сохранены. Внешние APT-репозитории не snapshot:
повторная Docker-сборка в будущем не обещает побитового совпадения digests.
Для повторения **того же архива** из неизменённого распакованного clean release:

```bash
python3 -B deploy/package_release.py --output /tmp/tatar-pattern-pilot-20261011-2.tar.gz
```

В clean tree не должно быть созданных .env, дополнительных файлов или кэшей.
Внешний checksum и PACK-VERIFICATION.json намеренно находятся вне самого release tree.
