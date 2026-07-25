# References

Prior work we plan to leverage or are considering, grouped by component. Status: **[leveraging]** = design depends on it, **[considering]** = candidate approach, **[context]** = shapes thinking / risk map.

> Link hygiene: arXiv IDs marked ✓ were verified this session; unmarked ones are from memory — spot-check on first serious use and fix here if wrong.

## Codec & embedding inversion (docs/02)

- **[leveraging]** BGE-M3 (BAAI, 2024) — [arXiv:2402.03216](https://arxiv.org/abs/2402.03216). Multi-functional embeddings: dense + sparse lexical + multi-vector from one pass. The sparse output is our identity channel.
- **[leveraging]** vec2text — "Text Embeddings Reveal (Almost) As Much As Text" (Morris et al., EMNLP 2023) — [arXiv:2310.06816](https://arxiv.org/abs/2310.06816). Iterative embedding inversion; near-exact recovery for ~32-token inputs. Diagnostic baseline + evidence short-text reconstruction is feasible.
- **[leveraging]** Whitening sentence representations (Su et al., 2021) — [arXiv:2103.15316](https://arxiv.org/abs/2103.15316). Isotropization of anisotropic embedding cones; prerequisite for rotation algebra (R5).
- **[leveraging]** SONAR-LLM (2025) — [arXiv:2508.05305](https://arxiv.org/abs/2508.05305) ✓. Token-CE **through a frozen decoder** fixes embedding-space training brittleness — our planned upstream training signal.
- **[considering]** SONAR (Meta, 2023) — [arXiv:2308.11466](https://arxiv.org/abs/2308.11466). Decodable-by-construction sentence embeddings; fallback encoder if BGE-M3 misses fidelity targets (D2).
- **[considering]** ICAE — In-Context AutoEncoder (2023) — [arXiv:2307.06945](https://arxiv.org/abs/2307.06945); Gist tokens (2023) — [arXiv:2304.08467](https://arxiv.org/abs/2304.08467). Text → few soft tokens in LLM embedding space; alternative codec family.
- **[context]** CALM — Continuous Autoregressive Language Models (2025, no ID recorded). Autoregression over robust autoencoder latents at scale; validates noise-injection + variational regularization for R1.

## Latent-space reasoning (docs/00, 05)

- **[leveraging]** Coconut — "Training LLMs to Reason in a Continuous Latent Space" (Meta, 2024) — [arXiv:2412.06769](https://arxiv.org/abs/2412.06769) ✓. Latent CoT works; thoughts can superpose alternatives (BFS-like). Entangled codec — our thesis is the decoupling.
- **[leveraging]** LCM — Large Concept Models (Meta, 2024) — arXiv:2412.08821. The direct precedent: frozen SONAR codec + embedding-space reasoner. Its failure modes (off-manifold decoding, fluency) define our R1/R5.
- **[context]** Latent CoT causal-structure study (2026) — [arXiv:2602.08783](https://arxiv.org/abs/2602.08783) ✓; Abstract latent CoT (2026) — [arXiv:2604.22709](https://arxiv.org/abs/2604.22709) ✓. Active-field markers; re-survey at Phase 3.
- **[context]** CODI (self-distilled continuous CoT); HybridCoT (interleaved latent/text) — from 2025–26 literature; IDs not recorded.

## Binding algebra — anchors & rotations (docs/03)

- **[leveraging]** RotatE (2019) — [arXiv:1902.10197](https://arxiv.org/abs/1902.10197). KG relations as complex rotations; composition/inversion/symmetry for free. Blueprint for relational memory addressing.
- **[leveraging]** RoPE / RoFormer (2021) — arXiv:2104.09864. Rotation composition preserving usable structure in transformer latents, at scale.
- **[leveraging]** HRR — Holographic Reduced Representations (Plate, IEEE TNN 1995) and FHRR (Fourier variant). Phasor binding = block-diagonal rotations; decades of capacity theory (capacity ~linear in width → ultra-wide reasoner bet).
- **[context]** VSA capacity theory (Frady et al., 2018); Kanerva's hyperdimensional computing survey (2009). Superposition capacity math.
- **[leveraging]** Orthogonal Procrustes (Schönemann, 1966). Closed-form optimal rotation between paired point sets — the Phase-1.5 relational probe.

## External memory & continual learning (docs/04)

- **[leveraging]** Titans (Google, 2025) — [arXiv:2501.00663](https://arxiv.org/abs/2501.00663). Gradient-surprise-gated test-time memory; precedent for surprisal-gated writes.
- **[leveraging]** Memory Layers at Scale (Meta, 2024) — [arXiv:2412.09764](https://arxiv.org/abs/2412.09764). Sparse KV memory beats dense params for factual capacity; supports T3's economics.
- **[context]** kNN-LM (2019) — arXiv:1911.00172; RETRO (2021) — arXiv:2112.04426; Product-Key Memories (2019) — arXiv:1907.05242. Similarity-addressed retrieval lineage; ours differs by relational (rotation) addressing.

## Recurrence & adaptive compute (docs/05)

- **[leveraging]** Universal Transformer (2018) — [arXiv:1807.03819](https://arxiv.org/abs/1807.03819); ACT (Graves, 2016) — arXiv:1603.08983. Weight-tied depth recurrence + learned halting.
- **[leveraging]** Recurrent-depth latent reasoning (Geiping et al., 2025) — [arXiv:2502.05171](https://arxiv.org/abs/2502.05171). 3.5B looped-core model; test-time compute scaling in latent space; random-depth training recipe.
- **[considering]** Mixture-of-Recursions (2025) — arXiv:2507.10524. Token-level dynamic recursion depth with shared weights.
- **[context]** TRM — Tiny Recursive Models (2025) — arXiv:2510.04871; HRM — Hierarchical Reasoning Model (2025) — arXiv:2506.21734. Tiny recursive nets beating large models on puzzles; existence proofs for capability-per-parameter via recurrence.

## Minimal concept inventories (docs/03 anchor minimization)

- **[context]** Longman Defining Vocabulary — ~2,000 words define the entire dictionary; existence proof for small compositional bases.
- **[context]** "The Latent Structure of Dictionaries" (Vincent-Lamarre et al., 2016) — dictionary digraphs have a small grounding kernel (~10% of vocab, reducible) from which all words are definable. Formal analogue of anchor minimization.
- **[context]** Natural Semantic Metalanguage (Wierzbicka) — ~65 semantic primes; lower-bound marker.

## Datasets & data generation (docs/02)

- **[leveraging]** Claude Haiku 4.5 (`claude-haiku-4-5`, 200K ctx, $1/$5 per MTok) via **Message Batches API** (50% off → $0.50/$2.50; ≤100k requests/batch, async ≤24h) — primary proposition generator.
- **[leveraging]** GSM8K (2021) — arXiv:2110.14168 — rationale sentences; open CoT corpora (survey at data-prep time).
- **[context]** Bonsai-27B (prism-ml, 1-bit Qwen3.6-27B) — local fallback generator; see `bonsai.sh`.


## Added 2026-07-25 (six-agent research sweep — full reports in session record)

**Latent/looped reasoning**: Coconut (2412.06769); DiscoLoop (2607.00341 — independent D26-law confirmation, internal-embedding variant); Limits of Continuous CoT (OpenReview UQFTJPqJAc); Reasoning by Superposition (2505.12514 — continuous IS better for parallel search); CODI (EMNLP 2025 — distill explicit teacher into latent steps); Huginn recurrent-depth (2502.05171 — randomized-unroll training); Ouro LoopLM (entropy-regularized exit); Adaptive Depth diagnosis (2607.20519 — readouts beat learned halting gates); Loop, Think & Generalize (2604.07822 — overthinking failure); CoLT (2602.04246 — latent deliberation, discrete tool calls); LatentRAG (2605.06285 — continuous subqueries against a retriever).

**Memory/editing**: Titans (2501.00663 — surprise needs momentum + decay); ATLAS (2505.23735 — write windows, not per-token); Nested Learning/HOPE (2512.24695 — frequency-tiered consolidation); Memory Layers at Scale (2412.09764 — the T3 anchor: ~100% factual-QA gain at equal compute); Knowledge Capacity Scaling Laws (2404.05405 — ~2 bits/param, ~1000 exposures/fact); AlphaEdit (2410.02355) + repro study (2606.26783 — lifelong ceiling); WISE (2405.14768); Supersede (2606.27472 — names the memory-update gap; FAMA metric); HippoRAG 2 (2502.14802 — baseline to beat); MemoryAgentBench (2507.05257); LongMemEval (2410.10813); NextMem (2603.15634 — nearest latent-store neighbor, no operators); TransE (NeurIPS 2013 — operator ancestry).

**Retrieval-native**: Stop-RAG (2510.14337 — Q(λ) stop head); CoRAG (2501.14342 — rejection-sampled hop traces); When Iterative RAG Beats Ideal Evidence (2601.19827 — anchor-carry drop = our hand-off, named); GRAIL (2605.28641 — closest query-arithmetic competitor); DGPO (2508.20324 — THE sub-1B recipe: distill then guided RL; pure RL dead); ToolOrchestra (2511.21689); StepSearch/GiGPO lineage (per-step rewards); MuSiQue/FRAMES/GRADE (2508.16994) for external eval.

**Codec/alignment**: LCM (2412.08821 — codec-boundary failures we route around); SONAR-LLM (2508.05305); CALM (2510.27688); 500xCompressor (2408.03094 — compression SOTA context); Sentence-Anchored Gists (2511.08128); vec2text (2310.06816); vec2vec (2505.12540) + mini-vec2vec (2510.02348 — linear maps suffice); Procrustes Bounds (2510.13406 — theorem for backbone transfer); Token Assorted (2502.03275); DLR (2606.29712 — discrete-beats-continuous for recoverability).


## Added 2026-07-25 (Northstar sweep: compute, ingestion, training-eff)

**Compute/ALU**: TAT-QA/TagOp (2105.07624 — op-classifier + exact execution at 125M, the proven small-scale shape); Replacing Thinking with Tool Usage (2507.05065 — constrained DSL beats free-form at ≤3B); QPL (2310.13575 — plans of simple operators beat monolithic code, more so for small parsers); WNSMN (2101.11802 — op-policy trains from answer-only reward); action masking (2602.10598); NALU→DMU lineage (learned arithmetic still failing, 2509.08180); PAL/CodeAct (big-model pattern).

**Ingestion**: APS (2406.19803 — segmentation solved at 2B); Sub-Billion Super-Frontier (2606.22606 — distilled 0.5B F1 0.83 beats prompted frontier on RE); EDC (2404.03868); ATOM (2510.22590 — atomic facts + bi-temporal); KGGen/Wikontic (MINE benchmark); SAGE (2605.30711 — three-way novelty write gate); deterministic freshness (2606.01435 — +28pts over LLM arbitration); Supersede (2606.27472) + Mem0 18% FactConsolidation = the open gap our supersession targets; EMERGE (2507.03617 — the streaming-edit benchmark).

**Training-eff**: bitsandbytes 0.50.0 (gfx1201 validated; paged/8-bit optimizers BROKEN on HIP — adamw_torch); Unsloth official AMD Full-tier incl. WSL; Level1Techs gfx1201 QLoRA field report (5 bugs + workarounds); SONAR-LLM objective sample-efficiency; ALGEN-lineage decoder alignment (1k–8k pairs vs 5M from scratch); u-μP / Cerebras-GPT HP transfer.
