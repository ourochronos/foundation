"""Codec-level comparison: min(struct_sim, identity_sim) — D20's caveat closed.

The structure channel owns relations-between-roles; the identity channel owns
literals (D3). This probe scores every transformation pair with both and
combines per-pair by min, reporting the ordering margin and pair-level AUC
against the structure channel alone.

Usage: .venv/bin/python scripts/probe_codec_compare.py
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

from codec.identity_channel import identity_sim               # noqa: E402
from codec.role_bits import _nlp                              # noqa: E402
from codec.structure_channel import (StructureChannel,        # noqa: E402
                                     hash_test_mask)

PRESERVE = ["active_passive", "synonym_swap", "clause_reorder",
            "formality_shift", "paraphrase",
            "cleft_construction", "nominalization", "contraction_expansion"]


def auc(lo, hi):
    order = np.concatenate([lo, hi]).argsort(kind="mergesort")
    ranks = np.empty(len(order)); ranks[order] = np.arange(1, len(order) + 1)
    u = ranks[:len(lo)].sum() - len(lo) * (len(lo) + 1) / 2
    return float(1 - u / (len(lo) * len(hi)))


def main() -> None:
    by_rel = {}
    for f in sorted((ROOT / "data" / "relations").glob("prop_*.jsonl")):
        rows, seen = [], set()
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            o = json.loads(line)
            if o["x"].lower() in seen:
                continue
            seen.add(o["x"].lower())
            rows.append(o)
        if rows:
            by_rel[rows[0]["relation"]] = rows

    ch = StructureChannel.load(ROOT)
    z = np.load(ROOT / "results" / "token_vecs.npz", allow_pickle=True)
    T = torch.from_numpy(z["T"].astype(np.float32))
    M = torch.from_numpy(z["M"])
    tindex = {t: i for i, t in enumerate(z["texts"])}
    zc = np.load(ROOT / "results" / "prop_relation_emb.npz", allow_pickle=True)
    cache_idx = {t: i for i, t in enumerate(zc["xs"])}
    Xw, Yw = zc["X"], zc["Y"]
    nlp = _nlp()

    print(f"{'type':>22} {'class':>9}  struct  ident  combined")
    table, struct_p, comb_p = [], {}, {}
    for rel in sorted(by_rel):
        rows = by_rel[rel]
        m = hash_test_mask([r["x"] for r in rows])
        test = [r for r, t in zip(rows, m) if t]
        xs, ys = [r["x"] for r in test], [r["y"] for r in test]
        ix = np.array([cache_idx[t] for t in xs])
        ti_x = torch.tensor([tindex[t] for t in xs])
        ti_y = torch.tensor([tindex[t] for t in ys])
        sc = ch.pair_scores(xs, ys, Xw[ix], Yw[ix],
                            T[ti_x], M[ti_x], T[ti_y], M[ti_y])
        ids = np.array([identity_sim(x, y, nlp) for x, y in zip(xs, ys)])
        comb = np.minimum(sc["combined"], ids)
        cls = "preserve" if rel in PRESERVE else "changing"
        struct_p[rel], comb_p[rel] = sc["combined"], comb
        table.append({"relation": rel, "class": cls, "n": len(test),
                      "struct": float(sc["combined"].mean()),
                      "identity": float(ids.mean()),
                      "combined": float(comb.mean())})
        print(f"{rel:>22} {cls:>9}  {sc['combined'].mean():.3f}  "
              f"{ids.mean():.3f}   {comb.mean():.3f}")

    def stats(pp):
        chg = np.concatenate([pp[r["relation"]] for r in table
                              if r["class"] == "changing"])
        pre = np.concatenate([pp[r["relation"]] for r in table
                              if r["class"] == "preserve"])
        worst_c = max((r for r in table if r["class"] == "changing"),
                      key=lambda r: float(np.mean(pp[r["relation"]])))
        worst_p = min((r for r in table if r["class"] == "preserve"),
                      key=lambda r: float(np.mean(pp[r["relation"]])))
        return (auc(chg, pre),
                float(np.mean(pp[worst_p["relation"]])) -
                float(np.mean(pp[worst_c["relation"]])),
                worst_c["relation"], worst_p["relation"])

    a0, m0, wc0, wp0 = stats(struct_p)
    a1, m1, wc1, wp1 = stats(comb_p)
    print(f"\n[struct alone ] margin {m0:+.3f} ({wp0} vs {wc0}) | pair-AUC {a0:.3f}")
    print(f"[with identity] margin {m1:+.3f} ({wp1} vs {wc1}) | pair-AUC {a1:.3f}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "table": table,
           "struct_alone": {"margin": m0, "pair_auc": a0,
                            "worst_changing": wc0, "worst_preserving": wp0},
           "with_identity": {"margin": m1, "pair_auc": a1,
                             "worst_changing": wc1, "worst_preserving": wp1}}
    (ROOT / "results" / "codec_compare_v0.json").write_text(json.dumps(out, indent=2))
    print("[done] results/codec_compare_v0.json")


if __name__ == "__main__":
    main()
