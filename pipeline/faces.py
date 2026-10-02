# -*- coding: utf-8 -*-
"""Sample the speaker's face position every N seconds with MediaPipe.

Usage: python faces.py <video> <out_json> [step_seconds]
Writes JSON: [{"t": sec, "found": bool, "box": {"x","y","w","h"}}] — box in
relative 0..1 coordinates of the frame.
"""
import json
import sys
from pathlib import Path

import cv2
import mediapipe as mp


def detect(video_path: str, out_json: Path, step_s: float = 5.0):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {video_path}")
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
        entry = {"t": round(t, 2), "found": False, "box": None}
        if res.detections:
            best = max(res.detections, key=lambda d: d.score[0])
            bb = best.location_data.relative_bounding_box
            entry["found"] = True
            entry["box"] = {
                "x": round(bb.xmin, 4),
                "y": round(bb.ymin, 4),
                "w": round(bb.width, 4),
                "h": round(bb.height, 4),
            }
        samples.append(entry)
        t += step_s
    cap.release()

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(samples, ensure_ascii=False, indent=1), encoding="utf-8")
    found = sum(1 for s in samples if s["found"])
    print(f"OK samples={len(samples)} face_found={found}")


if __name__ == "__main__":
    step = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
    detect(sys.argv[1], Path(sys.argv[2]), step)
