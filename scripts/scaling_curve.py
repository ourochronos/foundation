"""Data-scaling curve (D10): does eval fidelity rise with training-set size?

If the codec is memorization-bound rather than information-bound, eval EM should
climb with more training propositions while the train-eval gap narrows.

Compute is held FIXED across points (same step count, same effective batch), so
the curve isolates data diversity rather than training length. Every point is
scored on the SAME held-out eval set.

Usage: .venv/bin/python scripts/scaling_curve.py [--steps 700]
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

from codec import data as D_, whiten as W                        # noqa: E402
from codec.decoder import SoftPrefixDecoder, batch_iter, noise_z  # noqa: E402
from codec.evals import fidelity as F                             # noqa: E402


def train_one(Z_tr, P_tr, steps, bs, accum, sigma_max, max_len, seed):
    dec = SoftPrefixDecoder()
    tok = dec.tokenizer
    enc = tok([p.text + tok.eos_token for p in P_tr], padding=True, truncation=True,
              max_length=max_len, return_tensors="pt", add_special_tokens=False)
    ids, attn = enc["input_ids"], enc["attention_mask"]
    labels = ids.masked_fill(attn == 0, -100)
    Zt = torch.from_numpy(Z_tr).float()

    opt = torch.optim.AdamW([
        {"params": dec.proj.parameters(), "lr": 1e-3},
        {"params": [p for p in dec.lm.parameters() if p.requires_grad], "lr": 2e-4},
    ], weight_decay=0.01)
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=[1e-3, 2e-4], total_steps=steps, pct_start=max(0.05, 3.0 / steps))

    dec.train(); dec.lm.config.use_cache = False
    step, micro, losses, epoch = 0, 0, [], 0
    while step < steps:
        for idx in batch_iter(len(P_tr), bs, shuffle=True, seed=seed + epoch):
            z = noise_z(Zt[idx].to(dec.device),
                        torch.rand(len(idx), device=dec.device) * sigma_max)
            out = dec(z, ids[idx], attn[idx], labels[idx])
            (out.loss / accum).backward()
            losses.append(out.loss.item()); micro += 1
            if micro % accum:
                continue
            torch.nn.utils.clip_grad_norm_(
                [p for p in dec.parameters() if p.requires_grad], 1.0)
            opt.step(); sched.step(); opt.zero_grad(set_to_none=True); step += 1
            if step >= steps:
                break
        epoch += 1
    del opt, sched
    torch.cuda.empty_cache()
    dec.lm.config.use_cache = True
    return dec, float(np.mean(losses[-200:]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=700)
    ap.add_argument("--bs", type=int, default=8)
    ap.add_argument("--accum", type=int, default=4)
    ap.add_argument("--fractions", type=float, nargs="*",
                    default=[0.125, 0.25, 0.5, 1.0])
    ap.add_argument("--n-eval", type=int, default=150)
    ap.add_argument("--sigma-max", type=float, default=0.4)
    ap.add_argument("--max-len", type=int, default=64)
    args = ap.parse_args()

    clean = [D_.Proposition(**json.loads(l)) for l in
             (ROOT / "data" / "clean_v0.jsonl").read_text().splitlines() if l.strip()]
    dense = np.load(ROOT / "results" / "dense_v0.npy")
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    Z = W.apply(dense, whitener)

    _, eval_p = D_.split(clean, eval_frac=0.1)
    eval_keys = {p.text for p in eval_p}
    is_eval = np.array([p.text in eval_keys for p in clean])
    Z_tr_all = Z[~is_eval]
    P_tr_all = [p for p, e in zip(clean, is_eval) if not e]
    Z_ev = Z[is_eval][:args.n_eval]
    P_ev = [p for p, e in zip(clean, is_eval) if e][:args.n_eval]
    print(f"[data] pool={len(P_tr_all)} fixed-eval={len(P_ev)} "
          f"| compute held fixed at {args.steps} steps/point")

    rng = np.random.default_rng(0)
    order = rng.permutation(len(P_tr_all))
    rows = []
    for frac in args.fractions:
        n = max(int(frac * len(P_tr_all)), 32)
        sel = order[:n]
        Ztr, Ptr = Z_tr_all[sel], [P_tr_all[i] for i in sel]
        print(f"\n=== fraction {frac} -> n_train={n} ===")
        dec, loss = train_one(Ztr, Ptr, args.steps, args.bs, args.accum,
                              args.sigma_max, args.max_len, seed=int(frac * 1000))
        rec_ev = F.reconstruct(dec, Z_ev, bs=16)
        ev = F.em_rates(rec_ev, P_ev)
        n_tr_probe = min(len(Ptr), 100)
        rec_tr = F.reconstruct(dec, Ztr[:n_tr_probe], bs=16)
        tr = F.em_rates(rec_tr, Ptr[:n_tr_probe])
        row = {"fraction": frac, "n_train": n, "final_loss": loss,
               "eval": ev, "train": tr,
               "gap_entity": tr["entity_em"] - ev["entity_em"]}
        rows.append(row)
        print(f"[frac {frac}] loss={loss:.4f} | EVAL entity={ev['entity_em']:.3f} "
              f"number={ev['number_em']:.3f} | TRAIN entity={tr['entity_em']:.3f} "
              f"| gap={row['gap_entity']:+.3f}")
        del dec
        torch.cuda.empty_cache()

    print("\n=== SCALING CURVE (fixed compute) ===")
    print(f"{'n_train':>8} {'eval_entity':>12} {'eval_number':>12} "
          f"{'train_entity':>13} {'gap':>7}")
    for r in rows:
        print(f"{r['n_train']:>8} {r['eval']['entity_em']:>12.3f} "
              f"{r['eval']['number_em']:>12.3f} {r['train']['entity_em']:>13.3f} "
              f"{r['gap_entity']:>+7.3f}")

    first, last = rows[0]["eval"]["entity_em"], rows[-1]["eval"]["entity_em"]
    trend = "RISING — more data helps, consistent with D10" if last > first + 0.02 \
        else "FLAT — more data alone does not help; revisit D10"
    print(f"\n[verdict] eval entity EM {first:.3f} -> {last:.3f}: {trend}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "args": vars(args),
           "curve": rows, "verdict": trend}
    (ROOT / "results" / "scaling_curve_v0.json").write_text(json.dumps(out, indent=2))
    print("[done] results/scaling_curve_v0.json")


if __name__ == "__main__":
    main()
