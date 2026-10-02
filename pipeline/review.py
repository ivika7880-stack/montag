# -*- coding: utf-8 -*-
"""Render delete.json + words.json into a human-readable review file.

Usage: python review.py <work_dir>
Writes <work_dir>/REVIEW.md
"""
import json
import sys
from pathlib import Path

work = Path(sys.argv[1])
words = {w["i"]: w for w in json.loads((work / "words.json").read_text(encoding="utf-8"))}
spec = json.loads((work / "delete.json").read_text(encoding="utf-8"))
edl = json.loads((work / "edl.json").read_text(encoding="utf-8"))


def fmt_t(sec):
    m, s = divmod(int(sec), 60)
    return f"{m:02d}:{s:02d}"


lines = [f"# Ревью вырезок — {work.name}", ""]
lines.append(
    f"Исходник {fmt_t(edl['source_duration'])} -> итог {fmt_t(edl['kept_duration'])} "
    f"({len(edl['segments'])} сегментов). Ниже — что вырезано и почему.\n"
)
lines.append("| # | Таймкод | Вырезанный текст | Причина |")
lines.append("|---|---------|------------------|---------|")
for n, d in enumerate(spec["delete"], 1):
    ws = [words[i] for i in range(d["from"], d["to"] + 1) if i in words]
    text = " ".join(w["w"] for w in ws)
    if len(text) > 120:
        text = text[:60] + " … " + text[-55:]
    t0, t1 = ws[0]["start"], ws[-1]["end"]
    lines.append(f"| {n} | {fmt_t(t0)}–{fmt_t(t1)} | {text} | {d['reason']} |")

lines.append("")
lines.append("Плюс автоматика: паузы длиннее 0.5 с сжаты до ~0.35 с; тишина в начале/конце обрезана.")
(work / "REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
print("OK", work / "REVIEW.md")
