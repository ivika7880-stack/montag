import React from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  Series,
  getRemotionEnvironment,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { Audio, Video } from "@remotion/media";
import { brandFontFamily, hookFontFamily } from "./fonts";

export type ShortSeg = {
  start: number;
  end: number;
  startFrame: number;
  endFrame: number;
  tx: number; // horizontal crop offset (px) to centre the face
  faceY: number; // face centre Y in % (zoom origin)
};
export type ShortWord = { text: string; from: number; to: number; accent: boolean };
export type ShortPunch = { from: number; originY: number };
export type ShortInsert = {
  file: string;
  type: "image" | "video";
  from: number;
  to: number;
  layout?: "third" | "half" | "full"; // how much of the canvas the insert takes
  // zone of burned-in subs/watermark to hide, relative 0..1 of the insert area;
  // covered with a blur plate, our karaoke renders on top of everything anyway
  coverBox?: { x: number; y: number; w: number; h: number };
};

export type ShortHook = { text: string; from: number; to: number };

export type ShortsProps = {
  src: string;
  previewSrc: string | null;
  fps: number;
  videoW?: number; // source width scaled to canvas height (16:9 → 3413, 9:16 → 1080)
  hook?: ShortHook | null; // hook plate (Patsy Sans) at the start
  segments: ShortSeg[];
  words: ShortWord[];
  punchZooms: ShortPunch[];
  inserts: ShortInsert[];
  audioTrack: string | null;
  totalDurationInFrames: number;
};

const CANVAS_H = 1920;
const DEFAULT_VIDEO_W = Math.round((CANVAS_H * 16) / 9); // 3413: 16:9 source scaled to fill height
// Per-layout insert height and how far the speaker shifts down to stay clear.
// "full" covers the speaker entirely (voice keeps playing) — no shift needed.
const INSERT_LAYOUT = {
  third: { height: Math.round(CANVAS_H / 3), shift: 600 },
  half: { height: Math.round(CANVAS_H / 2), shift: 900 },
  full: { height: CANVAS_H, shift: 0 },
} as const;
const layoutOf = (i: ShortInsert) => INSERT_LAYOUT[i.layout ?? "third"];

// ч/б профиль (mono-bw): бумага #FFF, чернила #000, акцента-цвета нет
const PAPER = "#FFFFFF";
const INK = "#000000";
const STROKE = {
  WebkitTextStroke: "12px #000",
  paintOrder: "stroke fill",
} as React.CSSProperties;
const OUT_QUINT = Easing.bezier(0.16, 1, 0.3, 1);

// Aggressive punch-zoom on accent words.
const PUNCH_SCALE = 1.18;
const PUNCH_IN = 8;
const PUNCH_HOLD = 26;
const PUNCH_OUT = 16;
const CHUNK = 3; // caption words shown per card

const zoomAt = (frame: number, punches: ShortPunch[]) => {
  let scale = 1;
  let originY = 38;
  for (const p of punches) {
    const end = p.from + PUNCH_IN + PUNCH_HOLD + PUNCH_OUT;
    if (frame >= p.from && frame <= end) {
      const s = interpolate(
        frame,
        [p.from, p.from + PUNCH_IN, p.from + PUNCH_IN + PUNCH_HOLD, end],
        [1, PUNCH_SCALE, PUNCH_SCALE, 1],
        { easing: OUT_QUINT, extrapolateLeft: "clamp", extrapolateRight: "clamp" },
      );
      if (s > scale) {
        scale = s;
        originY = p.originY;
      }
    }
  }
  return { scale, originY };
};

// Active insert (if any) at a given frame, plus its fade envelope (0..1).
// The same envelope drives both the insert's opacity and how far the
// speaker shifts down to stay clear of the full-third insert.
const activeInsertAt = (
  frame: number,
  inserts: ShortInsert[],
): { insert: ShortInsert | null; amount: number } => {
  const active = inserts.filter((i) => frame >= i.from && frame < i.to).slice(-1)[0];
  if (!active) return { insert: null, amount: 0 };
  const dur = active.to - active.from;
  const local = frame - active.from;
  const amount = interpolate(local, [0, 7, dur - 7, dur], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return { insert: active, amount };
};

// b-roll fills the top of the canvas edge-to-edge (no card, no border);
// height comes from the insert's layout: third / half / full-screen.
const InsertTop: React.FC<{ insert: ShortInsert | null; opacity: number }> = ({
  insert,
  opacity,
}) => {
  if (!insert) return null;
  const dur = insert.to - insert.from;
  const file = staticFile(insert.file);
  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        height: layoutOf(insert).height,
        overflow: "hidden",
        opacity,
        backgroundColor: "#17171A",
      }}
    >
      {insert.type === "video" ? (
        <Video
          src={file}
          trimBefore={0}
          trimAfter={dur}
          muted
          objectFit="cover"
          style={{ width: "100%", height: "100%" }}
        />
      ) : (
        <Img
          src={file}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      )}
      {insert.coverBox ? (
        <div
          style={{
            position: "absolute",
            left: `${insert.coverBox.x * 100}%`,
            top: `${insert.coverBox.y * 100}%`,
            width: `${insert.coverBox.w * 100}%`,
            height: `${insert.coverBox.h * 100}%`,
            backdropFilter: "blur(26px)",
            backgroundColor: "rgba(20, 20, 23, 0.55)",
          }}
        />
      ) : null}
    </div>
  );
};

