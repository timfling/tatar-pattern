# Дополнение backend к релизу — 19.10.2026

## Flat: принятый публичный поднабор существующего контракта

Новые shape/генератор не вводятся: GET `/api/composition-schemes`, POST
`/api/composition-preflight`, POST `/api/generations` с `mode=flat`,
`selections.renderer=composition-v2`, `schemeId`, `registryVersion`,
`elementCodes`, `colorMode=original`; PNG/JPG/recipe/history прежние.

Production отдаёт **24** схемы с reviewStatus=owner_accepted_2026_10_13;
попытка новой генерации/preflight по другим37 →422 SCHEME_NOT_RELEASED.
Локальный TP_ENVIRONMENT=local_project/isolated_test сохраняет все61 для оценки;
frontend в локальном QA фильтрует reviewStatus явно. Preview не является новым результатом.
История/reopen старых работ не ограничиваются новым поднабором.

Дополнительные поля в прежнем catalog response: registeredSchemeCount=61,
acceptedSchemeCount=24, acceptedCoveredElementCount=62,
acceptedCoveredElementCodes (62 кода), elementsWithoutAcceptedScheme (48 кодов).
`coverage` соответствует выданным schemes; totalSchemes — их число.
Capabilities.compositionCatalog дополнен acceptedSchemes и acceptedCoveredElements.
Состав БД **110** мотивов и покрытие **62** мотивов принятыми схемами различаются.
37 revised/polished схем не приняты; приёмка примера не гарантирует любую ручную
комбинацию или культурную экспертизу. `availableElementCodes` и requiredRoles,
centerCandidates, ограничения/диагностику preflight необходимо учитывать в UI.

ID24: f02-directed, f03-directed, f03-wreath, f05-wreath, f07-repeat,
f07-hanging, f08-directed, f10-directed, f10-wreath, f14-directed, f14-panel,
f16-wreath, f17-directed, f17-wreath, f17-panel, f18-hanging, f19-directed,
f19-panel, f20-directed, f20-wreath, f21-panel, f24-wreath, f25-directed, f25-panel.

## Каталог production

Migration011 и scripts.production_catalog отделяют public_flat_catalog от local rights.
Пакет110 готов с269файлами+manifest (flat110/texture110/source49); sources3/artifacts46.
Декларация владельца11.10 учтена, повтор не нужен. Осталось утвердить конкретную
release-decision.pending.json (точные codes/manifestSHA/public scope/кто/когда/evidence).
verifiedBy=NULL/отрисовано/documented_unverified и фактические source rights не повышаются.
Transfer/training этим решением не включаются. Обязательны storage+DB backup до
migrations/import. Apply повторяем, verify read-only; оба проверяют счётчик110 по
реальным файлам/источникам. Команды Beget и rollback — backend/README.md, раздел19.10.
Публичный импорт на сервере ещё не выполнялся; рабочая5432 не затронута.

## AI registry и proof

В backend/app/ai-profiles.json импортированы22строки LoRA: всего28, из них25
с owner-accepted cloud evidence19.10. Исключены f07-repeat:textured,
f25-directed:textured и не участвовавший f08-directed:textured. Статус исключения
дополнительно блокирует admission (`AI_PAIR_NOT_ACCEPTED`), даже при ошибочном release flag.
GPU digests/prompts/settings сравнены с canonical profiles и SHA реальных evidence.
AI_MVP_ENABLED/releaseApproved/externalTransferApproved остаются false.
Это не worker proof и не E2E сайта. Existing HTTPProvider/env/drain договорённости действуют.

Из deployed worker выполняется прежний ai_gpu_probe --owner-run --worker-namespace
с25готовыми jobId из ИИ/gpu-runtime/img2img-http-2026-10-19/worker-probe-command.txt:
GET health→poll→download→health, submit=0. Для ежедневного обновления использовать
те же настоящие retained qualification PNG/UUID при том же boot/deployment и normal200.
До24ч обновить proof; рекомендован операционный запас (например повтор через20ч),
это не созданное расписание и не юридический срок. `python -m scripts.gpu_proof_status`
показывает UTC checkedAt/expiresAt и оставшиеся секунды, не подтверждает live health.
Истечение admission GPU может отключить AI раньше24ч: record/deadline владельца
не равны proof TTL. Нужен выбранный владельцем рабочий admission window.

Same Linux boot+неизменный deployment/state: systemd restart + normalhealth + GET-probe,
генераций0. Новый bootId/unshelve, deploymentDigest или утрата всех настоящих контрольных
PNG: старый proof непригоден; восстановить неизменный state в подходящем boot, иначе
владелец назначает новую qualification допускаемых пар и бюджет. Не переписывать bootId,
checkedAt/record, не продлевать proof health-only, не делать скрытый paid retry.
Если GET-probe не проходит, сохранить evidence, закрыть новые AI submits, оставить
flat/history; knownID poll продолжает восстановление. Timeout не означает cancel GPU.
Обновлённый proof заменяет список пар: всегда передавать все допускаемые UUID,
иначе проверен только переданный поднабор. Назначенного Beget probe/E2E окна ещё нет.

## Правовые механизмы: подготовка и зависимость

Registration имена теперь действительно необязательны, пустые строки допустимы.
Хостинг/profile/AI основания, termsAcceptance и активные версии документов ещё ожидают
согласования через владельца. В доступном handoff07 — v0.2 от11.10, иных утверждений нет.
Юридический acceptance journal/immutable document API/consent withdrawal пока не включены;
существующий register **не готов к публичной публикации** без этой части.
Не считать технический profile PATCH доказательством согласия.

Migration012: durable storage_deletions (pending/done/attempts), provider_deletions
(manual_required/confirmed), erasure_tombstones, access_blocked, privacy_operations.
Trash purge сначала фиксирует очередь+provider reference, удаляет ai_jobs перед generations,
после commit unlink; OSError остаётся в очереди для повторов. Expired sessions очищаются
в hourly/library cleanup. Blocked account не проходит me/login; внутренние block_account/
erase_account_local отзывают sessions и удаляют локальные SQL данные, не обещают удаления
backups/provider/logs. Публичного self-service/утверждённого ручного канала ещё нет.

Worker не начинает submit для удалённой строки; проверяет row lock перед записью
результата, поздний output после hard-delete не скачивает. JobId из позднего submit ack
сохраняет для operator reconciliation. Provider delete/cancel не реализованы GPU контрактом,
manual_required нельзя считать подтверждением уничтожения. KnownID/uncertain/no-retry
поведение и полный SIGTERM930/950/960 остаются прежними.

