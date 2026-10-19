# Актуальность 17.10.2026 — технический справочник выполненного smoke

**Реальный cloud inference выполнен успешно.** Инструкции ниже сохранены как справочник
совместимости/конвертации/среды; PREPARED/NOT_RUN относятся к первоначальной подготовке.
Не повторять конвертацию и матрицу автоматически. Исторический разбор:
[SMOKE-REVIEW](../../../archive/2026-10-17__gpu-runtime__immers-smoke-2026-10-17__SMOKE-REVIEW.md).
MVP-план: [композиционные основы](../../../COMPOSITION-AI-PLAN-2026-10-17.md).
После локального пилота переносим принятый рецепт и отдельно проверяем HTTP.
Скрипты этого пакета не считаются готовой реализацией нового сценария.

---

# immers.cloud: короткий SDXL + LoRA smoke

16.10.2026. **PREPARED; GPU / cloud / HTTP NOT_RUN.** Это отдельный экспериментальный пакет.
Все действия в immers.cloud, перенос и платные запуски выполняет владелец.
Обучение не требуется. Кандидат остаётся experimental; импорт, inference и качество — разные проверки.

## 1. Что обнаружено до аренды

Оригинал доступен локально, 245910997 байт:

```text
ИИ/draw-things/safetensor/full text+flat/tp_dualstyle_dt_full_r16_v1_1600_lora_f32.safetensors
SHA256 600293069a789ed8d8e1ff0b22b6d1dc301a75543fca4714102829224b622457
```

**Оригинал напрямую несовместим с SDXL loader Diffusers 0.35.1.** Реальный CPU-вызов
`StableDiffusionXLPipeline.lora_state_dict(..., unet_config=...)` остановился:
`Checkpoint not supported because layer lora_unet_label_emb_0_0.lora_up.weight not supported.`
Это ограничение конвертера SGM, а не доказательство повреждения экспорта.
Помимо имён специальных слоёв, у 56 пар требуется восстановить/снять только хвостовые
размерности 1×1 свёрточных факторов. 724 модуля rank/alpha16 и 70 rank/alpha32.
Если в native PEFT файле потерять alpha_pattern, rank32 получит scale0.5 вместо1.

Минимальное предлагаемое исправление в `compatibility.py`:

1. Сопоставить все SGM-имена с **реальными модулями UNet выбранной SDXL revision**.
2. Проверить формы и конечность значений, изменить только singleton-размерности.
3. Сохранить PEFT A/B, rank_pattern и alpha_pattern в metadata нового safetensors.
   Не сливать с базой, не отбрасывать нулевые модули, не менять значения/порядок чисел.
4. Проверить все загруженные A/B и scale каждого модуля. Только затем записать новую
   копию **по явной команде** `--write-converted ... --acknowledge-format-change`.

Локальный dry audit: `local-compatibility.json`. Все794 модуля /1588 A/B сопоставлены,
значения и alpha/rank=1 проверены через поддерживаемый `load_lora_into_unet`.
База при этой CPU-проверке — формы и компактные placeholder-тензоры, без реальных весов
и forward pass. Реальная LoRA проверялась только в памяти, производный файл не записан.
Тест синтетического файла проверил путь `load_lora_weights` с metadata, mixed rank и Conv2d.
Местная среда: Python3.14 / torch2.11.0.dev20260124, Diffusers0.35.1 / PEFT0.17.1.
Это **не проверка закреплённого GPU-окружения**. Повтор CPU-аудита на ВМ обязателен.

## 2. Ресурс и зависимости

Предварительный выбор: **одна RTX4090 или RTX3090, 24GB VRAM, 8vCPU, 32GB RAM,
80–160GB свободного SSD**. Это оценка, не гарантия; объём cache/venv/временных файлов
проверьте через `df -h`. На16GB этот workflow без offload может получить OOM.
Пакет рассчитан на один видимый GPU, batch1,1024×1024,fp16, без refiner/ControlNet,
без xformers/torch.compile/CPU offload. Если24GB не хватит, сначала сохранить ошибку
и остановиться; новый режим памяти оформляется отдельным измеряемым рецептом.