const Captions: React.FC<{ words: ShortWord[] }> = ({ words }) => {
  const frame = useCurrentFrame();
  let ci = -1;
  for (let i = 0; i < words.length; i++) {
    if (words[i].from <= frame) ci = i;
    else break;
  }
  if (ci < 0) return null;
  const start = Math.floor(ci / CHUNK) * CHUNK;
  // only words already spoken (no dim/gray look-ahead)
  const chunk = words.slice(start, ci + 1);

  return (
    <AbsoluteFill
      style={{ justifyContent: "flex-end", alignItems: "center", padding: "0 56px 300px" }}
    >
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          alignItems: "flex-end",
          gap: "0.26em",
          fontFamily: brandFontFamily,
          fontSize: 58,
          lineHeight: 1.04,
          letterSpacing: "0.01em",
          textTransform: "lowercase",
          textAlign: "center",
          maxWidth: "100%",
        }}
      >
        {chunk.map((w, k) => (
          <span
            key={start + k}
            style={{
              // обычное слово: белый с чёрной обводкой; акцент: инверсия (чёрное на белой плашке) + рост
              color: w.accent ? INK : PAPER,
              backgroundColor: w.accent ? PAPER : "transparent",
              padding: w.accent ? "0.04em 0.2em" : 0,
              ...(w.accent ? {} : STROKE),
              transform: w.accent ? "scale(1.14)" : "none",
              transformOrigin: "center bottom",
              overflowWrap: "anywhere",
            }}
          >
            {w.text}
          </span>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const HookPlate: React.FC<{ hook: ShortHook }> = ({ hook }) => {
  const frame = useCurrentFrame();
  if (frame < hook.from || frame >= hook.to) return null;
  const dur = hook.to - hook.from;
  const local = frame - hook.from;
  const opacity = interpolate(local, [0, 6, dur - 8, dur], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const lift = interpolate(local, [0, 10], [24, 0], {
    easing: OUT_QUINT,
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", padding: "170px 64px 0" }}>
      <div
        style={{
          opacity,
          transform: `translateY(${lift}px)`,
          fontFamily: hookFontFamily,
          fontSize: 118,
          lineHeight: 1,
          textTransform: "uppercase",
          textAlign: "center",
          color: PAPER,
          ...STROKE,
          WebkitTextStroke: "16px #000",
        }}
      >
        {hook.text}
      </div>
    </AbsoluteFill>
  );
};

export const Shorts916: React.FC<ShortsProps> = ({
  src,
  previewSrc,
  videoW = DEFAULT_VIDEO_W,
  hook,
  segments,
  words,
  punchZooms,
  inserts,
  audioTrack,
}) => {
  const frame = useCurrentFrame();
  const { scale, originY } = zoomAt(frame, punchZooms);
  const { insert: activeInsert, amount: insertAmount } = activeInsertAt(frame, inserts);
  const speakerSrc =
    previewSrc && !getRemotionEnvironment().isRendering ? previewSrc : src;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <AbsoluteFill
        style={{
          transform: `translateY(${insertAmount * (activeInsert ? layoutOf(activeInsert).shift : 0)}px) scale(${scale})`,
          transformOrigin: `50% ${originY}%`,
        }}
      >
        <Series>
          {segments.map((s, i) => (
            <Series.Sequence
              key={i}
              durationInFrames={Math.max(1, s.endFrame - s.startFrame)}
              premountFor={30}
            >
              <div style={{ position: "absolute", width: videoW, height: CANVAS_H, left: s.tx, top: 0 }}>
                <Video
                  src={staticFile(speakerSrc)}
                  trimBefore={s.startFrame}
                  trimAfter={s.endFrame}
                  muted={audioTrack != null}
                  objectFit="cover"
                  style={{ width: "100%", height: "100%" }}
                />
              </div>
            </Series.Sequence>
          ))}
        </Series>
      </AbsoluteFill>

      <InsertTop insert={activeInsert} opacity={insertAmount} />
      <Captions words={words} />

      {hook ? <HookPlate hook={hook} /> : null}

      {audioTrack ? <Audio src={staticFile(audioTrack)} /> : null}
    </AbsoluteFill>
  );
};
