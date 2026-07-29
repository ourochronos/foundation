"""Is it the ANCHORS, or just the bottleneck? And is one shared space enough? (D114)

D113 showed that predicting a point in an 8-d basis fit on known relations
generalises to unseen relations (0.264 top-1) while predicting a point in
raw 1024-d does not (0.000). That result has an obvious alternative
explanation which D113 did not rule out: **maybe any low-dimensional
bottleneck regularises**, and the anchor content is irrelevant. Until that
is excluded, "the basis is the mechanism" is not earned.

So this ships the control D8 demands, in its negative form:

  RELATION anchors  — D113's basis, fit on train relation labels
  RANDOM basis      — a random orthonormal frame of the same width. Same
                      bottleneck, zero content. If this matches, the claim
                      collapses to "compression helps".
  ENTITY anchors    — fit on embeddings of ENTITY NAMES from the store,
                      having never seen a relation label. This is the
                      "turtles" question made testable: if relations are
                      just concepts, a basis built from entities should
                      carry them, and one shared space suffices.

K_R is swept rather than fixed, per A1's knee discipline — D113 picked 8
with no justification, which is exactly the kind of unswept constant that
turns into a load-bearing accident.

Usage: .venv/bin/python scripts/exp20_sharedbasis.py
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
from codec.evals.anchors import fit_anchors                      # noqa: E402
from codec.manifest import run_manifest, wilson_ci               # noqa: E402
from foundation.kb import KB                                     # noqa: E402

MIN_N, PER_REL, N_HELD, SEED = 50, 150, 8, 0
KS = [2, 4, 8, 16, 32, 64]
N_ENT = 3000

sch = {d["pid"]: d for d in
       json.loads((ROOT / "data" / "schema_v0.json").read_text())}
kb = KB(backend="pg", table="poc")
wiki = [c for c in kb.claims
        if not c["page"].startswith(("arxiv:", "hf:", "user"))]
cnt = collections.Counter(c["pid"] for c in wiki)
RELS = sorted(p for p, n in cnt.items()
              if n >= MIN_N and p in sch
              and len(sch[p].get("aliases", ())) >= 2)
rng = np.random.default_rng(SEED)
perm = list(RELS)
rng.shuffle(perm)
HELD_R, TRAIN_R = sorted(perm[:N_HELD]), sorted(perm[N_HELD:])

by_rel = collections.defaultdict(list)
for c in wiki:
    if c["pid"] in RELS:
        by_rel[c["pid"]].append(c)
facts = []
for r in RELS:
    xs = by_rel[r]
    if len(xs) > PER_REL:
        xs = [xs[i] for i in rng.choice(len(xs), PER_REL, replace=False)]
    facts.extend(xs)
FRAMES = ["What is the {a} of {s}?", "For {s}, what is the {a}?"]
queries = []
for f in facts:
    for a in sch[f["pid"]]["aliases"]:
        for fr in FRAMES:
            queries.append({"pid": f["pid"], "subject": f["subject"],
                            "object": f["object"],
                            "text": fr.format(a=a, s=f["subject"])})
print(f"{len(RELS)} relations ({len(HELD_R)} held out), {len(queries)} "
      f"questions", flush=True)

# Reuse D113's cache — identical construction, so identical embeddings.
z = np.load(ROOT / "results" / "exp19_emb.npz", allow_pickle=True)
Zq, Zl, lab_order = z["Zq"], z["Zl"], list(z["lab_order"])
assert len(Zq) == len(queries), "query construction drifted from D113"
V = {p: Zl[i] for i, p in enumerate(lab_order)}

# Entity-name embeddings: the "one shared space" candidate basis. These are
# entity names only — no relation label is ever seen by this basis.
ecache = ROOT / "results" / "exp20_entity_emb.npz"
if ecache.exists():
    Ze = np.load(ecache)["Ze"]
else:
    names = sorted({c["subject"] for c in wiki} | {c["object"] for c in wiki})
    names = [names[i] for i in
             np.random.default_rng(SEED).choice(len(names),
                                                min(N_ENT, len(names)),
                                                replace=False)]
    Ze = P.unit(P.embed_texts(names))
    np.savez(ecache, Ze=Ze)
print(f"entity-name basis pool {Ze.shape}", flush=True)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

tr_i = [i for i, q in enumerate(queries) if q["pid"] in TRAIN_R]
he_i = [i for i, q in enumerate(queries) if q["pid"] in HELD_R]
gold = collections.defaultdict(set)
for c in wiki:
    gold[(c["subject"], c["pid"])].add(c["object"])
Xtr = torch.tensor(Zq[tr_i])
Xhe = torch.tensor(Zq[he_i])


def feasible(kind, k):
    # A k-means basis needs at least k points. The relation-anchor basis is
    # therefore CAPPED BY THE NUMBER OF KNOWN RELATIONS (18 here) — a real
    # limitation, and a direct argument for the shared entity space, whose
    # pool is thousands of names rather than a couple of dozen labels.
    return not (kind == "relation anchors" and k > len(TRAIN_R))


def basis(kind, k):
    if kind == "relation anchors":
        return P.unit(fit_anchors(np.stack([V[r] for r in TRAIN_R]), k,
                                  seed=SEED))
    if kind == "entity anchors":
        return P.unit(fit_anchors(Ze, k, seed=SEED))
    if kind == "mixed pool":
        # Entity names + TRAIN relation labels. If entity-only anchors fail
        # merely because the name manifold does not COVER the region where
        # relation labels live, then widening the pool should recover the
        # relation-anchor result — and unlike a relation-only basis it is
        # not capped at |TRAIN_R|. Held-out relations are still never seen.
        return P.unit(fit_anchors(
            np.concatenate([Ze, np.stack([V[r] for r in TRAIN_R])]), k,
            seed=SEED))
    g = np.random.default_rng(1000 + k).normal(size=(k, 1024))
    return P.unit(np.linalg.qr(g.T)[0].T.astype(np.float32))


def run(kind, k):
    PC = basis(kind, k)
    C = {p: P.unit(V[p] @ PC.T) for p in RELS}
    torch.manual_seed(SEED)
    Y = torch.tensor(np.stack([C[queries[i]["pid"]] for i in tr_i]))
    hd = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, k))
    opt = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(Xtr)).split(512):
            opt.zero_grad()
            pr = hd(Xtr[b])
            pr = pr / (pr.norm(dim=-1, keepdim=True) + 1e-9)
            (1 - (pr * Y[b]).sum(-1)).mean().backward()
            opt.step()
    hd.eval()
    M = np.stack([C[r] for r in RELS])
    with torch.no_grad():
        ph = hd(Xhe).numpy()
        pt = hd(Xtr).numpy()
    ph = ph / (np.linalg.norm(ph, axis=1, keepdims=True) + 1e-9)
    pt = pt / (np.linalg.norm(pt, axis=1, keepdims=True) + 1e-9)
    Sh, St = ph @ M.T, pt @ M.T
    ri = {r: i for i, r in enumerate(RELS)}
    h1 = np.mean([int(np.argmax(Sh[j]) == ri[queries[i]["pid"]])
                  for j, i in enumerate(he_i)])
    t1 = np.mean([int(np.argmax(St[j]) == ri[queries[i]["pid"]])
                  for j, i in enumerate(tr_i)])
    tal = collections.Counter()
    for j, i in enumerate(he_i):
        q = queries[i]
        got = gold.get((q["subject"], RELS[int(np.argmax(Sh[j]))]), set())
        tal["abstain" if not got else
            ("correct" if q["object"] in got else "wrong")] += 1
    a = tal["correct"] + tal["wrong"]
    return (float(h1), float(t1), tal["correct"] / sum(tal.values()),
            tal["correct"] / a if a else 0.0)


KINDS = ["relation anchors", "random orthonormal", "entity anchors",
         "mixed pool"]
print(f"\nHELD-OUT-RELATION top-1  (chance {1/len(RELS):.3f}, "
      f"n={len(he_i)} over {len(HELD_R)} unseen relations)")
print(f"{'K_R':>5}" + "".join(f"{k:>20s}" for k in KINDS))
grid = {}
for k in KS:
    row = {}
    for kind in KINDS:
        if feasible(kind, k):
            row[kind] = run(kind, k)
    grid[k] = row
    print(f"{k:5d}" + "".join(
        f"{row[kind][0]:20.3f}" if kind in row else f"{'—':>20s}"
        for kind in KINDS), flush=True)

print(f"\ntrain-relation top-1 (control — all should be high)")
print(f"{'K_R':>5}" + "".join(f"{k:>20s}" for k in KINDS))
for k in KS:
    print(f"{k:5d}" + "".join(
        f"{grid[k][kind][1]:20.3f}" if kind in grid[k] else f"{'—':>20s}"
        for kind in KINDS))

print(f"\nend-to-end precision-when-answered on the live store, HELD-OUT")
print(f"{'K_R':>5}" + "".join(f"{k:>20s}" for k in KINDS))
for k in KS:
    print(f"{k:5d}" + "".join(
        f"{grid[k][kind][3]:20.3f}" if kind in grid[k] else f"{'—':>20s}"
        for kind in KINDS))

best = {kind: max([k for k in KS if kind in grid[k]],
                  key=lambda k: grid[k][kind][0]) for kind in KINDS}
print("\nbest K_R per basis: " + ", ".join(
    f"{kind} K={best[kind]} ({grid[best[kind]][kind][0]:.3f})"
    for kind in KINDS))
lo, hi = wilson_ci(int(grid[best["relation anchors"]]["relation anchors"][0]
                       * len(he_i)), len(he_i))
lor, hir = wilson_ci(int(grid[best["random orthonormal"]]
                         ["random orthonormal"][0] * len(he_i)), len(he_i))
print(f"relation-anchor best CI95 [{lo:.3f}, {hi:.3f}] vs "
      f"random best CI95 [{lor:.3f}, {hir:.3f}] — "
      f"{'DISJOINT: content matters' if lo > hir else 'OVERLAP: bottleneck alone may explain D113'}")

out = {
    "manifest": run_manifest(seed=SEED, config={"KS": KS, "N_ENT": N_ENT,
                                                "held_out": HELD_R}),
    "chance_top1": round(1 / len(RELS), 4), "n_held_out_q": len(he_i),
    "grid": {str(k): {kind: {"held_out_top1": round(v[0], 4),
                             "train_top1": round(v[1], 4),
                             "end_to_end_correct": round(v[2], 4),
                             "end_to_end_precision": round(v[3], 4)}
                      for kind, v in row.items()} for k, row in grid.items()},
    "relation_basis_capped_at": len(TRAIN_R),
    "best_K": best,
    "scope": ("Negative control for D113: a random orthonormal basis of the "
              "same width isolates 'the anchor content matters' from "
              "'any bottleneck regularises'. Entity anchors test whether "
              "one shared concept space carries relations. Single-hop; "
              "same 8 held-out relations as D113, unstratified."),
}
(ROOT / "results" / "exp20_sharedbasis.json").write_text(json.dumps(out,
                                                                    indent=1))
print("\n[done] results/exp20_sharedbasis.json")
