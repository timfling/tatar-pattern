# Публичный выпуск — 26.10.2026

**https://tatar-pattern.ru — guest-20261026-2, сайт открыт.**
Основные внешние проверки успешны; дальнейшее комплексное тестирование проводит владелец.
Эксплуатация и ежедневная кнопка — `STAGE-A-2026-10-25.md`; точные факты и ограничения — summary6.
Копии на Beget и Mac обслуживаются вручную одной кнопкой ежедневно. ИИ выключен.
Уведомление РКН не подано; владелец решил оформлять его параллельно тестированию.
Ниже — исторические этапы. Старые команды установки не повторять.

---

# 24.10.2026 — GPU окно и закрытый scope утверждены владельцем

Сегодня после подготовки: максимум2часа/250₽/27новыхjobs, ставка86,74₽/ч,
25qualification+2sitejobs(E2E/drain), безновыхплатныхretry. Пополнение неувеличивает
лимит автоматически. Толькоf10-wreath:graphic допускаетсянасайт послеfreshPNGaccept
иworkerproof; base/profile/SHA/условия в beget-ai-window-20261024/decision.json.
DraftJSONреестры и два внешних Composeoverrides втойжепапке подготовлены,
конфигурации проверены локально, наVPS не применены. Другиепарына сайте закрыты.
Unshelve пока не подтверждён. Старт2часов фиксировать отначалаUnshelve, завершение
GPUbilling требуетShelve/кабинета, не systemctlstop. Публичныйзапускотдельно.

# 24.10.2026 — Beget tunnel files подготовлены, GPU окно ещё не согласовано

Владелец подтвердил создание отдельного key на Beget:
SHA256:9rfANttjzdEGuC93eSPMalQRvvv7KoJNXAfBhSVxH5c.
Live GPU login/ограниченный user/Bearer/proof отсутствуют, GPU SHELVED_OFFLOADED.

Локальные инструменты для следующего согласованного окна:
- gpu_tunnel_account_20261024.py: по умолчанию plan-only; --apply на GPU создаёт
  строго ограниченную учётку для этого publickey. До установки authorized_keys
  обязательны hostpin/sshd-t/effective config/reload; live проверки NOT_RUN.
- gpu_evidence_snapshot_20261024.py: при неактивном GPU service и свободном state
  lock сохраняет raw allowlist и coherentSQLite в /srv/tatar-gpu-evidence, без token.
  Потом download на Mac и manifestSHA. Не активирует/не останавливает service.
Локальные проверки на temp/mock прошли; GPU runtime не изменён.
После Unshelve новыеqualification UUID передаются реальному worker probe аргументами;
старый sealed qualification-jobs.json не переписывать/не выдавать за новый proof.
Предел2ч/250₽/27jobs лишь предложен, текущая ставка и решение владельца ожидаются.

# 24.10.2026 — v2 restore PASS; следующий шаг transport

Новый набор20261024T111907Z-452fae успешно восстановлен в tp-restore-b1d8516e:
исходные SHA/counts сверены, guest status0 до API; нет worker/publicports;
после проверки тестовые контейнеры/сети удалены. Evidence:
/srv/tatar-pattern/staging-data/restore-checks/restore-ocdybtvc.
Рабочий HTTPS/catalog110 доступен. Реальный AI drain ещё NOT_RUN.

`beget_gpu_transport_prepare_20261024.py` — офлайн-подготовка на Beget root:
отдельный новый ключ, known_hosts с ранее проверенным fingerprint, public output.
Сохраняет в /etc/tatar-pattern/gpu, не перезаписывает чужие/частичные файлы,
использует общий staging maintenance lock. Не меняет env/sshd, не читает Macключ,
не создаёт Bearer, не соединяется с GPU. Передавать в incoming и выполнять python3 -B.
Локальные temp checks PASS, на VPS пока NOT_RUN. Host pin исторический;
ограниченный GPU account, текущий hostkey/boot, live transport и worker proof
проверяются в отдельном согласованном платном окне.

# 24.10.2026 — обслуживание v2 установлено; backup с AI=false PASS

Владелец подтвердил check/install, успешные существующие cleanup/backup services
и status установленного `/etc/tatar-pattern/staging-maintenance.py`.
Новый backup: `/srv/tatar-pattern/staging-data/backups/20261024T111907Z-452fae`,
завершён 11:19:59 UTC (14:19:59 МСК). HTTPS/catalog110 и status PASS;
worker stopped/absent. Расписания и env сохранены, исходный wrapper сохранён
как `/etc/tatar-pattern/staging-maintenance.flat-20261023.py`.
Изолированный restore нового набора ещё ожидается. AI=true/GPU/drain NOT_RUN.
Ниже статусы «не установлен» относятся к более ранней подготовке этого дня.

