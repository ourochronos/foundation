"""Train decoder v2 — full-triple conditioning [gist ; identities ; s-vector].

The codec-v2 decoder run (D3/D10/D20): sparse identity channel with both D10
fixes (per-row weight normalization + learned gain; dense-channel dropout for
gradient pressure) plus the 192-d structure s-vector as a third prefix block.

Evaluation battery (house rules — every channel gets shuffled attribution):
  #1 fidelity σ=0, #2 robustness sweep, #4 cycle — like decoder_v0, PLUS
  ablation: full | shuffled-sparse | shuffled-s | shuffled-dense | zeroed-dense
    (channels shuffled ACROSS eval rows, so marginal distribution is intact
     but per-row information is destroyed — attribution = full − shuffled)
  role fidelity: mean role_sim(orig, recon) for full vs shuffled-s — does the
    decoder actually READ structure from s?

Baseline to beat (dense-only decoder_v0 @16k): entity 0.203 / number 0.336 /
cycle 0.619.

Usage: .venv/bin/python scripts/train_decoder_v2.py [--smoke] [--epochs 12]
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

from codec import data as D_, whiten as W                          # noqa: E402
from codec.decoder import (SoftPrefixDecoder, batch_iter,          # noqa: E402
                           build_sparse_tensors, noise_z)
from codec.evals import fidelity as F                              # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--bs", type=int, default=8)
    ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--gen-bs", type=int, default=16)
    ap.add_argument("--sigma-max", type=float, default=0.4)
    ap.add_argument("--dense-drop", type=float, default=0.25,
                    help="fraction of training rows whose gist prefix is zeroed")
    ap.add_argument("--k-sparse", type=int, default=24)
    ap.add_argument("--sparse-file", default="sparse_v0.json",
                    help="sparse_tagged_v0.json = slot-tagged identity channel")
    ap.add_argument("--max-sub", type=int, default=4,
                    help="subword budget per slot (tagged pairs need ~6)")
    ap.add_argument("--tag", default="v2", help="checkpoint/results suffix")
    ap.add_argument("--k-s", type=int, default=2)
    ap.add_argument("--lr-proj", type=float, default=1e-3)
    ap.add_argument("--lr-lora", type=float, default=2e-4)
    ap.add_argument("--max-len", type=int, default=64)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    clean = [D_.Proposition(**json.loads(l)) for l in
             (ROOT / "data" / "clean_v0.jsonl").read_text().splitlines() if l.strip()]
    dense = np.load(ROOT / "results" / "dense_v0.npy")
    sparse_rows = json.loads((ROOT / "results" / args.sparse_file).read_text())
    S_all = np.load(ROOT / "results" / "s_vecs_v0.npy")
    assert len(clean) == len(dense) == len(sparse_rows) == len(S_all), \
        "artifact misalignment — rerun the cascade + compute_s_vecs"
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    Z = W.apply(dense, whitener)

    _, eval_p = D_.split(clean, eval_frac=0.1)
    eval_keys = {p.text for p in eval_p}
    is_eval = np.array([p.text in eval_keys for p in clean])
    Z_tr, Z_ev = Z[~is_eval], Z[is_eval]
    S_tr = torch.from_numpy(S_all[~is_eval]).float()
    S_ev = torch.from_numpy(S_all[is_eval]).float()
    sp_rows_tr = [r for r, e in zip(sparse_rows, is_eval) if not e]
    sp_rows_ev = [r for r, e in zip(sparse_rows, is_eval) if e]
    P_tr = [p for p in clean if p.text not in eval_keys]
    P_ev = [p for p in clean if p.text in eval_keys]
    print(f"[data] train={len(P_tr)} eval={len(P_ev)} "
          f"| k_sparse={args.k_sparse} k_s={args.k_s} "
          f"dense_drop={args.dense_drop}")

    dec = SoftPrefixDecoder(k_sparse=args.k_sparse, k_s=args.k_s,
                            sparse_fix=True)
    tok = dec.tokenizer
    sp_tr = build_sparse_tensors(sp_rows_tr, tok, args.k_sparse, max_sub=args.max_sub)
    sp_ev = build_sparse_tensors(sp_rows_ev, tok, args.k_sparse, max_sub=args.max_sub)

    enc = tok([p.text + tok.eos_token for p in P_tr], padding=True,
              truncation=True, max_length=args.max_len, return_tensors="pt",
              add_special_tokens=False)
    input_ids, attn = enc["input_ids"], enc["attention_mask"]
    labels = input_ids.masked_fill(attn == 0, -100)
    Zt = torch.from_numpy(Z_tr).float()

    extra_params = list(dec.sparse_proj.parameters()) + list(dec.s_proj.parameters())
    if dec.sparse_gain is not None:
        extra_params.append(dec.sparse_gain)
    opt = torch.optim.AdamW([
        {"params": dec.proj.parameters(), "lr": args.lr_proj},
        {"params": extra_params, "lr": args.lr_proj},
        {"params": [p for p in dec.lm.parameters() if p.requires_grad],
         "lr": args.lr_lora},
    ], weight_decay=0.01)
    n_steps = max(args.epochs * (len(P_tr) // (args.bs * args.grad_accum) + 1), 2)
    if args.smoke:
        n_steps = 20
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=[args.lr_proj, args.lr_proj, args.lr_lora],
        total_steps=n_steps, pct_start=max(0.05, 3.0 / n_steps))

    g = torch.Generator().manual_seed(0)
    dec.train()
    dec.lm.config.use_cache = False
    step, losses, micro, done = 0, [], 0, False
    for epoch in range(args.epochs):
        if done:
            break
        for idx in batch_iter(len(P_tr), args.bs, shuffle=True, seed=epoch):
            z = noise_z(Zt[idx].to(dec.device),
                        torch.rand(len(idx), device=dec.device) * args.sigma_max)
            drop = torch.rand(len(idx), generator=g) < args.dense_drop
            sp_b = tuple(t[idx] for t in sp_tr)
            out = dec(z, input_ids[idx], attn[idx], labels[idx],
                      sp=sp_b, s=S_tr[idx], dense_drop=drop)
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
                gain = (float(dec.sparse_gain.detach().float())
                        if dec.sparse_gain is not None else float("nan"))
                print(f"[train] step {step}/{n_steps} "
                      f"loss={np.mean(losses[-50 * args.grad_accum:]):.4f} "
                      f"gain={gain:.2f}", flush=True)
            if step >= n_steps:
                done = True
                break

    ckpt = ROOT / "checkpoints" / f"decoder_{args.tag}"
    dec.save(ckpt)
    print(f"[save] {ckpt} (final loss {np.mean(losses[-200:]):.4f})")

    del opt, sched
    torch.cuda.empty_cache()
    dec.lm.config.use_cache = True

    # ---------------- evaluation battery ----------------
    n_ev = min(len(P_ev), 24 if args.smoke else 250)
    n_sw = min(len(P_ev), 12 if args.smoke else 100)
    rng = np.random.default_rng(0)
    perm = rng.permutation(n_ev)                    # shared shuffle permutation
    sp_e = tuple(t[:n_ev] for t in sp_ev)
    sp_shuf = tuple(t[:n_ev][perm] for t in sp_ev)
    s_e, s_shuf = S_ev[:n_ev], S_ev[:n_ev][perm]
    Z_e, Z_shuf = Z_ev[:n_ev], Z_ev[:n_ev][perm]

    conds = {
        "full":        dict(Z=Z_e,    sp=sp_e,    s=s_e),
        "shuf_sparse": dict(Z=Z_e,    sp=sp_shuf, s=s_e),
        "shuf_s":      dict(Z=Z_e,    sp=sp_e,    s=s_shuf),
        "shuf_dense":  dict(Z=Z_shuf, sp=sp_e,    s=s_e),
        "zero_dense":  dict(Z=np.zeros_like(Z_e), sp=sp_e, s=s_e),
    }
    recons_by, abl = {}, {}
    for name, c in conds.items():
        recons_by[name] = F.reconstruct(dec, c["Z"], bs=args.gen_bs,
                                        sp=c["sp"], s=c["s"])
        abl[name] = F.em_rates(recons_by[name], P_ev[:n_ev])
        print(f"[ablation {name:>11}] entity={abl[name]['entity_em']:.3f} "
              f"number={abl[name]['number_em']:.3f} "
              f"exact={abl[name]['exact_text_rate']:.3f}")
    for orig, rec in list(zip(P_ev, recons_by["full"]))[:5]:
        print(f"  ├─ orig: {orig.text}\n  └─ recon: {rec}")

    # binding: are numbers attached to the right heads? (D21 residual)
    bpairs = F.binding_pairs(P_ev[:n_ev])
    bind = {name: F.binding_rate(recons_by[name], bpairs)
            for name in ("full", "shuf_sparse")}
    print(f"[binding] full={bind['full']['binding_rate']:.3f} "
          f"(given-present {bind['full']['binding_given_present']:.3f}, "
          f"{bind['full']['n_pairs']} pairs) | "
          f"shuf_sparse={bind['shuf_sparse']['binding_rate']:.3f}")

    # role fidelity: does the decoder read structure from s?
    from codec import role_bits as RB
    def role_fid(recs):
        vals = [RB.role_sim(RB.extract(p.text), RB.extract(r), p.text, r)
                for p, r in zip(P_ev[:n_ev], recs)]
        return float(np.mean(vals))
    rf = {name: role_fid(recons_by[name]) for name in ("full", "shuf_s")}
    print(f"[role-fidelity] full={rf['full']:.3f} shuf_s={rf['shuf_s']:.3f} "
          f"(s-attribution {rf['full'] - rf['shuf_s']:+.3f})")

    from codec.encode import M3Encoder
    m3 = M3Encoder()
    cyc = F.cycle_cos(m3, whitener, recons_by["full"], Z_e)
    print(f"[cycle] {cyc}")
    del m3
    torch.cuda.empty_cache()

    sweep = F.robustness_sweep(dec, Z_ev[:n_sw], P_ev[:n_sw],
                               sigmas=[0.0, 0.1, 0.2, 0.3, 0.5],
                               bs=args.gen_bs,
                               sp=tuple(t[:n_sw] for t in sp_ev),
                               s=S_ev[:n_sw])
    for r in sweep:
        print(f"[robust σ={r['sigma']}] entity_em={r['entity_em']:.3f} "
              f"number_em={r['number_em']:.3f}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "args": vars(args), "steps": step,
           "final_loss": float(np.mean(losses[-50:])),
           "sparse_gain": (float(dec.sparse_gain.detach().float())
                           if dec.sparse_gain is not None else None),
           "sparse_file": args.sparse_file,
           "ablation": abl, "binding": bind, "role_fidelity": rf, "cycle": cyc,
           "robustness": sweep, "n_train": len(P_tr), "n_eval": len(P_ev),
           "baseline_dense_only_16k": {"entity_em": 0.203, "number_em": 0.336,
                                       "cycle_cos_mean": 0.619}}
    (ROOT / "results" / f"decoder_{args.tag}_eval.json").write_text(
        json.dumps(out, indent=2))
    print(f"[done] results/decoder_{args.tag}_eval.json")


if __name__ == "__main__":
    main()
