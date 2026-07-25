# foundation

Research program: decompose language-model capability into three separable parts —

1. a **language codec** (NL ↔ latent encoder/decoder),
2. a **latent reasoner** (small, ultra-wide, weight-tied recurrent core that thinks in latent space, CoT/Coconut-style),
3. an **external knowledge store** (addressed through latent-space operations — anchors and rotations — rather than baked into weights).

The bet: a small model with less knowledge distilled into its weights can match much larger dense models on knowledge-intensive reasoning, while gaining continuous learning — new knowledge is written to the store at inference time, not trained in.

**Status**: Phase 1 complete, Phase 1.5 gate resolved. Corpus **16,079 propositions / 56 domains** + **2,822 transformation pairs / 23 types**, all generated locally.

1. **Fidelity — the hybrid latent works (D21/D22).** The shipping decoder (`decoder_v2t`) conditions on the full triple `[gist ; slot-tagged symbolic identities ; structure s-vector]`: entity EM 0.46, number EM **0.72**, cycle cosine 0.81 — roughly double the dense-only decoder at the same corpus (0.203 / 0.336 / 0.619) — and identity fidelity is **noise-immune by construction** (number EM 0.725 at gist noise σ=0.5, where dense-only fell to 0.32), resolving the founding R1↔R3 tension. Per-channel shuffled attribution confirms the sparse channel carries the identities (shuffling it → ~0) and the s-vector carries binding (+0.03 role fidelity). D21's residual — right values in wrong slots — was cut by fusing each number with its parse head at encode time (D22: mis-attachment given presence 28.6% → 20.5%); the remaining ceiling is tag coverage, not method. Earlier scaling account: entity EM 0.115 → 0.178 → 0.203 across three like-for-like corpus points, no saturation (D10); the latent is traversable — off-manifold points decode fluently, losing fidelity rather than form (D19).
2. **Structure — channel v2 achieves the full ordering (D14–D18, D20).** Three mechanisms, combined per-pair by `min`: a linear valence subspace, a trained token-level pooler, and symbolic role bits. Every meaning-changing transformation now sits below every meaning-preserving one, at **pair-level AUC 0.942**, and it transfers to preserving constructions it never trained on (cleft, nominalization, contraction — 0.912). The result replicates across an independently refit embedding space (10.5k → 16k corpus). Binding was solved symbolically (argument_swap 0.98→0.59, causal_reverse 0.97→0.35). The **valence family** separates via a closed-form linear rebalance of BGE-M3 space (ordering AUC 0.705 → **0.866**); the **structural family** has *content-conditional* displacements, provably invisible to any fixed map over the pooled vector, which is what the token-level pooler and the parse-based role bits exist to catch. First confirmed latent operations are translations (negation = a steering vector, 100% held-out).

Rotations unsupported as a binding operator at both lexical and proposition altitude (D4). Details in [docs/02-codec.md](docs/02-codec.md), [docs/03-latent-algebra.md](docs/03-latent-algebra.md), [docs/decisions.md](docs/decisions.md), `results/`.

## Layout

| Path | What |
|------|------|
| `docs/` | Vision, roadmap, component specs, decision log |
| `models/` | Local GGUF models (Bonsai-27B — used as a local CoT-trace generator) |
| `llama.cpp/` | PrismML llama.cpp fork (HIP build) serving Bonsai |
| `bonsai.sh` | Runner for Bonsai-27B (chat / vision / serve / one-shot) |
| `gpu_check.py` | PyTorch ROCm sanity check |
| `.venv/` | Python 3.12 + torch 2.13 ROCm 7.2 |

## Environment

AMD RX 9070 (16 GB, gfx1201), ROCm 7.2, WSL2. All training/inference local.

```bash
source .venv/bin/activate
python gpu_check.py          # verify GPU
./bonsai.sh -p "hello"       # one-shot local LLM
```

Start reading at [docs/00-vision.md](docs/00-vision.md).
