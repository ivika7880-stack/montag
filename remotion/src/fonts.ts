// Шрифты профиля (ч/б стиль): Unbounded 700 (OFL-1.1) — основной/субтитры, Patsy Sans — заголовки-хуки.
// Регистрация через CSS @font-face (не @remotion/fonts / FontFace.load): Remotion
// пересоздаёт вкладку рендера под давлением памяти @remotion/media, и промисы
// загрузки шрифтов могут зависнуть. CSS-путь рисуется на любой странице без промисов.
//
// Patsy Sans — наклонный, кириллица без заглавных: любой текст выглядит капсом.
// Использовать только для коротких хуков (до 6–8 слов).

import { staticFile } from "remotion";

if (typeof document !== "undefined") {
  const style = document.createElement("style");
  style.textContent =
    `@font-face{font-family:"Unbounded";font-weight:700;` +
    `src:url("${staticFile("Unbounded-cyrillic-700.woff2")}") format("woff2");` +
    `unicode-range:U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116;font-display:block;}` +
    `@font-face{font-family:"Unbounded";font-weight:700;` +
    `src:url("${staticFile("Unbounded-latin-700.woff2")}") format("woff2");` +
    `unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD;font-display:block;}` +
    `@font-face{font-family:"PatsySans";` +
    `src:url("${staticFile("PatsySans.ttf")}") format("truetype");font-display:block;}`;
  document.head.appendChild(style);
}

// Основной шрифт (субтитры, слово за словом) — его импортируют Main169/Shorts916.
export const brandFontFamily = "Unbounded, 'Arial Black', Impact, sans-serif";
// Шрифт заголовков-хуков (плашка в начале ролика).
export const hookFontFamily = "PatsySans, Unbounded, 'Arial Black', Impact, sans-serif";
