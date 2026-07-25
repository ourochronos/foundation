"""Structure channel (D18): three mechanisms behind one API.

    struct_sim(x, y) = min( amp_cos, s_cos, role_sim )

- amp: rank-k valence-subspace amplification of the WHITENED gist (D16 —
  closed-form; subspace fit on train-split displacement bank). Catches the
  valence family (negation, approval/rejection, quantifier flips, ...).
- s:   trained StructPooler over BGE-M3 ColBERT token vectors (D17). Catches
  substitutions and part of the structural family.
- role: symbolic spaCy role bits (D18). Catches binding (argument_swap,
  causal_reverse) that survives both continuous channels.

min-combination: any sub-channel that flags a difference flags the pair.

Contract:
- Z inputs are whitened unit gists (codec.whiten.apply). The amp subspace is
  only valid in the space it was fit in — refit it whenever the whitener is.
- `amp()` output is a COMPARISON-TIME copy. Never store it, index it, or
  retrieve over it: the shipping gain (g=8) deliberately destroys retrieval
  geometry in exchange for valence discrimination (D20). The stored gist stays
  the untouched whitened dense vector.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import torch

from codec import role_bits as RB
from codec.struct_pooler import StructPooler

MAXLEN = 64          # token-cache padding length (matches train_struct_pooler)
AMP_TRAIN = ["negation", "argument_swap", "comparative_flip", "quantifier_change",
             "superlative_flip", "success_failure", "increase_decrease",
             "approval_rejection", "presence_absence"]


def hash_test_mask(texts: list[str], frac: float = 0.2) -> np.ndarray:
    """The project-wide deterministic pair split (True = test)."""
    return np.array([int.from_bytes(hashlib.sha256(t.encode()).digest()[:4],
                                    "big") < frac * 2**32 for t in texts])


def fit_amp_subspace(Xw: np.ndarray, Yw: np.ndarray, by_rel: dict,
                     cache_idx: dict, train_rels: list[str] = AMP_TRAIN,
                     k: int = 16) -> np.ndarray:
    """Top-k right singular vectors of the train-split displacement bank.

    Displacements are per-row normalized before concatenation so no single
    high-magnitude relation dominates the basis.
    """
    bank = []
    for rel in train_rels:
        rows = by_rel[rel]
        m = hash_test_mask([r["x"] for r in rows])
        idx = np.array([cache_idx[r["x"]] for r in rows])[~m]
        d = Xw[idx] - Yw[idx]
        bank.append(d / (np.linalg.norm(d, axis=1, keepdims=True) + 1e-12))
    _, _, Vt = np.linalg.svd(np.concatenate(bank), full_matrices=False)
    return Vt[:k]


def save_amp_subspace(path: str | Path, P: np.ndarray, gamma: float,
                      train_rels: list[str]) -> None:
    np.savez(path, P=P.astype(np.float32), gamma=np.float32(gamma),
             train_rels=np.array(train_rels))


def load_amp_subspace(path: str | Path) -> tuple[np.ndarray, float]:
    z = np.load(path, allow_pickle=True)
    return z["P"].astype(np.float32), float(z["gamma"])


class StructureChannel:
    def __init__(self, pooler: StructPooler, P: np.ndarray, gamma: float = 2.0,
                 device: str | None = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.pooler = pooler.to(self.device).eval()
        self.P = P
        self.gamma = gamma

    @classmethod
    def load(cls, root: str | Path, pooler_tag: str = "v2",
             subspace: str = "amp_subspace_v1.npz", d_pe: int = 32,
             device: str | None = None) -> "StructureChannel":
        """Defaults are the shipping config (D20): pooler v2 + amp v1."""
        root = Path(root)
        P, gamma = load_amp_subspace(root / "results" / subspace)
        pooler = StructPooler(d_pe=d_pe)
        pooler.load_state_dict(torch.load(
            root / "checkpoints" / f"struct_pooler_{pooler_tag}.pt",
            map_location="cpu"))
        return cls(pooler, P, gamma, device=device)

    # ---- mechanism 1: valence-subspace amplification (whitened gists) ----
    def amp(self, Z: np.ndarray) -> np.ndarray:
        out = Z + (self.gamma - 1.0) * (Z @ self.P.T) @ self.P
        return out / (np.linalg.norm(out, axis=1, keepdims=True) + 1e-12)

    def amp_cos(self, Zx: np.ndarray, Zy: np.ndarray) -> np.ndarray:
        return np.einsum("ij,ij->i", self.amp(Zx), self.amp(Zy))

    # ---- mechanism 2: structural pooler over token vectors ----
    def s(self, T: torch.Tensor, M: torch.Tensor, bs: int = 256) -> torch.Tensor:
        """Padded token tensors [N, L, 1024] / [N, L] -> unit s-vectors [N, d]."""
        outs = []
        with torch.no_grad():
            for i in range(0, len(T), bs):
                outs.append(self.pooler(T[i:i + bs].to(self.device),
                                        M[i:i + bs].to(self.device)).cpu())
        return torch.cat(outs)

    def s_cos(self, Tx, Mx, Ty, My, bs: int = 256) -> np.ndarray:
        sx, sy = self.s(Tx, Mx, bs), self.s(Ty, My, bs)
        return (sx * sy).sum(-1).numpy()

    def tokens(self, texts: list[str], encoder) -> tuple[torch.Tensor, torch.Tensor]:
        """ColBERT vectors via an M3Encoder, padded to MAXLEN."""
        vecs = encoder.encode_tokens(texts)
        d = vecs[0].shape[1]
        T = torch.zeros(len(texts), MAXLEN, d)
        M = torch.zeros(len(texts), MAXLEN, dtype=torch.bool)
        for i, v in enumerate(vecs):
            L = min(len(v), MAXLEN)
            T[i, :L] = torch.from_numpy(np.asarray(v[:L], dtype=np.float32))
            M[i, :L] = True
        return T, M

    # ---- mechanism 3: symbolic role bits ----
    def role_sim(self, x_text: str, y_text: str) -> float:
        return RB.role_sim(RB.extract(x_text), RB.extract(y_text), x_text, y_text)

    # ---- assembly ----
    def pair_scores(self, xs: list[str], ys: list[str],
                    Zx: np.ndarray, Zy: np.ndarray,
                    Tx, Mx, Ty, My) -> dict[str, np.ndarray]:
        rs = np.array([self.role_sim(x, y) for x, y in zip(xs, ys)])
        sc = self.s_cos(Tx, Mx, Ty, My)
        ac = self.amp_cos(Zx, Zy)
        return {"role_sim": rs, "s_cos": sc, "amp_cos": ac,
                "combined": np.minimum(np.minimum(sc, rs), ac)}
