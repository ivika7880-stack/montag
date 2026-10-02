<!-- AUTO-GENERATED from CLAUDE.md by sync-agents-md.js — правь CLAUDE.md, не этот файл -->

# Montage — пайплайн автомонтажа видео

## Старт (первым делом при открытии проекта)
1. Прочитай скилл **`montage-pipeline`** (`.claude/skills/montage-pipeline/`) — оркестратор всего пайплайна.
2. Покажи пользователю краткое содержание из **`README.md`** и пять путей старта:
   новый стиль → скилл **`brand-intake`**; видео с нуля (ещё не снято) → скилл **`script-gen`** (сценарий + план вставок); есть клип для монтажа → Stage 1 в `montage-pipeline`; только шортсы из клипа → shorts-only маршрут (Stage 1-lite: прокси + транскрипт + faces, без delete/edl/review → сразу Stage 2; shorts.py без edl.json берёт 30 fps); ремейк чужого шортса → Stage 2R (download.py по ссылке → reference.py разбирает референс на автора/визуал, пользователь записывает себя, сборка = он + чужой визуал по якорям).
3. Веди по стадиям из `montage-pipeline`, останавливаясь на воротах: сценарий (если был), `REVIEW.md`, брак сгенерённых картинок (`broll-gen`) и финальный рендер.
Ничего не рендерить и не пушить без явной команды пользователя.

## Что это
Автоматический монтаж «говорящей головы»: Python анализирует видео (транскрипт, дубли, лицо), Claude размечает вырезки и акценты, Remotion рендерит финал одним проходом (jump-cut, зумы на лицо, акцентные слова с эффектом печати). Стек: Python 3.11 (.venv) + Remotion 4 (Node 22) + FFmpeg + Deepgram API. Проект мультивидео: несколько роликов = несколько композиций Main169* с отдельными пропсами.

## Первый запуск
Новый пользователь / новый бренд — сначала скилл **`brand-intake`**: опрашивает по бренду, шрифтам, эффектам (визуальным Remotion), звуковым эффектам, стилю монтажа, вставкам и генерации изображений (`imagegen`: провайдер / референсы стиля / оживление), пишет `brand.config.json`. Сценарий до съёмки — скилл **`script-gen`** (Stage 0.5): `work/<id>/script.md` с маркерами вставок. Фабрика картинок — скилл **`broll-gen`** (Stage 1.5): промты → генерация (провайдер из `brand.config.json`, референсы из `assets/style-refs/`) → `public/inserts/<id>/` + `inserts.json` → опционально оживление (motion-промты + подхват mp4 c delogo и all-intra прокси).

## Карта
- `pipeline/` — Python-скрипты анализа (transcribe → indexed → edl → review → faces → props → audio). Шортсы: shorts.py (work/<id>/shorts.json → props/<id>.json + audio.py на шорт; `media` в shorts.json = имя записи в public, default source; вставки с `layout`: third/half/full). Ремейк: download.py (референс по ссылке YT/TT/IG: ScrapeCreators → фолбэк Apify) + reference.py (разбор чужого шортса: mediapipe 0.25с + сцены → сегменты автор/визуал → public/inserts/<id>/ref_NN.mp4 + work/<id>/ref.json + ref_plan.md + миниатюры ref/thumb_NN.jpg; вшитые субтитры референса метятся по миниатюрам → `coverBox` вставки, закрывается блюр-плитой под караоке автора)
- `remotion/` — Node-проект Remotion; `src/Main169.tsx` (16:9), `src/Shorts916.tsx` (9:16 вертикаль, кроп на лицо + караоке-субтитры), `src/Root.tsx` — регистрация. Пропсы генерятся пайплайном; в репо лежат `props/*.example.json` для запуска Studio из коробки. Новое видео = новый `main169_*.json` + своя `<Composition>` в Root.tsx (id без `_`); b-roll видео — в подпапку `public/inserts/<id>/`, в `inserts.json` путь `<id>/файл`
- `remotion/public/` — сюда кладёшь `source.mp4` (прокси исходника) + опц. `source_preview.mp4` (all-intra превью), declick-дорожку, шрифт, key.wav (звук клавиши). Все `*.wav`/прокси — в .gitignore
- `work/<id>/` — артефакты по каждому видео (в git не попадают): script.md (если видео с нуля), words.json, delete.json, edl.json, faces.json, accents.json, REVIEW.md, inserts_prompts.md + animate_prompts.md (от broll-gen), animate/ (mp4 от пользователя на подхват), ref.json + ref_plan.md + ref/ (разбор референса при ремейке), publish.md. `work/shorts-scripts/` — сценарии шортсов до записи
- `assets/` — fonts/, music/, sfx/, style-refs/ (2–4 эталонных картинки — референсы стиля для генерации b-roll)
- `docs/` — brandbook.md (шаблон стиля — задай свой через brand-intake), PIPELINE.md, REMOTION.md
- `tests/` — смоук-тесты (без сети): `python tests\test_download.py`
- `out/` — финальные рендеры (в git не попадают)
- `.env` — DEEPGRAM_API_KEY; для ремейка по ссылке — SCRAPECREATORS_API_KEY, APIFY_TOKEN (не коммитится)

