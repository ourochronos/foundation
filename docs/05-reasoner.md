# Latent reasoner — spec v2 (C0 rewrite, 2026-07-25)

v1 of this spec predated every Phase-1/2 measurement. This version is written
under empirical constraints; each is cited. The reasoner is no longer a
latent-transformer of thoughts — it is a **control policy over a store**.

## What the measurements fixed

- **State = the triple, discrete-dominant.** Continuous gist is a topic
  pointer only (D32: +0.01 frame contribution); frame and identity ride the
  symbolic/structure channels. Reasoner state: current entry id-set, walk
  bookkeeping (visited, prior subjects), a gist vector it may treat coarsely
  (D28: anchor-resolution suffices for decode), and the question encoding.
- **Actions = hop calls, not latent transforms** (D26/D27/D30): choose
  relation operator (linear readout suffices for selection — B1 1.000, tiny
  core), emit a SELECTIVE hand-off mask over the current entry's id tokens
  (D30: the naive `ids(entry) − ids(source)` mask is the first-order failure
  under collisions), soft demote/exclude preferences (D30 retracted them as
  invariants — they hurt on revisit patterns), HALT, ABSTAIN.
- **Halting/abstention = readouts, not gates** (B2 + literature): halt
  signals separate at ~1.0 AUC on store responses (margin/top1/id-coverage);
  abstain = identity coverage (AUC 0.952). Top-1 absolute score does NOT
  separate answerable from no-answer (D30). Surprisal-as-halting is
  redefined over store responses (margin collapse = confusion); latent
  prediction error is flat by construction (D24) and must not be used.
  Halt-surprisal ≠ write-surprisal (T5) — decoupled.
- **Architecture: small weight-tied recurrent core.** Ultra-wide is retired
  (B1 + D3/D21/D26 moved binding out of the continuous space; the original
  FHRR width argument is void). Loop-count = hop-count instruments T4.
- **Training = distill-then-guided-RL with per-step rewards** (DGPO evidence
  at sub-1B; pure RL there is a documented dead end). Imitation floor = the
  hand-coded oracle, which D30 demoted to a weak baseline with measured
  per-composition floors: cap_pop 0.808, big_pop 0.600, ceo_born 0.370,
  loc_cap 0.270, loc_big 0.327 (walk-off), 3-hop 0.000. The policy has real
  headroom exactly where the oracle fails: selective hand-off under
  collisions, revisit handling, abstention.

## Known hard parts (updated)

- FLOP-parity accounting for the T1 gate must include encoding cost and
  record weight precision on both sides (Track E2).
- Overthinking past training depth is the looped-model failure mode
  (2604.07822); randomized-unroll training (Huginn-style) + readout halting.
- The world's remaining syntheticness (A7 pending) bounds all claims.

## Eval ladder

Per 07-phase3-plan.md C4: clone→held-out compositions→unseen phrasings +
noised latents→FLOP parity vs text-CoT→MuSiQue closed-world (ARC-decomposed
metrics). Environment: `HopEnv` (C1) over `codec/memory_store.py`, world v3.

## Prior art (updated by the 2026-07-25 sweep)

DiscoLoop (discrete anchors between continuous hops — internal-embedding
variant of our D26 law); CoLT/LatentRAG (latent deliberation, discrete
retrieval boundary); Huginn/Ouro (recurrent depth, entropy exit); Stop-RAG
(value-head stopping); DGPO (small-policy training recipe). Full list in
references.md.
