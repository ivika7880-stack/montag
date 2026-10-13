import type React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { brandFontFamily, serifFontFamily } from "../fonts";
import { COLLAGE, OUT_QUINT } from "./theme";

// Фраза: короткий кусок речи (3–6 слов) на оранжевой плашке + необязательное
// акцентное слово крупным serif-italic под плашкой (без плашки).
export type PlatePhrase = {
  text: string;
  from: number; // кадры композиции
  to: number;
  accent?: string;
};

export type PlatePosition = "bottom" | "top-left";

// `lines` режет длинную фразу на две плашки-строки, как в референсе.
const splitLines = (text: string): string[] => {
  const words = text.split(/\s+/);
  if (words.length <= 4) return [text];
  const mid = Math.ceil(words.length / 2);
  return [words.slice(0, mid).join(" "), words.slice(mid).join(" ")];
};

export const PlateCaptions: React.FC<{
  phrases: PlatePhrase[];
  position?: PlatePosition;
}> = ({ phrases, position = "bottom" }) => {
  const frame = useCurrentFrame();
  const p = phrases.find((x) => frame >= x.from && frame < x.to);
  if (!p) return null;
  const local = frame - p.from;
  const appear = interpolate(local, [0, 6], [0, 1], { extrapolateRight: "clamp", easing: OUT_QUINT });
  const accentIn = interpolate(local, [4, 14], [0, 1], { extrapolateRight: "clamp", easing: OUT_QUINT });
  const top = position === "top-left";

  return (
    <div
      style={{
        position: "absolute",
        left: top ? 56 : 0,
        right: top ? 56 : 0,
        top: top ? 150 : undefined,
        bottom: top ? undefined : 330,
        display: "flex",
        flexDirection: "column",
        alignItems: top ? "flex-start" : "center",
        gap: 14,
        opacity: appear,
        transform: `translateY(${(1 - appear) * 14}px)`,
      }}
    >
      {splitLines(p.text).map((line, i) => (
        <span
          key={i}
          style={{
            background: COLLAGE.plate,
            color: COLLAGE.plateText,
            fontFamily: brandFontFamily,
            fontWeight: 700,
            fontSize: 34,
            textTransform: "lowercase",
            padding: "6px 16px",
            lineHeight: 1.15,
          }}
        >
          {line}
        </span>
      ))}
      {p.accent ? (
        <span
          style={{
            fontFamily: serifFontFamily,
            fontStyle: "italic",
            fontWeight: 600,
            fontSize: 84,
            lineHeight: 1,
            color: COLLAGE.serifOnDark,
            textAlign: top ? "left" : "center",
            opacity: accentIn,
            transform: `scale(${0.92 + 0.08 * accentIn})`,
            transformOrigin: top ? "left center" : "center",
            textShadow: "0 2px 18px rgba(0,0,0,0.55)",
          }}
        >
          {p.accent}
        </span>
      ) : null}
    </div>
  );
};