Tombstone скрывает restored generation из history/file/restore; актуальный erasure ledger
экспортируется отдельно от откатываемого backup. Offline restore обязан применить latest
ledger перед public start; scripts.privacy_maintenance export-ledger/replay-ledger/retry/status
дают исполнимую техническую часть (см. README). Реальный offsite restore на Beget не проверен.
Сроки обращений/legal events/tombstone/backup/logs/provider ещё не утверждены; рекомендации
7/14/30д не внедрены. Существующая корзина7д не срок account deletion.

---

# Контракт API для параллельной работы

Версия 0 от 30.09.2026. Агент backend+БД и агент frontend используют эти названия. Дополнительные поля допустимы; изменение названий согласовать через этот файл.

## Общие правила

- Префикс /api; JSON UTF-8; даты ISO 8601; идентификаторы строками.
- Ошибка: объект error с полями code и message и подходящий HTTP-статус.
- Авторизация: защищенная HttpOnly cookie; запросы клиента с credentials: include. Пароль и токен не хранить в localStorage.
- imageUrl ведет к настоящему PNG/JPG; результат сохраняется после перезагрузки и доступен в том же аккаунте.
- selections содержит существующие ключи frontend: style, composition, parameters, motifs, palette, usage. motifs — массив, остальные — строки.
- POST генерации может вернуть done сразу или queued/processing; клиент поддерживает оба. Показывать процент только при реальном измерении.

## Маршруты

| Метод и путь | Вход | Выход |
| --- | --- | --- |
| POST /api/auth/register | email, password | user: id, email; cookie |
| POST /api/auth/login | email, password | user: id, email; cookie |
| POST /api/auth/logout | — | ok; очистка cookie |
| GET /api/auth/me | cookie | user или 401 |
| GET /api/elements | — | items: code, nameRu, motifClass, imageUrl; только разрешенные и проверенные |
| POST /api/generations | selections, prompt?, projectId? | generation: id, status, progress?, imageUrl?, title, createdAt |
| GET /api/generations/:id | cookie | generation с selections, prompt, rating, projectId |
| GET /api/generations | cookie | items для библиотеки |
| PATCH /api/generations/:id | title?, rating?, projectId? | generation |
| GET /api/projects | cookie | items: id, title, createdAt |
| POST /api/projects | title | project |
| PATCH /api/projects/:id | title | project |
| DELETE /api/projects/:id | — | ok |
| GET /api/health | — | ok |

Backend проверяет владельца генерации/проекта. Удаление проекта не удаляет историю. Экспорт использует imageUrl с корректным Content-Type и именем файла либо документированный отдельный маршрут. Проверяемый путь: вход → параметры → настоящий результат → сохранение → повторное открытие → экспорт.

## Уточнение реализации v0 — 02.10.2026

Все маршруты и поля выше сохранены. Сервер: FastAPI + PostgreSQL, синхронный
алгоритмический генератор на Pillow, без обученной модели и очереди.

- Успешный POST генерации: HTTP 201, `generation.status = "done"`,
  `progress = 100` только после сохранения настоящих PNG и JPG. Пока запрос
  выполняется, клиент показывает неопределенный индикатор. Таймер и выдуманный
  процент запрещены. Отмена HTTP-запроса не гарантирует отмену серверной работы.
- `imageUrl = /api/generations/{id}/file?format=png` — относительный URL API.
  Для отдельного хоста клиент разрешает URL относительно адреса backend.
  Файл требует той же cookie. Экспорт: GET этого маршрута с
  `format=png|jpg&download=true`; Content-Disposition содержит имя файла.
- Generation во всех ответах имеет `id, status, imageUrl, title, createdAt,
  selections, prompt, rating, projectId`, а также `progress, finishedAt,
  algorithmVersion, warnings, recipe, error`. rating: `like`, `dislike` или
  null; projectId: строковый ID либо null. PATCH null снимает оценку/проект;
  пропущенное поле сохраняет прежнее значение. История сохраняется автоматически.
- GET /api/generations: необязательные `projectId`, `limit` (1–100, default 50),
  `offset` (default 0), ответ `items, total`. GET /api/projects: `items`.
- GET /api/elements: `items, total`; дополнительные `motifKey, isFixture`.
  GET /api/elements/{code}/file возвращает проверенный исходный PNG.
  Пустой каталог — items=[]; генерация — 409 `CATALOG_EMPTY`. Если выбранный
  мотив отсутствует — 422 `MOTIFS_UNAVAILABLE` с details.motifs; подмена другим
  мотивом запрещена. Fixture-каталог включается только явным ALLOW_FIXTURES=true,
  результаты имеют предупреждение и recipe.isFixture=true.
- Дополнительно GET /api/capabilities описывает параметры и ограничения.
  Композиции: `medallion`, `border`, `rapport`; палитры: `emerald`, `porcelain`,
  `leather`; мотивы: `tulip`, `bud`, `palmette`, `vine`, `border`, `trefoil`,
  `almond`, `horn` (соответствуют русским motif_class в БД).
- Стиль имеет алгоритмический эффект: heritage — исходная мягкая маска;
  modern — крупные одноцветные силуэты; porcelain-sign — синий контур;
  leather-mosaic — заливка и пунктирный шов; festive — чередование цветов.
  Это условные графические режимы, а не искусствоведческая атрибуция.
- parameters=`default`: стандартная плотность. Дополнительно `sparse` и `dense`
  меняют размер/число повторов. usage задает размер: architecture 1024×1024,
  textile 1024×1024, packaging 1200×900, interior 1200×900, web 800×600.
  Раппорт всегда квадратный для бесшовного повтора, предупреждение сообщает
  переопределение размера. Мотивы используются все, только из выбранного списка.
- Непустой prompt сохраняется, но не управляет изображением: ответ содержит
  warnings с code=`PROMPT_UNSUPPORTED`. Текстовая правка, AI и свободные
  произвольные параметры в v0 не поддерживаются; неизвестные значения — 422.
- Ошибки всегда `{error:{code,message,details?}}`; 401 — нет/истекла сессия,
  403 — недопустимый Origin, 404 — чужой или отсутствующий объект,
  409 — конфликт email/пустой каталог, 422 — неверные данные,
  503 — недоступна БД/файлы. GET /api/health проверяет БД и миграцию 005.
- Cookie `tp_session`: случайный непрозрачный токен, HttpOnly, SameSite=Lax,
  Path=/api, срок 7 дней. В PostgreSQL хранится SHA-256 токена. В production
  обязателен COOKIE_SECURE=true и HTTPS. В dev допустим false на localhost.
  Мутации с Origin принимаются с собственного origin API и настроенных
  CORS_ORIGINS; JSON обязателен.
  Локально Next.js: http://localhost:3000; API: http://localhost:8000.
  Для публикации рекомендуется один origin с reverse proxy /api.

## Дополнение 08.10.2026 — реальный каталог и режимы (совместимо с v0)

