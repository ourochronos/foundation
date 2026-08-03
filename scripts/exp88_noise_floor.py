"""The measurement that should have come first: how noisy is any of this?

Eight experiments have compared F1 scores across runs — 0.212, 0.291, 0.301,
0.276, 0.267 — and **not one measured run-to-run variance**. Every one of those
comparisons silently assumes the noise floor is zero. If it is 0.05, most of the
arc's rankings are unfalsifiable.

The need became concrete rather than theoretical. exp86 reported recall 0.266
and exp87 reported 0.200 for **the same prompt at the same coverage**, and the
gap was written up as "the anomaly worth understanding". It was not an anomaly:
exp86 ran on 10 documents (349 gold) and exp87 on 12 (471 gold), so the
denominators differed while the numerators — 93 and 94 correct — were nearly
identical. A population mismatch was read as a finding, twice, by me.

So this fixes the population and measures three things at once:

  j0    uncalibrated prompt          } the calibration effect, within one
  j2a   calibrated prompt            } population for the first time
  j2b   calibrated prompt, AGAIN     } identical input -> the noise floor

`j2a` and `j2b` are byte-identical requests. Any difference between them is
pure run-to-run variance, and it is the yardstick every other difference in
this arc should have been measured against.

Per-document results are recorded this time, because exp87 stored only totals
and that is why the exp86 discrepancy could not be diagnosed from the artifact.

Settings are exp87's `mid` (window 4, cap 260) — its best-F1 point — on the
same 12 documents as exp83/85/87, so numbers are comparable to all three.

Predictions, registered before running:

- **N1** the noise floor is material: |F1(j2a) − F1(j2b)| > 0.02. If so,
  several previously-reported gaps are inside it.
- **N2** the calibration effect (j2 vs j0) is **larger** than the noise floor —
  exp86's central finding survives being measured properly.
- **N3** per-document recall varies enormously, with at least one document near
  zero. Twelve documents is then too small a sample for the ±0.03 distinctions
  this arc has been drawing.

Usage: .venv/bin/python scripts/exp88_noise_floor.py [n_docs]
"""
from __future__ import annotations

import collections
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
WINDOW, CAP = 4, 260                       # exp87 "mid", its best-F1 setting

props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
docs = json.loads((ROOT / "data" / "gold" / "docred_200.json").read_text())[:N]


def collapse(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(s).lower())).strip()


LABEL2PID = {}
for pid, d in props.items():
    for nm in [d.get("label")] + list(d.get("aliases", [])):
        if nm:
            LABEL2PID.setdefault(collapse(nm), pid)
used = collections.Counter(l["r"] for d in docs for l in d["labels"])
VOCAB = [props[p]["label"] for p, _ in used.most_common(30) if p in props]

BASE = """For each numbered ENTITY PAIR below, state the relation the document
asserts from the first entity to the second, or NONE.

RELATIONS - use ONLY these names, exactly as written:
{rels}

Rules:
- Answer EVERY numbered pair. Do not skip any.
- Direction matters: the relation runs from the first entity to the second.
- If the document DENIES the relation, answer NONE.
- Only answer when the document asserts it; do not guess a plausible relation.
{calib}
Output one line per pair, nothing else:
{{"n":<number>,"r":"<relation or NONE>"}}

PAIRS:
{pairs}

DOCUMENT:
{text}
"""
CALIB = ("- Calibration: a document like this typically asserts 20-60 of these\n"
         "  relations. Answering NONE to almost everything is a mistake; read the\n"
         "  document again for pairs you passed over.\n")

# j2a and j2b are the SAME prompt. The pair exists to measure variance, so they
# must not differ by even a character.
ARMS = {"j0": "", "j2a": CALIB, "j2b": CALIB}


def haiku(p):
    try:
        r = subprocess.run(["copilot", "-p", p, "--no-ask-user", "--model",
                            "claude-haiku-4.5", "--no-auto-update"],
                           capture_output=True, text=True, timeout=900)
        return r.stdout
    except subprocess.TimeoutExpired:
        return ""