# 24.10.2026 — HTTPS staging: подготовка обслуживания v2 для AI

Актуальный закрытый staging: guest-20261020-1, tp-staging-20261023,
/etc/tatar-pattern/staging.env, /srv/tatar-pattern/staging-data. По выводу владельца
24.10 14:13 МСК: HTTPS/catalog110, LOCAL MAINTENANCE STATUS PASS; backup LAST
24.10 00:15 UTC (03:15 МСК), три timers активны, свободно49468MiB.

Внешний скрипт `beget_staging_maintenance_20261024.py` подготовлен локально;
выпуск и VPS пока не изменены. Действия check/install/status/cleanup/retention/backup/
restore-check/stop-ai. Использует sealed ops только для primitives и isolated restore,
собственную последовательность snapshot/drain. TLS override включён всегда;
AI_API_CONFIG=true добавляет compose.ai-api.yml/profileai, optional root0600
/etc/tatar-pattern/staging-ai.yml читается последним. Config JSON читается в памяти,
секреты не печатаются. Проверяет только loopback18080→443, Securecookie/CORS/guestTTL,
отсутствие других publishedports, одинаковые API/worker flags/budget/origin/proof/versions,
worker SIGTERM/grace960/restartno. Секреты/SSH ограничения готовятся отдельно.

Общий `.maintenance.lock` сохраняется. При занятом lock cleanup/retention пропускают
один запуск с exit0, следующие ticks сохраняются; прочие действия требуют повторного
ручного запуска. Это исключает убийство cleanup по TimeoutStartSec120 при ожидании
backup/drain960. Скрипт не меняет расписания и не отключает timers.

Backup: закрывает flatwriters120 → работающийworker960 → exit0+новыйDRAINED изlogs
точногоimmutablecontainerID → dump/storage/manifest. Внешний ledger
staging-data/.worker-drain-v2.json привязан кcontainerId/StartedAt/FinishedAt/ExitCode.
Уже остановленныйworker без совпадающего ledger, exit75/137/OOM, сменаcontainer/run,
нетmarker: отказ доsnapshot, DB/tunnel сохраняются, автоматическогоrestartнет.
Еслиworkerвообщеотсутствует, требуется0queued/submitting/polling вai_jobs.
После успешного quiesce flatwriters восстанавливаются даже приошибкеdump;
Возврат flat через start --wait без пересоздания контейнеров.
worker намеренноостаётсяостановленным, resume — отдельныйявныйшагвокневладельца.
Tunnelнеостанавливаетсяприbackup. stop-ai закрываетAPI→проверяетdrain→останавливает
толькоtunnel15→возвращаетflatAPI; это неостанавливаеттарификациюВМ.
Restore-check только для указанного локальногонабора: новыйprivateпроект,
AI=false/безworker/публичныхпортов, checksum/counts доguestreset передAPI.

Install заменяет только /etc/tatar-pattern/staging-maintenance.py атомарно после
check, общегоlock, точногоSHA исходногоскрипта ипроверкипринадлежностиexistingunits.
Сохраняет root0600 staging-maintenance.flat-20261023.py. Timers/env/containers
не меняет. Откат кflatwrapper допустим лишь после AI_API_CONFIG=false и безопасной
остановкиAI; приактивномAI старыйwrapper несовместим. Другуюверсиюнеперезаписывает.

Локальнаяпроверка:7unit safetytests PASS (fakeDocker/DB), Composeconfigдвематрицы
с синтетическимTLSoverride AIadapterfalse/true PASS; publicbind/insecurecookie отвергнуты.
Python3.9grammarPASS. Никакихконтейнеров/GPU/jobs в этихпроверкахнезапускали.
НастоящийVPScheck/install/новыйbackup/restore/drain ещё НЕ выполнены.

## 20.10.2026 — R5: обязательная область полного npm audit

Для полного source lock audit явно выполнять:

```sh
NODE_ENV=development npm audit --package-lock-only --include=dev --json
```

При запуске внутри production image передавать `docker run -e NODE_ENV=development`
и `--include=dev` в npm. Runtime audit выполнять отдельно с `--omit=dev`.
Metadata dev count и NODE_ENV=production audit0 не доказывают full0. Фиксировать
command/scope/NODE_ENV, SHA package+lock, Node/npm versions, JSON и exit code.

