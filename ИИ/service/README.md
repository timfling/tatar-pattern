# Собственный inference API на GPU-ВМ Selectel

**PREPARED / NOT DEPLOYED / GPU NOT TESTED**,11.10.2026.
Код запускает владелец после выбора LoRA и реального GPU smoke.
Основной контракт: `../SELECTEL-INTEGRATION.md`.

## Подготовка

1. Установить kit по START-HERE и проверить pinned модельный cache.
2. Скопировать config.example.json в собственный config.json; указать абсолютные
   adapter_path, SHA256, gpu_smoke_path и deadline рабочего окна с запасом до заморозки.
   Deadline0/просрочен дает BUDGET_EXHAUSTED при submit.
3. Smoke record `passed:true` создается только после **настоящей** успешной генерации
   и приемки: adapter_sha256, PNG SHA, workflow revision, времяUTC и измерения.
   Preflight CUDA и отрицательный HTTP test не дают passed=true.
4. Для принятого ControlNet установить alpha silhouette в allowlist templates.
   Произвольные URL/paths от пользователя не принимаются.
5. Задать TP_INFERENCE_TOKEN≥32символа через protected env, не в чат/фронтенд.
   При ручном запуске в активном GPU-окне:

```bash
source .venv/bin/activate
export HF_HOME="$PWD/selectel/model-cache"
export HF_HUB_OFFLINE=1
python service/server.py --config service/config.json --state service/state --port 8765
```

Для daemon есть `selectel/tatar-inference.service.example`; установка владельцем
после редактирования user/paths и создания env/config с корректными правами.
API слушает только127.0.0.1. Beget подключается по SSH-туннелю; template и вопросы
Docker-сети — SELECTEL-HANDOFF.md. Beget не входит в приватную сеть Selectel.

## Поведение и ограничения

- SQLite queue и UUID Idempotency-Key+hash тела, тот же key/body→тот же job ID,
  другой body→409; один render subprocess, очередь≤20, timeout задачи600сек,
  общий deadline15мин. После restart running→INFERENCE_INTERRUPTED;
  queued возобновляются только если readiness подтверждена.
- **Модель загружается заново в каждой задаче.** Пилотный вариант сохраняет hard timeout,
  но платит временем cold start. Persistent systemd не делает модель резидентной.
  Измерение на Selectel и дальнейший постоянный GPU worker нужны перед публичной нагрузкой.
- Readiness проверяет CUDA, adapter SHA и предыдущий реальный smoke;
  загрузку базы/ControlNet он не проверяет до render. Сбой дает честную ошибку.
- state0700, prompts/tokens не пишутся web access log; входы/PNG/технические логи
  удаляются через24ч **после завершения задачи**, не скачивания; metadata7д.
  Provider logs/backups/удаление дисков Selectel отдельно неизвестны.
- Admission deadline/остановка Python/systemd не прекращают оплату Selectel.
  Владелец сохраняет результаты, выполняет подтвержденную заморозку/удаление
  и проверяет вычислительную и остаточную дисковую/IP плату.

Локальная проверка: `python3 service/check_local.py`, только отрицательные HTTP без GPU.
Облачный endpoint, GPU/Canny/LoRA/перезапуск/идемпотентность не проверены.