Нужна Ubuntu с рабочим NVIDIA driver и Python3.11/3.12 + venv.
Удобный чистый образ: Ubuntu24.04/Python3.12, драйвер — из GPU-образа провайдера.
Системный CUDA toolkit устанавливать не требуется: wheel torch содержит runtime12.8.
Драйвер обязан поддерживать этот runtime; проверка — реальная CUDA-операция bootstrap.
Строка CUDA в `nvidia-smi` сама по себе не доказывает работоспособность PyTorch.
Если драйвер не подходит, выберите подходящий образ с поддержкой провайдера;
скрипт драйвер не обновляет.

Сохранены прежние версии проекта: torch2.8.0/cu128, Diffusers0.35.1,
transformers4.56.2, accelerate1.10.1, PEFT0.17.1, safetensors0.6.2,
HF hub0.34.4, Pillow11.3.0, numpy2.2.6, ftfy6.3.1.
Из старого training requirements исключены torchvision/datasets/tensorboard/Jinja2/OpenCV:
этот пакет не обучает, не использует Canny и не импортирует их. Версии оставленных
пакетов не изменены. Не запускайте старый `scripts/gpu/bootstrap.sh`: он ссылается
на архивированный pilot launcher и не является этим комплектом.

База: `stabilityai/stable-diffusion-xl-base-1.0`, revision
`462165984030d82259a11f4367a4eed129e94a7b`, fp16 Diffusers snapshot, без refiner.
Это уже закреплённая в проекте облачная revision, точный локальный Draw Things base SHA
не установлен. Нужен сетевой доступ к Hugging Face/PyTorch/PyPI. При401/403 владелец
сам проверяет доступ/лицензию в HF; секреты не вставлять в команды/логи/чат.
Условия SDXL сохранены в передаваемом `sdxl-license.md`.

Оценка времени RTX4090/3090: настройка/скачивание10–40мин, CPU audit1–5мин,
холодная загрузка30–180с; text2img30steps примерно10–90с/PNG,
img2img13steps примерно5–60с/PNG. Матрица с загрузкой ориентировочно3–15мин;
на всё первое окно разумно заложить45–90мин. Скорость сети/диска/конкретной GPU
может сильно изменить время. Ставки и наличие immers.cloud в этой задаче не проверялись.
До создания ВМ проверьте полную цену GPU, диска, IP и условия остановки, задайте свой
лимит времени/денег и таймер на телефоне.

## 3. Что перенести вручную

| Обязательно | Куда на ВМ |
|---|---|
| Каталог `ИИ/scripts/gpu/sdxl_smoke/` без `.venv`, `__pycache__`, runtime | `~/tp-smoke/kit/` |
| Оригинальная LoRA по пути из §1 | `~/tp-smoke/input/` |
| `ИИ/draw-things/composition-test/constructor-medallion-reference.png` | `~/tp-smoke/input/` |
| `ИИ/archive/2026-10-15-cloud-training/research/sdxl-license.md` | `~/tp-smoke/input/` |

У референса SHA256 `537b1799a352dc104d62cbebb19c47337b5f0977dbbe29b52bf8222977de37b5`,
213673байт, RGB1024×1024. Базовую модель владелец скачивает на ВМ отдельной командой.
Train/validation dataset, исходные CSV, старый owner-upload.zip для smoke не нужны.
Локальные E/F/G PNG уже есть в `ИИ/draw-things/results/composition-next/` и остаются
локально для визуального сравнения; переносить их на GPU не требуется.

Пример команд **на своём Mac из корня проекта**. Подставьте свой SSH-логин и адрес,
сверьте host key с доверенными данными провайдера при первом SSH-соединении.
Не отключайте проверку host key.

```bash
TP_GPU_USER=ubuntu
TP_GPU_HOST=YOUR_SERVER_IP
ssh "$TP_GPU_USER@$TP_GPU_HOST" 'mkdir -p ~/tp-smoke/input'
COPYFILE_DISABLE=1 tar --exclude=.venv --exclude=__pycache__ --exclude=runtime -czf /tmp/tp-sdxl-smoke-kit.tgz -C ИИ/scripts/gpu/sdxl_smoke .
scp /tmp/tp-sdxl-smoke-kit.tgz "$TP_GPU_USER@$TP_GPU_HOST:~/tp-smoke/"
scp 'ИИ/draw-things/safetensor/full text+flat/tp_dualstyle_dt_full_r16_v1_1600_lora_f32.safetensors' "$TP_GPU_USER@$TP_GPU_HOST:~/tp-smoke/input/"
scp ИИ/draw-things/composition-test/constructor-medallion-reference.png "$TP_GPU_USER@$TP_GPU_HOST:~/tp-smoke/input/"
scp ИИ/archive/2026-10-15-cloud-training/research/sdxl-license.md "$TP_GPU_USER@$TP_GPU_HOST:~/tp-smoke/input/"
ssh "$TP_GPU_USER@$TP_GPU_HOST"
```

