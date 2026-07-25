"""BGE-M3 encoder wrapper: dense gist channel + sparse lexical identity channel.

Dense: 1024-d L2-normalized. Sparse: per-text {token_id: weight} — the identity
channel (docs/02-codec.md, D3). Whitening/adapter are applied downstream.
"""

from __future__ import annotations

import numpy as np


class M3Encoder:
    def __init__(self, model_name: str = "BAAI/bge-m3", device: str | None = None):
        import torch
        from FlagEmbedding import BGEM3FlagModel

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        use_fp16 = device.startswith("cuda")
        try:
            self.model = BGEM3FlagModel(model_name, use_fp16=use_fp16, devices=[device])
        except TypeError:  # older FlagEmbedding signature
            self.model = BGEM3FlagModel(model_name, use_fp16=use_fp16, device=device)

    def encode(
        self,
        texts: list[str],
        batch_size: int = 64,
        max_length: int = 128,
        sparse: bool = True,
    ) -> tuple[np.ndarray, list[dict[str, float]] | None]:
        """Returns (dense [n,1024] float32, lexical_weights or None)."""
        out = self.model.encode(
            texts,
            batch_size=batch_size,
            max_length=max_length,
            return_dense=True,
            return_sparse=sparse,
            return_colbert_vecs=False,
        )
        dense = np.asarray(out["dense_vecs"], dtype=np.float32)
        lex = out.get("lexical_weights") if sparse else None
        return dense, lex

    def encode_tokens(
        self, texts: list[str], batch_size: int = 32, max_length: int = 96,
    ) -> list[np.ndarray]:
        """Per-token (ColBERT) vectors — order/binding info at full strength,
        before pooling discards it. Returns a list of [len_i, dim] float32."""
        out = self.model.encode(
            texts, batch_size=batch_size, max_length=max_length,
            return_dense=False, return_sparse=False, return_colbert_vecs=True,
        )
        return [np.asarray(v, dtype=np.float32) for v in out["colbert_vecs"]]


def sparse_stats(lex: list[dict[str, float]]) -> dict:
    """Aggregate stats proving the identity channel carries signal."""
    nnz = np.array([len(d) for d in lex])
    top_w = np.array([max(d.values()) if d else 0.0 for d in lex])
    return {
        "mean_nnz": float(nnz.mean()),
        "median_nnz": float(np.median(nnz)),
        "mean_top_weight": float(top_w.mean()),
        "empty_frac": float((nnz == 0).mean()),
    }
