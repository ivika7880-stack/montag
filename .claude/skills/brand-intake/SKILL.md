---
name: brand-intake
description: First-run onboarding interview for the Montage auto-editing pipeline. Run when someone opens this repo for the first time or wants to configure their look before editing — brand style, fonts, on-screen effects, editing pace, and b-roll inserts. Interviews the user with concrete options, saves a machine-readable brand.config.json the pipeline reads, and can generate b-roll image/video prompts from the transcript in the chosen style. Triggers: "brand intake", "настрой стиль", "настрой проект", "онбординг", "brand setup", "first time", "первый раз открыл", "мой стиль", "setup montage", "какой стиль монтажа".
metadata:
  tags: onboarding, brand, style, inserts, interview, montage
---

## Purpose

This repo auto-edits a talking-head video (analysis in Python → markup by Claude →
one-pass render in Remotion). Before editing, capture the creator's look so every
composition (Main169 16:9, Shorts916 9:16) and the b-roll match it. This skill
**interviews the user**, writes `brand.config.json` at the repo root, and — if asked —
drafts b-roll prompts from the transcript. Read `CLAUDE.md` and `docs/brandbook.md`
first so you can show the *current* defaults as one of the options.

**Rules while running this skill**
- Ask with `AskUserQuestion` (structured options) — one topic per question, batch 2–4
  related questions per call. Always give a recommended default first and let "Other"
  carry free text. Never invent an answer; if skipped, keep the current default and say so.
- Do not start rendering anything. This skill only *collects config* (and optionally
  drafts insert prompts). Editing happens afterwards through the normal pipeline.
- Keep the user's choices; write them verbatim into `brand.config.json`.

---

## Part A — Brand, fonts, effects, sound, editing style

Ask these six (three `AskUserQuestion` calls of two questions each is fine).

### 1. Brand style (`brand`)
- **Нейтральный пример (реком.)**: бумага `#F5F5F5`, акцент `#E5484D` дозой, графит `#17171A`. Задай свои HEX.
- **Свой бренд**: попроси HEX основного/акцентного/фона (or a logo/brandbook to derive from).
- **Минимал ч/б**: белый текст, чёрный фон, без цветного акцента.
- **Яркий/энергичный**: насыщенный акцент + контраст (уточни цвет акцента).

### 2. Fonts (`font`)
- **Свой дисплейный шрифт (реком.)** — попроси `.otf/.ttf` (кириллица обязательна) → в `remotion/public`, подключить в `src/fonts.ts`.
- **Свой шрифт** — попроси `.otf/.ttf` (кириллица обязательна) → положить в `remotion/public`, подключить в `src/fonts.ts`.
- **Системный гротеск** — Inter / Manrope (без файла).
- **Подобрать под бренд** — предложи 2–3 пары под выбранный бренд.

### 3. Effects (`effects`, multiSelect — «с твоими опциями»)
Offer this menu; the ones checked go into config as enabled. Explain each briefly.
- `jumpcut` — вырезка пауз и дублей (база, обычно всегда).
- `faceZoom` — медленный push-in на длинных планах.
- `punchZoom` — резкий панч-зум на акцентных словах.
- `accentCaptions` — акцентные слова с эффектом печати (дисплейный шрифт, алый курсор).
- `keySfx` — звук клавиши на каждую букву печати.
- `karaoke` — караоке-субтитры (для шортсов).
- `inserts` — b-roll вставки + PiP-лектор (спикер в углу).
- `music` — фоновая музыка (тихо, ~0.12).
- `progressBar` — прогресс-бар (шортсы).
- `declick` — дещелчок склеек (6-мс фейды, звук чище).
- `watermarkRemove` — снятие watermark со стоковых вставок.

### 4. Editing style / pace (`editStyle`)
Maps to the zoom/pause constants in `pipeline/props.py`.
- **Динамичный**: паузы жмём сильно, частые зумы, панч `1.30`+, много акцентов.
- **Сбалансированный (реком.)**: умеренные зумы, акценты дозой.
- **Спокойный/минимал**: длинные планы, мало зумов (push `1.05`), почти без панчей.
- **Нативный шортс**: агрессивно, вертикаль, крупная караоке, быстрый ритм.

