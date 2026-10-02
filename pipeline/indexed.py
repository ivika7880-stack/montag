# -*- coding: utf-8 -*-
"""Dump words.json as compact indexed text for LLM markup.

Usage: python indexed.py <work_dir>
Writes <work_dir>/indexed.txt: lines of "i:word" tokens, 12 per line,
with a timestamp marker at the start of each line.
"""
import json
import sys
from pathlib import Path

work = Path(sys.argv[1])
words = json.loads((work / "words.json").read_text(encoding="utf-8"))

lines = []
for chunk_start in range(0, len(words), 12):
    chunk = words[chunk_start : chunk_start + 12]
    t = chunk[0]["start"]
    toks = " ".join(f"{w['i']}:{w['w']}" for w in chunk)
    lines.append(f"[{t:7.1f}] {toks}")

(work / "indexed.txt").write_text("\n".join(lines), encoding="utf-8")
print(f"OK lines={len(lines)}")