Старые рецепты/маршруты сохранены. Отсутствующий `mode` означает `flat`.
Старые восемь motifKey продолжают работать, когда соответствующий класс есть
в разрешенном каталоге. Неприсутствующий класс дает `422 MOTIFS_UNAVAILABLE`.
Классы из manifest сохраняются буквально: например «угол рамки» не тюльпан.
Новые ключи: `class-` + первые 16 hex SHA256 строки класса UTF-8. Получать их
из `/api/elements` или `/api/capabilities`, не создавать на frontend вручную.

### Выбор/изображение flat

`selections` дополнены:

| Поле | Значение |
| --- | --- |
| `elementCodes` | До 16 различных TP-E; при непустом массиве заменяет выбор по классам `motifs` |
| `motifs` | До 16 ключей класса; выбор первого доступного элемента каждого класса для совместимости |
| `scale` | 0.3–2.0, по умолчанию 1.0 |
| `colorMode` | `original` (по умолчанию), `silhouette` |
| `transparentBackground` | boolean, по умолчанию false, относится к PNG |
| `backgroundColor` | `#RRGGBB`, фон JPG и непрозрачного PNG; иначе фон выбранной палитры |

Нужно выбрать хотя бы один класс или элемент. Неизвестные/вспомогательные TP-R
не подменяются. При `original` RGB/alpha исходного PNG сохраняются при
масштабировании и вращении, палитра меняет фон; стили кроме heritage дают
`ORIGINAL_COLORS`. При `silhouette` alpha служит единственной маской:
заливка/контур/шов согласно стилю. Независимой перекраски внутренних цветовых
областей нет. Нельзя обещать ее пользователю без дополнительных масок.
PNG результата — RGBA, JPG — RGB с alpha-композитингом на сплошном фоне.
Rapport строится на периодической плитке с переносом пересечений через края.
Рецепт содержит конкретные TP-E, SHA, предмет/кадр, версию алгоритма,
colorMode, фон, layout, selections; восстановление истории не регенерирует файл.

`GET /api/elements` добавляет `sha256`, `artifactCode`, `sourceFrame`,
`motifIdentity`, `provenanceStatus`, `qualityAcceptance`,
`externalTransferAllowed`. total считает элементы, а не flat+texture.
`capabilities.realUniqueElements` — число реальных исходных областей с файлами;
fixtures и TP-R исключены. SQL-аудит дополнительно сворачивает одинаковые SHA.

### Качество, происхождение и права

JSON catalog_import version=1 сохранен со всеми прежними проверками.
version=2 разделяет массовую приемку качества владельцем от 08.10.2026
(`qualityAcceptance`, SHA каждой версии), traceability и разрешение на
**локальную** работу конструктора (`localUseDecision`).
Экспертное заключение отсутствует: `verifiedBy=null`, status=отрисовано,
provenanceStatus=documented_unverified, artifact.reviewStatus=авто.
legalBasis остается NULL; сообщение владельца об устном некоммерческом согласии
музеев хранится как rightsEvidence с ограничениями, не как доказанное право.
usage_scope=контекст, rights=неясно; поля внешней передачи/обучения false.
Текущий импорт не разрешает публичное/коммерческое распространение материалов.
Новая ветвь допускается API только при явном TP_ENVIRONMENT=local_project или
isolated_test. Перед публичным запуском требуется отдельное подтверждение
конкретных прав и соответствующий импорт/миграция, не переключение флага.

### AI / задания

POST `/api/generations`: `mode: "flat" | "ai"`, `seed` 0–2147483647.
Flat остается синхронным. AI после настройки возвращает сохраненное queued
задание; опрашивать существующий `GET /api/generations/{id}`. История/ownership,
PATCH, PNG/JPG доступны теми же маршрутами. Ответ дополнен `mode`, `seed`,
`modelVersion`; `algorithmVersion` сохранен как совместимый alias.
Для queued/processing AI `progress=null`; проценты не выдумываются.
Рецепт хранит provider/modelVersion/seed и вход задачи без email/сессии.

Сейчас `modes.ai.available=false`, `AI_PROVIDER_UNCONFIGURED` (503): фактической
спецификации и доступа DSLab еще нет. Не возникает flat-результата вместо AI.
При неподтвержденной передаче материалов — `MATERIAL_TRANSFER_NOT_AUTHORIZED`
(422) с elementCodes. Ключ никогда не приходит в браузер или рецепт.

Очередь в PostgreSQL `ai_jobs`, отдельный `python -m scripts.ai_worker`:
один воркер/облачное задание (advisory lock), максимум 20 незавершенных задач,
deadline 15 минут от постановки (включая очередь), submit timeout 30 секунд,
poll 15 секунд/каждые 5 секунд, download 30 секунд/до 20 MiB,
до 3 ошибок poll/download с задержкой 10 секунд. Адаптер обязан обеспечить
эти сетевые timeout и безопасное ограниченное скачивание. После рестарта
сохраненный cloud ID продолжается; неизвестный исход submit завершается
AI_SUBMISSION_UNCERTAIN без автоматической повторной GPU-оплаты.
Timeout/ошибка/закрытие UI не означают отмену GPU. Endpoint отмены не заявлен.
Точный DSLab API, допустимый сценарий/модель, URL/ключ, правила хранения,
идемпотентность и материалы предоставляет спецификация агента ИИ/владелец.
Настройки лимитов пересмотреть после измерений настоящего облака.
Тестовый адаптер в tests — синтетический, не результат DSLab.

## Дополнение 09.10.2026 — профиль, формат и корзина

Миграция 010 добавляет users.profile JSONB и generations.deleted_at. Существующие строки и API login сохранены. Register дополнительно принимает firstName/lastName (до 80 символов), occupation (пусто/designer/artist/student/researcher/other), avatar (JPEG data URL до 12000 символов). Старые клиенты могут не передавать профиль; новая форма требует имя и фамилию. GET me и login/register возвращают профиль. PATCH /api/auth/profile заменяет профиль текущего пользователя без изменения email/пароля. Файл аватара уменьшается frontend до 96×96; сервер ограничивает тип/размер строки и JSON запроса.

selections.outputSize: null (прежний размер от usage) либо [1024,1024], [900,1200], [800,1200], [720,1280] и обратные ориентации. Другие размеры дают 422. capabilities.outputSizes содержит базовые вертикальные форматы; выбор ориентации меняет порядок сторон. Прямоугольный раппорт при явном outputSize имеет периодическую квадратную под-плитку, делящую обе стороны; прежние рецепты без outputSize сохраняют квадратный раппорт.

DELETE /api/generations/:id переносит завершенную работу в корзину (идемпотентно, незавершенное задание — 409). GET /api/generations исключает удалённые; trash=true возвращает корзину с deletedAt. POST /api/generations/:id/restore восстанавливает до семи дней. Ownership проверяется во всех маршрутах. Удалённые старше семи дней записи и PNG/JPG удаляются при обращении к библиотеке и фоновым заданием при старте API/каждый час. Просроченные записи недоступны даже до физической очистки. API должен работать для фонового удаления; после остановки очистка продолжится на старте. Отдельное удаление аккаунта/изменение почты/пароля не реализовано.

