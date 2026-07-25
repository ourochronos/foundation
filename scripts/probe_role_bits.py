"""Structure channel, assembled: valence subspace + pooler s + role bits.

Per transformation type (test pairs): each mechanism alone and the combined
channel  struct_sim = min(amp_cos, s_cos, role_sim)  — any sub-channel that
flags a difference flags the pair. Success = the FULL ordering: all
meaning-changing types low, all meaning-preserving types high.

Assembly lives in codec/structure_channel.py; this script only evaluates.
Defaults are the shipping config (D20): pooler v2 + amp subspace v1.

Requires: results/amp_subspace_v1.npz (scripts/probe_axis_amplify_v1.py
--persist), token_vecs.npz covering all pair texts (train_struct_pooler.py
rebuilds it), prop_relation_emb.npz covering all pairs (probe_prop_rotations.py
rebuilds it).

Usage: .venv/bin/python scripts/probe_role_bits.py
       ... --pooler-tag v1 --subspace amp_subspace_v0.npz --tag v1_rerun
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

from codec.structure_channel import StructureChannel, hash_test_mask   # noqa: E402

PRESERVE = ["active_passive", "synonym_swap", "clause_reorder",
            "formality_shift", "paraphrase",
            "cleft_construction", "nominalization", "contraction_expansion"]
BINDING = ["argument_swap", "causal_reverse"]
# preserving types NOT in this pooler version's training set (transfer readout)
HELD_PRESERVE = {
    "v1": {"formality_shift", "paraphrase"},
    "v2": {"cleft_construction", "nominalization", "contraction_expansion"},
}


def whitener_fp() -> str:
    """Fingerprint of the whitening transform. amp_cos lives in whitened
    coordinates, so results are only comparable across runs that share it."""
    z = np.load(ROOT / "results" / "whiten_v0.npz")
    h = hashlib.sha256()
    for k in sorted(z.files):
        h.update(np.ascontiguousarray(z[k], dtype=np.float64).tobytes())
    return h.hexdigest()[:16]


def auc(lo: np.ndarray, hi: np.ndarray) -> float:
    """P(a changing pair scores below a preserving pair); 0.5 = no signal."""
    order = np.concatenate([lo, hi]).argsort(kind="mergesort")
    ranks = np.empty(len(order)); ranks[order] = np.arange(1, len(order) + 1)
    u = ranks[:len(lo)].sum() - len(lo) * (len(lo) + 1) / 2
    return float(1 - u / (len(lo) * len(hi)))


def load_pairs():
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
    return by_rel


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pooler-tag", default="v2")
    ap.add_argument("--subspace", default="amp_subspace_v1.npz")
    ap.add_argument("--tag", default=None, help="output tag (default: pooler tag)")
    args = ap.parse_args()
    tag = args.tag or args.pooler_tag
    held = HELD_PRESERVE.get(args.pooler_tag, set())

    by_rel = load_pairs()
    n_corpus = sum(1 for l in (ROOT / "data" / "clean_v0.jsonl")
                   .read_text().splitlines() if l.strip())
    print(f"[space] whitener {whitener_fp()} over {n_corpus} propositions")
    ch = StructureChannel.load(ROOT, pooler_tag=args.pooler_tag,
                               subspace=args.subspace)

    z = np.load(ROOT / "results" / "token_vecs.npz", allow_pickle=True)
    T = torch.from_numpy(z["T"].astype(np.float32))
    M = torch.from_numpy(z["M"])
    tindex = {t: i for i, t in enumerate(z["texts"])}

    zc = np.load(ROOT / "results" / "prop_relation_emb.npz", allow_pickle=True)
    cache_idx = {t: i for i, t in enumerate(zc["xs"])}
    Xw, Yw = zc["X"], zc["Y"]

    print(f"{'type':>20} {'class':>13}  role_sim  s_cos  amp_cos  combined")
    table, pair_scores = [], {}
    for rel in sorted(by_rel):
        rows = by_rel[rel]
        m = hash_test_mask([r["x"] for r in rows])
        test = [r for r, t in zip(rows, m) if t]
        xs, ys = [r["x"] for r in test], [r["y"] for r in test]
        ix = np.array([cache_idx[t] for t in xs])       # cache rows x-aligned
        ti_x = torch.tensor([tindex[t] for t in xs])
        ti_y = torch.tensor([tindex[t] for t in ys])
        sc = ch.pair_scores(xs, ys, Xw[ix], Yw[ix],
                            T[ti_x], M[ti_x], T[ti_y], M[ti_y])
        pair_scores[rel] = sc["combined"]
        cls = ("preserve*" if rel in held and rel in PRESERVE else
               "preserve" if rel in PRESERVE else
               "binding" if rel in BINDING else "changing")
        table.append({"relation": rel, "class": cls.rstrip("*"), "n": len(test),
                      "held_out_preserve": rel in held,
                      "role_sim": float(sc["role_sim"].mean()),
                      "s_cos": float(sc["s_cos"].mean()),
                      "amp_cos": float(sc["amp_cos"].mean()),
                      "combined": float(sc["combined"].mean())})
        print(f"{rel:>20} {cls:>13}   {sc['role_sim'].mean():.3f}   "
              f"{sc['s_cos'].mean():.3f}   {sc['amp_cos'].mean():.3f}   "
              f"{sc['combined'].mean():.3f}")

    chg = [r["combined"] for r in table if r["class"] != "preserve"]
    pr = [r["combined"] for r in table if r["class"] == "preserve"]
    worst_change = max((r for r in table if r["class"] != "preserve"),
                       key=lambda r: r["combined"])
    worst_pres = min((r for r in table if r["class"] == "preserve"),
                     key=lambda r: r["combined"])
    margin = worst_pres["combined"] - worst_change["combined"]
    print(f"\n[means] changing={np.mean(chg):.3f} preserving={np.mean(pr):.3f}")
    print(f"[worst-case gap] hardest changing type "
          f"{worst_change['relation']}={worst_change['combined']:.3f} vs "
          f"weakest preserving {worst_pres['relation']}={worst_pres['combined']:.3f} "
          f"-> margin {margin:+.3f}")
    if held:
        hp = [r["combined"] for r in table if r["held_out_preserve"]]
        print(f"[transfer] never-trained preserving types (*): "
              f"combined mean {np.mean(hp):.3f}")

    # pair-level statistics — a type-mean margin of a few points says little
    chg_p = np.concatenate([pair_scores[r["relation"]] for r in table
                            if r["class"] != "preserve"])
    pre_p = np.concatenate([pair_scores[r["relation"]] for r in table
                            if r["class"] == "preserve"])
    pair_auc = auc(chg_p, pre_p)
    thr = float(np.quantile(chg_p, 0.95))
    below = float(np.mean(pre_p < thr))
    print(f"[pair-level] AUC={pair_auc:.3f} over {len(chg_p)} changing / "
          f"{len(pre_p)} preserving pairs | {100 * below:.1f}% of preserving pairs "
          f"fall below the changing-pair 95th percentile ({thr:.3f})")

    ordered = margin > 0
    verdict = ("FULL ORDERING ACHIEVED — every meaning-changing type sits below "
               "every meaning-preserving type" if ordered else
               "ordering not yet complete — see worst-case gap")
    print(f"[verdict] {verdict}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "pooler_tag": args.pooler_tag, "subspace": args.subspace,
           "whitener_fp": whitener_fp(), "n_corpus": n_corpus,
           "table": table, "mean_changing": float(np.mean(chg)),
           "mean_preserving": float(np.mean(pr)),
           "worst_changing": worst_change, "worst_preserving": worst_pres,
           "margin": float(margin), "pair_auc": pair_auc,
           "pair_n": {"changing": len(chg_p), "preserving": len(pre_p)},
           "preserving_below_changing_p95": below, "verdict": verdict}
    (ROOT / "results" / f"structure_channel_{tag}.json").write_text(
        json.dumps(out, indent=2))
    print(f"[done] results/structure_channel_{tag}.json")


if __name__ == "__main__":
    main()