## 4. Установка и явная подготовка исправленной копии

Далее команды **в SSH на ВМ**. При любой ошибке остановитесь и сохраните вывод.
Если на чистой Ubuntu24.04 нет venv: `sudo apt-get update`, затем
`sudo apt-get install python3-venv`. Python3 должен быть3.11/3.12.

```bash
mkdir -p ~/tp-smoke/kit
tar -xzf ~/tp-smoke/tp-sdxl-smoke-kit.tgz -C ~/tp-smoke/kit
cd ~/tp-smoke/kit
sha256sum -c kit-sha256.txt
sha256sum ../input/*.safetensors ../input/constructor-medallion-reference.png
bash bootstrap.sh --owner-run
source .venv/bin/activate
export CUDA_VISIBLE_DEVICES=0
export HF_HOME="$PWD/runtime/hf-cache"
export HF_HUB_DISABLE_TELEMETRY=1
export DO_NOT_TRACK=1
export TOKENIZERS_PARALLELISM=false
python -m unittest discover -s . -p test_cpu.py -v
python compatibility.py --lora ../input/tp_dualstyle_dt_full_r16_v1_1600_lora_f32.safetensors --report runtime/compat-dry.json
```

Ожидается `CPU_COMPATIBILITY_PASS_CONVERSION_REQUIRED`, original_loader=INCOMPATIBLE,
proposed_state_loader=PASS_ALL_VALUES_AND_MODULES, attached_modules=794.
В этой команде **производный файл ещё не создаётся**.

Если принимаете описанное выше исправление формата, выполните явную команду:

```bash
python compatibility.py --lora ../input/tp_dualstyle_dt_full_r16_v1_1600_lora_f32.safetensors --report runtime/compat-converted.json --write-converted runtime/tp_dualstyle_diffusers_peft.safetensors --acknowledge-format-change
sha256sum ../input/tp_dualstyle_dt_full_r16_v1_1600_lora_f32.safetensors runtime/tp_dualstyle_diffusers_peft.safetensors
python fetch_base.py --owner-run --output runtime/base-inventory.json
export HF_HUB_OFFLINE=1
```

Оригинальный SHA должен остаться прежним. Новый SHA фиксируется в compat-converted.json;
его не подменять исходным SHA. Команда не перезаписывает существующий результат.
CPU audit не требует CUDA, но полноценные базовые веса нужны следующему inference.
Если файлы результатов уже существуют, используйте новые имена/каталоги — не стирайте
предыдущие доказательства ошибки/успеха вслепую.

## 5. Сначала пара, затем E/F/G и матрица

```bash
set -o pipefail
timeout --signal=INT --kill-after=30s 15m python -u run.py --owner-run --lora runtime/tp_dualstyle_diffusers_peft.safetensors --compat-report runtime/compat-converted.json --reference ../input/constructor-medallion-reference.png --base-inventory runtime/base-inventory.json --suite pair --output runtime/pair-01 2>&1 | tee runtime/pair-01-console.log
python verify_results.py runtime/pair-01
```

Это F/E: исходный медальон, textured prompt, без/с LoRA. Посмотрите оба PNG.
Если загрузка не удалась, PNG чёрный, off/on побитово одинаковы или есть OOM —
не запускайте остальные серии. Сохраните logs/run.json и завершите платное окно.
Если техническая пара прошла, можно выполнить **один** из вариантов ниже.
Матрица уже включает E/F/G, повтор отдельного E/F/G необязателен.

Отдельное воспроизведение E/F/G (3PNG):

```bash
timeout --signal=INT --kill-after=30s 15m python -u run.py --owner-run --lora runtime/tp_dualstyle_diffusers_peft.safetensors --compat-report runtime/compat-converted.json --reference ../input/constructor-medallion-reference.png --base-inventory runtime/base-inventory.json --suite efg --output runtime/efg-01 2>&1 | tee runtime/efg-01-console.log
python verify_results.py runtime/efg-01
```

