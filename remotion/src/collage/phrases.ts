import type { PlatePhrase } from "./PlateCaptions";

type W = { text: string; from: number; to: number; accent: boolean };

// Режем поток слов на фразы по CHUNK слов для плашек. Акцентное слово не идёт в плашку —
// оно выводится отдельно крупным serif-italic (как в референсе).
export const buildPhrases = (words: W[], chunk = 4): PlatePhrase[] => {
  const out: PlatePhrase[] = [];
  for (let i = 0; i < words.length; i += chunk) {
    const part = words.slice(i, i + chunk);
    const accent = part.find((w) => w.accent);
    const plain = part.filter((w) => !w.accent).map((w) => w.text);
    const next = words[i + chunk];
    const last = part[part.length - 1];
    out.push({
      text: plain.join(" "),
      accent: accent?.text,
      from: part[0].from,
      to: next ? next.from : last.to,
    });
  }
  return out.filter((p) => p.text || p.accent);
};
