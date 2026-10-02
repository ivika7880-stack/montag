---
name: publish-pack
description: Final pipeline stage — turn a finished Montage video into publish-ready texts from its transcript. Generates a YouTube description in the author's style, a timeline, hashtag tags (#), comma-separated tags, and a short Telegram announcement. Reuses the transcript the pipeline already produced (no re-transcription). Triggers — "сделай описание для ютуба", "теги", "тг-пост", "публикация видео", "publish pack", "оформи ролик", "тексты для ютуба".
metadata:
  tags: publish, youtube, telegram, description, tags, montage
---

## Purpose

Last step of the montage pipeline, after the final render. Take the video's transcript
(already produced by `pipeline/transcribe.py` → `work/<id>/transcript.txt`) and write
publish-ready copy. **Do not re-transcribe** — the Deepgram transcript already exists.
**Do not render or touch the montage.**

## Inputs
- `work/<id>/transcript.txt` — required (the video's text). If missing, run the analysis
  pipeline first (see `docs/PIPELINE.md`), don't transcribe here.
- `work/<id>/edl.json` + `remotion/props/<id>.json` — optional, for **accurate timecodes**
  of the edited final (raw transcript has duplicate takes and original-video timing).

## Output — write `work/<id>/publish.md`
One file with these sections:
1. **Описание (YouTube)** — ~500 слов. Первые 2 строки = хук (только они видны до «ещё»),
   в них самый сильный факт из ролика. В конце CTA (комментарий + подписка) и `<ССЫЛКА>`.
2. **Таймкоды** — `MM:SS Название`, 8–15 глав, первая `00:00`. Тянуть из финального EDL;
   если рендер ещё не готов — дать приблизительные и пометить «сверить с финалом».
3. **Теги с #** — 12–15 хэштегов, микс RU + EN, без пробелов внутри тега.
4. **Теги через запятую** — 20–30 для поля «Теги» YouTube, микс RU + EN.
5. **ТГ-пост (короткий)** — анонс ~80–120 слов, хук + «что внутри» + 1 строка вывода +
   `<ССЫЛКА>`. Пользователь просил именно короткий, не разворачивать до 200 слов.

## Style (эталон — не выяснять заново)
Наследует стиль автора из глобального `yt-pack` §3:
- Эксперт, объясняющий широкой публике. Разговорный русский, обращение на **«ты»**
  (это off-screen копия; экранное «вы» из `docs/brandbook.md` сюда не переносим).
- Конкретные примеры и **цифры из самого видео**, не общие слова
  (напр. «1,8 триллиона крутилок», «27 000 лет», «от 50 млн $»).
- Запрещены: рекламный жаргон (ROAS, спенд, скоринг, открут, кликабл), канцелярит,
  em-dash (`—`), хайповые обещания.
- Структура описания: зачем смотреть → что внутри → вывод → CTA.
- Ссылки везде плейсхолдером `<ССЫЛКА>`, реальные линки не выдумывать.
- Если пользователь правит стиль — обновить ЭТУ секцию, чтобы правка осталась навсегда.

## Steps
1. Read `work/<id>/transcript.txt`; вычленить ключевые факты, метафоры, цифры и CTA автора.
2. Draft the five sections above in the author's style.
3. If `edl.json`/props exist and render is done — посчитать реальные тайминги глав
   (сопоставить первую фразу главы с временем в финальном монтаже); иначе приблизительно.
4. Write `work/<id>/publish.md`.
5. Reply: короткий ТГ-пост + хук описания + оба набора тегов прямо в чат (это и есть
   то, что пользователь хочет прочитать) + путь к файлу. Полное описание — в файле.
