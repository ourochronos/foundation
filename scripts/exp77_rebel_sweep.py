"""Can decoding parameters move REBEL's 0.155 recall? A precision/recall curve.

exp76 measured extraction at precision 0.222 / recall 0.155 with `num_beams=3`,
chosen arbitrarily and never examined. Since every corroboration and conflict
number in this project is a lower bound set by that recall, a cheap sweep is
worth more than another experiment run through the same sieve.

The knobs are decoding-side, so nothing is retrained:

- **num_beams / num_return_sequences** — REBEL emits one triple set per returned
  sequence, so returning more sequences strictly adds candidate triples. This
  should trade precision for recall and the question is the exchange rate.
- **length_penalty** — favours longer generations, which for this model means
  more triples per sequence rather than longer strings.

Predictions, registered before running:

- **P1** recall rises monotonically with returned sequences and precision falls
  — the usual trade.
- **P2** the trade is **worth taking** for this project's purposes: F1 peaks
  above `nb=3`, because a store that surfaces disagreement can tolerate false
  candidates (they are attributed and disputable) far better than it can
  tolerate missing the claim entirely.
- **P3** `length_penalty` matters less than beam count, since it shifts
  sequence length rather than the number of returned sequences.

Usage: .venv/bin/python scripts/exp77_rebel_sweep.py [n_docs]
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 12

props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
docs = json.loads((ROOT / "data" / "gold" / "docred_200.json").read_text())[:N]


def collapse(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(s).lower())).strip()


LABEL2PID = {}
for pid, d in props.items():
    for nm in [d.get("label")] + list(d.get("aliases", [])):
        if nm:
            LABEL2PID.setdefault(collapse(nm), pid)

tok = AutoTokenizer.from_pretrained("Babelscape/rebel-large")
mdl = AutoModelForSeq2SeqLM.from_pretrained("Babelscape/rebel-large")
dev = "cuda" if torch.cuda.is_available() else "cpu"
mdl.to(dev).eval()
print(f"REBEL on {dev}, {len(docs)} docs", flush=True)


def parse(decoded):
    out = []
    for d in decoded:
        d = d.replace("<s>", "").replace("</s>", "").replace("<pad>", "")
        s = r = o = ""
        cur = None
        for t in d.split():
            if t == "<triplet>":
                if s and r and o:
                    out.append((s.strip(), r.strip(), o.strip()))
                s, cur = "", "s"
            elif t == "<subj>":
                o, cur = "", "o"
            elif t == "<obj>":
                r, cur = "", "r"
            else:
                if cur == "s":
                    s += " " + t
                elif cur == "o":
                    o += " " + t
                elif cur == "r":
                    r += " " + t
        if s and r and o:
            out.append((s.strip(), r.strip(), o.strip()))
    return set(out)


def run(text, nb, lp):
    enc = tok(text, return_tensors="pt", truncation=True, max_length=256).to(dev)
    with torch.no_grad():
        g = mdl.generate(**enc, max_length=200, num_beams=nb,
                         num_return_sequences=nb, length_penalty=lp)
    return parse(tok.batch_decode(g, skip_special_tokens=False))


CONFIGS = [(nb, lp) for nb in (1, 3, 5, 8, 12) for lp in (1.0,)] + \
          [(5, lp) for lp in (0.5, 2.0)]
score = {c: collections.Counter() for c in CONFIGS}

for di, doc in enumerate(docs):
    vs = doc["vertexSet"]
    names = [{collapse(m["name"]) for m in v} for v in vs]
    gold = {(l["h"], l["r"], l["t"]) for l in doc["labels"]}
    sents = [" ".join(s) for s in doc["sents"] if len(" ".join(s)) >= 30]
    for cfg in CONFIGS:
        nb, lp = cfg
        preds = set()
        for text in sents:
            preds |= run(text, nb, lp)
        matched, mapped = set(), 0
        for s, r, o in preds:
            pid = LABEL2PID.get(collapse(r))
            if not pid:
                continue
            mapped += 1
            hs = [i for i, ns in enumerate(names) if collapse(s) in ns]
            ts = [i for i, ns in enumerate(names) if collapse(o) in ns]
            for h in hs:
                for t in ts:
                    if (h, pid, t) in gold:
                        matched.add((h, pid, t))
        score[cfg]["gold"] += len(gold)
        score[cfg]["mapped"] += mapped
        score[cfg]["hit"] += len(matched)
    if (di + 1) % 4 == 0:
        print(f"  {di + 1}/{len(docs)}", flush=True)

print(f"\n{'beams':>6} {'len_pen':>8} {'in-vocab':>9} {'correct':>8} "
      f"{'precision':>10} {'recall':>8} {'F1':>7}")
res = {}
for cfg in CONFIGS:
    s = score[cfg]
    p = s["hit"] / max(s["mapped"], 1)
    rc = s["hit"] / max(s["gold"], 1)
    f1 = 2 * p * rc / max(p + rc, 1e-9)
    res[f"nb{cfg[0]}_lp{cfg[1]}"] = {"beams": cfg[0], "length_penalty": cfg[1],
                                     "mapped": s["mapped"], "hit": s["hit"],
                                     "precision": round(p, 4),
                                     "recall": round(rc, 4), "f1": round(f1, 4)}
    print(f"  {cfg[0]:>4} {cfg[1]:>8.1f} {s['mapped']:>9} {s['hit']:>8} "
          f"{p:>10.3f} {rc:>8.3f} {f1:>7.3f}")

beam_only = [res[f"nb{nb}_lp1.0"] for nb in (1, 3, 5, 8, 12)]
best = max(res.values(), key=lambda x: x["f1"])
base = res["nb3_lp1.0"]
lp_spread = max(res[f"nb5_lp{l}"]["f1"] for l in (0.5, 1.0, 2.0)) - \
            min(res[f"nb5_lp{l}"]["f1"] for l in (0.5, 1.0, 2.0))
beam_spread = max(x["f1"] for x in beam_only) - min(x["f1"] for x in beam_only)

v = []
mono_r = all(beam_only[i]["recall"] <= beam_only[i + 1]["recall"] + 1e-9
             for i in range(len(beam_only) - 1))
v.append(f"P1 {'CONFIRMED' if mono_r else 'REFUTED'}: recall over beams "
         f"{[x['recall'] for x in beam_only]}, precision "
         f"{[x['precision'] for x in beam_only]}.")
v.append(f"P2 {'CONFIRMED' if best['beams'] > 3 else 'REFUTED'}: best F1 "
         f"{best['f1']:.3f} at beams={best['beams']} vs {base['f1']:.3f} at the "
         f"arbitrary default of 3 — recall {base['recall']:.3f} -> "
         f"{best['recall']:.3f}.")
v.append(f"P3 {'CONFIRMED' if lp_spread < beam_spread else 'REFUTED'}: "
         f"length_penalty moves F1 by {lp_spread:.3f}, beam count by "
         f"{beam_spread:.3f}.")
print("\n=== VERDICTS ===")
for x in v:
    print("  " + x)

(ROOT / "results" / "exp77_sweep.json").write_text(json.dumps({
    "n_docs": len(docs), "configs": res, "best": best, "verdicts": v,
    "scope": ("Decoding-side only, nothing retrained. Same gold, scoring and "
              "entity matching as exp76, so numbers are directly comparable to "
              "its 0.222/0.155 at beams=3. REBEL returns one triple set per "
              "returned sequence, so beam count is the primary recall knob."),
}, indent=1))
print("\n[done] results/exp77_sweep.json")
