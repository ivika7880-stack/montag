# -*- coding: utf-8 -*-
"""Build work/<id>/delete.json from a list of PHRASES instead of word indices.

Word indices change whenever the video is re-transcribed (Deepgram is not deterministic), so a
saved list of cuts must be anchored by text + time. Each entry finds the phrase in words.json
(nearest to `near`, seconds) and cuts it (or part of it).

Usage: python delete_from_phrases.py <work_dir> <spec.json>
spec.json = [{"phrase": "ой аху", "near": 7.4, "reason": "...",
              "off": 0, "count": null,             # cut only words [off, off+count) of the phrase
              "to_phrase": null, "to_near": null}] # or cut from this phrase's start to that phrase's end
Words are compared lowercase without punctuation. Fillers (э, ээ, мм) are added automatically.
"""
import json
import re
import sys
from pathlib import Path

norm = lambda s: re.sub(r"[^\w]", "", s.lower())
FILLERS = {"э", "ээ", "эээ", "эм", "мм", "ммм", "эхм"}


def main(work: Path, spec_file: Path) -> None:
    words = json.loads((work / "words.json").read_text(encoding="utf-8"))
    ws = [norm(w["w"]) for w in words]
    spec = json.loads(spec_file.read_text(encoding="utf-8"))

    def find(phrase, near):
        p = [norm(x) for x in phrase.split()]
        n = len(p)
        best = None
        for i in range(len(ws) - n + 1):
            if ws[i:i + n] == p:
                d = abs(words[i]["start"] - near)
                if best is None or d < best[0]:
                    best = (d, i)
        if best is None or best[0] > 6:
            raise SystemExit(f"NOT FOUND: {phrase!r} near {near}s (closest: {best}) - check the transcript")
        return best[1], n

    out = []
    for e in spec:
        i, n = find(e["phrase"], e["near"])
        a = i + e.get("off", 0)
        if e.get("to_phrase"):
            j, m = find(e["to_phrase"], e["to_near"])
            b = j + m - 1
        else:
            b = a + (n - e.get("off", 0) if e.get("count") is None else e["count"]) - 1
        out.append({"from": a, "to": b, "reason": e["reason"]})
    for i, w in enumerate(ws):
        if w in FILLERS:
            out.append({"from": i, "to": i, "reason": "filler"})
    out.sort(key=lambda d: d["from"])
    (work / "delete.json").write_text(json.dumps({"delete": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK delete.json: {len(out)} cuts, {sum(d['to'] - d['from'] + 1 for d in out)} of {len(ws)} words")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