Полная матрица text2img/img2img × flat/textured × off/on (8PNG):

```bash
timeout --signal=INT --kill-after=30s 20m python -u run.py --owner-run --lora runtime/tp_dualstyle_diffusers_peft.safetensors --compat-report runtime/compat-converted.json --reference ../input/constructor-medallion-reference.png --base-inventory runtime/base-inventory.json --suite matrix --output runtime/matrix-01 2>&1 | tee runtime/matrix-01-console.log
python verify_results.py runtime/matrix-01
```

timeout ограничивает процесс, **не аренду и счёт**. По завершении серии сохраните:

```bash
python -m pip freeze > runtime/pip-freeze-final.txt
nvidia-smi > runtime/nvidia-smi-final.txt
du -sh runtime
tar -czf ../tp-smoke-results.tgz --exclude=hf-cache -C runtime .
```

Включены журналы и исправленная копия LoRA; cache SDXL исключён. На Mac, в новом окне
Terminal, из корня проекта с теми же TP_GPU_USER/TP_GPU_HOST:

```bash
mkdir -p ИИ/gpu-runtime/immers-smoke-2026-10-16
scp "$TP_GPU_USER@$TP_GPU_HOST:~/tp-smoke/tp-smoke-results.tgz" ИИ/gpu-runtime/immers-smoke-2026-10-16/
tar -xzf ИИ/gpu-runtime/immers-smoke-2026-10-16/tp-smoke-results.tgz -C ИИ/gpu-runtime/immers-smoke-2026-10-16
```

Проверьте, что архив распакован, PNG открываются, run.json/logs и оба SHA сохранены.
При повторном платном окне используйте новый каталог. `snapshot_path` в inventory
ссылается на ВМ; после скачивания для просмотра PNG он не нужен.

## 6. Что записывается и как оценивать

`run.json`: версии/Python/драйвер/GPU, base inventory с revision и SHA файлов,
SHA source/converted/reference, параметры каждого изображения, seed, scheduler config,
активный adapter, покрытие794модулей, token IDs/возможное усечение prompt,
реальные timesteps/число denoising шагов, время загрузки и inference, ошибки.
PNG содержат параметры в текстовом поле `tp_smoke`; SHA файлов и пикселей — в run.json.
Console log сохраняет предупреждения библиотек и traceback, в том числе ошибки до импорта torch.

VRAM: после CUDA synchronize/reset_peak_memory_stats сохраняются `max_memory_allocated`
и `max_memory_reserved` отдельно для загрузки и каждого изображения. Это пики CUDA
allocator **этого процесса**, не вся занятая память платы; контекст CUDA/другие процессы
сюда полностью не входят. Показания не называть полной аппаратной пиковой VRAM.
Время загрузки включает SDXL/LoRA/перенос CUDA; inference — encode/denoise/decode без
сохраненияPNG. Общая wall duration включает проверки и SHA; скачивание отдельно.

Признаки технического успеха:

- CUDA preflight прошёл, все794модуля активируются, tensor values и alpha/rank проверены.
- 2/3/8 читаемых RGB PNG1024×1024, сохранены timings/VRAM, нет failed cases.
- `verify_results.py` → TECHNICAL_CHECKS_PASS; off/on имеют одинаковые параметры
  и timesteps, но разные пиксели. Это показывает изменение результата, не качество.
- Для подтверждения повторяемости можно повторить **ту же** suite в новом каталоге
  на той же ВМ и сравнить pixel_sha256. Одинаковый seed между иными GPU/движками/
  версиями не гарантирует побитового совпадения.

| Ошибка | Что сделать |
|---|---|
| Original loader INCOMPATIBLE на SGM | Ожидаемая причина явного исправления; не подавлять исключение и не отправлять оригинал в runtime loader |
| SHA mismatch | Остановиться, сверить файл/завершённость переноса; не переписать ожидаемый SHA под случайный файл |
| Unknown target/shape/alpha mismatch | Сохранить audit и остановиться; конвертер не отбрасывает такие ключи |
| Missing/unexpected LoRA keys, module coverage/scale mismatch | Остановиться; даже появившийся PNG не подтверждает корректный импорт |
| Нет text_encoder LoRA keys | Ожидаемо только для UNet-only экспорта; не игнорировать остальные warnings |
| CUDA unavailable/unsupported architecture | Проверить NVIDIA image/драйвер/GPU; не менять закреплённый torch наугад |
| CUDA out of memory | Не запускать серию повторно; сохранить лог, завершить окно, обсудить отдельный memory recipe |
| HF401/403/сеть/нет fp16 файлов | Проверить доступ/диск/revision; не заменять базу молча |
| Чёрный/одноцветный PNG, NaN warning | Ошибка численной стабильности; не принимать как успешный inference |
| Off/on одинаковые пиксели | Эффект не установлен, сверить activation/scales/logs; не считать качество доказанным |
| PNG разные, но узор хуже/фактуры нет | Совместимость может работать, полезный эффект/качество не принято |

