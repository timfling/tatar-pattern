# Актуальность 17.10.2026 — HTTP после адаптации img2img

Предварительный cloud inference уже успешен. Следующий технический этап ниже актуален
**после принятия локального MVP-пилота и адаптации сервиса под выбранную основу**.
Старый matrix-01 не заменяет проверку нового workflow/readiness. Поля/команды ниже —
заготовка; точный актуальный протокол фиксируется после реализации.
[MVP-план](../../../COMPOSITION-AI-PLAN-2026-10-17.md).

---

# Следующий этап: отдельный HTTP/API smoke

**NOT_RUN / DEPENDS_ON_GPU_INFERENCE_AND_SERVER_PORT.** Не входит в первый GPU smoke.
Клиент `http_smoke.py` подготовлен по GPU-INTEGRATION/HANDOFF и Provider Protocol
backend (submit/poll/download). Он не обращается к API управления immers.cloud.

## Что должно появиться до запуска

1. Успешный inference run и `verify_results.py` с TECHNICAL_CHECKS_PASS.
2. Отдельно подготовленный экспериментальный HTTP-сервис на127.0.0.1:8765,
   с тем же **производным SHA**, базой и записанным workflow. Сервис должен использовать
   проверенный native PEFT adapter metadata и фактический renderer, а не только считать
   файл присутствующим. Не помечать старый smoke record `passed:true` вручную.
3. Импорт smoke в readiness сервиса, immutable workflow/model IDs и time budget.
   Это работа следующего этапа: старый server ждёт другой формат smoke/selected workflow,
   разрешает loraScale только0/.5/.6/.8; старый renderer имеет EulerDiscrete/иной negative
   и не поддерживает img2img. Непосредственно запускать его как якобы проверенный новый
   workflow нельзя. Нужны отдельный port/версия и проверки до интеграции с сайтом.
4. Bearer≥32символа в защищённой переменной TP_INFERENCE_TOKEN на клиенте и сервисе.
   Не помещать его в frontend, CLI-аргумент, request.json, summary или переписку.
5. Для удалённого клиента — проверенный SSH host key и туннель, без публичного GPU-порта:

```bash
ssh -N -L 8765:127.0.0.1:8765 "$TP_GPU_USER@$TP_GPU_HOST"
```

Первую проверку проще выполнить на самой ВМ. Команда **только после пунктов выше**,
из каталога kit, в его venv, при уже заданном TP_INFERENCE_TOKEN:

```bash
python http_smoke.py --owner-run --inference-run runtime/matrix-01 --base-url http://127.0.0.1:8765 --workflow-version YOUR_TEST_WORKFLOW_VERSION --output runtime/http-01
```

Клиент заново проверяет сохранённые inference PNG и off/on. Проверяет unauthenticated401,
authenticated ready/versions/queue0; unsupported scenario422; сохраняет UUID и тело
до submit; создаёт **одну** задачу motif/textured/scale1; повторяет тот же key/body только
после202, ожидает тот же jobId; конфликт body с тем же key→409; poll до15мин; download
≤20MiB с MIME/SHA/размерами. Результат HTTP_SMOKE_PASS_REVIEW_REQUIRED сохраняется
в http.json, PNG и job.json. Токен не сохраняется. Redirect/proxy отключены.

На сетевой ошибке submit нет автоматического повторного создания задачи. Сохранены
request.json и ключ; сначала выяснить судьбу исходной задачи на сервере. Окончание
клиента/timeout не отменяет GPU-задачу. Не повторять клиент вслепую новым UUID.

После этого отдельно проверить сохранность idempotency при restart сервиса,
running→INFERENCE_INTERRUPTED, queued continuation,503 без готовности и после deadline,
409 до готовности image,404 неизвестного UUID, лимит очереди429 (контролируемым тестом,
без создания десятков платных GPU-задач), срок хранения24ч/7д и безопасную загрузку
с backend через согласованный tunnel namespace. Эти проверки клиент выше не выполняет.
HTTP smoke не принимает визуальное качество, img2img API, alpha/швы/культурную корректность
и не включает публичную AI-функцию сайта.
