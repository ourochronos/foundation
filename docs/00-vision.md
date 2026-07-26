# Vision

## The program

Modern LLMs entangle three functions in one set of weights: translating between language and internal representations, reasoning over those representations, and storing world knowledge. This project tests whether they can be **separated** — and whether the separation buys capability-per-parameter, interpretability, and continuous learning.

- **Codec** — NL ↔ latent translation, built first and frozen early. Every latent a downstream component produces remains *decodable to language* — the interpretability window Coconut-style latent reasoning lacks.
- **Reasoner** — a small, ultra-wide model with weight tying and dynamic recurrence: serial depth comes from looping a shared core, not from unique layers. Surprisal signals govern how long to think and what to remember.
- **Knowledge store** — external associative memory addressed through latent-space operations (anchors + rotations). Knowledge additions are writes, not weight updates.

## Falsifiable theses

- **T1 — Separability.** NL↔latent translation can be decoupled from reasoning: a reasoner over a *frozen* codec matches text-CoT baselines on toy multi-step tasks. Measured by cycle-consistency drift and end-task accuracy.
- **T2 — Novel expression via algebra.** The encoder's empirical manifold is not the boundary of expressible meaning: (anchor, rotation) operations reach novel-but-decodable latents. Measured by anchor-spanning coverage and bind-then-decode accuracy (see [03-latent-algebra.md](03-latent-algebra.md)).
- **T3 — Knowledge externalization.** Moving declarative facts to an external store preserves task performance at substantially reduced parameter count. Measured small+store vs. larger dense on knowledge-intensive tasks.
- **T4 — Depth on demand.** Weight-tied recurrence + surprisal halting yields accuracy that scales with inference-time loop count.
- **T5 — Continuous learning.** Surprisal-gated writes acquire new knowledge non-destructively: no catastrophic forgetting on sequential domain streams, no weight updates.
- **T7 — The self-training ladder (added 2026-07-26).** The system trains itself dynamically at four timescales, and every learned component is taught by a closed-form teacher the store itself provides: fast WRITES (entries; ground truth) → medium CLOSED-FORM re-derivation (operators, participation types, signatures, co-occurrence schema — J4: zero-retrain transfer) → slow DISTILLATION (heads trained from store-derived labels; oracle-walks→BC; resolver/canonicalizer→learned versions later) → glacial CRYSTALLIZATION into weights (D39's dial). "Truly learning" = this ladder running continuously over a growing store. Identity pointers (eids) and canonical relations are CACHES of derivable equivalence structures (M2 tests recoverability) — efficiencies, not external scaffolding, exactly as promotion is a cache of store content.
- **T6 — The crystallization spectrum (added 2026-07-25).** Every knowledge system allocates content between CRYSTALLIZED (weights: instant, fused, uneditable — acquisition ~1000 exposures/fact, capacity ~2 bits/param, staleness terminal) and EXTERNALIZED (store: addressed, edited, view-conditioned — one write, ~128 B/key, a retrieval per use). Frontier models are the fully-crystallized pole with the dial welded. Three things are MANDATORILY crystallized: the shared basis (the anchor-level coordinate system both model and store must natively speak — the KB's coordinate frame, not its content), the procedures (codec, detection, planning, halt/abstain), and an optional hot cache under an explicit promotion policy (promote when frequency × retrieval-cost saved > crystallization cost + staleness risk; the store stays CANONICAL after promotion, so weights are a cache with a backing store — reversible, flaggable stale, demotable; the frontier pole is a cache with no backing store). **Governing invariant: basis reduction is bounded by full expressivity — the shared core may shrink only while complete expression over KNOWN AND NOVEL content is preserved, and the SIZE an expression requires (bits of basis + symbols per proposition; first data point D28: ~9 bits of anchor identity + identity tokens) is a first-class measured quantity.** T3 becomes two dial settings compared; T5 is the externalized pole's native motion. Gate: the promotion/staleness demonstration (both poles instrumented in one system) and the basis-floor curve (interface + expressivity vs shrinking N).

## North star

A ~1B-class reasoner + external store that (a) matches a several-times-larger dense model on knowledge-heavy reasoning, and (b) can be told a new fact once, at inference time, and use it reliably thereafter.

## Design principles

1. **Codec quality gates everything.** If the interface is lossy or brittle, every upstream failure becomes uninterpretable. Hence codec-first, with hard exit criteria.
2. **Probes before commitments.** Cheap falsifiable experiments (days) before architectural bets (months). Each phase has explicit go/no-go measurements.
3. **Prior-art honesty.** Close relatives exist for each component (LCM/SONAR-LLM, Titans, memory layers, Mixture-of-Recursions, TRM). The novel bets are the *combination*, the anchor/rotation addressing algebra, and the identity-channel latent. Track the literature in [references.md](references.md); don't rediscover.
4. **Local-first.** Everything runs on the RX 9070. Bonsai-27B generates reasoning traces locally.

## Risk register

| Risk | Mitigation |
|------|------------|
| Off-manifold latents decode to garbage (LCM's core failure) | Noise-trained decoder; algebra-closure requirement (R5); train-through-decoder loss (SONAR-LLM lesson) |
| Latent CoT has not yet beaten token CoT anywhere broad | T1 targets *separability*, a contribution independent of beating token CoT |
| Retrieval precision bottleneck — bad recalls poison reasoning | Phase-2 gates on retrieval precision before reasoner integration |
| "Knowing what to query" floor — some knowledge must stay in weights | Accept a floor; measure where it is, don't assume zero |
| Wide-shallow may be FLOP-inefficient for token prediction | Width serves binding/working-memory, not token prediction; verify at FLOP parity |
| Anchor inventory drift under continual learning | Open problem, tracked in 03/04; not needed for Phase 1 |
