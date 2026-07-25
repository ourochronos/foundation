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
- **A2. Frame-only cycle metric** *(threat #4 — the gist-redundancy question)*:
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
- **A4. Bootstrap CIs in fidelity/compare probes**; re-emit JSONs; mark every
  logged delta smaller than its CI (several D2x conclusions sit inside error
  bars — the +0.011 margin, the 0.006 "cost", the ±0.02 EM deltas).
- **A5. Frozen adversarial battery for the structure channel** *(threat #3)*:
  ~30 pairs/type of naturally-phrased constructions from a different
  generator/prompt-author (converse predicates, "fail to X", "hardly/barely",
  un-normalized cleft variants); score ONCE through `pair_scores()`; bootstrap
  AUC; no code changes allowed after seeing results.
- **A6. Identity-channel ROC + edit stress** *(threats #7/#11)*: 100 number-
  reformatting/alias paraphrase pairs ("3 pm"↔"15:00", "a dozen"↔"12",
  "US"↔"United States") → false-flag rate for D23's rule; 200 edits with
  old-object queries and second-generation edits → does id-set union pollute?
- **A7. OOD codec eval** *(threat #5)*: 250 real number-bearing sentences +
  250 two-sentence chunks through the unchanged v2t eval; re-run the σ-sweep
  on them. In-distribution tables get a "synthetic register" qualifier until
  this exists.
- **A8. Equal-bit control for the paper** *(codec reviewer demand)*: identities
  injected into the dense channel at matched bit budget — separates
  architecture-win from information-win.

## Track B — Reasoner de-risk (parallel, CPU-cheap)

- ~~**B1**~~ ✅ D29 — 1.000 test acc, control at chance; provisional until re-run on v3 phrasings. Original text: question gist → relation choice
  (7-way + halt). If linearly separable (expected — relation choice is
  type-level, which is what the gist demonstrably carries), the core can be
  TINY and the "ultra-wide" clause of 05-reasoner.md is formally retired. The
  width-for-binding justification is already dead (binding moved to symbols).
- **B2. Halting-signal audit**: log per-step top1−top2 margin, id-coverage,
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

- **E1. Store-key quantization** *(highest value; D28 pre-justifies it)*: the
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

## Sequencing

Week 1: A1–A4 + B1–B2 (A1 is the long pole; everything else is hours).
Week 2: A5–A8 + E1; C0–C2 once A1's world exists; D2 metric adoption alongside.
Then: C3/C4 training runs (hours per run at the expected tiny-core size),
D1 external eval, D3 write-ups. Every A-item outcome gets a decisions.md entry
whether it confirms or cuts back a prior claim — the log's credibility rests on
recording the cutbacks with the same prominence as the wins.
