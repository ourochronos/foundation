"""Proposition-altitude transformation probe (D4 option 1).

The lexical probe (probe_rotations_v1.py) tested word-level relations
("France"->"Paris"). But the reasoner transforms *propositions*: negate a claim,
double a quantity, swap arguments, reverse causality. This probe asks whether
those act as rotations — the right altitude for the algebra.

Adds a diagnostic the lexical probe lacked: **transformation magnitude**,
mean cos(x, y). If a semantically decisive transformation (negation, argument
swap) barely moves the latent, that is a codec problem prior to any algebra
question — the reasoner could not tell P from not-P.

Includes the mandatory positive control (D8), matched to each cell's (d, n).

Usage: .venv/bin/python scripts/probe_prop_rotations.py [--cpu]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec import whiten as W                    # noqa: E402
from codec.evals import rotations as ROT         # noqa: E402

CACHE = ROOT / "results" / "prop_relation_emb.npz"


def load_pairs() -> dict[str, list[dict]]:
    by_rel: dict[str, list[dict]] = {}
    for f in sorted((ROOT / "data" / "relations").glob("prop_*.jsonl")):
        rows = []
        seen = set()
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
            rows.append({"relation": o.get("relation", f.stem), "x": x, "y": y})
        if rows:
            by_rel[rows[0]["relation"]] = rows
    return by_rel


def whitener_fp() -> str:
    """Fingerprint of the whitening transform. The cache stores WHITENED
    vectors, so it must invalidate when the whitener is refit — the pair texts
    alone are not a sufficient key (a corpus change refits the whitener while
    leaving every pair text identical, which would silently serve stale
    coordinates to every downstream probe)."""
    z = np.load(ROOT / "results" / "whiten_v0.npz")
    h = hashlib.sha256()
    for k in sorted(z.files):
        h.update(np.ascontiguousarray(z[k], dtype=np.float64).tobytes())
    return h.hexdigest()[:16]


def embed(by_rel, cpu: bool):
    xs = [p["x"] for ps in by_rel.values() for p in ps]
    ys = [p["y"] for ps in by_rel.values() for p in ps]
    fp = whitener_fp()
    if CACHE.exists():
        z = np.load(CACHE, allow_pickle=True)
        cached_fp = str(z["whitener_fp"]) if "whitener_fp" in z.files else None
        if list(z["xs"]) == xs and list(z["ys"]) == ys and cached_fp == fp:
            print(f"[cache] reusing proposition embeddings (whitener {fp})")
            return z["X"], z["Y"]
        why = ("whitener refit" if cached_fp != fp else "pair set changed")
        print(f"[cache] stale ({why}) — re-encoding")
    from codec.encode import M3Encoder
    enc = M3Encoder(device="cpu" if cpu else None)
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    dx, _ = enc.encode(xs, sparse=False)
    dy, _ = enc.encode(ys, sparse=False)
    X, Y = ROT.unit(W.apply(dx, whitener)), ROT.unit(W.apply(dy, whitener))
    np.savez(CACHE, X=X, Y=Y, xs=np.array(xs), ys=np.array(ys),
             whitener_fp=np.array(fp))
    return X, Y


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--dims", type=int, nargs="*", default=[1024, 128, 32])
    args = ap.parse_args()

    by_rel = load_pairs()
    if not by_rel:
        sys.exit("no data/relations/prop_*.jsonl found — generators still running?")
    print(f"[data] {len(by_rel)} transformations: "
          + ", ".join(f"{k}({len(v)})" for k, v in by_rel.items()))

    X_all, Y_all = embed(by_rel, args.cpu)
    offsets, o = {}, 0
    for rel, ps in by_rel.items():
        offsets[rel] = (o, o + len(ps))
        o += len(ps)

    # --- transformation magnitude: how far does each op move the latent? ---
    print("\n=== TRANSFORMATION MAGNITUDE (mean cos(x, y); 1.0 = no movement) ===")
    mags = {}
    for rel, ps in sorted(by_rel.items()):
        lo, hi = offsets[rel]
        c = float(np.einsum("ij,ij->i", X_all[lo:hi], Y_all[lo:hi]).mean())
        mags[rel] = c
        flag = "  <-- barely moves the latent" if c > 0.95 else ""
        print(f"  {rel:>18}: {c:.3f}{flag}")

    n_train_typical = int(0.8 * np.mean([len(v) for v in by_rel.values()]))
    print(f"\n=== POSITIVE CONTROL (n_train≈{n_train_typical}) ===")
    controls = []
    for d in args.dims:
        c = ROT.synthetic_control(d=d, n_train=n_train_typical, n_test=25, seed=0)
        controls.append(c)
        print(f"[d={d:>5}] block={c['cos_block']:.3f} (p={c['params']['block']}) "
              f"full={c['cos_full']:.3f} (p={c['params']['full']}) "
              f"| angle_mae={c['angle_mae']:.3f}")

    results = {}
    for d in args.dims:
        print(f"\n=== PROPOSITION TRANSFORMS @ d={d} "
              f"(params: block={d//2}, full={d*(d-1)//2}) ===")
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
            if is_test.sum() < 5 or (~is_test).sum() < 20:
                continue
            Xtr, Ytr, Xte, Yte = X[~is_test], Y[~is_test], X[is_test], Y[is_test]
            ang = ROT.fit_block_rotation(Xtr, Ytr)
            R = ROT.fit_full_rotation(Xtr, Ytr)
            t = (Ytr - Xtr).mean(axis=0)
            preds = {"block": ROT.apply_block_rotation(Xte, ang), "full": Xte @ R,
                     "translation": Xte + t, "identity": Xte}
            row = {"relation": rel, "n_train": int((~is_test).sum()),
                   "n_test": int(is_test.sum()), "transform_magnitude": mags[rel]}
            correct = np.where(is_test)[0]
            for name, P in preds.items():
                row[f"cos_{name}"] = float(
                    np.einsum("ij,ij->i", ROT.unit(P), ROT.unit(Yte)).mean())
                sims = ROT.unit(P) @ ROT.unit(Y).T
                row[f"top1_{name}"] = float((sims.argmax(axis=1) == correct).mean())
            rows.append(row)
            print(f"  {rel:>18}: cos b/t/id = {row['cos_block']:.3f}/"
                  f"{row['cos_translation']:.3f}/{row['cos_identity']:.3f}  "
                  f"top1 b/t/id = {row['top1_block']:.2f}/"
                  f"{row['top1_translation']:.2f}/{row['top1_identity']:.2f}")

        mean = {k: float(np.mean([r[k] for r in rows]))
                for k in rows[0] if k.startswith(("cos_", "top1_"))}
        results[str(d)] = {"per_relation": rows, "mean": mean}
        print(f"  {'MEAN':>18}: cos b/t/id = {mean['cos_block']:.3f}/"
              f"{mean['cos_translation']:.3f}/{mean['cos_identity']:.3f}  "
              f"top1 b/t/id = {mean['top1_block']:.2f}/"
              f"{mean['top1_translation']:.2f}/{mean['top1_identity']:.2f}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "transform_magnitude": mags, "controls": controls, "by_dim": results}
    (ROOT / "results" / "prop_rotations_v0.json").write_text(json.dumps(out, indent=2))
    print("\n[done] results/prop_rotations_v0.json")


if __name__ == "__main__":
    main()
