"""Is low eval fidelity an information limit or a generalization failure?

Train loss 0.0196 vs 11.5% eval entity EM is a large gap. Two very different
explanations, with opposite consequences for the program:

  A. the embedding genuinely lacks identity information
     -> TRAIN-set reconstruction is also poor. Founding hypothesis holds;
        the sparse channel is the fix.
  B. the decoder memorized 4.4k propositions and cannot generalize
     -> TRAIN-set reconstruction is near-perfect, eval is not. The bottleneck
        is data/learning, and eval numbers understate what the latent carries.

Also checks whether the sparse channel is being read at all on TRAIN data, and
the norm ratio between the two prefix channels (a plausible cause of the
decoder ignoring sparse).

Usage: .venv/bin/python scripts/diag_memorization.py [--ckpt decoder_v1]
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

from codec import data as D_, whiten as W                            # noqa: E402
from codec.decoder import SoftPrefixDecoder, build_sparse_tensors    # noqa: E402
from codec.evals import fidelity as F                                # noqa: E402

N = 200


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="decoder_v1")
    ap.add_argument("--gen-bs", type=int, default=12)
    args = ap.parse_args()

    clean = [D_.Proposition(**json.loads(l)) for l in
             (ROOT / "data" / "clean_v0.jsonl").read_text().splitlines() if l.strip()]
    dense = np.load(ROOT / "results" / "dense_v0.npy")
    sparse_rows = json.loads((ROOT / "results" / "sparse_v0.json").read_text())
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    Z = W.apply(dense, whitener)

    _, eval_p = D_.split(clean, eval_frac=0.1)
    eval_keys = {p.text for p in eval_p}
    is_eval = np.array([p.text in eval_keys for p in clean])

    dec = SoftPrefixDecoder.load(ROOT / "checkpoints" / args.ckpt)
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "ckpt": args.ckpt}

    for split_name, mask in [("TRAIN", ~is_eval), ("EVAL", is_eval)]:
        Zs = Z[mask][:N]
        Ps = [p for p, m in zip(clean, mask) if m][:N]
        Ss = [s for s, m in zip(sparse_rows, mask) if m][:N]
        sp = build_sparse_tensors(Ss, dec.tokenizer, dec.k_sparse) if dec.k_sparse else None
        rec = F.reconstruct(dec, Zs, bs=args.gen_bs, sp=sp)
        r = F.em_rates(rec, Ps)
        out[split_name] = r
        print(f"[{split_name}] exact={r['exact_text_rate']:.3f} "
              f"entity_em={r['entity_em']:.3f} number_em={r['number_em']:.3f}")
        if split_name == "TRAIN":
            for o, x in list(zip(Ps, rec))[:3]:
                print(f"   ├─ orig : {o.text}\n   └─ recon: {x}")

    # channel norm comparison — does the sparse prefix even register?
    if dec.k_sparse:
        with torch.no_grad():
            z = torch.from_numpy(Z[:32]).to(dec.device, torch.float32)
            sp32 = build_sparse_tensors(sparse_rows[:32], dec.tokenizer, dec.k_sparse)
            dense_pref = dec.proj(z.to(torch.bfloat16))
            sparse_pref = dec._sparse_prefix(sp32)
            dn = dense_pref.float().norm(dim=-1).mean().item()
            sn = sparse_pref.float().norm(dim=-1).mean().item()
        out["prefix_norms"] = {"dense": dn, "sparse": sn, "ratio": sn / max(dn, 1e-9)}
        print(f"\n[prefix norms] dense={dn:.3f} sparse={sn:.3f} "
              f"(sparse/dense = {sn / max(dn, 1e-9):.3f})")
        if sn / max(dn, 1e-9) < 0.25:
            print("  ^ sparse prefix is much smaller than dense — plausible cause of "
                  "the decoder ignoring it (weights ~0.05-0.3 shrink the embeddings)")

    gap = out["TRAIN"]["entity_em"] - out["EVAL"]["entity_em"]
    verdict = ("MEMORIZATION-DOMINATED — train >> eval; eval understates what the "
               "latent carries, bottleneck is data/generalization"
               if gap > 0.25 else
               "INFORMATION-LIMITED — train ≈ eval; the latent genuinely lacks "
               "identity detail (founding hypothesis)")
    out["verdict"] = verdict
    print(f"\n[train-eval entity EM gap] {gap:+.3f}\n[verdict] {verdict}")

    (ROOT / "results" / f"memorization_{args.ckpt}.json").write_text(json.dumps(out, indent=2))
    print(f"[done] results/memorization_{args.ckpt}.json")


if __name__ == "__main__":
    main()
