# -*- coding: utf-8 -*-
"""Смоук download.py: платформы, порядок провайдеров, извлечение URL из фикстур. Без сети.

Run: E:\Montage\.venv\Scripts\python.exe tests\test_download.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import download as d

# --- detect_platform ---
assert d.detect_platform("https://www.youtube.com/shorts/AbC12_x?feature=share") == "youtube"
assert d.detect_platform("https://youtu.be/AbC12_x") == "youtube"
assert d.detect_platform("https://www.tiktok.com/@user/video/7300000000000000000") == "tiktok"
assert d.detect_platform("https://www.instagram.com/reel/XyZ123/") == "instagram"
assert d.detect_platform("https://www.instagram.com/reels/XyZ123/") == "instagram"
try:
    d.detect_platform("https://example.com/video/1")
    raise AssertionError("мусорный URL обязан падать ValueError")
except ValueError:
    pass

# --- порядок провайдеров (спека: SC первым, Apify фолбэк; YouTube — только Apify) ---
assert [n for n, _ in d.REGISTRY["tiktok"]] == ["scrapecreators", "apify"]
assert [n for n, _ in d.REGISTRY["instagram"]] == ["scrapecreators", "apify"]
assert [n for n, _ in d.REGISTRY["youtube"]] == ["apify", "apify"]

# --- извлечение URL (фикстуры повторяют структуры из доков провайдеров) ---
assert d.extract_sc_tiktok({"aweme_detail": {"video": {
    "download_no_watermark_addr": {"url_list": ["https://cdn.tt/x.mp4"]}}}}) == "https://cdn.tt/x.mp4"
# нет no-watermark — берём download_addr
assert d.extract_sc_tiktok({"aweme_detail": {"video": {
    "download_addr": {"url_list": ["https://cdn.tt/wm.mp4"]}}}}) == "https://cdn.tt/wm.mp4"
assert d.extract_sc_instagram({"data": {"xdt_shortcode_media": {
    "video_url": "https://cdn.ig/r.mp4"}}}) == "https://cdn.ig/r.mp4"
assert d.extract_apify_items([{"videoUrl": "https://cdn.ig/i.mp4"}],
                             prefer=("videoUrl",)) == "https://cdn.ig/i.mp4"
kvs = "https://api.apify.com/v2/key-value-stores/st0re/records/video-1"
assert d.extract_apify_items([{"mediaUrls": [kvs]}], prefer=("mediaUrls",)) == kvs
# epctex кладёт ссылку вглубь item.output.url — ловится deep-scan'ом без prefer
assert d.extract_apify_items([{"output": {"url": "https://cdn.yt/y.mp4"}}]) == "https://cdn.yt/y.mp4"
for bad in ([], [{"foo": 1}]):
    try:
        d.extract_apify_items(bad)
        raise AssertionError("пустой/бесполезный датасет обязан падать ProviderError")
    except d.ProviderError:
        pass
try:
    d.extract_sc_instagram({"data": {}})
    raise AssertionError("нет video_url — обязан падать ProviderError")
except d.ProviderError:
    pass

print("OK: все проверки прошли")
