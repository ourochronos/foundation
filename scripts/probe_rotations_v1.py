"""Relational rotation probe v1 — capacity-aware, with a positive control.

v0 flaw: fitting full O(1024) (~524k params) from ~45 pairs is degenerate — R is
constrained only on the span of the training inputs and is arbitrary on the
complement, where most of a held-out vector's norm lives. Its negative result
could not distinguish "relations aren't rotational" from "the probe can't fit".

v1 fixes that:
  1. POSITIVE CONTROL first — synthetic data where y IS a known rotation of x.
     Any (family, d, n) cell that fails the control is capacity-limited, and its
     real-data result is uninformative. Report the control alongside.
  2. Fit the family D4 actually proposes — block-diagonal (d/2 params) — not
     full O(d).
  3. Sweep dimensionality (PCA) so n_train can exceed the parameter count.
  4. Report parameter counts next to every score.

Usage: .venv/bin/python scripts/probe_rotations_v1.py [--cpu]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec import whiten as W                    # noqa: E402
from codec.evals import rotations as ROT         # noqa: E402

CACHE = ROOT / "results" / "relation_emb_v0.npz"


def load_embeddings(cpu: bool):
    pairs = [json.loads(l) for l in
             (ROOT / "data" / "relations" / "pairs_v0.jsonl").read_text().splitlines()
             if l.strip()]
    by_rel: dict[str, list[dict]] = defaultdict(list)
    seen = set()
    for p in pairs:
        key = (p["relation"], p["x"].lower())
        if key not in seen:
            seen.add(key)
            by_rel[p["relation"]].append(p)

    xs = [p["x"] for ps in by_rel.values() for p in ps]
    ys = [p["y"] for ps in by_rel.values() for p in ps]
    if CACHE.exists():
        z = np.load(CACHE, allow_pickle=True)
        if list(z["xs"]) == xs and list(z["ys"]) == ys:
            print("[cache] reusing relation embeddings")
            return by_rel, z["X"], z["Y"]

    from codec.encode import M3Encoder
    enc = M3Encoder(device="cpu" if cpu else None)
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    dx, _ = enc.encode(xs, sparse=False)
    dy, _ = enc.encode(ys, sparse=False)
    X, Y = ROT.unit(W.apply(dx, whitener)), ROT.unit(W.apply(dy, whitener))
    np.savez(CACHE, X=X, Y=Y, xs=np.array(xs), ys=np.array(ys))
    return by_rel, X, Y


def evaluate(Xtr, Ytr, Xte, Yte, Yall, test_rows) -> dict:
    def cos(A, B):
        return float(np.einsum("ij,ij->i", ROT.unit(A), ROT.unit(B)).mean())

    ang = ROT.fit_block_rotation(Xtr, Ytr)
    R = ROT.fit_full_rotation(Xtr, Ytr)
    t = (Ytr - Xtr).mean(axis=0)
    preds = {"block": ROT.apply_block_rotation(Xte, ang), "full": Xte @ R,
             "translation": Xte + t, "identity": Xte}

    row = {}
    for name, P in preds.items():
        row[f"cos_{name}"] = cos(P, Yte)
        sims = ROT.unit(P) @ ROT.unit(Yall).T
        row[f"top1_{name}"] = float((sims.argmax(axis=1) == test_rows).mean())
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--dims", type=int, nargs="*", default=[1024, 256, 64, 16])
    args = ap.parse_args()

    # ---------- 1. positive control ----------
    print("=== POSITIVE CONTROL (y = known block rotation of x) ===")
    controls = []
    for d in args.dims:
        c = ROT.synthetic_control(d=d, n_train=45, n_test=15, seed=0)
        controls.append(c)
        print(f"[d={d:>5}] block={c['cos_block']:.3f} (params {c['params']['block']}) "
              f"full={c['cos_full']:.3f} (params {c['params']['full']}) "
              f"trans={c['cos_translation']:.3f} id={c['cos_identity']:.3f} "
              f"| angle_mae={c['angle_mae']:.3f} rad")
    print("  ^ a family scoring near identity here CANNOT fit a rotation at this "
          "(d, n=45) — its real-data score below is uninformative.\n")

    # ---------- 2. real relations ----------
    by_rel, X_all, Y_all = load_embeddings(args.cpu)
    offsets, o = {}, 0
    for rel, ps in by_rel.items():
        offsets[rel] = (o, o + len(ps))
        o += len(ps)

    results = {}
    for d in args.dims:
        print(f"=== REAL RELATIONS @ d={d} "
              f"(params: block={d//2}, full={d*(d-1)//2}, trans={d}) ===")
        if d < X_all.shape[1]:
            mu, comps = ROT.pca_basis(np.vstack([X_all, Y_all]), d)
            Xd = ROT.unit((X_all - mu) @ comps.T)
            Yd = ROT.unit((Y_all - mu) @ comps.T)
        else:
            Xd, Yd = X_all, Y_all

        rows = []
        for rel, ps in sorted(by_rel.items()):
            lo, hi = offsets[rel]
            X, Y = Xd[lo:hi], Yd[lo:hi]
            is_test = np.array([
                int.from_bytes(hashlib.sha256(p["x"].encode()).digest()[:4], "big")
                < 0.2 * 2**32 for p in ps])
            if is_test.sum() < 3 or (~is_test).sum() < 10:
                continue
            row = {"relation": rel, "n_train": int((~is_test).sum()),
                   "n_test": int(is_test.sum())}
            row.update(evaluate(X[~is_test], Y[~is_test], X[is_test], Y[is_test],
                                Y, np.where(is_test)[0]))
            rows.append(row)

        mean = {k: float(np.mean([r[k] for r in rows]))
                for k in rows[0] if k.startswith(("cos_", "top1_"))}
        results[str(d)] = {"per_relation": rows, "mean": mean}
        print(f"  cos   block={mean['cos_block']:.3f} full={mean['cos_full']:.3f} "
              f"trans={mean['cos_translation']:.3f} id={mean['cos_identity']:.3f}")
        print(f"  top1  block={mean['top1_block']:.3f} full={mean['top1_full']:.3f} "
              f"trans={mean['top1_translation']:.3f} id={mean['top1_identity']:.3f}\n")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "controls": controls, "by_dim": results}
    (ROOT / "results" / "rotations_v1.json").write_text(json.dumps(out, indent=2))
    print("[done] results/rotations_v1.json")


if __name__ == "__main__":
    main()