### 5. Sound effects (`sfx`, multiSelect)
Какими звуками озвучиваются монтажные события. Банк — `@remotion/sfx`
(грузится с `https://remotion.media/*.wav` или свои файлы в `assets/sfx` → `remotion/public`).
Объясни каждый коротко; отмеченные идут в конфиг как включённые.
- `keyType` — звук клавиши на печать акцентных слов (`key.wav`, реком.).
- `whoosh` — свуш/вжух на переходах и склейках (`whoosh.wav` / `whip.wav`).
- `pageTurn` — «перелистывание» на смене темы/главы (`page-turn.wav`).
- `click` — тихий клик/щелчок на джампкате (`switch.wav` / `mouse-click.wav`).
- `shutter` — затвор камеры на панч-зуме или фото-стопе (`shutter-modern.wav`).
- `ding` — «динь» на появлении цифры/факта (`ding.wav`).
- `recordScratch` — скрэтч на резком повороте мысли (`record-scratch.wav`).
- `riserBoom` — нарастание/удар на сильном акценте (в `@remotion/sfx` нет — свой файл в `assets/sfx`).
- `memePack` — мем-звуки для нативных шортсов (`vine-boom`, `bruh`, `anime-wow`, `record-scratch`).
- `none` — без звуковых эффектов, только голос (и музыка, если выбрана).

### 6. Remotion visual effects (`remotionEffects`, multiSelect)
Пост-эффекты картинки из библиотеки Remotion effects (`@remotion/effects`, см.
`.claude/skills/remotion/rules/effects.md`). Применяются в `Main169.tsx`/`Shorts916.tsx`.
Предупреди: тяжёлые эффекты удорожают рендер, дозируй.
- `filmGrain` — плёночное зерно/шум для киношной фактуры (`noise()` / `speckle()`).
- `vignette` — виньетка по краям, взгляд собирается в центр (`vignette()`).
- `glow` — свечение на акцентном тексте/лице (`glow()` / `shine()`).
- `chromaticAberration` — хром. аберрация/глитч на резких акцентах (`chromaticAberration()`).
- `lightLeaks` — блики/лайт-лики на переходах (`lightLeak()`, см. `rules/light-leaks.md`).
- `zoomBlur` — зум-блюр на панч-зуме, вход мощнее (`zoomBlur()`).
- `colorGrade` — цветокор под бренд (`duotone()` / `tint()` / `saturation()`).
- `retroPrint` — ретро/печатная стилизация под бумагу (`halftone()` / `scanlines()` / `dotGrid()`).
- `pixelDissolve` — пиксельный распад на переходах (`pixelDissolve()`).
- `none` — чистая картинка без пост-эффектов (реком. для строгого экспертного стиля).

After A, **echo the chosen config back** in one short block and confirm before saving.

---

## Part B — Inserts (b-roll)

### 7. Do inserts exist? (`inserts.source`)
Ask: **«Вставки уже есть — или сделать промты по тексту на основе вашего стиля?»**
- **Уже есть** — попроси папку; проверь форматы, HEVC→прокси; заполни `work/<id>/inserts.json` (anchorWord/endWord/file).
- **Сделать промты из текста (реком., если материала нет)** → задать 8–10 (стиль, плотность,
  imagegen), генерация — скиллом `broll-gen` после Stage 1.
- **Без вставок** — `effects.inserts=false`, дальше не спрашивать.

### 8. Insert visual style (`inserts.style`, if generating)
- **Фотореализм** · **3D / рендер** · **Флэт-иллюстрация** · **Скриншоты / UI** ·
  **Абстракция / моушн** · **Под бренд (алый/бумага/графит)**. (multiSelect допустим — миксуем.)

### 9. Insert density (`inserts.density`)
- **Мало** ≈ 1 вставка / 30 с · **Средне** ≈ 1 / 15 с · **Много** ≈ 1 / 8 с · **Точное число N**.

