"""Give the parametric head a fair fight (D148).

Task 2, and the falsifier D145's adversarial pass named for claim 9:

    "A better-trained parametric head matching 1-NN would falsify
     information destruction; one underperforming head does not rule
     that out."

That is a fair criticism. D129 compared 1-NN retrieval (0.925) against **one**
head — 512 hidden units, 40 epochs, an MSE-on-coordinates objective — and
concluded the head "destroys information the encoder preserves". One
configuration is not a bound.

**There is also a design flaw in that comparison worth naming up front.** The
head is trained as a REGRESSION onto a relation's coordinate, but scored as
nearest-centroid CLASSIFICATION over relations. Train and eval objectives
never matched, which is exactly the kind of mismatch that makes a model look
incapable when it was only misdirected. A contrastive objective — pull the
question toward its own relation and push it from the others — aligns them,
and is the arm most likely to close the gap.

Sweep, on D129's own population and cache, with training data held FIXED at
the two aliases D129 quoted so only the head varies:

  * objective : MSE on coordinates | cosine | contrastive (InfoNCE)
  * capacity  : 512 | 1024 | 2048 hidden
  * epochs    : 40 | 120 | 300 for the best config

1-NN is the fixed reference throughout.

**If the best head reaches 1-NN, D129 is withdrawn** and the architecture
recommendation changes. If it plateaus below, the claim becomes far stronger
than it is now: not "a head lost" but "no head we could train at any capacity
or objective matched retrieval".

Usage: .venv/bin/python scripts/exp49_fair_head.py
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
from codec.manifest import run_manifest, wilson_ci               # noqa: E402
from foundation.kb import KB                                     # noqa: E402

SEED, MIN_ALIAS, N_SUBJ, N_EVAL_ALIAS = 0, 6, 60, 2
TRAIN_ALIASES = 2                     # exactly what D129 quoted 0.614 for

sch = {d["pid"]: d for d in
       json.loads((ROOT / "data" / "schema_v0.json").read_text())}
props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
kb = KB(backend="pg", table="poc")
wiki = [c for c in kb.claims
        if not c["page"].startswith(("arxiv:", "hf:", "user"))]
LABEL, ALIAS = {}, {}
for c in wiki:
    p = c["pid"]
    if p in LABEL:
        continue
    lab = (sch.get(p) or {}).get("label") or (props.get(p) or {}).get("label")
    al = list((sch.get(p) or {}).get("aliases", []))
    al += [a for a in (props.get(p) or {}).get("aliases", []) if a not in al]
    al = [a for a in al if 2 < len(a) < 40]
    if lab and len(al) >= MIN_ALIAS:
        LABEL[p], ALIAS[p] = lab, al[:MIN_ALIAS]
RELS = sorted(LABEL)
gold = collections.defaultdict(set)
for c in wiki:
    if c["pid"] in LABEL:
        gold[(c["subject"], c["pid"])].add(c["object"])
by_rel = collections.defaultdict(list)
for (s, r) in sorted(gold):
    by_rel[r].append(s)
rng = np.random.default_rng(SEED)
SUBJ = {r: ([by_rel[r][i] for i in
             sorted(rng.choice(len(by_rel[r]), N_SUBJ, replace=False))]
            if len(by_rel[r]) > N_SUBJ else by_rel[r]) for r in RELS}
rows = [{"rel": r, "ai": ai, "text": f"What is the {a} of {s}?"}
        for r in RELS for ai, a in enumerate(ALIAS[r]) for s in SUBJ[r]]
z = np.load(ROOT / "results" / "exp35_emb.npz", allow_pickle=True)
assert list(z["texts"]) == [x["text"] for x in rows], \
    "population drifted from D129 — this must reuse that cache exactly"
Z, Zl = z["Z"], z["Zl"]
RC = {r: Zl[i] for i, r in enumerate(RELS)}
M = np.stack([RC[r] for r in RELS])
ridx = {r: i for i, r in enumerate(RELS)}
TR = [i for i, x in enumerate(rows) if x["ai"] < TRAIN_ALIASES]
EV = [i for i, x in enumerate(rows) if x["ai"] >= MIN_ALIAS - N_EVAL_ALIAS]
print(f"{len(RELS)} relations, {len(rows)} questions (D129's cache reused)")
print(f"train on {TRAIN_ALIASES} aliases = {len(TR)} rows; "
      f"eval on held-out aliases = {len(EV)} rows", flush=True)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

Y_IDX = torch.tensor([ridx[rows[i]["rel"]] for i in TR])
Y_VEC = torch.tensor(np.stack([RC[rows[i]["rel"]] for i in TR]))
X = torch.tensor(Z[TR])
Mt = torch.tensor(M)


def train_head(objective, hidden, epochs):
    torch.manual_seed(SEED)
    hd = nn.Sequential(nn.Linear(1024, hidden), nn.GELU(),
                       nn.Linear(hidden, 1024))
    op = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(epochs):
        for b in torch.randperm(len(X)).split(512):
            op.zero_grad()
            pr = hd(X[b])
            if objective == "mse":
                loss = ((pr - Y_VEC[b]) ** 2).sum(-1).mean()
            elif objective == "cosine":
                q = pr / (pr.norm(dim=-1, keepdim=True) + 1e-9)
                loss = (1 - (q * Y_VEC[b]).sum(-1)).mean()
            else:                       # contrastive: train == eval metric
                q = pr / (pr.norm(dim=-1, keepdim=True) + 1e-9)
                logits = (q @ Mt.T) * 20.0
                loss = nn.functional.cross_entropy(logits, Y_IDX[b])
            loss.backward()
            op.step()
    hd.eval()
    with torch.no_grad():
        pe = hd(torch.tensor(Z[EV])).numpy()
    pe = pe / (np.linalg.norm(pe, axis=1, keepdims=True) + 1e-9)
    pred = (pe @ M.T).argmax(1)
    return float(np.mean([RELS[int(pred[k])] == rows[i]["rel"]
                          for k, i in enumerate(EV)]))


# 1-NN reference on the identical training slice
S = Z[EV] @ Z[TR].T
nn_pred = S.argmax(1)
NN = float(np.mean([rows[TR[int(nn_pred[k])]]["rel"] == rows[i]["rel"]
                    for k, i in enumerate(EV)]))
print(f"\n1-NN reference on the same {TRAIN_ALIASES} aliases: {NN:.3f}")
print(f"D129's quoted head: 0.614\n")

print(f"{'objective':>12} {'512':>8} {'1024':>8} {'2048':>8}   (epochs=120)")
grid = {}
for obj in ("mse", "cosine", "contrastive"):
    row = {}
    for h in (512, 1024, 2048):
        row[h] = train_head(obj, h, 120)
    grid[obj] = row
    print(f"{obj:>12} " + " ".join(f"{row[h]:8.3f}" for h in (512, 1024, 2048)),
          flush=True)

best_obj = max(grid, key=lambda o: max(grid[o].values()))
best_h = max(grid[best_obj], key=grid[best_obj].get)
print(f"\nbest cell: {best_obj} @ {best_h} hidden = "
      f"{grid[best_obj][best_h]:.3f}")
print(f"\nepoch sweep at {best_obj}/{best_h}:")
ep = {}
for e in (40, 120, 300):
    ep[e] = train_head(best_obj, best_h, e)
    print(f"  {e:4d} epochs  {ep[e]:.3f}", flush=True)

BEST = max(max(v.values()) for v in grid.values()) if grid else 0.0
BEST = max(BEST, max(ep.values()))
lo, hi = wilson_ci(int(BEST * len(EV)), len(EV))
print(f"\n=== VERDICT ===")
print(f"  1-NN                    {NN:.3f}")
print(f"  best head (any config)  {BEST:.3f}  CI95 [{lo:.3f}, {hi:.3f}]")
print(f"  D129's single head      0.614")
gap = NN - BEST
if gap <= 0.02:
    verdict = "MATCHES — D129 is WITHDRAWN"
elif BEST > 0.614 + 0.05:
    verdict = ("head improves substantially but still trails retrieval — "
               "D129's direction stands, its magnitude does not")
else:
    verdict = "head plateaus — D129 stands and is now much better supported"
print(f"  gap {gap:+.3f}  ->  {verdict}")

out = {
    "manifest": run_manifest(seed=SEED,
                             config={"TRAIN_ALIASES": TRAIN_ALIASES,
                                     "epochs_grid": 120}),
    "n_relations": len(RELS), "n_eval": len(EV),
    "one_nn": round(NN, 4), "d129_head": 0.614,
    "grid": {o: {str(h): round(v, 4) for h, v in r.items()}
             for o, r in grid.items()},
    "epoch_sweep": {str(k): round(v, 4) for k, v in ep.items()},
    "best_head": round(BEST, 4), "best_ci95": [round(lo, 4), round(hi, 4)],
    "gap_to_1nn": round(gap, 4), "verdict": verdict,
    "scope": ("D129's own population and cache, with training data held "
              "FIXED at the two aliases that entry quoted, so only the head "
              "varies. The contrastive arm exists because D129 trained a "
              "REGRESSION and scored nearest-centroid CLASSIFICATION — a "
              "train/eval mismatch that could make a capable model look "
              "incapable. 1-NN is computed on the identical training slice."),
}
(ROOT / "results" / "exp49_fair_head.json").write_text(json.dumps(out,
                                                                  indent=1))
print("\n[done] results/exp49_fair_head.json")
