"""Procrustes relational probe (Phase 1.5 gate input, docs/03-latent-algebra.md).

Per relation: fit the optimal orthogonal map R on train pairs (closed form),
test generalization on held-out pairs vs. identity and translation baselines.
If relations act ~rotationally in our whitened space, R should beat both.

Usage: .venv/bin/python scripts/probe_procrustes.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.linalg import orthogonal_procrustes

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec import whiten as W          # noqa: E402
from codec.encode import M3Encoder     # noqa: E402


def _unit(X: np.ndarray) -> np.ndarray:
    return X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)


def main() -> None:
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

    enc = M3Encoder()
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    texts = [p["x"] for ps in by_rel.values() for p in ps] + \
            [p["y"] for ps in by_rel.values() for p in ps]
    dense, _ = enc.encode(texts, sparse=False)
    Zall = _unit(W.apply(dense, whitener))
    n_half = len(texts) // 2
    Xmap = dict(zip(texts[:n_half], Zall[:n_half]))
    Ymap = dict(zip(texts[n_half:], Zall[n_half:]))

    rows = []
    for rel, ps in sorted(by_rel.items()):
        X = np.stack([Xmap[p["x"]] for p in ps])
        Y = np.stack([Ymap[p["y"]] for p in ps])
        is_test = np.array([
            int.from_bytes(hashlib.sha256(p["x"].encode()).digest()[:4], "big") < 0.2 * 2**32
            for p in ps])
        if is_test.sum() < 3 or (~is_test).sum() < 10:
            rows.append({"relation": rel, "skipped": "too few pairs"})
            continue
        Xtr, Ytr, Xte, Yte = X[~is_test], Y[~is_test], X[is_test], Y[is_test]

        R, _ = orthogonal_procrustes(Xtr, Ytr)
        t = (Ytr - Xtr).mean(axis=0)

        def _cos(A, B):
            return float(np.einsum("ij,ij->i", _unit(A), _unit(B)).mean())

        preds = {"rotation": Xte @ R, "translation": Xte + t, "identity": Xte}
        row = {"relation": rel, "n_train": int((~is_test).sum()), "n_test": int(is_test.sum())}
        for name, P in preds.items():
            row[f"cos_{name}"] = _cos(P, Yte)
            # retrieval among ALL this relation's y vectors
            sims = _unit(P) @ _unit(Y).T                     # [n_test, n_all]
            correct = np.where(is_test)[0]
            row[f"top1_{name}"] = float((sims.argmax(axis=1) == correct).mean())
        rows.append(row)
        print(f"[{rel}] cos R/t/id = {row['cos_rotation']:.3f}/{row['cos_translation']:.3f}/"
              f"{row['cos_identity']:.3f}  top1 R/t/id = {row['top1_rotation']:.2f}/"
              f"{row['top1_translation']:.2f}/{row['top1_identity']:.2f} "
              f"(n={row['n_train']}+{row['n_test']})")

    ok = [r for r in rows if "skipped" not in r]
    summary = {k: float(np.mean([r[k] for r in ok]))
               for k in ["cos_rotation", "cos_translation", "cos_identity",
                          "top1_rotation", "top1_translation", "top1_identity"]}
    print(f"[mean] {summary}")
    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "per_relation": rows, "mean": summary}
    (ROOT / "results" / "procrustes_v0.json").write_text(json.dumps(out, indent=2))
    print("[done] results/procrustes_v0.json")


if __name__ == "__main__":
    main()
