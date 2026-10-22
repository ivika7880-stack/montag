# -*- coding: utf-8 -*-
"""Face box once per second (Haar cascade, OpenCV) -> work/<id>/faces_1fps.json for smartcut.py.

Usage: python faces_1fps.py <video> <work_dir>
Writes {"<second>": [x, y, w, h]} in a 360x640 frame (the largest frontal face of that second).
Used to frame long videos: smartcut.py takes the MEDIAN face position/size of the whole video.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2

video, work = Path(sys.argv[1]), Path(sys.argv[2])
cc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
out = {}
with tempfile.TemporaryDirectory() as td:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-an", "-vf", "fps=1,scale=360:640",
                    "-q:v", "4", str(Path(td) / "%05d.jpg")], check=True)
    files = sorted(Path(td).glob("*.jpg"))
    for f in files:
        r = cc.detectMultiScale(cv2.imread(str(f), cv2.IMREAD_GRAYSCALE), 1.1, 6, minSize=(60, 60))
        if len(r):
            x, y, w, h = max(r, key=lambda b: b[2] * b[3])
            out[int(f.stem) - 1] = [int(x), int(y), int(w), int(h)]
(work / "faces_1fps.json").write_text(json.dumps(out), encoding="utf-8")
print(f"OK faces_1fps.json: face found in {len(out)} of {len(files)} seconds")
