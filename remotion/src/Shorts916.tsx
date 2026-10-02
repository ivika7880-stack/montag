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
import { brandFontFamily } from "./fonts";

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

export type ShortsProps = {
  src: string;
  previewSrc: string | null;
  fps: number;
  segments: ShortSeg[];
  words: ShortWord[];
  punchZooms: ShortPunch[];
  inserts: ShortInsert[];
  audioTrack: string | null;
  totalDurationInFrames: number;
};

const CANVAS_H = 1920;
const VIDEO_W = Math.round((CANVAS_H * 16) / 9); // 3413: source scaled to fill height
// Per-layout insert height and how far the speaker shifts down to stay clear.
// "full" covers the speaker entirely (voice keeps playing) — no shift needed.
const INSERT_LAYOUT = {
  third: { height: Math.round(CANVAS_H / 3), shift: 600 },
  half: { height: Math.round(CANVAS_H / 2), shift: 900 },
  full: { height: CANVAS_H, shift: 0 },
} as const;
const layoutOf = (i: ShortInsert) => INSERT_LAYOUT[i.layout ?? "third"];

const PAPER = "#F5F5F5";
const SCARLET = "#E5484D";
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
          textTransform: "uppercase",
          textAlign: "center",
          maxWidth: "100%",
        }}
      >
        {chunk.map((w, k) => (
          <span
            key={start + k}
            style={{
              color: w.accent ? SCARLET : PAPER,
              transform: w.accent ? "scale(1.14)" : "none",
              transformOrigin: "center bottom",
              overflowWrap: "anywhere",
              textShadow: "0 6px 30px rgba(0,0,0,0.7), 0 2px 6px rgba(0,0,0,0.6)",
            }}
          >
            {w.text}
          </span>
        ))}
      </div>
    </AbsoluteFill>
  );
};

export const Shorts916: React.FC<ShortsProps> = ({
  src,
  previewSrc,
  segments,
  words,
  punchZooms,
  inserts,
  audioTrack,
  totalDurationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { scale, originY } = zoomAt(frame, punchZooms);
  const { insert: activeInsert, amount: insertAmount } = activeInsertAt(frame, inserts);
  const speakerSrc =
    previewSrc && !getRemotionEnvironment().isRendering ? previewSrc : src;
  const progress = interpolate(frame, [0, totalDurationInFrames], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

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
              <div style={{ position: "absolute", width: VIDEO_W, height: CANVAS_H, left: s.tx, top: 0 }}>
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

      {/* progress bar */}
      <div style={{ position: "absolute", top: 0, left: 0, height: 8, width: `${progress}%`, backgroundColor: SCARLET }} />

      {audioTrack ? <Audio src={staticFile(audioTrack)} /> : null}
    </AbsoluteFill>
  );
};
