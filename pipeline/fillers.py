# -*- coding: utf-8 -*-
"""Find fillers ("ээ", "мм"), breaths and throat sounds that ASR does not write down.

Why: Deepgram skips "ээ" in Russian, so such sounds sit between words and look like speech by
energy. Cutting every loud "gap" would also cut real words the ASR missed (e.g. a whole
"противоположным"), so each candidate is re-checked: its audio is sent to ASR alone; if a word
comes back it is kept, otherwise it is a filler and gets cut.

A "candidate" is a sound run (energy above the breath level) that does not contain the START of
any ASR word (word starts are reliable, word ends are not) and lasts >= MIN_RUN_S.

Usage: python fillers.py <work_dir>        (needs words.json, audio.wav; Deepgram key in .env)
Writes: work/<id>/filler_cuts.json = {"cut": [[t0, t1], ...], "keep": [[t0, t1], ...]}
        edl.py (profile longform) reads it: "cut" ranges are removed, "keep" ranges are protected.
"""
import io
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests
import soundfile as sf
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
SOUND_MARGIN_DB = 24     # sound = noise floor + this (breaths and fillers rise above it)
MERGE_GAP_S = 0.08       # sound runs closer than this are one run
MIN_RUN_S = 0.25         # shorter blips are left to the normal pause logic
CLIP_PAD_S = 0.15
MIN_CONF = 0.5
FILLER_TOKENS = {"э", "ээ", "эээ", "эм", "мм", "ммм", "хм", "а", "м", "ну"}
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def sound_runs(db, thr):
    idx = np.where(db > thr)[0]
    if not idx.size:
        return []
    runs = []
    for part in np.split(idx, np.where(np.diff(idx) > int(MERGE_GAP_S / 0.01))[0] + 1):
        runs.append((part[0] * 0.01, (part[-1] + 1) * 0.01))
    return runs


def asr_words(audio, sr, t0, t1):
    a = audio[int(max(t0, 0) * sr):int(t1 * sr)]
    buf = io.BytesIO()
    sf.write(buf, a, sr, format="WAV", subtype="PCM_16")
    key = os.environ.get("DEEPGRAM_API_KEY", "x")
    r = requests.post("https://api.deepgram.com/v1/listen",
                      params={"model": "nova-3", "language": "ru", "smart_format": "false"},
                      headers={"Authorization": f"Token {key}", "Content-Type": "audio/wav"},
                      data=buf.getvalue(), timeout=120).json()
    ws = r["results"]["channels"][0]["alternatives"][0].get("words", [])
    return [w for w in ws if w.get("confidence", 0) >= MIN_CONF and w["word"].lower().strip(".,!?") not in FILLER_TOKENS]


def main(work):
    words = json.loads((work / "words.json").read_text(encoding="utf-8"))
    audio, sr = sf.read(work / "audio.wav")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    hop = int(sr * 0.01)
    n = (len(audio) - hop) // hop
    rms = np.sqrt((audio[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
    db = 20 * np.log10(rms + 1e-9)
    floor = float(np.percentile(db, 5))
    thr = floor + SOUND_MARGIN_DB
    starts = np.array([w["start"] for w in words])
    first, last = starts.min(), words[-1]["end"]
    cands = []
    for t0, t1 in sound_runs(db, thr):
        if t1 - t0 < MIN_RUN_S or t0 < first - 1 or t1 > last + 1:
            continue
        if ((starts >= t0 - 0.12) & (starts <= t1 + 0.02)).any():   # explained by an ASR word start
            continue
        cands.append((t0, t1))
    print(f"floor {floor:.0f} dBFS, sound above {thr:.0f}; candidates: {len(cands)} "
          f"({sum(b - a for a, b in cands):.0f}s)", file=sys.stderr)

    def check(c):
        t0, t1 = c
        return c, asr_words(audio, sr, t0 - CLIP_PAD_S, t1 + CLIP_PAD_S)

    cut, keep = [], []
    with ThreadPoolExecutor(4) as ex:
        for (t0, t1), ws in ex.map(check, cands):
            (keep if ws else cut).append([round(t0, 3), round(t1, 3)])
            if ws:
                print(f"  keep {t0:.1f}-{t1:.1f}s: {' '.join(w['word'] for w in ws)}", file=sys.stderr)
    (work / "filler_cuts.json").write_text(json.dumps({"cut": cut, "keep": keep}), encoding="utf-8")
    print(f"fillers/breaths to cut: {len(cut)} ({sum(b - a for a, b in cut):.1f}s); words ASR missed, kept: {len(keep)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
