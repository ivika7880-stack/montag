# -*- coding: utf-8 -*-
"""Смоук pexels.py: выбор файла видео и URL фото. Без сети."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import pexels as p

files = [
    {"file_type": "video/mp4", "height": 720, "link": "a"},
    {"file_type": "video/mp4", "height": 1920, "link": "b"},
    {"file_type": "video/mp4", "height": 3840, "link": "c"},
    {"file_type": "video/webm", "height": 1920, "link": "d"},
]
assert p.pick_video_file(files)["link"] == "b"                       # ближе всего к 1920
assert p.pick_video_file(files[:1])["link"] == "a"                   # только маленькое — берём его
assert p.pick_video_file([{"file_type": "video/webm", "height": 1}]) is None
assert p.photo_url({"src": {"large2x": "x", "original": "y"}}) == "x"
assert p.photo_url({"src": {"original": "y"}}) == "y"
print("OK test_pexels")
