# Remotion: композиции и рендер

Проект: `E:\Montage\remotion` (Remotion 4.0.487, React 19, TS 5.9.3-пин, zod 4.3.6-пин).
Официальный скилл с правилами: `.claude/skills/remotion/` (37 rules-файлов — сверяться при работе с API).

## Композиции (src/Root.tsx)

- **Main169** — 1920×1080, 30 fps. Готова. defaultProps импортируются из `props/main169.json`;
  durationInFrames приходит из `calculateMetadata` (totalDurationInFrames из пропсов).
- **Shorts916** — 1080×1920, 30 fps. Пока заглушка (Placeholder). План: свои сегменты
  (лучшие отрезки), караоке-субтитры всех слов + выделение акцентов, агрессивнее зумы.

## Как устроен Main169 (src/Main169.tsx)

- **Jump-cut**: `<Series>` → `<Series.Sequence durationInFrames={endFrame-startFrame} premountFor={30}>`
  → `<Video src={staticFile(src)} trimBefore={seg.startFrame} trimAfter={seg.endFrame} muted={audioTrack!=null}>`
  из `@remotion/media`. Тримы `trimBefore`/`trimAfter` — в КАДРАХ (и у `<Video>`, и у `<Audio>`);
  секунды у `<Video>` дают чёрный экран.
- **Зумы**: весь видеослой обёрнут в AbsoluteFill c `transform: scale()` и
  `transformOrigin: "<x>% <y>%"` (координаты лица из пропсов). punch (1.30) поверх push (1.07),
  easing `Easing.bezier(0.16,1,0.3,1)`.
- **Акценты**: Sequence на a.frame → AccentCaption: печать по 1 символу каждые 2 кадра
  (slice по кадру, НЕ per-char opacity), алый блок-курсор мигает, звук key.wav на каждый
  непробельный символ (volume 0.5), fade-out последние 8 кадров.
- **Звук спикера**: НЕ из `<Video>` (он `muted`), а `props.audioTrack` → `<Audio src=audioTrack>` на всю
  таймлинию. Это declick-дорожка от `pipeline/audio.py`: сегменты аудио source.mp4, вырезанные
  sample-accurate (1600 сэмплов/кадр), с 6-мс косинус-фейдами на стыках (убирают щелчки склеек).
  Покадровая `volume`-функция для этого не годится — `@remotion/media` квантует громкость по кадрам.
- **Музыка**: `props.music` (имя файла в public/) → `<Audio volume={0.12}>`; сейчас null.

## Пропсы (props/main169.json)

Генерятся `pipeline/props.py` (+ `audioTrack` ставит `pipeline/audio.py`) — руками не править.
Схема: типы в Main169.tsx (MainProps: src, previewSrc, fps, segments, accents, punchZooms,
pushZooms, inserts, pipWindows, music, audioTrack, totalDurationInFrames).

## Прокси-исходник (public/source.mp4)

HEVC .mov ненадёжен в headless Chrome → обязательный прокси:
```
ffmpeg -y -i "<исходник>" -c:v libx264 -preset medium -crf 15 -g 1 -bf 0 \
  -pix_fmt yuv420p -c:a copy -movflags +faststart remotion/public/<id>.mp4
```
all-intra (`-g 1`) = мгновенный сик по 43+ сегментам; `-c:a copy` = звук не трогаем.

## Качество рендера (выяснено исследованием, причины прошлых проблем пользователя)

- Мыло даёт: композиция меньше целевого разрешения (720p → апскейл) и дефолтный CRF/preset.
  PNG-кадры без потерь и НЕ виноваты (даже рекомендованы для точности цвета).
- Дефолты, тихо снижающие качество: crf h264=18, preset medium, yuv420p (хрома-сабсэмплинг).
- **Финальная команда** (запуск только по явной команде пользователя):
```
npx remotion render src/index.ts Main169 ../out/main169.mp4 \
  --props=props/main169.json --image-format=png --crf=14 --x264-preset=slow
```
- **Превью — только `npx remotion studio`**, файлы-превью не рендерить (правило пользователя).
- ProRes-мастер запрещён пользователем.
- Известная проблема: деградация скорости OffthreadVideo на длинных видео из-за вымывания
  кэша кадров — если рендер замедляется после 20–30%, поднять cache size/threads
  (см. .claude/skills/remotion и github remotion#3088). `@remotion/media <Video>` — новее и оптимизированнее.

## Стиль текста в кадре (из docs/brandbook.md)

дисплейный брендовый шрифт (public/brandfont.otf, грузится через @remotion/fonts в src/fonts.ts),
КАПС, бумага #F5F5F5 на видео с тенью, алый #E5484D — дозой (курсор, один акцент в кадре),
стрелка «→» — фирменный значок, эмодзи нельзя, обращение на «вы».
