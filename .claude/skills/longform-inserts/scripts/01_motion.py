"""Per-second motion score of a series episode (limited-animation filter).
usage: motion.py <ep.mkv> <out.json>   -> {"fps":6,"m":[score per 1/6 s ...]}
score = mean abs diff between consecutive frames at 6 fps (96x54 gray)."""
import sys, json, subprocess, numpy as np

ffmpeg, src, out = sys.argv[1], sys.argv[2], sys.argv[3]
W, H, FPS = 96, 54, 6
p = subprocess.Popen([ffmpeg, "-v", "error", "-i", src, "-an", "-sn", "-vf", f"fps={FPS},scale={W}:{H},format=gray",
                      "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
m, prev, n = [], None, W * H
while True:
    b = p.stdout.read(n)
    if len(b) < n:
        break
    f = np.frombuffer(b, np.uint8).astype(np.int16)
    m.append(0.0 if prev is None else float(np.abs(f - prev).mean()))
    prev = f
json.dump({"fps": FPS, "m": [round(x, 3) for x in m]}, open(out, "w"))
print(src, len(m))
