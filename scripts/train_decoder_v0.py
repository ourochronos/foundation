"""Train decoder v0 (soft-prefix + LoRA, noise-injected) and run evals #1/#2/#4.

Requires artifacts from scripts/baseline_isotropy.py (clean_v0.jsonl,
dense_v0.npy, whiten_v0.npz — row-aligned).

Usage: .venv/bin/python scripts/train_decoder_v0.py [--smoke] [--epochs 6] [--bs 32]
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

from codec import data as D_, whiten as W                     # noqa: E402
from codec.decoder import SoftPrefixDecoder, batch_iter, noise_z  # noqa: E402
from codec.evals import fidelity as F                          # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=6)
    # bs is the micro-batch: CE logits are bs*seq*vocab*4 bytes (vocab ~152k),
    # which is what OOMs on 16GB. Keep bs small; use grad-accum for effective batch.
    ap.add_argument("--bs", type=int, default=8)
    ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--gen-bs", type=int, default=16)
    ap.add_argument("--sigma-max", type=float, default=0.4)
    ap.add_argument("--lr-proj", type=float, default=1e-3)
    ap.add_argument("--lr-lora", type=float, default=2e-4)
    ap.add_argument("--max-len", type=int, default=64)
    ap.add_argument("--smoke", action="store_true", help="60 steps, tiny eval")
    args = ap.parse_args()

    props, _ = D_.load_dir(ROOT / "data" / "propositions")
    clean = [D_.Proposition(**json.loads(l)) for l in
             (ROOT / "data" / "clean_v0.jsonl").read_text().splitlines() if l.strip()]
    dense = np.load(ROOT / "results" / "dense_v0.npy")
    assert len(clean) == len(dense), "clean_v0.jsonl and dense_v0.npy misaligned — rerun baseline"
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    Z = W.apply(dense, whitener)

    train_p, eval_p = D_.split(clean, eval_frac=0.1)
    eval_keys = {p.text for p in eval_p}
    is_eval = np.array([p.text in eval_keys for p in clean])
    Z_tr, Z_ev = Z[~is_eval], Z[is_eval]
    P_tr = [p for p in clean if p.text not in eval_keys]
    P_ev = [p for p in clean if p.text in eval_keys]
    print(f"[data] train={len(P_tr)} eval={len(P_ev)}")

    dec = SoftPrefixDecoder()
    tok = dec.tokenizer
    enc = tok([p.text + tok.eos_token for p in P_tr], padding=True,
              truncation=True, max_length=args.max_len, return_tensors="pt",
              add_special_tokens=False)
    input_ids, attn = enc["input_ids"], enc["attention_mask"]
    labels = input_ids.masked_fill(attn == 0, -100)
    Zt = torch.from_numpy(Z_tr).float()

    opt = torch.optim.AdamW([
        {"params": dec.proj.parameters(), "lr": args.lr_proj},
        {"params": [p for p in dec.lm.parameters() if p.requires_grad], "lr": args.lr_lora},
    ], weight_decay=0.01)
    n_steps = max(args.epochs * (len(P_tr) // (args.bs * args.grad_accum) + 1), 2)
    if args.smoke:
        n_steps = 20
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=[args.lr_proj, args.lr_lora], total_steps=n_steps, pct_start=0.05)

    dec.train()
    dec.lm.config.use_cache = False
    step, losses, micro = 0, [], 0
    done = False
    for epoch in range(args.epochs):
        if done:
            break
        for idx in batch_iter(len(P_tr), args.bs, shuffle=True, seed=epoch):
            z = noise_z(Zt[idx].to(dec.device),
                        torch.rand(len(idx), device=dec.device) * args.sigma_max)
            out = dec(z, input_ids[idx], attn[idx], labels[idx])
            (out.loss / args.grad_accum).backward()
            losses.append(out.loss.item())
            micro += 1
            if micro % args.grad_accum:
                continue
            torch.nn.utils.clip_grad_norm_(
                [p for p in dec.parameters() if p.requires_grad], 1.0)
            opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
            step += 1
            if step % 50 == 0:
                print(f"[train] step {step}/{n_steps} "
                      f"loss={np.mean(losses[-50 * args.grad_accum:]):.4f}", flush=True)
            if step >= n_steps:
                done = True
                break

    ckpt = ROOT / "checkpoints" / "decoder_v0"
    dec.save(ckpt)
    print(f"[save] {ckpt} (final loss {np.mean(losses[-200:]):.4f})")

    # free training state before eval — the encoder below also wants VRAM
    del opt, sched
    torch.cuda.empty_cache()
    dec.lm.config.use_cache = True

    # --- evals: fidelity at sigma=0, cycle, robustness sweep ---
    n_ev = min(len(P_ev), 24 if args.smoke else 250)
    n_sw = min(len(P_ev), 12 if args.smoke else 100)
    recons = F.reconstruct(dec, Z_ev[:n_ev], bs=args.gen_bs)
    fid = F.em_rates(recons, P_ev[:n_ev])
    print(f"[fidelity σ=0] {fid}")
    for orig, rec in list(zip(P_ev, recons))[:5]:
        print(f"  ├─ orig: {orig.text}\n  └─ recon: {rec}")

    from codec.encode import M3Encoder
    m3 = M3Encoder()
    cyc = F.cycle_cos(m3, whitener, recons, Z_ev[:n_ev])
    print(f"[cycle] {cyc}")

    sweep = F.robustness_sweep(dec, Z_ev[:n_sw], P_ev[:n_sw],
                               sigmas=[0.0, 0.1, 0.2, 0.3, 0.5], bs=args.gen_bs)
    for r in sweep:
        print(f"[robust σ={r['sigma']}] entity_em={r['entity_em']:.3f} "
              f"number_em={r['number_em']:.3f} exact={r['exact_text_rate']:.3f}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "args": vars(args), "steps": step, "final_loss": float(np.mean(losses[-50:])),
           "fidelity_sigma0": fid, "cycle": cyc, "robustness": sweep,
           "n_train": len(P_tr), "n_eval": len(P_ev)}
    (ROOT / "results" / "decoder_v0_eval.json").write_text(json.dumps(out, indent=2))
    print("[done] results/decoder_v0_eval.json")


if __name__ == "__main__":
    main()