### 10. Image generation (`imagegen`)
Как фабрика будет ДЕЛАТЬ картинки (сами промты и генерация — скилл `broll-gen`, Stage 1.5).
- `imagegen.provider` — чем генерить: **gemini-webapi (реком., MCP `gemini_generate_image`,
  Nano Banana 2 + референсы стиля)** · другой инструмент (спроси какой, запиши как есть) ·
  `manual` (пользователь генерит сам по промтам из `inserts_prompts.md`).
- `imagegen.styleRefs` — папка эталонов стиля (реком. `assets/style-refs`, 2–4 лучших
  прошлых вставки); передаются генератору как файлы-референсы.
- `imagegen.animate` — оживление картинок: **`prompts` (реком.)** — скилл пишет
  Veo/Kling-промты, пользователь генерит вручную, пайплайн подхватывает mp4
  (вотермарка + all-intra прокси) · `off` — вставки остаются статичными.

### If the user wants prompts or images now
Prompt writing, generation, and animation all live in skill **`broll-gen`** (Stage 1.5 of
`montage-pipeline`) — run it once Stage 1 artifacts (`words.json`/`transcript.txt`) exist.
It consumes the `inserts.*` and `imagegen.*` config saved here. Do **not** render.

---

## Output — `brand.config.json` (repo root)

Write the collected answers here (create or update; preserve unknown keys):

```json
{
  "brand": { "preset": "custom", "paper": "#F5F5F5", "scarlet": "#E5484D", "ink": "#17171A" },
  "font": { "family": "брендовый шрифт", "file": "brandfont.otf", "case": "upper" },
  "effects": {
    "jumpcut": true, "faceZoom": true, "punchZoom": true, "accentCaptions": true,
    "keySfx": true, "karaoke": true, "inserts": true, "music": false,
    "progressBar": true, "declick": true, "watermarkRemove": true
  },
  "sfx": ["keyType"],
  "remotionEffects": ["none"],
  "editStyle": "balanced",
  "inserts": { "source": "generate", "style": ["photoreal", "on-brand"], "density": "medium" },
  "imagegen": { "provider": "gemini-webapi", "styleRefs": "assets/style-refs", "animate": "prompts" }
}
```

**How the config maps to the pipeline (tell the user, apply when they next edit):**
- `brand` / `font` → `docs/brandbook.md`, `src/fonts.ts`, caption colors in `Main169.tsx` / `Shorts916.tsx`.
- `editStyle` → `PUNCH_SCALE` / `PUSH_SCALE` / pause threshold in `pipeline/props.py` and the
  `edl.py` pause value.
- `effects.*` → toggles: `music`→`props.music`; `declick`/`keySfx`→`audio.py` / `key.wav`;
  `inserts`→insert layer; `karaoke`/`progressBar`→`Shorts916.tsx`.
- `sfx.*` → монтажные звуки: `keyType`→`key.wav` в `audio.py`; остальные (`whoosh`/`pageTurn`/`click`/
  `shutter`/`ding`/`recordScratch`/`memePack`) → `<Audio from={...}>` в `Main169.tsx`/`Shorts916.tsx`
  на кадрах склеек/зумов (файлы из `@remotion/sfx` или `assets/sfx`→`public`).
- `remotionEffects.*` → пост-эффекты в `Main169.tsx`/`Shorts916.tsx` через `@remotion/effects`
  (`filmGrain`/`vignette`/`glow`/`chromaticAberration`/`lightLeaks`/`zoomBlur`/`colorGrade`/
  `retroPrint`/`pixelDissolve`); `none` — слой эффектов не добавляем.
- `inserts.*` → `shorts.py` / `props.py` insert anchoring + the generated prompts.
- `imagegen.*` → скилл `broll-gen` (Stage 1.5): провайдер генерации, папка референсов стиля,
  режим оживления (image-to-video промты + подхват mp4).

End by writing `brand.config.json`, showing a one-screen summary, and stating the next step
(run the analysis pipeline, or generate the b-roll images from `inserts_prompts.md`).
