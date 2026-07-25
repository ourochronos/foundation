# Phase-3 plan — synthesized from the 6-agent research & review sweep (2026-07-25)

Inputs: four literature surveys (latent reasoning, test-time memory, retrieval-native
architectures, codecs/alignment), one adversarial internal review, one gap analysis.
Full agent reports are in the session record; load-bearing citations added to
[references.md](references.md). This document is the working plan; decisions.md
gets entries as items complete.

## The strategic picture

**Three novelty verdicts, all being approached:**
1. *Translation-operator relational addressing over LLM latents in an external
   store* — unpublished through 07/2026 (TransE is 2013 ancestry; nearest
   neighbors NextMem = latent store without operators, GRAIL = query-embedding
   arithmetic without relations, HippoRAG 2 = relations via symbolic graph).
2. *The triple-latent codec* (channel separation at a frozen-encoder boundary;
   noise-immune symbolic identities; decoder-as-error-corrector) — LCM lineage
   hit exactly the failure we route around and pivoted back to tokens; no one
   tried channel separation.
3. *Small weight-tied reasoner + frozen codec + hop-call action space +
   surprisal-readout halting* — unclaimed composition; DiscoLoop (07/2026,
   Mei/Russell/Lee) independently published our D26 law ("continuous drifts
   across hops; discrete anchors error-correct") for internal embeddings.

**And one hard internal verdict:** the recent positive results are the
vulnerable ones. The 0.99/0.998 memory numbers are partly guaranteed by world
construction (globally unique name tokens, one store template per relation,
one hop composition, totality); the structure channel has no untouched test
set left (role_bits was hand-extended against two of the three "holdout"
constructions); `shuf_dense ≈ full` in `decoder_v2t_eval.json` means the
gist's semantic contribution beyond topic is *unmeasured* and the D24/D28
invariance narratives partly restate metric insensitivity; nothing has CIs.
The trustworthy results are the negatives (D11–13, D26's latent-hop death) and
the architecture-level attributions (shuffled-sparse collapse, D21).

**Resolution:** harden the vulnerable results first (Track A — cheap, ~days),
de-risk the reasoner in parallel (Track B — CPU), build the reasoner on the
hardened world (Track C), position externally (Track D). Publish after A, not
before.

## Track A — Hardening sprint (run before banking anything)

- ~~**A1**~~ ✅ D30 — adversary confirmed: relational 0.85–0.90 (phrasing-general), hops 0.0–0.81 by composition, walk semantics retracted to heuristics, no-answer inseparable from top-1 score. Floors per composition now in D30. Original spec: *(the single highest-value item; kills or
  confirms threats #1/#2/#9/#10 and doubles as the reasoner's training world)*:
  ~20% colliding entity names/shared surname tokens; ≥5 store-side templates
  per relation; query phrasings from a DIFFERENT generator than the templates
  (10/relation, report mean and worst-phrasing P@1); ≥4 hop compositions
  (incl. ceo_of∘born_in, located_in∘capital_of∘population_of 3-hops); hop
  patterns that REVISIT the source entity (tests whether demote/exclude are
  invariants or n=1 heuristics — expect them to become soft/learnable actions);
  no-answer cases; multiple facts per (subject, relation) with timestamps.
  Adversary's prediction to test: relational addressing falls to the 0.75–0.85
  regime and hop P@1 well below 0.9. Whatever survives is the real floor.
- ~~**A2**~~ ✅ D32 — gist is TOPIC-ONLY (+0.010 masked-cycle over wrong gist; null gist = 74% predicate recall). D24/D28 rhetoric cut back; reasoner state can be more discrete. Original:
  decode under (i) true gist (ii) same-domain WRONG gist (iii) null gist, all
  with true symbols; mask entities/numbers to placeholders in recon AND
  reference before re-encoding; add predicate/relation-word EM (verbs, units,
  connectives — nothing the symbol channels carry). If (i) ≈ (ii): the gist is
  topic-only, D24/D28 rhetoric gets cut back, and the reasoner design leans
  even harder on symbols. If (i) ≫ (ii): the frame claim survives with an
  identity-clean instrument. Either outcome is useful; one GPU evening.
- ~~**A3**~~ ✅ D29 — gist collapses (0.128 @cos 0.80), identity rescoring activates (+0.857, holds 0.985). Original text: *(threat #6)*: replace isotropic noise with
  confusable-drift (interpolate query latent toward same-relation different-
  entity facts at matched cos). Expect gist retrieval to degrade sharply and
  identity rescoring to finally activate — which would *strengthen* the
  architecture story while killing the "invariance" framing. One hour, cached.
- **A4** (disposition per D33: new probes carry CIs; retro-annex deferred). Original: re-emit JSONs; mark every
  logged delta smaller than its CI (several D2x conclusions sit inside error
  bars — the +0.011 margin, the 0.006 "cost", the ±0.02 EM deltas).
- ~~**A5**~~ ✅ D31 — natural-text struct AUC 0.767 (CI .70–.83); valence generalizes, symbolic normalizations are the gap. Original:
  ~30 pairs/type of naturally-phrased constructions from a different
  generator/prompt-author (converse predicates, "fail to X", "hardly/barely",
  un-normalized cleft variants); score ONCE through `pair_scores()`; bootstrap
  AUC; no code changes allowed after seeing results.
- ~~**A6**~~ ✅ D31/D33 — ROC 43% false-flag; edit stress 0.605@n=200 (shadow fired 114/200, 31 wrong targets) → store-v1 fix specified (identity-agreement targeting). Original: 100 number-
  reformatting/alias paraphrase pairs ("3 pm"↔"15:00", "a dozen"↔"12",
  "US"↔"United States") → false-flag rate for D23's rule; 200 edits with
  old-object queries and second-generation edits → does id-set union pollute?
- ~~**A7**~~ ✅ D33 — graded, no collapse: number 0.571, binding 0.429, entity 0.693; noise-invariance HOLDS OOD. Original: 250 real number-bearing sentences +
  250 two-sentence chunks through the unchanged v2t eval; re-run the σ-sweep
  on them. In-distribution tables get a "synthetic register" qualifier until
  this exists.
- ~~**A8**~~ ✅ D34 — equal-bit control collapses to dense-only (0.178/0.317/0.229) and degrades under noise; channel separation IS the mechanism. TRACK A COMPLETE. Original: identities
  injected into the dense channel at matched bit budget — separates
  architecture-win from information-win.

## Track B — Reasoner de-risk (parallel, CPU-cheap)

- ~~**B1**~~ ✅ D29 — 1.000 test acc, control at chance; provisional until re-run on v3 phrasings. Original text: question gist → relation choice
  (7-way + halt). If linearly separable (expected — relation choice is
  type-level, which is what the gist demonstrably carries), the core can be
  TINY and the "ultra-wide" clause of 05-reasoner.md is formally retired. The
  width-for-binding justification is already dead (binding moved to symbols).
- ~~**B2**~~ ✅ D31 — halt = trivial readout (~1.00); abstain = id-coverage AUC 0.952. Original: log per-step top1−top2 margin, id-coverage,
  Δstate over oracle walks incl. forced over-stepping; test separability of
  halt/continue. Literature triangulation says halting should be a cheap
  READOUT over store responses, not a learned gate (Cambridge 2607.20519:
  readouts beat gates; Ouro: entropy-exit works; Stop-RAG: Q(λ) value head;
  our D24: continuous prediction-error will be flat because we engineered it
  to be). Surprisal redefinition: retrieval-margin collapse = confusion.

## Track C — Reasoner v0 (on the A1 world)

- **C0.** Rewrite `05-reasoner.md` per the staleness audit: reasoner = control
  policy over the triple (state must include symbolic ids + walk bookkeeping);
  rotations→hop calls; drop width-for-binding; halting = supervised v0 with
  readout ablation; decouple halt-surprisal from write-surprisal (T5).
- **C1.** `HopEnv` over `MemoryStore`: action = (relation ∈ inventory | HALT |
  ABSTAIN, selective hand-off mask over entry id-tokens); demote/exclude are
  now confirmed non-invariants (D30) → soft action components. Abstain head
  cannot use top-1 score (D30) — candidate signals from B2 on world v3.
- **C2.** Oracle traces over world v3 (+ CoRAG-style rejection sampling where
  the oracle is partial). **C3.** Training per the DGPO recipe — the published
  evidence at sub-1B: cold-start distillation from traces, then RL with
  PER-STEP rewards (relation choice / hand-off / stop scored separately);
  pure RL at this scale is a documented dead end. Weight-tied loop, Huginn-
  style randomized unroll; loop-count = hop-count gives T4 its instrument.
- **C4.** Eval ladder: rung 1 clone-matches-oracle on held-out entities; rung 2
  held-out COMPOSITIONS; rung 3 unseen phrasings + distractor relations +
  reasoner-noised latents (closes D24's revisit); rung 4 text-CoT FLOP-parity
  (write the accounting first); metrics ARC-style decomposed (relation-selection
  vs retrieval vs synthesis) so the mechanism's contribution is attributable.

## Track D — External positioning

- **D1.** MuSiQue answerable-split, closed-world protocol — the community
  hardness standard; baselines: HippoRAG 2 (hops-without-generation) and
  GRAIL-style embedding arithmetic. GRADE methodology for controlled
  difficulty matrices over our own store.
- **D2.** Adopt, don't invent: LongMemEval-KU + FAMA (supersession — the
  *Supersede* paper names our solved failure mode), MQuAKE-style
  multi-hop-after-edit (**the headline candidate**: weight-editors demonstrably
  collapse there; our transparent edits + 0.998 traversal should not),
  MemoryAgentBench selective-forgetting streams (T5).
- **D3.** Write-ups after Track A: (i) codec characterization paper (triple
  latent, noise-immune identities, error-correcting decoder + A8 control +
  rotation-transfer demo — Procrustes bounds make backbone transfer a
  theorem-backed, demonstrable claim; symbolic channel transfers trivially);
  (ii) store paper (translation addressing + address-inheriting supersession +
  hop primitive), positioned as TransE-lifted-to-LLM-latents, benchmarked per
  D2. Timing pressure is real: DiscoLoop/GRAIL/NextMem are adjacent and recent.

## Track E — Efficiency & quantization (added 2026-07-25, scoped by our own results)

- ~~**E1**~~ ✅ D31 — int8 free, binary ~free (32×, the design point); anchor-codes collapse RETRIEVAL (decode≠retrieval resolution). Original: the
  gist reconstructs from ~9 bits of anchor identity, so store keys should
  compress radically — anchor-code (+ optional residual), int8, and binary
  variants vs fp32 on the full retrieval/hop suite. CPU, cached embeddings.
  Feeds T3's efficiency framing (store bytes-per-fact vs dense bits-per-fact
  à la 2404.05405). Run alongside Track A on the hardened world.
- **E2. Reasoner weight precision — GATED ON B1.** If the core is tiny
  (1–10M), precision is moot; skip. If FLOP-parity pressure grows it,
  BitNet-style 1.58-bit QAT-from-scratch is the default candidate (we train
  from scratch anyway) — enters C3 as an ablation, and the T1 FLOP-parity
  accounting must record precision on both sides either way. Unsloth-class
  tooling: skip unless a job doesn't fit — CUDA/Triton-first, ROCm/gfx1201
  friction expected, and our trainings already fit.
- **E3. Functional factorization probe** *(the "least-dense factorization"
  thesis, within-weights edition)*: after C3, test whether relation-selection,
  halting, and hand-off occupy separable low-rank subspaces of the trained
  core. The program already factors functions architecturally (knowledge →
  store, binding → symbols, expression → codec — that is WHY the core can be
  small); this measures whether the residual control function factors again
  internally. Cheap interpretability probe; pairs with the looped-model
  mechanistic-analysis literature from the sweep.

## Program priorities (standing, 2026-07-25)

1. **The goal** — the Northstar system (small factored model + store + continuous
   learning) outranks any individual result; findings serve the goal.
2. **Documented findings** — every result lands in decisions.md with cutbacks as
   prominent as wins; docs update AS WORK HAPPENS, not after.

## Module contracts (modularity, next level)

Components are replaceable behind MEASURED interfaces; a swap is legal when the
certifying number holds:
- Encoder: swappable via fitted orthogonal map (Procrustes-bound certifies;
  symbolic channel transfers trivially) — demonstrate in the codec paper (D3
  item).
- Decoder: pretrain-once/align-many (H2) — alignment run replaces retraining.
- Store scoring: capabilities compose as ADDITIVE score terms (gist + identity
  + demote + view + ...) — new capability = new term, never surgery.
- Policy: actions are a closed inventory (hop/ALU/halt/abstain); adding an
  action extends the inventory without retraining the world.

## Usability — the path to sizeable context (Northstar criterion)

The architecture's long-context strategy is THE STORE, not an attention window:
- Read side: Track G ingestion makes input context unbounded (documents →
  propositions → entries).
- Structure side: proposition-graph links (discourse relations BETWEEN triples
  — elaboration/cause/sequence as inter-entry relations, same machinery as
  located_in) so multi-sentence statements are entry clusters, not bigger
  latents.
- Write side: the H1 3B decoder trained for MULTI-TRIPLE rendering (sequences
  of entries → flowing prose) — answers longer than one sentence.

## Track I — Views & epistemics on a shared graph (design set; lit report in)

**The reference the user recalled**: MAGMA (arXiv 2601.03236, ACL 2026) — four
orthogonal graphs (semantic/temporal/causal/entity) as views with
policy-guided traversal — and notably it KEEPS a shared item set, validating
"views on a shared graph." Our differentiation (novelty-checked, unclaimed):
views as **additive score terms over a hybrid continuous+symbolic store** —
MAGMA's views are discrete edge-sets walked by a policy; eSPARQL/DEC condition
symbolic stores by hard logic; RA-RAG composes trust additively but as one
global scalar with no perspective. Nothing combines all three of our pieces.

Design (from the three literature lessons):
- **I1. Conflict typing at write time as a metadata bit** — temporal
  supersession vs epistemic disagreement vs semantic ambiguity (CONFLICTS
  evidence: knowing the type is worth ~24 points downstream). Temporal →
  supersede links (bi-temporal); epistemic → PERSPECTIVE FORK: both entries
  persist with attribution + stance bits. Never force disagreement into
  "old fact expired" (the Zep failure).
- **I2. One shared item set; perspectives soft** — a view = query-time score
  term over entry metadata, composing with gist/identity/demote terms. Plus
  DEC's refinement: a **distinguished factual core** = the default view whose
  scores apply absent any view term, so unattributed queries degrade
  gracefully.
- **I3. trust(view, source) as a learned, updateable weight** — per-view,
  not global (the productive gap between RA-RAG and eSPARQL); updatable by
  RA-RAG-style cross-source consistency voting. Rides the same additive
  scoring.
- **I4. Eval**: extend world v4 with attributed conflicting facts (two
  sources, different objects, no temporal ordering) — queries under view A /
  view B / no view; correct = view-consistent object, or surfaced
  disagreement when unattributed. ConflictBank/CONFLICTS taxonomies for the
  external rung.

## Northstar gap map (added 2026-07-25, second research sweep)

Between Track C's reasoner and the T3/T5 Northstar sit four gaps; three scouts
mapped them (full reports in session record; citations in references.md):

## Track F — Compute over retrieved values (the ALU)

Verdict from the survey: **fixed symbolic op inventory as policy actions** —
learned arithmetic is empirically dead (NALU lineage still failing single-op
seeds in 2025); free-form code emission is the big-model pattern whose
generation step is the small-model failure surface; every small-scale success
(TagOp ~125M op-classifier + exact execution; ≤3B constrained-DSL 2025;
SYRELM) shrank the action language to a closed op set. Trains from
answer-only reward (WNSMN precedent).
- **F1.** ALU ops in HopEnv: `compare | diff | count | filter | agg` over
  identity-channel operands, TYPED (numbers/years/counts) with neuro-symbolic
  action masking (ops whose operand types don't type-check are masked).
- **F2.** The guarded failure mode is OPERAND SELECTION, not the op: operand
  choice is part of the action; unit/scale mismatch (millions vs billions)
  fails silently — magnitude tags ride the identity channel.
- **F3.** World v4 adds compute questions ("which is larger", "how many
  founded before 1950") with oracle traces.

## Track G — Ingestion (documents → store)

The field's biggest open problem is OUR solved mechanism: streaming
supersession (Mem0 18%, GPT-4o 51.5% multi-hop, GRPO-3B 16.7% on fact
consolidation) — "a store whose addressing natively detects same-subject-
relation/different-object" is the survey's literal description of the gap and
of our A6b fix spec. Pipeline (all stages have recipes):
- **G1.** Segmentation: 2B-class APS distillate (solved; tune atomicity to
  one-triple capacity).
- **G2.** Extraction: fine-tuned 0.5–3B (distilled small BEATS prompted
  frontier: F1 0.83 vs 0.66–0.69); never prompt-per-chunk.
- **G3.** Write gate: SAGE-shaped three-way gate with OUR native signal —
  translation-operator predictive retrieval ("can the store already predict
  this fact?") — unpublished angle.
- **G4.** Supersession: deterministic bi-temporal metadata + identity-
  agreement targeting (the A6b fix); freshness is NEVER an LLM judgment
  (+28pts for deterministic, 2606.01435).
- **G5.** **Benchmark shot**: our store on MemoryAgentBench FactConsolidation
  + EMERGE — the axis where every published system fails and ours is
  structural. Headline-result candidate alongside MQuAKE-after-edit.

## Track H — Training infrastructure (unblocks the 3B decoder)

- **H1.** QLoRA on gfx1201 is OFFICIAL (bitsandbytes ≥0.50.0 validated;
  Unsloth now Full-tier AMD+WSL — earlier skip-verdict reversed). The
  gfx1201-safe config, from a same-GPU field report: NF4 base + LoRA
  all-linear + `adamw_torch` (paged/8-bit bnb optimizers SILENTLY CORRUPT on
  HIP) + gradient checkpointing + math-only SDPA + raw training loop; Qwen3
  tied-embeddings trap: never modules_to_save=[lm_head,embed_tokens]. Try
  bf16 LoRA first for 3B (~fits); NF4 unlocks 7B.
- **H2.** **Pretrain-once / align-many decoder** (the structural win):
  general-corpus decoder + 1k–8k-pair alignment per latent-space variant
  (ALGEN lineage) instead of per-variant retraining — turns codec iteration
  from training runs into alignment runs. CE-through-frozen-decoder
  (SONAR-LLM) is the more sample-efficient objective vs embedding-space
  regression. Pilot: 1k-pair alignment onto the current triple.
- **H3.** u-μP for the 1–10M sweep harness; 10M tier as HP-transfer proxy
  for any future from-scratch 0.6B-class run.

## Sequencing

Week 1: A1–A4 + B1–B2 (A1 is the long pole; everything else is hours).
Week 2: A5–A8 + E1; C0–C2 once A1's world exists; D2 metric adoption alongside.
Then: C3/C4 training runs (hours per run at the expected tiny-core size),
D1 external eval, D3 write-ups. Every A-item outcome gets a decisions.md entry
whether it confirms or cuts back a prior claim — the log's credibility rests on
recording the cutbacks with the same prominence as the wins.
