"""J2b — PQ vs sparse-anchor codes at matched bits (J2 follow-up).

J2 measured that m-sparse anchor codes fail in the whitened space (eff.
rank ~523: every direction carries variance, so <=16 atoms cannot span it).
Product quantization IS an anchor basis — S subspaces x 256 anchors each —
i.e. block-structured crystallization. Same three metrics, same eval sets,
expression size = 8*S bits. Closed-form (per-subspace k-means), no training.

Usage: .venv/bin/python scripts/probe_pq_j2b.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sklearn.cluster import MiniBatchKMeans   # noqa: E402
from codec import whiten as W                 # noqa: E402
from codec.manifest import run_manifest       # noqa: E402
from codec.memory_store import MemoryStore    # noqa: E402

rng = np.random.default_rng(0)
unit = lambda X: X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)

wh = W.load(str(ROOT / "results" / "whiten_v0.npz"))
X = unit(W.apply(np.load(ROOT / "results" / "dense_v0.npy"), wh))
hold = rng.choice(len(X), 2000, replace=False)
mask = np.ones(len(X), bool); mask[hold] = False
Xtr, Xev = X[mask], X[hold]

w4 = json.loads((ROOT / "data" / "closed_world_v4.json").read_text())
z4 = np.load(ROOT / "results" / "closed_world_v4_emb.npz")
Zf, Zq = z4["Zf"], z4["Zq"]
HELD = set(w4["held_out_phrasings"])
singles = [i for i, q in enumerate(w4["queries"]) if q["kind"] == "single"
           and q["phrasing_idx"] in HELD][:400]
gold = np.array([w4["queries"][i]["fact_idx"] for i in singles])
Zq_ev = Zq[singles].astype(np.float32)
ood = np.load(ROOT / "results" / "j2_ood_emb.npz")["Z"].astype(np.float32)

store = MemoryStore()
for f, zf in zip(w4["facts"], Zf):
    store.add(zf, [], f["text"])

RELS = sorted({f["relation"] for f in w4["facts"]})
det_head = nn.Sequential(nn.Linear(1024, 256), nn.GELU(),
                         nn.Linear(256, len(RELS)))
det_head.load_state_dict(torch.load(
    ROOT / "checkpoints" / "reasoner_v06_det.pt", weights_only=True))
det_top = lambda Z: torch.sigmoid(det_head(torch.tensor(
    np.asarray(Z, np.float32)))).detach().numpy().argmax(1)

def p1(Zhat):
    return sum(store.query(z, None, k=1, id_weight=0.0)[0][0] == g
               for z, g in zip(Zhat, gold)) / len(gold)

base_p1, base_det = p1(Zq_ev), det_top(Zq_ev)
res = {}
D = X.shape[1]
for S in (8, 16, 32, 64, 128):
    d = D // S
    books = []
    for s in range(S):
        km = MiniBatchKMeans(n_clusters=256, random_state=0,
                             batch_size=1024, n_init=3, max_iter=100)
        km.fit(Xtr[:, s * d:(s + 1) * d])
        books.append(km.cluster_centers_.astype(np.float32))
    def enc(Z):
        out = np.empty_like(Z, dtype=np.float32)
        for s in range(S):
            seg = Z[:, s * d:(s + 1) * d]
            j = ((seg[:, None, :] - books[s][None]) ** 2).sum(-1).argmin(1)
            out[:, s * d:(s + 1) * d] = books[s][j]
        return out
    fid_c = float(np.mean(np.sum(unit(enc(Xev)) * Xev, axis=1)))
    Zh = enc(Zq_ev)
    fid_o = float(np.mean(np.sum(unit(enc(ood)) * unit(ood), axis=1)))
    r_p1 = p1(Zh)
    agree = float(np.mean(det_top(Zh) == base_det))
    res[S] = {"bits": 8 * S, "corpus_fid": round(fid_c, 4),
              "ood_fid": round(fid_o, 4), "p1": round(r_p1, 4),
              "det_agree": round(agree, 4)}
    print(f"[PQ S={S:>3} {8*S:>4}b] corpus fid={fid_c:.3f} "
          f"P@1={r_p1:.3f}/{base_p1:.3f} det-agree={agree:.3f} "
          f"ood fid={fid_o:.3f}", flush=True)

knee = next((S for S in sorted(res) if res[S]["p1"] >= 0.97 * base_p1), None)
print(f"[knee] interface at {8*knee if knee else '>1024'} bits "
      f"(PQ) vs sparse-anchor: not reached at ~110 bits", flush=True)
out = ROOT / "results" / "pq_j2b.json"
out.write_text(json.dumps(
    {"results": {str(k): v for k, v in res.items()},
     "base": {"p1": base_p1},
     "interface_knee_bits": 8 * knee if knee else None,
     "manifest": run_manifest(seed=0, config={"K_per_sub": 256})},
    indent=2))
print(f"[done] {out.relative_to(ROOT)}")
