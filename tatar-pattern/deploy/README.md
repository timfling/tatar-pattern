# TATAR PATTERN — deploy на Beget

11.10.2026. Статус: **комплект подготовки к запуску; сайт не опубликован**. Результаты локальной проверки — [VERIFICATION.md](VERIFICATION.md), выбор/стоимость/действия владельца — [BEGET.md](BEGET.md), обязательные стыки — [HANDOFF.md](HANDOFF.md). Всё создано только в deploy/ и собственном summary. Нет аккаунта, VPS, домена или утвержденного бюджета.

## 0. Что именно запускаем

Один VPS РФ/СПб, 2CPU/4ГБ/40ГБNVMe, IPv4, Ubuntu24.04. Docker Compose: Caddy HTTPS80/443 → `/api` FastAPI8000 (1worker) → PostgreSQL16; остальное Next3000 (`next build --webpack`, `next start`). Доступны только80/443; SSH22 только с IP администратора. Нет Adminer, API docs, опубликованных5432/8000/3000, нет cloud job worker. ИИ предполагается на DSLab после отдельной реализации.

Данные `/srv/tatar-pattern/data/{postgres,storage,migration-backups,caddy-data,caddy-config,backups}` находятся вне версий кода. Только backend раздает защищенные изображения: storage не является публичным static-каталогом. Same-origin браузер, `/api` сохраняется целиком. CORS exact `https://DOMAIN`, Secure cookies, secrets из защищенного env, ни .env, ни dataset, ни backups не входят в image build context.

**Платная стадия:** владелец подтверждает конфигурацию/счет38₽/день с IPv4, месячный предел, цену домена/копий и аккаунт. **Публичная стадия:** отдельное конкретное разрешение на DNS/80/443/HTTPS, утвержденные права каталога и правовые документы (BEGET/HANDOFF), независимые копии. Эти действия агент не выполнял. Production с пустым разрешенным каталогом может быть healthy, но не считается принятой работающей системой.

## 1. Подготовить VPS после задания владельца

