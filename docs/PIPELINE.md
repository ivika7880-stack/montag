# Пайплайн анализа (Python)

Все скрипты запускаются venv-питоном: `E:\Montage\.venv\Scripts\python.exe` (Python 3.11.9).
Рабочая папка видео: `work/<id>/` (для исходника — `work/source/`).

## Stage 0.5 — Сценарий до съёмки (опционально, скилл `script-gen`)

Видео с нуля: тема + тезисы → `work/<id>/script.md` — полный текст под запись в голосе
автора (профиль голоса, брендбук, прошлые транскрипты как эталон) с маркерами
вставок `[ВСТАВКА: описание сцены]` отдельными строками (плотность — из
`brand.config.json → inserts.density`). Маркеры вслух не читаются. Ворота: сценарий
утверждён → съёмка → Stage 1 с тем же `<id>`. После транскрибации маркеры наследует
`broll-gen` (матчит фразы сценария с `words.json` → anchorWord/endWord).

## Порядок шагов

```powershell
# 1. Аудио для анализа (16 кГц моно WAV)
ffmpeg -y -i "<видео>" -vn -ac 1 -ar 16000 -c:a pcm_s16le work\<id>\audio.wav

# 2. Транскрибация (Deepgram nova-3, ключ из .env)
...python.exe pipeline\transcribe.py work\<id>\audio.wav work\<id> ru
#    -> deepgram_raw.json, words.json, transcript.txt, utterances.txt

# 3. Компактный вид для LLM-разметки
...python.exe pipeline\indexed.py work\<id>        # -> indexed.txt ("i:слово", 12 на строку)

# 4. Claude читает utterances.txt + indexed.txt и пишет delete.json (см. формат ниже)

# 5. Монтажный лист
...python.exe pipeline\edl.py work\<id> work\<id>\audio.wav 30   # -> edl.json

# 6. Отчёт для ревью пользователем (обязательная ревью-точка!)
...python.exe pipeline\review.py work\<id>         # -> REVIEW.md

# 7. Позиция лица каждые 5 с
...python.exe pipeline\faces.py "<видео>" work\<id>\faces.json 5

# 8. Claude пишет accents.json (акцентные слова, см. формат)

# 9. Пропсы для Remotion (3-й арг — базовое имя медиа в public/, по умолчанию source)
...python.exe pipeline\props.py work\<id> remotion\props\main169.json            # source
...python.exe pipeline\props.py work\<id2> remotion\props\main169_v2.json <media2>  # другое видео

# 10. Declick-дорожка спикера (после props.py; перезапускать после любой правки монтажа)
...python.exe pipeline\audio.py remotion\props\main169.json
```

**Shorts-only маршрут** (нужны только шортсы, без полного 16:9): из шагов выше — только 1
(прокси+wav), 2 (transcribe) и 7 (faces); `delete.json`/`edl.py`/`review`/`accents`/`props.py`/
основной `audio.py` пропускаются. Дальше отбор моментов → `work/<id>/shorts.json` →
`shorts.py` (`draft` для вычитки) → `audio.py` на каждый шорт. Без `edl.json` shorts.py
берёт fps=30 (пайплайн весь на 30).

**audio.py** — режет аудио `public/source.mp4` по сегментам (48000/30 = 1600 сэмплов/кадр ровно →
синк кадр-в-кадр), на каждом краю сегмента жёсткий гейт 6 мс (края в 0, убирает вдох/щелчок на
стыке) + 6-мс косинус-дещелчок сразу за гейтом (GATE_MS / FADE_MS в шапке), конкатенация →
`public/audio_main169.wav`, и прописывает `audioTrack` в props. Main169 глушит
`<Video>` и играет эту дорожку. Зависит от сегментов — гонять после `edl.py→props.py`.

## Stage 1.5 — Фабрика b-roll (опционально, скилл `broll-gen`)

После шага 2 (есть `words.json`). Три части, у каждой ворота:

**A. Промты.** Якоря — из маркеров `script.md` (если видео по сценарию) или отбором
визуализируемых фраз из транскрипта; мимо вырезок (`delete.json`) и окон акцентов
(`accents.json` ±80 кадров). На якорь — 6-частный промпт (Subject+Action+Context+
Composition+Lighting+Style; Style = `inserts.style` + цвета бренда + аспект 16:9/9:16) →
`work/<id>/inserts_prompts.md` + драфт `work/<id>/inserts.json`.

**B. Генерация.** Провайдер `brand.config.json → imagegen.provider` (default
`gemini-webapi` — MCP `gemini_generate_image`, Nano Banana 2). Пре-флайт одним вызовом;
авторизация мертва → стоп, переавторизация. Референсы стиля из `imagegen.styleRefs`
(default `assets/style-refs/`) передаются как `files`. Результат из `~/Pictures/gemini/`
→ `remotion/public/inserts/<id>/NN_slug.png`, доработка через `conversation_id`.

**C. Оживление (image-to-video).** Автогенерации нет: скилл пишет
`work/<id>/animate_prompts.md` (картинка + motion-промпт 4–8 с, композицию не менять),
пользователь генерит вручную (Veo/Kling), кладёт mp4 в `work/<id>/animate/`. Подхват:

```powershell
# вотермарка Gemini/Veo (искра справа внизу, бокс для 1920x1080 — сверять кадры до/после!)
ffmpeg -y -i work\<id>\animate\NN_slug.mp4 -vf "delogo=x=1700:y=852:w=90:h=92" -c:v libx264 -crf 15 -g 1 -bf 0 -an remotion\public\inserts\<id>\NN_slug.mp4
# без вотермарки — только all-intra прокси (тот же вызов без -vf)
```

В `inserts.json` у вставки `file`: `.png` → `.mp4` (якоря те же; mp4 обрезается по своей
длине). После любых правок вставок: `props.py …` → **`audio.py …`**.

## Ремейк чужого шортса (Stage 2R, скилл montage-pipeline + script-gen)

```powershell
# скачивание референса по ссылке (YT Shorts / TikTok / Reels): ScrapeCreators -> фолбэк Apify
E:\Montage\.venv\Scripts\python.exe pipeline\download.py "<url>" work\<id>
#   -> work/<id>/ref_source.mp4; ключи SCRAPECREATORS_API_KEY / APIFY_TOKEN в .env
#   --provider scrapecreators|apify — форс провайдера (тест фолбэка); YouTube только Apify
# разбор референса: лицо (mediapipe, шаг 0.25с) + сцены (ffmpeg scdet) -> сегменты автор/визуал
E:\Montage\.venv\Scripts\python.exe pipeline\reference.py "<референс.mp4>" work\<id> 0.25
#   -> work/<id>/ref.json (сегменты: тип/тайминги/файл/текст, раскладка-предложение)
#   -> work/<id>/ref_plan.md (таймлайн для ревью)
#   -> remotion/public/inserts/<id>/ref_NN.mp4 (визуал-фрагменты, all-intra, без звука)
#   -> work/<id>/ref/thumb_NN.jpg (миниатюра фрагмента — Claude по ней метит вшитые субтитры)
#   -> work/<id>/ref/ (words.json транскрипта референса; пропускается без DEEPGRAM_API_KEY)
```

Вшитые субтитры референса: по миниатюрам размечается `coverBox {x,y,w,h}` (0..1 от области
вставки) в `inserts.json` — в композиции зона закрывается блюр-плитой, караоке автора поверх.

Дальше: `script-gen` (режим «Ремейк») пишет текст в голосе автора с маркерами
`[ВИЗУАЛ ref_NN — full|half|third]` → пользователь записывает себя → его запись идёт
shorts-only маршрутом (в `shorts.json` поле `media` = имя записи в public) →
`work/<id>/inserts.json` якорит ref-фрагменты к фразам записи с `layout` → `shorts.py` →
`audio.py` → Studio. Раскладки вставок Shorts916: `third` (верхняя треть, default) /
`half` (полэкрана) / `full` (перекрывает спикера целиком, голос продолжается).
Пороги reference.py — в шапке файла (SCENE_THRESH 0.30, FACE_FRAC 0.50, MIN_SEG_S 0.40).

