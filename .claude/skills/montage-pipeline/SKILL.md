---
name: montage-pipeline
description: End-to-end orchestrator for the Montage auto-editing project — the map from idea to published video. Read this FIRST when the repo is opened or someone wants to edit a video. Walks the full pipeline: onboarding (brand-intake) → script before shooting (script-gen) → analysis (transcribe → cut markup → EDL → review → faces → accents → props → declick audio) → b-roll factory (broll-gen: image generation + animation pickup) → review in Remotion Studio → final render → publish texts (publish-pack). Triggers — "запусти проект", "начать монтаж", "новое видео", "смонтируй видео", "start", "run pipeline", "с чего начать", first repo open.
metadata:
  tags: pipeline, orchestrator, montage, remotion, workflow
---

## What this is

The single entry point for the Montage project. It doesn't do the work itself — it
routes to the right stage, skill, and command, and keeps the run in order. Read
`README.md`, `CLAUDE.md`, and `docs/PIPELINE.md` for detail; this skill is the sequence.

**On first open of the repo:** greet the user, show a 3-line summary of what the project
does (from `README.md`), tell them the three ways to start, and wait.
- New look / first run → **`brand-intake`** (configure brand, fonts, effects, sound, pace).
- Video from zero (nothing filmed yet) → **`script-gen`** (Stage 0.5 below).
- Have a clip to edit → go to Stage 1 below.
- **Only shorts from a clip** (no full 16:9 edit) → shorts-only route: Stage 1-lite + Stage 2.
- **Shorts factory** — тексты шортсов «перепиши под меня» / «придумай по темам» →
  `script-gen` (Shorts scripts) + shorts-only route; **ремейк чужого шортса** → Stage 2R.

Do not render or push anything without an explicit user command. Preview is Studio-only.

## The pipeline (per video `<id>`, artifacts in `work/<id>/`)

**Stage 0 — Onboarding (optional, once per brand).** Run skill `brand-intake` →
`brand.config.json` (brand, font, `effects`, `sfx`, `remotionEffects`, `editStyle`, inserts, `imagegen`).
Apply the config to `docs/brandbook.md`, `src/fonts.ts`, `pipeline/props.py` constants,
and the composition effect/sound layers before editing. See `brand-intake` for the mapping.

**Stage 0.5 — Script (optional, per video).** Run skill `script-gen`: тема + тезисы →
`work/<id>/script.md` — полный текст под запись в голосе автора с inline-маркерами
будущих вставок `[ВСТАВКА: …]`. **Gate:** сценарий утверждён → пользователь снимает видео →
Stage 1 (тот же `<id>`; маркеры наследует `broll-gen` на Stage 1.5).

**Stage 1 — Ingest + analysis (Python, `.venv`).** Full command list in `docs/PIPELINE.md`:
1. `ffmpeg … audio.wav` (16 kHz mono) — analysis audio.
2. `transcribe.py` (Deepgram, key from `.env`) → `words.json`, `transcript.txt`, `utterances.txt`.
3. `indexed.py` → `indexed.txt` (compact view for markup).
4. **Claude** reads `utterances.txt` + `indexed.txt`, writes `delete.json` (cut fillers/dupes —
   Deepgram filler_words is unreliable for Russian, so Claude does it).
5. `edl.py` → `edl.json` (segments + frames). Never hand-edit; always via `delete.json`.
6. `review.py` → `REVIEW.md`. **Mandatory review point** — show the user, wait for OK.
7. `faces.py` → `faces.json` (face position every 5 s).
8. **Claude** writes `accents.json` (accent words shown on screen).
9. `props.py` → `remotion/props/main169.json`.
10. `audio.py <props>` → declick speaker track `audio_main169.wav` (rerun after ANY edit change).

**Stage 1.5 — B-roll generation (optional).** Run skill `broll-gen` (после Stage 1 — нужны
`words.json`; до/параллельно Stage 3). Промты из маркеров `script.md` или из транскрипта →
генерация картинок через провайдер из `brand.config.json → imagegen` (default gemini-webapi
MCP; **pre-flight обязателен** — авторизация мертва → стоп, попросить переавторизоваться) →
файлы в `public/inserts/<id>/` + `inserts.json` → опционально «оживление» (motion-промты +
подхват mp4: delogo + all-intra прокси). Gates: список промтов и брак картинок. После —
`props.py` → `audio.py`.

**Stage 2 — Shorts (optional, or the whole point in shorts-only mode).** Pick moments
(Claude proposes: хуки, цифры, панчи — user approves) → `work/<id>/shorts.json`, then
`shorts.py work\<id> remotion\props` (+ `draft` first для вычитки слов) → `props/<id>.json`,
then `audio.py` per short. Subtitle text is hand-cleaned in `shorts.json` (Deepgram lies on
numbers/words). Вставки шортсов поддерживают `layout` в `inserts.json`: `third` (верхняя
треть, default) / `half` (полэкрана) / `full` (перекрывает спикера, голос продолжается);
`shorts.json` может задавать `media` — базовое имя записи в public (default `source`).

