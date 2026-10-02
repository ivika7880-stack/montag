# Montage — пайплайн автомонтажа «говорящей головы»

Автоматический монтаж видео с одним спикером: Python анализирует исходник
(транскрипт, дубли, положение лица), Claude размечает вырезки и акценты, а
[Remotion](https://www.remotion.dev/) рендерит финал одним проходом — джамп-кат,
зумы на лицо, акцентные слова с эффектом печати, вертикальные шортсы с караоке.
Плюс фабрика контента: сценарий в голосе автора до съёмки, генерация b-roll
картинок с «оживлением», шортсы без полного монтажа и ремейк чужих шортсов
по ссылке.

> **С чего начать:** открой проект и скажи агенту «запусти проект» или «начать монтаж».
> Он прочитает скилл **`montage-pipeline`** и проведёт тебя по шагам. Пять путей старта:
> новый стиль → `brand-intake`; видео с нуля (ещё не снято) → `script-gen`;
> есть клип → Stage 1; только шортсы из клипа → shorts-only маршрут;
> ремейк чужого шортса по ссылке → Stage 2R.

## Стек
Python 3.11 (`.venv`) · Remotion 4 (Node 22) · FFmpeg · Deepgram API ·
TypeScript 5.9.3 · zod 4.3.6 · mediapipe 0.10.21

## Как это работает

```
(опционально) script-gen → work/<id>/script.md (сценарий + маркеры вставок) → съёмка
   ▼
исходник.mov
   │  ffmpeg → audio.wav (16 кГц моно)
   ▼
transcribe.py ─ Deepgram ─→ words.json · transcript.txt · utterances.txt
   │  indexed.py → indexed.txt
   ▼
Claude → delete.json (вырезать паузы/дубли/паразиты)
   │  edl.py → edl.json (сегменты + кадры)
   ▼
review.py → REVIEW.md   ◄── обязательная ревью-точка
   │  faces.py → faces.json    Claude → accents.json
   ▼
(опционально) broll-gen → промты → картинки в public/inserts/<id>/ + inserts.json
   ▼
props.py → remotion/props/main169.json
   │  audio.py → declick-дорожка спикера (audio_main169.wav)
   ▼
Remotion Studio (превью)  ──edit loop──►  render → out/main169.mp4
   ▼
publish-pack → publish.md (описание YouTube · таймкоды · теги · ТГ-пост)
```

Шортсы: `shorts.py` собирает вертикальные 9:16 из тех же артефактов (кроп на лицо,
караоке-субтитры, панч-зумы); без `edl.json` работает shorts-only маршрут — прокси →
транскрипт → лица → сразу шортсы. Ремейк чужого шортса: `download.py` качает референс
по ссылке (YouTube Shorts / TikTok / Reels), `reference.py` разбирает его на сегменты
«автор в кадре» / «визуализация» — пользователь записывает себя, сборка берёт его
речь + чужой визуал по якорям.

## Быстрый старт

```powershell
# 1. Python-окружение
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Ключи (не коммитятся) — .env:
#    DEEPGRAM_API_KEY=...           # транскрипция (обязателен)
#    SCRAPECREATORS_API_KEY=...     # ремейк шортсов по ссылке (опционально)
#    APIFY_TOKEN=...                # фолбэк-загрузчик референсов (опционально)

# 3. Remotion
cd remotion && npm install

# 4. Анализ одного видео (подробно — docs/PIPELINE.md)
.venv\Scripts\python.exe pipeline\transcribe.py work\<id>\audio.wav work\<id> ru
# … далее indexed → delete → edl → review → faces → accents → props → audio

# 5. Превью (ТОЛЬКО в Studio, не рендером в файл)
cd remotion && npx remotion studio

# 6. Финал (по явной команде)
npx remotion render src/index.ts Main169 ../out/main169.mp4 \
  --props=props/main169.json --image-format=png --crf=14 --x264-preset=slow
```

## Скиллы (`.claude/skills/`)

| Скилл | Когда | Что делает |
|-------|-------|-----------|
| **montage-pipeline** | открытие проекта / «запусти проект» | оркестратор: ведёт по всем стадиям и маршрутам |
| **brand-intake** | первый запуск / новый стиль | опрос → `brand.config.json` (бренд, шрифт, эффекты, звук, ритм, вставки, imagegen) |
| **script-gen** | видео ещё не снято / тексты шортсов | Stage 0.5: сценарий в голосе автора с маркерами вставок; шортс-тексты (рерайт / идеи / ремейк) |
| **broll-gen** | нужны вставки | Stage 1.5: промты → генерация картинок → подхват «оживлённых» mp4 |
| **publish-pack** | после рендера | тексты для публикации из транскрипта (YouTube + ТГ) |
| **remotion** | правки Remotion-кода | доменные знания Remotion (эффекты, аудио, тайминги) |

## Структура

- `pipeline/` — Python-скрипты анализа; шортсы — `shorts.py`; ремейк — `download.py` + `reference.py`
- `remotion/` — Remotion-проект: `src/Main169.tsx` (16:9), `src/Shorts916.tsx` (9:16), `src/Root.tsx`
- `work/<id>/` — артефакты по каждому видео (в git не попадают)
- `docs/` — `PIPELINE.md` (анализ), `REMOTION.md` (композиции/рендер), `brandbook.md` (шаблон стиля — задай свой)
- `tests/` — смоук-тесты (без сети)
- `out/` — финальные рендеры (в git не попадают)

## Правила
- **Превью — только в Remotion Studio**, не рендером в файл. Финальный рендер — по явной команде.
- **Звук спикера не обрабатывается** (нормализация/шумодав запрещены). Исключение — 6-мс дещелчок склеек.
- Композиция всегда равна целевому разрешению (1920×1080 / 1080×1920).
- Правка монтажа: `delete.json` → `edl.py` → `props.py` → `audio.py` (не руками в `edl.json`).

Детали — в [CLAUDE.md](CLAUDE.md) и [docs/](docs/).