После технического PASS вручную оцените: сохранение схемы, число и роли частей,
контуры/поля, полезность текстуры E против F и различие E против G. Успешный импорт
не подтверждает качество, успешный inference не подтверждает готовность AI сайта.

## 7. E/F/G и различия Draw Things

| Draw Things | Здесь |
|---|---|
| E textured + LoRA1 | `img2img_textured_on.png` |
| F тот же textured без LoRA | `img2img_textured_off.png` |
| G flat + LoRA1 | `img2img_flat_on.png` |

Точные полные composition prompts перенесены из EFG-IMG2IMG.md в common.py;
у E/F остаётся tptrx, E/G отличаются только стилевой фразой. Перед каждой генерацией
берётся копия **оригинального** медальона с проверенным SHA, никогда предыдущий выход.
Везде seed20261008/CFG5/30steps/1024×1024/strength0.45/Control off/LoRA1.

Различия зафиксированы и не исправляются перебором:

- EulerAncestralDiscreteScheduler ближе по классу к локальному EulerA, чем старый
  EulerDiscreteScheduler из service. Реализации noise/sigmas/seed отличаются.
- Diffusers при30×0.45 обрезает до13 denoising шагов; локальные E/F/G metadata
  содержат16 sampling timings. Поэтому Strength45% не обещает одинакового denoising.
- Zero Negative приближён `negative_prompt=None` + `force_zeros_for_empty_prompt=True`:
  нулевые negative text embeddings. Это не encoded empty string и не старый непустой
  negative из service. SDXL negative size conditioning остаётся отдельным условием;
  здесь1024×1024/crop0 по умолчанию, в локальных metadata negative original512×512.
- Локальный CLIP Skip1 не переносится числом1. Здесь `clip_skip=None` — штатное
  SDXL penultimate conditioning обоих энкодеров; эквивалентность движкам не доказана.
- SDXL Base revision закреплена отдельно от неизвестного exact Draw Things base SHA.
  Scale Alike, VAE sampling, fp16/Metal/CUDA и токенизация отличаются. Token truncation
  в Diffusers записывается явно; полный prompt сохраняется даже при усечении.
- Refiner/upscale/HiRes/ControlNet отсутствуют; watermark отключён в cloud workflow.
  Тонкая круговая направляющая входа — современная добавка конструктора, не доказанный
  исторический стебель. Результаты не сравниваются побитово между движками.

Text2img использует короткий prompt одного синего цветка, img2img — точный E/F/G
composition prompt. Сравнение off/on корректно внутри каждой пары; это не сравнение
разницы text2img/img2img при одинаковом prompt.

## 8. Остановка и следующий шаг простыми словами

1. Дождитесь конца процесса. Если завис — Ctrl+C; timeout/kill не возвращают деньги
   автоматически. При SIGKILL run.json может остаться RUNNING, это незавершённый запуск.
2. Скачайте результаты, убедитесь, что они открываются. Не удаляйте единственный экземпляр.
3. В кабинете immers.cloud завершите платный GPU-ресурс способом, для которого провайдер
   подтверждает остановку начислений. Обычный Stop/выход из SSH этого не доказывает.
4. Проверьте статус и текущую оплату GPU/диска/IP. Shelve используйте только после
   подтверждения его условий; если нужно удаление, сначала проверьте сохранённый архив.
5. Передайте для разбора PNG, run.json, verification.json, compat-converted.json,
   console logs, preflight/pip freeze и фактическую конфигурацию. Секреты не прикладывайте.

Отдельный следующий этап — [HTTP-NEXT.md](HTTP-NEXT.md). В этой задаче текущие
service/server.py, renderer, сайт, публичный API и production-конфигурация не меняются.