## Дополнение 12.10.2026 — композиционный пилот и сохранённые описания

### Версии и переход

Default остаётся `renderer=legacy`. Композиционный пилот **не принят владельцем**;
он включается явным `selections.renderer="composition-v1"`. Реализованы только
три тройки, перечисленные в `capabilities.renderers["composition-v1"].pilotRecipes`:

| composition | selected elementCodes | Роли |
| --- | --- | --- |
| medallion | TP-E-050, TP-E-051, TP-E-052 | небольшой центр / направленные пальметты / одна нижняя парная опора |
| border | TP-E-061, TP-E-063, TP-E-066 | главный цветок / горизонтальная связка / малый петлевой цветок |
| rapport | TP-E-090, TP-E-091, TP-E-092 | дискретная рамочная полоса / вспомогательный ромб / главный ромб |

Порядок выбора не назначает роли: они закреплены по коду в recipe.roles.
Выбранные и реально использованные элементы различаются явно:
`selectedElementCodes`, `selectedMotifKeys`, `usedElementCodes`, `elements` с SHA.
При выборе по motifKey сохраняются ключи запроса и фактически разрешённые TP-E.
Другой ручной набор — 422 `COMPOSITION_SELECTION_UNSUPPORTED` с исходным
selectedElementCodes, diagnostics по usage/state/reason, alternatives и
requiresExplicitSelection=true. Alternatives являются предложением для нового
явного выбора; сервер не применяет их автоматически. Это ограничение объёма
пилота, а не универсальный культурный запрет на остальные мотивы.

Пилот поддерживает original RGBA. Silhouette — 422 PILOT_REQUIRES_ORIGINAL.
scale/parameters участвуют в размерах, числе повторов и чистых интервалах;
рекомендованный размер деталей имеет приоритет. Слишком крупный масштаб,
недостаточная ширина/модуль или потеря просветов — объясняющий 422, без
скрытого удаления элементов. Unknown угол сохраняет PNG-подачу; неизвестное
основание не подставляется. Отражения и реконструкции не применяются.

Версии: `algorithmic-pillow-v0.3` (исправление legacy gcd) и
`composition-pillow/1.0.0-pilot`, recipe `tp-composition-recipe/1.0.0`,
metadata `tp-composition-review/1.0.0`. Рецепт фиксирует SHA пакета ревизии,
rendererSourceSha256, pillowVersion, seed, selections, роли, размеры,
матрицы crop→sprite→output, основания и фактические размещения.

### Модуль и образец раппорта

| Поле запроса | Семантика |
| --- | --- |
| rapportOutput | `module` (default) или `sample`; действует в composition-v1/rapport |
| moduleSize | null = размер подбирается из плотности/деталей; либо [w,h], стороны 256–2048 px; слишком маленький модуль отклоняется |
| outputSize | В новом rapport задаёт **размер образца**. При module экспорт имеет фактический moduleSize, а MODULE_EXPORT_SIZE объясняет отличие |

`generation.outputKind`:

- `composition_image`: венок/бордюр, без обещания бесшовности;
- `repeat_module`: бесшовный модуль (пилот) либо прежний полный бесшовный
  экспорт legacy, заполненный периодическими прямоугольными модулями;
- `pattern_sample`: прямоугольный образец. `seamless=true` только если обе
  стороны целочисленно кратны соответствующим periodPx;
- `ai_image`: AI, seamless=null до отдельной проверки;
- `legacy_image`: старый рецепт без нового поля; seamless=null, не повышать
  его статус автоматически при открытии истории.

`repeat.periodPx=[w,h]` задаёт независимый период по каждой оси.
У пилота repeat дополнительно содержит moduleSha256; generation.moduleUrl
ведёт к защищённому `GET /api/generations/:id/file?artifact=module&format=png`.
`download=true` работает и для module. Модуль JPG не заявлен (404);
обычные output PNG/JPG сохраняют прежние маршруты и ownership.
PNG RGBA; JPG имеет сплошной выбранный фон. Для прозрачного PNG контраст на
будущей поверхности unknown, независимо от диагностики фонового JPG.

Пилотный модуль собирает **дискретные** фигуры с wrap. Он не является
восстановленным историческим периодом и не соединяет неизвестные концы TP-E-090.
Некратный образец получает SAMPLE_NOT_SEAMLESS. Frontend должен показывать
фактические size/moduleSize и отдельное действие «Скачать модуль».

**Совместимость legacy:** обещание бесшовного полного экспорта сохранено.
При явных прямоугольных outputSize периоды теперь выбираются независимо по
осям, без gcd(width,height): 900×1200 и 720×1280 не схлопывают мотивы к min20.
Без явного outputSize прежний квадратный экспорт rapport сохраняется.
`layout.moduleSize` / `repeat.periodPx` — новая пара сторон.
Исторический `layout.tileSize` остаётся числом для квадратного модуля и
становится null для прямоугольного; потребители геометрии должны читать пару
сторон. Старые сохранённые рецепты и файлы не переписываются. Изменение новых
legacy pixels закреплено версией v0.3; схемы венка/бордюра legacy сохранены.

### Описание и его основания

В generation (POST/GET/list/PATCH) добавлены:

- `description`: короткий русский текст;
- `descriptionDetails`: text, basis, claimType, templateVersion,
  schemaVersion, facts, evidence, culturalNote;
- `culturalNote`: отдельный nullable объект text/claimType/evidence/appliesTo;
- `compatibility`: status, geometry, aesthetic, cultural, metadataVersion,
  snapshotSha256, reasons и сведения по каждому использованному элементу;
- `outputKind`, `seamless`, `repeat`, `moduleUrl`.

`descriptionDetails` сохраняется внутри **recipe.description JSONB** в
существующем generations.params: миграция не требуется. Версия шаблонов
`tp-description/1.0.0`, схема `tp-description-schema/1.0.0`.
Новая flat работа: basis=saved_recipe, claimType=render_recipe_fact.
Facts описывают записанное размещение/цветовое исполнение, а не экспертное
заключение о красоте. Повторное открытие возвращает сохранённый текст,
факты и evidence, даже после появления новых шаблонов.
Старая работа без description: совместимый runtime fallback basis=legacy_recipe,
culturalNote=null; DB params массово не изменяются. Fallback не фиксируется
как исторически сохранённая версия нового текста и не добавляет культурную справку.

Reasons имеют code, severity (`prohibition` / `recommendation` / `unknown`),
scope, evidence, message. `geometry=checked_for_saved_layout` означает только
сохранённые размеры/поля/маски; aesthetic=designer_proposal,
cultural=unknown. Нет поля «семантически проверено». Метаданные по code+SHA
доступны также в `/api/elements.items[].compositionMetadata`.

