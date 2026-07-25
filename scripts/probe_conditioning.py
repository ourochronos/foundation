"""Is the decoder actually conditioning on z? (D8 control applied to the decoder)

A flat robustness curve is ambiguous: it means either (a) noise training gave
genuine robustness, or (b) the decoder ignores z and samples from its prior.
The shuffled-z control separates them — if reconstruction quality with a
permuted z matches that with the correct z, the decoder is not using z.

Also extends the sigma sweep: sigma relates to latent cosine as
cos ~ 1/sqrt(1+sigma^2), so sigma<=0.5 is only cos>=0.89 — far too mild a
perturbation to show degradation. sigma in {1,2,4} reaches cos 0.71/0.45/0.24.

Usage: .venv/bin/python scripts/probe_conditioning.py
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

from codec import data as D_, whiten as W       # noqa: E402
from codec.decoder import SoftPrefixDecoder     # noqa: E402
from codec.evals import fidelity as F           # noqa: E402

N = 120


def main() -> None:
    clean = [D_.Proposition(**json.loads(l)) for l in
             (ROOT / "data" / "clean_v0.jsonl").read_text().splitlines() if l.strip()]
    dense = np.load(ROOT / "results" / "dense_v0.npy")
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    Z = W.apply(dense, whitener)

    _, eval_p = D_.split(clean, eval_frac=0.1)
    eval_keys = {p.text for p in eval_p}
    is_eval = np.array([p.text in eval_keys for p in clean])
    Z_ev = Z[is_eval][:N]
    P_ev = [p for p in clean if p.text in eval_keys][:N]

    dec = SoftPrefixDecoder.load(ROOT / "checkpoints" / "decoder_v0")
    rng = np.random.default_rng(0)

    rows = []
    # correct z at increasing perturbation
    for sigma in [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]:
        rec = F.reconstruct(dec, Z_ev, bs=16, sigma=sigma)
        r = F.em_rates(rec, P_ev)
        r["condition"] = f"sigma={sigma}"
        r["latent_cos"] = float(1.0 / np.sqrt(1.0 + sigma**2))
        rows.append(r)
        print(f"[{r['condition']:>12}] (z·z'≈{r['latent_cos']:.2f}) "
              f"entity_em={r['entity_em']:.3f} number_em={r['number_em']:.3f}")

    # controls: shuffled z (wrong latent), and gaussian-random z
    perm = rng.permutation(len(Z_ev))
    while (perm == np.arange(len(Z_ev))).any():          # no fixed points
        perm = rng.permutation(len(Z_ev))
    for name, Zc in [("shuffled", Z_ev[perm]),
                     ("random", (lambda A: A / np.linalg.norm(A, axis=1, keepdims=True))(
                         rng.standard_normal(Z_ev.shape).astype(np.float32)))]:
        rec = F.reconstruct(dec, Zc, bs=16)
        r = F.em_rates(rec, P_ev)          # scored against the ORIGINAL propositions
        r["condition"] = name
        rows.append(r)
        print(f"[{name:>12}] entity_em={r['entity_em']:.3f} number_em={r['number_em']:.3f}")

    # semantic conditioning: does the reconstruction re-encode near the TRUE z?
    # (cycle cos is always measured against Z_ev, whatever latent produced the text)
    recs = {cond: F.reconstruct(dec, Zc, bs=16)
            for cond, Zc in [("sigma=0.0", Z_ev), ("shuffled", Z_ev[perm])]}
    del dec
    torch.cuda.empty_cache()

    from codec.encode import M3Encoder
    m3 = M3Encoder()
    sem = {}
    for cond, rec in recs.items():
        sem[cond] = F.cycle_cos(m3, whitener, rec, Z_ev)
        print(f"[cycle/{cond}] cos_mean={sem[cond]['cycle_cos_mean']:.3f}")

    verdict = ("CONDITIONING CONFIRMED" if
               rows[0]["entity_em"] > 2 * max(r["entity_em"] for r in rows if
                                              r["condition"] in ("shuffled", "random"))
               else "WEAK/NO CONDITIONING — decoder may be sampling from its prior")
    print(f"\n[verdict] {verdict}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "n": N, "rows": rows, "cycle": sem, "verdict": verdict}
    (ROOT / "results" / "conditioning_v0.json").write_text(json.dumps(out, indent=2))
    print("[done] results/conditioning_v0.json")


if __name__ == "__main__":
    main()
