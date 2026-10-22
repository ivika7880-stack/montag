import type React from "react";
import { AbsoluteFill } from "remotion";
import { COLLAGE } from "./theme";
import { VhsStamp } from "./VhsStamp";

// Фон «визуальной» сцены: красно-чёрный градиент по диагонали + виньетка.
// Зерно — статичный feTurbulence (без покадровой анимации, чтобы не мерцало и рендерилось дёшево).
export const RedScene: React.FC<{ stamp?: string; children?: React.ReactNode }> = ({
  stamp,
  children,
}) => (
  <AbsoluteFill
    style={{
      background: `linear-gradient(160deg, ${COLLAGE.gradientTop} 0%, #3A0600 38%, ${COLLAGE.gradientBottom} 78%)`,
    }}
  >
    <AbsoluteFill
      style={{ background: "radial-gradient(ellipse at 50% 55%, transparent 55%, rgba(0,0,0,0.45) 100%)" }}
    />
    <svg
      width="100%"
      height="100%"
      style={{ position: "absolute", inset: 0, opacity: 0.12, mixBlendMode: "overlay" }}
    >
      <filter id="grain">
        <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="3" />
        <feColorMatrix type="saturate" values="0" />
      </filter>
      <rect width="100%" height="100%" filter="url(#grain)" />
    </svg>
    {children}
    {stamp ? <VhsStamp text={stamp} /> : null}
  </AbsoluteFill>
);
