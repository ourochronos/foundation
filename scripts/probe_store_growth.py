"""J4 — store-growth invariance (D38 §2's continual-learning end-to-end check).

Protocol: the v0.6 heads are trained on world v4 (seed 41) and FROZEN, as is
the participation-cluster basis PC they were trained against. The store then
DOUBLES with seed-43's facts (new entities; ~650 surface-name collisions —
honest aliasing stress, reported). Everything store-side is recomputed
closed-form over the union: participation vectors, relation dom/rng
signatures, question prototypes, translation operators, range-cluster
profiles. Measured:

  A. seed-41 questions against the 2× store — does doubling the distractor
     mass break retrieval/planning that worked at 1×? (baseline = D44)
  B. seed-43 questions (subjects the heads NEVER saw; for holdout
     compositions, never-seen composition shapes over never-seen entities)
     — does the reasoner transfer to new store content with zero retraining?

Usage: .venv/bin/python scripts/probe_store_growth.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from codec.manifest import run_manifest, wilson_ci                # noqa: E402
import v06_pipeline as P                                          # noqa: E402

w41 = json.loads((ROOT / "data" / "closed_world_v4.json").read_text())
w43 = json.loads((ROOT / "data" / "closed_world_v4_s43.json").read_text())
Zf1, Zq1, Zh1 = P.load_or_build_emb(
    w41, ROOT / "results" / "closed_world_v4_emb.npz")
print("[emb] seed-43 world (build on first run)", flush=True)
Zf3, Zq3, Zh3 = P.load_or_build_emb(
    w43, ROOT / "results" / "closed_world_v4_s43_emb.npz")

# ---- heads trained on seed-41 only (identical procedure/seed to D44) ----
art41 = P.build_artifacts(w41, Zf1, Zq1)                # fresh PC -> frozen
det_head, ans_head, hop_eval_ids = P.train_heads_with(art41, w41, Zq1, Zh1)
print(f"[heads] trained on seed-41; {len(hop_eval_ids)} held-back hop rows",
      flush=True)

# ---- union world: seed-41 facts [0, n1) + seed-43 facts [n1, n1+n3) ----
n1 = len(w41["facts"])
q43 = []
for q in w43["queries"]:
    q = dict(q)
    if q["fact_idx"] >= 0:
        q["fact_idx"] += n1
    q43.append(q)
union = {"facts": w41["facts"] + w43["facts"],
         "queries": w41["queries"] + q43,
         "hops": [],
         "held_out_phrasings": w41["held_out_phrasings"],
         "holdout_compositions": w41["holdout_compositions"]}
Zf_u = np.concatenate([Zf1, Zf3])
Zq_u = np.concatenate([Zq1, Zq3])
art_u = P.build_artifacts(union, Zf_u, Zq_u, PC=art41["PC"])
coll = len({f["subject"] for f in w41["facts"]}
           & {f["subject"] for f in w43["facts"]})
print(f"[store] {n1} -> {len(union['facts'])} facts "
      f"({coll} cross-seed subject collisions)", flush=True)

plan = P.make_planner(det_head, ans_head, art_u)

print("[eval A] seed-41 questions vs 2x store", flush=True)
resA = P.evaluate(w41, Zq1, Zh1, art_u, plan, hop_eval_ids=hop_eval_ids,
                  fact_offset=0, tag="A ")
print("[eval B] seed-43 questions (novel entities) vs 2x store", flush=True)
resB = P.evaluate(w43, Zq3, Zh3, art_u, plan, hop_eval_ids=None,
                  fact_offset=n1, tag="B ")

base = json.loads((ROOT / "results" / "reasoner_v06.json").read_text())
deltas = {}
for k, row in resA.items():
    b = base["results"].get(k, {})
    for m in ("chain", "p1", "abstain"):
        if m in row and m in b:
            deltas.setdefault(k, {})[m] = round(row[m] - b[m], 4)
print("[delta A vs 1x-store baseline]",
      json.dumps(deltas, separators=(",", ":")), flush=True)

for res in (resA, resB):
    for row in res.values():
        for m in ("chain", "p1", "abstain"):
            if m in row:
                row[m + "_ci95"] = wilson_ci(round(row[m] * row["n"]),
                                             row["n"])

out = ROOT / "results" / "store_growth_j4.json"
out.write_text(json.dumps(
    {"A_seed41_vs_2x": resA, "B_seed43_novel": resB,
     "delta_A_vs_baseline": deltas,
     "collisions": coll, "store_size": len(union["facts"]),
     "manifest": run_manifest(seed=0, inputs={
         "world41": ROOT / "data" / "closed_world_v4.json",
         "world43": ROOT / "data" / "closed_world_v4_s43.json",
         "emb41": ROOT / "results" / "closed_world_v4_emb.npz",
         "emb43": ROOT / "results" / "closed_world_v4_s43_emb.npz"},
         config={"frozen": ["det_head", "ans_head", "PC"],
                 "recomputed": ["P_name", "rel_entry", "operators",
                                "rng_cprof", "store"]})},
    indent=2))
print(f"[done] {out.relative_to(ROOT)}")
