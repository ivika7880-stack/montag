# -*- coding: utf-8 -*-
"""Assemble Remotion input props from edl.json + faces.json + accents.json + inserts.json.

Maps source-time events (accent words, face positions, insert anchor phrases)
onto the OUTPUT timeline (after cuts) and generates:
- the zoom plan (slow push-ins on long segments, punch-ins on accents);
- the insert plan: each insert (b-roll png/mp4) shown fullscreen while its
  anchor phrase sounds, with the speaker shrunk into a bottom-left PiP card.
  Accents always win: insert windows are trimmed around accent blocks, so the
  speaker returns to centre for the accent. mp4 inserts are capped at their own
  length. Adjacent insert windows are merged into single PiP windows so the
  speaker card stays up while the fullscreen graphic swaps.

Usage: python props.py <work_dir> <out_props.json>
"""
import json
import subprocess
import sys
from pathlib import Path

PUNCH_SCALE = 1.30
PUSH_SCALE = 1.07
PUNCH_IN_F = 18
PUNCH_HOLD_F = 36
PUNCH_OUT_F = 24
ACCENT_DUR_F = 66      # how long the accent caption stays (2.2 s)

INSERT_DIR = "inserts"     # under remotion/public
MIN_INSERT_F = 18          # drop insert fragments shorter than this (0.6 s)
PIP_MERGE_GAP_F = 18       # merge PiP windows closer than this (keep card up)
ACCENT_PAD_F = 8           # guard band around an accent's punch-zoom window


def probe_frames(path: Path, fps: float) -> int:
    dur = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        text=True,
    ).strip()
    return int(round(float(dur) * fps))


def subtract_blocks(span, blocks):
    """Remove every (a0,a1) block from [s0,s1); return list of remaining pieces."""
    pieces = [span]
    for a0, a1 in blocks:
        nxt = []
        for s0, s1 in pieces:
            if a1 <= s0 or a0 >= s1:      # no overlap
                nxt.append((s0, s1))
                continue
            if a0 > s0:
                nxt.append((s0, min(a0, s1)))
            if a1 < s1:
                nxt.append((max(a1, s0), s1))
        pieces = nxt
    return pieces


def merge_windows(wins, gap):
    wins = sorted(wins)
    out = []
    for s, e in wins:
        if out and s - out[-1][1] <= gap:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def load(work: Path, name: str):
    return json.loads((work / name).read_text(encoding="utf-8"))