Для guest-20261020-1 корректный full-dev результат:5HIGHpackages одной dev-цепочки
braces, GHSA-vfj7-8cjw-p6xm; runtime audit0 не опровергнут. Внешний addendum:
`Выпуски/guest-20261020-1-SECURITY-ADDENDUM-2026-10-20.md`.
Запечатанный runtime-checks script не копировать как full audit без этой поправки.
Архив/images этого выпуска не меняются. Исключение не распространяется на dev/CI
с недоверенными glob patterns/исходниками/config. Подробные границы в addendum.

---

# 20.10.2026 — guest-20261020-1, только локальный этап А

Приоритет имеет новый выпуск `Выпуски/guest-20261020-1` и его `RELEASE-NOTES.md`,
`INTEGRATOR-RECHECK.md`, deploy/RELEASE-MANIFEST.json и deploy/IMAGES.json.
Backend R1/R2/SQL исправления и актуальный frontend включены в новые amd64 images.
Точный GPU payload из guest-20261019-1 сохранён; R3 review лежит отдельно в
release-evidence/gpu-review. Старый tp-img2img-http.tgz для восстановления не подходит.
AI/public gates закрыты, GUEST_GPU_BUDGET=0; deployed worker proof отсутствует.
VPS/SSH/GPU/public deploy/production restore не выполнялись. Legal placeholders и
public catalog approved=false сохраняют блок публичного запуска. Свежий OSV выявил
certifi advisory в dev-lock; подробное ограничение в SECURITY-EXCEPTIONS.md выпуска.
Нижележащие датированные записи и результаты прежних выпусков — история.

---

# TATAR PATTERN — deploy на Beget

## Провайдер и готовый комплект — 19.10.2026

Beget подтвердил отсутствие ресурсов VPS без ETA; владелец выбирает альтернативу.
Комплект guest-20261019-1 подходит для другого российского Ubuntu x86_64 VPS с Docker.
Бюджет VPS + независимые копии — до 2500 ₽/мес, GPU и домен отдельно.
Заменить имя провайдера/географию в legal DRAFT после фактического выбора, до публикации.

Точный каталог передачи: `Выпуски/guest-20261019-1`.
Проверка после распаковки: `python3 -B deploy/verify_release.py`.
Загрузка образов: `gzip -dc deploy/images/guest-20261019-1-amd64.tar.gz | docker load`.
Затем `python3 -B deploy/verify_release.py --images` — без запуска сервисов.
Базовый Git commit не включает все рабочие изменения. Отдельный sourceCommit и Git bundle
фиксируют исходники выпуска, не меняя общий Git. Большие catalog110.tgz/LoRA weights
включены отдельно; их SHA входят в закоммиченный INPUT-SHA256.json. SOURCE-SHA256.json
и IMAGES.json дополнительно проверяют полный комплект и готовые images. .env/ключи/БД/QA в комплект не входят. GPU payload не устанавливать поверх
живого qualified deployment; он нужен для отдельного согласованного переноса/восстановления.
APT-репозитории не заморожены: готовые images точны, будущая пересборка может иметь иной ID.

## Приоритет 19.10.2026 — guest-20261019-1

Текущий выпуск — снимок рабочей копии, включая изменённые/untracked assets/scripts/UI,
не pilot11.10. `snapshot_release.py` создаёт allowlist-копию вне Git дерева, manifest
с baseCommit+dirty status, lock SHA и полным SHA файлов. Image IDs фиксируются после
linux/amd64 build; SOURCE_FROZEN не является серверной приёмкой. Без .env/QA/DB/storage.
GPU service/профили/PEFTweights передаются отдельным payload; baseSDXL остаётся по exact
revision/inventory на GPU ВМ. Нельзя автоматически перезаписывать qualified GPU runtime.

Первый публичный режим — **PUBLIC_GUEST_MODE=true,COOKIE_SECURE=true,GUEST_GPU_BUDGET=0**,
миграции001–013. Нет постоянной истории/аккаунтов; проверять текущую работу/экспорт,
чужой доступ/expiry и сохранение неистёкших PNG/jobId после restart. Исторические
аккаунтные сценарии ниже не являются требованиями публичного гостевого выпуска.
Production import готов у backend: README «Подготовка релиза19.10»,110реальных элементов;
комплект payload/catalog:110flat+110texture+49кадров. Pending decision ещё approved=false;
конкретную запись public scope утверждает владелец, декларацию заново не запрашивать.

### Закрытое staging в выбранное окно

