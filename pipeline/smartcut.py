# -*- coding: utf-8 -*-
"""Smart cut of a talking-head video: seamless jump cuts + framing zoom, rendered with ffmpeg.

Starts from an EDL (work/<id>/edl.json, see edl.py) and improves how the cuts LOOK:
1. slivers   - a kept stretch shorter than SLIVER_S that holds only silence is dropped (two cuts
               in a row 0.14 s apart read as one nervous double cut);
2. match cut - the EDL cuts out a silent stretch; ANY frame inside that silence can be the
               frame we cut out of / into. For every seam we pick the pair of frames whose
               picture differs least (same head pose), so most cuts become invisible;
3. seam type - difference <= HARD_MAX: plain cut; <= XFADE_MAX: 6-frame cross-dissolve
               (blends only frames that sit in silence, audio is untouched);
               above that: "punch" - the picture jumps by PUNCH more zoom (alternating),
               so the cut reads as an intentional change of shot instead of a glitch;
4. framing   - the whole video is zoomed so the head sits like in a reference frame
               (less empty space above it), anchored on the median face position.

Audio is cut on the same frame boundaries as the video (audio.py: 6 ms gate + de-click).

Usage: python smartcut.py <work_dir> <source.mp4> <out.mp4> [--profile longform|default] [--zoom Z] [--top T] [--lufs L]
Needs: work/<id>/{edl.json,audio.wav,faces_1fps.json}; ffmpeg; numpy, soundfile.
faces_1fps.json = {"<second>": [x, y, w, h]} in a 360x640 frame (any face detector).
"""
import argparse
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import soundfile as sf

FPS = 30
SRC_W, SRC_H = 720, 1280
AN_FPS = 15                  # analysis frame rate for candidate frames
GA, GB = 64, 114             # analysis thumbnail size (gray)
SLIVER_S = 0.35              # kept stretches shorter than this are dropped when silent
SLIVER_MAX_DB = -52.0
QUIET_DB = -64.0             # a candidate cut frame must sit in silence (neighbourhood too)
QUIET_PAD_S = 0.06
BACK_S, FWD_S = 0.40, 1.60   # how far around the original cut we may move it (inside silence)
MOVE_PENALTY = 0.3           # picture-difference units per second of shift from the EDL cut
HARD_MAX = 4.0               # picture difference (0..255 scale, face crop) up to which a plain cut is invisible
XFADE_MAX = 11.0             # up to here a short cross-dissolve hides the cut
XFADE_FRAMES = 6
HANDLE = XFADE_FRAMES // 2
PUNCH = 1.08                 # extra zoom on "punch" seams (alternates in/out)
MIN_SEG_FOR_XFADE = 0.4


def even(v):
    return int(round(v / 2) * 2)


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


class Framing:
    """Crop windows (zoom Z around the face anchor) in source pixels."""

    def __init__(self, faces, zoom, top):
        a = np.array(list(faces.values()), float)
        self.fx = float(np.median((a[:, 0] + a[:, 2] / 2) / 360))          # face centre X, fraction
        ftop = float(np.median(a[:, 1] / 640))                               # face box top, fraction
        fh = float(np.median(a[:, 3] / 640))
        self.fy = ftop + fh / 2                                              # face centre Y
        self.zoom = zoom
        y0 = min(max(ftop - top / zoom, 0.0), 1 - 1 / zoom)
        x0 = min(max(self.fx - 0.5 / zoom, 0.0), 1 - 1 / zoom)
        self.out_x = (self.fx - x0) * zoom                                   # where the face lands in the output
        self.out_y = (self.fy - y0) * zoom

    def crop(self, punch=False):
        z = self.zoom * (PUNCH if punch else 1.0)
        x0 = min(max(self.fx - self.out_x / z, 0.0), 1 - 1 / z)
        y0 = min(max(self.fy - self.out_y / z, 0.0), 1 - 1 / z)
        cw = even(SRC_W / z)
        ch = min(even(cw * 16 / 9), SRC_H)
        cx = min(max(int(round(x0 * SRC_W)), 0), SRC_W - cw)
        cy = min(max(int(round(y0 * SRC_H)), 0), SRC_H - ch)
        return cw, ch, cx, cy

    def vf(self, punch=False, size=None):
        cw, ch, cx, cy = self.crop(punch)
        w, h = size if size else (SRC_W, SRC_H)
        return f"crop={cw}:{ch}:{cx}:{cy},scale={w}:{h}:flags=lanczos"


