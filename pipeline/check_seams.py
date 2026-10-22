# -*- coding: utf-8 -*-
"""Find cut seams that sit on audible sound (clipped soft word endings / onsets).

For every seam of edl.json, measures the audio on the REMOVED side right at the cut. If it is
above the threshold (default -60 dBFS) and the seam is not next to a word deleted via delete.json,
the cut probably clips something: e.g. the unvoiced end of «находиться», «меняется», «личности»
(-50..-62 dBFS, while the room itself is at -73..-80). Prints the suspicious seams with the
nearest kept word.

Usage: python check_seams.py <work_dir>/ [threshold_dB=-60]
"""
import json
import sys

import numpy as np
import soundfile as sf

W = sys.argv[1]
thr = float(sys.argv[2]) if len(sys.argv) > 2 else -60.0
words = json.load(open(W + "words.json", encoding="utf-8"))
dele = set()
for r in json.load(open(W + "delete.json", encoding="utf-8"))["delete"]:
    dele |= set(range(r["from"], r["to"] + 1))
segs = json.load(open(W + "edl.json", encoding="utf-8"))["segments"]
x, sr = sf.read(W + "audio.wav")


def db(t0, t1):
    a = x[int(max(t0, 0) * sr):int(t1 * sr)]
    return 20 * np.log10(np.sqrt((a ** 2).mean()) + 1e-9) if len(a) else -99


dw = [(k["start"] - 0.1, k["end"] + 0.1) for k in words if k["i"] in dele]
kept = [k for k in words if k["i"] not in dele]
bad = []
for s in segs:
    for t, side in ((s["end"], "end"), (s["start"], "start")):
        d = db(t, t + 0.02) if side == "end" else db(t - 0.02, t)
        if d > thr and not any(a <= t <= b for a, b in dw):
            near = min(kept, key=lambda k: abs((k["end"] if side == "end" else k["start"]) - t))
            bad.append((round(t, 2), side, round(d), near["w"]))
print(f"seams: {2 * len(segs)}; with sound on the removed side (> {thr:.0f} dB): {len(bad)}")
for b in bad:
    print("  ", b)