Культурная справка P3 ограничена документированным общим принципом иерархии
полос и ведущего/вспомогательного мотива (C03/C04); включает полные записи
источников, locator, автора, URL, basis и предел применимости. Остальные
пилоты culturalNote=null. Цвета и имена классов не порождают символику.

### AI requested / observed / verified

AI по-прежнему unavailable/AI_PROVIDER_UNCONFIGURED; этот этап не подключает
провайдера или GPU. Для будущего/тестового задания описание сохраняется с
basis=requested_only, claimType=request, facts.requested (selections/входные
элементы), facts.observed=null, facts.verified=null. Текст начинается
«Для генерации выбраны…» и прямо говорит, что итог пока не проверен.
Успешный provider download сам по себе не подтверждает мотивы, цвета,
симметрию, число частей или бесшовность. Старые AI работы без описания получают
такой же requested-only fallback.

Будущее подтверждённое наблюдение должно ссылаться на **SHA результата**,
method/version, наблюдаемый факт, evidence и конкретный verified scope.
Без отдельного механизма visual/geometry проверки nullable поля остаются null.
Такая проверка пока не реализована; provider prompt/ответ/seed не являются
visual evidence. Описания не повышают происхождение, rights или verifiedBy.

### Доработка 13.10.2026 — бордюр после визуальной оценки

Владелец принял раппорты и счёл венки приемлемыми при возможности настройки
заполнения; P2 потребовал исправить. Оценка конкретных PNG/SHA закреплена в
backend/docs/OWNER-VISUAL-REVIEW-2026-10-12.json. Она не является культурной
экспертизой. Capabilities.renderers["composition-v1"].status=owner_reviewed_partial,
visualReview различает medallion/rapport/border. Default остаётся legacy.

Renderer теперь **composition-pillow/1.1.0-pilot**. P1/P3 сохраняют прежние
пиксели при тех же запросах; существующие файлы/recipe/описания не переписаны.
Replay поддерживает сохранённые placements v1.0.0 и v1.1.0.
Description templates новых работ — **tp-description/1.1.0**, старая сохранённая
версия описаний продолжает возвращаться из recipe без изменений.

P2 сохраняет ту же явно выбранную тройку061/063/066, original и отсутствие
отражений. Layout теперь имеет rows=3 и registers (role/y/count): крупные
цветы сверху, завитковые блоки посередине, более частый ряд малых цветов снизу.
Все ярусы центрированы по ширине, шаг внутри яруса равномерный; малые акценты
больше не подвешены вне общего ритма. parameters=sparse/default/dense вместе
пересчитывают размер и интервалы; на1200×900/scale1 получаются4/5/6 главных
повторов и7/9/11 малых. Другие размеры пересчитываются по габаритам и px-floor.
Недостаточная высота —422 BORDER_TOO_TALL, ширина — BORDER_TOO_NARROW;
скрытого удаления элементов нет.

modernAdditions.kind=horizontal_border_rules хранит координаты/цвет/толщину
двух тонких линий обрамления. Это современная добавка, не восстановленный
музейный элемент или стебель. Непрерывные стыки и основание с unknown
по-прежнему не выдумываются.

Для P2 culturalNote теперь является **справкой об одном исходном предмете**:
claimType=single_object_visual_observation, evidence OBS-TP-E-061/063/066 и
CAT-NM-9585; appliesTo=source_object_hierarchy_only_not_general_cultural_rule.
Она подтверждает наблюдаемые ярусы DSC9585, а не культурную закономерность
любого бордюра. compatibility.cultural остаётся unknown;
historicalLayout=not_verified, symbolicMeaning=unknown, contextEvidence
перечисляет источники. Поэтому UI показывает «Контекст источника», а не
«Семантически проверено». Legacy v0.2 также не имеет подтверждения исторической
семантики: он не применял роли и автоматически поворачивал средний ряд.

Заполнение P1 уже настраивается существующими parameters и scale:
проверенный пример dense/scale1.2 имеет11 акцентов и центр244px вместо192px
у исходного default/scale1. Новые поля запроса для этого не нужны.

### Дополнение 13.10.2026 — смешение визуальных весов

Владелец оценил исправленный трёхъярусный P2 как удовлетворительный и запросил
более сложное смешение лёгких/средних/тяжёлых элементов. Это отзыв о галерее,
не индивидуальная экспертная проверка всех карточек.

Новый необязательный `selections.borderLayout`:

- `registers` — default, сохранённая трёхъярусная схема;
- `interwoven` — крупные цветы/средние завитковые блоки чередуются по высоте,
  малые цветы образуют локальные группы. Только composition-v1/border;
  другой renderer/composition с interwoven даёт422 BORDER_LAYOUT_REQUIRES_COMPOSITION.

Capabilities сообщает borderLayouts и borderVisualReview по варианту;
visualReview.border остаётся строкой для совместимости.
Renderer **composition-pillow/1.2.0-pilot**, новые description templates
**tp-description/1.2.0**; предыдущие версии recipe поддерживает replay,
сохранённые описания и удовлетворительный registers не переписаны.

layout.variant=interwoven, rows/registers=null, visualWeights задаёт относительные
роли heavy/medium/light. Это дизайнерская оценка размера/заполненности/деталей,
а не новая культурная классификация PNG. Исходная тройка061/063/066 сохранена;
невидимых дополнительных мотивов, отражений или реконструкций нет.
ModernAddition wave_guide фиксирует точки/цвет/толщину и purpose=
rhythm_guide_not_attachment. Направляющая современная, физический стебель
или неизвестный узел крепления не восстановлены. Справка источника явно
ограничена мотивами одного предмета и не подтверждает interwoven расстановку.

scale/parameters действуют вместе с px-floor. Число повторов зависит от доступной
ширины и габаритов; dense не обязан увеличивать count в каждом формате.
Описание говорит о просветах и сохранённом волнообразном размещении по recipe.
Новый interwoven пока awaiting_owner_visual_review; registers сохранён отдельным
вариантом, рабочий default не переключён.

### Закрытие пилота 13.10.2026

Владелец принял interwoven и завершил текущий этап при оговорённом основании:
современная декоративная композиция из мотивов каталогизированного татарского
костюма, с сохранением форм/направлений/внутренних полей и явной маркировкой
дизайнерского расположения/направляющей. Это не экспертная верификация пары,
исторической реконструкции или символики. compatibility.cultural=unknown и
evidence/claimType не повышаются из-за визуальной приёмки.

Capabilities composition-v1.status=owner_accepted_pilot,
visualReview.border=accepted_contemporary_design,
borderVisualReview.interwoven=owner_accepted. Схема принята; явно показанный
плотный пример связан с PNG+recipe SHA в owner-review JSON. Остальным карточкам
не приписывается отдельная индивидуальная проверка владельцем.

