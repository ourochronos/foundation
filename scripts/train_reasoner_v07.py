"""v0.7 — detector fix for the two replicated weaknesses (D47/D48):
big_pop under-detection (population_of suppressed when paired with
largest_city_of — a never-seen-together pair) and the "runs" mayor↔ceo
confusion under post-freeze templates.

Fixes, both DATA (architecture unchanged, 1024→256→9):
  1. pair-complete composition augmentation: synthetic nested questions for
     every co-occurrence-legal relation pair (legality by counting, D54),
     spliced from nominal templates. NOTE: this retires big_pop as a
     COMPOSITIONAL holdout (logged in D59) — the compositional-transfer
     claim rests on cap_mayor/hq_loc_cap/K6-natural-data.
  2. contrast set for the "runs/leads/heads" verb family: same verbs, city
     vs company subjects, opposite labels.

Acceptance (pre-registered in D48): on the K5 FROZEN templates — big_pop
and the "runs" cells (mayor_born 0.700, cap_mayor 0.500) must close
without regressing the other 9 compositions or singles (0.900).

Usage: .venv/bin/python scripts/train_reasoner_v07.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from codec.manifest import run_manifest, wilson_ci                # noqa: E402
from codec.memory_store import id_tokens                          # noqa: E402
import v06_pipeline as P                                          # noqa: E402

torch.manual_seed(0)
rng = random.Random(0)
w = json.loads((ROOT / "data" / "closed_world_v4.json").read_text())
facts, queries, hops = w["facts"], w["queries"], w["hops"]
Zf, Zq, Zh = P.load_or_build_emb(
    w, ROOT / "results" / "closed_world_v4_emb.npz")
art = P.build_artifacts(w, Zf, Zq)
RELS, KC = art["RELS"], P.KC
R = len(RELS)

# ---- augmentation 1: pair-complete nested questions -----------------------
NOM = {"capital_of": "the capital of {s}",
       "largest_city_of": "the largest city of {s}",
       "located_in": "the country containing {s}",
       "headquartered_in": "the city where {s} is based",
       "mayor_of": "the mayor of {s}",
       "ceo_of": "the chief executive of {s}"}
OUTER = {"population_of": ["How many people live in {x}?",
                           "What is the population of {x}?"],
         "mayor_of": ["Who is the mayor of {x}?", "Who governs {x}?"],
         "capital_of": ["What is the capital of {x}?"],
         "largest_city_of": ["What is the largest city of {x}?"],
         "located_in": ["Which country is {x} in?"],
         "born_in": ["In which year was {x} born?"],
         "founded_in": ["In which year was {x} founded?"],
         "headquartered_in": ["Where is {x} headquartered?"],
         "ceo_of": ["Who is the CEO of {x}?"]}
subj_slots, obj_slots = {}, {}
for f in facts:
    subj_slots.setdefault(f["subject"], set()).add(f["relation"])
    obj_slots.setdefault(f["object"], set()).add(f["relation"])
BRIDGE = {(a, b) for n in set(subj_slots) | set(obj_slots)
          for a in obj_slots.get(n, ()) for b in subj_slots.get(n, ())}
subs_of = {r: sorted({f["subject"] for f in facts if f["relation"] == r})
           for r in RELS}
trained_pairs = {tuple(h["chain"]) for h in hops if len(h["chain"]) == 2
                 and h["kind"] not in w["holdout_compositions"]}
# F1 (adversarial review, D64): holdout-chain pairs must NOT be augmented
# either — v0.7's first run synthesized (capital_of, mayor_of), silently
# consuming the cap_mayor holdout. Exclude every consecutive pair of every
# holdout chain so the holdouts stay holdouts.
holdout_pairs = set()
for h in hops:
    if h["kind"] in w["holdout_compositions"]:
        holdout_pairs |= set(zip(h["chain"], h["chain"][1:]))
aug_texts, aug_labels = [], []
for r1 in NOM:
    for r2 in OUTER:
        if (r1, r2) not in BRIDGE or (r1, r2) in trained_pairs \
                or (r1, r2) in holdout_pairs or r1 == r2:
            continue
        for s_ in rng.sample(subs_of[r1], min(60, len(subs_of[r1]))):
            t = rng.choice(OUTER[r2]).format(x=NOM[r1].format(s=s_))
            y = np.zeros(R, np.float32)
            y[RELS.index(r1)] = y[RELS.index(r2)] = 1.0
            aug_texts.append(t); aug_labels.append(y)
n_pair = len(aug_texts)

# ---- augmentation 2: "runs" contrast set ----------------------------------
VERBS = ["Who runs {x}?", "Who is in charge of {x}?", "Who heads {x}?",
         "Who leads {x}?", "Name the person at the top of {x}."]
for s_ in rng.sample(subs_of["mayor_of"], 120):
    y = np.zeros(R, np.float32); y[RELS.index("mayor_of")] = 1.0
    aug_texts.append(rng.choice(VERBS).format(x=s_)); aug_labels.append(y)
for s_ in rng.sample(subs_of["ceo_of"], 120):
    y = np.zeros(R, np.float32); y[RELS.index("ceo_of")] = 1.0
    aug_texts.append(rng.choice(VERBS).format(x=s_)); aug_labels.append(y)
print(f"[aug] {n_pair} pair-complete + {len(aug_texts)-n_pair} contrast",
      flush=True)

cache = ROOT / "results" / "v07_aug_emb.npz"
if cache.exists():
    Za = np.load(cache)["Za"]
else:
    Za = P.embed_texts(aug_texts)
    np.savez(cache, Za=Za)

# ---- heads: D44 training set + augmentation -------------------------------
HELD = art["HELD"]
HOLD = set(w["holdout_compositions"])
Xs, Ys = [], []
for i, q in enumerate(queries):
    if q["kind"] == "single" and q["phrasing_idx"] not in HELD:
        y = np.zeros(R, np.float32)
        y[RELS.index(q["relation"])] = 1.0
        Xs.append(Zq[i]); Ys.append(y)
hop_rows = [(i, h) for i, h in enumerate(hops) if h["kind"] not in HOLD]
prm = np.random.default_rng(0).permutation(len(hop_rows))
cut = int(0.8 * len(hop_rows))
for j in prm[:cut]:
    i, h = hop_rows[j]
    y = np.zeros(R, np.float32)
    for r in h["chain"]:
        y[RELS.index(r)] = 1.0
    Xs.append(Zh[i]); Ys.append(y)
Xs += list(Za); Ys += aug_labels
X = torch.tensor(np.stack(Xs)); Y = torch.tensor(np.stack(Ys))
det = nn.Sequential(nn.Linear(1024, 256), nn.GELU(), nn.Linear(256, R))
opt = torch.optim.AdamW(det.parameters(), lr=1e-3, weight_decay=1e-4)
lf = nn.BCEWithLogitsLoss()
for ep in range(60):
    for b in torch.randperm(len(X)).split(512):
        opt.zero_grad(); lf(det(X[b]), Y[b]).backward(); opt.step()
torch.save(det.state_dict(), ROOT / "checkpoints" / "reasoner_v07_det.pt")
print(f"[det] trained n={len(X)}", flush=True)

ans = nn.Sequential(nn.Linear(1024, 128), nn.GELU(), nn.Linear(128, KC))
ans.load_state_dict(torch.load(ROOT / "checkpoints" / "reasoner_v06_ans.pt",
                               weights_only=True))

plan = P.make_planner(det, ans, art)
walker = art["walker"]

# ---- acceptance: K5 frozen templates (same rows, cached embeddings) -------
import importlib.util as _ilu
_k5src = (ROOT / "scripts" / "probe_frozen_templates_k5.py").read_text()
_tdefs = _k5src.split("SINGLE_T = ")[1].split("w = json.loads")[0]
exec("SINGLE_T = " + _tdefs)  # defines SINGLE_T and HOP_T dicts
rng5 = random.Random(7)
srows = []
for rel, ts in SINGLE_T.items():
    fs = [i for i, f in enumerate(facts) if f["relation"] == rel]
    for j, fi in enumerate(rng5.sample(fs, 40)):
        srows.append({"fact_idx": fi, "relation": rel,
                      "text": ts[j % len(ts)].format(s=facts[fi]["subject"])})
hrows = []
for kind, ts in HOP_T.items():
    ks = [h for h in hops if h["kind"] == kind]
    for j, h in enumerate(rng5.sample(ks, 30)):
        hrows.append({**h, "text": ts[j % len(ts)].format(s=h["subject"])})
k5z = np.load(ROOT / "results" / "frozen_templates_k5_emb.npz")
Zs, Zhn = k5z["Zs"], k5z["Zhn"]

res = {}
hit = 0
for r_, zq in zip(srows, Zs):
    pp = plan(zq, facts[r_["fact_idx"]]["subject"])
    if pp and not walker.abstain_hop1(P.qids_of(r_["text"]), pp[0]):
        hit += walker.walk(P.qids_of(r_["text"]), pp) == r_["fact_idx"]
res["single"] = {"p1": hit / len(srows), "n": len(srows)}
print(f"[v07-k5   single] P@1={hit/len(srows):.3f} [v0.6: 0.900]",
      flush=True)
BASE = {"big_pop": 0.500, "cap_mayor": 0.467, "mayor_born": 0.700}
for kind in sorted(HOP_T):
    rows = [(r_, Zhn[i]) for i, r_ in enumerate(hrows)
            if r_["kind"] == kind]
    pok = hit = 0
    for r_, zq in rows:
        pp = plan(zq, r_["subject"])
        pok += pp == r_["chain"]
        if pp and not walker.abstain_hop1(P.qids_of(r_["text"]), pp[0]):
            hit += walker.walk(P.qids_of(r_["text"]), pp) == r_["answer_fact"]
    res[kind] = {"chain": pok / len(rows), "p1": hit / len(rows),
                 "n": len(rows)}
    ref = f" [v0.6: {BASE[kind]:.3f}]" if kind in BASE else ""
    print(f"[v07-k5 {kind:>12}] chain={pok/len(rows):.3f} "
          f"P@1={hit/len(rows):.3f}{ref}", flush=True)

# ---- v4 regression: holdouts + detector-held-back trained rows ------------
hop_eval_ids = {hop_rows[j][0] for j in prm[cut:]}
reg_res = P.evaluate(w, Zq, Zh, art, plan, hop_eval_ids=hop_eval_ids,
                     tag="v07 ")
for row in list(res.values()) + list(reg_res.values()):
    if "n" in row:
        for m in ("chain", "p1", "abstain"):
            if m in row:
                row[m + "_ci95"] = wilson_ci(round(row[m] * row["n"]),
                                             row["n"])
out = ROOT / "results" / "reasoner_v07.json"
out.write_text(json.dumps(
    {"k5_frozen": res, "v4_regression": reg_res,
     "aug": {"pair_complete": n_pair,
             "contrast": len(aug_texts) - n_pair},
     "manifest": run_manifest(seed=0, config={
         "note": "big_pop retired as compositional holdout (pair-complete "
                 "augmentation); transfer claim rests on cap_mayor/"
                 "hq_loc_cap/K6"})}, indent=2))
print(f"[done] {out.relative_to(ROOT)}")
