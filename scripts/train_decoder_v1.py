"""M2 ablation: decoder v1 = dense gist channel + sparse identity channel.

Compares directly against decoder v0 (dense-only): does the sparse channel close
the identity-loss gap (11.8% entity / 18.2% number EM)?

Includes per-channel attribution (D8): shuffling each channel independently
shows what each actually contributes, and guards against the decoder simply
copying sparse tokens while ignoring the gist.

Usage: .venv/bin/python scripts/train_decoder_v1.py [--epochs 12] [--smoke]
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

from codec import data as D_, whiten as W                              # noqa: E402
from codec.decoder import (SoftPrefixDecoder, batch_iter,              # noqa: E402
                           build_sparse_tensors, noise_z)
from codec.evals import fidelity as F                                   # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--bs", type=int, default=6)
    ap.add_argument("--grad-accum", type=int, default=5)
    ap.add_argument("--gen-bs", type=int, default=12)
    ap.add_argument("--k-sparse", type=int, default=24)
    ap.add_argument("--sigma-max", type=float, default=0.4)
    ap.add_argument("--lr-proj", type=float, default=1e-3)
    ap.add_argument("--lr-lora", type=float, default=2e-4)
    ap.add_argument("--max-len", type=int, default=64)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    clean = [D_.Proposition(**json.loads(l)) for l in
             (ROOT / "data" / "clean_v0.jsonl").read_text().splitlines() if l.strip()]
    dense = np.load(ROOT / "results" / "dense_v0.npy")
    sparse_rows = json.loads((ROOT / "results" / "sparse_v0.json").read_text())
    assert len(clean) == len(dense) == len(sparse_rows), "artifacts misaligned"
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    Z = W.apply(dense, whitener)

    _, eval_p = D_.split(clean, eval_frac=0.1)
    eval_keys = {p.text for p in eval_p}
    is_eval = np.array([p.text in eval_keys for p in clean])
    Z_tr, Z_ev = Z[~is_eval], Z[is_eval]
    P_tr = [p for p, e in zip(clean, is_eval) if not e]
    P_ev = [p for p, e in zip(clean, is_eval) if e]
    S_tr = [r for r, e in zip(sparse_rows, is_eval) if not e]
    S_ev = [r for r, e in zip(sparse_rows, is_eval) if e]
    print(f"[data] train={len(P_tr)} eval={len(P_ev)} k_sparse={args.k_sparse}")

    dec = SoftPrefixDecoder(k_sparse=args.k_sparse)
    tok = dec.tokenizer
    enc = tok([p.text + tok.eos_token for p in P_tr], padding=True, truncation=True,
              max_length=args.max_len, return_tensors="pt", add_special_tokens=False)
    input_ids, attn = enc["input_ids"], enc["attention_mask"]
    labels = input_ids.masked_fill(attn == 0, -100)
    Zt = torch.from_numpy(Z_tr).float()
    sp_tr = build_sparse_tensors(S_tr, tok, args.k_sparse)
    sp_ev = build_sparse_tensors(S_ev, tok, args.k_sparse)
    print(f"[prefix] dense k={dec.proj.k} + sparse k={args.k_sparse} "
          f"= {dec.n_prefix()} slots")

    opt = torch.optim.AdamW([
        {"params": list(dec.proj.parameters()) + list(dec.sparse_proj.parameters()),
         "lr": args.lr_proj},
        {"params": [p for p in dec.lm.parameters() if p.requires_grad], "lr": args.lr_lora},
    ], weight_decay=0.01)
    n_steps = max(args.epochs * (len(P_tr) // (args.bs * args.grad_accum) + 1), 2)
    if args.smoke:
        n_steps = 20
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=[args.lr_proj, args.lr_lora], total_steps=n_steps,
        pct_start=max(0.05, 3.0 / n_steps))  # keep >=3 warmup steps (smoke runs)

    dec.train(); dec.lm.config.use_cache = False
    step, losses, micro, done = 0, [], 0, False
    for epoch in range(args.epochs):
        if done:
            break
        for idx in batch_iter(len(P_tr), args.bs, shuffle=True, seed=epoch):
            # noise the gist channel only — identities stay exact by design (D3)
            z = noise_z(Zt[idx].to(dec.device),
                        torch.rand(len(idx), device=dec.device) * args.sigma_max)
            out = dec(z, input_ids[idx], attn[idx], labels[idx],
                      sp=tuple(t[idx] for t in sp_tr))
            (out.loss / args.grad_accum).backward()
            losses.append(out.loss.item()); micro += 1
            if micro % args.grad_accum:
                continue
            torch.nn.utils.clip_grad_norm_(
                [p for p in dec.parameters() if p.requires_grad], 1.0)
            opt.step(); sched.step(); opt.zero_grad(set_to_none=True); step += 1
            if step % 50 == 0:
                print(f"[train] step {step}/{n_steps} "
                      f"loss={np.mean(losses[-50 * args.grad_accum:]):.4f}", flush=True)
            if step >= n_steps:
                done = True
                break

    ckpt = ROOT / "checkpoints" / "decoder_v1"
    dec.save(ckpt)
    print(f"[save] {ckpt} (final loss {np.mean(losses[-200:]):.4f})")
    del opt, sched
    torch.cuda.empty_cache()
    dec.lm.config.use_cache = True

    # ---------- evals ----------
    n_ev = min(len(P_ev), 24 if args.smoke else 250)
    Ze, Pe = Z_ev[:n_ev], P_ev[:n_ev]
    spe = tuple(t[:n_ev] for t in sp_ev)
    rng = np.random.default_rng(0)
    perm = rng.permutation(n_ev)
    while (perm == np.arange(n_ev)).any():
        perm = rng.permutation(n_ev)
    sp_shuf = tuple(t[perm] for t in spe)

    conditions = {
        "both_correct":   (Ze, spe),
        "sparse_shuffled": (Ze, sp_shuf),      # gist intact, identities wrong
        "dense_shuffled": (Ze[perm], spe),     # identities intact, gist wrong
        "both_shuffled":  (Ze[perm], sp_shuf),
    }
    results = {}
    for name, (Zc, spc) in conditions.items():
        rec = F.reconstruct(dec, Zc, bs=args.gen_bs, sp=spc)
        results[name] = F.em_rates(rec, Pe)
        r = results[name]
        print(f"[{name:>16}] exact={r['exact_text_rate']:.3f} "
              f"entity_em={r['entity_em']:.3f} number_em={r['number_em']:.3f}")
        if name == "both_correct":
            for o, x in list(zip(Pe, rec))[:5]:
                print(f"   ├─ orig : {o.text}\n   └─ recon: {x}")

    n_sw = min(n_ev, 100)
    sweep = F.robustness_sweep(dec, Ze[:n_sw], Pe[:n_sw],
                               sigmas=[0.0, 0.5, 1.0, 2.0], bs=args.gen_bs,
                               sp=tuple(t[:n_sw] for t in spe))
    for r in sweep:
        r["latent_cos"] = float(1 / np.sqrt(1 + r["sigma"] ** 2))
        print(f"[robust σ={r['sigma']} (cos≈{r['latent_cos']:.2f})] "
              f"entity_em={r['entity_em']:.3f} number_em={r['number_em']:.3f}")

    # compare against v0 (dense-only)
    v0 = json.loads((ROOT / "results" / "decoder_v0_eval.json").read_text())
    b = results["both_correct"]
    print(f"\n[M2 ablation] entity EM {v0['fidelity_sigma0']['entity_em']:.3f} -> "
          f"{b['entity_em']:.3f} | number EM "
          f"{v0['fidelity_sigma0']['number_em']:.3f} -> {b['number_em']:.3f} | "
          f"exact {v0['fidelity_sigma0']['exact_text_rate']:.3f} -> {b['exact_text_rate']:.3f}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "args": vars(args),
           "steps": step, "final_loss": float(np.mean(losses[-200:])),
           "conditions": results, "robustness": sweep,
           "v0_dense_only": v0["fidelity_sigma0"]}
    (ROOT / "results" / "decoder_v1_eval.json").write_text(json.dumps(out, indent=2))
    print("[done] results/decoder_v1_eval.json")


if __name__ == "__main__":
    main()
