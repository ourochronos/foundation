"""Fidelity + robustness + cycle evals (codec evals #1, #2, #4).

Reconstruction from z; entity/number exact-match against validated labels;
robustness = same metrics under noise sigma; cycle = cos(encode(decode(z)), z).
"""

from __future__ import annotations

import re

import numpy as np
import torch


def _relax(s: str) -> str:
    return re.sub(r"[,\s]", "", s)


def em_rates(recons: list[str], props) -> dict:
    """props: list of codec.data.Proposition aligned with recons."""
    ent_hit = ent_tot = num_hit = num_tot = num_hit_rel = 0
    exact_text = 0
    for r, p in zip(recons, props):
        exact_text += int(r.strip() == p.text.strip())
        for e in p.entities:
            ent_tot += 1
            ent_hit += int(e in r)
        for n in p.numbers:
            num_tot += 1
            num_hit += int(n in r)
            num_hit_rel += int(_relax(n) in _relax(r))
    return {
        "n": len(recons),
        "exact_text_rate": exact_text / max(len(recons), 1),
        "entity_em": ent_hit / max(ent_tot, 1), "n_entities": ent_tot,
        "number_em": num_hit / max(num_tot, 1),
        "number_em_relaxed": num_hit_rel / max(num_tot, 1), "n_numbers": num_tot,
    }


def reconstruct(decoder, Z: np.ndarray, bs: int = 32, sigma: float = 0.0,
                sp=None, s=None) -> list[str]:
    """sp: optional (ids, mask, w) tensors for the sparse identity channel;
    s: optional [N, s_dim] structure vectors — both row-aligned with Z."""
    from codec.decoder import noise_z
    outs: list[str] = []
    for i in range(0, len(Z), bs):
        z = torch.from_numpy(Z[i:i + bs]).to(decoder.device, torch.float32)
        if sigma > 0:
            z = noise_z(z, sigma)
        sp_b = tuple(t[i:i + bs] for t in sp) if sp is not None else None
        s_b = s[i:i + bs] if s is not None else None
        outs.extend(decoder.generate(z, sp=sp_b, s=s_b))
    return outs


def _num_head(text: str, number: str, nlp) -> str | None:
    """The content word a number binds to: its dependency head, ascending
    through number-like heads ("1.2 billion gallons" -> gallons)."""
    doc = nlp(text)
    for tok in doc:
        if tok.text == number or tok.text.replace(",", "") == number.replace(",", ""):
            head = tok.head
            for _ in range(3):
                if head.like_num or head.pos_ == "NUM":
                    head = head.head
                else:
                    break
            if head is not tok:
                return head.text
    return None


def binding_pairs(props) -> list[list[tuple[str, str]]]:
    """Per proposition: [(number, head-word)] pairs from the validated labels
    plus a dependency parse. The unit of the binding metric (D21 residual)."""
    from codec.role_bits import _nlp
    nlp = _nlp()
    out = []
    for p in props:
        pairs = []
        for n in p.numbers:
            h = _num_head(p.text, n, nlp)
            if h is not None and h.lower() != n.lower():
                pairs.append((n, h))
        out.append(pairs)
    return out


def binding_rate(recons: list[str], pairs: list[list[tuple[str, str]]],
                 window: int = 3) -> dict:
    """A pair is BOUND when the number appears in the recon with its head word
    within `window` tokens. Number EM counts presence; this counts attachment —
    the two diverge exactly on D21's failure mode (right value, wrong slot)."""
    hit = tot = present = 0
    for r, ps in zip(recons, pairs):
        toks = r.split()
        for n, h in ps:
            tot += 1
            idxs = [i for i, t in enumerate(toks)
                    if n in t or n.replace(",", "") in t.replace(",", "")]
            if not idxs:
                continue
            present += 1
            lo_h = h.lower()
            for i in idxs:
                lo, hi = max(0, i - window), min(len(toks), i + window + 1)
                if any(lo_h in t.lower() for t in toks[lo:hi]):
                    hit += 1
                    break
    return {"binding_rate": hit / max(tot, 1),
            "binding_given_present": hit / max(present, 1),
            "n_pairs": tot, "n_present": present}


def cycle_cos(encoder, whitener, recons: list[str], Z_ref: np.ndarray) -> dict:
    """cos( whiten(encode(recon)), z_ref ) — eval #4 at k=1."""
    from codec import whiten as W
    dense, _ = encoder.encode(recons, sparse=False)
    Zc = W.apply(dense, whitener)
    cos = np.einsum("ij,ij->i", Zc, Z_ref)
    return {"cycle_cos_mean": float(cos.mean()),
            "cycle_cos_median": float(np.median(cos)),
            "cycle_cos_p10": float(np.quantile(cos, 0.10))}


def robustness_sweep(decoder, Z: np.ndarray, props, sigmas, bs: int = 32,
                     sp=None, s=None) -> list[dict]:
    """Noise applied to the gist channel only; the identity channel (sp) and
    the structure vector (s) pass through unperturbed — symbolic/side-channel
    by design (D3/D20)."""
    rows = []
    for sig in sigmas:
        recons = reconstruct(decoder, Z, bs=bs, sigma=float(sig), sp=sp, s=s)
        r = em_rates(recons, props)
        r["sigma"] = float(sig)
        rows.append(r)
    return rows
