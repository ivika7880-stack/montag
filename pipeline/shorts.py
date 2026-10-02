# -*- coding: utf-8 -*-
"""Build vertical Shorts916 props from work/<id>/shorts.json.

Each short = ordered source-time spans (clean takes) concatenated. For every
short we emit remotion/props/<id>.json with:
- segments (frame trims) + per-segment face crop offset (tx) and zoom originY;
- karaoke words (text/from/to in frames, accent flag) built from words.json,
  with per-word text fixes (clean ASR, format numbers) from shorts.json;
- punch zooms on accent words.

Native full-bleed 9:16: the 16:9 source is scaled to fill height 1920, so its
width is 3413 px; we translate X to centre the face (from faces.json).

Usage:
  python shorts.py <work_dir> <remotion_props_dir> draft   # dump words per short
  python shorts.py <work_dir> <remotion_props_dir>          # build props
"""
import json
import subprocess
import sys
from pathlib import Path

CANVAS_W = 1080
CANVAS_H = 1920
VIDEO_W = round(CANVAS_H * 16 / 9)   # 3413: source scaled to fill height
TX_MIN = CANVAS_W - VIDEO_W           # -2333 (clamp so no black edge)


def load(work: Path, name: str):
    return json.loads((work / name).read_text(encoding="utf-8"))


def probe_frames(path: Path, fps: float) -> int:
    dur = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], text=True).strip()
    return int(round(float(dur) * fps))


def face_center(faces, t):
    best = min((f for f in faces if f.get("found")),
               key=lambda f: abs(f["t"] - t), default=None)
    if not best:
        return 0.5, 0.4
    b = best["box"]
    return b["x"] + b["w"] / 2, b["y"] + b["h"] / 2


def build(work: Path, props_dir: Path, draft: bool):
    # fps from edl.json when the full pipeline ran; shorts-only mode has no EDL
    fps = load(work, "edl.json")["fps"] if (work / "edl.json").exists() else 30

    words = load(work, "words.json")
    faces = load(work, "faces.json")
    data = load(work, "shorts.json")
    shorts = data["shorts"]
    media = data.get("media", "source")  # base media name in public/ (remakes use their own)
    preview = (props_dir.parent / "public" / f"{media}_preview.mp4").exists()

    for sh in shorts:
        spans = sh["spans"]
        fixes = {int(k): v for k, v in sh.get("fixes", {}).items()}
        accents = set(sh.get("accents", []))

        # source-time -> output-time (seconds) within this short's spans
        def out_t(src):
            acc = 0.0
            for a, b in spans:
                if a <= src <= b:
                    return acc + (src - a)
                acc += b - a
            return None

        # words falling inside the spans, in order
        wlist = [w for w in words if out_t(w["start"]) is not None]
        wlist.sort(key=lambda w: out_t(w["start"]))

        if draft:
            lines = [f"# {sh['id']} — {sh['title']}  ({sum(b-a for a,b in spans):.1f}s)"]
            for w in wlist:
                lines.append(f"{w['i']:5d} [{w['start']:8.2f}] {w['w']}")
            out = props_dir.parent / "props" / f"_draft_{sh['id']}.txt"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("\n".join(lines), encoding="utf-8")
            print(f"draft {sh['id']}: {len(wlist)} words -> {out.name}")
            continue

        # segments with face crop offset
        segments = []
        for a, b in spans:
            fx, fy = face_center(faces, (a + b) / 2)
            tx = max(TX_MIN, min(0, round(CANVAS_W / 2 - fx * VIDEO_W)))
            segments.append({
                "start": a, "end": b,
                "startFrame": round(a * fps), "endFrame": round(b * fps),
                "tx": tx, "faceY": round(fy * 100, 1),
            })
        total = sum(s["endFrame"] - s["startFrame"] for s in segments)

        # karaoke words (highlight window = up to the next word, capped at 1.5 s)
        kw = []
        for w in wlist:
            txt = fixes.get(w["i"], w["w"])
            if txt == "":
                continue
            kw.append({"text": txt, "from": round(out_t(w["start"]) * fps),
                       "accent": w["i"] in accents})
        for idx, k in enumerate(kw):
            nxt = kw[idx + 1]["from"] if idx + 1 < len(kw) else k["from"] + 12
            k["to"] = max(k["from"] + 2, min(nxt, k["from"] + 45))

        # punch zooms on accent words (origin at the face, centred horizontally)
        punch = []
        for w in wlist:
            if w["i"] in accents:
                _, fy = face_center(faces, w["start"])
                punch.append({"from": round(out_t(w["start"]) * fps) - 4,
                              "originY": round(fy * 100, 1)})

        # b-roll inserts anchored inside this short; layout: third (default) / half / full
        insert_events = []
        ins_file = work / "inserts.json"
        if ins_file.exists():
            wbi = {w["i"]: w for w in words}
            public = props_dir.parent / "public"
            media_cache = {}
            for it in json.loads(ins_file.read_text(encoding="utf-8"))["inserts"]:
                w0, w1 = wbi.get(it["anchorWord"]), wbi.get(it["endWord"])
                if not w0 or not w1:
                    continue
                span = next(((a, b) for a, b in spans if a <= w0["start"] <= b), None)
                if span is None:                       # anchor not in this short
                    continue
                f0 = round(out_t(w0["start"]) * fps)
                f1 = round(out_t(min(w1["end"], span[1])) * fps)
                is_video = it["file"].lower().endswith((".mp4", ".mov", ".webm"))
                if is_video:                           # cap to the clip's own length
                    p = public / "inserts" / it["file"]
                    if it["file"] not in media_cache:
                        media_cache[it["file"]] = probe_frames(p, fps) if p.exists() else 120
                    f1 = min(f1, f0 + media_cache[it["file"]])
                f1 = max(f1, f0 + 20)                   # keep on screen >=0.66s
                ev = {
                    "file": f"inserts/{it['file']}",
                    "type": "video" if is_video else "image",
                    "from": f0, "to": min(f1, total),
                }
                if it.get("layout"):
                    ev["layout"] = it["layout"]
                if it.get("coverBox"):  # blur plate over burned-in subs of the fragment
                    ev["coverBox"] = it["coverBox"]
                insert_events.append(ev)
        insert_events.sort(key=lambda e: e["from"])

        props = {
            "src": f"{media}.mp4",
            "previewSrc": f"{media}_preview.mp4" if preview else None,
            "fps": fps,
            "segments": segments,
            "words": kw,
            "punchZooms": punch,
            "inserts": insert_events,
            "audioTrack": None,
            "totalDurationInFrames": total,
        }
        out = props_dir / f"{sh['id']}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(props, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"OK {sh['id']}: {total}f ({total/fps:.1f}s) segs={len(segments)} "
              f"words={len(kw)} accents={len(punch)} inserts={len(insert_events)}")


if __name__ == "__main__":
    work = Path(sys.argv[1])
    props_dir = Path(sys.argv[2])
    draft = len(sys.argv) > 3 and sys.argv[3] == "draft"
    build(work, props_dir, draft)
