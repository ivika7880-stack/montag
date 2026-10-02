# -*- coding: utf-8 -*-
"""Download a reference short by URL (Stage 2R entry step).

Providers per platform, priority order (any error -> next one):
  tiktok    : ScrapeCreators /v2/tiktok/video       -> Apify clockworks/tiktok-scraper
  instagram : ScrapeCreators /v1/instagram/post     -> Apify apify/instagram-scraper
  youtube   : Apify streamers/youtube-video-downloader -> Apify epctex/youtube-video-downloader
              (ScrapeCreators has no video-file endpoint for YouTube, metadata only)

Usage: python download.py <url> <work_dir> [--provider scrapecreators|apify]
Writes: <work_dir>/ref_source.mp4  (path printed to stdout)
Keys (.env): SCRAPECREATORS_API_KEY, APIFY_TOKEN
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

SC_BASE = "https://api.scrapecreators.com"
APIFY_BASE = "https://api.apify.com/v2"
SYNC_TIMEOUT_S = 300     # hard Apify sync-API cap is 5 min; one video runs 2-10 s
MIN_FILE_BYTES = 50_000  # smaller than this is an error page, not a video
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"  # bare python-requests UA gets rejected by CDNs

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class ProviderError(RuntimeError):
    pass


PLATFORM_RES = {
    "youtube": re.compile(r"(youtube\.com/shorts/|youtu\.be/)", re.I),
    "tiktok": re.compile(r"tiktok\.com/", re.I),
    "instagram": re.compile(r"instagram\.com/(reels?|p)/", re.I),
}


def detect_platform(url: str) -> str:
    for name, rx in PLATFORM_RES.items():
        if rx.search(url):
            return name
    raise ValueError(
        f"не понял платформу URL: {url}\n"
        "поддерживаются: youtube.com/shorts/…, youtu.be/…, "
        "tiktok.com/@…/video/…, instagram.com/reel/…"
    )


# --- извлечение прямой ссылки из ответов (чистые функции, тестируются фикстурами) ---

def extract_sc_tiktok(data: dict) -> str:
    video = (data.get("aweme_detail") or {}).get("video") or {}
    for field in ("download_no_watermark_addr", "download_addr", "play_addr"):
        urls = (video.get(field) or {}).get("url_list") or []
        if urls:
            return urls[0]
    raise ProviderError(
        f"ScrapeCreators/tiktok: нет url_list в ответе: {json.dumps(data, ensure_ascii=False)[:300]}")


def extract_sc_instagram(data: dict) -> str:
    url = ((data.get("data") or {}).get("xdt_shortcode_media") or {}).get("video_url")
    if not url:
        raise ProviderError(
            f"ScrapeCreators/instagram: нет video_url в ответе: {json.dumps(data, ensure_ascii=False)[:300]}")
    return url


VIDEO_URL_FIELDS = ("videoUrl", "downloadUrl", "download_url", "url", "video_url", "mediaUrls")


def _first_video_url(obj):
    """Deep-scan датасет-итема: первый URL, похожий на видео/KVS-запись."""
    if isinstance(obj, str):
        if obj.startswith("http") and (
                ".mp4" in obj or "googlevideo" in obj or "key-value-stores" in obj):
            return obj
        return None
    if isinstance(obj, dict):
        for f in VIDEO_URL_FIELDS:
            got = _first_video_url(obj.get(f))
            if got:
                return got
        for v in obj.values():
            got = _first_video_url(v)
            if got:
                return got
    if isinstance(obj, list):
        for v in obj:
            got = _first_video_url(v)
            if got:
                return got
    return None


def extract_apify_items(items: list, prefer: tuple = ()) -> str:
    if not items:
        raise ProviderError("Apify: пустой датасет (актор ничего не вернул)")
    item = items[0]
    for f in prefer:
        v = item.get(f)
        if isinstance(v, list) and v:
            v = v[0]
        if isinstance(v, str) and v.startswith("http"):
            return v
    got = _first_video_url(item)
    if got:
        return got
    raise ProviderError(
        f"Apify: не нашёл видео-URL в ответе: {json.dumps(item, ensure_ascii=False)[:300]}")


# --- сеть ---

def sc_get(path: str, url: str) -> dict:
    key = os.environ.get("SCRAPECREATORS_API_KEY")
    if not key:
        raise ProviderError("нет SCRAPECREATORS_API_KEY в .env (E:\\Montage\\.env)")
    resp = requests.get(f"{SC_BASE}{path}", params={"url": url},
                        headers={"x-api-key": key}, timeout=120)
    if resp.status_code != 200:
        raise ProviderError(f"ScrapeCreators {path}: HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def apify_run(actor: str, payload: dict) -> list:
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        raise ProviderError("нет APIFY_TOKEN в .env (E:\\Montage\\.env)")
    resp = requests.post(
        f"{APIFY_BASE}/acts/{actor}/run-sync-get-dataset-items",
        params={"token": token}, json=payload, timeout=SYNC_TIMEOUT_S + 30)
    if resp.status_code == 408:
        raise ProviderError(
            f"Apify {actor}: 408 — ран не уложился в 5-мин лимит sync-API; "
            "ран продолжает крутиться, смотри https://console.apify.com/actors/runs")
    if resp.status_code >= 300:
        raise ProviderError(f"Apify {actor}: HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


# --- провайдеры (возвращают прямую ссылку на видеофайл) ---

def p_sc_tiktok(url: str) -> str:
    return extract_sc_tiktok(sc_get("/v2/tiktok/video", url))


def p_sc_instagram(url: str) -> str:
    return extract_sc_instagram(sc_get("/v1/instagram/post", url))


def p_apify_tiktok(url: str) -> str:
    # shouldDownloadVideos: файл сохраняется на стороне Apify (KVS) — прямые CDN-ссылки
    # TikTok подписаны и капризны к заголовкам, KVS-путь надёжнее
    items = apify_run("clockworks~tiktok-scraper", {
        "postURLs": [url], "resultsPerPage": 1, "shouldDownloadVideos": True})
    return extract_apify_items(items, prefer=("mediaUrls",))


def p_apify_instagram(url: str) -> str:
    items = apify_run("apify~instagram-scraper", {
        "directUrls": [url], "resultsType": "posts", "resultsLimit": 1})
    return extract_apify_items(items, prefer=("videoUrl",))


def p_apify_youtube_streamers(url: str) -> str:
    items = apify_run("streamers~youtube-video-downloader", {"startUrls": [{"url": url}]})
    return extract_apify_items(items, prefer=("downloadUrl", "url"))


def p_apify_youtube_epctex(url: str) -> str:
    items = apify_run("epctex~youtube-video-downloader", {
        "startUrls": [url], "quality": "720", "proxy": {"useApifyProxy": True}})
    return extract_apify_items(items, prefer=("downloadUrl", "url"))


REGISTRY = {
    "tiktok": [("scrapecreators", p_sc_tiktok), ("apify", p_apify_tiktok)],
    "instagram": [("scrapecreators", p_sc_instagram), ("apify", p_apify_instagram)],
    "youtube": [("apify", p_apify_youtube_streamers), ("apify", p_apify_youtube_epctex)],
}


# --- скачивание и валидация ---

def download_file(direct_url: str, dest: Path):
    params = {}
    if direct_url.startswith(APIFY_BASE) and "token=" not in direct_url:
        params["token"] = os.environ.get("APIFY_TOKEN", "")
    with requests.get(direct_url, headers={"User-Agent": UA}, params=params,
                      stream=True, timeout=600) as r:
        if r.status_code != 200:
            raise ProviderError(f"скачивание: HTTP {r.status_code} с {direct_url[:120]}…")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)


def validate(dest: Path):
    if not dest.exists() or dest.stat().st_size < MIN_FILE_BYTES:
        size = dest.stat().st_size if dest.exists() else 0
        raise ProviderError(f"файл подозрительно мал ({size} байт) — похоже, это не видео")
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name", "-of", "json", str(dest)],
            text=True, encoding="utf-8")
    except subprocess.CalledProcessError as e:
        raise ProviderError(f"ffprobe не прочитал файл: {e}") from e
    if not json.loads(out).get("streams"):
        raise ProviderError("в скачанном файле нет видеопотока")


def main():
    ap = argparse.ArgumentParser(
        description="Скачивание референс-шортса по ссылке (Stage 2R)")
    ap.add_argument("url")
    ap.add_argument("work_dir")
    ap.add_argument("--provider", choices=["scrapecreators", "apify"],
                    help="форс конкретного провайдера (тест фолбэк-ветки)")
    args = ap.parse_args()

    try:
        platform = detect_platform(args.url)
    except ValueError as e:
        sys.exit(str(e))
    chain = REGISTRY[platform]
    if args.provider:
        chain = [(n, fn) for n, fn in chain if n == args.provider]
        if not chain:
            sys.exit(f"для {platform} нет провайдера {args.provider} "
                     "(YouTube качается только через Apify)")

    dest = Path(args.work_dir) / "ref_source.mp4"
    errors = []
    for name, fn in chain:
        try:
            print(f"[{platform}] пробую {name}…")
            direct_url = fn(args.url)
            download_file(direct_url, dest)  # ссылки протухают за часы — качаем сразу
            validate(dest)
            print(f"OK: {dest} ({dest.stat().st_size // 1024} KB, провайдер {name})")
            print(f"дальше: E:\\Montage\\.venv\\Scripts\\python.exe "
                  f"pipeline\\reference.py \"{dest}\" {args.work_dir}")
            return
        except (ProviderError, requests.RequestException) as e:
            errors.append(f"  {name}: {e}")
            print(f"  {name} не справился: {e}")
    sys.exit("все провайдеры упали:\n" + "\n".join(errors))


if __name__ == "__main__":
    main()
