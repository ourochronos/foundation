"""Fit and persist the v0 valence-amplification subspace (structure channel).

Rebuilds the D16 displacement-bank SVD (k=16, gain 2.0 — the geometry-safe
config kept for any in-place use) through codec.structure_channel and writes
results/amp_subspace_v0.npz. The SHIPPING subspace is v1: see
scripts/probe_axis_amplify_v1.py --persist (D20).

Parity check: recomputes per-type amp_cos and compares against the reference
run. This is only meaningful in the space the reference was measured in — the
subspace lives in whitened coordinates, so a refit whitener legitimately moves
every number. The check is therefore gated on a whitener fingerprint and
downgraded to informational when the space has changed.

Usage: .venv/bin/python scripts/fit_amp_subspace.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec.structure_channel import (AMP_TRAIN, fit_amp_subspace,   # noqa: E402
                                     hash_test_mask, load_amp_subspace,
                                     save_amp_subspace)

GAMMA = 2.0
OUT = ROOT / "results" / "amp_subspace_v0.npz"


def whitener_fp() -> str:
    """Short fingerprint of the whitening transform — amp_cos values are only
    comparable across runs that share it."""
    z = np.load(ROOT / "results" / "whiten_v0.npz")
    h = hashlib.sha256()
    for k in sorted(z.files):
        h.update(np.ascontiguousarray(z[k], dtype=np.float64).tobytes())
    return h.hexdigest()[:16]


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
    by_rel = load_pairs()
    zc = np.load(ROOT / "results" / "prop_relation_emb.npz", allow_pickle=True)
    cache_idx = {t: i for i, t in enumerate(zc["xs"])}
    Xw, Yw = zc["X"], zc["Y"]

    P = fit_amp_subspace(Xw, Yw, by_rel, cache_idx)
    save_amp_subspace(OUT, P, GAMMA, AMP_TRAIN)
    print(f"[fit] P {P.shape} gamma={GAMMA} <- {len(AMP_TRAIN)} train relations")

    # reload through the module and verify parity with the shipped v1 numbers
    P2, g2 = load_amp_subspace(OUT)

    def amp(Z):
        out = Z + (g2 - 1.0) * (Z @ P2.T) @ P2
        return out / (np.linalg.norm(out, axis=1, keepdims=True) + 1e-12)

    ref_path = ROOT / "results" / "structure_channel_v1.json"
    ref_doc = json.loads(ref_path.read_text())
    ref = {r["relation"]: r["amp_cos"] for r in ref_doc["table"]}
    same_space = ref_doc.get("whitener_fp") == whitener_fp()
    if not same_space:
        print("[parity] whitener fingerprint differs from the reference run — "
              "amp_cos lives in whitened coordinates, so deltas below are "
              "expected and INFORMATIONAL (they measure how far the refit "
              "space moved, not a regression).")
    worst = 0.0
    for rel, rows in sorted(by_rel.items()):
        if rel not in ref:            # types added after v1 shipped
            continue
        m = hash_test_mask([r["x"] for r in rows])
        test = [r for r, t in zip(rows, m) if t]
        ix = np.array([cache_idx[r["x"]] for r in test])
        ac = float(np.einsum("ij,ij->i", amp(Xw[ix]), amp(Yw[ix])).mean())
        d = abs(ac - ref[rel])
        worst = max(worst, d)
        flag = "" if d < 1e-4 else ("  <-- differs" if not same_space
                                    else "  <-- MISMATCH")
        print(f"  {rel:>18}  persisted={ac:.4f}  v1_probe={ref[rel]:.4f}{flag}")
    if same_space:
        print(f"[parity] max |delta| = {worst:.2e} -> "
              f"{'OK' if worst < 1e-4 else 'FAILED'}")
        if worst >= 1e-4:
            raise SystemExit(1)
    else:
        print(f"[parity] max |delta| = {worst:.2e} across the space change "
              f"(informational; subspace is stable if this is small)")
    print(f"[done] {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
