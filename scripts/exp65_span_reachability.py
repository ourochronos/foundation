"""Is a novel relation's coordinate REACHABLE from the trained ones? (D174's conjecture)

D174 proposed, post-hoc, that sparse codes "separate maximally and interpolate
not at all": the head learns to emit coordinates in the span of its training
targets, so a novel relation is identifiable only if its coordinate lies in
that span. A dense low-K basis puts every relation inside a small space the
head has covered; a sparse overcomplete code gives each relation its own atoms,
outside anything the head has learned to produce.

That explanation fit every number in D174 and was **untested**, which after
D159, D165 and D172 is a distinction worth keeping. This tests it, and it needs
no training whatsoever — only linear algebra on coordinate matrices.

**The measurement.** For a basis, take the 44 trained relations' coordinates as
a matrix `T` and each of the 12 held-out coordinates `c` (unit norm). Project
`c` onto `span(T)`:

    span_reach(c) = || proj_{span(T)} c ||       (in [0, 1] for unit c)

1.0 means the novel coordinate is fully expressible as a combination of trained
ones — reachable in principle. Near 0 means it is orthogonal to everything the
head was ever asked to emit — unreachable no matter how well the head is
trained.

**What the conjecture predicts, registered before running.** `span_reach`
should correlate strongly and positively with the already-measured novel
transfer across bases. It should also be **necessary but not sufficient**: at
K=32 with 44 trained relations the trained coordinates generically span all of
R^32, so `span_reach` is 1.0 for *every* K=32 basis — yet `lda_between` scores
0.2767 and `kmeans_label` 0.1111 on the same span. So among high-span bases the
residual must be explained by D168's partition alignment, and the two accounts
compose rather than compete.

**Refinement registered after the first run, before the second.** `span_reach`
came back degenerate — pinned to exactly 1.0 in 35 of 45 cells by counting
rather than geometry — so it cannot carry the conjecture either way. The
non-degenerate form of the same idea is `convex_reach`: the cosine of the best
NON-NEGATIVE combination of trained coordinates, which is what "interpolate"
actually means. Prediction, written before running it: sparse codes score near
zero (private atoms cannot be built additively from other private atoms) while
dense low-K bases score high, and `convex_reach` correlates with novel transfer
more strongly than `span_reach` did. **This is a second measure on the same
data**, so a correlation here is worth materially less than a pre-registered
one and is labelled as such wherever it is reported.

**What would refute it.** If sparse and raw bases show high `span_reach` while
still scoring at chance, reachability is not the constraint and D174's
explanation should be withdrawn rather than kept as a story that happens to
fit.

Novel-transfer numbers are read from the stored exp56/exp57/exp64 artifacts —
nothing is re-measured here, so this cannot accidentally re-derive the thing it
is trying to explain.

Usage: .venv/bin/python scripts/exp65_span_reachability.py [m3|gemma|both]
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import nnls

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from codec.evals.anchors import fit_anchors                      # noqa: E402
from codec.manifest import run_manifest                          # noqa: E402
from foundation.kb import KB                                     # noqa: E402

SEED, MIN_ALIAS, N_SUBJ, N_HOLD_REL, K_ENTITY = 0, 6, 40, 12, 32
TRAIN_ALIASES = 2
WHICH = sys.argv[1] if len(sys.argv) > 1 else "both"

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
TRIP = sorted({(c["subject"], c["pid"], c["object"]) for c in wiki
               if c["pid"] in LABEL})
by_rel = collections.defaultdict(list)
for s, p, o in TRIP:
    by_rel[p].append(s)
rng = np.random.default_rng(SEED)
SUBJ = {}
for r in RELS:
    s = sorted(set(by_rel[r]))
    SUBJ[r] = ([s[i] for i in sorted(rng.choice(len(s), N_SUBJ, replace=False))]
               if len(s) > N_SUBJ else s)
HELD_R = {RELS[i] for i in sorted(rng.permutation(len(RELS))[:N_HOLD_REL])}
TRAINED_R = [r for r in RELS if r not in HELD_R]
HELD_L = [r for r in RELS if r in HELD_R]
rows = [{"rel": r, "ai": ai, "alias": a, "subj": s}
        for r in RELS for ai, a in enumerate(ALIAS[r]) for s in SUBJ[r]]
QTEXT = [f"What is the {x['alias']} of {x['subj']}?" for x in rows]
ENTS = sorted({t[0] for t in TRIP} | {t[2] for t in TRIP})
print(f"{len(RELS)} relations: {len(TRAINED_R)} trained, {len(HELD_L)} held "
      f"out", flush=True)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402


def unit(a):
    return a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9)


def span_reach(C):
    """Mean ||proj_span(trained) c|| over held-out unit coordinates.

    DEGENERATE BY CONSTRUCTION below K=44 and reported anyway because it was
    the registered measure: with 44 trained relations their coordinates
    generically span all of R^K whenever K <= 44, so this is pinned to exactly
    1.0 by counting rather than by geometry. Only the K > 44 cells carry
    information, and there the statistic is confounded with everything else
    that changes at large K. See `convex_reach` for the non-degenerate form.
    """
    T = unit(np.stack([C[r] for r in TRAINED_R]))
    H = unit(np.stack([C[r] for r in HELD_L]))
    # orthonormal basis for the row space of T
    U, s, Vt = np.linalg.svd(T, full_matrices=False)
    rank = int((s > 1e-8 * max(s[0], 1e-12)).sum())
    Q = Vt[:rank].T                                   # [K, rank]
    proj = H @ Q @ Q.T
    return (float(np.mean(np.linalg.norm(proj, axis=1))),
            rank, int(T.shape[1]))


def _convex(T, c):
    """cos(c, best NON-NEGATIVE combination of rows of T). Literal interpolation."""
    a, _ = nnls(T.T, c)
    f = T.T @ a
    n = np.linalg.norm(f)
    return 0.0 if n < 1e-9 else float(f @ c / (n * np.linalg.norm(c)))


def convex_reach(C):
    """Can a novel coordinate be INTERPOLATED from the trained ones?

    Non-degenerate at every K: being inside the span says a combination exists,
    but interpolation means a combination with bounded, non-negative weights.
    A sparse code on private atoms is in the span of anything of full rank and
    still cannot be built additively from its peers.

    Control (`loo`): the same quantity for TRAINED relations, leave-one-out. If
    trained coordinates are equally hard to reconstruct from their peers, the
    measure is not capturing anything specific to novelty and the gap, not the
    level, is the signal.
    """
    T = unit(np.stack([C[r] for r in TRAINED_R]))
    held = float(np.mean([_convex(T, unit(C[r])) for r in HELD_L]))
    loo = float(np.mean([_convex(np.delete(T, i, 0), T[i])
                         for i in range(len(TRAINED_R))]))
    # conditioning: L1 mass of the exact least-squares coefficients
    l1 = float(np.mean([np.abs(np.linalg.lstsq(T.T, unit(C[r]), rcond=None)[0]).sum()
                        for r in HELD_L]))
    return held, loo, l1


def pair_cos(C):
    """Mean pairwise cosine between ALL relation coordinates."""
    M = unit(np.stack([C[r] for r in RELS]))
    G = M @ M.T
    n = len(M)
    return float((G.sum() - np.trace(G)) / (n * (n - 1)))


class SAE(nn.Module):
    def __init__(self, d, k):
        super().__init__()
        self.b_d = nn.Parameter(torch.zeros(d))
        self.W_e = nn.Linear(d, k)
        self.W_d = nn.Linear(k, d, bias=False)
        with torch.no_grad():
            self.W_d.weight.copy_(self.W_e.weight.T.contiguous())
            self._renorm()

    def _renorm(self):
        with torch.no_grad():
            w = self.W_d.weight
            w /= (w.norm(dim=0, keepdim=True) + 1e-8)

    def encode(self, x):
        return torch.relu(self.W_e(x - self.b_d))

    def forward(self, x):
        h = self.encode(x)
        return self.W_d(h) + self.b_d, h


def train_sae(X, k, l1, epochs=150):
    torch.manual_seed(SEED)
    m = SAE(X.shape[1], k)
    op = torch.optim.AdamW(m.parameters(), lr=1e-3)
    Xt = torch.tensor(X)
    for _ in range(epochs):
        for b in torch.randperm(len(Xt)).split(512):
            op.zero_grad()
            xb = Xt[b]
            xh, h = m(xb)
            (((xh - xb) ** 2).sum(-1).mean()
             + l1 * h.abs().sum(-1).mean()).backward()
            op.step()
            m._renorm()
    m.eval()
    return m


ARMS = (["m3"] if WHICH in ("m3", "both") else []) + \
       (["gemma_symmetric"] if WHICH in ("gemma", "both") else [])
OUT, ALL = {}, []
for arm in ARMS:
    z = np.load(ROOT / "results" / f"exp56_{arm}_emb.npz", allow_pickle=True)
    assert list(z["qtext"]) == QTEXT and list(z["ents"]) == ENTS, \
        f"population drift vs exp56 for {arm}"
    Zq, Zl, Zent = z["Zq"], z["Zl"], z["Zent"]
    d = Zq.shape[1]
    RAW = {r: Zl[i] for i, r in enumerate(RELS)}
    L_tr = np.stack([RAW[r] for r in TRAINED_R])
    ei = {e: i for i, e in enumerate(ENTS)}
    subs, objs = collections.defaultdict(list), collections.defaultdict(list)
    for s, p, o in TRIP:
        if p in TRAINED_R:
            subs[p].append(ei[s])
            objs[p].append(ei[o])
    dom_g = [Zent[subs[r]] for r in TRAINED_R if subs[r]]
    rng_g = [Zent[objs[r]] for r in TRAINED_R if objs[r]]
    OFF = unit(np.stack([Zent[ei[o]] - Zent[ei[s]] for s, p, o in TRIP
                         if p in TRAINED_R]))
    qg = [Zq[[i for i, x in enumerate(rows)
              if x["rel"] == r and x["ai"] < TRAIN_ALIASES]]
          for r in TRAINED_R]

    def between(groups, K):
        mus = [g.mean(0) for g in groups if len(g)]
        ns = [len(g) for g in groups if len(g)]
        if len(mus) < 2 or K > len(mus) - 1:
            return None
        M = np.stack(mus)
        mu = np.average(M, axis=0, weights=ns)
        D = (M - mu) * np.sqrt(np.array(ns))[:, None]
        return unit(np.linalg.svd(D, full_matrices=False)[2][:K])

    def basis(st, K):
        if st == "kmeans_label":
            return unit(fit_anchors(L_tr, K, seed=SEED)) if K <= len(L_tr) else None
        if st == "pca_label":
            if K > len(L_tr) - 1:
                return None
            return unit(np.linalg.svd(L_tr - L_tr.mean(0),
                                      full_matrices=False)[2][:K])
        if st == "lda_between":
            return between(qg, K)
        if st == "lda_range":
            return between(rng_g, K)
        if st == "kmeans_offset":
            return unit(fit_anchors(OFF, K, seed=SEED))
        if st == "entity_complement":
            if K > len(L_tr):
                return None
            E = fit_anchors(Zent, K_ENTITY, seed=SEED)
            Q = np.linalg.qr(E.T)[0]
            Lp = L_tr - (L_tr @ Q) @ Q.T
            keep = np.linalg.norm(Lp, axis=1) > 1e-6
            return unit(fit_anchors(unit(Lp[keep]), K, seed=SEED)) \
                if keep.sum() >= K else None
        if st == "random_orthonormal":
            g = np.random.default_rng(SEED).standard_normal((d, K))
            return unit(np.linalg.qr(g)[0].T.astype(np.float32)) if K <= d else None
        return None

    # measured novel transfer, read from the stored artifacts
    measured = {}
    for fn in ("exp56_anchor_strategy.json", "exp57_layer_derivation.json"):
        p = ROOT / "results" / fn
        if not p.exists():
            continue
        j = json.loads(p.read_text())["arms"].get(arm, {})
        cells = j.get("cells", j)
        for k, v in cells.items():
            if isinstance(v, dict) and "novel" in v:
                measured[(v["strategy"], v["K"])] = v["novel"]
    e64 = json.loads((ROOT / "results"
                      / "exp64_sparse_dictionary.json").read_text())["arms"][arm]

    print(f"\n=== {arm} (d={d}) ===")
    print(f"  {'basis':>26} {'K':>5} {'rank':>5} {'span':>7} {'convex':>7} "
          f"{'cvxLOO':>7} {'coefL1':>8} {'pair_cos':>9} {'NOVEL':>8}")
    pts = []

    def record(name, C, K, novel):
        sr, rank, dim = span_reach(C)
        cv, loo, l1 = convex_reach(C)
        pc = pair_cos(C)
        pts.append({"basis": name, "K": K, "rank": rank,
                    "span_reach": round(sr, 4), "convex_reach": round(cv, 4),
                    "convex_loo_trained": round(loo, 4),
                    "coef_l1": round(l1, 3), "pair_cos": round(pc, 4),
                    "novel": novel})
        print(f"  {name:>26} {K:5d} {rank:5d} {sr:7.4f} {cv:7.4f} {loo:7.4f} "
              f"{l1:8.2f} {pc:9.4f} {novel:8.4f}", flush=True)

    record("raw_label_space", RAW, d, e64["raw_label_space"]["novel"])
    g = np.random.default_rng(SEED).standard_normal((2048, d)).astype(np.float32)
    PCr = unit(g)
    record("dense_random_2048",
           {r: unit(RAW[r] @ PCr.T) for r in RELS}, 2048,
           e64["dense_random_2048"]["novel"])
    for st in ("kmeans_label", "pca_label", "lda_between", "lda_range",
               "kmeans_offset", "entity_complement", "random_orthonormal"):
        for K in (4, 8, 16, 32, 43, 64, 128, 256):
            if (st, K) not in measured:
                continue
            PC = basis(st, K)
            if PC is None:
                continue
            record(f"{st}_K{K}", {r: unit(RAW[r] @ PC.T) for r in RELS},
                   PC.shape[0], measured[(st, K)])
    POOL = unit(np.concatenate([Zq, Zent, Zl], 0)).astype(np.float32)
    for key, (ex, l1) in (("sae_x2_l10.001", (2, 1e-3)),
                          ("sae_x2_l10.01", (2, 1e-2))):
        if key not in e64:
            continue
        m = train_sae(POOL, ex * d, l1)
        with torch.no_grad():
            H = m.encode(torch.tensor(np.stack([RAW[r] for r in RELS]))).numpy()
        if H.sum() == 0:
            continue
        record(key, {r: unit(H[i]) for i, r in enumerate(RELS)},
               ex * d, e64[key]["novel"])
    OUT[arm] = pts
    ALL += [dict(p, arm=arm) for p in pts]

print("\n=== does span-reachability predict novel transfer? ===")
corrs = {}
for arm, pts in OUT.items():
    nv = np.array([p["novel"] for p in pts])
    c = {"n_cells": len(pts)}
    for key in ("span_reach", "convex_reach", "convex_loo_trained",
                "coef_l1", "pair_cos"):
        v = np.array([p[key] for p in pts])
        c[f"{key}_vs_novel"] = (round(float(np.corrcoef(v, nv)[0, 1]), 4)
                                if v.std() > 1e-9 else None)
    corrs[arm] = c
    print(f"  {arm:>18}  " + "  ".join(
        f"{k}={c[k + '_vs_novel']:+.3f}" if c[k + '_vs_novel'] is not None
        else f"{k}=const" for k in ("span_reach", "convex_reach", "coef_l1",
                                    "pair_cos")) + f"   ({len(pts)} cells)")

print("\n=== within-strategy: does the measure track novel INSIDE a family? ===")
within = {}
for arm, pts in OUT.items():
    fam = collections.defaultdict(list)
    for p in pts:
        fam[p["basis"].rsplit("_K", 1)[0]].append(p)
    rs = {}
    for f, ps in sorted(fam.items()):
        if len(ps) < 4:
            continue
        nvf = np.array([p["novel"] for p in ps])
        row = {}
        for key in ("span_reach", "convex_reach"):
            v = np.array([p[key] for p in ps])
            row[key] = (round(float(np.corrcoef(v, nvf)[0, 1]), 3)
                        if v.std() > 1e-9 else None)
        rs[f] = row
        print(f"  {arm:>16} {f:>20}  span="
              f"{'const' if row['span_reach'] is None else format(row['span_reach'], '+.3f')}"
              f"  convex="
              f"{'const' if row['convex_reach'] is None else format(row['convex_reach'], '+.3f')}"
              f"   ({len(ps)} K values)")
    within[arm] = rs

print("\n=== necessary but not sufficient? ===")
suff = {}
for arm, pts in OUT.items():
    hi = [p for p in pts if p["span_reach"] > 0.99]
    lo = [p for p in pts if p["span_reach"] < 0.90]
    hn = [p["novel"] for p in hi]
    ln = [p["novel"] for p in lo]
    suff[arm] = {"n_high_span": len(hi), "n_low_span": len(lo),
                 "high_span_novel_range": [round(min(hn), 4), round(max(hn), 4)]
                 if hn else None,
                 "low_span_novel_max": round(max(ln), 4) if ln else None}
    print(f"  {arm}: span>0.99 -> novel {suff[arm]['high_span_novel_range']} "
          f"({len(hi)} cells);  span<0.90 -> novel max "
          f"{suff[arm]['low_span_novel_max']} ({len(lo)} cells)")

mr = float(np.mean([c["span_reach_vs_novel"] for c in corrs.values()]))
mc = float(np.mean([c["convex_reach_vs_novel"] for c in corrs.values()]))
lows = [v["low_span_novel_max"] for v in suff.values()
        if v["low_span_novel_max"] is not None]
ceiling = max(lows) if lows else None
degenerate = all(p["span_reach"] == 1.0
                 for pts in OUT.values() for p in pts if p["K"] <= len(TRAINED_R))
if degenerate:
    n_pin = sum(1 for pts in OUT.values() for p in pts if p["span_reach"] == 1.0)
    n_all = sum(len(p) for p in OUT.values())
    print(f"\n  NOTE: span_reach is pinned to exactly 1.0 in {n_pin}/{n_all} "
          f"cells — forced by counting (44 trained coordinates span all of R^K "
          f"for K <= 44), not measured. Its correlation is uninterpretable.")
if mr > 0.5 and ceiling is not None and ceiling < 0.20:
    verdict = (f"SUPPORTED — span-reachability predicts novel transfer "
               f"(r={mr:+.3f}), and no basis with span_reach < 0.90 exceeds "
               f"{ceiling:.4f} novel. Reachability is NECESSARY. It is not "
               f"sufficient: high-span bases spread widely, and D168's "
               f"partition alignment explains that residual. The two accounts "
               f"compose.")
elif ceiling is not None and ceiling > 0.20:
    verdict = (f"REFUTED — a basis with span_reach < 0.90 reaches "
               f"{ceiling:.4f} novel, so a novel coordinate outside the "
               f"trained span is evidently still reachable. D174's "
               f"interpolation explanation should be withdrawn.")
elif mc > 0.5:
    verdict = (f"PARTIAL — the registered measure (span_reach) is degenerate "
               f"and settles nothing at r={mr:+.3f}, but its non-degenerate "
               f"form, convex_reach, correlates at r={mc:+.3f}. That is a "
               f"SECOND measure on the same data and is worth less than a "
               f"pre-registered one; D174's conjecture is supported enough to "
               f"keep testing and not enough to assert.")
else:
    verdict = (f"UNSUPPORTED — span_reach r={mr:+.3f} on a degenerate measure, "
               f"and its non-degenerate form convex_reach only reaches "
               f"r={mc:+.3f}. Reachability/interpolability does not explain "
               f"novel transfer, so D174's post-hoc explanation should be "
               f"withdrawn rather than kept as a story that fits.")
print(f"\n=== VERDICT ===\n  {verdict}")

out = {"manifest": run_manifest(seed=SEED, config={"N_HOLD_REL": N_HOLD_REL}),
       "n_relations": len(RELS), "n_trained": len(TRAINED_R),
       "chance": round(1 / len(RELS), 4),
       "cells": OUT, "correlations": corrs, "sufficiency": suff,
       "within_strategy": within,
       "span_reach_degenerate": degenerate,
       "verdict": verdict,
       "registered_prediction": (
           "span_reach correlates strongly and positively with novel "
           "transfer, and is NECESSARY BUT NOT SUFFICIENT — at K=32 with 44 "
           "trained relations the trained coordinates span all of R^32 so "
           "span_reach is 1.0 for every K=32 basis, yet lda_between scores "
           "0.2767 and kmeans_label 0.1111; the residual is D168's partition "
           "alignment, so the two accounts compose rather than compete"),
       "scope": ("Tests D174's post-hoc interpolation conjecture without "
                 "training anything: for each basis, project each held-out "
                 "relation's unit coordinate onto the span of the 44 trained "
                 "coordinates and take the norm. Novel-transfer numbers are "
                 "READ from stored exp56/exp57/exp64 artifacts and never "
                 "re-measured here, so the test cannot re-derive the quantity "
                 "it is explaining. Refuted if a low-span basis still "
                 "transfers, which would mean reachability is not the "
                 "constraint.")}
(ROOT / "results" / "exp65_span_reachability.json").write_text(
    json.dumps(out, indent=1))
print("\n[done] results/exp65_span_reachability.json")