score = {k: collections.Counter() for k in ARMS}
perdoc = collections.defaultdict(dict)
cover = collections.Counter()

for di, doc in enumerate(docs):
    vs = doc["vertexSet"]
    disp = [sorted(m["name"] for m in v)[0] for v in vs]
    sents_of = [{m["sent_id"] for m in v} for v in vs]
    gold = {(l["h"], l["r"], l["t"]) for l in doc["labels"]}
    sents = [" ".join(s) for s in doc["sents"]]

    cands = [(h, t) for h in range(len(vs)) for t in range(len(vs))
             if h != t and any(abs(a - b) <= WINDOW
                               for a in sents_of[h] for b in sents_of[t])]
    cands.sort(key=lambda ht: min(abs(a - b) for a in sents_of[ht[0]]
                                  for b in sents_of[ht[1]]))
    cands = cands[:CAP]
    cs = set(cands)
    cover["gold"] += len(gold)
    cover["enum"] += sum(1 for (h, _, t) in gold if (h, t) in cs)

    pl = "\n".join(f"  {i+1}. {disp[h]}  ->  {disp[t]}"
                   for i, (h, t) in enumerate(cands))
    for k, calib in ARMS.items():
        prompt = BASE.format(rels="\n".join(f"  {x}" for x in VOCAB),
                             calib=calib, pairs=pl,
                             text=" ".join(sents)[:6000])
        txt = haiku(prompt)
        got, mapped = set(), 0
        for m in re.finditer(
                r'\{[^{}]*"n"\s*:\s*(\d+)[^{}]*"r"\s*:\s*"([^"]*)"[^{}]*\}', txt):
            i, rel = int(m.group(1)) - 1, m.group(2)
            if not (0 <= i < len(cands)) or rel.strip().upper() == "NONE":
                continue
            pid = LABEL2PID.get(collapse(rel))
            if not pid:
                continue
            mapped += 1
            h, t = cands[i]
            if (h, pid, t) in gold:
                got.add((h, pid, t))
        s = score[k]
        s["gold"] += len(gold)
        s["mapped"] += mapped
        s["hit"] += len(got)
        perdoc[di][k] = {"gold": len(gold), "answered": mapped, "hit": len(got)}
    print(f"  {di+1}/{len(docs)} pairs={len(cands)} gold={len(gold)}  " +
          "  ".join(f"{k}={perdoc[di][k]['hit']}" for k in ARMS), flush=True)

covr = cover["enum"] / max(cover["gold"], 1)
print(f"\n  coverage {covr:.3f}   [exp87 mid: 0.809]")
print(f"\n{'arm':>5} {'answered':>9} {'correct':>8} {'precision':>10} "
      f"{'recall':>8} {'F1':>7}")
res = {}
for k in ARMS:
    s = score[k]
    p = s["hit"] / max(s["mapped"], 1)
    rc = s["hit"] / max(s["gold"], 1)
    res[k] = {"answered": s["mapped"], "hit": s["hit"], "precision": round(p, 4),
              "recall": round(rc, 4), "f1": round(2 * p * rc / max(p + rc, 1e-9), 4)}
    print(f"  {k:>3} {s['mapped']:>9} {s['hit']:>8} {p:>10.3f} {rc:>8.3f} "
          f"{res[k]['f1']:>7.3f}")

# TWO j2b calls returned nothing usable (docs 1 and 11), so the raw j2a-vs-j2b
# gap mixes model variance with API failure. Both are real sources of run-to-run
# difference, but they are different problems with different fixes, so the noise
# floor is reported on the documents where BOTH calls succeeded and the failure
# rate is reported separately.
ok = [di for di in perdoc if perdoc[di]["j2b"]["answered"] > 0
      and perdoc[di]["j2a"]["answered"] > 0]
failed = len(perdoc) - len(ok)


