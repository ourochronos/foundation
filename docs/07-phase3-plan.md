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

## Track J — T6: the crystallization spectrum (added 2026-07-25)

- ~~**J1**~~ ✅ D39 — crystallized 0.987acc/279ms/98% stale vs store 0.900acc/78ms/0.78 updated; promotion-for-latency INVERTS (store is 3.6× faster). Original:
  LoRA-distill ~500 hot facts into the decoder base (plain QA format, H1's
  gfx1201-safe config, no chat template, all-linear targets); measure
  retrieval-free accuracy + latency vs the store path; then supersede 100 of
  them in the store and measure crystallized copies answering STALE while
  store answers update. One system, both poles instrumented.
- **J2. Basis-floor curve** — design pre-registered 2026-07-25 (D51), runs
  after the training pause. Operationalizes T6's expressivity invariant.
  - **Basis**: k-means anchors over the whitened 16k corpus,
    N ∈ {64, 256, 1k, 4k, 16k, 65k}.
  - **Expression**: matching pursuit of a latent z onto ≤m anchors,
    m ∈ {1, 2, 4, 8, 16}; expression size = m·log₂(N) bits (+ symbolic
    identities, which ride outside the basis by D3 and are constant across
    the sweep). Deliverable: the (N, m) fidelity surface and iso-fidelity
    contours in BITS — "how big must a message between model and KB be."
  - **Three graded metrics per (N, m)** (which one knees first is the
    finding): (1) reconstruction cos(z, ẑ); (2) INTERFACE: v4 single-hop
    retrieval P@1 querying with ẑ, and v0.6 detection-head agreement on ẑ
    vs z (CPU-cheap, cached embeddings); (3) DECODE: decoder_v2t EM through
    ẑ (deferred — GPU eval).
  - **Novelty tax**: same surface on `ood_sentences_v0` + the K5
    post-freeze questions; report Δm required for iso-fidelity vs
    in-corpus — the "size the expression needs" for novel content,
    measured.
  - **Knee criterion (pre-registered, no eyeballing)**: smallest N with
    retrieval-P@1(ẑ, m=8) ≥ 0.97 × full-z performance.
  - **Falsifiable prediction (from D32 gist-is-topic)**: the INTERFACE knee
    sits far below the reconstruction knee (retrieval is topic-level; full
    decode-grade expressivity needs the big basis). If confirmed, T6's
    "minimal shared core" is small for model↔KB traffic and the expensive
    basis belongs to the codec boundary only. If refuted — interface needs
    the big basis too — the crystallization dial loses its cheap end.
- ~~**J3**~~ ✅ D41 — zero-hand-schema planner BEATS hand schema on holdouts
  (cap_mayor 1.000 vs 0.353; big_pop 0.693 vs 0.553); participation types +
  evidence-proposes/types-dispose scoring. Original: relations-as-entries,
  detection-as-retrieval, soft unification; same v4 holdouts as D37.
- ~~**J5**~~ ✅ D42 — ZERO cross-lingual gap (FR 0.650/0.720 vs EN 0.630/0.705
  gist/hybrid; DE matches). Gist is the interlingua; identities transfer as
  verbatim symbols. Original: FR/DE paraphrase queries vs the English store;
  gist vs identity contribution measured separately.
- ~~**J4**~~ ✅ D46 — planning perfectly growth-invariant at 2× (chain Δ
  0.000 everywhere); novel-entity questions transfer fully with zero
  retraining; execution tax is 100% surface-name collisions (0.488 collided
  vs 0.964 clean) → next symbolic upgrade = entity individuation.

## Track K — Consolidation (D45, external review 2026-07-25)

- ~~**K1. Canonical executor**~~ ✅ `codec/walker.py`; probes import it;
  HopEnv marked legacy. Standing rule: mechanism changes land in `codec/`
  in the same commit as their D-entry.
- ~~**K2. Provenance**~~ ✅ `codec/manifest.py`; result JSONs carry
  commit/seed/versions/input-hashes/config + Wilson CIs. Older artifacts
  backfill on next regeneration.
- ~~**K3. Tests**~~ ✅ `tests/` 16 passing (walker regression on the two
  measured failure modes, store invariants, env guards) + pyproject pins.
- ~~**K4**~~ ✅ D47 — all D44 claims stable ±0.02 across seeds 41/43/44;
  big_pop's failure replicates (structural, not luck).
- ~~**K5**~~ ✅ D48 — post-freeze templates: singles 0.993→0.900 (held-out
  phrasings WERE style-inflated); 9/12 comps hold 0.93–1.00; weak cells are
  one lexical family (mayor-as-"runs" ↔ ceo). Aliases blocked on D46
  individuation.
- **K6. External benchmark shot** — protocol PRE-REGISTERED (D50,
  [09-k6-protocol.md](09-k6-protocol.md)): MQuAKE-CF-3k, per-case + pooled
  stores, matched-scale local baseline, success criteria fixed before test
  contact. Runs after D49 individuation + training-pause lift.
- ~~CI deferred~~ → un-parked with Track L (the CPU test suite now exists
  and runs in 0.1s; gate every push). LICENSE: still the user's call.

## Track L — Path to PoC (added 2026-07-26; goal: confidently build a PoC)

Target demo: feed it documents, ask multi-hop questions in natural
language, edit facts, watch answers update — at 100k+ facts and
interactive latency, on the local GPU.

- **L1. Finish K6 tail**: per-case setting (formal both-settings pass),
  propagation-decay diagnosis (0.745→0.427→0.244 — likely multi-edit
  chains), B1 single-hop recall, 3-phrasing sensitivity, MQuAKE-T.
