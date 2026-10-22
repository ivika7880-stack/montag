import type React from "react";
import { Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { COLLAGE, OUT_QUINT } from "./theme";

// Карточка стопки. Без `src` рисуется серая заглушка с подписью (для проверки в Studio).
export type StackCard = {
  from: number; // кадр композиции, когда карточка влетает
  src?: string; // файл в public/
  label?: string;
};

// Детерминированные повороты/сдвиги: никакого Math.random (кадры должны быть воспроизводимы).
const ROT = [-5, 4, -3, 6, -7, 3, -4, 5];
const DX = [-28, 34, -14, 42, -36, 18, -22, 30];
const DY = [10, -18, 22, -8, 16, -24, 6, -12];

const W = 700;
const H = 880;

export const CardStack: React.FC<{
  cards: StackCard[];
  to: number; // кадр, когда стопка уходит
  centerY?: number; // px от верха холста до центра стопки
}> = ({ cards, to, centerY = 880 }) => {
  const frame = useCurrentFrame();
  const visible = cards.filter((c) => frame >= c.from);
  const outT = interpolate(frame, [to - 8, to], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div style={{ position: "absolute", inset: 0, opacity: outT }}>
      {visible.map((c, i) => {
        const idx = cards.indexOf(c);
        const depth = visible.length - 1 - i; // 0 = верхняя
        const t = interpolate(frame - c.from, [0, 12], [0, 1], {
          extrapolateRight: "clamp",
          easing: OUT_QUINT,
        });
        const rot = ROT[idx % ROT.length] + (1 - t) * 14;
        return (
          <div
            key={idx}
            style={{
              position: "absolute",
              left: (1080 - W) / 2,
              top: centerY - H / 2,
              width: W,
              height: H,
              transform: `translate(${DX[idx % DX.length]}px, ${DY[idx % DY.length] + (1 - t) * 1100}px) rotate(${rot}deg)`,
              background: COLLAGE.cream,
              padding: 18,
              borderRadius: 16,
              boxShadow: "0 24px 60px rgba(0,0,0,0.55)",
              filter: `brightness(${Math.max(0.55, 1 - depth * 0.12)})`,
            }}
          >
            {c.src ? (
              <Img
                src={staticFile(c.src)}
                style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: 6 }}
              />
            ) : (
              <div
                style={{
                  width: "100%",
                  height: "100%",
                  background: "#8c8c8c",
                  borderRadius: 6,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontFamily: "Arial, sans-serif",
                  fontSize: 56,
                  color: "#fff",
                }}
              >
                {c.label ?? `карточка ${idx + 1}`}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
