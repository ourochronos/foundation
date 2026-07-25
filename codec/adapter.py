"""Separation adapter (D9).

The frozen BGE-M3 latent barely distinguishes meaning-inverting propositional
edits (argument swap cos 0.974, negation 0.734) — smaller than the noise the
decoder is trained to ignore. Whitening fixes anisotropy but not this: the
adapter's job is upgraded from *isotropize* to *separate*.

Residual by construction — f(z) = normalize(z + MLP(z)) — so it starts at
identity and the geometry-preservation term has something to hold onto.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as Fn


class SeparationAdapter(nn.Module):
    def __init__(self, d: int = 1024, hidden: int = 2048, scale: float = 0.1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d, hidden), nn.GELU(), nn.Linear(hidden, d))
        # small init: start close to the identity map
        nn.init.normal_(self.net[-1].weight, std=1e-3)
        nn.init.zeros_(self.net[-1].bias)
        self.scale = nn.Parameter(torch.tensor(scale))

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        return Fn.normalize(z + self.scale * self.net(z), dim=-1)


def cos(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    return (Fn.normalize(a, dim=-1) * Fn.normalize(b, dim=-1)).sum(-1)


def separation_loss(
    f, x_inv, y_inv, x_pre, y_pre, z_a, z_b,
    m_invert: float = 0.5, m_preserve: float = 0.9, w_geom: float = 1.0,
) -> tuple[torch.Tensor, dict]:
    """Three terms:
      invert  — meaning-inverting pairs pushed below m_invert cosine
      preserve— meaning-preserving pairs held above m_preserve
      geom    — random corpus pairs keep their ORIGINAL cosine, so the adapter
                cannot satisfy the first two by collapsing or scrambling the
                space (this is what protects retrieval geometry, D2)
    """
    c_inv = cos(f(x_inv), f(y_inv))
    c_pre = cos(f(x_pre), f(y_pre))
    l_inv = Fn.relu(c_inv - m_invert).mean()
    l_pre = Fn.relu(m_preserve - c_pre).mean()

    c_before = cos(z_a, z_b)
    c_after = cos(f(z_a), f(z_b))
    l_geom = ((c_after - c_before) ** 2).mean()

    total = l_inv + l_pre + w_geom * l_geom
    return total, {"loss": float(total), "invert": float(l_inv),
                   "preserve": float(l_pre), "geom": float(l_geom),
                   "cos_invert": float(c_inv.mean()),
                   "cos_preserve": float(c_pre.mean())}
