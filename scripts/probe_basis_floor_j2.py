"""J2 — basis-floor curve (D51, pre-registered; T6 expressivity invariant).

Expression: matching pursuit of z onto <=m of N k-means anchors; size =
m*log2(N) bits (symbols ride outside the basis, D3). Three graded metrics —
reconstruction / interface (retrieval + detection through z-hat) / decode
(deferred, GPU) — because WHICH KNEES FIRST is the finding.

AMENDMENT (logged): D51 listed N up to 65k; the anchor pool is the 16k
corpus, so N cannot exceed train points. Top rung = all-train-points
(nearest-neighbor limit). Everything else as registered. No training.

Usage: .venv/bin/python scripts/probe_basis_floor_j2.py
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

from codec import whiten as W                                     # noqa: E402
from codec.evals.anchors import fit_anchors                       # noqa: E402
from codec.manifest import run_manifest                           # noqa: E402
from codec.memory_store import MemoryStore                        # noqa: E402

rng = np.random.default_rng(0)


def unit(X):
    return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)


# ---- spaces -------------------------------------------------------------
wh = W.load(str(ROOT / "results" / "whiten_v0.npz"))
X = unit(W.apply(np.load(ROOT / "results" / "dense_v0.npy"), wh))
hold = rng.choice(len(X), 2000, replace=False)
mask = np.ones(len(X), bool); mask[hold] = False
Xtr, Xev = X[mask], X[hold]

w4 = json.loads((ROOT / "data" / "closed_world_v4.json").read_text())
z4 = np.load(ROOT / "results" / "closed_world_v4_emb.npz")
Zf, Zq, Zh = z4["Zf"], z4["Zq"], z4["Zh"]
HELD = set(w4["held_out_phrasings"])
singles = [i for i, q in enumerate(w4["queries"]) if q["kind"] == "single"
           and q["phrasing_idx"] in HELD][:400]
gold = np.array([w4["queries"][i]["fact_idx"] for i in singles])
Zq_ev = Zq[singles]
hops_ix = rng.choice(len(Zh), 300, replace=False)
Zh_ev = Zh[hops_ix]

ood = json.loads((ROOT / "data" / "ood_sentences_v0.json").read_text())
ood_texts = ood if isinstance(ood[0], str) else [o["text"] for o in ood]
k5 = np.load(ROOT / "results" / "frozen_templates_k5_emb.npz")
Z_k5 = np.concatenate([k5["Zs"], k5["Zhn"]])

cache = ROOT / "results" / "j2_ood_emb.npz"
if cache.exists():
    Z_ood = np.load(cache)["Z"]
else:
    sys.path.insert(0, str(ROOT / "scripts"))
    import v06_pipeline as P
    Z_ood = P.embed_texts(ood_texts)
    np.savez(cache, Z=Z_ood)

store = MemoryStore()
for f, zf in zip(w4["facts"], Zf):
    store.add(zf, [], f["text"])

RELS = sorted({f["relation"] for f in w4["facts"]})
det_head = nn.Sequential(nn.Linear(1024, 256), nn.GELU(),
                         nn.Linear(256, len(RELS)))
det_head.load_state_dict(torch.load(
    ROOT / "checkpoints" / "reasoner_v06_det.pt", weights_only=True))


def det_top(Z):
    with torch.no_grad():
        return torch.sigmoid(det_head(torch.tensor(np.asarray(
            Z, np.float32)))).numpy().argmax(1)


def mp(Z, A, m_max):
    """Greedy matching pursuit; returns reconstructions at each m."""
    Rres = np.asarray(Z, np.float32).copy()
    out, acc = {}, np.zeros_like(Rres)
    for m in range(1, m_max + 1):
        S = Rres @ A.T
        j = np.abs(S).argmax(1)
        c = S[np.arange(len(Rres)), j]
        acc += c[:, None] * A[j]
        Rres -= c[:, None] * A[j]
        out[m] = acc.copy()
    return out


def p_at_1(Zhat):
    hit = 0
    for z, g in zip(Zhat, gold):
        hit += store.query(z, None, k=1, id_weight=0.0)[0][0] == g
    return hit / len(gold)


base_p1 = p_at_1(Zq_ev)
base_det = det_top(np.concatenate([Zq_ev, Zh_ev]))
print(f"[base] retrieval P@1 (full z, gist-only) = {base_p1:.3f}", flush=True)

MS = [1, 2, 4, 8, 16]
NS = [64, 256, 1024, 4096, len(Xtr)]
res = {}
for N in NS:
    A = (unit(Xtr) if N == len(Xtr)
         else fit_anchors(Xtr, N))
    row = {}
    for name, Z in (("corpus", Xev), ("query", Zq_ev),
                    ("hopq", Zh_ev), ("ood", Z_ood), ("k5", Z_k5)):
        recon = mp(Z, A, max(MS))
        ent = {}
        for m in MS:
            fid = float(np.mean(np.sum(unit(recon[m]) * unit(np.asarray(
                Z, np.float32)), axis=1)))
            ent[m] = {"fid": round(fid, 4)}
            if name == "query":
                ent[m]["p1"] = round(p_at_1(recon[m]), 4)
        if name in ("query", "hopq"):
            agree = float(np.mean(det_top(recon[8])
                                  == det_top(np.asarray(Z, np.float32))))
            ent["det_agree_m8"] = round(agree, 4)
        row[name] = ent
    res[N] = row
    q8 = row["query"][8]
    print(f"[N={N:>5}] corpus fid m8={row['corpus'][8]['fid']:.3f}  "
          f"query P@1 m8={q8['p1']:.3f}/{base_p1:.3f}  "
          f"det-agree m8={row['query']['det_agree_m8']:.3f}  "
          f"ood fid m8={row['ood'][8]['fid']:.3f}", flush=True)

# knees (pre-registered criteria)
knee_int = next((N for N in NS
                 if res[N]["query"][8]["p1"] >= 0.97 * base_p1), None)
knee_rec = next((N for N in NS
                 if res[N]["corpus"][8]["fid"] >= 0.90), None)
print(f"[knees] interface (P@1>=0.97x base @m8): N={knee_int} | "
      f"reconstruction (fid>=0.90 @m8): N={knee_rec}", flush=True)

# novelty tax: min m to reach fid 0.85 per set at N=4096
tax = {}
for name in ("corpus", "ood", "k5"):
    tax[name] = next((m for m in MS
                      if res[4096][name][m]["fid"] >= 0.85), ">16")
print(f"[novelty] min m for fid>=0.85 @N=4096: {tax}", flush=True)

out = ROOT / "results" / "basis_floor_j2.json"
out.write_text(json.dumps(
    {"results": {str(k): v for k, v in res.items()},
     "base": {"p1": base_p1},
     "knees": {"interface": knee_int, "reconstruction": knee_rec,
               "criteria": "P@1>=0.97xbase @m8; fid>=0.90 @m8"},
     "novelty_tax_m_at_fid085_N4096": tax,
     "amendment": "N=65k impossible (pool=16k corpus); top rung = "
                  "all-train-points NN limit",
     "manifest": run_manifest(seed=0, inputs={
         "corpus": ROOT / "results" / "dense_v0.npy",
         "whitener": ROOT / "results" / "whiten_v0.npz"},
         config={"NS": NS, "MS": MS,
                 "heads": "loaded (no training)"})},
    indent=2))
print(f"[done] {out.relative_to(ROOT)}")