Сначала проверка release SHA и `docker load` новых images. Отдельный env0600:
COMPOSE_PROJECT_NAME=tp-staging-20261019,DATA_ROOT=/srv/tatar-pattern/staging-data,
STAGING_MODE=true,DOMAIN=localhost,AI_API_CONFIG=false,CALENDAR_LOGS=false.
Создать каталоги storage/migration-backups UID10001; другие volumes/проекты не трогать.
`python3 ops.py --env /etc/tatar-pattern/staging.env config`, затем up-internal,migrate.
Мигратор делает pg_dump до SQL. В существующем окружении сначала штатный stop-ai+backup;
exit75/nonzero/нет свежегоDRAINED: сохранить tunnel/DB, не переходить к копии/миграции.
Production catalog apply/verify — **ровно backend/README**, с назначенной operation и
отдельной утверждённой decision. Не импортировать рабочую БД или fixtures.
Затем `python3 ops.py --env /etc/tatar-pattern/staging.env up-staging`.
Доступ владельца: `ssh -N -L 18080:127.0.0.1:18080 ADMIN@VPS`, открыть
http://localhost:18080. Порт опубликован только на VPSloopback; внешнийDNS не нужен.
HTTP staging использует COOKIE_SECURE=false и не доказывает публичныеHTTPS/cookie.

Приёмка: production_catalog verify publicRealUniqueElements=110+PNG/SHA/provenance;
превью; принятаяflat схема→реальныйPNG/JPG→скачивание; два гостя не видят чужое;
аккаунтныеAPI404; restart→тот же неистёкший файл/SHA; послеexpiry отказ+cleanup.
Backup→restore-check в новый tp-restore проект: checksum/counts ДО reset, migrate,
guest_maintenance reset-restored --offline-restore --designated-operation=<copy-ref>,
затем status=0guestProcesses/guestGenerations/pendingGuestFiles,только после этого API.
Ни worker,ни публичныепорты в restore не запускаются. При legacyusers restore-check
останавливается: нужен latest independent erasure ledger по backendREADME. Не открывать.

### Эксплуатация и фактические overrides

AI_API_CONFIG=true в выбранном env **фактически добавляет compose.ai-api.yml и profileai**
во всех ops/offsite/maintenance действиях. API видит тот же origin/Bearer_FILE/sharedproof,
gates остаютсяfalse. GPU endpoint и readonly секреты готовит владелец в окне; известный
ED25519 SHA256:2uI6K/NhT8SghAVz0mgX3QBGgF1nQmV7yrqS4p2s2pk,publickey в payload/gpu/evidence.
Отдельная tunnel-учётка обязательна; ubuntu остаётся ownerlogin. Подготовка ограничений:
отдельный user/ключ, PermitOpen127.0.0.1:8765,AllowTcpForwardinglocal,безTTY/agent/X11/
shell-команд (authorized_keys command=/bin/false,restrict,port-forwarding,permitopen).
ServerMatchuser дополнительно ограничивает forwarding доlocal; сначала sshd -t и
вторая ownerсессия. Privatekey UID10001/0600,known_hosts readonly,внешнийBearer≥32символа;
значения не отправлять в чат/repo. ssh-keyscan сам не подтверждает подлинность ключа.

`maintenance.py --env ... proof` исполняет готовые25GET-probe UUID через **exec реального
ai-worker**, затем gpu_proof_status; POST/submit0. Timer tatar-proof каждые20ч и послеboot
включается только после живой приёмки. Он не продлевает GPU admissiondeadline/не включаетVM.
Тот же GPUboot/deployment: новыйGETproof; новыйboot/deployment: новаяqualification иaccept
поGPUправилам. Ошибкаrenew/normal503/просроченныйproof закрывают новыеAI; никаких paid retry.
Следить за expiry и Result timer, GPU normaldeadline должен покрывать согласованный период.
AI_EXPECTED_ONLINE=true задаётся только на согласованные часы доступностиGPU:
monitor проверяет readiness,expiry,worker/tunnel и Result/active proof timer каждые5мин.
При плановомGPUoff поставитьfalse; это не включает/выключаетVM и не разрешаетsubmit.
AIне объявлять24/7 при GPUокнах30мин; цена/часыдоступности сообщаются владельцу явно.

