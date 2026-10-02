import React from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  Sequence,
  Series,
  getRemotionEnvironment,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { Audio, Video } from "@remotion/media";
import { brandFontFamily } from "./fonts";

export type Seg = {
  start: number;
  end: number;
  startFrame: number;
  endFrame: number;
};
export type Accent = { text: string; frame: number; durationInFrames: number };
export type Punch = {
  from: number;
  inF: number;
  holdF: number;
  outF: number;
  scale: number;
  originX: number;
  originY: number;
};
export type Push = {
  from: number;
  to: number;
  scale: number;
  originX: number;
  originY: number;
};
export type Insert = {
  file: string;
  type: "image" | "video";
  startFrame: number;
  endFrame: number;
};
export type PipWindow = { start: number; end: number };

export type MainProps = {
  src: string;
  previewSrc: string | null;
  fps: number;
  segments: Seg[];
  accents: Accent[];
  punchZooms: Punch[];
  pushZooms: Push[];
  inserts: Insert[];
  pipWindows: PipWindow[];
  music: string | null;
  audioTrack: string | null;
  totalDurationInFrames: number;
};

const OUT_QUINT = Easing.bezier(0.16, 1, 0.3, 1);
const CHAR_FRAMES = 2;

// Speaker PiP card geometry (canvas is 1920x1080).
const CANVAS_W = 1920;
const CANVAS_H = 1080;
const CARD_W = 480;
const CARD_H = 270;
const CARD_MARGIN = 60;
const PIP_FLIGHT_F = 16; // ~0.53 s flight in/out

// How much of the speaker card is deployed at a given frame: 0 = fullscreen
// centre, 1 = docked bottom-left card. Ramps up/down at each PiP window edge.
const pipProgressAt = (frame: number, windows: PipWindow[]) => {
  let p = 0;
  for (const w of windows) {
    if (frame < w.start || frame > w.end) continue;
    const up = interpolate(frame, [w.start, w.start + PIP_FLIGHT_F], [0, 1], {
      easing: OUT_QUINT,
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    const down = interpolate(frame, [w.end - PIP_FLIGHT_F, w.end], [1, 0], {
      easing: OUT_QUINT,
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    p = Math.max(p, Math.min(up, down));
  }
  return p;
};

const InsertLayer: React.FC<{ insert: Insert }> = ({ insert }) => {
  const frame = useCurrentFrame();
  const dur = insert.endFrame - insert.startFrame;
  const opacity = interpolate(
    frame,
    [0, PIP_FLIGHT_F, dur - 8, dur],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const file = staticFile(insert.file);
  return (
    <AbsoluteFill style={{ backgroundColor: "#17171A", opacity }}>
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
        <>
          <Img
            src={file}
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
              filter: "blur(28px)",
              transform: "scale(1.12)",
              opacity: 0.5,
            }}
          />
          <Img
            src={file}
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "contain",
            }}
          />
        </>
      )}
    </AbsoluteFill>
  );
};

