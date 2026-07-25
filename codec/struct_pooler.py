"""Structural pooler (D14 option b): token vectors -> binding-aware s-vector.

Why token level: the pooled dense vector's structural signal is content-
conditional and ~16% of inter-proposition distance (D16) — no fixed map over it
can separate role rebindings. Token embeddings carry order/binding at full
strength; this small attention pooler learns WHAT to keep instead of averaging
it away.

Why it can't cheat lexically: argument_swap training pairs are bag-of-words
IDENTICAL (only binding differs) and must separate, while active_passive /
clause_reorder pairs change surface order but preserve meaning and must stay
together. Satisfying both requires reading binding, not word presence or
position alone.

s is a SEPARATE channel: the gist vector is untouched, so no retrieval-geometry
guardrail applies — only non-degeneracy checks.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as Fn


class StructPooler(nn.Module):
    """d_pe > 0 concatenates sinusoidal position features to each token vector.

    Without them the pooler is a SET function: if per-token embeddings are
    near position-invariant (BGE-M3 ColBERT vectors empirically are — v0 could
    not fit argument_swap even on training pairs), swapped-role sentences
    present nearly identical token sets and are provably indistinguishable.
    """

    def __init__(self, d_in: int = 1024, d: int = 192, n_queries: int = 8,
                 heads: int = 4, d_out: int = 192, dropout: float = 0.1,
                 d_pe: int = 32):
        super().__init__()
        self.d_pe = d_pe
        self.proj = nn.Linear(d_in + d_pe, d)
        self.queries = nn.Parameter(torch.randn(n_queries, d) * 0.02)
        self.attn = nn.MultiheadAttention(d, heads, dropout=dropout, batch_first=True)
        self.out = nn.Linear(n_queries * d, d_out)

    def _pe(self, L: int, device) -> torch.Tensor:
        pos = torch.arange(L, device=device, dtype=torch.float32).unsqueeze(1)
        i = torch.arange(self.d_pe // 2, device=device, dtype=torch.float32)
        ang = pos / torch.pow(10000.0, 2 * i / self.d_pe)
        return torch.cat([torch.sin(ang), torch.cos(ang)], dim=-1)   # [L, d_pe]

    def forward(self, tok: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """tok [B, L, d_in], mask [B, L] (True = real token) -> s [B, d_out] unit."""
        if self.d_pe:
            pe = self._pe(tok.shape[1], tok.device).expand(tok.shape[0], -1, -1)
            tok = torch.cat([tok, pe], dim=-1)
        h = self.proj(tok)
        q = self.queries.unsqueeze(0).expand(h.shape[0], -1, -1)
        o, _ = self.attn(q, h, h, key_padding_mask=~mask)
        return Fn.normalize(self.out(o.flatten(1)), dim=-1)


def pooler_loss(
    s_xi, s_yi,      # inverting pairs   — push apart
    s_xp, s_yp,      # preserving pairs  — hold together
    s_neg,           # unrelated propositions — spread (anti-collapse/anti-hash)
    m_inv: float = 0.4, m_pre: float = 0.8, w_unif: float = 0.5,
):
    c_inv = (s_xi * s_yi).sum(-1)
    c_pre = (s_xp * s_yp).sum(-1)
    l_inv = Fn.relu(c_inv - m_inv).mean()
    l_pre = Fn.relu(m_pre - c_pre).mean()
    if len(s_neg) < 2:
        raise ValueError("pooler_loss needs >= 2 negative rows")
    G = s_neg @ s_neg.T
    off = G - torch.diag(torch.diag(G))
    l_unif = (off ** 2).sum() / (len(s_neg) * (len(s_neg) - 1))
    total = l_inv + l_pre + w_unif * l_unif
    return total, {"inv": float(c_inv.mean()), "pre": float(c_pre.mean()),
                   "unif": float(l_unif), "loss": float(total)}