Установить rsyslog/restic и dedicated tatar-logs.service (конфиг rsyslog.conf), затем
CALENDAR_LOGS=true. compose.logs.yml направляет только этотпроект в /var/log/tatar-pattern;
Docker localcache disabled,accesslogsCaddy/Uvicorn выключены. WorkerDRAINED читается из
точногоcontainerName и времени>=SIGTERM в этихлогах. Без свежегоmarker остановкаfailclosed.
Обычный docker compose logs приэтом недоступен; читать защищённыеUTCdaily files.
Включить tatar-guest-cleanup.timer(60с),tatar-backup.timer,tatar-retention.timer(1ч),
tatar-monitor.timer. Systemdunits должны указывать на выбранный /srv/.../current;
staging только с отдельным env/unit,не устанавливатьproductionunit наstagingпоумолчанию.
Проверить systemctl --failed, journalctl -u tatar-guest-cleanup.service и statuspending=0.
ОшибкиFS не считатьудалением. Retention:2локальныхполныхнабора и возраст≤7д+1ч,
restic dedicatedrepository тотжевозраст,prune; migrationbackups тоже≤7д+1ч; logs<14д.
КопииполногоDBвключаютtransient,поэтому **каждыйrestore reset**; копии закрыты,неwebroot.
Providerbackup/WAL/snapshot/versioning и GPUTTL24ч/7д+qualificationисключения проверяются
отдельно,кодBegetне подтверждаетихудаление. Никакихдвухмесячныхкопийподобещаниеmax30д.

### Публичный gate

Нужно окно владельца с точнымVPS/domain/release/env/портами, approvedcatalogscope,
актуальныеутверждённыеlegal02/03/05(покаDRAFT),секреты/backuprepository+restoreevidence,
проверкаproviderretention, реальныйworkerproof+AIrelease/transferрешенияприоткрытииAI.
ГостевойGPUbudget0 менять тольконазначеннымокном/числомзадач. DNS/HTTPS/80/443 послеокна;
STAGING_MODE=false,COOKIE_SECURE=true,CORS=https://DOMAIN,толькоpublished80/443.
Снаружи проверитьHTTPS/главную/2логотипа/flat/AIошибкиилиразрешённыйE2E/текущуюработу/
скачивание,SecureHttpOnlyStrictcookie,чужойOrigin/ownership,затемrestart/reboot/persistence.
Серверной/публичнойприёмки в этомлокальномкомплекте пока нет.

---

## Воспроизводимая сборка комплекта

1. `snapshot_release.py --output /ABS/Выпуски/NEW_RELEASE` копирует allowlist вне общего Git.
2. Из снимка собрать backend/frontend/tunnel через штатные Dockerfile с `--platform linux/amd64`.
3. PostgreSQL/Caddy закрепить по amd64 platform manifest, не по выбранному Mac ARM multiarch tag.
4. `python3 -B deploy/commit_release.py --root .` создаёт отдельный source commit/bundle.
5. `python3 -B deploy/finalize_release.py --root .` сохраняет images, IDs и полные SHA.
6. `python3 -B deploy/verify_release.py --images`, затем `package_release.py --output ../RELEASE.tgz`.

Имя выпуска в текущем builder/template фиксировано guest-20261019-1; для нового выпуска
сначала задать новое имя в builder и .env.example, не перезаписывать старый tag/archive.
Git bundle восстанавливается `git clone --branch release deploy/guest-20261019-1-source.bundle ../release-source`.
Готовые images и большие отдельные payload брать из проверенного комплекта, не из старого GitHub.

## Команды на выбранном VPS: подготовлено, ещё не выполнялось

После назначения окна, установки Docker по официальной инструкции и передачи release
(ниже root/sudo, путь current указывает на guest-20261019-1):

```bash
apt-get update
apt-get install -y python3 restic rsyslog
install -d -m 700 /etc/tatar-pattern /srv/tatar-pattern/data
install -d -o 10001 -g 10001 -m 750 /srv/tatar-pattern/data/storage /srv/tatar-pattern/data/migration-backups
cd /srv/tatar-pattern/current/deploy
python3 -B ops.py --env /etc/tatar-pattern/production.env init
# Владелец заполняет защищённый env: DOMAIN, ACME_EMAIL, DATA_ROOT, RELEASE.
# Новый пароль БД генерирует init, его не копируют из примера.
python3 -B ops.py --env /etc/tatar-pattern/production.env config
```

Для закрытого staging создавать отдельные staging.env и DATA_ROOT по разделу выше.
Production env не подставлять в staging-команды. Для установки календарных логов и
задач, только после настройки независимого restic repository и его credentials:

```bash
install -d -m 700 /run/tatar-pattern-logs /var/log/tatar-pattern
rsyslogd -N1 -f /srv/tatar-pattern/current/deploy/rsyslog.conf
install -m 644 systemd/tatar-*.service systemd/tatar-*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now tatar-logs.service
# Только после появления /run/tatar-pattern-logs/syslog: CALENDAR_LOGS=true в env.
# Действующие контейнеры получают logging override при согласованном пересоздании.
# Сначала вручную проверить cleanup, offsite и retention на выбранном DATA_ROOT.
python3 -B maintenance.py --env /etc/tatar-pattern/production.env cleanup
# offsite.py/retention запускаются с credentials из защищённого restic.env через systemd.
systemctl start tatar-backup.service
systemctl start tatar-retention.service
systemctl enable --now tatar-guest-cleanup.timer tatar-backup.timer tatar-retention.timer tatar-monitor.timer
systemctl --failed
```

