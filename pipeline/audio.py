# -*- coding: utf-8 -*-
"""Build the speaker's de-clicked audio track from the EDL segments.

Remotion plays the speaker as a chain of `<Video>` trims (one per kept
segment). At every jump-cut the source waveform jumps, which can click. A
per-frame `volume` function can't fix this: @remotion/media quantises volume to
one value per frame (33 ms at 30 fps), far coarser than a de-click fade needs.

So we bake the fix into audio instead: cut each segment out of the source
audio sample-accurately (48000 / 30 fps = 1600 samples/frame, exact), apply a
short raised-cosine fade at both edges so every splice ramps to zero on both
sides, concatenate, and write one WAV spanning the whole timeline. Main169 then
mutes the `<Video>` and plays this track via `<Audio>` (see `audioTrack` prop).

This is NOT loudness/tone processing (which the project forbids): the voice is
untouched except at cut edges, where each segment is hard-gated (silenced) for
6 ms to drop the breath/click on the splice, then de-clicked with a 6 ms
raised-cosine ramp over the next 6 ms.

Usage: python audio.py <props.json> [source_media]
  source_media defaults to <props>/../../public/<props.src> (source.mp4).
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 48000          # 48000 / 30 fps = 1600 samples/frame (integer -> exact sync)
GATE_MS = 6         # hard-silence at each segment edge (drops breath/click on splice)
FADE_MS = 6         # de-click ramp length just inside the gate


def cosine_window(n: int) -> np.ndarray:
    """Raised-cosine ramp 0->1 over n samples (smoother than linear for de-click)."""
    if n <= 1:
        return np.ones(max(n, 0), dtype=np.float32)
    i = np.arange(n, dtype=np.float32)
    return (0.5 * (1.0 - np.cos(np.pi * i / (n - 1)))).astype(np.float32)


def build(props_path: Path, source: Path) -> None:
    props = json.loads(props_path.read_text(encoding="utf-8"))
    fps = props["fps"]
    segs = props["segments"]
    assert SR % fps == 0, f"SR {SR} not divisible by fps {fps}"
    spf = SR // int(fps)                       # samples per frame (1600)
    gate = round(GATE_MS / 1000 * SR)          # 288 samples of hard silence
    fade = round(FADE_MS / 1000 * SR)          # 288 samples of de-click ramp

    public = props_path.parent.parent / "public"
    out_name = f"audio_{props_path.stem}.wav"   # main169.json -> audio_main169.wav
    out_path = public / out_name

    # Decode the source audio to 48k mono once (-vn: audio only, fast).
    with tempfile.TemporaryDirectory() as td:
        tmp_wav = Path(td) / "src48.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(source),
             "-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(tmp_wav)],
            check=True,
        )
        y, sr = sf.read(tmp_wav, dtype="float32")
    assert sr == SR
    if y.ndim > 1:
        y = y.mean(axis=1)

    parts = []
    max_end = 0
    for s in segs:
        a = s["startFrame"] * spf
        b = s["endFrame"] * spf
        max_end = max(max_end, b)
        clip = np.array(y[a:b], dtype=np.float32)
        n = len(clip)
        half = n // 2                          # guard very short segments
        g = min(gate, half)                    # hard-silence the outer GATE_MS
        if g > 0:
            clip[:g] = 0.0
            clip[-g:] = 0.0
        f = min(fade, half - g)                # de-click ramp just inside the gate
        if f > 0:
            clip[g:g + f] *= cosine_window(f)
            clip[n - g - f:n - g] *= cosine_window(f)[::-1]
        parts.append(clip)

    track = np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)
    expected = sum(s["endFrame"] - s["startFrame"] for s in segs) * spf
    assert len(track) == expected, f"len {len(track)} != expected {expected}"
    assert len(track) == props["totalDurationInFrames"] * spf, "track != comp length"
    if max_end > len(y):
        raise SystemExit(f"segment audio {max_end} exceeds source {len(y)} samples")

    sf.write(out_path, track, SR, subtype="PCM_16")

    # Wire the track into the props so the composition mutes video and plays it.
    props["audioTrack"] = out_name
    props_path.write_text(json.dumps(props, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    print(f"OK {out_name}: {len(track)} samples = {len(track)/SR:.2f}s, "
          f"{len(segs)} segments, {GATE_MS}ms gate + {FADE_MS}ms fades, "
          f"audioTrack set in props")


if __name__ == "__main__":
    props_path = Path(sys.argv[1])
    if len(sys.argv) > 2:
        source = Path(sys.argv[2])
    else:
        props = json.loads(props_path.read_text(encoding="utf-8"))
        source = props_path.parent.parent / "public" / props["src"]
    build(props_path, source)