Этап1 закрыт как принятый пилот трёх схем на9 TP-E. Этап2 закрыт в backend:
описания/версии/facts/evidence/fallback/requested-only AI и контракт готовы.
Frontend подключение, расширение на новые наборы и переключение рабочего default
являются последующими задачами. Default всё ещё legacy, рабочие данные не изменены.

## Расширенный генератор — 13.10.2026

`composition-v2` — отдельный явный renderer, `composition-pillow/2.0.0`, recipe
`tp-composition-recipe/2.0.0`. Legacy default и принятый `composition-v1`
сохранены. Новые схемы — современные дизайнерские предложения, без повышения
культурной атрибуции или прав каталога.

### Каталог схем

`GET /api/composition-schemes` возвращает `schemaVersion`, `registryVersion`,
`sha256`, `metadataVersion`, `totalElements`, `totalFamilies`, `totalSchemes`,
`roleLabelsRu`, `families`, `schemes`, `coverage`, `availableElementCodes`.

Семейство: `id`, `titleRu`, `elementCodes`, `subgroups[{artifactCode,elementCodes}]`,
`basis`, `mixingPolicy`, `evidence`. Схема: `id`, `familyId`, `composition`,
`layout`, `useScope`, `titleRu`, `descriptionRu`, `allowedElementCodes`,
`defaultElementCodes`, `minimumSelected`, `maximumSelected`, `requiredRoles`,
`centerCandidates`, `roleOptions`, `constraints`, `previewUrl`, `previewIsExample`,
`reviewStatus`, `availableElementCodes`, `available`.

`available` означает доступность всех предложенных элементов в текущем каталоге.
`allowedElementCodes` — граница поддержки схемы; наличие элемента в списке
не гарантирует размещение любого сочетания при любом масштабе/формате.
Предложенный набор применяется только по явному действию пользователя.
`coverage` сопоставляет каждому TP-E список схем. Тип `hanging_panel` использует
существующий `composition=border`; `framed_panel` — `composition=medallion`.

`GET /api/composition-schemes/{id}/preview` возвращает настоящий уменьшенный PNG
генератора с предложенным набором. Это пример схемы, не результат текущего выбора.
Пример доступен только когда соответствующий набор доступен в текущем каталоге.
Запрос к неизвестной/недоступной схеме →404; отсутствие подготовленного файла →503.

### Выбор и preflight

В `selections` добавлены:

- `renderer: "composition-v2"`;
- `schemeId`: устойчивый ID из каталога, обязательный для v2;
- `registryVersion`: опциональная защита от устаревшего каталога;
- `primaryElementCode`: опциональный главный мотив из явно выбранного набора.

`POST /api/composition-preflight` принимает ту же структуру `Generate`, что
`POST /api/generations`: `mode=flat`, `seed`, `selections`; требует сессию.
Он строит ту же геометрию без записи generation и файлов, возвращая
`schemaVersion=tp-preflight/2.0.0`, `supported=true`, `engineVersion`,
`registryVersion`, `registrySha256`, `schemeId`, `selectedElementCodes`,
`usedElementCodes`, `assignments[{code,role,recommendedMinLongSidePx}]`,
`primaryElementCode`, `layout`, `size`, `reasons`, `factsBasis`.
Preflight не является художественной или культурной экспертизой; генерация
повторно проверяет план. Долгий запрос занимает обычный слот renderer; занятость →503.

Неподдерживаемый выбор →422 `SCHEME_ELEMENTS_UNSUPPORTED`: `selectedElementCodes`,
`diagnostics`, `alternatives` (код→ID схем), `requiresExplicitSelection=true`.
Набор не заменяется и не урезается. Другие ошибки: `SCHEME_REQUIRED`,
`SCHEME_COMPOSITION_MISMATCH`, `CENTER_ROLE_REQUIRED`, `PRIMARY_NOT_SELECTED`,
`SCHEME_REQUIRES_ORIGINAL`, `MODULE_TOO_SMALL` (`minimumSize`), `MODULE_LIMIT`,
`BORDER_TOO_NARROW`, `BORDER_TOO_TALL`, `COMPOSITION_TOO_LARGE`,
`LAYOUT_CLEARANCE_FAILED`. Несовпадение версии →409 `SCHEME_REGISTRY_CHANGED`.
Поля scheme/registry/primary у других renderer →422 `SCHEME_FIELDS_REQUIRE_V2`.
`borderLayout=interwoven` относится только к пилоту v1; v2 выбирает layout через
schemeId. `moduleSize`/`rapportOutput` относятся только к rapport.

### Сохранённый результат

Результат сохраняет `schemeId`, `familyId`, `schemeDefinition`, `registryVersion`,
`registrySha256`, назначенные роли/главный код, все placements и матрицы, исходные
SHA и диагностику. Description `tp-description/2.0.0` описывает фактический layout;
старые сохранённые тексты не переписываются. Reopen/история/PNG/JPG/moduleUrl
используют прежние маршруты и правила владения. Replay v2 использует placements,
не актуальный реестр. Раппорт — дискретный периодический модуль, без заявления
об историческом соединении краевых узлов. Некратный sample не бесшовный.

### Визуальная доработка по оценке владельца —13.10.2026

Renderer v2 теперь `composition-pillow/2.1.0`, registry `tp-schemes/2.1.0`,
description `tp-description/2.1.0`. Recipe schema и API shape остаются2.0.0.
Replay поддерживает сохранённые2.0.0 и2.1.0 без пересчёта схемы.

У24 схем `reviewStatus=owner_accepted_2026_10_13`; их исходные PNG и runtime
preview PNG сохранены по SHA. У21 переработанной схемы
`reviewStatus=revised_awaiting_owner_review`, у16 доработанных —
`polished_awaiting_owner_review`. Это художественная оценка предложенных примеров,
не культурная экспертиза и не автоматическое принятие любой ручной комбинации.

У отмеченных37 схем дополнительно есть `design` (профиль размещения),
`applicationRu` (предложение применения, без гарантии производства),
`previewKind`, `previewDescriptionRu`. `previewKind=repeat_field` означает
уменьшенное окно1200×900, собранное повторением настоящего модуля; края этого
обзора могут быть некратны модулю. `visible_band` — рабочая область полосы без
больших пустых полей; полные поля/слабая alpha-окантовка сохраняются в экспорте.
Это пример, не текущий результат/модуль для скачивания. В `provenance.json`
сохранён `previewTransform` с размером окна, периодом или crop и SHA.

