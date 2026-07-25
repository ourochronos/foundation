"""Interpolation coherence (codec eval #3) — is the latent space navigable?

Decode points along the geodesic (slerp) between two eval latents and measure
round-trip fidelity at each step: cos(encode(decode(z_t)), z_t). Endpoints are
on the encoder manifold; midpoints are not. A reasoner's predicted latents are
exactly such off-manifold points, so the shape of this curve says whether the
space can be traversed at all.

Reports the midpoint drop relative to endpoints — the number that matters.

Usage: .venv/bin/python scripts/probe_interpolation.py [--ckpt decoder_v1]
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

from codec import data as D_, whiten as W        # noqa: E402
from codec.decoder import SoftPrefixDecoder, build_sparse_tensors   # noqa: E402
from codec.evals import fidelity as F            # noqa: E402


def slerp(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    """Spherical interpolation, row-wise, on unit vectors."""
    dot = np.clip(np.einsum("ij,ij->i", a, b), -1.0, 1.0)
    om = np.arccos(dot)[:, None]
    so = np.sin(om)
    flat = so < 1e-6
    out = np.where(flat, (1 - t) * a + t * b,
                   np.sin((1 - t) * om) / np.where(flat, 1, so) * a
                   + np.sin(t * om) / np.where(flat, 1, so) * b)
    return (out / (np.linalg.norm(out, axis=1, keepdims=True) + 1e-12)).astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="decoder_v1")
    ap.add_argument("--n-pairs", type=int, default=60)
    ap.add_argument("--gen-bs", type=int, default=12)
    args = ap.parse_args()

    clean = [D_.Proposition(**json.loads(l)) for l in
             (ROOT / "data" / "clean_v0.jsonl").read_text().splitlines() if l.strip()]
    dense = np.load(ROOT / "results" / "dense_v0.npy")
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    Z = W.apply(dense, whitener)
    _, eval_p = D_.split(clean, eval_frac=0.1)
    eval_keys = {p.text for p in eval_p}
    is_eval = np.array([p.text in eval_keys for p in clean])
    Z_ev = Z[is_eval]
    sparse_rows = json.loads((ROOT / "results" / "sparse_v0.json").read_text())
    S_ev = [r for r, e in zip(sparse_rows, is_eval) if e]

    n = min(args.n_pairs, len(Z_ev) // 2)
    A, B = Z_ev[:n], Z_ev[n:2 * n]
    dec = SoftPrefixDecoder.load(ROOT / "checkpoints" / args.ckpt)

    sp_A = None
    if dec.k_sparse:
        # identity channel is symbolic: carry endpoint A's tokens along the path
        sp_A = build_sparse_tensors(S_ev[:n], dec.tokenizer, dec.k_sparse)
    s_A = None
    if getattr(dec, "k_s", 0):
        # structure channel likewise rides fixed (endpoint A's s-vector) —
        # only the gist is slerped; the side channels are not interpolable
        import torch as _t
        s_all = np.load(ROOT / "results" / "s_vecs_v0.npy")
        s_A = _t.from_numpy(s_all[is_eval][:n]).float()

    from codec.encode import M3Encoder
    rows, texts_at = [], {}
    for t in [0.0, 0.25, 0.5, 0.75, 1.0]:
        Zt = slerp(A, B, t)
        rec = F.reconstruct(dec, Zt, bs=args.gen_bs, sp=sp_A, s=s_A)
        texts_at[t] = rec[:3]
        rows.append({"t": t, "recons": rec, "Zt": Zt})

    del dec
    torch.cuda.empty_cache()
    m3 = M3Encoder()

    out_rows = []
    for r in rows:
        d2, _ = m3.encode(r["recons"], sparse=False)
        Zc = W.apply(d2, whitener)
        cos = np.einsum("ij,ij->i", Zc, r["Zt"])
        lens = [len(x.split()) for x in r["recons"]]
        out_rows.append({"t": r["t"], "roundtrip_cos_mean": float(cos.mean()),
                         "roundtrip_cos_p10": float(np.quantile(cos, 0.10)),
                         "mean_words": float(np.mean(lens))})
        print(f"[t={r['t']:.2f}] roundtrip_cos={cos.mean():.3f} "
              f"(p10 {np.quantile(cos, 0.10):.3f})  mean_words={np.mean(lens):.1f}")

    ends = np.mean([out_rows[0]["roundtrip_cos_mean"], out_rows[-1]["roundtrip_cos_mean"]])
    mid = out_rows[2]["roundtrip_cos_mean"]
    print(f"\n[midpoint drop] endpoints {ends:.3f} -> midpoint {mid:.3f} "
          f"({100 * (1 - mid / max(ends, 1e-6)):.0f}% relative drop)")
    print("\n[samples at each t]")
    for t, xs in texts_at.items():
        print(f"  t={t}: {xs[0][:110]}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "ckpt": args.ckpt,
           "n_pairs": n, "curve": out_rows,
           "endpoint_mean": float(ends), "midpoint": float(mid),
           "relative_drop": float(1 - mid / max(ends, 1e-6)),
           "samples": {str(k): v for k, v in texts_at.items()}}
    (ROOT / "results" / f"interpolation_{args.ckpt}.json").write_text(json.dumps(out, indent=2))
    print(f"[done] results/interpolation_{args.ckpt}.json")


if __name__ == "__main__":
    main()