def small_frames(src, t0, t1, framing):
    """Gray thumbnails of the (base-zoom) crop at AN_FPS between t0 and t1."""
    t0 = max(t0, 0.0)
    vf = f"fps={AN_FPS},{framing.vf(False, (GA, GB))},format=gray"
    r = run(["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(src),
             "-an", "-vf", vf, "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(r.stdout, np.uint8)
    n = len(a) // (GA * GB)
    return np.array([t0 + i / AN_FPS for i in range(n)]), a[:n * GA * GB].reshape(n, GB, GA).astype(np.float32)


def load_audio_db(wav):
    x, sr = sf.read(wav)
    if x.ndim > 1:
        x = x.mean(axis=1)
    hop = int(sr * 0.01)
    n = (len(x) - hop) // hop
    idx = np.arange(n)[:, None] * hop + np.arange(hop)[None, :]
    rms = np.sqrt((x[idx] ** 2).mean(axis=1))
    return 20 * np.log10(rms + 1e-9)


def quiet_at(db, t, pad=QUIET_PAD_S):
    a = max(int((t - pad) / 0.01), 0)
    b = min(int((t + pad) / 0.01) + 1, len(db))
    return b > a and float(db[a:b].max()) < QUIET_DB + 2.0


def contiguous(db, t0, direction, limit):
    """Grid times from t0 moving in `direction` (+1/-1) while the audio stays quiet, up to `limit` s."""
    out, k = [], 0
    while True:
        t = t0 + direction * k / AN_FPS
        if k / AN_FPS > limit or t < 0 or not quiet_at(db, t):
            break
        out.append(t)
        k += 1
    return out


def drop_slivers(segs, db):
    keep = []
    for s in segs:
        a, b = int(s[0] / 0.01), int(s[1] / 0.01) + 1
        if s[1] - s[0] < SLIVER_S and float(db[a:b].max()) < SLIVER_MAX_DB:
            continue
        keep.append(list(s))
    return keep


def refine(segs, src, db, framing):
    """Return (new segments in frames, seam info list)."""
    seams = []
    cuts = []                                    # (out_t, in_t) per seam
    for i in range(len(segs) - 1):
        e, s = segs[i][1], segs[i + 1][0]
        cuts.append((e, s))
    info = []
    for i, (e, s) in enumerate(cuts):
        tmin, tmax = segs[i][0] + 0.25, segs[i + 1][1] - 0.25
        outs = [t for t in sorted(set(contiguous(db, e, +1, FWD_S) + contiguous(db, e, -1, BACK_S))) if t >= tmin]
        ins = [t for t in sorted(set(contiguous(db, s, -1, FWD_S) + contiguous(db, s, +1, BACK_S))) if t <= tmax]
        if not outs or not ins:
            outs, ins = [e], [s]
        to, fo = small_frames(src, min(outs) - 0.05, max(outs) + 0.1, framing)
        ti, fi = small_frames(src, min(ins) - 0.05, max(ins) + 0.1, framing)

        def nearest(tt, t):
            return int(np.argmin(np.abs(tt - t)))
        cur = float(np.abs(fo[nearest(to, e)] - fi[nearest(ti, s)]).mean()) if len(to) and len(ti) else 0.0
        best = (cur + 0.0, e, s)
        for t in outs:
            a = fo[nearest(to, t)] if len(to) else None
            for u in ins:
                # never keep MORE silence than the EDL cut did: the removed stretch may slide
                # inside the silence but must stay at least as long as the original one
                if u - t < (s - e) - 1.0 / AN_FPS or u <= t + 1.5 / AN_FPS:
                    continue
                b = fi[nearest(ti, u)] if len(ti) else None
                if a is None or b is None:
                    continue
                d = float(np.abs(a - b).mean())
                cost = d + MOVE_PENALTY * (abs(t - e) + abs(u - s))
                if cost < best[0] + 0.0 and d < cur + 1e-6:
                    best = (cost, t, u)
        _, t, u = best
        d = float(np.abs(fo[nearest(to, t)] - fi[nearest(ti, u)]).mean()) if len(to) and len(ti) else cur
        # handles for a cross-dissolve: HANDLE frames of silence beyond the out point / before the in point
        fwd = len(contiguous(db, t, +1, 0.5)) / AN_FPS
        bwd = len(contiguous(db, u, -1, 0.5)) / AN_FPS
        info.append(dict(out=t, inn=u, diff=d, cur=cur, handles=fwd >= 0.11 and bwd >= 0.11))
        print(f"\r  seam {i + 1}/{len(cuts)}", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    # frames
    fr = []
    starts = [segs[0][0]] + [x["inn"] for x in info]
    ends = [x["out"] for x in info] + [segs[-1][1]]
    for a, b in zip(starts, ends):
        fr.append([int(round(a * FPS)), int(round(b * FPS))])
    return fr, info


def classify(fr, info):
    kinds, punch, state = [], [], False
    seg_punch = [False]
    for i, x in enumerate(info):
        long_enough = (fr[i][1] - fr[i][0]) / FPS >= MIN_SEG_FOR_XFADE and (fr[i + 1][1] - fr[i + 1][0]) / FPS >= MIN_SEG_FOR_XFADE
        if x["diff"] <= HARD_MAX:
            k = "hard"
        elif x["diff"] <= XFADE_MAX and x["handles"] and long_enough:
            k = "xfade"
        elif x["diff"] <= XFADE_MAX:
            k = "hard"
        else:
            k = "punch"
            state = not state
        kinds.append(k)
        seg_punch.append(state)
    return kinds, seg_punch


def render(src, out, fr, kinds, seg_punch, framing, workdir, jobs=4):
    cmds, pieces = [], []

    def enc(vf_inputs, name):
        return name

    for i, (a, b) in enumerate(fr):
        hs = HANDLE if i > 0 and kinds[i - 1] == "xfade" else 0
        he = HANDLE if i < len(kinds) and kinds[i] == "xfade" else 0
        n = (b - a) - hs - he
        if n <= 0:
            raise SystemExit(f"segment {i} too short for its cross-dissolves")
        ss = max((a + hs) / FPS - 0.0167, 0.0)
        name = workdir / f"b{i:04d}.mp4"
        cmds.append(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss:.4f}", "-i", str(src), "-an",
                     "-vf", f"fps=30,{framing.vf(seg_punch[i])}", "-frames:v", str(n),
                     "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", "30", str(name)])
        pieces.append(name)
        if i < len(kinds) and kinds[i] == "xfade":
            o, inn = fr[i][1], fr[i + 1][0]
            vf = framing.vf(seg_punch[i])
            bname = workdir / f"x{i:04d}.mp4"
            fc = (f"[0:v]fps=30,{vf},trim=end_frame={XFADE_FRAMES},setpts=PTS-STARTPTS[a];"
                  f"[1:v]fps=30,{vf},trim=end_frame={XFADE_FRAMES},setpts=PTS-STARTPTS[b];"
                  f"[a][b]blend=all_expr='A*(1-(N+0.5)/{XFADE_FRAMES})+B*((N+0.5)/{XFADE_FRAMES})'[v]")
            cmds.append(["ffmpeg", "-v", "error", "-y",
                         "-ss", f"{max((o - HANDLE) / FPS - 0.0167, 0):.4f}", "-t", "0.5", "-i", str(src),
                         "-ss", f"{max((inn - HANDLE) / FPS - 0.0167, 0):.4f}", "-t", "0.5", "-i", str(src),
                         "-filter_complex", fc, "-map", "[v]", "-frames:v", str(XFADE_FRAMES),
                         "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", "30", str(bname)])
            pieces.append(bname)
    done = 0
    with ThreadPoolExecutor(jobs) as ex:
        for _ in ex.map(lambda c: subprocess.run(c, check=True), cmds):
            done += 1
            print(f"\r  render {done}/{len(cmds)}", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    lst = workdir / "list.txt"
    lst.write_text("\n".join(f"file '{p}'" for p in pieces), encoding="utf-8")
    return lst


def build_audio(fr, src, root, lufs=None):
    """audio.py de-click track for the refined frame segments -> wav path."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import audio
    props = root / "remotion" / "props" / "_smartcut.json"
    segs = [{"startFrame": a, "endFrame": b, "start": a / FPS, "end": b / FPS} for a, b in fr]
    cfg = {"fps": FPS, "src": src.name, "segments": segs,
           "totalDurationInFrames": sum(b - a for a, b in fr)}
    if lufs is not None:
        cfg["targetLufs"] = lufs
    props.write_text(json.dumps(cfg), encoding="utf-8")
    try:
        audio.build(props, src)
    finally:
        props.unlink(missing_ok=True)
    return root / "remotion" / "public" / "audio__smartcut.wav"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work_dir")
    ap.add_argument("source")
    ap.add_argument("out")
    ap.add_argument("--profile", choices=("longform", "default"), default="longform",
                    help="longform = the author's style measured on her manual edit: zoom x1.41, face top 16.4%%, "
                         "ONE scale (no punch-in), plain cuts only, loudness -19 LUFS (gain only)")
    ap.add_argument("--zoom", type=float, default=None)
    ap.add_argument("--top", type=float, default=None, help="face-box top as a fraction of frame height")
    ap.add_argument("--lufs", type=float, default=None, help="target loudness, linear gain only (longform: -19)")
    a = ap.parse_args()
    work, src, out = Path(a.work_dir), Path(a.source), Path(a.out)
    global HARD_MAX, XFADE_MAX
    if a.profile == "longform":
        a.zoom = a.zoom or 1.41
        a.top = a.top or 0.164
        a.lufs = -19.0 if a.lufs is None else a.lufs
        HARD_MAX = XFADE_MAX = 1e9              # every seam is a plain cut at one constant scale
    else:
        a.zoom = a.zoom or 1.18
        a.top = a.top or 0.21
    root = Path(__file__).resolve().parents[1]
    faces = json.loads((work / "faces_1fps.json").read_text(encoding="utf-8"))
    framing = Framing(faces, a.zoom, a.top)
    print("framing crop (base):", framing.crop(False), "| punch:", framing.crop(True))
    db = load_audio_db(work / "audio.wav")
    edl = json.loads((work / "edl.json").read_text(encoding="utf-8"))["segments"]
    segs = [[s["start"], s["end"]] for s in edl]
    segs = drop_slivers(segs, db)
    print(f"segments {len(edl)} -> {len(segs)} after dropping silent slivers")
    fr, info = refine(segs, src, db, framing)
    d0 = np.array([x["cur"] for x in info])
    d1 = np.array([x["diff"] for x in info])
    kinds, seg_punch = classify(fr, info)
    print(f"picture jump at seams: median {np.median(d0):.1f} -> {np.median(d1):.1f}; "
          f"75% {np.percentile(d0, 75):.1f} -> {np.percentile(d1, 75):.1f}; max {d0.max():.1f} -> {d1.max():.1f}")
    print("seams:", {k: kinds.count(k) for k in ("hard", "xfade", "punch")})
    (work / "smartcut.json").write_text(json.dumps(
        {"frames": fr, "seams": [dict(k=k, **{kk: round(v, 3) if isinstance(v, float) else v for kk, v in x.items()})
                                 for k, x in zip(kinds, info)]}, indent=1), encoding="utf-8")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        lst = render(src, out, fr, kinds, seg_punch, framing, td)
        wav = build_audio(fr, src, root, a.lufs)
        out.parent.mkdir(parents=True, exist_ok=True)
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(wav),
             "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ac", "2",
             "-movflags", "+faststart", "-shortest", str(out)])
    total = sum(b - a for a, b in fr) / FPS
    print(f"OK {out} ({total:.1f}s)")


if __name__ == "__main__":
    main()