Профиль явно задаёт предложенный набор, относительные размеры/главный мотив и
разведение полос/акцентов. В request по-прежнему передаются elementCodes,
schemeId, registryVersion и optional primaryElementCode. Ручной выбор не
заменяется предложенным набором. Геометрия опирается на alpha>=16 рабочие
границы, сохраняет полные исходные sprite/alpha и проверяет заметные маски;
слабые ореолы могут пересекаться. `layout.designProfile/bands/offsetRepeat`
описывают фактический новый ритм; `designSourceSha256` закрепляет код планировщика.

## AI MVP: фиксированные основы и оформление — 18.10.2026

**Этот раздел заменяет прежний AI-ввод через selections/prompt для НОВЫХ задач.**
Старые сохранённые flat/AI записи, их prompt/selections/recipe и файлы читаются как
раньше. Flat Generate shape и selections.style остаются прежними. D/D1 отменены.
Ни каталог, ни preview, ни локальный synthetic provider не подтверждают GPU readiness.

### Каталог

`GET /api/ai-bases` без сессии:

```json
{
  "schemaVersion": "tp-ai-bases/1.0.0",
  "catalogVersion": "2026-10-18.1",
  "palettePolicy": "source",
  "freePrompt": false,
  "outputSize": [1024, 1024],
  "available": false,
  "bases": [{
    "id": "f10-wreath",
    "schemeId": "f10-wreath",
    "titleRu": "Пестречинский медальон",
    "sha256": "5032b6b6ad6365873c147b72b2642326b261db2888c50be2f08014814699d25b",
    "previewUrl": "/api/ai-bases/f10-wreath/preview",
    "palette": {"policy":"source", "background":"#f3ebdb", "swatches":[]},
    "styles": [{
      "id":"graphic", "labelRu":"Графический стиль",
      "profileVersion":"2026-10-18.local-v1",
      "qualityStatus":"local_candidate", "available":false,
      "unavailableReasons":["AI_DISABLED","AI_PROVIDER_UNVERIFIED","AI_PROFILE_NOT_RELEASED","MATERIAL_TRANSFER_NOT_AUTHORIZED"]
    }]
  }]
}
```

Пример сокращён: каждый base также содержит familyId/familyTitleRu, elementCodes,
sources (предмет/кадр/SHA), roles, modernAdditions, recipeSha256, ownerStatus,
acceptanceScope, originalSha256, aiQualityStatus, aiSeamless=false, size/mode.
Каждый base имеет обе записи styles: graphic и textured; для ещё не проверенной
связки profileVersion=null и qualityStatus=pending_artistic_tests. UI может показать
каталог, но генерировать можно только при styles[].available=true. При недоступности
показать причину, а не flat fallback. Фактурный f08 помечен local_candidate_weak_texture.

`GET /api/ai-bases/{baseId}/preview` отдаёт зарегистрированный RGB PNG, проверяет SHA.
Неизвестный ID →422 AI_BASE_UNKNOWN; повреждённый/отсутствующий файл →503.
Preview — исходная композиционная основа, не образец успешной AI-генерации.

Источники каталога — app/ai-assets/index.json (15 основ: прежние3 + новые12),
PNG и `.recipe.json` рядом. Разрешённый квадратный экспорт: пропорциональное
вписывание и padding исходным фоном, без crop/recolor/перестановки. Реальный фон
может быть тёмным. Swatches — описательные образцы, не параметры перекраски.
Раппорт проверяется как декоративный PNG, AI-бесшовность не обещается.

### Создание AI-задачи

`POST /api/generations`, JSON, сессия/ownership/Origin как прежде:

```json
{
  "mode": "ai",
  "ai": {
    "baseId": "f10-wreath",
    "ornamentStyle": "graphic",
    "profileVersion": "2026-10-18.local-v1"
  },
  "seed": 20261008,
  "requestId": "6dcfe0b1-005f-46c5-99da-df745eb1817a"
}
```

projectId опционален, принадлежит пользователю; seed integer0–2147483647.
requestId UUID обязателен: один ID на одну попытку пользователя. Повтор того же
requestId с тем же ai/seed/projectId возвращает ту же запись (201), без второго
submit. Изменённый запрос с тем же ID →409 AI_IDEMPOTENCY_CONFLICT. Новый вариант
или явный повтор после ошибки требует нового requestId; seed передаётся явно UI,
сервер не увеличивает его автоматически. Идемпотентность сохраняется в PostgreSQL
через params.clientRequestId + requestFingerprint и transaction advisory lock.
Новая миграция для этого этапа не требуется.

ai.ornamentStyle: **graphic / textured**, подписи «Графический стиль» /
«Фактурный стиль». Это не selections.style, не технические mode или renderer.
Для AI selections целиком запрещён →422 AI_SELECTIONS_UNSUPPORTED: палитра,
масштаб, плотность, ручные мотивы, произвольный фон/формат не применяются к фиксированной
основе. Для flat ai/requestId запрещены; selections обязателен.

prompt можно опустить или передать пустую/пробельную строку для совместимости.
Непустой prompt →422 **AI_PROMPT_UNSUPPORTED** до постановки задачи, не игнорируется.
Неизвестные поля (включая strength/steps, arbitrary recipe, prompt внутри ai,
URL/пути/модель) →422 VALIDATION_ERROR. Свободный prompt из старой истории остаётся
читаемым, но не может повторно отправляться в новый AI endpoint.

Ошибки до GPU: неизвестная основа422 AI_BASE_UNKNOWN; отсутствующая проверенная
связка422 AI_COMBINATION_UNAVAILABLE; устаревшая profileVersion409 AI_PROFILE_CHANGED
с details.expected; отсутствующая/изменённая PNG/recipe503 AI_ASSET_UNAVAILABLE /
AI_ASSET_CHANGED; профиль с другим SHA503 AI_PROFILE_ASSET_MISMATCH; недоступность
релиза503 AI_UNAVAILABLE с details.reasons; переполненная очередь503 AI_QUEUE_FULL.
Сочетание должно иметь releaseApproved, разрешение передачи материала, включённый
AI_MVP_ENABLED и verified provider. В текущем checkout все связки unavailable.

### Серверные профили и сохранение

app/ai-profiles.json — серверные версии пары baseId×ornamentStyle, связанные с точным
baseSha256. Клиент присылает только версию из каталога, не параметры рецепта.
Локальные кандидаты из плана чата5:

| Основа | graphic | textured |
|---|---|---|
|f10-wreath|0.55 /30steps|0.76 /30steps|
|f14-directed|0.55 /30steps|0.70 /100steps|
|f08-directed|0.55 /30steps|0.70 /100steps, слабая фактура|

Для12новых основ профиль намеренно отсутствует до художественных тестов/решения чата5.
Не назначать всем автоматически0.76/30 и не считать локальный Draw Things рецепт
проверенным облачным рецептом. base/profile JSON не редактируются браузером.

