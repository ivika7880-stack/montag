import type { PlatePhrase } from "./PlateCaptions";

type W = { text: string; from: number; to: number; accent: boolean; brk?: boolean };

const MAX_WORDS = 5; // длиннее плашка не помещается в две строки
const MIN_WORDS = 2; // не оставляем «висячее» одно слово

// Режем поток слов на фразы: по знакам препинания (brk), но не короче MIN_WORDS и не длиннее
// MAX_WORDS. Акцентное слово не идёт в плашку — оно выводится отдельно крупным serif-italic.
export const buildPhrases = (words: W[]): PlatePhrase[] => {
  const groups: W[][] = [];
  let cur: W[] = [];
  words.forEach((w, i) => {
    cur.push(w);
    const left = words.length - 1 - i;
    if (cur.length >= MAX_WORDS || (w.brk && cur.length >= MIN_WORDS && left >= 1)) {
      groups.push(cur);
      cur = [];
    }
  });
  if (cur.length) groups.push(cur);

  const out: PlatePhrase[] = groups.map((part, gi) => {
    const accent = part.find((w) => w.accent);
    const next = groups[gi + 1];
    return {
      text: part.filter((w) => !w.accent).map((w) => w.text).join(" "),
      accent: accent?.text,
      from: part[0].from,
      to: next ? next[0].from : part[part.length - 1].to,
    };
  });
  return out.filter((p) => p.text || p.accent);
};
