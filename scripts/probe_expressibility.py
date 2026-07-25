"""Expressibility gate (T2, Phase 2.5): are anchors + projections + symbols
sufficient to EXPRESS novel propositions?

Rotations were rejected as the novelty mechanism (isometries relabel, they
don't extend — D4/D15/D27 discussion). The surviving hypothesis: novel gists
are reachable as PROJECTIONS onto the anchor span (compositional novelty),
while referential novelty (which entity) rides the symbolic identity channel
and needs no geometry at all.

Method: k-means anchors fit on TRAIN gists only; every held-out eval gist is
approximated as a least-squares combination of its m nearest anchors; the
approximation replaces the true gist in the shipping codec (identities and
s-vector intact — that separation is the architecture under test).

**Pre-registered prediction (D24)**: decoder output quality is invariant to
gist perturbation through latent cos ~0.78. Therefore wherever the anchor
approximation reaches cos >= ~0.78, reconstruction fidelity must equal the
true-gist baseline. If it does, `anchors + operators + symbols` is sufficient
for expression and anchor MINIMIZATION (D6's deferred workstream) becomes the
next measurable question — the N-sweep here is its first curve.

Usage: .venv/bin/python scripts/probe_expressibility.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec import data as D_, whiten as W                       # noqa: E402
from codec.decoder import SoftPrefixDecoder, build_sparse_tensors  # noqa: E402
from codec.evals import fidelity as F                            # noqa: E402
from codec.evals.anchors import fit_anchors                      # noqa: E402

N_EVAL = 150
GEN_BS = 16


def unit(X):
    return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)


def approx(Z, A, m):
    """Least-squares combination of each row's m nearest anchors, renormed."""
    sims = Z @ A.T
    out = np.zeros_like(Z)
    for i, z in enumerate(Z):
        idx = np.argpartition(-sims[i], m)[:m]
        B = A[idx]                                     # [m, d]
        w, *_ = np.linalg.lstsq(B.T, z, rcond=None)
        out[i] = w @ B
    return unit(out)


def main() -> None:
    clean = [D_.Proposition(**json.loads(l)) for l in
             (ROOT / "data" / "clean_v0.jsonl").read_text().splitlines() if l.strip()]
    Z = unit(W.apply(np.load(ROOT / "results" / "dense_v0.npy"),
                     W.load(str(ROOT / "results" / "whiten_v0.npz"))))
    sparse_rows = json.loads((ROOT / "results" / "sparse_tagged_v0.json").read_text())
    S_all = np.load(ROOT / "results" / "s_vecs_v0.npy")

    _, eval_p = D_.split(clean, eval_frac=0.1)
    ek = {p.text for p in eval_p}
    is_ev = np.array([p.text in ek for p in clean])
    Z_tr, Z_ev = Z[~is_ev], Z[is_ev][:N_EVAL]
    P_ev = [p for p in clean if p.text in ek][:N_EVAL]

    dec = SoftPrefixDecoder.load(ROOT / "checkpoints" / "decoder_v2t")
    sp = build_sparse_tensors([r for r, e in zip(sparse_rows, is_ev) if e][:N_EVAL],
                              dec.tokenizer, dec.k_sparse, max_sub=6)
    s = torch.from_numpy(S_all[is_ev][:N_EVAL]).float()
    bpairs = F.binding_pairs(P_ev)

    def score(Zx, label):
        rec = F.reconstruct(dec, Zx, bs=GEN_BS, sp=sp, s=s)
        em = F.em_rates(rec, P_ev)
        b = F.binding_rate(rec, bpairs)
        row = {"label": label,
               "entity_em": em["entity_em"], "number_em": em["number_em"],
               "binding": b["binding_rate"]}
        print(f"[{label:>22}] entity={em['entity_em']:.3f} "
              f"number={em['number_em']:.3f} binding={b['binding_rate']:.3f}",
              flush=True)
        return row

    rows = [score(Z_ev, "TRUE gist (baseline)")]

    for n_anchors in (512, 1024, 4096):
        A = unit(fit_anchors(Z_tr, n_anchors))
        for m in (1, 8, 32):
            Za = A[np.argmax(Z_ev @ A.T, axis=1)] if m == 1 else approx(Z_ev, A, m)
            cos = float(np.einsum("ij,ij->i", Za, Z_ev).mean())
            label = f"N={n_anchors} m={m}"
            print(f"[{label:>22}] approx latent cos = {cos:.3f}", flush=True)
            row = score(Za, label)
            row.update({"n_anchors": n_anchors, "m": m, "latent_cos": cos})
            rows.append(row)

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "n_eval": len(P_ev), "prediction":
           "quality equals baseline wherever latent_cos >= ~0.78 (D24)",
           "rows": rows}
    (ROOT / "results" / "expressibility_v0.json").write_text(json.dumps(out, indent=2))
    print("[done] results/expressibility_v0.json")


if __name__ == "__main__":
    main()
