"""A8 — equal-bit control: identities injected into the DENSE channel.

The codec-paper ablation reviewers will demand: is the symbolic channel's win
architecture (channel separation) or information (identities easy)? Control:
same identity strings, hash-embedded and CONCATENATED into the gist
(z' = unit([z ; h]), 2048-d, no sparse slots, no s), decoder otherwise
identical. If v2e ~= v2t, the win was information; if v2e << v2t (esp. under
noise — h now rides the noised channel), channel separation is load-bearing.

Usage: .venv/bin/python scripts/train_decoder_v2e.py [--epochs 12]
"""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, torch
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from codec import data as D_, whiten as W
from codec.decoder import SoftPrefixDecoder, batch_iter, noise_z
from codec.evals import fidelity as F

def unit(X): return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)

def hash_embed(rows, dim=1024, seed=13):
    rng = np.random.default_rng(seed)
    cache = {}
    out = np.zeros((len(rows), dim), dtype=np.float32)
    for i, r in enumerate(rows):
        for tok in r["tokens"]:
            if tok not in cache:
                g = np.random.default_rng(abs(hash((seed, tok))) % 2**32)
                cache[tok] = g.standard_normal(dim).astype(np.float32)
            out[i] += cache[tok]
    return unit(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--bs", type=int, default=8)
    ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--gen-bs", type=int, default=16)
    ap.add_argument("--sigma-max", type=float, default=0.4)
    ap.add_argument("--max-len", type=int, default=64)
    args = ap.parse_args()

    clean = [D_.Proposition(**json.loads(l)) for l in
             (ROOT / "data" / "clean_v0.jsonl").read_text().splitlines() if l.strip()]
    Z = W.apply(np.load(ROOT / "results" / "dense_v0.npy"),
                W.load(str(ROOT / "results" / "whiten_v0.npz")))
    sparse_rows = json.loads((ROOT / "results" / "sparse_tagged_v0.json").read_text())
    H = hash_embed(sparse_rows)
    ZH = unit(np.concatenate([unit(Z), H], axis=1))
    _, eval_p = D_.split(clean, eval_frac=0.1)
    ek = {p.text for p in eval_p}
    is_ev = np.array([p.text in ek for p in clean])
    Ztr, Zev = ZH[~is_ev], ZH[is_ev]
    P_tr = [p for p in clean if p.text not in ek]
    P_ev = [p for p in clean if p.text in ek]
    print(f"[data] train={len(P_tr)} eval={len(P_ev)} z_dim=2048", flush=True)

    dec = SoftPrefixDecoder(z_dim=2048)
    tok = dec.tokenizer
    enc = tok([p.text + tok.eos_token for p in P_tr], padding=True, truncation=True,
              max_length=args.max_len, return_tensors="pt", add_special_tokens=False)
    ids, attn = enc["input_ids"], enc["attention_mask"]
    labels = ids.masked_fill(attn == 0, -100)
    Zt = torch.from_numpy(Ztr).float()
    opt = torch.optim.AdamW([
        {"params": dec.proj.parameters(), "lr": 1e-3},
        {"params": [p for p in dec.lm.parameters() if p.requires_grad], "lr": 2e-4},
    ], weight_decay=0.01)
    n_steps = max(args.epochs * (len(P_tr) // (args.bs * args.grad_accum) + 1), 2)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=[1e-3, 2e-4],
        total_steps=n_steps, pct_start=max(0.05, 3.0 / n_steps))
    dec.train(); dec.lm.config.use_cache = False
    step = micro = 0; losses = []; done = False
    for ep in range(args.epochs):
        if done: break
        for idx in batch_iter(len(P_tr), args.bs, shuffle=True, seed=ep):
            z = noise_z(Zt[idx].to(dec.device),
                        torch.rand(len(idx), device=dec.device) * args.sigma_max)
            out = dec(z, ids[idx], attn[idx], labels[idx])
            (out.loss / args.grad_accum).backward()
            losses.append(out.loss.item()); micro += 1
            if micro % args.grad_accum: continue
            torch.nn.utils.clip_grad_norm_([p for p in dec.parameters() if p.requires_grad], 1.0)
            opt.step(); sched.step(); opt.zero_grad(set_to_none=True); step += 1
            if step % 200 == 0:
                print(f"[train] {step}/{n_steps} loss={np.mean(losses[-800:]):.4f}", flush=True)
            if step >= n_steps: done = True; break
    dec.save(ROOT / "checkpoints" / "decoder_v2e")
    print(f"[save] final loss {np.mean(losses[-200:]):.4f}")
    del opt, sched; torch.cuda.empty_cache(); dec.lm.config.use_cache = True
    n_ev = min(len(P_ev), 250)
    bp = F.binding_pairs(P_ev[:n_ev])
    rows = []
    for sg in (0.0, 0.5, 0.8):
        rec = F.reconstruct(dec, Zev[:n_ev], bs=args.gen_bs, sigma=sg)
        em = F.em_rates(rec, P_ev[:n_ev]); b = F.binding_rate(rec, bp)
        rows.append({"sigma": sg, "entity_em": em["entity_em"],
                     "number_em": em["number_em"], "binding": b["binding_rate"]})
        print(f"[v2e σ={sg}] entity={em['entity_em']:.3f} number={em['number_em']:.3f} "
              f"binding={b['binding_rate']:.3f}", flush=True)
    (ROOT / "results" / "decoder_v2e_eval.json").write_text(json.dumps(
        {"generated_at": datetime.now(timezone.utc).isoformat(), "rows": rows,
         "reference_v2t": {"entity": 0.462, "number": 0.720, "binding": 0.617,
                           "number_at_0.5": 0.725}}, indent=2))
    print("[done] results/decoder_v2e_eval.json")

if __name__ == "__main__":
    main()
