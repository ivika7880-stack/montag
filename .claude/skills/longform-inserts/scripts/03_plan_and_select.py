"""Full-video plan: narration slots + target hero per slot + vectorised scene selection.
Slots 0..28 (0-157.3 s) are the approved trial (selection2.json) and are kept as is."""
import json, re, math
import numpy as np

TRIAL_END = 157.3
words = json.load(open("work/prism/words.json", encoding="utf-8"))
TOTAL = words[-1]["end"] + 0.5

# ---- 1. slots from sentence/pause boundaries, 4.5-8 s ----
slots, start, wi0 = [], TRIAL_END, None
tail = [w for w in words if w["start"] >= TRIAL_END - 0.05]
cur_start, cur_words = TRIAL_END, []
for k, w in enumerate(tail):
    cur_words.append(w)
    el = w["end"] - cur_start
    nxt = tail[k + 1]["start"] if k + 1 < len(tail) else None
    gap = (nxt - w["end"]) if nxt is not None else 9
    sent_end = re.search(r"[.?!…]$", w.get("pw", w["w"])) is not None
    if (el >= 3.0 and (sent_end or gap >= 0.25)) or el >= 5.0 or nxt is None:
        end = (nxt + w["end"]) / 2 if nxt is not None else TOTAL
        end = min(end, cur_start + 5.3) if nxt is not None else end
        slots.append(dict(t0=round(cur_start, 2), t1=round(end, 2), words=" ".join(x["w"] for x in cur_words)))
        cur_start, cur_words = end, []
# merge a too-short last slot into previous
if len(slots) > 1 and slots[-1]["t1"] - slots[-1]["t0"] < 2.5:
    slots[-2]["t1"] = slots[-1]["t1"]; slots.pop()

# ---- 2. target hero per slot ----
PARTS = [(64.7, "kit"), (788.0, "lili"), (1470.6, "shin"), (1849.3, "mix")]


def default_target(t, idx):
    d = "kit"
    for t0, name in PARTS:
        if t >= t0:
            d = name
    if d == "mix":
        return ["kit", "lili", "shin"][idx % 3]
    return d


CUE = dict(kit=r"\bкит", lili=r"\bлил", shin=r"\bсин|\bшин")
for i, s in enumerate(slots):
    d = default_target(s["t0"], i)
    txt = s["words"].lower()
    hit = [h for h, p in CUE.items() if re.search(p, txt)]
    s["target"] = d if (not hit or d in hit) else hit[0]
    s["dur"] = round(s["t1"] - s["t0"], 2)

# ---- 3. vectorised selection (same rules as select2.py) ----
IDX = dict(kit=0, lili=1, shin=2)
MOVE, MIN_MOVE, CUT = 1.0, 0.60, 20.0
WHO = {e: np.load(f"work/prism/who/ep{e:02d}.npy") for e in range(1, 21)}
MOT = {e: np.array(json.load(open(f"work/prism/motion/ep{e:02d}.json"))["m"], dtype=np.float32) for e in range(1, 21)}
SEC_MV, SEC_CUT = {}, {}
for e, m in MOT.items():
    n = len(m) // 6
    r = m[:n * 6].reshape(n, 6)
    SEC_MV[e] = (r > MOVE).mean(axis=1); SEC_CUT[e] = (r > CUT).sum(axis=1)
from numpy.lib.stride_tricks import sliding_window_view as swv

trial = json.load(open("work/prism/selection2.json"))
used = [(t["ep"], t["start"]) for t in trial if t.get("ep")]
blocked = {e: np.zeros(len(WHO[e]) + 50, bool) for e in WHO}
for ep, st in used:
    blocked[ep][max(0, int(st) - 12):int(st) + 12] = True
epuse = {e: sum(1 for u in used if u[0] == e) for e in WHO}

out = list(trial)
fails = 0
for i, s in enumerate(slots):
    d = s["dur"]; k = int(math.ceil(d)) + 1
    ti = IDX[s["target"]]
    best = None
    for (rm, rn, rv) in ((0.60, 0.35, 0.50), (0.50, 0.25, 0.35), (0.40, 0.15, 0.20), (0.30, 0.0, 0.0)):
        for e in WHO:
            n = min(len(WHO[e]), len(SEC_MV[e]))
            if n < k + 12:
                continue
            P = WHO[e][:n, ti]
            wm = swv(P, k).mean(axis=1); wn = swv(P, k).min(axis=1)
            kk = int(math.ceil(d))
            mv = swv(SEC_MV[e][:n], kk).mean(axis=1)
            cuts = swv(SEC_CUT[e][:n], kk).sum(axis=1)
            L = min(len(wm), len(wn), len(mv), len(cuts))
            st = np.arange(L)
            ok = ((wm[:L] >= rm) & (wn[:L] >= rn) & (mv[:L] >= rv)
                  & (cuts[:L] <= 1 + (d > 7) + (4 if rm < 0.35 else 0)) & (st >= 5) & (st < n - kk - 5) & (~blocked[e][:L]))
            if not ok.any():
                continue
            score = wm[:L] + 0.3 * mv[:L] - 0.08 * epuse[e]
            score = np.where(ok, score, -9)
            j = int(score.argmax())
            if best is None or score[j] > best[0]:
                best = (float(score[j]), e, j, float(wm[j]), float(wn[j]), float(mv[j]), int(cuts[j]))
        if best:
            break
    if not best:
        fails += 1
        out.append(dict(slot=len(out), t0=s["t0"], t1=s["t1"], dur=d, target=s["target"], ep=None)); continue
    _, e, j, pm, pmin, mv_, c = best
    blocked[e][max(0, j - 12):j + 12] = True; epuse[e] += 1
    out.append(dict(slot=len(out), t0=s["t0"], t1=s["t1"], dur=d, target=s["target"], ep=e, start=float(j),
                    p_mean=round(pm, 2), p_min=round(pmin, 2), move=round(mv_, 2), cuts=c))
json.dump(out, open("work/prism/selection_full.json", "w"), indent=1)
json.dump(slots, open("work/prism/slots_full_text.json", "w"), ensure_ascii=False, indent=1)
from collections import Counter
print("slots", len(out), "fails", fails, "total", round(TOTAL, 1))
print(Counter(o["target"] for o in out))
print("episodes use:", dict(sorted(Counter(o["ep"] for o in out if o["ep"]).items())))