## Команды
```powershell
# весь анализ (venv-python), подробности в docs/PIPELINE.md
.venv\Scripts\python.exe pipeline\<script>.py ...

# Remotion (из ./remotion)
npx remotion studio                      # превью — ТОЛЬКО так
npx tsc --noEmit                         # typecheck
npx remotion compositions src/index.ts   # проверить регистрацию
# пропсы: 3-й арг = базовое имя медиа в public (source по умолчанию):
.venv\Scripts\python.exe pipeline\props.py work\<id> remotion\props\main169.json source
# declick-дорожка спикера (после props.py; перезапускать после любой правки монтажа):
.venv\Scripts\python.exe pipeline\audio.py remotion\props\main169.json   # src берётся из пропсов
# шортсы: отбор в work\<id>\shorts.json → пропсы → declick-дорожка на каждый:
.venv\Scripts\python.exe pipeline\shorts.py work\<id> remotion\props   # + shorts.py ... draft для вычитки
.venv\Scripts\python.exe pipeline\audio.py remotion\props\<id>.json     # на каждый шорт
# ремейк: скачать референс-шортс по ссылке (дальше reference.py):
.venv\Scripts\python.exe pipeline\download.py "<url>" work\<id>
# финал — только по явной команде пользователя:
npx remotion render src/index.ts Main169 ../out/main169.mp4 --props=props/main169.json --image-format=png --crf=14 --x264-preset=slow
```

## Публикация (после рендера)
Финальная стадия — скилл **`publish-pack`**: из готового `work/<id>/transcript.txt` (повторно НЕ транскрибируем) пишет `work/<id>/publish.md` — описание для YouTube в стиле автора, таймкоды, теги с `#`, теги через запятую и короткий ТГ-пост.

## Правила
- **Превью НЕ рендерить файлом** — смотреть в Remotion Studio. Финальный рендер только по явной команде.
- **ProRes не делать. Звук не обрабатывать** (нормализация/шумодав запрещены; в прокси `-c:a copy`). Исключение: 6-мс гейт + дещелчок на краях склеек — это устранение артефакта монтажа, не обработка голоса.
- **Звук спикера = declick-дорожка**, не звук из `<Video>`: audio.py режет аудио источника по сегментам (48000/30 = 1600 сэмплов/кадр ровно), на каждом стыке жёсткий гейт 6 мс (края в 0) + 6-мс косинус-дещелчок → один WAV; Main169 глушит `<Video>` (`muted={audioTrack!=null}`) и играет `<Audio audioTrack>`. Покадровая `volume`-функция для дещелчка НЕ годится: `@remotion/media` квантует громкость по кадрам (33 мс при 30fps).
- Версии-пины: TypeScript 5.9.3 (7.x ломает Remotion), zod 4.3.6, mediapipe 0.10.21 (новее — нет `.solutions`).
- `@remotion/media`: `<Video>` И `<Audio>` тримы (`trimBefore`/`trimAfter`) — в КАДРАХ, не секундах (секунды у `<Video>` → чёрный экран).
- Remotion `id` композиции: только `a-z A-Z 0-9 - CJK`, **без `_`** (дефис — ок). Шортсы: id `Short-*`.
- Шортсы (Shorts916): кроп 16:9→9:16 через `<Video>` шириной 3413px (заполняет высоту 1920) + `translateX(tx)` на центр лица (tx из shorts.py по faces.json). Субтитры — караоке капсом, акцентное слово акцентным цветом + панч-зум. Текст субтитров вычищается вручную (fixes в shorts.json), т.к. Deepgram врёт числа/слова.
- Исходники HEVC → обязательно прокси all-intra H.264 (`-crf 15 -g 1 -bf 0 -c:a copy`) в remotion/public.
- Композиция всегда равна целевому разрешению (1920×1080 / 1080×1920) — иначе мыло.
- Правка монтажа = правка `work/<id>/delete.json` → edl.py → props.py → **audio.py** (не руками в edl.json). audio.py зависит от сегментов — перезапускать после каждой правочной цепочки, иначе дорожка рассинхронится.
- Deepgram filler_words не работает для русского — паразиты/дубли размечает Claude в delete.json.
- Стиль текста в кадре — по `docs/brandbook.md` (задай свой бренд через `brand-intake` → `brand.config.json`).
- PowerShell 5.1: без `&&`. Пути с пробелами/кириллицей — в кавычках.

## Детали
- Пайплайн анализа, форматы JSON, пороги пауз — `docs/PIPELINE.md`
- Композиции, зумы, акценты, качество рендера — `docs/REMOTION.md`
