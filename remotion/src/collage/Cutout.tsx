import type React from "react";
import { Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { serifFontFamily } from "../fonts";
import { COLLAGE, OUT_QUINT } from "./theme";

// Вырезка: PNG с прозрачным фоном + ч/б + белая «рваная» обводка-стикер.
// Обводка: расширяем альфу (feMorphology), рвём край шумом (feDisplacementMap), заливаем белым.
// Сам PNG с вырезанным фоном готовится заранее (внешний шаг).
export const Cutout: React.FC<{
  src: string;
  from: number;
  to: number;
  caption?: string; // serif-italic подпись над вырезкой (имя)
  width?: number;
  grayscale?: boolean;
}> = ({ src, from, to, caption, width = 860, grayscale = true }) => {
  const frame = useCurrentFrame();
  if (frame < from || frame >= to) return null;
  const local = frame - from;
  const inT = interpolate(local, [0, 12], [0, 1], { extrapolateRight: "clamp", easing: OUT_QUINT });
  const outT = interpolate(frame, [to - 6, to], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fid = "cutout-edge";
  return (
    <div style={{ position: "absolute", inset: 0, opacity: outT }}>
      <svg width="0" height="0" style={{ position: "absolute" }}>
        <filter id={fid} x="-10%" y="-10%" width="120%" height="120%">
          <feMorphology in="SourceAlpha" operator="dilate" radius="14" result="grow" />
          <feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed="7" result="noise" />
          <feDisplacementMap in="grow" in2="noise" scale="16" result="rough" />
          <feFlood floodColor="#fff" result="white" />
          <feComposite in="white" in2="rough" operator="in" result="outline" />
          <feMerge>
            <feMergeNode in="outline" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </svg>
      {caption ? (
        <div
          style={{
            position: "absolute",
            top: 360,
            left: 72,
            fontFamily: serifFontFamily,
            fontStyle: "italic",
            fontWeight: 600,
            fontSize: 108,
            lineHeight: 1,
            color: COLLAGE.serifOnDark,
            opacity: inT,
            textShadow: "0 2px 18px rgba(0,0,0,0.55)",
          }}
        >
          {caption}
        </div>
      ) : null}
      <div
        style={{
          position: "absolute",
          left: (1080 - width) / 2,
          bottom: 0,
          width,
          transform: `translateY(${(1 - inT) * 160}px) scale(${0.94 + 0.06 * inT})`,
          transformOrigin: "50% 100%",
          filter: `url(#${fid}) ${grayscale ? "grayscale(1) contrast(1.08)" : ""}`,
        }}
      >
        <Img src={staticFile(src)} style={{ width: "100%", display: "block" }} />
      </div>
    </div>
  );
};
