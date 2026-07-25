"""ZCA whitening + isotropy metrics.

Contrastive embedding spaces occupy a narrow anisotropic cone; rotation algebra
presupposes symmetric use of dimensions, so whitening is a prerequisite for R5
(docs/02-codec.md, docs/03-latent-algebra.md). ZCA (not PCA) keeps the whitened
space in the original basis.
"""

from __future__ import annotations

import numpy as np


def fit(X: np.ndarray, eps: float = 1e-3) -> dict:
    """Fit ZCA whitener. Returns {mean, W, eigvals}. Warn threshold: n < 4d."""
    n, d = X.shape
    mean = X.mean(axis=0)
    Xc = X - mean
    cov = (Xc.T @ Xc) / max(n - 1, 1)
    eigvals, V = np.linalg.eigh(cov)
    eigvals = np.clip(eigvals, 0.0, None)
    W = V @ np.diag(1.0 / np.sqrt(eigvals + eps)) @ V.T
    return {"mean": mean, "W": W.astype(np.float32), "eigvals": eigvals,
            "n_fit": n, "eps": eps, "underdetermined": n < 4 * d}


def apply(X: np.ndarray, whitener: dict, renorm: bool = True) -> np.ndarray:
    Z = (X - whitener["mean"]) @ whitener["W"]
    if renorm:
        Z = Z / (np.linalg.norm(Z, axis=1, keepdims=True) + 1e-12)
    return Z.astype(np.float32)


def save(whitener: dict, path: str) -> None:
    np.savez(path, **whitener)


def load(path: str) -> dict:
    z = np.load(path)
    return {k: z[k] for k in z.files}


def isotropy_report(X: np.ndarray, n_pairs: int = 200_000, seed: int = 0) -> dict:
    """Isotropy metrics (codec eval #5). Higher effective rank / lower mean |cos| = better."""
    rng = np.random.default_rng(seed)
    n, d = X.shape

    Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)
    i = rng.integers(0, n, n_pairs)
    j = rng.integers(0, n, n_pairs)
    keep = i != j
    cos = np.einsum("ij,ij->i", Xn[i[keep]], Xn[j[keep]])

    Xc = X - X.mean(axis=0)
    cov = (Xc.T @ Xc) / max(n - 1, 1)
    lam = np.clip(np.linalg.eigvalsh(cov), 0.0, None)
    lam_sum = lam.sum() + 1e-12
    p = lam / lam_sum
    entropy = -(p[p > 0] * np.log(p[p > 0])).sum()

    return {
        "n": int(n), "dim": int(d),
        "mean_abs_cos": float(np.abs(cos).mean()),
        "mean_cos": float(cos.mean()),
        "p95_cos": float(np.quantile(cos, 0.95)),
        "effective_rank": float(np.exp(entropy)),
        "participation_ratio": float(lam_sum**2 / ((lam**2).sum() + 1e-12)),
        "top1_eig_share": float(lam.max() / lam_sum),
    }
