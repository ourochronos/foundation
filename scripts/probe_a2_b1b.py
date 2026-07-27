"""A2 (novel-coordinate transfer) + B1b (frozen coords at proper T0) —
docs/11, D89. Protocols registered here, committed BEFORE the run (D64).

A2 — does the anchor basis TRANSFER to a novel domain?
- Anchors fit on ALL wiki gists (raw, L2-normalized — A1's frame),
  N = 256 (A1's knee). Joint anchors: same fit on wiki+arxiv.
- Project the 297 ArXiv claim gists with each basis; measure projection
  residual and retrieval parity/jaccard (100 seeded queries over the
  arxiv set, projected-query vs true-query, as in A1).
- REGISTERED ACCEPTANCE (docs/11): wiki-only vs joint gap — parity gap
  <= 2 points AND residual ratio <= 1.5x. Pass => type space transfers;
  fail => domain-conditional anchors needed (feeds B2's minting rule).

B1b — does freezing work once T0 exceeds the fit-size floor?
- B1's instrument unchanged; T0 = ALL wiki vectors (~8k > dim, vs B1's
  1,420-vector under-determined T0). Frozen whitener+anchors from T0;
  refit = wiki+arxiv. Parity for 100 seeded arxiv queries over the full
  corpus, frozen vs refit. NULL control: refit on T0 itself (~1.0).
- REGISTERED RULE (unchanged): freezing stands iff arxiv parity >= 0.95.
  Clears => fit size explained B1 and append-only growth stands on
  frozen coordinates; fails => cross-domain growth genuinely demands new
  coordinates and B2 minting is load-bearing.

Usage: .venv/bin/python scripts/probe_a2_b1b.py
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
N_A2 = 256
N_B1 = 128
EPS = 1e-3


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


def project(B, X):
    G = B @ B.T + 1e-6 * np.eye(len(B))
    W = np.linalg.solve(G, B @ X.T).T
    P = W @ B
    return P / (np.linalg.norm(P, axis=1, keepdims=True) + 1e-12)


def retrieval(Yq, Yc, q_rows):
    tops = []
    for r in q_rows:
        s = Yq[r] @ Yc.T
        t = np.argpartition(-s, 10)[:11]
        tops.append(t[np.argsort(-s[t])][:10])
    return tops


kb = KB(backend="pg", table="poc")
wiki_i, arx_i = [], []
for c in kb.claims:
    if not kb._live(c):
        continue
    p = str(c["page"])
    if p.startswith(("planted", "user:", "demo:")):
        continue
    (arx_i if p.startswith("arxiv:") else wiki_i).append(c["idx"])
W = np.stack([kb.store.vec(i) for i in wiki_i]).astype(np.float64)
A = np.stack([kb.store.vec(i) for i in arx_i]).astype(np.float64)
W /= np.linalg.norm(W, axis=1, keepdims=True) + 1e-12
A /= np.linalg.norm(A, axis=1, keepdims=True) + 1e-12
print(f"[a2b1b] wiki={len(W)} arxiv={len(A)}", flush=True)

# ---- A2 --------------------------------------------------------------------
out_a2 = {}
q = np.random.default_rng(5).choice(len(A), size=min(100, len(A)),
                                    replace=False)
true_tops = retrieval(A, A, q)
for tag, fitset in (("wiki_only", W), ("joint", np.vstack([W, A]))):
    C = kmeans(fitset, N_A2)
    B = C / (np.linalg.norm(C, axis=1, keepdims=True) + 1e-12)
    P = project(B, A)
    resid = float(1 - (P * A).sum(1).mean())
    tops = retrieval(P, A, q)
    par = float(np.mean([t[0] == tt[0] for t, tt in zip(tops, true_tops)]))
    jac = float(np.mean([len(set(t) & set(tt)) / len(set(t) | set(tt))
                         for t, tt in zip(tops, true_tops)]))
    out_a2[tag] = {"residual": resid, "parity_p1": par, "jaccard10": jac}
    print(f"[a2] {tag}: resid={resid:.4f} parity={par:.3f} jac={jac:.3f}",
          flush=True)
gap = out_a2["joint"]["parity_p1"] - out_a2["wiki_only"]["parity_p1"]
ratio = out_a2["wiki_only"]["residual"] / max(out_a2["joint"]["residual"],
                                              1e-9)
a2_pass = gap <= 0.02 and ratio <= 1.5
print(f"[a2] VERDICT: parity gap={gap:.3f} [<=0.02] resid ratio="
      f"{ratio:.2f} [<=1.5] => {'PASS' if a2_pass else 'FAIL'}", flush=True)

# ---- B1b -------------------------------------------------------------------
def whitener(X):
    mu = X.mean(0)
    Cv = np.cov((X - mu).T) + EPS * np.eye(X.shape[1])
    vals, vecs = np.linalg.eigh(Cv)
    return mu, vecs @ np.diag(vals ** -0.5) @ vecs.T


def apply_w(X, mu, Wm):
    Y = (X - mu) @ Wm
    return Y / (np.linalg.norm(Y, axis=1, keepdims=True) + 1e-12)


X = np.vstack([W, A])
arx_rows = np.arange(len(W), len(W) + len(A))
mu0, W0 = whitener(W)
Yfroz = apply_w(X, mu0, W0)
qb = np.random.default_rng(7).choice(arx_rows,
                                     size=min(100, len(arx_rows)),
                                     replace=False)


def parity_vs(Yref):
    agree, jac = 0, []
    for r in qb:
        sf, sr = Yfroz[r] @ Yfroz.T, Yref[r] @ Yref.T
        sf[r] = sr[r] = -np.inf
        tf = np.argpartition(-sf, 10)[:10]
        tr = np.argpartition(-sr, 10)[:10]
        tf = tf[np.argsort(-sf[tf])]
        tr = tr[np.argsort(-sr[tr])]
        agree += tf[0] == tr[0]
        jac.append(len(set(tf) & set(tr)) / len(set(tf) | set(tr)))
    return agree / len(qb), float(np.mean(jac))


muN, WN = whitener(W)
p_null, j_null = parity_vs(apply_w(X, muN, WN))
mur, Wr = whitener(X)
p1, j10 = parity_vs(apply_w(X, mur, Wr))
b1b_pass = p1 >= 0.95
print(f"[b1b] null={p_null:.3f} | arxiv frozen-vs-refit parity={p1:.3f} "
      f"jac={j10:.3f} [rule >=0.95] => "
      f"{'FROZEN OK' if b1b_pass else 'REINDEX'}", flush=True)

json.dump({"a2": {**out_a2, "parity_gap": gap, "resid_ratio": ratio,
                  "n_anchors": N_A2, "pass": bool(a2_pass)},
           "b1b": {"t0_size": len(W), "null_parity": p_null,
                   "arxiv_parity": p1, "arxiv_jaccard10": j10,
                   "pass_freeze": bool(b1b_pass)},
           "manifest": run_manifest(seed=0)},
          open(ROOT / "results" / "a2_b1b.json", "w"), indent=1)
print("[done] results/a2_b1b.json", flush=True)
