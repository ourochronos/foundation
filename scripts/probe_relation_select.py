"""B1 — Relation-selection linear probe (Phase-3 de-risk, 07-phase3-plan.md).

The one capability the trained reasoner must have that nothing has measured:
map a QUESTION latent to a RELATION-OPERATOR choice. If this is linearly
separable, the core can be tiny and 05-reasoner.md's "ultra-wide" clause is
formally retired (its width-for-binding justification is already dead — D3/
D21/D26 moved binding to symbols).

Method: ridge regression to one-hot relation labels over whitened question
gists (world v1: 1,200 single-hop queries across 7 relations + 400 2-hop
questions as an 8th class — the composed question must be distinguishable
from its own first hop for the walk to start correctly). Hash split, and the
D8 positive control: shuffled labels must fall to chance.

Usage: .venv/bin/python scripts/probe_relation_select.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec.structure_channel import hash_test_mask   # noqa: E402


def fit_ridge_onehot(X, y, n_cls, alpha=1.0):
    Y = np.eye(n_cls)[y]
    G = X.T @ X + alpha * np.eye(X.shape[1])
    return np.linalg.solve(G, X.T @ Y)


def main() -> None:
    world = json.loads((ROOT / "data" / "closed_world_v1.json").read_text())
    z = np.load(ROOT / "results" / "closed_world_v1_emb.npz")
    Zq, Zh = z["Zq"], z["Zh"]

    rels = sorted({q["relation"] for q in world["queries"]})
    cls = {r: i for i, r in enumerate(rels)}
    HOP = len(rels)                                   # composed-question class
    X = np.concatenate([Zq, Zh])
    y = np.array([cls[q["relation"]] for q in world["queries"]]
                 + [HOP] * len(Zh))
    texts = [q["text"] for q in world["queries"]] + [h["text"] for h in world["hops"]]
    n_cls = len(rels) + 1

    m = hash_test_mask(texts, frac=0.3)               # 30% test
    Xtr, ytr, Xte, yte = X[~m], y[~m], X[m], y[m]

    W = fit_ridge_onehot(Xtr, ytr, n_cls)
    acc = float((np.argmax(Xte @ W, 1) == yte).mean())

    rng = np.random.default_rng(0)
    ysh = rng.permutation(ytr)
    Wsh = fit_ridge_onehot(Xtr, ysh, n_cls)
    acc_sh = float((np.argmax(Xte @ Wsh, 1) == yte).mean())

    per = {}
    pred = np.argmax(Xte @ W, 1)
    for r, i in list(cls.items()) + [("2hop_composed", HOP)]:
        sel = yte == i
        if sel.any():
            per[r] = float((pred[sel] == i).mean())

    chance = 1.0 / n_cls
    print(f"[B1] relation selection: test acc = {acc:.3f} over {n_cls} classes "
          f"(n_test={len(yte)}) | shuffled-label control = {acc_sh:.3f} "
          f"(chance ~{chance:.3f})")
    for r, a in sorted(per.items(), key=lambda kv: kv[1]):
        print(f"     {r:>18}: {a:.3f}")
    verdict = ("LINEAR — relation choice is type-level; the reasoner core can "
               "be tiny" if acc > 0.95 else
               "not cleanly linear — the core needs capacity for relation "
               "selection")
    print(f"[verdict] {verdict}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "test_acc": acc, "shuffled_control": acc_sh, "chance": chance,
           "per_class": per, "n_test": int(len(yte)), "verdict": verdict}
    (ROOT / "results" / "relation_select_b1.json").write_text(json.dumps(out, indent=2))
    print("[done] results/relation_select_b1.json")


if __name__ == "__main__":
    main()
