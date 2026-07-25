"""Cycle-under-noise for the triple-conditioned decoder (D21/D22 follow-up).

Under gist noise the v2 family's EM metrics stay flat BY DESIGN — identities
ride the symbolic channel. What noise should cost is the semantic frame, and
EM can't see that. This measures it: for each sigma, reconstruct (identities
and s intact, gist noised), re-encode, and report cycle cos against the CLEAN
gist. The gap between flat EM and falling cycle = what the gist actually
contributes under degradation.

Usage: .venv/bin/python scripts/probe_cycle_noise.py [--ckpt decoder_v2t]
"""

from __future__ import annotations

import argparse
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="decoder_v2t")
    ap.add_argument("--sparse-file", default="sparse_tagged_v0.json")
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--gen-bs", type=int, default=16)
    args = ap.parse_args()

    clean = [D_.Proposition(**json.loads(l)) for l in
             (ROOT / "data" / "clean_v0.jsonl").read_text().splitlines() if l.strip()]
    Z = W.apply(np.load(ROOT / "results" / "dense_v0.npy"),
                W.load(str(ROOT / "results" / "whiten_v0.npz")))
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    sparse_rows = json.loads((ROOT / "results" / args.sparse_file).read_text())
    S_all = np.load(ROOT / "results" / "s_vecs_v0.npy")

    _, eval_p = D_.split(clean, eval_frac=0.1)
    ek = {p.text for p in eval_p}
    is_ev = np.array([p.text in ek for p in clean])
    P_ev = [p for p in clean if p.text in ek][:args.n]
    Z_ev = Z[is_ev][:args.n]
    dec = SoftPrefixDecoder.load(ROOT / "checkpoints" / args.ckpt)
    max_sub = 6 if "tagged" in args.sparse_file else 4
    sp = build_sparse_tensors([r for r, e in zip(sparse_rows, is_ev) if e][:args.n],
                              dec.tokenizer, dec.k_sparse, max_sub=max_sub)
    s = torch.from_numpy(S_all[is_ev][:args.n]).float()

    sigmas = [0.0, 0.1, 0.2, 0.3, 0.5, 0.8]
    recons_by = {}
    for sg in sigmas:
        recons_by[sg] = F.reconstruct(dec, Z_ev, bs=args.gen_bs, sigma=sg,
                                      sp=sp, s=s)
    del dec
    torch.cuda.empty_cache()

    from codec.encode import M3Encoder
    m3 = M3Encoder()
    bpairs = F.binding_pairs(P_ev)
    rows = []
    for sg in sigmas:
        em = F.em_rates(recons_by[sg], P_ev)
        cyc = F.cycle_cos(m3, whitener, recons_by[sg], Z_ev)
        b = F.binding_rate(recons_by[sg], bpairs)
        lat_cos = 1.0 / np.sqrt(1.0 + sg * sg)
        rows.append({"sigma": sg, "latent_cos": lat_cos,
                     "entity_em": em["entity_em"], "number_em": em["number_em"],
                     "binding": b["binding_rate"],
                     "cycle_cos": cyc["cycle_cos_mean"],
                     "cycle_p10": cyc["cycle_cos_p10"]})
        print(f"[σ={sg:.1f} lat_cos={lat_cos:.2f}] entity={em['entity_em']:.3f} "
              f"number={em['number_em']:.3f} binding={b['binding_rate']:.3f} "
              f"cycle={cyc['cycle_cos_mean']:.3f} (p10 {cyc['cycle_cos_p10']:.3f})",
              flush=True)

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "ckpt": args.ckpt, "n": len(P_ev), "rows": rows}
    (ROOT / "results" / f"cycle_noise_{args.ckpt}.json").write_text(
        json.dumps(out, indent=2))
    print(f"[done] results/cycle_noise_{args.ckpt}.json")


if __name__ == "__main__":
    main()
