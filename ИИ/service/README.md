# GPU img2img HTTP — текущий этап принят 19.10.2026

Последняя owner-проверка после продления admission на30мин и systemd restart:
**HTTP200, passed=true; normal/notDraining/qualified25/sameBoot/sameDeployment — PASS.**
BootId `a6e2f4bf-14f4-43fd-a842-76608ce2ce5d`, deploymentDigest
`51615fddf6fa09d8ad2155f432a3c79bccef9f810e996f4167000e5abe617771`.
Предыдущий503 вызван истёкшим admission; восстановление выполнено.
27GPU HTTP job прошли,25конкретных PNG приняты владельцем на15основах.
Исключены только f07-repeat:textured и f25-directed:textured.

GPU/LoRA этап готов к передаче; новых генераций/restart для его приёмки не нужно.
`post-renewal-health.json` и `normal-health.json` сохранены наВМ, локально raw ещё нет.
Остались сохранение backup record/health/state/evidence, импорт22профилей backend,
реальный Beget deploy worker/tunnel и worker namespace probe (submit0).
Актуальная передача — `../GPU-HANDOFF.md`, результаты — `cloud-http-handoff.json`.
Release/externalTransfer/AI gates не включены, весь MVP ещё не принят.
Admission ограничен30мин от выполнения owner-блока; точный новый deadline не передан.

Ниже справочные команды развёртывания и диагностики. На текущем boot не повторять
qualification и принятый restart-тест. После нового Linux boot нужна новая реальная
qualification; переносить bootId в record нельзя.

## 1. Локальный отбор завершён — 27 кандидатов на 15 основах

Владелец принял все четыре исправления с оговорками: f21-panel textured .60,
f07-hanging textured .65, f07-repeat textured .60, f10-directed textured .65.
У последнего завитки по-прежнему заметно переработаны; владелец это допускает.
Дополнительных локальных генераций не требуется.

Точный список содержит **27 реально проверенных GPU HTTP пар** из `service/qualification-pairs.txt`. Владелец принял 25 cloud PNG; исключены только `f07-repeat:textured` и `f25-directed:textured`. JobId, PNG SHA, metadata и evidence закреплены в `cloud-http-handoff.json`. Изображения просмотрены; слабые пары не отправлялись на новую сетку. `f08-directed:textured` не входил в qualification list; `f17-wreath:textured` и `f25-panel:textured` профилей не имеют. Все `releaseApproved` остаются false.

Новые4profileVersion=`2026-10-19.correction1-v1`, promptVersion прежний
`2026-10-19.batch23-prompts-v1`. Exact inputSHA/recipeSHA/prompt/promptSHA/profileDigest/
settings/versions — profiles.json и qualification-plan.json. Backend получит своей
правкой22новые строки из backend-profile-handoff.json; исходные6неизменны.

Ранее владелец сообщал баланс около 1400 ₽ и ставку около 86–87 ₽/ч. 27 GPU HTTP job реально выполнены; суммарные времена есть в evidence, но оплаченная продолжительность и фактическая стоимость ВМ неизвестны. Новые генерации для same-boot restart test не нужны. Не оставлять ВМ включённой без необходимости.

## 2. Перепроверить ВМ и SSH в начале согласованного окна

**Уже проверено владельцем19.10:** существующая ВМtp-sdxl-smoke-20261016 ACTIVE,
SSHlogin **ubuntu@195.209.221.75:22** успешно прошёл StrictHostKeyChecking=yes.
ED25519 fingerprint `SHA256:2uI6K/NhT8SghAVz0mgX3QBGgF1nQmV7yrqS4p2s2pk` получен
из JupyterLab-терминала этойKVMВМ и совпал при SSH. Publickey рядом сbundle в
verified-host-ed25519.pub, known_hosts вverified-known-hosts; Macкопиябезпробелов
`/tmp/tp-http-known-hosts`. Доступвладельцаесть, отдельныйtunnel-userнеподтверждён.
Для текущего окна повторно искать порт/ключ не требуется. Припересоздании/сменеIP/
hostkey ихпроверяютзаново. Ниже справочные шаги полученияключа при необходимости.

