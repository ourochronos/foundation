"""Axis amplification v1 — retune the valence metric for its actual job.

v0 (D16) amplified the top-k subspace of meaning-inverting displacements, but
formality_shift — the type that moves BGE-M3's latent most without changing
meaning (D13) — got dragged down with the valence types, and it is the
structure channel's one remaining ordering defect (D18).

Two hypotheses tested here:

1. **Preserve deflation**: project the preserving-displacement subspace out of
   the invert bank before its SVD, so amplification keeps only valence
   directions that preserving rewrites don't move.
       D_inv' = D_inv - (D_inv @ P_pre.T) @ P_pre
2. **Higher gain**: the amplified vector is a COMPARISON-TIME copy — the
   stored gist is never modified (codec/structure_channel.py) — so the kNN
   retrieval guardrail that capped v0 at g=2.0 does not bind on this use.
   For a metric the binding guardrail is non-degeneracy: unrelated
   propositions must stay far below preserving pairs.

Both guardrails are computed and reported either way; selection uses the
metric one, and the retrieval one is reported so an in-place variant can be
chosen later if the amplified vector is ever stored.

House rules (D8): banks fit on TRAIN-split pairs of TRAIN types only;
selection reads trained types only; held-out types (including the three
preserving types generated after v1 shipped) are scored once, after
selection; random-subspace control at the same (k, g).

Usage: .venv/bin/python scripts/probe_axis_amplify_v1.py [--persist]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec import whiten as W                          # noqa: E402
from codec.structure_channel import (hash_test_mask,   # noqa: E402
                                     save_amp_subspace)

TRAIN_INVERT = ["negation", "argument_swap", "comparative_flip", "quantifier_change",
                "superlative_flip", "success_failure", "increase_decrease",
                "approval_rejection", "presence_absence"]
TRAIN_PRESERVE = ["active_passive", "synonym_swap", "clause_reorder",
                  "formality_shift", "paraphrase"]
HELD_INVERT = ["causal_reverse", "quantity_double", "tense_shift", "date_shift",
               "location_swap", "hedge"]
HELD_PRESERVE = ["cleft_construction", "nominalization", "contraction_expansion"]

# the valence types amp is responsible for (binding/substitution types are the
# pooler's and role-bits' jobs — scoring amp against them measures nothing)
TRAIN_VALENCE = [r for r in TRAIN_INVERT if r != "argument_swap"]

GRID = {"k_i": [8, 16, 32], "g_i": [2.0, 3.0, 4.0, 6.0, 8.0],
        "k_def": [0, 4, 16, 32]}
KNN_GUARDRAIL = 0.70        # applies only to in-place (representation) use
RANDOM_P95_MAX = 0.30       # metric non-degeneracy: unrelated pairs stay low


def unit(X):
    return X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)


def load():
    z = np.load(ROOT / "results" / "prop_relation_emb.npz", allow_pickle=True)
    idx_of = {t: i for i, t in enumerate(z["xs"])}
    by_rel, spans = {}, {}
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
            rel = rows[0]["relation"]
            by_rel[rel] = rows
            spans[rel] = [idx_of[r["x"]] for r in rows]
    return by_rel, spans, z["X"], z["Y"]


def make_f(P, g):
    def f(Z):
        if P is None or g == 1.0:
            return unit(Z)
        return unit(Z + (g - 1.0) * (Z @ P.T) @ P)
    return f


def auc(lo, hi):
    order = np.concatenate([lo, hi]).argsort(kind="mergesort")
    ranks = np.empty(len(order)); ranks[order] = np.arange(1, len(order) + 1)
    u = ranks[:len(lo)].sum() - len(lo) * (len(lo) + 1) / 2
    return float(1 - u / (len(lo) * len(hi)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--persist", action="store_true",
                    help="write the selected subspace to results/amp_subspace_v1.npz")
    args = ap.parse_args()

    rng = np.random.default_rng(0)
    by_rel, spans, X, Y = load()

    def sel(rel, split):
        idx = np.array(spans[rel])
        m = hash_test_mask([r["x"] for r in by_rel[rel]])
        return idx[m] if split == "test" else idx[~m]

    def mag(f, rel, split="test"):
        s = sel(rel, split)
        return float(np.einsum("ij,ij->i", f(X[s]), f(Y[s])).mean())

    def pair_cos(f, rels, split="test"):
        return np.concatenate([np.einsum("ij,ij->i", f(X[sel(r, split)]),
                                         f(Y[sel(r, split)])) for r in rels])

    dense = np.load(ROOT / "results" / "dense_v0.npy")
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    Zs = unit(W.apply(dense, whitener))[rng.permutation(len(dense))[:1500]]
    S0 = Zs @ Zs.T
    np.fill_diagonal(S0, -np.inf)
    n0 = np.argpartition(-S0, 10, axis=1)[:, :10]
    iu = np.triu_indices(len(Zs), k=1)
    S0_flat = (Zs @ Zs.T)[iu]

    def geometry(f):
        Za = f(Zs)
        S1 = Za @ Za.T
        np.fill_diagonal(S1, -np.inf)
        n1 = np.argpartition(-S1, 10, axis=1)[:, :10]
        ov = float(np.mean([len(set(a) & set(b)) / 10 for a, b in zip(n0, n1)]))
        return ov, float(spearmanr(S0_flat, (Za @ Za.T)[iu]).statistic)

    # unrelated-pair distribution: the guardrail for metric (not in-place) use
    Zall = unit(W.apply(dense, whitener))
    ia = rng.permutation(len(Zall))[:3000]
    ib = rng.permutation(len(Zall))[:3000]
    ZA, ZB = Zall[ia[ia != ib]], Zall[ib[ia != ib]]

    def random_p95(f):
        c = np.einsum("ij,ij->i", f(ZA), f(ZB))
        return float(np.quantile(c, 0.95)), float(np.median(c))

    def bank(rels):
        return np.concatenate([unit(X[sel(r, "train")] - Y[sel(r, "train")])
                               for r in rels])

    D_inv, D_pre = bank(TRAIN_INVERT), bank(TRAIN_PRESERVE)
    _, _, Vt_p = np.linalg.svd(D_pre, full_matrices=False)
    print(f"[banks] invert={len(D_inv)} preserve={len(D_pre)}")

    subspaces = {}
    for k_def in GRID["k_def"]:
        D = D_inv if not k_def else D_inv - (D_inv @ Vt_p[:k_def].T) @ Vt_p[:k_def]
        _, _, Vt = np.linalg.svd(unit(D), full_matrices=False)
        subspaces[k_def] = Vt

    # ---- selection: TRAIN types only, metric guardrail (held-out untouched) ----
    # Criterion = worst TRAIN-preserving type minus mean TRAIN-valence type.
    # Worst-case, because the channel's failure mode is one preserving type
    # dipping below the changing types — not the average gap v0 maximized.
    results, best = [], None
    for k_def, Vt in subspaces.items():
        for k_i in GRID["k_i"]:
            for g_i in GRID["g_i"]:
                f = make_f(Vt[:k_i], g_i)
                val = float(np.mean([mag(f, r) for r in TRAIN_VALENCE]))
                worst_p = min(mag(f, r) for r in TRAIN_PRESERVE)
                ov, rho = geometry(f)
                p95, p50 = random_p95(f)
                row = {"k_def": k_def, "k_i": k_i, "g_i": g_i,
                       "train_valence": val, "worst_preserve": float(worst_p),
                       "margin": float(worst_p - val),
                       "knn_overlap": ov, "spearman": rho,
                       "random_p95": p95, "random_p50": p50}
                results.append(row)
                if p95 <= RANDOM_P95_MAX and (best is None
                                              or row["margin"] > best["margin"]):
                    best = row
    if best is None:
        best = min(results, key=lambda r: r["random_p95"])
        print("[warn] no config met the non-degeneracy guardrail; least-bad shown")
    print(f"[selected] k_def={best['k_def']} k_i={best['k_i']} g_i={best['g_i']} "
          f"| worst-preserve {best['worst_preserve']:.3f} - valence "
          f"{best['train_valence']:.3f} = margin {best['margin']:+.3f}")
    print(f"[guardrails] unrelated-pair p95={best['random_p95']:.3f} "
          f"(cap {RANDOM_P95_MAX}) | in-place kNN@10={best['knn_overlap']:.3f} "
          f"(informational: the gist is not modified by this channel)")

    P = subspaces[best["k_def"]][:best["k_i"]]
    fb, ident = make_f(P, best["g_i"]), make_f(None, 1.0)
    v0 = json.loads((ROOT / "results" / "axis_amplify_v0.json").read_text())
    v0_by_type = {r["relation"]: r["after"] for r in v0["per_type"]}

    print(f"\n{'type':>22} {'role':>14}   raw -> v0    -> v1")
    table = []
    for rel in sorted(by_rel):
        role = ("train-invert" if rel in TRAIN_INVERT else
                "train-preserve" if rel in TRAIN_PRESERVE else
                "HELD-invert" if rel in HELD_INVERT else
                "HELD-preserve" if rel in HELD_PRESERVE else "unused")
        b, a = mag(ident, rel), mag(fb, rel)
        old = v0_by_type.get(rel)
        table.append({"relation": rel, "role": role, "raw": b,
                      "v0": old, "v1": a})
        print(f"{rel:>22} {role:>14}  {b:.3f} -> "
              f"{'  n/a' if old is None else f'{old:.3f}'} -> {a:.3f}")

    inv_all = TRAIN_INVERT + HELD_INVERT
    pre_all = TRAIN_PRESERVE + HELD_PRESERVE
    auc_b = auc(pair_cos(ident, inv_all), pair_cos(ident, pre_all))
    auc_a = auc(pair_cos(fb, inv_all), pair_cos(fb, pre_all))
    ho_i = float(np.mean([mag(fb, r) for r in HELD_INVERT]))
    ho_p = float(np.mean([mag(fb, r) for r in HELD_PRESERVE]))

    Q, _ = np.linalg.qr(rng.standard_normal((X.shape[1], best["k_i"])))
    fr = make_f(Q.T, best["g_i"])
    rand_i = float(np.mean([mag(fr, r) for r in TRAIN_INVERT]))
    rand_p = float(np.mean([mag(fr, r) for r in TRAIN_PRESERVE]))

    ov, rho = geometry(fb)
    p95, p50 = random_p95(fb)
    print(f"\n[held-out] invert {ho_i:.3f} | preserve {ho_p:.3f}")
    print(f"[random-subspace control] invert {rand_i:.3f} preserve {rand_p:.3f} "
          f"(separation {rand_p - rand_i:+.3f} — should be ~0)")
    print(f"[unrelated pairs] median {p50:.3f} p95 {p95:.3f}")
    print(f"[ordering AUC] raw {auc_b:.3f} -> v0 {v0['auc_after']:.3f} -> v1 {auc_a:.3f}")
    print(f"[in-place geometry] knn@10={ov:.3f} (v0 {v0['knn_overlap']:.3f}) "
          f"spearman={rho:.3f} (v0 {v0['spearman']:.3f})")

    worst_pres = min((r for r in table if "preserve" in r["role"]),
                     key=lambda r: r["v1"])
    worst_chg = max((r for r in table if "invert" in r["role"]),
                    key=lambda r: r["v1"])
    print(f"[amp-alone worst case] weakest preserving {worst_pres['relation']}="
          f"{worst_pres['v1']:.3f} vs hardest changing {worst_chg['relation']}="
          f"{worst_chg['v1']:.3f} -> margin "
          f"{worst_pres['v1'] - worst_chg['v1']:+.3f}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "grid": results, "selected": best, "per_type": table,
           "heldout_invert": ho_i, "heldout_preserve": ho_p,
           "random_control": {"invert": rand_i, "preserve": rand_p},
           "unrelated_pairs": {"median": p50, "p95": p95},
           "auc_raw": auc_b, "auc_v0": v0["auc_after"], "auc_v1": auc_a,
           "knn_overlap": ov, "spearman": rho,
           "splits": {"train_invert": TRAIN_INVERT, "train_preserve": TRAIN_PRESERVE,
                      "held_invert": HELD_INVERT, "held_preserve": HELD_PRESERVE}}
    (ROOT / "results" / "axis_amplify_v1.json").write_text(json.dumps(out, indent=2))
    print("[done] results/axis_amplify_v1.json")

    if args.persist:
        save_amp_subspace(ROOT / "results" / "amp_subspace_v1.npz", P,
                          best["g_i"], TRAIN_INVERT)
        print(f"[persist] results/amp_subspace_v1.npz  P{P.shape} g={best['g_i']}")


if __name__ == "__main__":
    main()