Generation/history/reopen возвращают прежний объект generation, дополнительно
`ai:{baseId,ornamentStyle,profileVersion}` и `requestId` (nullable у старых работ).
У новых AI selections=null, prompt="", mode=ai, seed сохранён; recipe содержит
schemaVersion=tp-ai-composition-recipe/1.0, immutable base snapshot с source/output SHA,
profile snapshot, provider/modelVersion, input, description и после успеха outputSha256.
Повторное открытие использует сохранённые PNG/recipe, не текущий профиль и не inference.
Изменение каталога не переписывает историю. imageUrl появляется только для done и
существующего файла; moduleUrl=null, seamless=false. Гарантия исходной палитры означает
неизменный input и отсутствие свободной перекраски; diffusion может сдвинуть оттенки.
Описание сохраняет basis=requested_only, observed/verified=null: технически валидный
PNG не доказывает сохранение числа мотивов, культурную корректность или качество.

### Provider/worker — HTTP adapter, 18.10.2026

Внутренний payload **tp-ai-task/1.0** сохраняется: baseId, inputArtifact.sha256/size/mode,
ornamentStyle, profileVersion, server profile snapshot, seed, palette, output PNG1024².
HTTPProvider переводит его в **tp-gpu-img2img/1.0**: ровно9полей contractVersion,
workflowVersion, modelVersion, catalogVersion, baseId, baseSha256, ornamentStyle,
profileVersion, seed. Prompt/settings/paths/URL/profile JSON не передаются.
Точный транспорт, версии, error mapping, proof и handoff Beget: актуальный верх
[GPU-INTEGRATION.md](../ИИ/GPU-INTEGRATION.md). GPU-код не менялся; реальный HTTP ещё не проверен.

Env: AI_GPU_BASE_URL=http://gpu-tunnel:18765; ровно один AI_GPU_TOKEN либо
AI_GPU_TOKEN_FILE=/run/secrets/gpu_bearer; GPU_EXPECTED_WORKFLOW_VERSION=
tp-sdxl-composition-img2img/1.0.0; GPU_EXPECTED_MODEL_VERSION=
378c08ff157660a3399573e1cd5918ad8f3aec344646c5336b027d63fe50ca42;
AI_GPU_HTTP_PROOF_FILE=/data/storage/ai-gpu-worker-proof.json. DATABASE_URL/STORAGE_ROOT
общие API/worker; одинаковый app/assets/profiles. AI_MVP_ENABLED=false по умолчанию.
Без URL configured_provider()=None; неполная/противоречивая конфигурация отвергается.
Без real worker proof ready=false. Local_project/isolated_test всегдаready=false.

Readiness требует health200 normal/non-draining, точных contract/workflow/model/catalog,
qualified пары с exact SHA/profileDigest/promptVersion и owner-run proof текущих origin/
deploymentDigest/bootId (≤24ч). Команда python -m scripts.ai_gpu_probe --owner-run
--worker-namespace --job-id <готовый UUID> выполняется только позже в разрешённом окне
из worker namespace, без submit/inference; проверяет poll/download/SHA/PNG. Для нескольких
пар --job-id повторяется. API читает общий proof, сам не создаёт. Capability дополнительно
требует releaseApproved, externalTransferApproved и AI_MVP_ENABLED. В этом checkout
эти разрешения не включены, реального proof нет; все пары остаются unavailable.

Worker: python -m scripts.ai_worker. Один процесс через advisory lock, очередь≤20,
deadline900с от enqueue. Сохраняет submitting до HTTP и известный provider_job_id до poll.
GPU Idempotency-Key = generation.id UUID (стабилен, уникален между владельцами);
frontend requestId остаётся owner-scoped PostgreSQL ключом. Неизвестный submit/restart
без ID → AI_SUBMISSION_UNCERTAIN без retry; сохранённый ID продолжает poll независимо
от readiness. Даже jobId из acknowledgement с неверными версиями сохраняется для проверки.
Явный GPU отказ до принятия получает согласованный AI_* код. Старые queued schema не
конвертируются молча; история сохранённых результатов читается как прежде.

HTTP: без redirects/ambient proxy; health5с, submit30с, poll15с/interval5с,
download30с, JSON≤256KiB, PNG≤20MiB, ошибки poll/download≤3. DNS/TCP/TLS/headers/body
ограничены абсолютным сетевым бюджетом; watchdog закрывает зависшее I/O.
Только фиксированный route с проверенным UUID; никакого произвольного result URL.
Poll сверяет pinned workflow metadata и task seed/пару; download требует descriptor
bytes/MIME/SHA и PNG RGB1024²/один кадр/verify+decode. PNG сохраняется побайтно через
temporary→replace, JPG отдельно. recipe: gpuMetadata (allowlist), providerOutputSha256,
outputSha256 PNG/JPG, outputSize. requested_only не повышается до verified.
Истёкший result → ошибка, без нового submit. Нет flat fallback/автозапуска облака.

SIGTERM/SIGINT закрывают admission, queued остаются в БД. Deadline930с считается
от первого сигнала, timestamp фиксируется в signal handler; повторные сигналы не
сбрасывают его. Текущий вызов/запись/commit входят в общий срок. Следующие HTTP-фазы
получают динамический остаток deadline даже при сигнале внутри текущего poll.
После930с сохраняются workerShutdown.state=poll_resume_required/gpuCancelled=false
и known jobId с commit перед acknowledgement. На firstSignal+950с действует аварийный
ITIMER_REAL/SIGALRM → os._exit(75), включая container PID1; без cleanup/commit/success
acknowledgement, активен до выхода процесса/закрытия DB. Grace960с оставляет10с.
Это полный приложенческий предел SIGTERM→exit, а не гарантия успешной записи при
зависшем storage/DB. Код75/crash/nonzero exit требует сверить persistent состояние
и оставить tunnel/DB доступными. Known ID не приводит к новому submit; uncertain
submit не повторяется. DB connect/statement/lock timeout5с дополнительно сохранены.

Backend подтвердил Beget env (включая AI_GPU_HTTP_PROOF_FILE) и последовательность
ops.py stop-ai/backup: admission/backend stop≤120с → worker SIGTERM/grace960с →
exit0 + свежий AI_WORKER_DRAINED после сигнала → tunnel stop≤15с. Итого1095с плюс
служебное время Docker. При nonzero exit даже существующий marker не подтверждает
drain; backup/tunnel stop запрещены до сверки. GPU drain915с/supervisor960с отдельно.
4новых signal/deadline теста (в том числе реальные POSIX signals в дочерних процессах
с имитацией I/O) и4затронутых SQL worker теста прошли. Реальные контейнеры/GPU/tunnel,
latency файлов/commit и runtime stop order ещё не проверены. Production не менялся.

AI_MVP_ENABLED=true само по себе не открывает доступ без остальных проверок.
Production в этом этапе не менялся.
