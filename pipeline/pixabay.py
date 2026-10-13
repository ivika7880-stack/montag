# -*- coding: utf-8 -*-
"""Подбор и скачивание фото/видео для вставок с Pixabay (Stage 1.5, коллажный стиль).

Вход:  work/<id>/stock_queries.json
       [{"id": "01", "kind": "video"|"photo", "query": "city night rain", "pick": 0}, ...]
       (query — на английском; pick — какой из найденных брать, по умолчанию 0)
Выход: remotion/public/inserts/<id>/NN.jpg | NN.mp4
       (mp4 — кроп по центру в 1080x1920, all-intra H.264, без звука, ≤ MAX_VIDEO_S)
       work/<id>/stock_credits.md  (автор + ссылка; лицензия Pixabay атрибуции не требует,
       но запись нужна для проверки источника)

Usage: python pixabay.py <work_dir> [--list]   # --list: показать кандидатов, ничего не качать
Ключ (.env): PIXABAY_API_KEY. Лимит API ~100 запросов/60 с. Хотлинк запрещён — только скачивание.
Лицензия Pixabay (Content License): бесплатно, в т.ч. коммерчески; нельзя перепродавать файлы как
есть и показывать узнаваемых людей в оскорбительном/чувствительном контексте.
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

API = "https://pixabay.com/api/"
MAX_VIDEO_S = 8
PER_PAGE = 10

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def pick_video_url(videos: dict) -> str | None:
    """Крупнейший из large/medium с шириной или высотой ≥ 1080; иначе лучший доступный."""
    for name in ("large", "medium", "small", "tiny"):
        v = videos.get(name) or {}
        if v.get("url") and max(v.get("width", 0), v.get("height", 0)) >= 1080:
            return v["url"]
    for name in ("large", "medium", "small", "tiny"):
        if (videos.get(name) or {}).get("url"):
            return videos[name]["url"]
    return None


def search(kind: str, query: str, key: str) -> list[dict]:
    if kind == "video":
        url, params = API + "videos/", {}
    else:
        url, params = API, {"image_type": "photo", "orientation": "vertical"}
    r = requests.get(url, params={"key": key, "q": query, "per_page": PER_PAGE,
                                  "safesearch": "true", **params}, timeout=30)
    if r.status_code in (400, 401, 403):
        raise SystemExit(f"Pixabay отклонил запрос ({r.status_code}): {r.text[:120]} — проверь PIXABAY_API_KEY")
    r.raise_for_status()
    return r.json().get("hits", [])


def download(url: str, dest: Path) -> None:
    with requests.get(url, stream=True, timeout=180) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)


def to_vertical_intra(src: Path, dest: Path) -> None:
    vf = "scale=-2:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-t", str(MAX_VIDEO_S), "-vf", vf,
                    "-c:v", "libx264", "-crf", "15", "-g", "1", "-bf", "0", "-an", str(dest)],
                   check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("work_dir")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    work = Path(a.work_dir)
    vid = work.name
    key = os.environ.get("PIXABAY_API_KEY", "")
    if not key:
        raise SystemExit("Нет PIXABAY_API_KEY в .env (бесплатный ключ: pixabay.com/api/docs)")
    queries = json.loads((work / "stock_queries.json").read_text(encoding="utf-8"))
    out_dir = ROOT / "remotion" / "public" / "inserts" / vid
    credits = ["# Stock credits (Pixabay)\n"]

    for q in queries:
        kind, query, pick = q.get("kind", "photo"), q["query"], q.get("pick", 0)
        items = search(kind, query, key)
        print(f"[{q['id']}] {kind} «{query}»: найдено {len(items)}")
        for i, it in enumerate(items):
            print(f"    {i}: {it['pageURL']}  — {it.get('user', '?')}  [{it.get('tags', '')[:60]}]")
        if a.list or not items:
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        it = items[min(pick, len(items) - 1)]
        if kind == "video":
            url = pick_video_url(it.get("videos", {}))
            if not url:
                print("    нет подходящего mp4, пропуск")
                continue
            tmp = out_dir / f"{q['id']}_raw.mp4"
            download(url, tmp)
            to_vertical_intra(tmp, out_dir / f"{q['id']}.mp4")
            tmp.unlink()
            name = f"{q['id']}.mp4"
        else:
            name = f"{q['id']}.jpg"
            download(it.get("largeImageURL") or it["webformatURL"], out_dir / name)
        credits.append(f"- `{vid}/{name}` — {it.get('user', '?')}, {it['pageURL']}")
        print(f"    OK → {vid}/{name}")

    if not a.list:
        (work / "stock_credits.md").write_text("\n".join(credits) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
