# Anchor basis & reindex-free growth — post-PoC research axes (D84)

User-directed (2026-07-26): two exploration areas, which turn out to be
one architecture.

**Axis A** — a SMALL latent anchor basis with the capability to project
novel content into its coordinates.
**Axis B** — externalized knowledge that dynamically expands the manifold
WITHOUT reindexing existing embeddings.

## The unifying hypothesis (registered)

**Manifold-expansion demand concentrates in TYPE space, which saturates;
identity growth is unbounded but rides the symbolic channel and is
therefore free.** This is the channel-separation law (7 measurements)
pushed to its infrastructure conclusion: if the continuous channel only
carries type-level content (D32: gist is topic-only), then a small,
eventually-frozen anchor basis spans it, and corpus growth almost never
demands new continuous coordinates — it demands new SYMBOLS, which append
trivially. Confirming signature: anchor-minting rate DECELERATES over a
content stream while eid growth stays linear.

Standing results this builds on: D28 (32-anchor projection ≈ true gist
end-to-end; cycle 0.811 vs 0.808), D32 (semantic load on discrete
channels; reasoner state can be radically discrete), D31 constraint
(anchor-codes COLLAPSE retrieval — anchors coordinate the reasoner and
the portable representation layer; store ANN keys stay full-resolution),
D6 (100k over-provision was insurance, minimization deferred = this doc),
J2 seed (`scripts/probe_basis_floor_j2.py`). References: mini-vec2vec
(linear maps suffice), Procrustes bounds (backbone transfer theorem).

## Axis A probes (pre-registered)

- **A1. Expressivity knee on the REAL corpus.** k-means anchors
  N ∈ {8,16,32,64,128,256,512,1024} fit on Wikipedia statement gists;
  metrics: (i) projection residual, (ii) retrieval parity vs full gist
  through the store (P@1 on the frozen KB battery + 100 sampled
  statement-queries), (iii) ask/brief end-to-end parity. **Target: name
  the knee N* where parity is within CI of full-gist; expect O(10^1–10^2)
  per D28.**
- **A2. Novel-coordinate transfer (the "project into novel coordinates"
  claim).** Anchors fit on WIKIPEDIA ONLY, frozen; project ArXiv claim
  gists (OOD domain). Compare residual and retrieval parity against
  anchors fit on wiki+arxiv jointly. **Registered acceptance: parity gap
  ≤ 2 points and residual ratio ≤ 1.5× at N*.** Below → type space
  transfers across domains; above → domain-conditional anchors needed
  (also a finding; feeds B2's minting rule).
- **A3. Operator arithmetic in anchor coordinates.** Translation
  addressing (t_rel) executed on anchor-weight vectors instead of raw
  gists; P@1 parity vs raw-space addressing on the same query set.
  Holds → reasoner state = N*-dim weights + symbols.

## Axis B probes (pre-registered)

The enemy is not the ANN index (HNSW appends fine) — it is GLOBAL
statistics in the coordinate stack: whitener refits, amp subspaces,
pooled caches (the corpus cascade in 06-state invalidates them on every
corpus change), and eventual encoder swaps.

- **B1. Frozen-coordinates drift.** Whitener + anchors fit at snapshot
  T0 (wiki-200 layer), FROZEN; apply to wiki-1000 and the ArXiv stream.
  Measure retrieval parity frozen-vs-refit + isotropy/eff-rank of new
  batches in old coordinates. **Deliverable: the drift curve and a
  decision rule (reindex never / reindex at Δ threshold).**
- **B2. Append-only anchor growth (the manifold-expansion mechanism).**
  Stream ArXiv claims through frozen wiki anchors; when projection
  residual > τ (τ from A2's distribution), MINT a new anchor (local
  centroid); old entries untouched by construction. Measure: residual
  recovery, retrieval parity over the stream, and the KEY curve —
  **anchors minted vs claims seen. Sublinear/decelerating = the
  hypothesis confirms; linear = type space does not saturate and the
  small-basis bet fails (criterion-scored either way).**
- **B3. Encoder-swap insurance (design only, no run).** If BGE-M3 is
  ever replaced: learn the linear bridge old→new ON THE ANCHOR SET ONLY
  (mini-vec2vec result: linear suffices), migrate entries lazily at
  touch-time. Anchors make the bridge's train set canonical and tiny.

## Constraints carried forward

- Anchors never key the ANN store (D31: decode ≠ retrieval resolution).
- Store rows keep full-res vectors + symbolic ids; anchor coordinates
  are a VIEW for the reasoner/portability, not a replacement (D21/D22).
- Every probe ships with a positive control (D8) and per-channel
  attribution where multi-channel (house rules).

## Sequencing

A1 → B1 first (cheap: existing embeddings, one fit each). A2/B2 next
(embeddings already on disk for both corpora). A3 after A1 names N*.
Independent of the 800-page extraction tranche — can interleave.