- **L2. Ingest v0** (was "codec v3 natural-text"): passage → propositions
  → (subject, relation, object) + registry resolution (document = batch,
  D52 locality). Extraction via local Bonsai-27B or Haiku subagents;
  quality measured against MuSiQue-answerable before trusting it.
- **L3. Store engine v2** (un-parked, PQ from J2b): 1024-bit PQ codes +
  exact GPU top-k; acceptance = J4/K6 batteries reproduce within CI at
  100k+ facts; latency budget ≤50 ms/query at 1M.
- **L4. NL answer surface**: walked fact + question → one-sentence answer
  (decoder_v2t or template+object); abstention/ambiguity phrased honestly.
- **L5. v4b world — Track F compute + Track I views/conflicts** (the
  epistemics differentiator: attributed conflicts, views as additive score
  terms on ONE shared graph, D40 tiers operational).
- **L6. CI** (un-parked): pytest on push; result-manifest lint (every new
  results/*.json carries manifest + CIs).
- **L7. PoC assembly**: CLI/notebook demo wiring L2–L4 over the K6+v4b
  stores; scripted walkthrough = the demo IS the acceptance test.
- Paper draft (Track D) proceeds in parallel from logged material.
- STILL PARKED: T5 self-imitation, dial follow-ups beyond J1/J2b,
  distributed ANN serving, streaming split-repair.

## Track M — Pre-build research (adopted with user 2026-07-26; run BEFORE
## architecting the keeper system)

Target after M: the keeper — a subagent service (ingest / ask / edit /
subject_brief) over a durable KB, seeded from Wikipedia (Math +
Epistemology, branching by links), later ArXiv. Scaling via a StoreBackend
interface with PGVector as the durability tier. Federation is explicitly
post-PoC; its primitives (views, provenance batches, evidence-gated
merges, redirects) are already measured at small scale.

- **M1 (=R1). Relation canonicalization** — the D61 gate. Merge relation
  phrases by paraphrase similarity + argument-distribution agreement;
  redirects; counting-calibrated. **Targets (D64/F12): MuSiQue oracle-chain
  QA ≥ 0.40 (≥70% of the 0.567 extraction ceiling); canonical relations in
  [30, 120] on the MuSiQue set; over-merge control — a 40-pair antonym/
  sibling set (born_in vs died_in style, identical type signatures) must
  keep precision ≥ 0.9.**
- **M2 (=R2). Individuation recoverability** — can content geometry
  (fact-anchor clusters) re-derive the eid partition for same-name
  entities? **Targets: pairwise-F1 ≥ 0.80 vs the registry partition, and
  must beat the surface-only baseline by ≥ 15 points; below either →
  identity needs the symbolic scaffold (also a finding, criterion-scored
  not vibes-scored).**
- **M3 (=R3). Wikipedia seed pilot** (AMENDED from ArXiv, user 2026-07-26:
  Wikipedia first — redirects = gold aliases, wikilinks = gold entity
  linking, infoboxes = extraction ground truth). Seed: Math +
  Epistemology PLUS an infobox-rich slice (mathematician biographies —
  D64/F12: the thematic seed is infobox-sparse, so ground truth needs the
  structured slice); branch by links. ~200 pages. **Targets: extraction
  P/R vs infobox fields ≥ 0.6/0.5 on infobox-bearing pages; entity-link
  accuracy vs wikilinks ≥ 0.8; ≥ 20 attributed conflicts surfaced with
  ≥ 0.8 precision on a 25-item audit. Coreference (title-entity +
  pronoun) is IN M3's scope, measured as an error term.** ArXiv = M3b.
- **M4 (=R4). StoreBackend parity**: interface extracted from the walker's
  consumption (query/ids/content_ids/vec/supersede/texts/shadowed);
  MemoryStore/PQStore/PgStore(PGVector) conform; accept = K6+J4 batteries
  reproduce + latency at 100k/1M (absorbs D62's open GPU bench; pgvector
  quantization re-measured under the J2b protocol).
- **M5 (=R5). Grounded synthesis**: subject_brief = retrieve subgraph →
  summary with per-sentence store citations. **Targets: entailment-judged
  faithfulness ≥ 0.9 (each sentence cites an entry that entails it; judged
  set n=50); distractor-subgraph control — unsupported-claim refusal
  ≥ 0.8; disputed points surfaced via views on ≥ 0.8 of planted
  conflicts.**
- **M6 (=R6). Open-relation detection** — retire D61's oracle-chain scope
  after M1 (canonical relations → trainable det head → MuSiQue end-to-end).
- **M7 (=R7). Continual soak**: scheduled ingest for a week; J4-protocol
  invariance checks on the growing store; artifact-refresh cadence. The
  "worth keeping running" test.

Build gate: **M1–M4 MEET TARGETS** (D64/F12 — not merely "have numbers")
→ keeper architecture session (with the package restructure that earns
itself at that point). Pre-publication additions from D64: MeLLo-style
iterative 0.6B baseline + chat-template B1; M6 must compare fixed-head vs
detection-as-retrieval (F15); M7 gets drift thresholds (weekly headline
metrics within CI of day-0; rollback = snapshot restore).

## Sequencing

Week 1: A1–A4 + B1–B2 (A1 is the long pole; everything else is hours).
Week 2: A5–A8 + E1; C0–C2 once A1's world exists; D2 metric adoption alongside.
Then: C3/C4 training runs (hours per run at the expected tiny-core size),
D1 external eval, D3 write-ups. Every A-item outcome gets a decisions.md entry
whether it confirms or cuts back a prior claim — the log's credibility rests on
recording the cutbacks with the same prominence as the wins.
