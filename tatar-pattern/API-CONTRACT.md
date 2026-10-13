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