## Публикация (после финального рендера)
Скилл **`publish-pack`** берёт готовый `work/<id>/transcript.txt` (повторно не транскрибирует) и
пишет `work/<id>/publish.md`: описание для YouTube в стиле автора, таймкоды (точные — из `edl.json`),
теги с `#`, теги через запятую, короткий ТГ-пост. Триггеры: «сделай описание для ютуба», «теги», «тг-пост».

## Форматы

**words.json** — список слов: `{"i": индекс, "w": слово, "pw": с пунктуацией, "start", "end", "conf"}`.

**delete.json** — что вырезать (пишет Claude):
```json
{"delete": [{"from": 74, "to": 85, "reason": "дубль хука — оставлена вторая версия"}]}
```
Индексы — из words.json/indexed.txt, диапазоны включительные.

**edl.json** — результат: `segments: [{start, end, startFrame, endFrame}]` + kept_duration.
Не править руками — только через delete.json → edl.py.

**accents.json** — `{"accents": [{"word": <индекс слова>, "text": "ТЕКСТ КАПСОМ"}]}`.
Текст — как должен появиться на экране (дисплейный шрифт, капс, можно «→» и $).

**faces.json** — `[{t, found, box: {x,y,w,h}}]`, box относительный 0..1.

## Логика edl.py (пороги — константы в шапке файла)

1. **Вырезка слов**: границы ищутся по минимуму RMS-энергии (окно 20 мс, шаг 4 мс)
   в коридоре между концом оставляемого слова и началом удаляемого (±150 мс) —
   оставленные слова не обрезаются никогда.
2. **Сжатие пауз**: паузы между оставленными словами > 0.35 с → ~0.22 с
   (0.12 хвост + 0.10 голова). Динамику монтажа регулировать здесь (MAX_PAUSE_S / KEEP_TAIL_S / KEEP_HEAD_S).
   Это же режет зажёванные «эээ» — Deepgram по-русски их отдельным словом не пишет, они сидят в разрыве и уходят с серединой паузы.
3. **Голова/хвост**: тишина до первого слова → 0.3 с, после последнего → 0.8 с.
4. Сегменты короче 0.15 с выбрасываются, зазоры < 40 мс сливаются.

## Логика props.py

- Маппит source-время → выходной кадр (учитывая вырезки); события, попавшие в вырезанное, пропускаются с WARN.
- **punch-зумы**: на каждый акцент, scale 1.30, вход 18 к., холд 36 к., выход 24 к., origin = центр лица (ближайший замер).
- **push-in**: сегменты длиннее 6 с — плавный наезд до 1.07 (если не пересекается с punch).
- Длительность плашки акцента: 66 кадров (2.2 с).
- **totalDurationInFrames = Σ(endFrame−startFrame)** по сегментам (кадрово-точно = реальная длина `<Series>` = длина declick-дорожки). НЕ `round(kept_duration*fps)` — то давало дрейф в неск. кадров на многих склейках и валило assert в audio.py.

## Выбор дублей и чистка (правила для Claude)

- Дубль = сосед-сегмент с совпадающим началом фразы. Оставлять тот, что переходит
  в продолжение речи (обычно последний). Критерии: точность, отсутствие запинок,
  темп, чистые края. Со сценарием — сверять по нему.
- Обращение к зрителю на «вы» (брендбук) — при выборе версии дубля предпочитать «вы».
- Всё вырезанное — в REVIEW.md с причиной; рендерить только после утверждения.

## Deepgram

- nova-3, language=ru, smart_format+punctuate+utterances. ~$0.0043–0.0077/мин, на аккаунте $200 кредитов.
- filler_words работает только для английского — для русского паразиты приходят как обычные слова.
- Ключ: `.env` → DEEPGRAM_API_KEY (при утечке — перевыпустить в консоли Deepgram).