`rsyslogd -N1` требует созданных каталогов; systemd RuntimeDirectory/LogsDirectory создают
их при старте. При первоначальной проверке сначала создать /run/tatar-pattern-logs и
/var/log/tatar-pattern с правами0700 либо выполнять validation после старта service.
Не включать tatar-proof.timer до действующего worker и успешного ручного GET-probe.
Не применять эти production units на чужие/существующие проекты. Credentials не source
из недоверенных файлов и не печатать в терминал/чат; systemd читает EnvironmentFile.

После reboot VPS db/API/frontend/proxy восстанавливаются по restart policy. Worker с
restart=no требует ручной сверки ai_jobs и запуска в назначенном окне — это осознанно.
Из deploy, с тем же выбранным env, AI_API_CONFIG=true и реальными readonly секретами:

```python
from pathlib import Path
from ops import read_env, compose
p = Path('/etc/tatar-pattern/production.env')
v = read_env(p)
assert v['AI_API_CONFIG'] == 'true'
dc = compose(p, v)
dc('up', '-d', '--wait', '--no-build', 'gpu-tunnel', 'ai-worker')
```

Далее `python3 -B maintenance.py --env /etc/tatar-pattern/production.env proof`.
Если GPU boot/deployment изменился, сначала qualification/accept по GPU handoff;
если admission истёк — согласованное продление на GPU, timer этого не делает.
При ошибках proof новые AI закрыты; jobId нельзя заменять новым paid submit.
Проверить сохранённые неистёкшие PNG/SHA и текущую работу снаружи после каждого restart.

## Историческая инструкция 11–18.10 (применять с поправками выше)

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


## AI MVP — совместимость с новым GPU HTTP, 18.10.2026

**LOCAL_CONFIG_READY / GPU_HTTP_NOT_RUN / SHUTDOWN_RUNTIME_NOT_TESTED.**
Актуальные контракт/согласования: верх ../../ИИ/GPU-HANDOFF.md и GPU-INTEGRATION.md.
Художественный отбор идёт параллельно разработке; старый motif/D/D1 не контракт.
Сайт/backend/storage остаются на Beget. GPU выполняет SDXL+LoRA img2img в immers.cloud.

### Подключение и имена env

Профиль ai в compose.yml выключен по умолчанию. Один ai-worker: тот же backend release,
команда `python -m scripts.ai_worker`, UID10001, общие DATABASE_URL и STORAGE_ROOT=/data/storage.
Сети worker: data и internal gpu-link. Tunnel: gpu-link и gpu-egress для исходящего SSH.
Worker → http://gpu-tunnel:18765 → SSH → GPU-host127.0.0.1:8765. Tunnel слушает
контейнерный интерфейс0.0.0.0:18765, host ports отсутствуют. Localhost worker,
Beget-хоста и GPU-хоста различаются. Сайт использует прежние edge/Caddy/HTTPS.

В верхнем backend-согласовании GPU-INTEGRATION.md уже приняты и в коде прочитаны:

```dotenv
AI_GPU_BASE_URL=http://gpu-tunnel:18765
AI_GPU_TOKEN_FILE=/run/secrets/gpu_bearer
AI_GPU_HTTP_PROOF_FILE=/data/storage/ai-gpu-worker-proof.json
GPU_EXPECTED_WORKFLOW_VERSION=tp-sdxl-composition-img2img/1.0.0
GPU_EXPECTED_MODEL_VERSION=378c08ff157660a3399573e1cd5918ad8f3aec344646c5336b027d63fe50ca42
AI_MVP_ENABLED=false
```

Имена env и последовательность остановки окончательно подтверждены backend и чатом5
через владельца. Самостоятельных сообщений агентам в этом ходе нет. AI_GPU_TOKEN пуст в Compose:
используется ровно один Bearer source, TOKEN_FILE. GPU-серверная настройка
TP_INFERENCE_TOKEN(_FILE) — другая сторона, не имя клиентской настройки.
AI_PROVIDER_ENV_FILE — optional внешний0600 env для дополнительных настроек;
явные environment в Compose имеют приоритет. URL/TOKEN_FILE/proof path закреплены
в Compose; версиям заданы согласованные defaults и значения .env.example.
Никакие реальные env/secret files этим ходом не создавались/менялись.

