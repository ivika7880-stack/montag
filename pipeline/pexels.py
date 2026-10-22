# -*- coding: utf-8 -*-
"""Подбор и скачивание фото/видео для вставок с Pexels (Stage 1.5, коллажный стиль).

Вход:  work/<id>/pexels_queries.json
       [{"id": "01", "kind": "video"|"photo", "query": "city night rain", "pick": 0}, ...]
       (query — на английском, Pexels ищет лучше; pick — какой из найденных брать, по умолчанию 0)
Выход: remotion/public/inserts/<id>/NN.jpg | NN.mp4  (mp4 — all-intra H.264 без звука, ≤ MAX_VIDEO_S)
       work/<id>/pexels_credits.md  (автор, ссылка, лицензия — для публикации)

Usage: python pexels.py <work_dir> [--list]   # --list: только показать кандидатов, ничего не качать
Ключ (.env): PEXELS_API_KEY (бесплатный: pexels.com/api). Лимит API ~200 запросов/час.
Лицензия Pexels: бесплатно, в т.ч. коммерчески; нельзя выдавать контент за свой «как есть»
для перепродажи и показывать узнаваемых людей в оскорбительном/чувствительном контексте.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

API = "https://api.pexels.com"
MAX_VIDEO_S = 8
TARGET_H = 1920           # вертикальный холст
PER_PAGE = 8

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def pick_video_file(files: list[dict]) -> dict | None:
    """Лучший mp4: высота ≥ 1280 и ближе всего к 1920 (не качаем 4K зря)."""
    mp4 = [f for f in files if f.get("file_type") == "video/mp4" and f.get("height")]
    if not mp4:
        return None
    big = [f for f in mp4 if f["height"] >= 1280]
    pool = big or mp4
    return min(pool, key=lambda f: abs(f["height"] - TARGET_H)) if big else max(pool, key=lambda f: f["height"])


def photo_url(photo: dict) -> str:
    src = photo.get("src", {})
    return src.get("large2x") or src.get("large") or src["original"]


def search(kind: str, query: str, key: str) -> list[dict]:
    path = "/videos/search" if kind == "video" else "/v1/search"
    r = requests.get(API + path, headers={"Authorization": key},
                     params={"query": query, "orientation": "portrait", "per_page": PER_PAGE},
                     timeout=30)
    if r.status_code == 401:
        raise SystemExit("PEXELS_API_KEY неверный или не задан (.env). Ключ бесплатный: pexels.com/api")
    r.raise_for_status()
    data = r.json()
    return data.get("videos" if kind == "video" else "photos", [])


def download(url: str, dest: Path) -> None:
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)


def to_intra(src: Path, dest: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-t", str(MAX_VIDEO_S),
                    "-c:v", "libx264", "-crf", "15", "-g", "1", "-bf", "0", "-an", str(dest)],
                   check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("work_dir")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    work = Path(a.work_dir)
    vid = work.name
    key = os.environ.get("PEXELS_API_KEY", "")
    if not key:
        raise SystemExit("Нет PEXELS_API_KEY в .env (бесплатный ключ: pexels.com/api)")
    queries = json.loads((work / "pexels_queries.json").read_text(encoding="utf-8"))
    out_dir = ROOT / "remotion" / "public" / "inserts" / vid
    out_dir.mkdir(parents=True, exist_ok=True)
    credits = ["# Pexels credits\n"]

    for q in queries:
        kind, query, pick = q.get("kind", "photo"), q["query"], q.get("pick", 0)
        items = search(kind, query, key)
        print(f"[{q['id']}] {kind} «{query}»: найдено {len(items)}")
        for i, it in enumerate(items):
            who = (it.get("photographer") or (it.get("user") or {}).get("name") or "?")
            print(f"    {i}: {it['url']}  — {who}")
        if a.list or not items:
            continue
        it = items[min(pick, len(items) - 1)]
        who = it.get("photographer") or (it.get("user") or {}).get("name") or "?"
        if kind == "video":
            f = pick_video_file(it.get("video_files", []))
            if not f:
                print("    нет подходящего mp4, пропуск")
                continue
            tmp = out_dir / f"{q['id']}_raw.mp4"
            download(f["link"], tmp)
            to_intra(tmp, out_dir / f"{q['id']}.mp4")
            tmp.unlink()
            name = f"{q['id']}.mp4"
        else:
            name = f"{q['id']}.jpg"
            download(photo_url(it), out_dir / name)
        credits.append(f"- `{vid}/{name}` — {who}, {it['url']}")
        print(f"    OK → {vid}/{name}")

    if not a.list:
        (work / "pexels_credits.md").write_text("\n".join(credits) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
