"""Soft-prefix decoder: latent -> text via a small causal LM + LoRA.

v0: z (whitened, unit-norm, 1024-d) -> MLP projector -> k soft prefix
embeddings prepended to the LM input. Noise injection during training
implements R1 (docs/02-codec.md): z' = normalize(z + sigma * u), u a uniform
unit vector, so sigma is directly the perturbation norm
(cos(z, z') ~ 1/sqrt(1 + sigma^2)).

v2 (codec v2, D3/D10/D20): conditions on the full triple
    [ gist z | sparse identities | structure s-vector ]
with the two D10 sparse fixes —
  norm rescale       weights are per-row max-normalized (BGE-M3 sparse weights
                     average ~0.28, which silently shrank v1's identity
                     prefixes to a quarter of embedding scale) plus a learned
                     scalar gain;
  gradient pressure  `dense_drop` zeroes the gist prefixes for a random subset
                     of training rows, so exact values are learnable ONLY
                     through the identity channel (dense alone reaches loss
                     0.02 and starves the other channels of gradient).
Prefix layout: [k gist | k_sparse identity | k_s structure].
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn


class PrefixProjector(nn.Module):
    def __init__(self, z_dim: int, k: int, d_model: int, hidden: int = 2048):
        super().__init__()
        self.k, self.d_model = k, d_model
        self.net = nn.Sequential(
            nn.Linear(z_dim, hidden), nn.GELU(), nn.Linear(hidden, k * d_model)
        )

    def forward(self, z: torch.Tensor) -> torch.Tensor:  # [B, z_dim] -> [B, k, d_model]
        return self.net(z).view(z.shape[0], self.k, self.d_model)


def noise_z(z: torch.Tensor, sigma: torch.Tensor | float) -> torch.Tensor:
    """Perturb unit-norm rows by a vector of norm sigma, then renormalize."""
    u = torch.randn_like(z)
    u = u / (u.norm(dim=-1, keepdim=True) + 1e-8)
    if not torch.is_tensor(sigma):
        sigma = torch.full((z.shape[0],), float(sigma), device=z.device, dtype=z.dtype)
    zn = z + sigma.unsqueeze(-1) * u
    return zn / (zn.norm(dim=-1, keepdim=True) + 1e-8)


def build_sparse_tensors(rows, tokenizer, k_sparse: int, max_sub: int = 4):
    """Sparse identity channel -> decoder-vocab tensors.

    rows: [{"tokens": [str], "weights": [float]}] from results/sparse_v0.json.
    Returns (ids [N,k,max_sub], mask [N,k,max_sub], weights [N,k]).
    """
    n = len(rows)
    ids = torch.zeros(n, k_sparse, max_sub, dtype=torch.long)
    mask = torch.zeros(n, k_sparse, max_sub, dtype=torch.float32)
    w = torch.zeros(n, k_sparse, dtype=torch.float32)
    for i, r in enumerate(rows):
        for j, (tok, wt) in enumerate(zip(r["tokens"][:k_sparse], r["weights"][:k_sparse])):
            sub = tokenizer(" " + tok, add_special_tokens=False)["input_ids"][:max_sub]
            if not sub:
                continue
            ids[i, j, :len(sub)] = torch.tensor(sub)
            mask[i, j, :len(sub)] = 1.0
            w[i, j] = wt
    return ids, mask, w


class SoftPrefixDecoder(nn.Module):
    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-0.6B",
        z_dim: int = 1024,
        k: int = 16,
        lora_r: int = 16,
        k_sparse: int = 0,
        k_s: int = 0,
        s_dim: int = 192,
        sparse_fix: bool = False,
        device: str = "cuda",
    ):
        super().__init__()
        from peft import LoraConfig, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.config = {"model_name": model_name, "z_dim": z_dim, "k": k,
                       "lora_r": lora_r, "k_sparse": k_sparse,
                       "k_s": k_s, "s_dim": s_dim, "sparse_fix": sparse_fix}
        self.k_sparse, self.k_s, self.sparse_fix = k_sparse, k_s, sparse_fix
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        lm = AutoModelForCausalLM.from_pretrained(model_name, dtype=torch.bfloat16)
        lora = LoraConfig(
            task_type="CAUSAL_LM", r=lora_r, lora_alpha=2 * lora_r, lora_dropout=0.05,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"],
        )
        self.lm = get_peft_model(lm, lora)
        d_model = lm.config.hidden_size
        self.proj = PrefixProjector(z_dim, k, d_model).to(torch.bfloat16)
        # identity channel: weighted lexical-token embeddings -> prefix slots
        self.sparse_proj = (nn.Linear(d_model, d_model).to(torch.bfloat16)
                            if k_sparse else None)
        # D10 fix (b): learned gain over max-normalized weights. fp32 — a
        # bf16 scalar's optimizer updates round away below ~1e-3 resolution
        self.sparse_gain = (nn.Parameter(torch.tensor(1.0))
                            if (k_sparse and sparse_fix) else None)
        # structure channel: pooled s-vector -> k_s prefix slots
        self.s_proj = (PrefixProjector(s_dim, k_s, d_model, hidden=512)
                       .to(torch.bfloat16) if k_s else None)
        self.device = device
        self.to(device)

    def n_prefix(self) -> int:
        return self.proj.k + self.k_sparse + self.k_s

    def _sparse_prefix(self, sp):
        """sp = (ids [B,k,s], mask [B,k,s], w [B,k]) -> [B, k, d_model]"""
        ids, mask, w = (t.to(self.device) for t in sp)
        emb = self.lm.get_input_embeddings()(ids)                    # [B,k,s,d]
        m = mask.unsqueeze(-1).to(emb.dtype)
        pooled = (emb * m).sum(2) / m.sum(2).clamp(min=1e-6)          # [B,k,d]
        if self.sparse_fix:
            # relative importance only — raw BGE-M3 weights average ~0.28 and
            # crushed v1's identity prefixes to a quarter of embedding scale
            w = w / w.amax(dim=1, keepdim=True).clamp(min=1e-6)
            pooled = pooled * w.unsqueeze(-1).to(pooled.dtype)
            return self.sparse_proj(pooled) * self.sparse_gain.to(pooled.dtype)
        pooled = pooled * w.unsqueeze(-1).to(pooled.dtype)
        return self.sparse_proj(pooled)

    def _embeds(self, z: torch.Tensor, input_ids: torch.Tensor | None, sp=None,
                s: torch.Tensor | None = None,
                dense_drop: torch.Tensor | None = None):
        z = z.to(self.device, torch.bfloat16)
        if dense_drop is not None:
            # D10 fix (a): rows where the gist is withheld — identities must
            # then flow from the sparse channel or nowhere. Drop by zeroing z
            # BEFORE the projector: dropped rows get proj(0), a learned
            # in-distribution "null gist" embedding. Zeroing the projected
            # embeddings instead sends exact-zero vectors through every
            # RMSNorm and produces non-finite LoRA gradients in backward
            # (measured: finite loss, 246 inf/NaN grads).
            keep = (~dense_drop.to(self.device)).to(z.dtype)
            z = z * keep[:, None]
        parts = [self.proj(z)]
        if self.k_sparse:
            if sp is None:
                raise ValueError("decoder built with k_sparse>0 but no sparse input")
            parts.append(self._sparse_prefix(sp))
        if self.k_s:
            if s is None:
                raise ValueError("decoder built with k_s>0 but no s-vector input")
            parts.append(self.s_proj(s.to(self.device, torch.bfloat16)))
        if input_ids is not None:
            parts.append(self.lm.get_input_embeddings()(input_ids.to(self.device)))
        return torch.cat(parts, dim=1)

    def forward(self, z, input_ids, attention_mask, labels, sp=None, s=None,
                dense_drop=None):
        B, k = z.shape[0], self.n_prefix()
        embeds = self._embeds(z, input_ids, sp, s, dense_drop)
        attn = torch.cat(
            [torch.ones(B, k, dtype=attention_mask.dtype, device=self.device),
             attention_mask.to(self.device)], dim=1)
        lab = torch.cat(
            [torch.full((B, k), -100, dtype=labels.dtype, device=self.device),
             labels.to(self.device)], dim=1)
        return self.lm(inputs_embeds=embeds, attention_mask=attn, labels=lab)

    @torch.no_grad()
    def generate(self, z: torch.Tensor, max_new_tokens: int = 72, sp=None,
                 s=None) -> list[str]:
        self.eval()
        embeds = self._embeds(z, None, sp, s)
        attn = torch.ones(embeds.shape[:2], dtype=torch.long, device=self.device)
        out = self.lm.generate(
            inputs_embeds=embeds, attention_mask=attn,
            max_new_tokens=max_new_tokens, do_sample=False,
            pad_token_id=self.tokenizer.pad_token_id,
            eos_token_id=self.tokenizer.eos_token_id,
        )
        return [t.strip() for t in self.tokenizer.batch_decode(out, skip_special_tokens=True)]

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        self.lm.save_pretrained(path / "lora")
        torch.save(self.proj.state_dict(), path / "projector.pt")
        if self.sparse_proj is not None:
            torch.save(self.sparse_proj.state_dict(), path / "sparse_proj.pt")
        extras = {}
        if self.sparse_gain is not None:
            extras["sparse_gain"] = self.sparse_gain.detach().cpu()
        if self.s_proj is not None:
            extras["s_proj"] = self.s_proj.state_dict()
        if extras:
            torch.save(extras, path / "extras.pt")
        (path / "config.json").write_text(json.dumps(self.config))

    @classmethod
    def load(cls, path: str | Path, device: str = "cuda") -> "SoftPrefixDecoder":
        path = Path(path)
        cfg = json.loads((path / "config.json").read_text())
        inst = cls(model_name=cfg["model_name"], z_dim=cfg["z_dim"], k=cfg["k"],
                   lora_r=cfg["lora_r"], k_sparse=cfg.get("k_sparse", 0),
                   k_s=cfg.get("k_s", 0), s_dim=cfg.get("s_dim", 192),
                   sparse_fix=cfg.get("sparse_fix", False), device=device)
        from peft import PeftModel
        base = inst.lm.get_base_model()
        inst.lm = PeftModel.from_pretrained(base, path / "lora").to(device)
        inst.proj.load_state_dict(torch.load(path / "projector.pt", map_location=device))
        if inst.sparse_proj is not None:
            inst.sparse_proj.load_state_dict(
                torch.load(path / "sparse_proj.pt", map_location=device))
        ex_path = path / "extras.pt"
        if ex_path.exists():
            extras = torch.load(ex_path, map_location=device)
            if inst.sparse_gain is not None and "sparse_gain" in extras:
                with torch.no_grad():
                    inst.sparse_gain.copy_(extras["sparse_gain"])
            if inst.s_proj is not None and "s_proj" in extras:
                inst.s_proj.load_state_dict(extras["s_proj"])
        return inst


def batch_iter(n: int, bs: int, shuffle: bool, seed: int = 0):
    idx = np.random.default_rng(seed).permutation(n) if shuffle else np.arange(n)
    for i in range(0, n, bs):
        yield idx[i:i + bs]