def on(arm, keys):
    g = sum(perdoc[k][arm]["gold"] for k in keys)
    h = sum(perdoc[k][arm]["hit"] for k in keys)
    a = sum(perdoc[k][arm]["answered"] for k in keys)
    pp, rr = h / max(a, 1), h / max(g, 1)
    return {"precision": round(pp, 4), "recall": round(rr, 4),
            "f1": round(2 * pp * rr / max(pp + rr, 1e-9), 4)}


matched = {k: on(k, ok) for k in ARMS}
noise = abs(matched["j2a"]["f1"] - matched["j2b"]["f1"])
noise_r = abs(matched["j2a"]["recall"] - matched["j2b"]["recall"])
print(f"\n  {failed}/{len(perdoc)} j2b calls returned nothing usable — "
      f"a {100*failed/len(perdoc):.0f}% hard-failure rate, reported separately "
      f"from model variance")
print(f"  on the {len(ok)} documents where both calls succeeded:")
for k in ARMS:
    print(f"    {k:>3}  P {matched[k]['precision']:.3f}  R {matched[k]['recall']:.3f}"
          f"  F1 {matched[k]['f1']:.3f}")
j2 = (matched["j2a"]["f1"] + matched["j2b"]["f1"]) / 2
effect = j2 - matched["j0"]["f1"]
rec_hits = [(di, perdoc[di]["j2a"]["hit"], perdoc[di]["j2a"]["gold"])
            for di in perdoc]
rates = sorted(h / max(g, 1) for _, h, g in rec_hits)

print(f"\n  NOISE FLOOR (j2a vs j2b, identical prompt): "
      f"F1 {noise:+.3f}, recall {noise_r:+.3f}")
print(f"  CALIBRATION EFFECT (mean j2 vs j0):          F1 {effect:+.3f}")
print(f"  per-document recall: min {rates[0]:.3f}  median "
      f"{rates[len(rates)//2]:.3f}  max {rates[-1]:.3f}")

v = []
v.append(f"N1 {'CONFIRMED' if noise > 0.02 else 'REFUTED'}: identical prompts "
         f"differ by {noise:.3f} F1 / {noise_r:.3f} recall. Gaps smaller than "
         f"this in earlier experiments are not interpretable.")
v.append(f"N2 {'CONFIRMED' if effect > noise else 'REFUTED'}: calibration effect "
         f"{effect:+.3f} F1 vs noise floor {noise:.3f} — exp86's finding "
         f"{'survives proper measurement' if effect > noise else 'does NOT survive: it is within run-to-run variance'}.")
v.append(f"N3 {'CONFIRMED' if rates[0] < 0.05 else 'REFUTED'}: per-document "
         f"recall ranges {rates[0]:.3f}–{rates[-1]:.3f}; 12 documents is "
         f"{'too small for the +-0.03 distinctions this arc has drawn' if rates[0] < 0.05 else 'more homogeneous than feared'}.")
print("\n=== VERDICTS ===")
for x in v:
    print("  " + x)

(ROOT / "results" / "exp88_noise.json").write_text(json.dumps({
    "n_docs": len(docs), "window": WINDOW, "cap": CAP,
    "coverage": round(covr, 4), "arms": res,
    "noise_floor_f1": round(noise, 4), "noise_floor_recall": round(noise_r, 4),
    "hard_failures": failed, "matched_docs": len(ok), "matched_arms": matched,
    "calibration_effect_f1": round(effect, 4),
    "per_document": {str(k): v_ for k, v_ in perdoc.items()},
    "verdicts": v,
    "scope": ("j2a and j2b are byte-identical requests, so their difference is "
              "pure run-to-run variance. Same 12 documents, gold and scoring as "
              "exp83/85/87 at exp87's mid setting (window 4, cap 260). Per-"
              "document results are stored because exp87 kept only totals, "
              "which is why the exp86 population mismatch could not be "
              "diagnosed from its artifact."),
}, indent=1))
print("\n[done] results/exp88_noise.json")
