"""B2 — append-only anchor minting over a content stream (docs/11, D90).

PROTOCOL (registered here, committed BEFORE the run — D64). D89 made this
the load-bearing mechanism of axis B: anchors transfer, global statistics
don't, so growth = appending anchors.

- BASE: N*=256 anchors (A1) fit on the EVEN half of the original wiki
  layer (v3+g2 claims; raw L2-normalized gists — the A2 frame, no
  whitener per D89).
- tau: 95th percentile projection residual of the ODD half (held-out,
  in-domain) under the base — "more novel than 95% of in-domain content".
- STREAMS, in order: (1) the 1k tranche (in-domain growth control,
  ~4.9k items); (2) the ArXiv claims (cross-domain, 297). Per item:
  project onto the CURRENT basis; residual > tau => MINT the item's own
  vector as a new anchor (append-only; nothing old moves, by
  construction).
- CONTROLS (D8): a replay stream of base-fit items must mint ~0%; a
  pure-noise stream (100 items) must mint ~100%.
- REGISTERED CRITERION (docs/11): per stream, second-half minting slope /
  first-half slope <= 0.5 => DECELERATING (saturation confirms);
  >= 0.8 => LINEAR (small-basis bet fails); between => inconclusive.
- End-state quality: retrieval parity of the final enlarged basis
  (100 seeded queries per stream segment, projected-vs-true top-1).

Usage: .venv/bin/python scripts/probe_mint_b2.py
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
N0 = 256


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


def norm_rows(X):
    return X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)


kb = KB(backend="pg", table="poc")
base_i, tranche_i, arx_i = [], [], []
for c in kb.claims:
    if not kb._live(c):
        continue
    p, sid = str(c["page"]), str(c["sid"])
    if p.startswith(("planted", "user:", "demo:")):
        continue
    if p.startswith("arxiv:"):
        arx_i.append(c["idx"])
    elif sid.startswith(("out_v3", "out_g2")):
        base_i.append(c["idx"])
    else:
        tranche_i.append(c["idx"])
V = {i: kb.store.vec(i) for i in base_i + tranche_i + arx_i}
BASE = norm_rows(np.stack([V[i] for i in base_i]).astype(np.float64))
TR = norm_rows(np.stack([V[i] for i in tranche_i]).astype(np.float64))
AX = norm_rows(np.stack([V[i] for i in arx_i]).astype(np.float64))
print(f"[b2] base={len(BASE)} tranche={len(TR)} arxiv={len(AX)}",
      flush=True)

fit, held = BASE[::2], BASE[1::2]
B = norm_rows(kmeans(fit, N0))


class Basis:
    def __init__(self, B0):
        self.B = list(B0)
        self._refresh()

    def _refresh(self):
        Bm = np.stack(self.B)
        self.Bm = Bm
        self.Ginv = np.linalg.inv(Bm @ Bm.T + 1e-6 * np.eye(len(Bm)))

    def resid(self, x):
        w = self.Ginv @ (self.Bm @ x)
        p = w @ self.Bm
        p /= np.linalg.norm(p) + 1e-12
        return 1 - float(p @ x)

    def mint(self, x):
        self.B.append(x)
        self._refresh()


bas = Basis(B)
tau = float(np.quantile([bas.resid(x) for x in held], 0.95))
print(f"[b2] tau (P95 held-out in-domain) = {tau:.4f}", flush=True)

# controls
replay_mints = sum(bas.resid(x) > tau for x in fit[:200])
noise = norm_rows(rng.standard_normal((100, BASE.shape[1])))
noise_mints = sum(bas.resid(x) > tau for x in noise)
print(f"[b2] controls: replay mint-rate {replay_mints}/200 [~0], "
      f"noise {noise_mints}/100 [~100]", flush=True)

curves = {}
for name, S in (("tranche_in_domain", TR), ("arxiv_cross_domain", AX)):
    minted_at, n0 = [], len(bas.B)
    for t, x in enumerate(S):
        if bas.resid(x) > tau:
            bas.mint(x)
            minted_at.append(t)
        if (t + 1) % 1000 == 0:
            print(f"[b2] {name}: {t+1}/{len(S)} seen, "
                  f"{len(bas.B)-n0} minted", flush=True)
    m = len(minted_at)
    half = len(S) / 2
    m1 = sum(1 for t in minted_at if t < half)
    m2 = m - m1
    ratio = (m2 / max(m1, 1)) if m1 else (np.inf if m2 else 0.0)
    verdict = ("DECELERATING" if ratio <= 0.5 else
               "LINEAR" if ratio >= 0.8 else "INCONCLUSIVE")
    curves[name] = {"n_stream": len(S), "minted": m,
                    "mint_rate": m / len(S), "first_half": m1,
                    "second_half": m2, "slope_ratio": ratio,
                    "verdict": verdict, "minted_at": minted_at}
    print(f"[b2] {name}: minted {m}/{len(S)} "
          f"(halves {m1}/{m2}, ratio {ratio:.2f}) => {verdict}",
          flush=True)

# end-state retrieval parity per segment
def parity(S):
    q = np.random.default_rng(5).choice(len(S), size=min(100, len(S)),
                                        replace=False)
    P = np.stack([norm_rows((bas.Ginv @ (bas.Bm @ S[r]) @ bas.Bm
                             ).reshape(1, -1))[0] for r in q])
    hits = 0
    for k, r in enumerate(q):
        hits += int(np.argmax(P[k] @ S.T) == r)
    return hits / len(q)


par = {"tranche": parity(TR), "arxiv": parity(AX)}
print(f"[b2] end-state parity: tranche={par['tranche']:.3f} "
      f"arxiv={par['arxiv']:.3f} | final basis {len(bas.B)} anchors "
      f"(+{len(bas.B)-N0})", flush=True)

json.dump({"tau": tau, "n_base_anchors": N0,
           "final_anchors": len(bas.B),
           "controls": {"replay_mints_per200": int(replay_mints),
                        "noise_mints_per100": int(noise_mints)},
           "curves": curves, "end_parity": par,
           "manifest": run_manifest(seed=0)},
          open(ROOT / "results" / "mint_b2.json", "w"), indent=1)
print("[done] results/mint_b2.json", flush=True)
