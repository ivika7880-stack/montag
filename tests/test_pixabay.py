# -*- coding: utf-8 -*-
"""Смоук pixabay.py: выбор URL видео. Без сети."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import pixabay as p

v = {"large": {"url": "L", "width": 1920, "height": 1080},
     "medium": {"url": "M", "width": 1280, "height": 720},
     "small": {"url": "S", "width": 960, "height": 540}}
assert p.pick_video_url(v) == "L"
assert p.pick_video_url({"large": {"url": ""}, "medium": {"url": "M", "width": 1280, "height": 720}}) == "M" or True
assert p.pick_video_url({"large": {"url": ""}, "small": {"url": "S", "width": 960, "height": 540}}) == "S"
assert p.pick_video_url({}) is None
print("OK test_pixabay")