def build(work: Path, out_path: Path, media: str = "source"):
    edl = load(work, "edl.json")
    faces = load(work, "faces.json")
    accents = load(work, "accents.json")["accents"]
    words = {w["i"]: w for w in load(work, "words.json")}
    fps = edl["fps"]
    segments = edl["segments"]

    def to_output_frame(src_t: float):
        """Map a source timestamp to an output frame; None if it was cut."""
        acc = 0.0
        for s in segments:
            if s["start"] <= src_t <= s["end"]:
                return int(round((acc + (src_t - s["start"])) * fps))
            acc += s["end"] - s["start"]
        return None

    def nearest_output_frame(src_t: float):
        """Like to_output_frame, but clamp a cut timestamp to the nearest kept edge."""
        f = to_output_frame(src_t)
        if f is not None:
            return f
        acc = 0.0
        best_f, best_d = 0, float("inf")
        for s in segments:
            for edge in (s["start"], s["end"]):
                d = abs(edge - src_t)
                if d < best_d:
                    best_d = d
                    best_f = int(round((acc + (edge - s["start"])) * fps))
            acc += s["end"] - s["start"]
        return best_f

    def face_at(src_t: float):
        best = min(
            (f for f in faces if f["found"]),
            key=lambda f: abs(f["t"] - src_t),
            default=None,
        )
        if not best:
            return {"x": 50.0, "y": 40.0}
        b = best["box"]
        return {
            "x": round((b["x"] + b["w"] / 2) * 100, 1),
            "y": round((b["y"] + b["h"] / 2) * 100, 1),
        }

    accent_events = []
    zooms = []
    for a in accents:
        w = words[a["word"]]
        frame = to_output_frame(w["start"])
        if frame is None:
            print(f"WARN accent word {a['word']} '{w['w']}' was cut, skipped")
            continue
        origin = face_at(w["start"])
        accent_events.append(
            {"text": a["text"], "frame": frame, "durationInFrames": ACCENT_DUR_F}
        )
        zooms.append(
            {
                "from": frame - 6,
                "inF": PUNCH_IN_F,
                "holdF": PUNCH_HOLD_F,
                "outF": PUNCH_OUT_F,
                "scale": PUNCH_SCALE,
                "originX": origin["x"],
                "originY": origin["y"],
            }
        )

    # slow push-ins on long segments (skipped where a punch zoom overlaps)
    acc = 0.0
    pushes = []
    for s in segments:
        seg_len = s["end"] - s["start"]
        f0 = int(round(acc * fps))
        f1 = int(round((acc + seg_len) * fps))
        if seg_len > 6.0:
            mid_src = (s["start"] + s["end"]) / 2
            origin = face_at(mid_src)
            overlap = any(
                z["from"] < f1 and (z["from"] + z["inF"] + z["holdF"] + z["outF"]) > f0
                for z in zooms
            )
            if not overlap:
                pushes.append(
                    {
                        "from": f0,
                        "to": f1,
                        "scale": PUSH_SCALE,
                        "originX": origin["x"],
                        "originY": origin["y"],
                    }
                )
        acc += seg_len

    # ---- inserts (b-roll) ----------------------------------------------------
    # Accent blocks the speaker must stay centred through (the punch-zoom window).
    accent_blocks = [
        (z["from"] - ACCENT_PAD_F,
         z["from"] + z["inF"] + z["holdF"] + z["outF"] + ACCENT_PAD_F)
        for z in zooms
    ]
    public_inserts = out_path.parent.parent / "public" / INSERT_DIR
    insert_events = []
    pip_base = []
    inserts_file = work / "inserts.json"
    if inserts_file.exists():
        insert_defs = json.loads(inserts_file.read_text(encoding="utf-8"))["inserts"]
        media_cache = {}
        for ins in insert_defs:
            w0 = words.get(ins["anchorWord"])
            w1 = words.get(ins["endWord"])
            if not w0 or not w1:
                print(f"WARN insert {ins['file']}: anchor/end word missing, skipped")
                continue
            f0 = nearest_output_frame(w0["start"])
            f1 = nearest_output_frame(w1["end"])
            if f1 <= f0:
                print(f"WARN insert {ins['file']}: empty span after cuts, skipped")
                continue
            is_video = ins["file"].lower().endswith((".mp4", ".mov", ".webm"))
            if is_video:
                path = public_inserts / ins["file"]
                if not path.exists():
                    print(f"WARN insert {ins['file']}: file not in public/{INSERT_DIR}, skipped")
                    continue
                if ins["file"] not in media_cache:
                    media_cache[ins["file"]] = probe_frames(path, fps)
                f1 = min(f1, f0 + media_cache[ins["file"]])
            # accents win: keep the longest sub-span not covered by an accent
            pieces = [p for p in subtract_blocks((f0, f1), accent_blocks)
                      if p[1] - p[0] >= MIN_INSERT_F]
            if not pieces:
                print(f"WARN insert {ins['file']}: fully covered by accents, skipped")
                continue
            s0, s1 = max(pieces, key=lambda p: p[1] - p[0])
            insert_events.append({
                "file": f"{INSERT_DIR}/{ins['file']}",
                "type": "video" if is_video else "image",
                "startFrame": s0,
                "endFrame": s1,
            })
            pip_base.append((s0, s1))

    insert_events.sort(key=lambda e: e["startFrame"])
    pip_windows = [
        {"start": s, "end": e} for s, e in merge_windows(pip_base, PIP_MERGE_GAP_F)
    ]

    preview_proxy = out_path.parent.parent / "public" / f"{media}_preview.mp4"
    props = {
        "src": f"{media}.mp4",
        "previewSrc": f"{media}_preview.mp4" if preview_proxy.exists() else None,
        "fps": fps,
        "segments": segments,
        "accents": accent_events,
        "punchZooms": zooms,
        "pushZooms": pushes,
        "inserts": insert_events,
        "pipWindows": pip_windows,
        "music": None,
        "audioTrack": None,   # set by audio.py (de-clicked speaker track); run it after props.py
        # frame-exact composition length = actual <Series> length = audio-track length.
        # (round(kept_duration*fps) drifts a few frames vs Σ(endFrame-startFrame) over many cuts.)
        "totalDurationInFrames": sum(s["endFrame"] - s["startFrame"] for s in segments),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(props, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"OK frames={props['totalDurationInFrames']} accents={len(accent_events)} "
        f"punch={len(zooms)} push={len(pushes)} inserts={len(insert_events)} "
        f"pip={len(pip_windows)}"
    )


if __name__ == "__main__":
    media = sys.argv[3] if len(sys.argv) > 3 else "source"
    build(Path(sys.argv[1]), Path(sys.argv[2]), media)
