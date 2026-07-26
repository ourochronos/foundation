# Covalence survey (agent report, 2026-07-27) — EKB lineage prior art

Commissioned per user: "Covalence in the Ourochronos GitHub org is the
latest successor of EKB... gives good insight into the story of that work."
Lineage: EKB → valence → valence-v2 → valence-engine → covalence v1 →
Covalence v2 (Rust/Axum/petgraph over PostgreSQL 17 + pgvector + AGE).

## The five transferable insights (agent's distillation)
1. Blanket LLM extraction is a dead end — gate by embedding novelty; make
   the stored unit a SELF-CONTAINED, coref-resolved statement (post-hoc
   filters are never complete; 29k flat claims = noise + 90% of API cost).
2. Belief change = INVALIDATION, never deletion (bi-temporal edges,
   two-pointer supersession chains) — buys "what was believed at T."
3. Epistemic sophistication has a complexity budget: SL opinion tuples
   (belief/disbelief/uncertainty/base_rate; "unknown ≠ 50%") and TYPED
   conflict edges (CONFIRMS/CONTENDS/CONTRADICTS/SUPERSEDES/CORRECTS)
   earned their keep; stacking five frameworks caused belief OSCILLATION.
4. Design federation INTO THE SCHEMA day one, defer the protocol
   indefinitely: clearance levels on every row (most-restrictive
   inheritance), is_synthetic flags, ALGORITHM ISOLATION (public scores
   computed only on public subgraphs — confidence is a side channel),
   DUAL SYNTHESIS (public views generated independently, not redacted).
5. The spec is the continuity layer across rewrites; velocity without an
   operator is a stall mode (26 agent-driven waves in a month, then
   silence right after adding heavyweight process).

## Resonances with foundation (convergent, independently measured here)
- statements-as-primitive ↔ our proposition-level triple-latent entries
- invalidate-never-delete ↔ D33/D55 supersession + shadow
- views as perspectives over ONE shared graph (MAGMA-derived, both
  projects) ↔ Track I / D60; their split into domains vs clearance vs
  views refines D40's tiers
- hybrid multi-dimensional retrieval beats graph-only ↔ our hybrid law
- 5-tier entity resolution + residual pool ↔ D49/D52 (their HDBSCAN
  residual pool ≈ our deferred split-repair pass)

## Key files in the repo (cloned in session scratchpad)
VISION.md · spec/10-lessons-learned.md (22 lessons — densest) ·
spec/02-data-model.md · spec/07-epistemic-model.md · spec/09-federation.md ·
docs/adr/0022-knowledge-primitives.md (7 primitives: Entity, Relationship,
Source, Observation, Opinion, View, Schema) · MILESTONES.md

Full agent report in the session record; EKB DB backup (the data ancestor)
at ~/backups/ekb-20260727/.
