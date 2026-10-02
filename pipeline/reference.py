# -*- coding: utf-8 -*-
"""Break down a reference short: author-on-screen vs visualization segments.

Face presence is sampled with MediaPipe every `step` seconds (default 0.25 —
finer than the requested 0.5 s), scene cuts come from ffmpeg scdet; combined
they yield author/visual segments. Visual fragments are exported as all-intra
clips ready to become inserts; the transcript (Deepgram, optional — skipped
without DEEPGRAM_API_KEY) is attached per segment.

Usage:
  python reference.py <video> <work_dir> [step_seconds]
Writes:
  <work_dir>/ref/…                      ASR artifacts (words.json, transcript.txt)
  <work_dir>/ref.json                   segments (type, timing, file, text, layout hint)
  <work_dir>/ref_plan.md                human timeline for review
  remotion/public/inserts/<id>/ref_NN.mp4   visual fragments (all-intra, no audio)
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import cv2
import mediapipe as mp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))

SCENE_THRESH = 0.30   # ffmpeg scdet sensitivity
FACE_FRAC = 0.50      # >= this fraction of face-found samples -> author segment
MIN_SEG_S = 0.40      # shorter segments are glued to the previous one
# layout hint by fragment length: long visual passages replace the speaker
LAYOUT_FULL_S = 3.0
LAYOUT_HALF_S = 1.5

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def probe(video: str) -> dict:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate:format=duration",
         "-of", "json", video], text=True, encoding="utf-8")
    d = json.loads(out)
    st = d["streams"][0]
    num, den = st["r_frame_rate"].split("/")
    return {
        "w": st["width"], "h": st["height"],
        "fps": float(num) / float(den or 1),
        "duration": float(d["format"]["duration"]),
    }


def sample_faces(video: str, step_s: float):
    """Like faces.py but returns samples in memory (t, found)."""
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {video}")
    duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 30)
    fd = mp.solutions.face_detection.FaceDetection(
        model_selection=1, min_detection_confidence=0.4
    )
    samples = []
    t = 0.0
    while t < duration:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            break
        res = fd.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        samples.append({"t": round(t, 3), "found": bool(res.detections)})
        t += step_s
    cap.release()
    return samples


def scene_cuts(video: str) -> list:
    """Scene-change timestamps (seconds) via ffmpeg scdet."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", video, "-an",
         "-vf", f"select='gt(scene,{SCENE_THRESH})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [float(m) for m in re.findall(r"pts_time:([0-9.]+)", proc.stderr)]


def classify(samples, cuts, duration):
    """Scene-bounded segments typed author/visual by face-found fraction."""
    bounds = [0.0] + sorted(c for c in cuts if 0.05 < c < duration - 0.05) + [duration]
    segs = []
    for a, b in zip(bounds, bounds[1:]):
        inside = [s for s in samples if a - 1e-6 <= s["t"] < b]
        frac = (sum(1 for s in inside if s["found"]) / len(inside)) if inside else 0.0
        segs.append({"start": a, "end": b, "type": "author" if frac >= FACE_FRAC else "visual"})

    # glue too-short segments to the previous one, then merge same-type neighbours
    glued = []
    for s in segs:
        if glued and (s["end"] - s["start"]) < MIN_SEG_S:
            glued[-1]["end"] = s["end"]
        elif glued and glued[-1]["type"] == s["type"]:
            glued[-1]["end"] = s["end"]
        else:
            glued.append(dict(s))
    merged = []
    for s in glued:
        if merged and merged[-1]["type"] == s["type"]:
            merged[-1]["end"] = s["end"]
        else:
            merged.append(s)
    return merged


def layout_hint(dur: float) -> str:
    if dur >= LAYOUT_FULL_S:
        return "full"
    if dur >= LAYOUT_HALF_S:
        return "half"
    return "third"


