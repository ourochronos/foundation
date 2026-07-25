"""v0.6 hybrid reasoner — learned detection ∘ soft unification ∘ store walk.

The decomposition every prior rung measured its way to:
  detection  LEARNED multi-label head (question gist → which relations are
             mentioned, unordered). v0.1 showed relation *logits* were fine
             while sequence prediction failed; D41 showed span-prototype
             detection is the planner's only bottleneck (spurious-append vs
             weak-but-real is not separable by span cosine).
  assembly   D41 soft unification: participation-type feasibility gate +
             evidence ranking. Zero hand schema.
  execution  D43 channel-separated walk (proto+t dense, id hand-off).
  abstain    id-coverage (B2) OR hop-1 relation mismatch: classify the
             retrieved fact's relation as argmax_r cos(z_fact, proto_r+t_r)
             and abstain if it isn't the requested one (relations-as-entries
             cashing out as a discrete readout).

Training data: single-hop queries + TRAINED-composition hop questions, seen
phrasings only. Holdout compositions and held-out phrasings never seen.

Usage: .venv/bin/python scripts/train_reasoner_v06.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# reuse the J3 probe's store, types, relation entries, walk, qids (exec the
# module body up to its eval loop — same pattern as the v0.3 debug harness)
_src = (ROOT / "scripts" / "probe_soft_planner.py").read_text()
_head = _src.split("res, chain_ok = {}, {}")[0].replace(
    'ROOT = Path(__file__).resolve().parent.parent', f'ROOT = Path("{ROOT}")')
exec(_head)  # noqa: S102 — facts/queries/hops/store/rel_entry/walk/plan/...

import torch  # noqa: E402
from torch import nn  # noqa: E402

torch.manual_seed(0)
np.random.seed(0)
R = len(RELS)
HOLDOUT = set(world["holdout_compositions"])
HELD_PHR = set(world["held_out_phrasings"])

# ---- detector training set: singles + trained comps, seen phrasings ----
Xs, Ys = [], []
for i, q in enumerate(queries):
    if q["kind"] == "single" and q["phrasing_idx"] not in HELD_PHR:
        y = np.zeros(R, np.float32)
        y[RELS.index(q["relation"])] = 1.0
        Xs.append(Zq[i]); Ys.append(y)
hop_rows = []
for i, h in enumerate(hops):
    if h["kind"] not in HOLDOUT:
        y = np.zeros(R, np.float32)
        for r in h["chain"]:
            y[RELS.index(r)] = 1.0
        hop_rows.append((i, y))
# hold back 20% of trained-comp questions from detector training so the
# trained-comp eval row is not memorized
rng = np.random.default_rng(0)
perm = rng.permutation(len(hop_rows))
cut = int(0.8 * len(hop_rows))
for j in perm[:cut]:
    i, y = hop_rows[j]
    Xs.append(Zh[i]); Ys.append(y)
hop_eval_ids = {hop_rows[j][0] for j in perm[cut:]}
X = torch.tensor(np.stack(Xs)); Y = torch.tensor(np.stack(Ys))
print(f"[data] detector train n={len(X)} "
      f"(singles + {cut} trained-comp questions)", flush=True)

det_head = nn.Sequential(nn.Linear(1024, 256), nn.GELU(),
                         nn.Linear(256, R))
opt = torch.optim.AdamW(det_head.parameters(), lr=1e-3, weight_decay=1e-4)
lossf = nn.BCEWithLogitsLoss()
for ep in range(60):
    idx = torch.randperm(len(X))
    tot = 0.0
    for b in idx.split(512):
        opt.zero_grad()
        loss = lossf(det_head(X[b]), Y[b])
        loss.backward(); opt.step()
        tot += float(loss) * len(b)
    if (ep + 1) % 20 == 0:
        print(f"[train] ep{ep+1} loss={tot/len(X):.4f}", flush=True)
torch.save(det_head.state_dict(), ROOT / "checkpoints" / "reasoner_v06_det.pt")

# ---- learned answer-type head: question -> participation cluster of the
# answer object (the D41 cosine aprof is mush: truncated chains scored HIGHER
# than gold, 0.392 vs 0.346 — measured before this rewrite) ----
Xa, Ya = [], []
for i, q in enumerate(queries):
    if q["kind"] == "single" and q["phrasing_idx"] not in HELD_PHR:
        obj = facts[q["fact_idx"]]["object"]
        if obj in clus_of:
            Xa.append(Zq[i]); Ya.append(clus_of[obj])
for j in perm[:cut]:
    i, _ = hop_rows[j]
    obj = facts[hops[i]["answer_fact"]]["object"]
    if obj in clus_of:
        Xa.append(Zh[i]); Ya.append(clus_of[obj])
Xa_t = torch.tensor(np.stack(Xa)); Ya_t = torch.tensor(Ya)
ans_head = nn.Sequential(nn.Linear(1024, 128), nn.GELU(), nn.Linear(128, KC))
opta = torch.optim.AdamW(ans_head.parameters(), lr=1e-3)
ce = nn.CrossEntropyLoss()
for ep in range(40):
    idx = torch.randperm(len(Xa_t))
    for b in idx.split(512):
        opta.zero_grad(); ce(ans_head(Xa_t[b]), Ya_t[b]).backward(); opta.step()
torch.save(ans_head.state_dict(), ROOT / "checkpoints" / "reasoner_v06_ans.pt")
print(f"[ans_head] trained n={len(Xa_t)}", flush=True)

for r in RELS:
    if r not in rng_cprof:
        rng_cprof[r] = rng_cluster_prof(r)

@torch.no_grad()
def detect(q_emb):
    p = torch.sigmoid(det_head(torch.tensor(q_emb)[None]))[0].numpy()
    return {r: float(p[j]) for j, r in enumerate(RELS)}

# ---- assembly: D41 unification with learned det probabilities ----
def plan_v06(q_emb, subject):
    det = detect(q_emb)
    cand = sorted(det, key=det.get, reverse=True)[:4]
    # confidently detected relations are REQUIRED: if no type-feasible chain
    # contains them, planning fails -> abstain. Without this, the feasibility
    # gate silently rewrites unanswerable questions into answerable ones
    # (born_in of a CITY -> [mayor_of, born_in], answering the mayor's birth).
    req = {r for r in RELS if det[r] > 0.5}
    cand = [r for r in cand if det[r] >= 0.2]   # chains build ONLY from
    # detected relations — without this floor the planner smuggles in a
    # det~0.0 relation to satisfy req feasibly ([mayor_of, born_in] for a
    # city birth question) instead of failing to plan
    if subject not in name_i:
        return None
    subj_p = P_name[name_i[subject]]
    with torch.no_grad():
        ap = torch.softmax(ans_head(torch.tensor(q_emb)[None]), -1)[0].numpy()
    best, best_s = None, -1e9
    for k in range(1, 4):
        for pm in permutations(cand, k):
            feas = cosd(subj_p, rel_entry[pm[0]]["dom"])
            for a, b in zip(pm, pm[1:]):
                feas = min(feas, cosd(rel_entry[a]["rng"], rel_entry[b]["dom"]))
            if feas < 0.35 or not req <= set(pm):
                continue
            # product of experts, both learned: detection log-odds +
            # answer-type log-mass (predicted answer cluster under the last
            # relation's range distribution). aw=1.0 by construction, not
            # tuned (holdout sensitivity 0.46/0.54/0.60 at 0.5/1/2 — logged).
            ev = sum(np.log(max(det[r], 1e-4) / (1 - min(det[r], 1 - 1e-4)))
                     for r in pm)
            ans = float(ap @ rng_cprof[pm[-1]])
            s_ = ev + np.log(max(ans, 1e-4))
            if s_ > best_s:
                best_s, best = s_, list(pm)
    return best


def abstain_hop1(q_z, q_ids, rel):
    """Canonical readout (codec/walker.py): coverage OR relation-classify
    mismatch (measured: recall 1.000, false-abstain 0.010)."""
    return walker.abstain_hop1(q_ids, rel)

# ---- eval: all compositions (holdouts flagged), trained rows use the 20%
# detector-held-back questions; singles on held-out phrasings; no_answer ----
res = {}
print("[eval]", flush=True)
for kind in sorted({h["kind"] for h in hops}):
    if kind in HOLDOUT:
        cases = [(h, Zh[i]) for i, h in enumerate(hops) if h["kind"] == kind]
    else:
        cases = [(h, Zh[i]) for i, h in enumerate(hops)
                 if h["kind"] == kind and i in hop_eval_ids]
    if not cases:
        continue
    hit = pok = 0
    for h, zq in cases:
        p = plan_v06(zq, h["subject"])
        pok += p == h["chain"]
        if p and not abstain_hop1(zq, qids_of(h["text"]), p[0]):
            hit += walk(zq, qids_of(h["text"]), p) == h["answer_fact"]
    res[kind] = {"chain": pok / len(cases), "p1": hit / len(cases),
                 "n": len(cases)}
    tag = " [HOLDOUT]" if kind in HOLDOUT else ""
    print(f"[v06 {kind:>12}] chain={pok/len(cases):.3f} "
          f"P@1={hit/len(cases):.3f} (n={len(cases)}){tag}", flush=True)

singles_eval = [i for i, q in enumerate(queries) if q["kind"] == "single"
                and q["phrasing_idx"] in HELD_PHR][:400]
hit = 0
for i in singles_eval:
    q = queries[i]
    p = plan_v06(Zq[i], facts[q["fact_idx"]]["subject"])
    if p and not abstain_hop1(Zq[i], qids_of(q["text"]), p[0]):
        hit += walk(Zq[i], qids_of(q["text"]), p) == q["fact_idx"]
res["single"] = {"p1": hit / len(singles_eval), "n": len(singles_eval)}
print(f"[v06       single] P@1={hit/len(singles_eval):.3f} "
      f"(n={len(singles_eval)}, held-out phrasings)", flush=True)

na = [i for i, q in enumerate(queries) if q["kind"] == "no_answer"][:200]
abst = 0
for i in na:
    q = queries[i]
    subj = next((n for n in name_i if n in q["text"]), "")
    p = plan_v06(Zq[i], subj)
    abst += (p is None) or abstain_hop1(Zq[i], qids_of(q["text"]), p[0])
res["no_answer"] = {"abstain": abst / len(na), "n": len(na)}
print(f"[v06    no_answer] abstain={abst/len(na):.3f} (n={len(na)})",
      flush=True)

from codec.manifest import run_manifest, wilson_ci
for kind, row in res.items():
    for key in ("chain", "p1", "abstain"):
        if key in row:
            row[key + "_ci95"] = wilson_ci(round(row[key] * row["n"]),
                                           row["n"])
out = ROOT / "results" / "reasoner_v06.json"
out.write_text(json.dumps(
    {"results": res,
     "detector": {"params": sum(p_.numel() for p_ in det_head.parameters()),
                  "train_n": len(X)},
     "ans_head": {"params": sum(p_.numel() for p_ in ans_head.parameters()),
                  "train_n": len(Xa_t)},
     "manifest": run_manifest(seed=0, inputs={
         "world": ROOT / "data" / "closed_world_v4.json",
         "emb_cache": ROOT / "results" / "closed_world_v4_emb.npz"},
         config={"det_floor": 0.2, "req_thr": 0.5, "aw": 1.0,
                 "feas_thr": 0.35, "holdback": 0.2})},
    indent=2))
print(f"[done] {out.relative_to(ROOT)}")