Официальные инструкции immers.cloud проверены19.10:
[Linux/SSH](https://immers.cloud/faq/view/?id=6),
[VNC-консоль](https://immers.cloud/faq/view/?id=89),
[Shelve/Unshelve и оплата](https://immers.cloud/faq/view/?id=35).
В публичном SSH-примере указан22 — это стандартный пример, не проверка нашей ВМ.
На странице ВМ открыть меню **«Действия» → VNC-консоль** после Unshelve в рабочем
окне. В shelved_offloaded гостевая ОС не исполняет команды; IP/login/сохранённые
настройки кабинета можно посмотреть без включения. Ключевая пара tatar-pattern-immers-
timfling в кабинете — клиентский ключ, а не server host key.
VNC подключается к гипервизору; по FAQ у GPU-конфигураций с эмулятором монитора
она может не работать. Если нет доступа/логина в консоль, не менять пароли/образ:
запросить поддержку immers.cloud о доверенном способе получить server host key и
внешний SSH-port. Можно проверить доступность сохранённого журнала/SSH-команды
пока ВМ архивирована; наличие таких данных в нашей карточке ещё не подтверждено.
Включать ВМ только ради поиска сейчас не нужно — совместить с подготовленным окном.

В доверенной консоли самой ВМ получить публичный ключ и fingerprint:

```bash
sudo cat /etc/ssh/ssh_host_ed25519_key.pub
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
sudo sshd -T | rg '^port '
```

Если на ВМ нет rg, последнюю команду заменить `sudo sshd -T` и найти строку port.
Публичный ключ сохранить на Mac, например `/tmp/tp-verified-host.pub`, из доверенной
консоли; это **не** приватный клиентский ключ. Сверить fingerprint файла:

```bash
ssh-keygen -lf /tmp/tp-verified-host.pub -E sha256
```

На Mac из `Разработка`, подставить фактические значения:

```bash
export TP_GPU_HOST='ТЕКУЩИЙ_IP'
export TP_GPU_PORT='ПРОВЕРЕННЫЙ_ВНЕШНИЙ_ПОРТ'
export TP_GPU_KEY='/АБСОЛЮТНЫЙ/ПУТЬ/К/ВАШЕМУ/ПРИВАТНОМУ_КЛЮЧУ'
export TP_KNOWN_HOSTS='/tmp/tp-http-known-hosts'
python3 - <<'PY'
import os
from pathlib import Path
port=int(os.environ['TP_GPU_PORT']); assert 1 <= port <= 65535
key=Path('/tmp/tp-verified-host.pub').read_text().split()
assert key[0]=='ssh-ed25519' and len(key)>=2
host=os.environ['TP_GPU_HOST']
lookup=host if port==22 else '['+host+']:'+str(port)
Path(os.environ['TP_KNOWN_HOSTS']).write_text(lookup+' '+key[0]+' '+key[1]+'\n')
PY
ssh -i "$TP_GPU_KEY" -p "$TP_GPU_PORT" -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$TP_KNOWN_HOSTS" "ubuntu@$TP_GPU_HOST"
```

При несовпадении ключа остановиться и сверить через доверенную консоль; не отключать
проверку и не принимать новый ключ вслепую. Отдельный tunnel-user ещё не подтверждён:
ubuntu — доступ владельца, Beget получает отдельно выбранного пользователя/ключ.

## 3. Перенести текущий пакет и подготовить среду

Локально подготовленный пакет: `../gpu-runtime/img2img-http-2026-10-19/tp-img2img-http.tgz`
и рядом `.sha256`. Он содержит текущий service, 15 PNG+recipe/index, server profiles,
существующую PEFT derivative, прежний base-inventory, pinned requirements, systemd
шаблон. SDXL snapshot остаётся в прежнем cache ВМ; dataset/обучение не нужны.
Финальный локальный кандидатный пакет содержит28профилей (6старых+22новых),
qualification-pairs.txt выбирает27. Число/статус/SHA конкретногоbundle — в
bundle-info.json. В текущей ВМ архив был установлен владельцем и проверен; после этого владелец отдельно передал workflow.py с SHA и запустил текущую версию. Раздел ниже — только повторное развёртывание.

На Mac в другом терминале с теми же TP_GPU_*:

```bash
scp -i "$TP_GPU_KEY" -P "$TP_GPU_PORT" -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$TP_KNOWN_HOSTS" ИИ/gpu-runtime/img2img-http-2026-10-19/tp-img2img-http.tgz ИИ/gpu-runtime/img2img-http-2026-10-19/tp-img2img-http.tgz.sha256 "ubuntu@$TP_GPU_HOST:/tmp/"
```

В SSH ВМ:

```bash
cd /tmp
sha256sum -c tp-img2img-http.tgz.sha256
sudo install -d -o ubuntu -g ubuntu /srv/tatar-lora-kit
cd /srv/tatar-lora-kit
tar -xzf /tmp/tp-img2img-http.tgz
sha256sum -c bundle-files.sha256
python3 --version
nvidia-smi
df -h .
```

Нужны Python3.11/3.12 и одна GPU, целевой запас 24GB VRAM, RAM32GB. Если прежняя
проверенная venv существует, можно использовать её через symlink `.venv`, предварительно
сверив версии. Иначе в `/srv/tatar-lora-kit` создать текущую среду:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install 'pip==25.2'
.venv/bin/python -m pip install --index-url https://download.pytorch.org/whl/cu128 'torch==2.8.0'
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
```

Эти команды установки могут обращаться к PyPI/PyTorch; inference работает с offline
assets. При отсутствии base cache восстановить прежний snapshot **той же revision**
462165984030d82259a11f4367a4eed129e94a7b из сохранённого cache/носителя. Не запускать
старые train/bootstrap/smoke/конвертацию. Если cache потерян, остановиться и отдельно
спланировать загрузку; не менять revision ради запуска.

Секрет создать без вывода на экран и передать Beget через согласованный секретный
файл/канал; приватные ключи и Bearer в чат не присылать:

```bash
umask 077
.venv/bin/python - <<'PY'
import secrets
from pathlib import Path
p=Path('service/token')
if not p.exists(): p.write_text(secrets.token_hex(32)+'\n')
p.chmod(0o600)
PY
export TP_INFERENCE_TOKEN_FILE=/srv/tatar-lora-kit/service/token
export HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 CUDA_VISIBLE_DEVICES=0 TOKENIZERS_PARALLELISM=false
```

Подготовить конфиг. В примере 90 минут — **только если владелец выбрал такое окно**;
заменить срок на согласованный. base-inventory содержит прежний snapshot_path;
если cache перенесён, исправить его на реальный путь **до qualification**.

```bash
.venv/bin/python - <<'PY'
import json,sys,time
from pathlib import Path
sys.path.insert(0,'service')
from workflow import deployment, VERSIONS
import importlib.metadata,torch
assert sys.version_info[:2] in ((3,11),(3,12))
assert all(importlib.metadata.version(k).split('+')[0]==v for k,v in VERSIONS.items())
assert torch.version.cuda=='12.8' and torch.cuda.is_available() and torch.cuda.device_count()==1
x=torch.ones((4,4),device='cuda'); assert (x@x).sum().item()==64; torch.cuda.synchronize()
root=Path.cwd()
c=json.loads((root/'service/config.example.json').read_text())
c.update(adapter_path=str(root/'model/adapter.safetensors'),base_inventory_path=str(root/'model/base-inventory.json'),assets_dir=str(root/'ai-assets'),profiles_path=str(root/'service/profiles.json'),gpu_smoke_path=str(root/'service/http-record.json'),admission_deadline_epoch=time.time()+90*60)
identity=deployment(c) # checks offline base22files/LoRA/assets/profiles SHA
(root/'service/config.json').write_text(json.dumps(c,indent=2)+'\n')
(root/'service/deployment-preflight.json').write_text(json.dumps(identity,indent=2)+'\n')
print('Deployment preflight PASS',identity['deploymentDigest'])
PY
```

Не изменять code/profiles/cache/index во время окна. При конкретной ошибке сохранить
traceback/log, состояние задачи и передать LoRA-агенту; исправляем обнаруженную причину.

## 4. GPU HTTP qualification — выполнено для 27 пар (не повторять на текущем boot)

Фактическая проверка завершена: 27 реальных job прошли auth/submit/replay/conflict/poll/download и проверку PNG/SHA/metadata; владелец принял 25 PNG. Команды ниже — справочник для нового развёртывания после изменения Linux boot или deploymentDigest. Не исполняйте их повторно для текущего record: это создаст новые inference jobs и расходы.

Терминал A, SSH ВМ, `/srv/tatar-lora-kit`, с переменными из шага3:

```bash
.venv/bin/python service/server.py --config service/config.json --state service/state --qualification-mode
```

Health всегда503 в этом режиме. Если preflight/лимит не пройдены, submit закрыт.
Терминал B в той же ВМ, Bash:

```bash
cd /srv/tatar-lora-kit
export TP_INFERENCE_TOKEN_FILE=/srv/tatar-lora-kit/service/token
mapfile -t TP_GPU_PAIRS < service/qualification-pairs.txt
[ "${#TP_GPU_PAIRS[@]}" -eq 27 ] || { echo 'Expected final27pair list'; exit 1; }
.venv/bin/python service/qualify.py --owner-run --pair "${TP_GPU_PAIRS[0]}" --output service/proof-first
```

Первая пара — f10-wreath graphic. Это одна из итоговых27, а не дополнительный smoke.
После успешного завершения скачать/посмотреть PNG и evidence: фактические load/inference/
server total/client wall time, peak VRAM, denoising steps, CLIP truncation. Убедиться,
что нетOOM/timeout и владельцу приемлем дальнейший расход в оставшемся окне. При
ошибке сохранить evidence/requestId/jobId и state/<jobId>.log, не повторять генерацию
с новым UUID вслепую. Deadline900с, render≤600с, cold load на каждой задаче.

Когда первая технически прошла и остаток бюджета позволяет, в том же терминале
выполнить оставшиеся26:

```bash
TP_GPU_ARGS=()
for TP_PAIR in "${TP_GPU_PAIRS[@]:1}"; do TP_GPU_ARGS+=(--pair "$TP_PAIR"); done
.venv/bin/python service/qualify.py --owner-run "${TP_GPU_ARGS[@]}" --output service/proof-remaining26
```

Каждая пара получает ровно одну генерацию с seed20261008. Реплей submit проверяет тот
же jobId, вторую inference не создаёт; конфликт body с тем же ключом должен дать409.
Клиент проверяет401безBearer, submit202, replay/conflict/poll/download, PNG1024²/RGB/
≤20MiB/SHA и embedded metadata. Evidence сохраняет все версии/digests/метрики и
requestId/jobId до следующего вызова. Metrics.loadSeconds измеряет загрузку модели,
server elapsed также включает проверку файлов; startup preflight измерять отдельно.

Не запускать список целиком повторно при сбое на одной паре. В evidence уже есть
completedProfiles и activeSubmission; завершённые пары сохраняются. При прерванном
пакете `--accept-reviewed --pair ...` может принять явно выбранные полностью проверенные
пары со statusRUNNING, если их checks полные и SHA неизменен. Незавершённая задача
не принимается. Не редактировать evidence/status вручную.

Скачать обе папки proof с PNG на Mac до24ч и просмотреть каждый PNG. Результат
DrawThings не гарантирует такой же вид вDiffusers. Условныеf18/f25 и изменённые
f10-directed textured смотреть особенно внимательно. Включать только конкретно
принятые владельцем cloudPNG. Новую сетку слабой паре автоматически не запускать.
Loopback здесь доказываетGPUHTTP, но не связь изBeget.

Эта команда ниже была использована только как общий пример при первой настройке. В текущем запуске владелец принял не все27, а ровно25 пар; record уже создан/загружен normal service. Не запускать пример сейчас: он без `--pair` включает все27, в том числе две визуально исключённые пары. Текущий список принятия записан в `cloud-http-handoff.json`.

Для нового Linux boot, если владелец решит повторно квалифицировать те же25 пар, нужен новый record по свежим jobs с новым bootId; передавайте `--pair` только для этих25 принятых пар из handoff.

Если владелец принял все27cloudPNG, объединить настоящее evidence:

```bash
.venv/bin/python service/qualify.py --owner-run --accept-reviewed --evidence service/proof-first/http-evidence.json --evidence service/proof-remaining26/http-evidence.json --record service/http-record.json
```

Чтобы принять лишь часть, добавить точные `--pair baseId:style`. Отсутствие `--pair`
принимает весь набор: не выполнять эту команду до просмотра/решения владельца.
Record должен быть новым файлом, deploymentDigest и Linux bootId обоих evidence
должны совпасть. Новых генераций при accept нет; ready/release по CPUтестам не включается.
Команда печатает реальную backend probe-команду с принятыми jobId. Record указан
в config.gpu_smoke_path. После этого перейти кnormalmode и проверке изworker.

## 5. Normal service активен; обязательная проверка из worker ещё впереди

Последняя owner-проверка в SSH-терминале: systemd `active`, health HTTP 200, `qualificationMode=false`, `qualified=25`, bootId `a6e2f4bf-14f4-43fd-a842-76608ce2ce5d`, deploymentDigest `51615fddf6fa09d8ad2155f432a3c79bccef9f810e996f4167000e5abe617771`. Не переустанавливайте unit на уже работающей ВМ; команды установки ниже относятся к первому развёртыванию.

Первичное переключение с foreground qualification уже выполнено владельцем; текущий unit active. Ниже — справочная установка для чистого развёртывания, на этой работающей ВМ её не повторять. При первом установочном запуске остановить foreground qualification процесс SIGTERM: в терминале A Ctrl+C (SIGINT исполняет тот же drain), дождаться возврата prompt. Установить systemd шаблон:

```bash
cd /srv/tatar-lora-kit
sed 's/REPLACE_WITH_GPU_VM_USER/ubuntu/g' tatar-inference.service.example > /tmp/tatar-inference.service
sudo install -m 0644 /tmp/tatar-inference.service /etc/systemd/system/tatar-inference.service
printf '%s\n' 'TP_INFERENCE_TOKEN_FILE=/srv/tatar-lora-kit/service/token' 'CUDA_VISIBLE_DEVICES=0' 'TOKENIZERS_PARALLELISM=false' | sudo tee /etc/tatar-inference.env >/dev/null
sudo chmod 0600 /etc/tatar-inference.env
sudo systemctl daemon-reload
sudo systemctl start tatar-inference
sudo systemctl status tatar-inference --no-pager
```

Шаблон имеет TimeoutStopSec960/KillMode=mixed/SIGTERM; home read-only, чтобы видеть
старый cache в /home/ubuntu. Текущая инструкция не включает автозапуск ВМ или аренду.
Проверить auth health через Python, без секрета в аргументах curl:

```bash
.venv/bin/python - <<'PY'
import json,urllib.request
from pathlib import Path
req=urllib.request.Request('http://127.0.0.1:8765/v1/health',headers={'Authorization':'Bearer '+Path('service/token').read_text().strip()})
with urllib.request.urlopen(req,timeout=10) as r:
 h=json.load(r); assert r.status==200 and not h['qualificationMode'];print(json.dumps(h,indent=2))
Path('service/normal-health.json').write_text(json.dumps(h,indent=2)+'\n')
PY
```

При503 смотреть `sudo journalctl -u tatar-inference -n 80 --no-pager` и сверять
record/config/deadline/digest/boot. Не подделывать record.

Передать владельцем backend/Beget блоки из GPU-HANDOFF: новые профили должны быть
синхронизированы **их агентом**. Реальный путь уже согласован:
`ai-worker → http://gpu-tunnel:18765 → SSH → GPU 127.0.0.1:8765`.
Не заменять его localhost на Beget и не открывать GPU8765 наружу.

**В уже развёрнутом ai-worker Beget** выполнить команду, напечатанную accept:
`python -m scripts.ai_gpu_probe --owner-run --worker-namespace --job-id <реальный UUID>`.
Указать все принятые jobId. Этот probe делает submit=0, проверяет health/poll/download
через фактический туннель и сохраняет `/data/storage/ai-gpu-worker-proof.json`.
Proof действует≤24ч, привязан к origin/deploymentDigest/bootId/парам. Повтор из Mac
или GPUloopback его не заменяет. Передать PNG/evidence/record/normal-health и proof
владельцу/агентам. Отдельно проверить реальный backend → PNG → история/скачивание.
Флаги releaseApproved/externalTransferApproved/AI_MVP_ENABLED меняются отдельным
явным решением владельца по принятым парам; выбор локальных кандидатов их не включает.

## 6. Same-boot restart и восстановление admission — PASS; справочные проверки

Владелец уже выполнил stop/start и последующее восстановление admission:
последний HTTP200, все6 checks=true. Повторять проверку для сдачи GPU этапа не нужно.
Блок ниже сохранён для последующей диагностики, не продлевает deadline и не делает restart.
Его прежний503 зафиксирован отдельно; успешный новый ответ — post-renewal-health.json.

```bash
cd /srv/tatar-lora-kit
.venv/bin/python - <<'PYHEALTH'
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

req = Request('http://127.0.0.1:8765/v1/health', headers={
    'Authorization': 'Bearer ' + Path('service/token').read_text().strip()})
try:
    with urlopen(req, timeout=10) as r:
        code, h = r.status, json.load(r)
except HTTPError as e:
    code, h = e.code, json.loads(e.read(65536))
qualified = [p for p in h.get('profiles', []) if p.get('qualified') is True]
checks = {
    'http200': code == 200,
    'normal': h.get('qualificationMode') is False,
    'notDraining': h.get('draining') is False,
    'qualified25': len(qualified) == 25,
    'sameBoot': h.get('bootId') == 'a6e2f4bf-14f4-43fd-a842-76608ce2ce5d',
    'sameDeployment': h.get('deploymentDigest') == '51615fddf6fa09d8ad2155f432a3c79bccef9f810e996f4167000e5abe617771',
}
result = dict(checkedAt=datetime.now(timezone.utc).isoformat(),
              httpStatus=code, qualifiedProfiles=len(qualified),
              bootId=h.get('bootId'), deploymentDigest=h.get('deploymentDigest'),
              checks=checks, passed=all(checks.values()))
Path('service/post-restart-health.json').write_text(
    json.dumps(dict(result=result, health=h), indent=2) + '\n')
if result['passed']:
    Path('service/normal-health.json').write_text(json.dumps(h, indent=2) + '\n')
print(json.dumps(result, indent=2))
raise SystemExit(0 if result['passed'] else 1)
PYHEALTH
```

Ожидается `passed=true` и все шесть checks=true. Пришлите напечатанный JSON;
секрета в нём нет. Stop/start уже принят по выводу владельца: повторять его не нужно.

Проверка с активным renderer
может быть проверена при будущем уже запланированном GPU inference: пока клиент
poll, послать SIGTERM процессу GPU, подтвердить health503/new submit503,
poll/download/replay доступны до завершения, затем exit≤915с без потери PNG. Systemd
даёт960с. Все текущие qualification jobs уже завершены; не создавать отдельную платную
задачу только для drain. Пустой same-boot systemd stop/start уже выполнен; восстановление readiness
после восстановления admission подтверждено владельцем: HTTP200/all6checks=true.
Локально проверен лишь пустой CPU-процесс; активный CUDA drain ещё NOT_RUN.

### Что потребуется для доступности после сдачи

| Событие | Действия | Новые платные генерации |
|---|---|---|
| Restart только Python/systemd; та же загрузка Linux, state, digest | Обновить admission deadline по выбранному владельцем рабочему окну, start; проверить health200; worker probe | 0, пока есть сохранённые job PNG≤24ч |
| Worker proof старше24ч, та же ВМ/boot/digest, контрольные PNG сохранены в state | Повторить реальный worker probe по принятым qualification jobId; сервер сохраняет эти job/PNG до смены record | 0 |
| State/контрольные PNG потеряны | Восстановить неизменный state из backup, проверить SHA/probe; если восстановить нечего — новый qualification | По1 на пару, если нет настоящих доступных jobs |
| Reboot/unshelve/recreate ВМ с новым Linux bootId | Новый qualification → конкретные PNG/accept → normal → worker probe; cache/профили переиспользовать, host key/IP перепроверить | По1 на каждую снова допускаемую пару |
| Изменились code/profiles/weights/assets/inventory | Новый deploymentDigest, повтор qualification/accept/worker probe | По1 на каждую допускаемую пару |
| Истёк admission deadline | Health503 и новые submit закрыты; владелец продлевает окно в config и делает restart с неизменным deployment | Само продление не требует генерации |

bootId берётся из `/proc/sys/kernel/random/boot_id`: systemctl restart его не меняет.
Произвольный перенос bootId в record запрещён. При живой ВМ record не истекает сам,
но backend worker proof≤24ч. Поэтому до истечения суток владелец/оператор повторяет
реальный probe из worker по тем же принятым jobId (генераций0). Сервер теперь сохраняет
реальные принятые qualification job/PNG/metrics до смены действующего record; обычные
результаты по-прежнему удаляет через24ч, metadata/idempotency через7дней. Это хранение
настоящего доказательства, без смены bootId/фиктивного record. Новая политика проверена
CPU-тестом очистки, фактический повтор worker probe ещё NOT_RUN. Автоматический
ежедневный probe не настроен; без оператора proof истечёт и backend закроет readiness.

Для обычной остановки после приёмки: сначала закрыть admission backend и дождаться
его worker, затем остановить tunnel по процедуре Beget, затем `sudo systemctl stop
tatar-inference`; сохранить evidence вне ВМ. После этого **владелец** останавливает/
shelve ВМ в immers.cloud и проверяет тарификацию диска/IP. SIGTERM/Python/systemd
не останавливают счёт провайдера. При остановленной ВМ AI недоступен.

## 7. Совместимость и доказательства

Целевой runtime: Python3.11/3.12, torch2.8.0/cu128, Diffusers0.35.1, PEFT0.17.1,
transformers4.56.2 и остальные VERSIONS в workflow.py/requirements.txt.
SDXLImg2Img + EulerAncestral поддерживает выбранные30/100steps. Реальный CPU-вызов
Diffusers0.35.1 подтвердил .55/30→16, .76/30→22, .70/100→70 denoising steps.
negative_prompt=None + force_zeros_for_empty_prompt=True даёт нулевые negative и
pooled embeddings. clip_skip=None выбирает hidden_states[-2]; числовой1 выбрал бы
[-3], поэтому Draw Things CLIPSkip1 не переносится числом. Prompt в обоих CLIP,
обрезание на77 tokens фиксируется в PNG metrics; long-prompt weighting DT не обещан.
Euler ancestral/RNG/VAE/CLIP/исходная база DT могут дать другое изображение.
PEFT794modules/A/B/scale1 проверяются при каждом render; существующую производную
не конвертировать заново. Текущий полный CUDA img2img всё ещё NOT_RUN.

Локальные результаты: `local-runtime-checks.json` (CPU runtime с другим Torch/Python,
не целевая CUDA-среда), `local-process-checks.json` (401/503/SIGTERM/restart без GPU),
15 CPU contract/readiness/queue/retention tests. Готовых production acceptance records нет.
Все фактические jobId/PNG SHA/VRAM/стоимость добавляются после окна владельца.