def main(video: str, work_dir: Path, step_s: float = 0.25):
    vid_id = work_dir.name
    info = probe(video)
    print(f"probe: {info['w']}x{info['h']} {info['fps']:.2f}fps {info['duration']:.1f}s")

    samples = sample_faces(video, step_s)
    found = sum(1 for s in samples if s["found"])
    print(f"faces: {found}/{len(samples)} samples with a face (step {step_s}s)")

    cuts = scene_cuts(video)
    print(f"scenes: {len(cuts)} cuts")

    segs = classify(samples, cuts, info["duration"])

    # optional ASR (words land in work_dir/ref/, never clash with the user's own recording)
    words = []
    try:
        from transcribe import transcribe as dg_transcribe
        wav = work_dir / "ref" / "ref_audio.wav"
        wav.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video, "-vn",
                        "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)],
                       check=True)
        dg_transcribe(wav, work_dir / "ref")
        words = json.loads((work_dir / "ref" / "words.json").read_text(encoding="utf-8"))
        print(f"asr: {len(words)} words")
    except Exception as e:  # no key / network / etc. — segmentation still useful
        print(f"asr skipped: {type(e).__name__}: {e}")

    def text_for(a, b):
        return " ".join(w["pw"] for w in words if a <= w["start"] < b)

    # export visual fragments as all-intra inserts
    out_dir = ROOT / "remotion" / "public" / "inserts" / vid_id
    n_vis = 0
    for i, s in enumerate(segs):
        s["i"] = i
        s["dur"] = round(s["end"] - s["start"], 3)
        s["start"] = round(s["start"], 3)
        s["end"] = round(s["end"], 3)
        s["text"] = text_for(s["start"], s["end"])
        if s["type"] == "visual":
            n_vis += 1
            s["layout"] = layout_hint(s["dur"])
            s["file"] = f"{vid_id}/ref_{n_vis:02d}.mp4"
            out_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", video,
                 "-ss", f"{s['start']:.3f}", "-to", f"{s['end']:.3f}",
                 "-c:v", "libx264", "-crf", "15", "-g", "1", "-bf", "0", "-an",
                 str(out_dir / f"ref_{n_vis:02d}.mp4")],
                check=True)
            # mid-fragment thumbnail — Claude reads it to spot burned-in subs/watermarks
            thumb = work_dir / "ref" / f"thumb_{n_vis:02d}.jpg"
            thumb.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error",
                 "-ss", f"{(s['start'] + s['end']) / 2:.3f}", "-i", video,
                 "-frames:v", "1", "-vf", "scale=540:-1", str(thumb)],
                check=True)
            s["thumb"] = str(thumb.relative_to(work_dir)).replace("\\", "/")

    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "ref.json").write_text(
        json.dumps({"src": video, "info": info, "step": step_s, "segments": segs},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    lines = [f"# Разбор референса — {Path(video).name}",
             f"{info['w']}x{info['h']}, {info['duration']:.1f} с; "
             f"сегментов: {len(segs)} (визуал: {n_vis})", "",
             "| # | тип | время | длит | раскладка | файл | текст |",
             "|---|-----|-------|------|-----------|------|-------|"]
    for s in segs:
        lines.append(
            f"| {s['i']} | {'🗣 автор' if s['type'] == 'author' else '🖼 визуал'} "
            f"| {s['start']:.2f}–{s['end']:.2f} | {s['dur']:.2f}с "
            f"| {s.get('layout', '—')} | {s.get('file', '—')} | {s['text'][:80]} |")
    lines += ["", "Раскладка — предложение (full ≥ 3с, half ≥ 1.5с, third < 1.5с); "
              "правится при сборке в inserts.json.",
              "Миниатюры фрагментов — ref/thumb_NN.jpg: по ним размечаются зоны вшитых "
              "субтитров/вотермарок (`coverBox` вставки — закрывается блюр-плитой)."]
    (work_dir / "ref_plan.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"OK: {len(segs)} segments ({n_vis} visual) -> "
          f"{work_dir / 'ref.json'}, {work_dir / 'ref_plan.md'}")


if __name__ == "__main__":
    step = float(sys.argv[3]) if len(sys.argv) > 3 else 0.25
    main(sys.argv[1], Path(sys.argv[2]), step)
