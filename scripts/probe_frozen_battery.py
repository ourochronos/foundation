"""A5 + A6a — frozen adversarial battery + identity-channel ROC. SCORE ONCE.

A5: 210 naturally-phrased pairs across 7 construction types from a different
generator/prompt-author, through the SHIPPING channel stack — struct
(pair_scores) and codec-level min(struct, identity). No code changes are
permitted after this runs (07-plan rule); results stand as scored.

A6a: 100 number/entity-REFORMATTING preserving pairs (times, spelled numbers,
aliases, unit conversions) through identity_sim — the false-flag rate that
bounds D23's bidirectional rule on natural text.

Usage: .venv/bin/python scripts/probe_frozen_battery.py
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

from codec import whiten as W                              # noqa: E402
from codec.identity_channel import identity_sim            # noqa: E402
from codec.role_bits import _nlp                           # noqa: E402
from codec.structure_channel import StructureChannel       # noqa: E402


def unit(X):
    return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)


def auc(lo, hi):
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    order = np.concatenate([lo, hi]).argsort(kind="mergesort")
    ranks = np.empty(len(order)); ranks[order] = np.arange(1, len(order) + 1)
    u = ranks[:len(lo)].sum() - len(lo) * (len(lo) + 1) / 2
    return float(1 - u / (len(lo) * len(hi)))


def boot_ci(fn, lo, hi, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    vals = [fn(lo[rng.integers(0, len(lo), len(lo))],
               hi[rng.integers(0, len(hi), len(hi))]) for _ in range(n)]
    return float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))


def main() -> None:
    rows = [json.loads(l) for l in
            (ROOT / "data" / "relations" / "frozen_battery_v0.jsonl")
            .read_text().splitlines() if l.strip()]
    reform = [json.loads(l) for l in
              (ROOT / "data" / "relations" / "reformat_pairs_v0.jsonl")
              .read_text().splitlines() if l.strip()]

    from codec.encode import M3Encoder
    enc, nlp = M3Encoder(), _nlp()
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    ch = StructureChannel.load(ROOT)

    xs, ys = [r["x"] for r in rows], [r["y"] for r in rows]
    dx, _ = enc.encode(xs, sparse=False)
    dy, _ = enc.encode(ys, sparse=False)
    Zx, Zy = unit(W.apply(dx, whitener)), unit(W.apply(dy, whitener))
    Tx, Mx = ch.tokens(xs, enc)
    Ty, My = ch.tokens(ys, enc)
    sc = ch.pair_scores(xs, ys, Zx, Zy, Tx, Mx, Ty, My)
    ids = np.array([identity_sim(x, y, nlp) for x, y in zip(xs, ys)])
    comb = np.minimum(sc["combined"], ids)

    print(f"{'type':>18} {'label':>10}  struct  ident  codec-min")
    by_type = {}
    for i, r in enumerate(rows):
        by_type.setdefault((r["relation"], r["label"]), []).append(i)
    for (rel, lab), idx in sorted(by_type.items()):
        print(f"{rel:>18} {lab:>10}  {sc['combined'][idx].mean():.3f}  "
              f"{ids[idx].mean():.3f}   {comb[idx].mean():.3f}")

    chg = [i for i, r in enumerate(rows) if r["label"] == "changing"]
    pre = [i for i, r in enumerate(rows) if r["label"] == "preserving"]
    a = auc(comb[chg], comb[pre])
    lo, hi = boot_ci(auc, comb[chg], comb[pre])
    print(f"\n[A5 frozen battery] codec-min pair AUC = {a:.3f} "
          f"(95% CI {lo:.3f}–{hi:.3f}; {len(chg)} changing / {len(pre)} preserving)")
    a_s = auc(sc["combined"][chg], sc["combined"][pre])
    print(f"[A5] struct-only AUC = {a_s:.3f} (reference: templated-world 0.942)")

    # ---- A6a: reformatting false-flag rate ----
    rsims = np.array([identity_sim(r["x"], r["y"], nlp) for r in reform])
    ff = float((rsims < 0.999).mean())
    print(f"[A6a reformat ROC] false-flag rate = {ff:.2%} over {len(reform)} "
          f"preserving reformat pairs (mean identity_sim {rsims.mean():.3f})")
    worst = np.argsort(rsims)[:5]
    for i in worst:
        if rsims[i] < 0.999:
            print(f"    flag {rsims[i]:.2f}: {reform[i]['x'][:52]} || "
                  f"{reform[i]['y'][:52]}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "battery_auc_codec": a, "battery_auc_ci": [lo, hi],
           "battery_auc_struct": a_s,
           "per_type": {f"{k[0]}|{k[1]}": {"struct": float(sc['combined'][v].mean()),
                                           "ident": float(ids[v].mean()),
                                           "comb": float(comb[v].mean())}
                        for k, v in by_type.items()},
           "reformat_false_flag_rate": ff,
           "reformat_mean_sim": float(rsims.mean())}
    (ROOT / "results" / "frozen_battery_a5.json").write_text(json.dumps(out, indent=2))
    print("[done] results/frozen_battery_a5.json — FROZEN; no post-hoc changes")


if __name__ == "__main__":
    main()
