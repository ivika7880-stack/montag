# -*- coding: utf-8 -*-
"""Check an EDL by ear of the ASR: rebuild the cut audio, re-transcribe it, diff against the
expected text (kept words of words.json, minus delete.json).

Catches clipped words, leftovers of deleted takes ("вы уже вы уже") and lost words, none of which
show up in word-timestamp statistics because ASR timings stretch over silence.

Usage: python verify_edl.py <work_dir> [analysis.wav]    # default <work_dir>/audio.wav
Needs DEEPGRAM_API_KEY in .env. Prints every difference with its source-time position.
"""
import difflib
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import requests
import soundfile as sf
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
FADE_S = 0.006
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def norm(w: str) -> str:
    return re.sub(r"[^\w]", "", w.lower())


def main(work: Path, wav: Path) -> None:
    x, sr = sf.read(wav)
    segs = json.loads((work / "edl.json").read_text(encoding="utf-8"))["segments"]
    parts, n = [], int(FADE_S * sr)
    for s in segs:
        a = x[int(s["start"] * sr):int(s["end"] * sr)].copy()
        if len(a) > 2 * n:
            a[:n] *= np.linspace(0, 1, n)
            a[-n:] *= np.linspace(1, 0, n)
        parts.append(a)
    y = np.concatenate(parts)
    tmp = work / "_verify.wav"
    sf.write(tmp, y, sr)
    key = os.environ.get("DEEPGRAM_API_KEY", "x")
    with open(tmp, "rb") as f:
        r = requests.post("https://api.deepgram.com/v1/listen",
                          params={"model": "nova-3", "language": "ru", "smart_format": "true"},
                          headers={"Authorization": f"Token {key}", "Content-Type": "audio/wav"},
                          data=f, timeout=900).json()
    tmp.unlink()
    gw = r["results"]["channels"][0]["alternatives"][0]["words"]
    got = [norm(w["word"]) for w in gw]

    words = json.loads((work / "words.json").read_text(encoding="utf-8"))
    dele = set()
    dj = work / "delete.json"
    if dj.exists():
        for q in json.loads(dj.read_text(encoding="utf-8"))["delete"]:
            dele |= set(range(q["from"], q["to"] + 1))
    exp = [norm(w["w"]) for w in words if w["i"] not in dele]

    def src_t(t):
        acc = 0.0
        for s in segs:
            d = s["end"] - s["start"]
            if t <= acc + d:
                return s["start"] + t - acc
            acc += d
        return segs[-1]["end"]

    sm = difflib.SequenceMatcher(None, exp, got, autojunk=False)
    print(f"cut length {len(y) / sr:.1f}s | expected {len(exp)} words, heard {len(got)} | "
          f"match {sm.ratio() * 100:.1f}%")
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        j = min(max(j1 - 1, 0), len(gw) - 1)
        print(f"  {tag:7s} {exp[i1:i2]} -> {got[j1:j2]}   ~{src_t(gw[j]['start']):.1f}s of source")


if __name__ == "__main__":
    w = Path(sys.argv[1])
    main(w, Path(sys.argv[2]) if len(sys.argv) > 2 else w / "audio.wav")
