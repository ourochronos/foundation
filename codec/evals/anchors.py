"""Anchor-spanning probe v0 (codec eval #7, thesis T2).

Measures how much of held-out embedding space is reachable from a k-means
anchor set, bracketing the rotation question analytically:

  lower bracket — cos(z, nearest anchor): anchors alone, no transform.
  upper bracket — best per-plane phase alignment (FHRR/RoPE family with a FREE
    angle per 2-d plane): closed form, cos_bound(z, a) = sum_p |z_p||a_p| over
    d/2 complex planes. Any constrained rotation family we'd actually adopt
    lands between the brackets; a gradient-fit constrained-R probe is Phase 1.5.
"""

from __future__ import annotations

import numpy as np
from sklearn.cluster import MiniBatchKMeans


def _plane_mags(X: np.ndarray) -> np.ndarray:
    """[n, d] -> [n, d/2] magnitudes of consecutive-pair 2-d planes."""
    n, d = X.shape
    return np.linalg.norm(X.reshape(n, d // 2, 2), axis=2)


def phase_aligned_bound(Z: np.ndarray, A: np.ndarray) -> np.ndarray:
    """Max cosine between each Z row and each A row under free per-plane rotation.

    Z: [n, d] unit rows; A: [m, d] unit rows. Returns [n, m].
    """
    return _plane_mags(Z) @ _plane_mags(A).T


def fit_anchors(X_train: np.ndarray, n_anchors: int, seed: int = 0) -> np.ndarray:
    km = MiniBatchKMeans(n_clusters=n_anchors, random_state=seed,
                         batch_size=1024, n_init=3, max_iter=200)
    km.fit(X_train)
    A = km.cluster_centers_
    return (A / (np.linalg.norm(A, axis=1, keepdims=True) + 1e-12)).astype(np.float32)


def spanning_report(
    X_train: np.ndarray,
    X_eval: np.ndarray,
    anchor_counts: list[int],
    top_k: int = 8,
    seed: int = 0,
) -> list[dict]:
    """Coverage vs anchor count. Rows: cosine (anchors only) and the
    phase-aligned upper bound taken over the top_k nearest anchors."""
    rows = []
    for n_anchors in anchor_counts:
        if n_anchors > len(X_train) // 2:
            rows.append({"n_anchors": n_anchors, "skipped": "n_anchors > train/2"})
            continue
        A = fit_anchors(X_train, n_anchors, seed)
        cos = X_eval @ A.T                                  # [n_eval, m]
        top_idx = np.argpartition(-cos, min(top_k, cos.shape[1]) - 1, axis=1)[:, :top_k]
        nearest = cos.max(axis=1)
        bound_all = phase_aligned_bound(X_eval, A)          # [n_eval, m]
        bound_topk = np.take_along_axis(bound_all, top_idx, axis=1).max(axis=1)
        rows.append({
            "n_anchors": n_anchors,
            "nearest_cos_mean": float(nearest.mean()),
            "nearest_cos_median": float(np.median(nearest)),
            "nearest_cos_p10": float(np.quantile(nearest, 0.10)),
            "phase_bound_mean": float(bound_topk.mean()),
            "phase_bound_median": float(np.median(bound_topk)),
            "phase_bound_p10": float(np.quantile(bound_topk, 0.10)),
        })
    return rows
