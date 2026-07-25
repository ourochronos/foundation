# Codec v0 — NL ↔ latent

The codec's job is not reconstruction alone: it must produce a latent space a *reasoner can operate in* and a decoder that stays reliable on latents the encoder never emitted.

## Requirements

- **R1 — Noise robustness.** `decode(z + ε)` degrades gracefully. A reasoner's outputs are predictions near, never on, the encoder manifold. Metric: reconstruction quality vs. noise σ (a curve, not a number).
- **R2 — Cycle consistency.** `encode(decode(z)) ≈ z`. Keeps latent-space and text-space reasoning in registration; k-round-trip drift is the falsifiable core of thesis T1.
- **R3 — Identity/value fidelity.** Names, numbers, dates survive round-trips exactly. Contrastive dense embeddings are weakest precisely here; the sparse lexical channel is the countermeasure.
- **R4 — Proposition-sized units.** One latent ≈ one thought (≤ ~64 tokens). Short text is the regime where faithful reconstruction is achievable and reasoning steps are naturally this size.
- **R5 — Algebra closure** *(added for anchors/rotations)*. The decodable set must be closed under the operations the reasoner will use. Gaussian-noise robustness (R1) does not imply tolerance to *structured* transforms; test rotations explicitly.

## Architecture

```
text ──► BGE-M3 (frozen) ──► dense d1024 ─┐
                    └──► sparse lexical ──► top-k pooler ─┤
                                                          ▼
                                    whitening → adapter MLP → unit-norm z
                                                          │
                              MLP projector → k=8–16 soft prefix tokens
                                                          ▼
                                 decoder LM (≈0.6B, LoRA) ──► text
```

Notes:
- **Whitening before the adapter.** Contrastive embedding spaces are anisotropic (narrow cone). Rotation-based operations presuppose dimensions are used symmetrically, so isotropization is a *prerequisite for R5*, not a nicety. Track isotropy metrics as first-class evals.
- **Adapter** gives gradients a place to reshape the space (smoothness, isotropy) without retraining BGE-M3 or losing its pretrained semantics/multilinguality.
- **Sparse channel** carries identities: exact tokens ("$103.50", "Zylkorp") with weights, order-free. Dense carries gist. The split resolves the smooth-continuous vs. discrete-exact tension: the reasoner operates mostly on the gist channel; identities behave symbolically.
- **Decoder conditioning** via soft prefixes; train with noise injection σ ~ U(0, σ_max) on z (R1), later add cycle loss (R2) and token-CE through the frozen decoder when training upstream components (SONAR-LLM lesson).

## Training data

Sentence-split reasoning traces (GSM8K rationales, open CoT sets), general sentences for coverage, plus generated thinking-register propositions. **Primary generator: Haiku subagents run in the background from Claude Code sessions** (subscription-covered, no API billing) — parallel agents with distinct register briefs (math steps, factual, procedural, causal, narrative, finance) writing labeled JSONL to `data/propositions/`; each line carries `text` + verbatim `entities` and `numbers` lists so the fidelity evals have ground truth. Generation prompts deliberately request entity/number-dense propositions. Scale-up option if needed: Message Batches API at $0.50/$2.50 per MTok. Local Bonsai-27B remains the offline fallback. Dedupe, length-bucket, keep ≤64-token propositions as the core distribution. Caveat: entity/number labels are generator-self-reported; the eval harness re-validates them against the text (verbatim-substring check) and drops mislabeled ones.

## Evaluation harness (build first)

| # | Probe | Measures | Requirement |
|---|-------|----------|-------------|
| 1 | Entity/number exact-match by length bucket + semantic sim | fidelity | R3, R4 |
| 2 | Quality vs. Gaussian σ curve | robustness | R1 |
| 3 | Interpolation coherence (decode midpoints of thought pairs) | smoothness | R1 — ✓ D19: endpoints 0.58 → midpoint 0.30 round-trip cos, smooth V, fluent at every t (decoder projects off-manifold points) |
| 4 | k-round-trip drift ‖encode(decode(z)) − z‖ and semantic drift | registration | R2 |
| 5 | Isotropy (eigenspectrum, mean pairwise cosine) | space health | R5 prereq |
| 6 | Rotation tolerance (random small-angle block rotations → decode) | structured robustness | R5 |
| 7 | Anchor spanning (see [03](03-latent-algebra.md)) | expressiveness | T2 |

## Milestones

- **M1** — harness + dense-only baseline (no sparse channel, no noise training): quantifies the identity-loss problem.
  - *2026-07-22, first cut (seed corpus n=1148, `results/baseline_v0.json`)*: pipeline runs end-to-end on the RX 9070. Isotropy: whitening opens the BGE-M3 cone from mean|cos| 0.351 → 0.033 (effective rank 212 → 438/1024) — R5's prerequisite behaves as theorized, provisional while n < 4d. Anchor probe (whitened): nearest-anchor-alone cosine ≈ 0.23–0.26 (N=64–256), free-phase-rotation ceiling ≈ 0.80 and insensitive to N at this scale — large headroom for the rotation algebra; constrained-family fit (Phase 1.5) will locate the achievable point inside [0.26, 0.80]. Sparse channel alive: ~20 active tokens/proposition, none empty. Decoder-dependent evals (#1–4, #6) pending decoder v0.
