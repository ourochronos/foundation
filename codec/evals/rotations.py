"""Rotation-family fitting for the relational probe (docs/03-latent-algebra.md).

Two families, very different capacity — the distinction the v0 probe missed:

  full orthogonal   O(d)          d(d-1)/2 params  (d=1024 -> ~524k)
  block-diagonal    FHRR/RoPE     d/2 params       (d=1024 -> 512)

D4 proposes the *block-diagonal* family. Fitting full O(d) from ~45 pairs is
degenerate: R is constrained only on the span of the training inputs and is
arbitrary on the complement, where most of a held-out vector's norm lives.

Per-plane closed form: for plane p, the angle minimizing sum_i ||R(th) x_i - y_i||^2
is atan2(sum_i (x1*y2 - x2*y1), sum_i (x1*y1 + x2*y2)) — a 2-d Procrustes.
"""

from __future__ import annotations

import numpy as np


def fit_block_rotation(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """Closed-form per-plane angles. X, Y: [n, d] (d even). Returns [d/2]."""
    n, d = X.shape
    xp = X.reshape(n, d // 2, 2)
    yp = Y.reshape(n, d // 2, 2)
    num = (xp[:, :, 0] * yp[:, :, 1] - xp[:, :, 1] * yp[:, :, 0]).sum(axis=0)
    den = (xp[:, :, 0] * yp[:, :, 0] + xp[:, :, 1] * yp[:, :, 1]).sum(axis=0)
    return np.arctan2(num, den)


def apply_block_rotation(X: np.ndarray, angles: np.ndarray) -> np.ndarray:
    n, d = X.shape
    xp = X.reshape(n, d // 2, 2)
    c, s = np.cos(angles), np.sin(angles)
    out = np.empty_like(xp)
    out[:, :, 0] = xp[:, :, 0] * c - xp[:, :, 1] * s
    out[:, :, 1] = xp[:, :, 0] * s + xp[:, :, 1] * c
    return out.reshape(n, d)


def fit_full_rotation(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    from scipy.linalg import orthogonal_procrustes
    R, _ = orthogonal_procrustes(X, Y)
    return R


def param_counts(d: int) -> dict[str, int]:
    return {"full": d * (d - 1) // 2, "block": d // 2,
            "translation": d, "identity": 0}


def pca_basis(X: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Fit PCA on X. Returns (mean, components [k, d])."""
    mu = X.mean(axis=0)
    Xc = X - mu
    _, _, Vt = np.linalg.svd(Xc, full_matrices=False)
    return mu, Vt[:k]


def unit(X: np.ndarray) -> np.ndarray:
    return X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)


def synthetic_control(d: int, n_train: int, n_test: int, seed: int = 0) -> dict:
    """Positive control: Y is X rotated by a KNOWN block rotation (+ small noise).

    If a family cannot recover this at the given (d, n_train), the probe is
    capacity-limited and its negative result on real data says nothing about
    whether relations are rotational.
    """
    rng = np.random.default_rng(seed)
    n = n_train + n_test
    X = unit(rng.standard_normal((n, d)))
    true_angles = rng.uniform(-np.pi, np.pi, d // 2)
    Y = apply_block_rotation(X, true_angles)
    Y = unit(Y + 0.05 * rng.standard_normal((n, d)))

    Xtr, Ytr, Xte, Yte = X[:n_train], Y[:n_train], X[n_train:], Y[n_train:]
    ang = fit_block_rotation(Xtr, Ytr)
    R = fit_full_rotation(Xtr, Ytr)

    def cos(A, B):
        return float(np.einsum("ij,ij->i", unit(A), unit(B)).mean())

    return {
        "d": d, "n_train": n_train, "n_test": n_test,
        "cos_block": cos(apply_block_rotation(Xte, ang), Yte),
        "cos_full": cos(Xte @ R, Yte),
        "cos_translation": cos(Xte + (Ytr - Xtr).mean(axis=0), Yte),
        "cos_identity": cos(Xte, Yte),
        "angle_mae": float(np.abs(np.angle(np.exp(1j * (ang - true_angles)))).mean()),
        "params": param_counts(d),
    }