GPU_BEARER_FILE → readonly /run/secrets/gpu_bearer, create_host_path=false; Bearer
минимум32ASCII, файл0600 читается UID10001. GPU_SSH_KEY_FILE0600 и проверенный
GPU_KNOWN_HOSTS_FILE также readonly, без создания отсутствующих source paths;
каталог секретов вне checkout0700. SSH StrictHostKeyChecking/BatchMode/IdentitiesOnly,
ExitOnForwardFailure и keepalive включены, ключ без shell/agent forwarding.
IP195.209.221.75 и loginобразаubuntu получены от владельца из кабинета:
ВМtp-sdxl-smoke-20261016, статусSHELVED_OFFLOADED; живой endpoint не проверен.
Фактические SSH-порт, tunnel-user и проверенный host key/fingerprint ещё нужны. GPU SSH restrictions
устанавливаются отдельно в будущем; firewall/SSH config GPU сейчас не менялись.

Для будущей конфигурации API подготовлен **неприменённый** compose.ai-api.yml:
те же URL/versions/proof и readonly Bearer, backend получает gpu-link, остаётся AI=false.
Обычные ops-команды этот override не применяют. Его применение требует защищённого
файла и отдельного release-плана; сейчас обычный API не получает GPU secret/network.
Proof хранится в общем persistent storage, API читает его; записывает только явный
owner-run probe из worker namespace. Дублирующий bind proof не нужен: используется storage.

### Контракт и readiness

Transport совместим с tp-gpu-img2img/1.0: Bearer на всех routes, девять JSON-полей
submit, UUID idempotency, status/image. Изображения/recipe/profiles заранее на GPU;
произвольные prompt/URL/path/base64/strength/steps не передаются. Перевод внутренней
задачи, pins и PNG/metadata проверку выполняет backend adapter, не deploy.
Backend локально реализовал HTTP adapter и scripts.ai_gpu_probe; реального proof нет.
Нужно подтвердить одинаковый release API/worker с актуальными app/assets/profiles/scripts.

Tunnel health — только TCP listener. /api/health сайта — не GPU readiness.
ai-readiness.py — ручная проверка только health: auth, exact contract/catalog/workflow/
model, normal mode, draining=false, deploymentDigest/bootId. Не пишет proof и не разрешает
AI. Финальная readiness у backend проверяет также qualified пары/профили и свежий
worker proof≤24ч с теми же origin/deploymentDigest/bootId. После GPU restart нужен новый proof.
AI_MVP_ENABLED=false и gates releaseApproved/externalTransferApproved не включены.
GPU off/draining → AI недоступен явно; сайт/сохранённые PNG/история независимы.
Никакого flat fallback, запуска ВМ или платного resubmit при uncertain submit.

### Порядок и время остановки

Backend подтвердил: drain930с от первого SIGTERM/SIGINT, включая текущие HTTP,
запись результата и commit; повторный сигнал срок не продлевает. Аварийный watchdog
на950-й секунде делает exit75 без успешного drain, оставаясь активным и при закрытии БД.
Compose **SIGTERM, stop_grace_period960s** принят: предел приложения950с + запас10с. GPU drain≤915с, отдельный GPU supervisor TimeoutStopSec960 —
это не worker timer. Timeout туннеля после успешного worker drain —15с.

Безопасная локальная операция подготовлена: `python3 ops.py --env <protected.env> stop-ai`.
Она сейчас НЕ запускалась. Последовательность:

1. Остановить backend с timeout120с: закрывается admission новых API задач.
   Это maintenance API целиком; статический frontend не останавливается. Для AI-only
   admission потребуется отдельный согласованный backend механизм.
2. Пока DB/storage и tunnel доступны, послать SIGTERM worker и ждать до960с.
   Worker не берёт новые queued, завершает poll/download либо сохраняет явное
   resumable/uncertain состояние. Ожидается exit0 и новый `AI_WORKER_DRAINED:` после сигнала.
3. Только после двух подтверждений остановить tunnel с timeout15с. DB сохраняется.
   Локальный верх таймаутов последовательности120+960+15=1095с (18мин15с),
   плюс служебное время Docker. Это предел остановочных ожиданий, не обещание drain latency.
4. При exit75(watchdog)/exit137/другом nonzero/crash/неподтверждённом marker/ошибке DB операция прерывается:
   tunnel и DB остаются, admission не возобновляется автоматически. Сверить ai_jobs/
   generations и сохранить явное состояние через backend-процедуру. Не повторять submit.

