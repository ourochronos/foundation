# Latent reasoner — ultra-wide, weight-tied, dynamically recurrent

*Intentionally thin until Phases 1–2 land; this records the shape of the bet and its precedents.*

## Shape

- **Ultra-wide, few unique blocks, weight-tied, looped.** Serial depth comes from recurrence over a shared core, not unique layers. Width is prioritized because binding/superposition capacity lives in width (FHRR capacity ~linear in d) — width serves *working memory*, not knowledge storage (knowledge is external, see [04](04-memory.md)).
- **Operates on codec latents** (one latent ≈ one thought), reading/writing the external store via the rotation algebra.
- **Dynamic recurrence depth** — think longer on harder steps.

## Surprisal, triple duty

1. **Halting**: loop until surprise (prediction error / state change) falls below threshold — think-harder-when-surprised (ACT/Universal Transformer lineage).
2. **Memory-write gate**: high surprise → worth storing (Titans lineage).
3. *(Speculative)* **Branch trigger**: high surprise → widen search over next-thought candidates rather than deepen.

## Precedents

| Work | Evidence provided |
|------|-------------------|
| Universal Transformer ([arXiv:1807.03819](https://arxiv.org/abs/1807.03819)) | weight-tied depth recurrence + adaptive halting trains |
| Recurrent-depth latent reasoning ([arXiv:2502.05171](https://arxiv.org/abs/2502.05171)) | 3.5B model loops a core block; test-time compute scales reasoning in latent space |
| Mixture-of-Recursions (2025) | token-level dynamic recursion depth with shared weights |
| TRM / HRM (2025) | tiny recursive models beat much larger ones on hard puzzles |
| Coconut ([arXiv:2412.06769](https://arxiv.org/abs/2412.06769)) | latent CoT can encode superposed alternative next steps (BFS-like) |
| SONAR-LLM ([arXiv:2508.05305](https://arxiv.org/abs/2508.05305)) | train through a frozen decoder with token CE to keep generated latents decodable |

## Training sketch

1. **Trajectory supervision first**: encode each step of text CoT traces into latent sequences (the codec provides free supervision); train next-thought prediction with token-CE through the frozen decoder + latent-space regression.
2. Curriculum toward dropping text scaffolding (Coconut-style stage schedule).
3. Search/RL over latent trajectories only after supervised competence.

## Known hard parts

- Backprop through variable-depth unrolls (truncated BPTT; random-depth training à la recurrent-depth; DEQ-style fixed-point methods as fallback).
- FLOP-parity honesty: wide-shallow recurrent vs. standard decoder baselines at matched compute, not matched params.
- Halting calibration (premature convergence = shallow reasoning; the failure mode of ACT-style halting).