- **M2** — +sparse channel ablation: how much of the gap closes. *First attempt (decoder v1) invalid — the channel was ignored for lack of gradient pressure (D10); redo inside codec v2 with the D10 fixes and per-channel shuffled attribution.* **← next (as codec v2)**
- **M3** — noise-trained decoder: robustness curve before/after. ✅ (eval #2: ~94% at latent cos 0.89)
- **M4** — probe report (evals 5–7) → go/no-go input for the algebra (Phase 1.5 gate). ✅ resolved: rotations rejected, translation-first + structure channel (D15–D20; see [03](03-latent-algebra.md)).

### Decoder v0 results — 2026-07-22 (`results/decoder_v0_eval.json`, `conditioning_v0.json`)

Corpus 4,859 propositions / 16 domains; Qwen3-0.6B + LoRA, k=16 soft prefix, noise-trained σ~U(0,0.4); 1,656 steps, final train loss 0.029. **Latent is dense-only — this is the M1/M2 ablation's dense arm; the sparse identity channel is not yet wired into the decoder.**

**The founding hypothesis is confirmed quantitatively.** Gist survives, identities do not:

| metric | value |
|---|---|
| exact text reconstruction | **0.0%** |
| entity exact-match | **11.8%** |
| number exact-match | **18.2%** |
| cycle cosine (k=1) | **0.467** |

Reconstructions are topically faithful and specifically wrong — e.g. *"magnetic field reached 5 Tesla, electron trajectories curved inward with a radius of 2.3 cm"* → *"magnetic field reached 5.3 Tesla, the electron's critical frequency jumped by a factor of 4.4."* Right concepts, confabulated values. This is exactly the failure the sparse channel (D3) exists to fix, now with a number to beat.

**Conditioning control (D8).** The first σ sweep looked suspiciously flat (0.125 → 0.117 over σ∈[0,0.5]), which is ambiguous between "robust" and "ignores the latent." Cause: **σ must be read as latent cosine**, `cos ≈ 1/√(1+σ²)` — σ=0.5 is cos 0.89, a trivial perturbation. Re-run wide, plus shuffled/random-latent controls:

| condition | latent cos | entity EM | number EM |
|---|---|---|---|
| σ=0 | 1.00 | 0.118 | 0.182 |
| σ=0.5 | 0.89 | 0.111 | 0.172 |
| σ=1 | 0.71 | 0.092 | 0.131 |
| σ=2 | 0.45 | 0.020 | 0.062 |
| σ=4 | 0.24 | 0.000 | 0.036 |
| **shuffled z** | — | **0.000** | **0.029** |
| **random z** | — | **0.000** | **0.018** |

Shuffled-latent cycle cosine is **−0.009** vs **0.467** for the true latent. **Conditioning confirmed** — the decoder genuinely reads z; it is not sampling from a prior. And R1 holds: quality is ~94% retained at latent cos 0.89 and ~75% at 0.71, collapsing only below ~0.45. That is real headroom for a reasoner whose predicted latents land near, not on, the manifold.

*Method note*: always report the noise axis as latent cosine, not raw σ, and always include a shuffled-input control.

### M2 ablation + diagnosis — 2026-07-22 (`decoder_v1_eval.json`, `memorization_decoder_v1.json`, `identity_info_probe.json`)

**M2 result: the sparse channel as implemented is ignored.** v1 = dense + 24 sparse identity slots, same schedule. Headline deltas look mildly positive (number EM 0.174 → 0.207, entity EM 0.115 → 0.115) — but per-channel attribution kills that reading:

| condition | entity EM | number EM |
|---|---|---|
| both correct | 0.115 | 0.207 |
| **sparse shuffled** (identities wrong) | **0.110** | **0.208** |
| dense shuffled (gist wrong) | 0.005 | 0.021 |
| both shuffled | 0.005 | 0.021 |

Shuffling the identity channel changes nothing; shuffling gist destroys everything. The decoder reads dense only. Without this control the +3-point number-EM delta would have been reported as the sparse channel working. Likely causes: (a) **no gradient pressure** — dense alone drives train loss to 0.02, so the model never needs the identity channel; (b) **scale** — the sparse prefix's mean norm is 0.27× the dense prefix's (lexical weights 0.05–0.3 shrink the pooled embeddings).

**Diagnosis: the codec is memorization-bound, not information-bound.**

| split | exact | entity EM | number EM |
|---|---|---|---|
| **train** | **0.990** | **1.000** | **0.997** |
| eval | 0.000 | 0.115 | 0.200 |

The decoder reconstructs *training* propositions verbatim — numbers, names, everything — and generalizes only to gist. Ambiguous on its own (real readout vs. z-as-index-key), so a **decoder-free linear probe** settles it: ridge regression from whitened dense z → lexical-token presence, fit on train, scored on held-out:

| token class | recall@20 | frequency baseline | lift |
|---|---|---|---|
| **numeric** | **0.809** | 0.390 | **2.08×** |
| non-numeric | 0.591 | 0.244 | 2.42× |

**The identities are in the dense latent.** A *linear* readout recovers 81% of held-out numeric tokens. So the founding hypothesis needs amending: values are not absent from the embedding — they are present but hard to decode, and our decoder overfit 4.4k propositions instead of learning a general readout. This matches the vec2text result that short-text embeddings are far more invertible than they appear.

*Caveat*: token **presence** is weaker than exact value reconstruction (BGE-M3 splits numbers into subword tokens), and 379 numeric tokens with recall@20 is a permissive task. The claim is directional, not that decoding is solved.

**Consequences**: fidelity is a data/regularization problem (tractable — scale the corpus, hold out properly, penalize memorization) and is *separate* from the structural-distinction problem in D9 (which more data will not fix). Fix the sparse channel's gradient pressure and norm scale before re-running M2.

If M1–M3 miss fidelity/robustness targets badly, fallback encoders exist (SONAR — decodable by construction; ICAE/gist-style compressors) at the cost of BGE-M3's sparse identity channel and retrieval geometry. Decision logged in [decisions.md](decisions.md) D2.
