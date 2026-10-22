import type React from "react";

// Мелкий вертикальный штамп в левом нижнем углу (как дата с камеры).
// Точный текст в референсе не разобрать — задаётся пропом.
export const VhsStamp: React.FC<{ text: string }> = ({ text }) => (
  <div
    style={{
      position: "absolute",
      left: 34,
      bottom: 150,
      transform: "rotate(-90deg)",
      transformOrigin: "left bottom",
      fontFamily: "'Courier New', monospace",
      fontSize: 26,
      letterSpacing: "0.12em",
      color: "#FF3B22",
      opacity: 0.85,
      whiteSpace: "nowrap",
    }}
  >
    {text}
  </div>
);