Не использовать общий `stop -t120`, `down --timeout120` или принудительный kill всего
стека. Даже dependency order не проверяет DB commit/marker. Внешний supervisor,
если появится, должен дать всей последовательности больше1095с + запас, не обрывая
ops.py на60с. Compose stop по истечении960с может послать SIGKILL: это авария,
а не успешный drain; helper не разрешит затем автоматическую остановку tunnel.

Прежний зазор начала drain закрыт backend и подтверждён владельцем. Это не гарантия
сохранения при зависшем storage/БД: watchdog75 требует сверки ai_jobs/generations,
как и любое неподтверждённое завершение. Реальный контейнерный SIGTERM→exit и задержки
записи/commit ещё не проверены; backend-код здесь не менялся.

Чат5 исправил собственный, пока не установленный GPU systemd template:
TimeoutStopSec960, KillMode=mixed, KillSignal=SIGTERM, SendSIGKILL=yes. Первым сигнал
получает main server, renderer может завершить работу в пределах GPU drain≤915с.
Реальная работа systemd/HTTP при drain не проверена.

Backup теперь отдельно останавливает admission writers(proxy/frontend/backend,120с),
затем worker960с с той же проверкой exit+marker, и только потом делает DB dump+storage.
Tunnel/DB всё время доступны. При неподтверждённом drain backup не делает dump/manifest
и не перезапускает writers автоматически. После успешного quiesce они возобновляются
даже при ошибке dump; это не отменяет удалённую GPU-задачу.

### Будущее разрешённое окно проверки

1. Env/worker shutdown согласованы. IP195.209.221.75 известен из кабинета, перед подключением сверить заново.
   Нужны подтверждённые SSH-порт, tunnel-user и проверенный fingerprint/public host key
   для known_hosts через согласованный файл; ubuntu пока только loginобраза.
   Реально qualified-пар пока0: шесть локальных кандидатов для f10-wreath/f14-directed/
   f08-directed × graphic/textured; textured f08 слабый. Новые12основ без GPU-профилей.
   Владелец выбирает пары и разрешённое окно; ни один кандидат не включается автоматически.
2. Подготовить внешние секреты, одинаковые release images и assets; собрать tunnel image.
   Проверить Compose с выбранным env без печати секретов (`config --quiet`).
3. Запустить только tunnel. Из worker namespace выполнить health-only check:

   ```bash
   dc_ai() { docker compose --env-file /etc/tatar-pattern/production.env -f compose.yml --profile ai "$@"; }
   dc_ai run --rm --no-deps ai-worker python /opt/deploy/ai-readiness.py
   ```

4. После GPU qualification/visual accept и normal GPU service проверить готовые GPU jobs
   из worker (команда backend не создаёт inference):

   ```bash
   dc_ai run --rm --no-deps ai-worker python -m scripts.ai_gpu_probe --owner-run --worker-namespace --job-id <approved-ready-GPU-UUID>
   ```

   Повторить --job-id для каждой допускаемой пары. Создаётся только настоящий runtime
   proof в shared storage, не repo. Health200/CPU tests не заменяют этот шаг.
5. После остальных разрешений отдельным reviewed release согласовать API override и
   включение gates. Один явный сайт→job→GPU→PNG1024²≤20MiB/SHA/metadata→Beget storage+DB;
   открыть историю/скачивание при GPU off без нового submit. Нужен backend-specific путь
   qualification при AI=false: не обходить gates для теста.
6. В этом же окне проверить реальный SIGTERM worker/GPU, доступность poll/download
   при GPU drain, marker/exit/DB state, время и backup. GPUstop/оплата отдельно владельцем.

### Проверки нового изменения

Только новые настройки: compose config worker и optional API override, env/versions/
readonly secret,960s grace, без published AI ports — PASS. Пять целевых unit tests
backup/stop-ai: порядок, отдельные timeouts, crash/missing marker блокируют tunnel stop,
backup не создаёт complete snapshot при неподтверждённом drain — PASS. Новые health fixtures:
normal→health-onlyOK, draining/qualification/old contract→unavailable, без HTTP/proof. Python syntax PASS.
Образы/контейнеры/SSH/GPU/HTTP/proof/реальный process shutdown не запускались.
Production/DNS/firewall/реальные секреты/облако/платные ресурсы не менялись.


Подтверждение завершения согласования18.10: backend отдельно проверил сигналы/deadline
в дочерних процессах и worker на изолированной PostgreSQL (сведения backend, Beget эти
проверки не повторял). В deploy добавлена только целевая regression-проверка exit75:
при watchdog не останавливать tunnel/DB, не делать backup dump/manifest и не возобновлять
admission автоматически. GPU qualification/jobId/record/worker-proof по-прежнему отсутствуют.