Администратор на новом сервере: обновляет Ubuntu24.04, устанавливает Docker Engine/Compose v2 по [официальной инструкции Docker](https://docs.docker.com/engine/install/ubuntu/), Python3, restic (`apt install python3 restic`), включает docker.service. Не устанавливать платную панель. Проверить SSH ключом во второй сессии, затем отключить password/root login по принятой политике. Настроить firewall Beget/хоста:22 только IP администратора,80/443 лишь после разрешения, IPv6 по той же политике; не создавать AAAA, пока IPv6 не проверен. Не полагаться только на UFW: Docker publication может обходить UFW, поэтому конфигурация сама не публикует служебные порты.

Проверить `docker compose version`, `docker info`, `df -h`, `free -h`, `timedatectl` (NTP), имеющиеся Docker сети: диапазон edge по умолчанию172.29.86.0/24 должен быть свободен. При конфликте задать EDGE_SUBNET и PROXY_IP из его диапазона. Сеть data internal; db подключен только к ней. Backend доверяет forwarded headers только IP Caddy, а Caddy переписывает X-Forwarded-For реальным remote_host.

Создать новую структуру, команды на сервере под root:

```bash
install -d -m 700 /etc/tatar-pattern /srv/tatar-pattern/data
install -d -m 755 /srv/tatar-pattern/releases
install -d -o 10001 -g 10001 -m 750 /srv/tatar-pattern/data/storage /srv/tatar-pattern/data/migration-backups
```

`postgres`/Caddy каталоги Compose создаст; не делать рекурсивный chown всего postgres. Docker daemon/root — административный доступ; env виден администратору Docker. Хранить доступы ограниченно.

## 2. Зафиксировать и передать release

Интегратор согласует состояние backend/frontend/db и прекращение одновременных изменений. Общего Git в корне нет: сохранить source manifest SHA256, tar выбранных исходников, release ID, locks, Dockerfile и image IDs. В build нужны backend app/scripts/pyproject/uv.lock, db migrations, frontend src/public/configs/package+lock и deploy. Не включать `.env`, `.venv`, `node_modules`, `.next`, `.git`, `.qa`, local-test, catalog-input, storage, backups и персональные данные. Manifest/файлы каталога передавать отдельно только после подтвержденных прав.

На сервере распаковать согласованный комплект в `/srv/tatar-pattern/releases/pilot-20261011-1` (это корень tatar-pattern), создать ссылку:

```bash
ln -s /srv/tatar-pattern/releases/pilot-20261011-1 /srv/tatar-pattern/current
cd /srv/tatar-pattern/current/deploy
python3 ops.py --env /etc/tatar-pattern/production.env init
```

Отредактировать новый env0600 на сервере: реальный DOMAIN (hostname без схемы/пути), ACME_EMAIL, DATA_ROOT=/srv/tatar-pattern/data, RELEASE уникальный неизменяемый ID. Init создает64hex DB password: URI безопасен, повторный init существующий файл не перезаписывает. Не выводить env/`docker compose config` целиком и не вставлять секреты в shell history. Ввести restic секреты позднее в отдельный `/etc/tatar-pattern/restic.env`0600 и password-file0600 (ни ключи, ни password не передавать frontend). У приложения нет придуманного JWT/DSLab key: нынешние сессии непрозрачные и хранятся в PostgreSQL.

```bash
python3 ops.py --env /etc/tatar-pattern/production.env config
python3 ops.py --env /etc/tatar-pattern/production.env build --platform linux/amd64
python3 ops.py --env /etc/tatar-pattern/production.env check-frontend
python3 ops.py --env /etc/tatar-pattern/production.env up-internal
python3 ops.py --env /etc/tatar-pattern/production.env migrate
```

Build последовательно по lock, по умолчанию для linux/amd64; --platform linux/arm64 допускается только для отдельной локальной проверки. Build и check-frontend сверяют архитектуру и установленный next/package.json с точной стабильной версией dependencies.next в исходниках, отклоняют версии ниже 16.3.8. Publish всегда требует linux/amd64 независимо от --platform. Порог не заменяет свежий npm audit. Check-frontend не запускает Compose и не открывает порты; up-internal запускает только db без портов. Мигратор перед любой миграцией сохраняет pg_dump16 в migration-backups; mount доступен UID10001. Если backup/ledger не прошел — не продолжать. Сиды/fixtures в production не запускать. После первого build записать image IDs и RepoDigests; для опубликованного release использовать сохраненные образы, а не заново собирать тот же tag. PostgreSQL16/Caddy version tags обновляемы: перед запуском закрепить их RepoDigest в POSTGRES_IMAGE/CADDY_IMAGE. Python/Node base tags также фиксировать digest при утверждении release; абсолютная побайтовая идентичность при новой apt сборке не заявлена. Проверка на Mac arm64 не заменяет сборку/приемку на Beget amd64.

## 3. Каталог и внутренний старт

Штатный install_local_catalog не является публичным importer. По HANDOFF чат2/интегратор предоставляет согласованный manifest/права и безопасную production-команду. Копируются только нужные исходные кадры и PNG в storage с сохранением относительных путей, затем импорт/аудит; не импортировать целую рабочую БД с QA аккаунтами. `TP_ENVIRONMENT=production`, `ALLOW_FIXTURES=false` обязательны. Backend может скрыть неподтвержденный каталог — это ожидаемое ограничение, не повод включать локальный режим.

Для операций задать функцию, она сама ничего не публикует:

```bash
dc() {
  docker compose --env-file /etc/tatar-pattern/production.env -p tp-production \
    -f compose.yml -f compose.public.yml --profile public "$@"
}
dc up -d --wait db backend frontend
```

До разрешенной публичной стадии **proxy не запускать**. Внутренняя проверка:

```bash
dc exec -T backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health').status)"
dc exec -T backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/capabilities').read().decode())"
dc exec -T backend python -m scripts.catalog_audit --storage-root /data/storage --report /tmp/catalog-audit.json
python3 ops.py --env /etc/tatar-pattern/production.env backup
```

Нужны фактические realUniqueElements/файлы, а не только health200. Отчет аудита копировать отдельно из /tmp до пересоздания; tmpfs не постоянен. Не запускать migrate одновременно с API/импортом.

## 4. HTTPS — только после конкретного разрешения

Еще раз назвать владельцу exact VPS/domain/DNS/ports/env/release и остающиеся правовые зависимости. После подтверждения: A для выбранного домена →IPv4 VPS. Удалить неверный AAAA, CAA должен разрешать issuer Caddy; www не настроен и отдельно не обещан. Проверить DNS извне. Открыть80/443 (22 остается IP администратора).

```bash
python3 ops.py --env /etc/tatar-pattern/production.env publish --confirm-public
curl --fail --silent --show-error "https://DOMAIN/api/health"
curl --fail --silent --show-error "https://DOMAIN/api/capabilities"
curl --head "http://DOMAIN/"
curl --head "https://DOMAIN/"
```

Заменить DOMAIN настоящим hostname. Caddy сам получает/продлевает ACME сертификат, data/config persistent; TLS не заменяется self-signed. HTTP должен перенаправлять на HTTPS. Если выпуск сертификата/health не прошел — не объявлять сайт опубликованным. Не использовать curl -k.

## 5. Проверяемая приемка на сервере

В протоколе указать время, release/image IDs, OS/архитектуру, реальные URL, длительность/restarts, SHA результатов; не хранить пароль/cookie в протоколе.

- HTTPS с валидной цепочкой, `/` и `/api/health`200, capabilities честно AI unavailable до DSLab; real elements доступны с правами. `/docs`, `/openapi.json`404; из внешней сети5432/8000/3000 закрыты. `docker compose ps` показывает только80/443 у proxy, `ss -lntp` сверить на хосте.
- Через браузер register/login→flat→history→PNG/JPG; cookie Secure, HttpOnly, SameSite=Lax, Path=/api. Чужой Origin мутации403, чужие result/project404, несанкционированный export401. X-Forwarded-For из внешнего запроса не подменяет IP limiter (проверять без персональных логов).
- Сохранить SHA PNG/JPG и generation ID, выйти/войти. `dc restart backend frontend proxy`, затем снова открыть историю/скачать тот же файл и сравнить SHA. Контейнеры без dev/reload, один Uvicorn worker. Проверить отказ/восстановление API (ограниченный maintenance тест), health/restart monitor.
- Сделать DB+storage backup, independent copy, восстановить в отдельный проект без published ports. Данные production не перезаписывать. Потом reboot VPS в согласованное окно; проверить Docker restart unless-stopped, health, same files/session/history, работающий backup timer.
- Пилот3–5 пользователей: измерить p50/p95 запросов/генерации, RSS/OOM, CPU/disk, ошибки429/503. Два параллельных flat-запроса — текущий лимит; длительность до замеров не гарантирована. Timeout120s — стартовая настройка, при превышении измерить/согласовать алгоритм, не маскировать повторной генерацией.

**«Опубликовано и принято»** только после этого протокола. Подготовленные файлы/локальный fixture тест этого не доказывают.

## 6. Backup, offsite, проверка восстановления

`ops.py backup` останавливает работающие proxy/frontend/backend на время snapshot, дает120s graceful stop, сохраняет custom pg_dump и storage tar со SHA/числом строк, затем возвращает ровно ранее работающие сервисы. DB продолжает работать без других writers; пока job worker отсутствует. Запретить параллельные импорты/миграции/ручную запись. Это короткое окно недоступности; измерить его и согласовать с владельцем. Если процесс backup оборван/упал хост, вручную проверить/start сервисы. Неполный набор без manifest не восстанавливается. Dump в текущем скрипте читается в память: при росте БД до сотен МБ/ГБ пересмотреть на streaming/увеличить резерв RAM.

Копия включает каталог+пользовательские файлы, БД+рецепты+сессии; SHA manifest не криптографическая подпись. Секреты/SSH keys не кладутся в архив. Отдельно хранить защищенные env (менеджер паролей), source release/images и ключ restic, чтобы восстановление не зависело от погибшего VPS. Бесплатный Beget backup дополнительный.

Владелец выбирает независимый repository в РФ, цену/сроки/доступ; endpoint S3 не придуман. Защищенный restic.env содержит точный `RESTIC_REPOSITORY`, `RESTIC_PASSWORD_FILE`, для S3 `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, при необходимости `AWS_DEFAULT_REGION` по реальной спецификации. Не shell-source неизвестные файлы. Первый `restic init` выполнить из защищенной admin-сессии с этими переменными. Одна отдельная копия на диске того же VPS не offsite.

```bash
install -m 644 systemd/tatar-backup.* systemd/tatar-monitor.* /etc/systemd/system/
systemctl daemon-reload
systemctl start tatar-backup.service
systemctl status tatar-backup.service
systemctl enable --now tatar-backup.timer tatar-monitor.timer
systemctl list-timers 'tatar-*'
python3 ops.py --env /etc/tatar-pattern/production.env health
```

Offsite скрипт после успешного restic backup оставляет2 local sets. Ошибка backup/upload оставляет прежние копии, возвращает error; контролировать место. Предложенная offsite retention:7daily/4weekly/2monthly, утвердить с политикой ПДн. Еженедельно в admin-сессии с restic env:

```bash
restic check --read-data-subset=1/10
restic forget --tag tatar-pattern --keep-daily 7 --keep-weekly 4 --keep-monthly 2 --prune
```

Мигратор дополнительно копит migration-backups: старые копии удалять только после сохранения нужного комплекта вне VPS и успешного restore, не бесконтрольно. Restore ежемесячно и перед опасным обновлением: взять последний набор **из независимого repository**, `restic restore SNAPSHOT_ID --target /srv/tatar-pattern/restore-download`; найти в восстановленной исходной структуре каталог с manifest.json и передать:

```bash
python3 ops.py --env /etc/tatar-pattern/production.env restore-check --source /ABSOLUTE/PATH/TO/BACKUP_SET
```

Создается новый tp-restore-* проект, новый deploy/local-check/restore-* каталог; ports не публикуются. Проверяются контрольные суммы архива/каждого storage файла, pg_restore без ошибок, counts users/generations/elements/migrations, API DB health, затем контейнеры снимаются, данные/RESTORE-PASS сохраняются. Это не полная проверка браузером: staging проверку доступа к результату после login провести отдельно без публикации персональных данных. После теста новые каталоги можно убрать адресно администратором; не удалять production DATA_ROOT.

Для аварийного восстановления: новый VPS/новые DATA_ROOT/DB (или новый изолированный каталог на прежнем), вернуть согласованный release/images, получить offsite набор, пройти restore-check, восстановить туда БД+storage, исправить UID10001 и env, закрыть публичный доступ до проверки. Нельзя pg_restore в действующую БД или распаковывать tar поверх действующего storage. Переключать DNS/production env только после отдельной приемки; сохранить прежние данные для расследования. Повторить удаление данных по действующей политике (старый backup может вернуть удаленные записи).

## 7. Logs и мониторинг

Каждый Docker service: json-file10MB×3, backend access log выключен, Caddy access log выключен. Смотреть `dc logs --tail 100 backend proxy`, не отправлять логи с данными/URL/credentials третьим лицам. На VPS настроить journald `SystemMaxUse=200M`, `MaxRetentionSec=14day`, перезапуск journald в плановом окне; logs могут содержать traceback, ограниченный срок не делает их публичными.

Monitor5мин: healthy db/backend/frontend и работающие optional proxy; warning disk≥80% или free<5ГБ; backup local/offsite старше26h считается error. При Docker health=unhealthy API/Next/Caddy monitor делает один restart за запуск, оставляет error для видимости; DB не перезапускает автоматически. `restart: unless-stopped` перезапускает упавший процесс и после reboot, сам по себе healthcheck не перезапускает unhealthy процесс. Намеренно остановленный сервис monitor не включает.

Включить правила CPU/RAM/disk и email/Telegram уведомления в Beget на реальные контакты. Сбой `tatar-backup.service`/`tatar-monitor.service` обязан попадать в согласованный канал администратора (текущие unit не выдумывают SMTP/бота): настроить OnFailure/внешний мониторинг отдельно и проверить искусственным отказом. Пока оповещения не настроены — ежедневная проверка `systemctl --failed`, `journalctl -u tatar-backup -u tatar-monitor --since today`, `df -h`, `docker system df`. Не выполнять общий docker system prune, image prune -a, compose down -v, reset. Хранить текущую и предыдущую image версии; чистить только конкретные проверенные старые images/backup наборы.

## 8. Обновление и откат

1. Новый уникальный RELEASE и отдельный source каталог; прежние images сохранить. Build до переключения, вне трафика/на отдельной amd64 машине если4ГБ мало. Не переписывать published tag.
2. `ops backup`→offsite→restore-check; записать snapshot/release ID и изменения миграций. После согласованного maintenance `dc stop proxy frontend backend`.
3. Сменить current на новый release (в env тоже RELEASE), `migrate` при остановленном API. При ошибке не продолжать. DATA_ROOT/COMPOSE_PROJECT_NAME/POSTGRES_PASSWORD прежние: пароль env сменой не ротируется в существующем postgres, ротацию делать отдельно через SQL и обновление env.
4. Внутренние `dc up -d --wait db backend frontend`, smoke, затем разрешенный `publish`. Проверить same generation/files/session, offsite и health.
5. Откат приложения: при совместимой добавочной схеме вернуть предыдущие current/RELEASE, `dc up -d --wait --no-build`, проверить. **Миграции автоматически назад не откатывать.** Если схема несовместима — оставить maintenance, восстановить предмиграционный DB+storage в новые каталоги/БД и отдельно согласовать переключение/потерю новых записей. Старые данные не удалять.

## 9. Локальная изоляция и продолжение

Локальная проверка использует только deploy/local-check, tp-deploy-check-20261011, отдельную db без host port, localhost случайный port Caddy, синтетические fixtures. compose.local ослабляет Secure исключительно для этого HTTP теста; в production не применять. Продолжение и фактические команды/ограничения — VERIFICATION. После получения VPS выполнить этапы1–8 с реальными env/правами/доступом; не путать подготовку с опубликованным сервисом.

### Команды восстановления в новый DATA_ROOT при аварии

Только после выбора нового VPS/каталога и maintenance; below запускаются вручную администратором. `/etc/tatar-pattern/recovery.env` — защищенная копия config с **новым** DATA_ROOT, COMPOSE_PROJECT_NAME=tp-recovery-..., тем же согласованным image RELEASE и новым DB password. Предыдущая БД/файлы не затрагиваются. Убедиться, что production остановлен и snapshot прошел restore-check.

```bash
# Из deploy/. RESTORE_SET и RECOVERY_DATA — проверенные абсолютные пути, не production DATA_ROOT.
install -d -o 10001 -g 10001 -m 750 "$RECOVERY_DATA/storage" "$RECOVERY_DATA/migration-backups"
python3 ops.py --env /etc/tatar-pattern/recovery.env up-internal
recovery_dc() {
  docker compose --env-file /etc/tatar-pattern/recovery.env -f compose.yml "$@"
}
recovery_dc exec -T db sh -c 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_restore -U tp -d tatar_pattern --exit-on-error --no-owner --no-acl' < "$RESTORE_SET/database.dump"
tar -xzf "$RESTORE_SET/storage.tar.gz" -C "$RECOVERY_DATA"
chown -R 10001:10001 "$RECOVERY_DATA/storage"
recovery_dc up -d --wait backend frontend
```

Restore только в чистую tatar_pattern нового проекта. Повторный restore поверх частичного/существующего — остановиться и создать другой новый DATA_ROOT, без --clean/reset. Затем повторный аудит/checksum, проверка login/history/export, удаления по политике и согласованное переключение. Recovery proxy/ports пока не запущены; `publish` требует явный public gate и исправленный Next. Новая база восстанавливает TP пользователя/таблицы под credentials recovery.env, dump не переносит суперпользовательские роли.

Для смены code symlink при update/rollback администратор использует `ln -sfn /srv/tatar-pattern/releases/APPROVED_RELEASE /srv/tatar-pattern/current` и редактирует RELEASE в защищенном env; DATA_ROOT сохраняется. Указать настоящий APPROVED_RELEASE. Перед откатом подтвердить совместимость схемы и существование точных image tags; не выполнять повторный build старого tag.
