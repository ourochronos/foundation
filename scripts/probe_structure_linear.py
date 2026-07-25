"""Is structural information linearly present in BGE-M3's pooled latent?

Decides between two branches of D12:
  - role/polarity info is present-but-tiny  -> fine-tuning pooling can salvage it
  - it is absent from the pooled vector     -> structure must come from elsewhere

Two tests, both parameter-free or near-so (D8: no overparameterized fits), each
with a permutation control:

1. ROLE AXIS (argument_swap): if roles are encoded ~additively by position,
   z("A verb B") - z("B verb A") should align with embed(A) - embed(B) up to
   sign conventions. Zero-parameter test: cos(z_x - z_y, e_A - e_B) per pair.
   Control: same statistic with B drawn from a *different* pair.

2. POLARITY AXIS (negation): is there a consistent linear "not" direction?
   Consistency = mean pairwise cosine between difference vectors d_i;
   classification = sign(cos(d_i, mu_train)) on held-out pairs.
   Control: pairwise consistency between random unit vectors (~0 in 1024-d).

Usage: .venv/bin/python scripts/probe_structure_linear.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec import whiten as W               # noqa: E402
from codec.evals import rotations as ROT    # noqa: E402


def load_pairs(name: str) -> list[dict]:
    f = ROOT / "data" / "relations" / f"prop_{name}.jsonl"
    rows, seen = [], set()
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        if o["x"].lower() in seen:
            continue
        seen.add(o["x"].lower())
        rows.append(o)
    return rows


def cached_span(rel: str) -> tuple[np.ndarray, np.ndarray]:
    """Slice the (whitened, unit) pair embeddings for one relation from cache."""
    z = np.load(ROOT / "results" / "prop_relation_emb.npz", allow_pickle=True)
    xs = list(z["xs"])
    rows = load_pairs(rel)
    idx = [xs.index(r["x"]) for r in rows]     # cache holds all rels concatenated
    return z["X"][idx], z["Y"][idx], rows


def first_diff_words(x: str, y: str) -> tuple[str, str] | None:
    xt, yt = x.split(), y.split()
    for a, b in zip(xt, yt):
        ca, cb = a.strip(".,;:!?'\""), b.strip(".,;:!?'\"")
        if ca != cb and ca and cb:
            return ca, cb
    return None


def main() -> None:
    rng = np.random.default_rng(0)
    out = {"generated_at": datetime.now(timezone.utc).isoformat()}

    # ---------- 1. ROLE AXIS ----------
    Xs, Ys, rows = cached_span("swap")
    ab = [first_diff_words(r["x"], r["y"]) for r in rows]
    keep = [i for i, p in enumerate(ab) if p is not None]
    Xs, Ys = Xs[keep], Ys[keep]
    A_words = [ab[i][0] for i in keep]
    B_words = [ab[i][1] for i in keep]
    print(f"[swap] {len(keep)} pairs with extractable (A,B) "
          f"e.g. {A_words[0]!r} vs {B_words[0]!r}")

    from codec.encode import M3Encoder
    enc = M3Encoder()
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    eA, _ = enc.encode(A_words, sparse=False)
    eB, _ = enc.encode(B_words, sparse=False)
    eA = ROT.unit(W.apply(eA, whitener))
    eB = ROT.unit(W.apply(eB, whitener))

    d_z = Xs - Ys                      # latent response to the swap
    d_e = eA - eB                      # entity-embedding difference

    def paircos(P, Q):
        num = np.einsum("ij,ij->i", P, Q)
        den = (np.linalg.norm(P, axis=1) * np.linalg.norm(Q, axis=1) + 1e-12)
        return num / den

    align = paircos(d_z, d_e)
    perm = rng.permutation(len(d_e))
    while (perm == np.arange(len(d_e))).any():
        perm = rng.permutation(len(d_e))
    align_null = paircos(d_z, d_e[perm])

    # magnitude context: how big is the swap response at all?
    d_norm = np.linalg.norm(d_z, axis=1)
    rand_norm = np.linalg.norm(Xs - Xs[rng.permutation(len(Xs))], axis=1)

    role = {
        "n": len(keep),
        "align_mean": float(align.mean()),
        "align_abs_mean": float(np.abs(align).mean()),
        "sign_consistency": float((align > 0).mean()),
        "null_mean": float(align_null.mean()),
        "null_abs_mean": float(np.abs(align_null).mean()),
        "swap_diff_norm_mean": float(d_norm.mean()),
        "random_pair_norm_mean": float(rand_norm.mean()),
        "signal_fraction": float(d_norm.mean() / rand_norm.mean()),
    }
    out["role_axis"] = role
    print(f"[role] cos(z_x - z_y, e_A - e_B): mean={role['align_mean']:+.3f} "
          f"|mean|={role['align_abs_mean']:.3f} sign+={role['sign_consistency']:.2f}"
          f"  (null: {role['null_mean']:+.3f}/{role['null_abs_mean']:.3f})")
    print(f"[role] swap displacement = {role['signal_fraction']:.2%} of a random "
          f"inter-proposition distance")

    # ---------- 2. POLARITY AXIS ----------
    Xn, Yn, _ = cached_span("negation")
    d = Xn - Yn
    d = d / (np.linalg.norm(d, axis=1, keepdims=True) + 1e-12)
    n = len(d)
    te = rng.permutation(n)[: n // 5]
    tr = np.setdiff1d(np.arange(n), te)
    mu = d[tr].mean(axis=0)
    mu /= np.linalg.norm(mu) + 1e-12

    G = d @ d.T
    consistency = float((G.sum() - n) / (n * n - n))
    rand = rng.standard_normal(d.shape)
    rand /= np.linalg.norm(rand, axis=1, keepdims=True)
    Gr = rand @ rand.T
    consistency_null = float((Gr.sum() - n) / (n * n - n))
    heldout_acc = float((d[te] @ mu > 0).mean())

    # single-latent separability along mu: project affirmative vs negated
    proj_x, proj_y = Xn[te] @ mu, Yn[te] @ mu
    sep_acc = float((proj_x > proj_y).mean())

    pol = {"n": n, "direction_consistency": consistency,
           "consistency_null": consistency_null,
           "heldout_sign_acc": heldout_acc,
           "heldout_pair_separation_acc": sep_acc}
    out["polarity_axis"] = pol
    print(f"[polarity] direction consistency={consistency:.3f} "
          f"(null {consistency_null:+.3f}) | held-out sign acc={heldout_acc:.2f} "
          f"| pair separation along mu={sep_acc:.2f}")

    # ---------- verdicts ----------
    role_present = role["align_abs_mean"] > 3 * role["null_abs_mean"] and \
        (role["sign_consistency"] > 0.65 or role["sign_consistency"] < 0.35)
    pol_present = consistency > 0.1 and heldout_acc > 0.8
    out["verdict"] = {
        "role": ("LINEARLY PRESENT (tiny but systematic) — pooling salvageable"
                 if role_present else
                 "NOT SYSTEMATICALLY ENCODED in the pooled vector — structure "
                 "must come from below pooling or another encoder"),
        "polarity": ("LINEAR DIRECTION EXISTS — polarity is a steerable axis"
                     if pol_present else "no consistent linear polarity axis"),
    }
    print(f"\n[verdict/role] {out['verdict']['role']}")
    print(f"[verdict/polarity] {out['verdict']['polarity']}")

    (ROOT / "results" / "structure_linear_probe.json").write_text(json.dumps(out, indent=2))
    print("[done] results/structure_linear_probe.json")


if __name__ == "__main__":
    main()
