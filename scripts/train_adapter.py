"""Train the separation adapter (D9) and test whether separation GENERALIZES.

Design: train on a subset of transformation types, hold out others entirely.
  TRAIN   invert : negation, argument_swap, comparative_flip
  TRAIN   preserve: active_passive
  HELD OUT (never seen): quantity_double, causal_reverse, tense_shift, hedge

If held-out inverting transformations also separate, the adapter learned
something about semantic difference. If only trained types separate, it
memorized transformation signatures — a much weaker result.

Guardrail (D2): retrieval geometry must survive. Reported as kNN overlap and
Spearman correlation of pairwise cosines, before vs after.

Usage: .venv/bin/python scripts/train_adapter.py [--cpu]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec import whiten as W                                  # noqa: E402
from codec.adapter import SeparationAdapter, cos, separation_loss   # noqa: E402
from codec.evals import rotations as ROT                        # noqa: E402

CACHE = ROOT / "results" / "prop_relation_emb.npz"

# "narrow" = the original D11 attempt (3 inverting types). "broad" = the breadth
# test: 9 inverting + 3 preserving types trained, the SAME held-out inverting
# types retained so the two runs are directly comparable.
CONFIGS = {
    "narrow": {
        "invert": ["negation", "argument_swap", "comparative_flip"],
        "preserve": ["active_passive"],
    },
    "broad": {
        "invert": ["negation", "argument_swap", "comparative_flip",
                   "quantifier_change", "superlative_flip", "success_failure",
                   "increase_decrease", "approval_rejection", "presence_absence"],
        "preserve": ["active_passive", "synonym_swap", "clause_reorder"],
    },
}
# never trained on, under either config
HELD_OUT_INVERT = ["causal_reverse", "quantity_double", "tense_shift",
                   "date_shift", "location_swap"]
HELD_OUT_PRESERVE = ["formality_shift", "paraphrase"]


def load_rel_embeddings():
    """Reuse the cache written by probe_prop_rotations.py (same pair order)."""
    by_rel, order = {}, []
    for f in sorted((ROOT / "data" / "relations").glob("prop_*.jsonl")):
        rows, seen = [], set()
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                o = json.loads(line)
                x, y = str(o["x"]).strip(), str(o["y"]).strip()
            except (json.JSONDecodeError, KeyError):
                continue
            if not x or not y or x.lower() in seen:
                continue
            seen.add(x.lower())
            rows.append({"x": x, "y": y, "relation": o.get("relation", f.stem)})
        if rows:
            by_rel[rows[0]["relation"]] = rows
            order.append(rows[0]["relation"])
    if not CACHE.exists():
        sys.exit("run scripts/probe_prop_rotations.py first (builds the embedding cache)")
    z = np.load(CACHE, allow_pickle=True)
    X, Y = z["X"], z["Y"]
    spans, o = {}, 0
    for rel in order:
        spans[rel] = (o, o + len(by_rel[rel]))
        o += len(by_rel[rel])
    assert o == len(X), "cache does not match current pair files — delete and re-probe"
    return by_rel, spans, X, Y


def split_mask(rows) -> np.ndarray:
    return np.array([
        int.from_bytes(hashlib.sha256(r["x"].encode()).digest()[:4], "big") < 0.2 * 2**32
        for r in rows])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--steps", type=int, default=1500)
    ap.add_argument("--bs", type=int, default=128)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--w-geom", type=float, default=1.0)
    ap.add_argument("--m-invert", type=float, default=0.5)
    ap.add_argument("--m-preserve", type=float, default=0.9)
    ap.add_argument("--config", choices=list(CONFIGS), default="broad")
    args = ap.parse_args()
    dev = "cpu" if args.cpu or not torch.cuda.is_available() else "cuda"
    TRAIN_INVERT = CONFIGS[args.config]["invert"]
    TRAIN_PRESERVE = CONFIGS[args.config]["preserve"]

    by_rel, spans, X, Y = load_rel_embeddings()
    print(f"[config={args.config}] {len(by_rel)} transformations available")
    print(f"  train-invert ({len(TRAIN_INVERT)}): {TRAIN_INVERT}")
    print(f"  train-preserve ({len(TRAIN_PRESERVE)}): {TRAIN_PRESERVE}")
    print(f"  HELD-OUT invert: {HELD_OUT_INVERT} | HELD-OUT preserve: {HELD_OUT_PRESERVE}")

    tt = lambda a: torch.from_numpy(np.asarray(a, dtype=np.float32)).to(dev)
    tr_x_inv, tr_y_inv, tr_x_pre, tr_y_pre = [], [], [], []
    test_sets = {}
    for rel, rows in by_rel.items():
        lo, hi = spans[rel]
        is_test = split_mask(rows)
        Xr, Yr = X[lo:hi], Y[lo:hi]
        test_sets[rel] = (Xr[is_test], Yr[is_test])
        if rel in TRAIN_INVERT:
            tr_x_inv.append(Xr[~is_test]); tr_y_inv.append(Yr[~is_test])
        elif rel in TRAIN_PRESERVE:
            tr_x_pre.append(Xr[~is_test]); tr_y_pre.append(Yr[~is_test])
    Xi, Yi = tt(np.concatenate(tr_x_inv)), tt(np.concatenate(tr_y_inv))
    Xp, Yp = tt(np.concatenate(tr_x_pre)), tt(np.concatenate(tr_y_pre))
    print(f"[pairs] invert-train={len(Xi)} preserve-train={len(Xp)}")

    # corpus sample for the geometry-preservation term
    dense = np.load(ROOT / "results" / "dense_v0.npy")
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    Zc = tt(W.apply(dense, whitener))
    print(f"[geometry] corpus sample {tuple(Zc.shape)}")

    model = SeparationAdapter(d=X.shape[1]).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    g = torch.Generator(device="cpu").manual_seed(0)

    for step in range(1, args.steps + 1):
        bi = torch.randint(0, len(Xi), (args.bs,), generator=g).to(dev)
        bp = torch.randint(0, len(Xp), (args.bs,), generator=g).to(dev)
        ga = torch.randint(0, len(Zc), (args.bs,), generator=g).to(dev)
        gb = torch.randint(0, len(Zc), (args.bs,), generator=g).to(dev)
        loss, logs = separation_loss(
            model, Xi[bi], Yi[bi], Xp[bp], Yp[bp], Zc[ga], Zc[gb],
            m_invert=args.m_invert, m_preserve=args.m_preserve, w_geom=args.w_geom)
        opt.zero_grad(); loss.backward(); opt.step()
        if step % 300 == 0:
            print(f"[train] {step}/{args.steps} loss={logs['loss']:.4f} "
                  f"inv={logs['cos_invert']:.3f} pre={logs['cos_preserve']:.3f} "
                  f"geom={logs['geom']:.5f}")

    # ---------- eval: transformation magnitude before vs after ----------
    model.eval()
    print("\n=== TRANSFORMATION MAGNITUDE, held-out pairs (lower = better separated) ===")
    print(f"{'transformation':>18}  {'role':>12}  before -> after")
    rows = []
    with torch.no_grad():
        for rel in sorted(by_rel):
            xa, ya = test_sets[rel]
            if len(xa) == 0:
                continue
            b = float(np.einsum("ij,ij->i", ROT.unit(xa), ROT.unit(ya)).mean())
            a = float(cos(model(tt(xa)), model(tt(ya))).mean())
            role = ("train-invert" if rel in TRAIN_INVERT else
                    "train-preserve" if rel in TRAIN_PRESERVE else
                    "HELD-invert" if rel in HELD_OUT_INVERT else
                    "HELD-preserve" if rel in HELD_OUT_PRESERVE else "unused")
            rows.append({"relation": rel, "role": role, "before": b, "after": a,
                         "delta": a - b})
            print(f"{rel:>18}  {role:>12}  {b:.3f} -> {a:.3f}  ({a - b:+.3f})")

    # ---------- guardrail: is retrieval geometry intact? ----------
    with torch.no_grad():
        idx = torch.randperm(len(Zc), generator=g)[:1500].to(dev)
        Zs = Zc[idx]
        Za = model(Zs)
        S0 = (Zs @ Zs.T).cpu().numpy()
        S1 = (Za @ Za.T).cpu().numpy()
    np.fill_diagonal(S0, -np.inf); np.fill_diagonal(S1, -np.inf)
    k = 10
    n0 = np.argpartition(-S0, k, axis=1)[:, :k]
    n1 = np.argpartition(-S1, k, axis=1)[:, :k]
    overlap = float(np.mean([len(set(a) & set(b)) / k for a, b in zip(n0, n1)]))
    iu = np.triu_indices(len(S0), k=1)
    from scipy.stats import spearmanr
    rho = float(spearmanr(S0[iu], S1[iu]).statistic)
    print(f"\n[geometry guardrail] kNN@{k} overlap={overlap:.3f}  "
          f"pairwise-cosine Spearman={rho:.3f}")

    def mean_of(role, key="after"):
        vals = [r[key] for r in rows if r["role"] == role]
        return float(np.mean(vals)) if vals else float("nan")

    mean_tr = mean_of("train-invert")
    mean_ho = mean_of("HELD-invert")
    mean_pre = mean_of("train-preserve")
    mean_hpre = mean_of("HELD-preserve")
    ho_before = mean_of("HELD-invert", "before")
    generalizes = (mean_ho < ho_before - 0.10) and (mean_ho < mean_hpre - 0.10)
    print(f"\n[summary] trained-invert={mean_tr:.3f} | HELD-invert={mean_ho:.3f} "
          f"(was {ho_before:.3f}) | trained-preserve={mean_pre:.3f} | "
          f"HELD-preserve={mean_hpre:.3f}")
    print(f"[verdict] separation "
          f"{'GENERALIZES to unseen transformation types' if generalizes else 'does NOT generalize — memorized trained signatures'}"
          f"; geometry {'preserved' if overlap > 0.7 else 'DAMAGED'}")

    torch.save(model.state_dict(), ROOT / "checkpoints" / f"adapter_{args.config}.pt")
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "args": vars(args),
           "config": args.config, "train_invert": TRAIN_INVERT,
           "train_preserve": TRAIN_PRESERVE, "per_relation": rows,
           "knn_overlap": overlap, "spearman": rho,
           "mean_trained_invert": mean_tr, "mean_heldout_invert": mean_ho,
           "mean_heldout_invert_before": ho_before,
           "mean_preserve": mean_pre, "mean_heldout_preserve": mean_hpre,
           "generalizes": bool(generalizes)}
    (ROOT / "results" / f"adapter_{args.config}.json").write_text(json.dumps(out, indent=2))
    print(f"[done] results/adapter_{args.config}.json")


if __name__ == "__main__":
    main()
