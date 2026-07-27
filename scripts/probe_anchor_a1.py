"""A1 — anchor-basis expressivity knee on the REAL corpus (docs/11, D88).

PROTOCOL (pre-registered; committed before the scoring run — D64):
- Vectors: gist embeddings of all live wiki-layer claims pulled from the
  poc PG table (source of record; ArXiv rows excluded here — they are
  A2/B1 material).
- Anchors: k-means (k = N, seed 0, 20 iters) on a train HALF (even idx);
  eval on the odd half — residual/parity numbers are out-of-sample.
- For N in {8,16,32,64,128,256,512,1024}: project eval gists onto the
  anchor span (least-squares onto the k centroid basis), measure
  (i) mean projection residual (1 - cos(z, z_proj)),
  (ii) retrieval parity: for 100 sampled eval statements (seed 5), query
  the eval-half matrix with the PROJECTED vector — P@1 of recovering the
  statement's own row vs querying with the true gist (parity = agreement
  of top-1 between projected and true query),
  (iii) neighborhood overlap: mean Jaccard of top-10 sets.
- POSITIVE CONTROL (D8): synthetic data with a KNOWN 32-dim latent
  (random low-rank + small noise) run through the same code — the knee
  must appear at ~32 or the probe cannot detect knees.
- Deliverable: the curve + named knee N* = smallest N with parity >= 0.95
  and overlap >= 0.8.

Usage: .venv/bin/python scripts/probe_anchor_a1.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from codec.manifest import run_manifest  # noqa: E402

rng = np.random.default_rng(0)


def kmeans(X: np.ndarray, k: int, iters: int = 20) -> np.ndarray:
    C = X[rng.choice(len(X), size=k, replace=False)].copy()
    for _ in range(iters):
        d = ((X[:, None, :] - C[None]) ** 2).sum(-1) if k <= 64 else None
        if d is None:   # memory-lean assignment for larger k
            a = np.empty(len(X), np.int64)
            for i in range(0, len(X), 4096):
                blk = X[i:i + 4096]
                a[i:i + 4096] = ((blk ** 2).sum(1, keepdims=True)
                                 - 2 * blk @ C.T
                                 + (C ** 2).sum(1)).argmin(1)
        else:
            a = d.argmin(1)
        for j in range(k):
            m = a == j
            if m.any():
                C[j] = X[m].mean(0)
    return C


def evaluate(Z: np.ndarray, tag: str, Ns: list[int], out: dict):
    half = np.arange(len(Z))
    tr, ev = Z[half % 2 == 0], Z[half % 2 == 1]
    ev = ev / (np.linalg.norm(ev, axis=1, keepdims=True) + 1e-12)
    q_idx = np.random.default_rng(5).choice(len(ev), size=min(100, len(ev)),
                                            replace=False)
    true_top = {}
    sims_true = ev[q_idx] @ ev.T
    for r, qi in enumerate(q_idx):
        s = sims_true[r].copy()
        top10 = np.argpartition(-s, 10)[:11]
        true_top[qi] = top10[np.argsort(-s[top10])][:10]
    rows = []
    for N in Ns:
        C = kmeans(tr, N)
        B = C / (np.linalg.norm(C, axis=1, keepdims=True) + 1e-12)
        # least-squares projection of eval gists onto span(B)
        G = B @ B.T + 1e-6 * np.eye(N)
        W = np.linalg.solve(G, B @ ev.T).T          # coords (n_ev, N)
        P = W @ B
        Pn = P / (np.linalg.norm(P, axis=1, keepdims=True) + 1e-12)
        resid = float(1 - (Pn * ev).sum(1).mean())
        agree = 0
        jac = []
        sims_p = Pn[q_idx] @ ev.T
        for r, qi in enumerate(q_idx):
            s = sims_p[r].copy()
            top10 = np.argpartition(-s, 10)[:11]
            top10 = top10[np.argsort(-s[top10])][:10]
            agree += top10[0] == true_top[qi][0]
            jac.append(len(set(top10) & set(true_top[qi]))
                       / len(set(top10) | set(true_top[qi])))
        rows.append({"N": N, "residual": resid,
                     "parity_p1": agree / len(q_idx),
                     "jaccard10": float(np.mean(jac))})
        print(f"[a1:{tag}] N={N:5d} resid={resid:.4f} "
              f"parity={agree/len(q_idx):.3f} jac={np.mean(jac):.3f}",
              flush=True)
    out[tag] = rows


# ---- load real vectors from PG ---------------------------------------------
from foundation.kb import KB  # noqa: E402

kb = KB(backend="pg", table="poc")
wiki_idx = [c["idx"] for c in kb.claims
            if not str(c["page"]).startswith("arxiv:")
            and not str(c["page"]).startswith("planted")
            and kb._live(c)]
import numpy as _np
Z = _np.stack([kb.store.vec(i) for i in wiki_idx]).astype(np.float64)
Z = Z / (np.linalg.norm(Z, axis=1, keepdims=True) + 1e-12)
print(f"[a1] {len(Z)} wiki-layer gists from poc store", flush=True)

NS = [8, 16, 32, 64, 128, 256, 512, 1024]
results: dict = {}

# positive control first: known 32-dim latent
lat = rng.standard_normal((4000, 32))
mix = rng.standard_normal((32, Z.shape[1]))
Zc = lat @ mix + 0.05 * rng.standard_normal((4000, Z.shape[1]))
Zc /= np.linalg.norm(Zc, axis=1, keepdims=True)
evaluate(Zc, "control32", [8, 16, 32, 64, 128], results)

evaluate(Z, "wiki", NS, results)

knee = next((r["N"] for r in results["wiki"]
             if r["parity_p1"] >= 0.95 and r["jaccard10"] >= 0.8), None)
ctrl_ok = (results["control32"][2]["parity_p1"] >= 0.9
           and results["control32"][0]["parity_p1"] < 0.9)
print(f"[a1] positive control (knee at 32): "
      f"{'PASS' if ctrl_ok else 'FAIL'}", flush=True)
print(f"[a1] knee N* = {knee} (parity>=0.95 & jac>=0.8)", flush=True)

json.dump({"n_vectors": len(Z), "curve": results["wiki"],
           "control": results["control32"], "control_pass": bool(ctrl_ok),
           "knee_Nstar": knee, "criteria": "parity>=0.95 & jaccard10>=0.8",
           "manifest": run_manifest(seed=0)},
          open(ROOT / "results" / "anchor_a1.json", "w"), indent=1)
print("[done] results/anchor_a1.json", flush=True)
