#!/usr/bin/env python3
"""Видео/аудио -> JSON расшифровки Deepgram (русский, nova-3, абзацы + таймкоды).

python transcribe.py <видео-или-аудио> <выходной.json>

Ключ: переменная DEEPGRAM_API_KEY или строка DEEPGRAM_API_KEY=... в .env
(в облачной сессии ключ может подставлять прокси — тогда он не нужен).
Нужен ffmpeg в PATH. Повторяет запрос при временных ошибках Deepgram.
"""
import json, os, subprocess, sys, tempfile, time, urllib.request, urllib.error

URL = ("https://api.deepgram.com/v1/listen?model=nova-3&language=ru"
       "&punctuate=true&smart_format=true&paragraphs=true")


def api_key():
    k = os.environ.get("DEEPGRAM_API_KEY")
    if k:
        return k
    for p in (".env", os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".env")):
        if os.path.exists(p):
            for line in open(p, encoding="utf8"):
                if line.startswith("DEEPGRAM_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"\'')
    return None


def to_mp3(src, dst):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vn", "-ac", "1",
                    "-ar", "16000", "-b:a", "48k", dst], check=True)


def valid(path):
    try:
        json.load(open(path, encoding="utf8"))["results"]["channels"][0]["alternatives"][0]["paragraphs"]
        return True
    except Exception:
        return False


def main(src, out):
    if valid(out):
        print("уже есть:", out); return
    mp3 = os.path.join(tempfile.mkdtemp(), "audio.mp3")
    to_mp3(src, mp3)
    data = open(mp3, "rb").read()
    headers = {"Content-Type": "audio/mpeg"}
    key = api_key()
    if key:
        headers["Authorization"] = "Token " + key
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(URL, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=3000) as r:
                open(out, "wb").write(r.read())
            if valid(out):
                print("OK", out); return
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                sys.exit("Deepgram отклонил ключ (%d): проверь DEEPGRAM_API_KEY" % e.code)
            print("ошибка", e.code, "попытка", attempt, file=sys.stderr)
        except Exception as e:
            print("ошибка", repr(e)[:200], "попытка", attempt, file=sys.stderr)
        time.sleep(5 * attempt)
    sys.exit("не удалось расшифровать: " + src)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:3])
