# -*- coding: utf-8 -*-
"""Build an EDL (keep-segments) from words.json + delete.json.

Three cut passes:
1. deleted word runs — boundaries snapped to local RMS-energy minima in the
   corridor between kept speech and deleted speech, so kept words never clip;
2. pause compression — any gap between kept words longer than MAX_PAUSE_S is
   shrunk to KEEP_TAIL_S + KEEP_HEAD_S;
3. head/tail trim — silence before the first and after the last kept word.

Usage: python edl.py <work_dir> <audio.wav> [fps]
Reads:  <work_dir>/words.json, <work_dir>/delete.json
Writes: <work_dir>/edl.json

delete.json format:
{"delete": [{"from": <word idx>, "to": <word idx>, "reason": "..."}]}
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

HOP_S = 0.004          # RMS grid step, 4 ms
WIN_S = 0.020          # RMS window, 20 ms
SEARCH_PAD_S = 0.150   # how far around a boundary we search for silence
MIN_GAP_S = 0.024      # if boundary corridor is narrower, use its midpoint
MERGE_S = 0.040        # merge keep-segments separated by less than this
MIN_KEEP_S = 0.060     # drop keep-segments shorter than this (short words between cuts must survive)
# Tight jump-cut profile (micro-pauses go too): every gap longer than MAX_PAUSE_S is cut
# down to KEEP_TAIL_S + KEEP_HEAD_S (~80 ms of air), snapped to real silence in the audio.
MAX_PAUSE_S = 0.12     # gaps between kept words longer than this get shrunk
KEEP_TAIL_S = 0.04     # air left after a kept word
KEEP_HEAD_S = 0.04     # air left before the next kept word
# Audio-based tightening: ASR word edges can stretch over silence (a word "lasting" seconds),
# so after the word-based cuts every real silent stretch inside a kept segment is cut as well.
SIL_RMS = 0.0056       # RMS (~-45 dBFS) below which audio counts as a candidate silence
DEEP_RMS = 0.0013      # RMS (~-58 dBFS): a dip whose MEDIAN is below it is a real pause (digital quiet)
MIN_SILENCE_S = 0.10   # shortest REAL pause that gets cut
MIN_SHALLOW_S = 0.22   # shallow dips (never reach DEEP_RMS) are plosive closures / breaths: cut only if long
AIR_S = 0.04           # air kept on each side of a cut silence (~80 ms between words)
EDGE_LOUD_RMS = 0.006  # RMS (~-44 dBFS) above which a cut edge would be inside speech
EDGE_SHIFT_MAX_S = 0.12  # max distance a cut edge may be pushed away from a word to dodge speech
# ASR sometimes drops a word entirely; its audio then sits inside a "gap" between kept words.
# Speech-level audio inside a gap is protected, only the real silence around it is cut.
SPEECH_RMS = 0.010     # RMS (~-40 dBFS) counted as speech inside a gap
SPEECH_MIN_S = 0.06    # shortest loud stretch that counts as an untranscribed word
SPEECH_PAD_S = 0.05    # air kept around such a stretch
HEAD_LEAD_S = 0.30     # silence kept before the very first word
TAIL_LEAD_S = 0.80     # silence kept after the very last word


def rms_curve(wav_path: Path):
    audio, sr = sf.read(wav_path, dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    hop = int(sr * HOP_S)
    win = int(sr * WIN_S)
    n = max(0, (len(audio) - win) // hop)
    idx = np.arange(n)[:, None] * hop + np.arange(win)[None, :]
    frames = audio[idx]
    rms = np.sqrt((frames ** 2).mean(axis=1))
    times = (np.arange(n) * hop + win // 2) / sr
    return times, rms, len(audio) / sr


def quietest_point(times, rms, lo, hi):
    """Time of minimal RMS inside [lo, hi]; midpoint if corridor is too narrow."""
    if hi - lo < MIN_GAP_S:
        return (lo + hi) / 2
    mask = (times >= lo) & (times <= hi)
    if not mask.any():
        return (lo + hi) / 2
    seg_t = times[mask]
    seg_r = rms[mask]
    return float(seg_t[int(np.argmin(seg_r))])


def rms_at(times, rms, t):
    return float(rms[int(np.argmin(np.abs(times - t)))])


def safe_cut(times, rms, a_end, b_start):
    """Cut the gap between two kept words down to KEEP_TAIL_S + KEEP_HEAD_S of air.

    ASR word edges are only approximate (they can overlap the neighbour or end early), so each
    edge is nudged away from the word while the audio right next to it is still loud.
    """
    cs, ce = a_end + KEEP_TAIL_S, b_start - KEEP_HEAD_S
    limit = EDGE_SHIFT_MAX_S
    while limit > 0 and cs < ce and rms_at(times, rms, cs - 0.012) > EDGE_LOUD_RMS:
        cs += HOP_S
        limit -= HOP_S
    limit = EDGE_SHIFT_MAX_S
    while limit > 0 and ce > cs and rms_at(times, rms, ce + 0.012) > EDGE_LOUD_RMS:
        ce -= HOP_S
        limit -= HOP_S
    return [cs, ce]


def gap_cuts(times, rms, a_end, b_start):
    """Cut intervals for the gap between two kept words, never through untranscribed speech."""
    idx = np.where((times >= a_end) & (times <= b_start) & (rms > SPEECH_RMS))[0]
    zones = []
    if idx.size:
        for run in np.split(idx, np.where(np.diff(idx) > 1)[0] + 1):
            t0, t1 = float(times[run[0]]), float(times[run[-1]])
            if t1 - t0 >= SPEECH_MIN_S:
                zones.append([t0 - SPEECH_PAD_S, t1 + SPEECH_PAD_S])
    zones = merge_intervals(zones)
    cuts, cursor = [], a_end
    for z0, z1 in zones + [[b_start, b_start]]:
        if z0 - cursor > MAX_PAUSE_S:
            cuts.append(safe_cut(times, rms, cursor, z0))
        cursor = max(cursor, z1)
    return cuts


def tighten(keeps, times, rms):
    """Cut every silent run >= MIN_SILENCE_S inside the keep segments, leaving AIR_S on each side."""
    out = []
    for s, e in keeps:
        idx = np.where((times >= s) & (times <= e) & (rms < SIL_RMS))[0]
        cur = s
        if idx.size:
            for run in np.split(idx, np.where(np.diff(idx) > 1)[0] + 1):
                r0, r1 = float(times[run[0]]), float(times[run[-1]])
                deep = float(np.median(rms[run])) < DEEP_RMS
                if r1 - r0 < (MIN_SILENCE_S if deep else MIN_SHALLOW_S):
                    continue
                cs, ce = max(r0, s) + AIR_S, min(r1, e) - AIR_S
                if ce - cs >= MERGE_S:
                    if cs > cur:
                        out.append([cur, cs])
                    cur = ce
        if e > cur:
            out.append([cur, e])
    return [seg for seg in out if seg[1] - seg[0] >= MIN_KEEP_S]


def merge_intervals(intervals):
    merged = []
    for s, e in sorted(intervals):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def build_edl(work_dir: Path, wav_path: Path, fps: float = 30.0):
    words = json.loads((work_dir / "words.json").read_text(encoding="utf-8"))
    spec = json.loads((work_dir / "delete.json").read_text(encoding="utf-8"))

    deleted = set()
    for d in spec["delete"]:
        deleted.update(range(d["from"], d["to"] + 1))

    times, rms, total = rms_curve(wav_path)
    kept_words = [w for w in words if w["i"] not in deleted]

    cut_intervals = []

    # --- pass 1: deleted word runs ---
    run = []
    runs = []
    for w in words:
        if w["i"] in deleted:
            run.append(w)
        elif run:
            runs.append(run)
            run = []
    if run:
        runs.append(run)

    for r in runs:
        first, last = r[0], r[-1]
        prev_kept_end = 0.0
        next_kept_start = total
        for w in reversed(words[: first["i"]]):
            if w["i"] not in deleted:
                prev_kept_end = w["end"]
                break
        for w in words[last["i"] + 1:]:
            if w["i"] not in deleted:
                next_kept_start = w["start"]
                break
        # ASR word ENDS are unreliable (they stretch over silence and overlap the next take),
        # word STARTS are not: look for the quietest point just around the first deleted word's
        # start and just before the next kept word's start, ignoring the neighbours' ends.
        cut_start = quietest_point(times, rms, first["start"] - SEARCH_PAD_S, first["start"] + 0.03)
        lo2 = max(last["start"] + 0.05, next_kept_start - SEARCH_PAD_S)
        cut_end = quietest_point(times, rms, lo2, next_kept_start)
        if cut_end > cut_start:
            cut_intervals.append([cut_start, cut_end])

    # --- pass 2: pause compression between kept words ---
    for a, b in zip(kept_words, kept_words[1:]):
        gap = b["start"] - a["end"]
        if gap > MAX_PAUSE_S:
            cut_intervals.extend(gap_cuts(times, rms, a["end"], b["start"]))

    # --- pass 3: head/tail trim ---
    if kept_words:
        first_start = kept_words[0]["start"]
        last_end = kept_words[-1]["end"]
        if first_start - HEAD_LEAD_S > 0:
            cut_intervals.append([0.0, first_start - HEAD_LEAD_S])
        if last_end + TAIL_LEAD_S < total:
            cut_intervals.append([last_end + TAIL_LEAD_S, total])

    cut_intervals = merge_intervals(cut_intervals)

    # complement -> keep segments
    keeps = []
    cursor = 0.0
    for cs, ce in cut_intervals:
        if cs > cursor:
            keeps.append([cursor, cs])
        cursor = max(cursor, ce)
    if cursor < total:
        keeps.append([cursor, total])

    merged = []
    for seg in keeps:
        if merged and seg[0] - merged[-1][1] < MERGE_S:
            merged[-1][1] = seg[1]
        elif seg[1] - seg[0] >= MIN_KEEP_S:
            merged.append(seg)

    merged = tighten(merged, times, rms)

    out = {
        "fps": fps,
        "source_duration": round(total, 3),
        "kept_duration": round(sum(e - s for s, e in merged), 3),
        "segments": [
            {
                "start": round(s, 3),
                "end": round(e, 3),
                "startFrame": int(round(s * fps)),
                "endFrame": int(round(e * fps)),
            }
            for s, e in merged
        ],
    }
    (work_dir / "edl.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    removed = out["source_duration"] - out["kept_duration"]
    print(
        f"OK segments={len(merged)} kept={out['kept_duration']:.1f}s "
        f"removed={removed:.1f}s ({removed / out['source_duration'] * 100:.1f}%)"
    )


if __name__ == "__main__":
    fps = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0
    build_edl(Path(sys.argv[1]), Path(sys.argv[2]), fps)
