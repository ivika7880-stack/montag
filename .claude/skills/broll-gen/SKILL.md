---
name: broll-gen
description: Stage 1.5 of the Montage pipeline — the b-roll factory. From the transcript (and script.md markers if the video was scripted) it writes 6-part image prompts in the brand style, generates the images through the configured provider (default — gemini-webapi MCP, Nano Banana 2, with style-reference images), places them into remotion/public/inserts/<id>/ + inserts.json, and optionally "revives" selected stills: writes image-to-video motion prompts, then picks up the user-generated mp4s (delogo watermark + all-intra proxy). Triggers — "сгенери вставки", "сделай картинки", "картинки для видео", "b-roll", "генерация изображений", "оживи вставки", "оживление", "generate inserts".
metadata:
  tags: b-roll, inserts, image-generation, gemini, animate, montage
---

## Purpose

Turn the video's text into finished b-roll files the pipeline can consume. Three parts,
each with its own gate; the user can enter at any part (e.g. «оживи вставки» → Part C only).

**Prereqs:** Stage 1 done — `work/<id>/words.json` + `transcript.txt` exist (anchors need word
indices). Style comes from `brand.config.json` (run `brand-intake` if missing; fallback —
defaults from `docs/brandbook.md`: бумага `#F5F5F5`, акцент `#E5484D` дозой, графит `#17171A`).

This skill writes files under `work/<id>/` and `remotion/public/inserts/<id>/` only. It never
edits `edl.json`/props by hand and never renders. After it finishes, the normal chain applies:
`props.py … → audio.py …` (напомнить команду, запускать по ходу пайплайна, не самовольно).

---

## Part A — Prompts (`inserts_prompts.md` + draft `inserts.json`)

**Anchor source, in priority order:**
1. **`work/<id>/script.md` markers** (video was scripted via `script-gen`): for each
   `[ВСТАВКА: …]` find the sentence right after it in the script, locate the same phrase in
   `words.json` (fuzzy match — Deepgram mangles numbers/words), take its word indices →
   `anchorWord` = first word of the phrase, `endWord` ≈ anchor + 15–40 words (по смыслу фразы).
2. **No script** — pick anchors from `transcript.txt`: concrete nouns/objects/metaphors the
   viewer can *see* (not abstract connectives). Density from `brand.config.json →
   inserts.density` (мало ≈ 1/30 с, средне ≈ 1/15 с, много ≈ 1/8 с).

Skip anchors that fall inside cut ranges (`delete.json`) and keep clear of accent windows
(`accents.json` word ±80 frames — punch-zoom lives there, см. props.py).

**Prompt formula (per anchor)** — 6 parts: **Subject + Action + Context + Composition +
Lighting + Style**, where Style = стиль из `brand.config.json → inserts.style` + brand colors
+ явный аспект: **16:9** для Main169, **9:16** для шортсов. Промпт пишется по-английски
(генераторы понимают лучше), описание сцены в файле — по-русски.

**Output:**
- `work/<id>/inserts_prompts.md` — по строке на вставку: якорная фраза, таймкод source-видео,
  предлагаемое имя файла `NN_slug` (нумерация по порядку: `01_…`, `02_…`), полный промпт,
  пустая колонка «оживление?» (заполнится в Part C).
- Draft `work/<id>/inserts.json`: `{"inserts": [{"file": "<id>/NN_slug.png", "anchorWord": N,
  "endWord": M, "note": "…"}]}` — пути уже с подпапкой `<id>/` (namespace, props.py клеит
  `inserts/` сам).

**Gate:** показать список (фраза → промпт одной строкой), дать вычеркнуть/добавить якоря.

---

## Part B — Image generation

**Provider** = `brand.config.json → imagegen.provider`, default `"gemini-webapi"`.
Пользователь может переопределить на запуске («сгенери через X»):
- `gemini-webapi` — MCP tools `gemini_generate_image` (см. ниже).
- Другой MCP/API — использовать его инструменты по той же схеме (промпт + референсы).
- `manual` — отдать `inserts_prompts.md` пользователю, попросить сложить готовые PNG в
  названную папку, продолжить с шага «Placement».

**Pre-flight (обязателен, один раз за сессию):** один маленький вызов
`gemini_generate_image` (например «solid paper-white background, single scarlet square,
flat, 16:9»). Ошибка авторизации/куки → **остановиться** и попросить пользователя
переавторизоваться в gemini-webapi MCP; не молотить ретраями и не переключать провайдера молча.