**Shorts-only route** (user wants shorts, no full 16:9 edit): run Stage 1-lite —
only steps 1 (proxy + analysis wav), 2 (`transcribe.py`), 7 (`faces.py`) — then Stage 2.
Skip `delete.json`/`edl.py`/`REVIEW.md`/`accents.json`/`props.py`/main `audio.py`
(shorts cut clean takes straight from source via `spans`; `shorts.py` defaults to 30 fps
when `edl.json` is absent). Gates: подборка моментов утверждается пользователем, дальше
Stage 3 (Studio) и Stage 4 (render `Short-*` по явной команде).

**Stage 2R — Shorts remake (переделать чужой шортс под автора).**
1. Пользователь даёт ссылку (YouTube Shorts / TikTok / Reels) или готовый mp4. Ссылка →
   `download.py <url> work\<id>` → `work/<id>/ref_source.mp4` (ScrapeCreators первым,
   при ошибке Apify; YouTube — только Apify; ключи `SCRAPECREATORS_API_KEY`/`APIFY_TOKEN`
   в `.env`, нет ключей — попросить у пользователя, не ретраить). Дальше
   `reference.py <mp4> work\<id> [0.25]`: mediapipe-лицо
   с шагом 0.25 с + ffmpeg-сцены → сегменты «автор в кадре» / «визуализация»; визуал
   режется в `public/inserts/<id>/ref_NN.mp4` (all-intra, без звука) + миниатюра
   `work/<id>/ref/thumb_NN.jpg` на каждый фрагмент; текст — Deepgram (опционально).
   Выход: `work/<id>/ref.json` + `ref_plan.md` (таймлайн + раскладки). **Прочитай
   миниатюры глазами** (Read): вшитые субтитры/вотермарки → зона `coverBox {x,y,w,h}`
   (0..1 от области вставки) в `inserts.json` — Shorts916 закроет её блюр-плитой, твоё
   караоке рисуется поверх. Статичная вотермарка → альтернатива delogo (кадры до/после
   сверить); движущаяся — предупредить. **Gate:** показать `ref_plan.md`.
2. Текст: `script-gen` → режим «Ремейк» — рерайт в голосе автора под структуру референса,
   маркеры `[ВИЗУАЛ ref_NN — full|half|third]`. **Gate:** текст утверждён → пользователь
   записывает себя.
3. Сборка: запись → shorts-only маршрут (прокси → transcribe → faces → `shorts.json`,
   в нём `media: "<имя записи>"`) → `work/<id>/inserts.json`: ref-фрагменты по якорям фраз
   (anchorWord/endWord) с `layout` из маркеров → `shorts.py` → `audio.py` → `<Composition
   Short-*>` в Root.tsx → Stage 3. Чужие фрагменты в ремейке — ответственность автора канала.

**Stage 3 — Review in Studio.** `cd remotion && npx remotion studio`. User previews Main169
(16:9) and `Short-*` (9:16). Preview is NEVER a file render. Edits loop back:
`delete.json` → `edl.py` → `props.py` → **`audio.py`** (rerun audio every time).

**Stage 4 — Final render (only on explicit user command).** High quality:
`npx remotion render src/index.ts Main169 ../out/main169.mp4 --props=props/main169.json --image-format=png --crf=14 --x264-preset=slow`.
Long job → run in background with a completion notice; watch by output-file growth, not by
process name. Bump `--concurrency` if a single stuck frame can deadlock the run.

**Stage 5 — Publish texts.** Run skill `publish-pack` → `work/<id>/publish.md`
(YouTube description in the author's style, timecodes from `edl.json`, `#`-tags, comma tags,
short Telegram post). Uses the transcript already produced — no re-transcription.

## Guardrails (from CLAUDE.md — do not violate)
- Preview only in Studio; final render only on explicit command; no ProRes.
- Speaker sound = declick track, not `<Video>` audio. No normalization/denoise on the voice.
- Composition size always equals target resolution (1920×1080 / 1080×1920).
- Version pins: TypeScript 5.9.3, zod 4.3.6, mediapipe 0.10.21. `@remotion/media` trims in FRAMES.
- Composition `id`: no `_` (use `-`). PowerShell 5.1: no `&&`; Cyrillic paths in quotes.

## Reply pattern
At each stage: say which stage you're on, run its command(s), show the artifact/summary,
and name the next step. Hard gates — never skip: script approval (Stage 0.5, if scripted),
`REVIEW.md` (Stage 1.6), b-roll approval (Stage 1.5, if generating), and the final
render (Stage 4).
