# Latent algebra — anchors & rotations

## Motivation

A fixed embedding topology restricts expression: everything sayable must already have coordinates, and retrieval-trained spaces actively absorb novel things into nearest clusters (the identity-loss problem). The proposal: express meaning as **operations relative to anchors** — `z ≈ R · a (+ residual)` where `a` is a known anchor and `R` a rotation — so novel meanings are reachable as *transformations of known ones* without leaving the decodable set, and so the same algebra can later serve as the **addressing scheme for external memory** (query = rotate an anchor by a relation).

## Why rotations are the right operator family to try first

Three independent research lines converged on elementwise/blockwise rotation as a binding operator:

1. **FHRR (Fourier Holographic Reduced Representations)** — vector-symbolic architectures bind role↔filler by adding phases of unit phasors = block-diagonal 2D rotations. Decades of capacity theory: superposed bindings decode reliably with capacity growing ~linearly in width (supports the ultra-wide reasoner bet).
2. **RoPE** — relative position emerges from composing position-dependent block rotations; proof at scale that rotation composition preserves usable structure in transformer latents.
3. **RotatE** ([arXiv:1902.10197](https://arxiv.org/abs/1902.10197)) — knowledge-graph relations modeled as rotations in complex space; handles composition, inversion, and symmetry patterns — exactly the relational algebra external memory needs.

Properties that matter here: rotations are **invertible** (exact unbinding via transpose), **norm/angle-preserving** (no collapse, stays near the decoder's operating manifold), **composable** (group structure → relation chains), and in high dimensions random rotations yield near-orthogonal results (**superposition headroom**).

## Candidate parameterizations

| Family | Params | Cost | Notes |
|--------|--------|------|-------|
| Block-diagonal 2D (Givens/phasor) | d/2 angles | O(d) | ≡ FHRR/RoPE/RotatE family. **Default.** |
| Cayley transform of low-rank skew-symmetric | rank-controlled | O(dr) | more expressive, tunable capacity |
| Butterfly/FFT-style products | O(d log d) | O(d log d) | dense-ish mixing if block-diag too weak |

## Anchor inventory — over-provision first, minimize later

The base-concept set baked into weights is itself a research axis (how small can it get?), but minimization is **deferred**: start with an inventory small relative to LM embedding tables yet large enough that expressibility is off the table as a failure explanation while the algebra is validated.

- **v0 — over-provisioned, data-derived.** k-means centroids over adapter outputs on the training corpus; sweep N ∈ {1k, 4k, 16k, 64k, 100k}. The 100k ceiling is deliberately robust (still only ~400MB fp32 — well within hardware budget) so expressibility can't confound algebra validation; reported intuitions put the eventual sufficient size in the low thousands. The anchor-spanning probe (codec eval #7) yields the coverage-vs-N curve directly.
- **Later — minimization research.** Candidate methods: coreset/facility-location selection, VQ codebook learning with a size penalty, usage-frequency pruning. Prior art says small bases genuinely can span a language:
  - **Longman Defining Vocabulary** — ~2,000 words suffice to write every definition in the dictionary; an existence proof that a small basis + composition covers the lexicon.
  - **Dictionary grounding-kernel analysis** (Vincent-Lamarre et al., 2016) — digraph analysis of real dictionaries finds a small strongly-connected core (≈10% of vocabulary, further reducible) from which every word is reachable through definitions; the closest formal analogue of anchor minimization.
  - **NSM semantic primes** (Wierzbicka) — a claimed ~65 universal primitives; likely too aggressive for engineering, useful as the floor marker.

  Plausible landing zone spans 10²–10⁴; start at the high end, compress once T2 is validated.
- Learned codebook (VQ-style) replaces k-means only if centroids underperform. Anchor drift under continual learning remains open (tracked, not Phase-1).

## Consequences for the codec (already folded into 02)

- **R5 algebra closure**: decoder must tolerate rotated latents, not just noisy ones.
- **Whitening/isotropy prerequisite**: rotations assume dimensions are used symmetrically; anisotropic cones break the algebra silently.

## Probe plan (Phase 1.5 — cheap, before any architectural commitment)

1. **Rotation tolerance** — apply random small-angle block rotations to z, decode, measure degradation vs. angle. The structured analogue of the noise curve.
2. **Anchor spanning** — with N k-means anchors, fit best-in-family R per held-out sample; measure reconstruction/decode quality vs. N. Tests T2's claim that (anchor, rotation) *spans* expressive space.
3. **Procrustes relational probe** — for a relation with example pairs (subj → obj), orthogonal Procrustes gives the optimal rotation in closed form (SVD). Fit per relation on real sentence embeddings; test generalization on held-out pairs. **Directly measures whether relations act rotationally in the adapted space** — the load-bearing assumption for memory addressing. Days of work, high information.

## Go/no-go

Adopt rotations as the binding operator only if: rotation-tolerance degradation is comparable to Gaussian noise of matched magnitude, anchor-spanning coverage rises convincingly with N, and Procrustes relations generalize above a trivial-baseline margin (numeric thresholds fixed after M1 baselines, then held). Otherwise: iterate the adapter's geometry or evaluate alternative operators before Phase 2.

## Probe results — 2026-07-22 (`results/rotations_v1.json`)

**Instrument validation first.** A v0 probe fitting full `O(1024)` (~524k params) from ~45 pairs/relation returned "rotation loses to identity" — but that was a **capacity artifact, not evidence**. The v1 positive control (synthetic `y = known block rotation of x`, same n) proves it: full-`O(d)` recovers the known rotation at cos **0.01 / 0.09 / 0.60 / 0.98** for d = 1024 / 256 / 64 / 16 — i.e. it cannot fit at all above d≈64. Block-diagonal (d/2 params, the family D4 proposes) recovers at **0.52 / 0.77 / 0.93 / 0.98**. Any cell failing the control says nothing about the hypothesis; always report the control.

**Real relations (10 lexical/encyclopedic relations, ~57 pairs each), block family:**

| d | params | cos: block / trans / identity | top1: block / trans / identity |
|---|---|---|---|
| 1024 | 512 | 0.578 / 0.631 / 0.563 | 0.496 / 0.486 / 0.479 |
| 256 | 128 | 0.397 / 0.492 / 0.370 | 0.489 / 0.467 / 0.489 |
| **64** | **32** | **0.482 / 0.584 / 0.431** | **0.394 / 0.437 / 0.437** |
| 16 | 8 | 0.607 / 0.710 / 0.512 | 0.263 / 0.273 / 0.259 |

**Reading.** At the best-conditioned cell (d=64: 32 params vs 45 pairs, control 0.93) block rotation beats identity on cosine by ~0.05 but is **worse on retrieval**; translation is comparable or better everywhere. Conclusion: **in frozen BGE-M3 + linear whitening, common lexical relations do not act as clean rotations.** Translation's edge echoes word2vec-style additive analogy structure.

**Confound to respect**: the identity baseline is strong (top1 ≈ 0.48, cos ≈ 0.56) — BGE-M3 already co-locates related terms, so the probe has little dynamic range. A relation set where x and y are *not* pre-co-located would be more discriminative.

**What this does NOT overturn**: the anchor-spanning headroom (nearest-anchor 0.36 → free-rotation ceiling 0.82, eval #7) is a *reachability/expressiveness* claim — orthogonal to whether semantic relations are natively rotational.

## Proposition-altitude probe — 2026-07-22 (`results/prop_rotations_v0.json`)

Option 1 above, executed: 1,200 pairs across 8 **propositional** transformations (the operations a reasoner actually applies), 120–150 pairs each, ~110 train / ~30 test — far better conditioned than the lexical probe.

**The headline is not about rotations.** The new diagnostic — *transformation magnitude*, mean cos(x, y) — shows the dense latent barely registers semantically decisive edits:

| transformation | cos(x, y) | example |
|---|---|---|
| **argument_swap** | **0.974** | "Marisol transferred 400 euros to Dietrich" vs. the reverse |
| active_passive | 0.951 | *(meaning-preserving — SHOULD be high)* |
| causal_reverse | 0.937 | "because A, B" vs. "because B, A" |
| hedge | 0.910 | asserted vs. "may" |
| tense_shift | 0.895 | past vs. future |
| comparative_flip | 0.852 | "more ore than" vs. "less ore than" |
| quantity_double | 0.853 | 40 → 80 liters |
| **negation** | **0.734** | P vs. not-P *(largest mover, still 0.73 similar)* |

**Put this next to the decoder's noise tolerance and the problem is stark**: the decoder retains ~94% fidelity at latent cos 0.89 and ~75% at 0.71 (docs/02). So *reversing who paid whom* (0.974) displaces the latent **less than the noise the codec is explicitly trained to ignore**. The distinctions a reasoner must make are smaller than the codec's designed noise floor. Meaning-preserving `active_passive` (0.951) moves the latent *more* than the meaning-inverting `argument_swap` (0.974) — the ordering is backwards.

**Rotation verdict (secondary)**: block rotation ≈ identity at every dimensionality (mean cos 0.889 vs 0.887 at d=1024); translation is consistently best (0.925), and its wins cluster on transformations with a consistent lexical direction — tense_shift 0.892→0.959, hedge 0.902→0.949, negation 0.734→0.841 (adding "will"/"may"/"not" is an offset). Rotations add nothing over doing nothing, at either altitude. Controls confirm the instrument works (block recovers a known rotation at 0.96 at d=32).

**Metric caveat**: top1 retrieval saturates at 1.00 — with topically distinct candidates, matching x to its own y is a topic-matching task, not a transformation test. Ignore top1 at proposition altitude; use cosine and magnitude.

**Consequence**: no operator family can recover a distinction the representation does not encode. The blocker is upstream of the algebra — see decisions.md **D9**.

**Live options** (see decisions.md D4):
1. **Wrong altitude?** These are lexical relations between short phrases; the reasoner applies *propositional* transformations (negate, change a quantity, shift tense, swap an argument). Re-probe at proposition altitude — highest-value next experiment.
2. **Learn the geometry.** The adapter (D2) exists to reshape the space; an auxiliary objective can *induce* rotational relational structure rather than hoping frozen BGE-M3 has it.
3. **Change the operator family.** Translation is invertible and composable too, though not norm-preserving — the property that kept rotated latents near the decoder's manifold. Affine/scaled-rotation is a middle path.

## Resolution — 2026-07-22: translation-first algebra (D15)

Option 3 is where the evidence landed. Every operator probe had translation ≥ rotation; the linear structure probe then found *why*: lexically-marked transformations live along consistent linear axes — the negation direction alone classifies held-out affirmative/negated pairs at **100%** by projection. First confirmed latent operation: `negate(z) ≈ z − α·μ_not`, a translation. The algebra design is now **translation-first** (steering-vector inventory per marked transformation), with the operator for *role-level* structure deferred until the structure channel exists (decisions.md D14). Rotations remain unadopted; the FHRR/RoPE/RotatE prior did not survive contact with this space at any altitude.

## Update — 2026-07-22 (later): the structure channel exists; the operator inventory is confirmed (D18, D20)

The deferred role-level question is answered: role structure is carried **symbolically** (parse-derived slots — the D3 mirror), not by any continuous operator. The confirmed inventory the memory design (04) should build against:

| transformation | operator | channel |
|---|---|---|
| valence flip (negation, approval, presence, …) | **translation / subspace scaling** (`negate(z) ≈ z − α·μ_not`; shared 8-dim subspace, `results/amp_subspace_v1.npz`) | continuous gist |
| role swap / causal direction | **slot exchange** | symbolic role bits |
| tense | **bit flip** | symbolic role bits |
| epistemic hedge | **bit flip** | symbolic role bits |
| identity substitution (date/place/quantity) | **symbolic replacement** | sparse identity channel (D3) |

Comparison-side assembly = `min(amp_cos, s_cos, role_sim)` (codec/structure_channel.py; full ordering at pair-AUC 0.942, D20). Note the asymmetry discovered on the way: the *detector* for valence needed gain 8 amplification, which destroys retrieval geometry — fine because it runs on comparison-time copies; the *operator* (steering translation) acts on the intact gist.

## Open questions

- Composition depth before interference dominates.
- ~~Learned per-relation rotations vs. derived-from-context rotations~~ — moot; rotations unadopted (D4/D15).
- ~~Interaction with the sparse identity channel~~ — **settled 2026-07-22**: identities stay in the symbolic side-channel, out of the continuous algebra (decisions.md D3, confirmed).
- Does the decoder need explicit algebra conditioning, or is robust training on transformed z sufficient?
- Can the steering translations be *applied* (not just detected) and decoded — i.e., does `decode(z − α·μ_not)` produce the negated proposition? First test of the algebra as a write-path.
