# -*- coding: utf-8 -*-
"""Deepgram nova-3 transcription with word-level timestamps.

Usage: python transcribe.py <audio.wav> <out_dir> [language]
Writes: deepgram_raw.json, words.json, transcript.txt, utterances.txt
"""
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def transcribe(wav_path: Path, out_dir: Path, language: str = "ru", model: str = "nova-3"):
    key = os.environ["DEEPGRAM_API_KEY"]
    params = {
        "model": model,
        "language": language,
        "smart_format": "true",
        "punctuate": "true",
        "utterances": "true",
    }
    with open(wav_path, "rb") as f:
        resp = requests.post(
            "https://api.deepgram.com/v1/listen",
            params=params,
            headers={"Authorization": f"Token {key}", "Content-Type": "audio/wav"},
            data=f,
            timeout=900,
        )
    resp.raise_for_status()
    data = resp.json()

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "deepgram_raw.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )

    alt = data["results"]["channels"][0]["alternatives"][0]
    words = [
        {
            "i": i,
            "w": w["word"],
            "pw": w.get("punctuated_word", w["word"]),
            "start": w["start"],
            "end": w["end"],
            "conf": round(w.get("confidence", 0.0), 3),
        }
        for i, w in enumerate(alt["words"])
    ]
    (out_dir / "words.json").write_text(
        json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (out_dir / "transcript.txt").write_text(alt["transcript"], encoding="utf-8")

    utt_lines = []
    for u in data["results"].get("utterances", []):
        utt_lines.append(f"[{u['start']:8.2f} - {u['end']:8.2f}] {u['transcript']}")
    (out_dir / "utterances.txt").write_text("\n".join(utt_lines), encoding="utf-8")

    print(f"OK words={len(words)} last_end={words[-1]['end'] if words else 0:.2f}s")


if __name__ == "__main__":
    lang = sys.argv[3] if len(sys.argv) > 3 else "ru"
    transcribe(Path(sys.argv[1]), Path(sys.argv[2]), lang)
