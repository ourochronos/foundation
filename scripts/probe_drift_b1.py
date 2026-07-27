"""B1 — frozen-coordinates drift across corpus growth (docs/11, D88).

PROTOCOL (pre-registered; committed before the scoring run — D64):
- T0 = wiki v3 layer (sid prefix out_v3). Fit FROZEN artifacts on T0:
  ZCA whitener (mean + (Sigma+eps I)^-1/2) and N=128 k-means anchors
  (N fixed here to decouple from A1's knee search).
- Batches, in arrival order: T0 (v3), T1 (G2 deep layer, out_g2), T2
  (1k tranche, out_1k), T3 (ArXiv claims).
- Per batch, in FROZEN coordinates: (a) retrieval-parity frozen-vs-refit —
  whiten the full corpus BOTH ways (frozen T0 whitener vs whitener refit
  on everything-so-far), run 100 seeded queries per batch over the full
  corpus in each system, report top-1 agreement + top-10 Jaccard;
  (b) isotropy proxies of the batch in frozen coordinates (mean pairwise
  cosine, effective rank of the batch covariance); (c) frozen-anchor
  projection residual.
- NULL CONTROL (D8): frozen-vs-"refit on T0 itself" — whitened-cosine
  retrieval is rotation-invariant, so parity must be ~1.0; the comparison
  machinery must not manufacture drift.
- REGISTERED DECISION RULE: reindex is warranted for a batch only when
  its frozen-vs-refit top-1 parity < 0.95; above that, frozen coordinates
  stand (append-only growth).

Usage: .venv/bin/python scripts/probe_drift_b1.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from codec.manifest import run_manifest  # noqa: E402
from foundation.kb import KB             # noqa: E402

rng = np.random.default_rng(0)
EPS = 1e-3
N_ANCH = 128


def whitener(X):
    mu = X.mean(0)
    C = np.cov((X - mu).T) + EPS * np.eye(X.shape[1])
    vals, vecs = np.linalg.eigh(C)
    W = vecs @ np.diag(vals ** -0.5) @ vecs.T
    return mu, W


def apply_w(X, mu, W):
    Y = (X - mu) @ W
    return Y / (np.linalg.norm(Y, axis=1, keepdims=True) + 1e-12)


def kmeans(X, k, iters=20):
    C = X[rng.choice(len(X), size=k, replace=False)].copy()
    for _ in range(iters):
        a = np.empty(len(X), np.int64)
        for i in range(0, len(X), 4096):
            b = X[i:i + 4096]
            a[i:i + 4096] = ((b ** 2).sum(1, keepdims=True)
                             - 2 * b @ C.T + (C ** 2).sum(1)).argmin(1)
        for j in range(k):
            m = a == j
            if m.any():
                C[j] = X[m].mean(0)
    return C


kb = KB(backend="pg", table="poc")
batches: dict[str, list[int]] = {"T0_v3": [], "T1_g2": [], "T2_1k": [],
                                 "T3_arxiv": []}
for c in kb.claims:
    if not kb._live(c):
        continue
    sid, page = str(c["sid"]), str(c["page"])
    if page.startswith("planted") or page.startswith("user:") \
            or page.startswith("demo:"):
        continue
    if page.startswith("arxiv:"):
        batches["T3_arxiv"].append(c["idx"])
    elif sid.startswith("out_v3"):
        batches["T0_v3"].append(c["idx"])
    elif sid.startswith("out_g2"):
        batches["T1_g2"].append(c["idx"])
    elif sid.startswith("out_1k"):
        batches["T2_1k"].append(c["idx"])
vec = {i: kb.store.vec(i) for b in batches.values() for i in b}
order = [i for k in ("T0_v3", "T1_g2", "T2_1k", "T3_arxiv")
         for i in batches[k]]
X = np.stack([vec[i] for i in order]).astype(np.float64)
pos = {i: r for r, i in enumerate(order)}
print(f"[b1] batches: " + ", ".join(f"{k}={len(v)}"
      for k, v in batches.items()), flush=True)

T0 = np.stack([vec[i] for i in batches["T0_v3"]]).astype(np.float64)
mu0, W0 = whitener(T0)
A0 = kmeans(apply_w(T0, mu0, W0), N_ANCH)
B0 = A0 / (np.linalg.norm(A0, axis=1, keepdims=True) + 1e-12)
G0 = B0 @ B0.T + 1e-6 * np.eye(N_ANCH)

Yfroz = apply_w(X, mu0, W0)


def parity(batch_idx, Yref, tag):
    q = np.random.default_rng(7).choice(batch_idx,
                                        size=min(100, len(batch_idx)),
                                        replace=False)
    rows_f = np.array([pos[i] for i in q])
    agree, jac = 0, []
    for r in rows_f:
        sf = Yfroz[r] @ Yfroz.T
        sr = Yref[r] @ Yref.T
        sf[r] = sr[r] = -np.inf
        tf = np.argpartition(-sf, 10)[:10]
        tr_ = np.argpartition(-sr, 10)[:10]
        tf = tf[np.argsort(-sf[tf])]
        tr_ = tr_[np.argsort(-sr[tr_])]
        agree += tf[0] == tr_[0]
        jac.append(len(set(tf) & set(tr_)) / len(set(tf) | set(tr_)))
    return agree / len(q), float(np.mean(jac))


out = {"batches": {k: len(v) for k, v in batches.items()},
       "n_anchors": N_ANCH, "rows": []}

# null control: refit on T0 itself
muN, WN = whitener(T0)
Ynull = apply_w(X, muN, WN)
p1, j10 = parity(batches["T0_v3"], Ynull, "null")
out["null_control"] = {"parity_p1": p1, "jaccard10": j10}
print(f"[b1] NULL control parity={p1:.3f} jac={j10:.3f} "
      f"[must be ~1.0]", flush=True)

seen: list[int] = []
for k in ("T0_v3", "T1_g2", "T2_1k", "T3_arxiv"):
    seen += batches[k]
    if not batches[k]:
        out["rows"].append({"batch": k, "skipped": "empty"})
        continue
    Xs = np.stack([vec[i] for i in seen]).astype(np.float64)
    mur, Wr = whitener(Xs)
    Yref = apply_w(X, mur, Wr)
    p1, j10 = parity(batches[k], Yref, k)
    Yb = Yfroz[[pos[i] for i in batches[k]]]
    n = min(len(Yb), 1500)
    sub = Yb[np.random.default_rng(3).choice(len(Yb), n, replace=False)]
    mpc = float((sub @ sub.T)[np.triu_indices(n, 1)].mean())
    ev = np.linalg.eigvalsh(np.cov(sub.T))
    ev = np.clip(ev, 1e-12, None)
    p = ev / ev.sum()
    eff = float(np.exp(-(p * np.log(p)).sum()))
    Wc = np.linalg.solve(G0, B0 @ Yb.T).T
    P = Wc @ B0
    Pn = P / (np.linalg.norm(P, axis=1, keepdims=True) + 1e-12)
    resid = float(1 - (Pn * Yb).sum(1).mean())
    row = {"batch": k, "parity_p1": p1, "jaccard10": j10,
           "mean_pairwise_cos_frozen": mpc, "eff_rank_frozen": eff,
           "anchor_resid_frozen": resid,
           "reindex_warranted": p1 < 0.95}
    out["rows"].append(row)
    print(f"[b1] {k}: parity={p1:.3f} jac={j10:.3f} mpc={mpc:.3f} "
          f"effrank={eff:.0f} resid={resid:.4f} "
          f"{'REINDEX' if p1 < 0.95 else 'frozen OK'}", flush=True)

out["decision_rule"] = "reindex batch iff frozen-vs-refit top-1 parity < 0.95"
out["manifest"] = run_manifest(seed=0)
json.dump(out, open(ROOT / "results" / "drift_b1.json", "w"), indent=1)
print("[done] results/drift_b1.json", flush=True)
