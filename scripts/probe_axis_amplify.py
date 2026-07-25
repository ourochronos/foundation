"""Axis amplification (D14 build option a) — closed-form spectral rebalancing.

Instead of a trained adapter (whose hinge objective got satisfied by lexical
shortcuts, D11/D12), build a LINEAR map from measured statistics only:

    f(z) = normalize( z + (g_i - 1) P_inv z + (g_p - 1) P_pre z )

  P_inv — projector onto the top-k subspace of unit-normalized displacement
          vectors (x - y) from TRAINED meaning-inverting types
  P_pre — same for trained meaning-preserving types (damped: g_p <= 1)

No gradient descent -> nothing can learn per-type detectors; whatever
generalization appears comes from genuine shared structure in the subspaces.

Controls (D8): random-subspace amplification at the same (k, g); model
selection touches ONLY trained types' test pairs + the geometry guardrail —
held-out types are scored once, after selection.

Usage: .venv/bin/python scripts/probe_axis_amplify.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec import whiten as W    # noqa: E402

TRAIN_INVERT = ["negation", "argument_swap", "comparative_flip", "quantifier_change",
                "superlative_flip", "success_failure", "increase_decrease",
                "approval_rejection", "presence_absence"]
TRAIN_PRESERVE = ["active_passive", "synonym_swap", "clause_reorder"]
HELD_INVERT = ["causal_reverse", "quantity_double", "tense_shift", "date_shift",
               "location_swap"]
HELD_PRESERVE = ["formality_shift", "paraphrase"]

GRID = {"k_i": [4, 16, 64], "g_i": [2.0, 4.0, 8.0],
        "k_p": [0, 16], "g_p": [0.33]}
GUARDRAIL = 0.70


def unit(X):
    return X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)


def load():
    z = np.load(ROOT / "results" / "prop_relation_emb.npz", allow_pickle=True)
    xs = list(z["xs"])
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
            spans[rel] = [xs.index(r["x"]) for r in rows]
    return by_rel, spans, z["X"], z["Y"]


def test_mask(rows):
    return np.array([int.from_bytes(hashlib.sha256(r["x"].encode()).digest()[:4],
                                    "big") < 0.2 * 2**32 for r in rows])


def make_f(P_inv, g_i, P_pre, g_p):
    def f(Z):
        out = Z.copy()
        if P_inv is not None and g_i != 1.0:
            out = out + (g_i - 1.0) * (Z @ P_inv.T) @ P_inv
        if P_pre is not None and g_p != 1.0:
            out = out + (g_p - 1.0) * (Z @ P_pre.T) @ P_pre
        return unit(out)
    return f


def mags_after(f, by_rel, spans, X, Y, rels, split):
    out = {}
    for rel in rels:
        idx = np.array(spans[rel])
        m = test_mask(by_rel[rel])
        sel = idx[m] if split == "test" else idx[~m]
        out[rel] = float(np.einsum("ij,ij->i", f(X[sel]), f(Y[sel])).mean())
    return out


def auc(lo, hi):
    order = np.concatenate([lo, hi]).argsort(kind="mergesort")
    ranks = np.empty(len(order)); ranks[order] = np.arange(1, len(order) + 1)
    u = ranks[: len(lo)].sum() - len(lo) * (len(lo) + 1) / 2
    return float(1 - u / (len(lo) * len(hi)))


def ordering_auc(f, by_rel, spans, X, Y):
    inv, pre = [], []
    for rel in TRAIN_INVERT + HELD_INVERT:
        idx = np.array(spans[rel]); m = test_mask(by_rel[rel])
        inv.append(np.einsum("ij,ij->i", f(X[idx[m]]), f(Y[idx[m]])))
    for rel in TRAIN_PRESERVE + HELD_PRESERVE:
        idx = np.array(spans[rel]); m = test_mask(by_rel[rel])
        pre.append(np.einsum("ij,ij->i", f(X[idx[m]]), f(Y[idx[m]])))
    return auc(np.concatenate(inv), np.concatenate(pre))


def main() -> None:
    rng = np.random.default_rng(0)
    by_rel, spans, X, Y = load()
    dense = np.load(ROOT / "results" / "dense_v0.npy")
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    Zc = unit(W.apply(dense, whitener))
    sub = rng.permutation(len(Zc))[:1500]
    Zs = Zc[sub]
    S0 = Zs @ Zs.T
    np.fill_diagonal(S0, -np.inf)
    k_nn = 10
    n0 = np.argpartition(-S0, k_nn, axis=1)[:, :k_nn]
    iu = np.triu_indices(len(Zs), k=1)
    S0_flat = (Zs @ Zs.T)[iu]

    def geometry(f):
        Za = f(Zs)
        S1 = Za @ Za.T
        np.fill_diagonal(S1, -np.inf)
        n1 = np.argpartition(-S1, k_nn, axis=1)[:, :k_nn]
        ov = float(np.mean([len(set(a) & set(b)) / k_nn for a, b in zip(n0, n1)]))
        rho = float(spearmanr(S0_flat, (Za @ Za.T)[iu]).statistic)
        return ov, rho

    # displacement banks from TRAIN-split pairs of TRAINED types only
    def bank(rels):
        ds = []
        for rel in rels:
            idx = np.array(spans[rel]); m = test_mask(by_rel[rel])
            d = X[idx[~m]] - Y[idx[~m]]
            ds.append(unit(d))
        return np.concatenate(ds)

    D_inv, D_pre = bank(TRAIN_INVERT), bank(TRAIN_PRESERVE)
    print(f"[banks] invert displacements={len(D_inv)} preserve={len(D_pre)}")
    _, _, Vt_i = np.linalg.svd(D_inv, full_matrices=False)
    _, _, Vt_p = np.linalg.svd(D_pre, full_matrices=False)

    # ---------- grid search, selection on TRAIN types' test pairs only ----------
    results, best = [], None
    for k_i in GRID["k_i"]:
        for g_i in GRID["g_i"]:
            for k_p in GRID["k_p"]:
                for g_p in (GRID["g_p"] if k_p else [1.0]):
                    f = make_f(Vt_i[:k_i], g_i, Vt_p[:k_p] if k_p else None, g_p)
                    tr_i = np.mean(list(mags_after(
                        f, by_rel, spans, X, Y, TRAIN_INVERT, "test").values()))
                    tr_p = np.mean(list(mags_after(
                        f, by_rel, spans, X, Y, TRAIN_PRESERVE, "test").values()))
                    ov, rho = geometry(f)
                    row = {"k_i": k_i, "g_i": g_i, "k_p": k_p, "g_p": g_p,
                           "train_invert": float(tr_i), "train_preserve": float(tr_p),
                           "sep": float(tr_p - tr_i), "knn_overlap": ov, "spearman": rho}
                    results.append(row)
                    if ov >= GUARDRAIL and (best is None or row["sep"] > best["sep"]):
                        best = row
    if best is None:
        best = max(results, key=lambda r: r["knn_overlap"])
        print("[warn] no config met the geometry guardrail; reporting least-bad")
    print(f"[selected] k_i={best['k_i']} g_i={best['g_i']} k_p={best['k_p']} "
          f"g_p={best['g_p']} | train sep={best['sep']:.3f} "
          f"knn={best['knn_overlap']:.3f}")

    # ---------- held-out scoring, once, for the selected config ----------
    fb = make_f(Vt_i[:best["k_i"]], best["g_i"],
                Vt_p[:best["k_p"]] if best["k_p"] else None, best["g_p"])
    ident = make_f(None, 1.0, None, 1.0)

    print(f"\n{'type':>18} {'role':>14}  before -> after")
    table = []
    for rel in sorted(by_rel):
        role = ("train-invert" if rel in TRAIN_INVERT else
                "train-preserve" if rel in TRAIN_PRESERVE else
                "HELD-invert" if rel in HELD_INVERT else
                "HELD-preserve" if rel in HELD_PRESERVE else "unused")
        b = mags_after(ident, by_rel, spans, X, Y, [rel], "test")[rel]
        a = mags_after(fb, by_rel, spans, X, Y, [rel], "test")[rel]
        table.append({"relation": rel, "role": role, "before": b, "after": a})
        print(f"{rel:>18} {role:>14}  {b:.3f} -> {a:.3f}  ({a - b:+.3f})")

    def mean_role(role, key):
        v = [r[key] for r in table if r["role"] == role]
        return float(np.mean(v)) if v else float("nan")

    ho_i_b, ho_i_a = mean_role("HELD-invert", "before"), mean_role("HELD-invert", "after")
    ho_p_a = mean_role("HELD-preserve", "after")
    auc_b = ordering_auc(ident, by_rel, spans, X, Y)
    auc_a = ordering_auc(fb, by_rel, spans, X, Y)

    # random-subspace control at the same (k, g)
    Q, _ = np.linalg.qr(rng.standard_normal((X.shape[1], best["k_i"])))
    fr = make_f(Q.T[:best["k_i"]], best["g_i"], None, 1.0)
    ho_i_rand = np.mean(list(mags_after(
        fr, by_rel, spans, X, Y, HELD_INVERT, "test").values()))
    tr_i_rand = np.mean(list(mags_after(
        fr, by_rel, spans, X, Y, TRAIN_INVERT, "test").values()))

    ov, rho = geometry(fb)
    print(f"\n[held-out] invert {ho_i_b:.3f} -> {ho_i_a:.3f} | preserve after "
          f"{ho_p_a:.3f} | random-subspace control: trained {tr_i_rand:.3f}, "
          f"held {ho_i_rand:.3f}")
    print(f"[ordering AUC] {auc_b:.3f} -> {auc_a:.3f}")
    print(f"[geometry] knn@10={ov:.3f} spearman={rho:.3f}")

    generalizes = (ho_i_a < ho_i_b - 0.10) and (ho_i_a < ho_p_a - 0.10)
    verdict = ("GENERALIZES — shared linear structure across transformation types"
               if generalizes else
               "does not generalize to held-out types — shared-subspace hypothesis "
               "not supported; proceed to token-level pooler (D14 option b)")
    print(f"[verdict] {verdict}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "grid": results, "selected": best, "per_type": table,
           "heldout_invert_before": ho_i_b, "heldout_invert_after": ho_i_a,
           "heldout_preserve_after": ho_p_a,
           "random_control": {"trained": float(tr_i_rand), "held": float(ho_i_rand)},
           "auc_before": auc_b, "auc_after": auc_a,
           "knn_overlap": ov, "spearman": rho, "verdict": verdict}
    (ROOT / "results" / "axis_amplify_v0.json").write_text(json.dumps(out, indent=2))
    print("[done] results/axis_amplify_v0.json")


if __name__ == "__main__":
    main()