**Style references:** папка из `brand.config.json → imagegen.styleRefs` (default
`assets/style-refs/`) — 2–4 эталонных изображения (лучшие прошлые вставки). Передавать их
в каждый вызов через `files=[…]` с фразой «match the visual style of the attached
references». Папка пуста/нет — генерить только по текстовому Style-блоку и сказать об этом
пользователю (и предложить положить эталоны).

**Per prompt:**
1. `gemini_generate_image(prompt, files=[styleRefs])` — модель по умолчанию (Nano Banana 2,
   поддерживает неквадратные аспекты; аспект должен быть назван в промпте).
2. Результат сохраняется MCP в `~/Pictures/gemini/` — путь возвращается в ответе.
3. Доработка по замечаниям — тем же инструментом с `conversation_id` из ответа
   («make the meter larger», «less clutter») — не начинать промпт с нуля.

**Placement:** копировать выбранный файл в `remotion/public/inserts/<id>/NN_slug.png`
(PNG; кириллических имён избегать), обновить `work/<id>/inserts.json`. Убедиться, что
`work/<id>/` и подпапка существуют.

**Gate:** показать таблицу «файл → якорная фраза → путь», спросить, что бракуем. Забракованное —
перегенерить через `conversation_id` (или новым промптом), затем снова показать. Только
после ОК двигаться дальше (Part C или назад в пайплайн: `props.py` → `audio.py`).

---

## Part C — Оживление (image-to-video, optional)

Включается если `brand.config.json → imagegen.animate == "prompts"` и пользователь захотел,
или по прямой просьбе («оживи 03 и 07»). Автогенерации видео нет — только промты + подхват.

**1. Выбор.** Спросить, какие вставки оживлять (обычно 2–4 самые важные: хук, ключевая
метафора). Остальные остаются PNG.

**2. Промты** → `work/<id>/animate_prompts.md`, на каждую картинку:
- источник: `remotion/public/inserts/<id>/NN_slug.png` (прикладывается в Veo/Kling как кадр);
- motion-промпт (EN): движение камеры (slow push-in / pan / orbit), движение объекта
  (одно, простое), длительность 4–8 с, и обязательные ограничители: «keep the exact
  composition and style of the source image, no new objects, no text morphing».
- Напомнить: генерить в родном аспекте картинки (16:9 / 9:16).

**3. Подхват.** Пользователь генерит вручную (Veo/Kling/…), кладёт mp4 в
`work/<id>/animate/` (имя = как у картинки: `NN_slug.mp4`). Дальше на каждый файл:
1. **Вотермарка**: у Gemini/Veo — «искра» в правом нижнем углу; для 1920×1080 рецепт
   `ffmpeg -i in.mp4 -vf "delogo=x=1700:y=852:w=90:h=92" …`.
   Другое разрешение/сервис — найти бокс по кадру. **Всегда** сверять кадры до/после
   (`ffmpeg -ss … -frames:v 1`) — фон под боксом должен быть чист. Оригинал не трогать.
2. **Прокси all-intra** (Remotion требует): `-c:v libx264 -crf 15 -g 1 -bf 0 -an`
   (звук вставкам не нужен) → `remotion/public/inserts/<id>/NN_slug.mp4`.
3. `work/<id>/inserts.json`: у этой вставки `file` меняется `.png` → `.mp4` (якоря те же;
   mp4 в композиции обрезается по своей длине).
4. Удалить/оставить PNG-версию — спросить один раз (обычно оставить рядом как fallback,
   в inserts.json смотрит только `file`).

**Финал скилла:** список изменённых файлов + напомнить цепочку:
`props.py work\<id> remotion\props\<props>.json <media>` → `audio.py remotion\props\<props>.json`.

## Gotchas
- PowerShell 5.1: без `&&`; пути с кириллицей в кавычках; файлы писать UTF-8.
- `~/Pictures/gemini/` — папка `Pictures\gemini` в профиле пользователя Windows.
- `remotion/public/inserts/` под несколько видео — всегда подпапка `<id>/`, в inserts.json
  путь `<id>/файл` (ролики делят префиксы `01_…`).
- Deepgram врёт числа/имена — матчить якоря по нескольким соседним словам, не по одному.
