"""How stable is D110's answer-type threshold? (owed caveat)

D110 recorded that the selection rule landed on 0.50 in one run and 0.55 in
another and blamed an unseeded cluster basis. That was wrong: `fit_anchors`
passes `random_state=0`. The two runs simply drew different question
samples. The honest characterisation is therefore not "seed the basis" but
"resample the dev/test split and report the spread" — which is what this
does. A threshold picked once on one split is a point estimate; a rule is
only usable if its OUTCOME is stable across splits, so the outcome is what
gets reported.

Usage: .venv/bin/python scripts/exp17_stability.py
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import v06_pipeline as P                                        # noqa: E402
from codec.manifest import run_manifest                          # noqa: E402
from foundation.kb import KB                                     # noqa: E402

world = json.loads((ROOT / "data" / "real_world_ai.json").read_text())
facts, queries = world["facts"], world["queries"]
HELD = set(world["held_out_phrasings"])
d = np.load(ROOT / "results" / "real_world_ai_emb.npz")
Zf, Zq = d["Zf"], d["Zq"]
art = P.build_artifacts(world, Zf, Zq)
RELS = art["RELS"]
det, ans, _ = P.train_heads_with(art, world, Zq,
                                 np.zeros((0, Zq.shape[1]), np.float32),
                                 seed=0, epochs=60)
import torch                                                     # noqa: E402

kb = KB(backend="pg", table="poc")
gold = collections.defaultdict(set)
for c in kb.claims:
    if c["pid"] in RELS and c["page"].startswith("arxiv:"):
        gold[(c["subject"], c["pid"])].add(c["object"])
plan = P.make_planner(det, ans, art)
rng_cprof = art["rng_cprof"]


def walk(subject, path):
    cur = {subject}
    for r in path:
        nxt = set()
        for s in cur:
            nxt |= gold.get((s, r), set())
        if not nxt:
            return set()
        cur = nxt
    return cur


# Score EVERY held-out question once; the sweep is over splits, not over
# re-planning, so the planner cost is paid a single time.
held_all = [i for i, q in enumerate(queries) if q["phrasing_idx"] in HELD]
with torch.no_grad():
    app = torch.softmax(ans(torch.tensor(Zq[held_all])), -1).numpy()
rows = []
for j, i in enumerate(held_all):
    f = facts[queries[i]["fact_idx"]]
    path = plan(Zq[i], f["subject"])
    if not path:
        rows.append(("abstain", 0.0, f["subject"]))
        continue
    got = walk(f["subject"], path)
    o = "abstain" if not got else ("correct" if f["object"] in got else "wrong")
    rows.append((o, float(app[j] @ rng_cprof[path[-1]]), f["subject"]))
print(f"scored {len(rows)} held-out questions", flush=True)

THRS = [round(0.05 * k, 2) for k in range(17)]
subs_all = sorted({r[2] for r in rows})
sweep = []
for seed in range(20):
    s = list(subs_all)
    np.random.default_rng(seed).shuffle(s)
    dev = set(s[: len(s) // 2])

    def tally(thr, in_dev):
        c = collections.Counter()
        for o, fit, sub in rows:
            if (sub in dev) == in_dev:
                c[o if fit >= thr else "abstain"] += 1
        return c

    thr = next((t for t in THRS
                if (lambda c: c["wrong"] / max(sum(c.values()), 1) <= 0.02)(
                    tally(t, True))), THRS[-1])
    T = tally(thr, False)
    n = sum(T.values())
    a = T["correct"] + T["wrong"]
    sweep.append({"seed": seed, "thr": thr,
                  "correct": T["correct"] / n, "wrong": T["wrong"] / n,
                  "abstain": T["abstain"] / n,
                  "precision": T["correct"] / a if a else 0.0})


def spread(k):
    v = np.array([s[k] for s in sweep])
    return float(v.min()), float(np.median(v)), float(v.max())


print("\n20 dev/test subject splits, rule re-applied independently on each")
print(f"{'':11s} {'min':>7} {'median':>7} {'max':>7}")
for k in ("thr", "correct", "wrong", "abstain", "precision"):
    lo, md, hi = spread(k)
    print(f"  {k:9s} {lo:7.3f} {md:7.3f} {hi:7.3f}")
print(f"\nthresholds chosen: {sorted(collections.Counter(s['thr'] for s in sweep).items())}")

out = {"manifest": run_manifest(seed=0, config={"splits": 20,
                                                "grid": THRS}),
       "n_held_out_questions": len(rows),
       "sweep": sweep,
       "spread": {k: dict(zip(("min", "median", "max"), spread(k)))
                  for k in ("thr", "correct", "wrong", "abstain",
                            "precision")},
       "note": ("Corrects D110's caveat: fit_anchors is seeded "
                "(random_state=0), so the 0.50-vs-0.55 difference came from "
                "the two runs drawing different question samples, not from "
                "an unstable cluster basis.")}
(ROOT / "results" / "exp17_stability.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp17_stability.json")
