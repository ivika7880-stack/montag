import { Easing } from "remotion";

// Цвета коллажного стиля. Градиент сэмплирован из кадров референса
// (верх-лево #A91700 → низ почти чёрный). Цвет плашки — ПРИБЛИЗИТЕЛЬНЫЙ
// (оранжево-красный на глаз), сверить с эталоном при доводке.
export const COLLAGE = {
  gradientTop: "#A91700",
  gradientBottom: "#0A0000",
  plate: "#E8502F",
  plateText: "#FFFFFF",
  cream: "#F4EBD8",
  serifOnDark: "#F6EEE3",
  highlight: "#FFE94A",
};

export const OUT_QUINT = Easing.bezier(0.16, 1, 0.3, 1);