const zoomAt = (frame: number, punch: Punch[], push: Push[]) => {
  let scale = 1;
  let originX = 50;
  let originY = 40;
  for (const p of push) {
    if (frame >= p.from && frame <= p.to) {
      scale = interpolate(frame, [p.from, p.to], [1, p.scale], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      originX = p.originX;
      originY = p.originY;
    }
  }
  for (const p of punch) {
    const end = p.from + p.inF + p.holdF + p.outF;
    if (frame >= p.from && frame <= end) {
      const s = interpolate(
        frame,
        [p.from, p.from + p.inF, p.from + p.inF + p.holdF, end],
        [1, p.scale, p.scale, 1],
        {
          easing: OUT_QUINT,
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        },
      );
      if (s > scale) {
        scale = s;
        originX = p.originX;
        originY = p.originY;
      }
    }
  }
  return { scale, originX, originY };
};

const AccentCaption: React.FC<{ text: string; durationInFrames: number }> = ({
  text,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const typed = Math.min(text.length, Math.floor(frame / CHAR_FRAMES) + 1);
  const opacity = interpolate(
    frame,
    [durationInFrames - 8, durationInFrames - 1],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  return (
    <AbsoluteFill
      style={{ justifyContent: "flex-end", alignItems: "center", opacity }}
    >
      <div
        style={{
          marginBottom: 96,
          fontFamily: brandFontFamily,
          fontSize: 81,
          color: "#F5F5F5",
          letterSpacing: "0.04em",
          whiteSpace: "pre",
          textShadow: "0 4px 28px rgba(0,0,0,0.6), 0 1px 4px rgba(0,0,0,0.5)",
        }}
      >
        {text.slice(0, typed)}
      </div>
      {Array.from(text).map((ch, i) =>
        ch === " " || i >= Math.ceil(durationInFrames / CHAR_FRAMES) ? null : (
          <Sequence
            key={i}
            from={i * CHAR_FRAMES}
            durationInFrames={4}
            layout="none"
          >
            <Audio src={staticFile("key.wav")} volume={0.5} />
          </Sequence>
        ),
      )}
    </AbsoluteFill>
  );
};

export const Main169: React.FC<MainProps> = ({
  src,
  previewSrc,
  segments,
  accents,
  punchZooms,
  pushZooms,
  inserts,
  pipWindows,
  music,
  audioTrack,
}) => {
  const frame = useCurrentFrame();
  const { scale, originX, originY } = zoomAt(frame, punchZooms, pushZooms);

  // Studio previews the lightweight proxy for smooth playback; the final
  // render always uses the sharp all-intra source.
  const speakerSrc =
    previewSrc && !getRemotionEnvironment().isRendering ? previewSrc : src;

  const p = pipProgressAt(frame, pipWindows);
  const cardLeft = interpolate(p, [0, 1], [0, CARD_MARGIN]);
  const cardTop = interpolate(p, [0, 1], [0, CANVAS_H - CARD_H - CARD_MARGIN]);
  const cardWidth = interpolate(p, [0, 1], [CANVAS_W, CARD_W]);
  const cardHeight = interpolate(p, [0, 1], [CANVAS_H, CARD_H]);
  const cardRadius = interpolate(p, [0, 1], [0, 20]);
  const edge = interpolate(p, [0, 0.4, 1], [0, 0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#17171A" }}>
      {inserts.map((ins, i) => (
        <Sequence
          key={i}
          from={ins.startFrame}
          durationInFrames={Math.max(1, ins.endFrame - ins.startFrame)}
          premountFor={30}
        >
          <InsertLayer insert={ins} />
        </Sequence>
      ))}
      <div
        style={{
          position: "absolute",
          left: cardLeft,
          top: cardTop,
          width: cardWidth,
          height: cardHeight,
          borderRadius: cardRadius,
          overflow: "hidden",
          border: `2px solid rgba(255,255,255,${0.16 * edge})`,
          boxShadow: `0 16px 48px rgba(0,0,0,${0.5 * edge})`,
        }}
      >
        <AbsoluteFill
          style={{
            transform: `scale(${scale})`,
            transformOrigin: `${originX}% ${originY}%`,
          }}
        >
          <Series>
            {segments.map((s, i) => (
              <Series.Sequence
                key={i}
                durationInFrames={Math.max(1, s.endFrame - s.startFrame)}
                premountFor={30}
              >
                <Video
                  src={staticFile(speakerSrc)}
                  trimBefore={s.startFrame}
                  trimAfter={s.endFrame}
                  muted={audioTrack != null}
                  objectFit="cover"
                  style={{ width: "100%", height: "100%" }}
                />
              </Series.Sequence>
            ))}
          </Series>
        </AbsoluteFill>
      </div>
      {accents.map((a, i) => (
        <Sequence
          key={i}
          from={a.frame}
          durationInFrames={a.durationInFrames}
          layout="none"
        >
          <AccentCaption text={a.text} durationInFrames={a.durationInFrames} />
        </Sequence>
      ))}
      {audioTrack ? <Audio src={staticFile(audioTrack)} /> : null}
      {music ? <Audio src={staticFile(music)} volume={0.12} /> : null}
    </AbsoluteFill>
  );
};
