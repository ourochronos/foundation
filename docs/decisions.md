# Decision log

Format: date · decision · rationale · revisit-when.

## 2026-07-27 — D67: Strategy — commodity rails, custom only where measurement earned it (with user; D68 Phase-A audit in flight)
**The shift**: progress-per-week now beats architecture-per-component. Custom parts that EARNED their keep by measurement stay (reasoner stack — detection heads, typed unification, channel-separated walker; supersession/ripple + views SEMANTICS; eval harness/manifests/worlds). Everything else moves to off-the-shelf: **storage/search/quantization → PGVector (FAISS locally)** with our semantics as a thin StoreBackend layer — the Phase-A bugs are the closing argument, both living in hand-rolled plumbing (GPU cache, top-k) no thesis needed; **relation inventory → Wikidata's property schema** for the Wikipedia pilot — M1 re-scoped from open-vocabulary induction (stuck at 0.284 antonym precision, D66) to CLASSIFICATION into a curated schema (extractor prompted with the inventory; the antonym problem dissolves by construction — schema properties are distinct); open-vocab induction parks as research-later for schema-less sources; **entity candidates → Wikipedia redirects/wikilinks**, with our evidence rules (D49–D52) kept as the decision layer they were measured as.
**Re-sequencing**: Phase A finish → **M4 pulled forward** (pgvector backend replaces the code that produced the audit's two bugs; parity battery K6+J4 non-negotiable before the custom store retires to reference-implementation status) → M1-rescoped (schema mapping ≥0.85 on a 100-triple audit; ≥70% of extractions mappable) → M3 (Wikidata schema + redirect ground truth) → M2 anytime → M5–M7.
**The honest caution, logged**: shelf engines do not natively do hybrid dense+id scoring or address-inheritance supersession — parity is proven by battery, never assumed.

## 2026-07-26 — D66: M1 IN PROGRESS — three iterations logged, two defects named, gates NOT met yet
Relation canonicalization on the MuSiQue triples (`probe_canon_m1.py`, `results/canon_m1.json`): v1 (bare-phrase embeds, τ0.85) under-merged 687→624, QA floor. v2 (carrier-template embeds "X {rel} Y.", question-level batching) hit the count gate (111 @ τ0.75 ∈ [30,120]) but **antonym precision 0.284** — distributional twins ("birth date"/"death") merge at every τ. v3 (evidence gate for frequent pairs + D52 relation-gated multi-candidate query resolution) changed NOTHING — both defects survived, and that's diagnostic:
1. **Rare-hub transitivity**: my gate exempted pairs where either relation is rare — union-find then chains antonyms THROUGH rare hubs ("attended"→"career start"→"start"). Fix direction: embedding-only merges require BOTH rare; any pair touching a frequent relation needs shared-(s,o) counting evidence; possibly complete-linkage instead of connected components.
2. **QA pinned at exactly 3/150 across every variant** — a constant that loud means a structural break upstream of everything varied (suspects: MuSiQue decomposition-question format (">>" strings) breaking subject/chain extraction; hop-2 "#1" placeholder handling; walk hand-off across question-batch eids). Needs a 5-row trace next session, not more parameter guessing.
**Scoring vs the D64 gates: count ✓ (116), antonym ✗ (0.284 vs ≥0.9), QA ✗ (0.020 vs ≥0.40).** M1 is NOT passed and the keeper build stays gated. The honest read: canonicalization-by-embedding is the easy half; canonicalization-by-EVIDENCE (the D38 way) is the real mechanism and its first implementation had two logic holes, both now named. Session ends here by context; resume at the trace.

## 2026-07-26 — D65: v0.7b + K5b — the corrected pipeline gives STRONGER transfer evidence and an honest negative
**v0.7b** (holdout-chain pairs excluded from augmentation per D64/F1; `results/reasoner_v07.json` regenerated): v4 battery — **big_pop 0.360** (the prior 1.000 was coverage, not generalization — F2's suspicion confirmed by ablation), **cap_mayor 0.920/0.880 as a legitimate holdout**, singles 0.993, abstention 0.840.
**K5b** (fresh-author frozen gate per D64/F2: Haiku-authored, cue-words banned, independent sampling, no component ever saw the strings; `results/k5b_probe.json`): singles **0.975**; **cap_mayor chain 1.000 / P@1 0.933 [CI 0.79–0.98]** and **hq_loc_cap 1.000/0.933** — composition transfer CONFIRMED on a clean instrument with untrained pairs; all trained compositions 0.867–1.000; **big_pop 0.000** — without pair coverage, K5b's phrasings of that composition are not detected at all.
**Net position, stated plainly**: compositional transfer via typed unification is real (cap_mayor, hq_loc_cap, K6 natural data — three independent instruments). The big_pop detection entanglement is a REAL limit of pooled-gist detection for that relation pair — fixable by coverage (D59 measured that), not yet by generalization. D59's "weaknesses CLOSED by data alone" is retracted in favor of this entry. The "runs"-confusion fix DID survive the fresh instrument (mayor_born/cap_mayor cells at 1.000/0.933 with the cue family banned — the contrast set taught the distinction, not the test strings).

## 2026-07-26 — D64: Second adversarial review (internal agent) — 14/16 findings accepted; the failure pattern is CRITERIA DRIFT AT ACCEPTANCE, and the fixes are running
Full report in the session record; ranked F1–F16. The reviewer verified every quoted number against its artifact (all match) and confirmed the negatives are recorded at headline prominence — then correctly indicted the acceptance discipline. Dispositions:
- **F1 ACCEPTED+FIXED THE RIGHT WAY**: v0.7's pair augmentation had synthesized the cap_mayor holdout pair. Rather than retire it, v0.7b retrains with ALL holdout-chain pairs excluded — cap_mayor AND big_pop stay genuine holdouts. D59's "true holdouts unchanged" was false as written [corrected below].
- **F2 ACCEPTED**: K5 was burned as an instrument the moment its failure phrasings seeded v0.7's contrast set. K5b commissioned from a different author (Haiku, cue-words banned); v0.7b's gate = K5b, which none of our components has ever seen.
- **F3 ACCEPTED**: D52's entry-ambiguity carve-out is POST-HOC by the repo's own record. Restated: the original criterion as registered FAILS (all-collided 0.830 < 0.90; parity clause also fails, 0.948 CI excludes 0.978). The amended reading (path-collided 0.948 / flag recall 1.000) remains the defensible one — but it is an amended criterion, and D52's "ACCEPTED"/"closed" language over-claimed.
- **F4 ACCEPTED**: the per-case "train-store bridge" was in fact built from ALL pooled facts including test cases (code vs comment). Rerun with train-only artifacts queued; materiality low (local-only 0.670 still beats B1 0.352) but D57's anti-leakage sentence was wrong about its own code.
- **F5 ACCEPTED**: K6 metric 4 (post-edit abstention honesty) was never run and never dispositioned — it is VACUOUS on CF-3k (every case has a post-edit answer) and that should have been logged at protocol time, not discovered by a reviewer. 3-phrasing sensitivity (the registered forking-paths bound) queued now, before any further K6 claims.
- **F6 ACCEPTED**: D62 re-scoped L3's registered acceptance in the acceptance entry. PQStore status → **provisionally accepted**: statistical parity (not "bit-parity") on the K6 battery at native scale; 100k latency ✓; 1M-GPU bench, J4-battery-through-PQ, and a ≥100k-fact battery all OWED.
- **F7 PARTIAL**: per-case (0.683, or 0.670 leakage-free variant, vs 0.352 full-store reader) is now the PRIMARY comparison; the pooled 11.7× is demoted to secondary with its single-shot-RAG scope note. MeLLo-style iterative 0.6B baseline + chat-template B1 upgrade queued as pre-publication items.
- **F8 ACCEPTED**: K6 ran surface-token ids only; the individuation machinery has never touched natural data. docs/09's claim amended; M3 is the owed venue.
- **F9 ACCEPTED**: commit-then-run is now the rule for headline-bound results; the three naked artifacts (clean-regime 0.602, extraction 0.717/0.567, contamination 153/600) queued for manifested regeneration.
- **F10 ACCEPTED**: D42 mis-scored its own registered prediction — the identity term did NOT go silent cross-lingually (names are language-invariant strings); gist-half confirmed, identity-half refuted-for-proper-nouns. "Zero gap" → "no detectable gap at n=100/language."
- **F11/F13/F14/F16 ACCEPTED**: 06-state consolidation pass queued; superlatives get their CIs adjacent or get dropped ("lossless"→400/400 [CI ≥0.990]; "FREE/PERFECTLY"→"invariant at one 2× doubling, seeds 41+43"); metrics named next to numbers (D48 quoted chain, D59 quoted P@1 — same cell, different metrics).
- **F12 ACCEPTED**: Track M gates now carry NUMERIC targets (plan doc updated this commit); build gate rewords to "M1–M4 meet targets." Coreference assigned to M3's scope. Wikipedia seed amended: Math+Epistemology PLUS an infobox-rich slice (mathematician biographies) so ground truth exists where the thematic seed is infobox-sparse.
- **F15 ACCEPTED**: fixed detection heads REVERSED D38's detection-as-retrieval ruling without a logged amendment. Logged now: fixed heads are the measured practical regime through K6; detection-as-retrieval remains the design goal for continual relation growth, and M6 must compare both — the continual-learning thesis currently rests on a retrainable component, which is a real limitation.
- **REBUTTED (2)**: F7's "strawman" as a full dismissal — the per-case comparison was always reported and survives every discount the reviewer applied (their own verification); and F12's claim that M4 lacked gates (it had them; the reviewer concedes "M4 is fine").
**Mechanical fixes COMPLETE (same day)**: F4 rerun with train-only bridge — per-case 0.670/0.675/0.682/0.685, unchanged (leakage was immaterial; code now matches the claim). F5 phrasing sensitivity MEASURED: post-edit pooled P@1 0.468/0.437/0.405 across the three MQuAKE phrasings (±6 pts — the registered forking-paths bound, now on record). F9: clean-regime regenerated WITH manifest (0.604, CI'd; contamination 153/600 = 0.255 now an artifact, not stdout); extraction artifact manifested. F11: 06-state consolidated.
**Meta-lesson, standing rule**: an acceptance criterion may only be amended in a commit that PRECEDES the run it judges. If results and amendment land together, the amendment is post-hoc and must say so.

## 2026-07-26 — D63: Pre-build research track adopted (M1–M7); Wikipedia-first seed; eids reframed as caches pending M2
With the user: the keeper system (subagent service over a durable KB) is gated on Track M numbers, not built on vibes. Amendments from discussion: (1) **Wikipedia before ArXiv** — Math+Epistemology seed, branching by links; chosen not just for gentler prose but because Wikipedia SHIPS ground truth for our machinery (redirects=aliases, wikilinks=entity links, infoboxes=extraction targets), and the seed topics map onto D40's tiers (math=constitutive, epistemology=views). (2) **Eids settled conceptually, tested empirically**: the pointer is the name of a DISCOVERED equivalence class (all content stays in the store); the residual concerns are (a) hand-coded resolver → future distillation per the T7 ladder, (b) recoverability from content geometry → M2 probe. (3) **T7 (self-training ladder) added to the vision** — the user's "training it to train itself" observation, formalized as the four-timescale loop. (4) PGVector = durability tier behind a StoreBackend interface, accepted only through the same batteries (M4). (5) Federation post-PoC; primitives already exist in miniature. Next: adversarial review subagent over claims/plans/consistency, then M1.

## 2026-07-26 — D62: PQStore PROVISIONALLY accepted [amended D64/F6] — K6 battery STATISTICAL parity at 1024-bit codes, 4× faster, 32× smaller; 1M-GPU bench + J4-battery + ≥100k battery owed
**Acceptance** (`probe_store_pq_l3.py`, `results/store_pq_l3.json`; engine `codec/store_pq.py`, D55 semantics preserved, 28 tests): the full K6 pooled post-edit battery through PQ codes — **0.740/0.427/0.215 vs fp32 0.745/0.427/0.244** (all within CI) at **8 ms/question vs 34** (ADC LUT-gathers beat the fp32 matmul at store scale — compression made it FASTER). Codes: 13 MB per 100k entries vs 410 MB fp32. Scale bench (CPU-forced — the GPU was occupied): **24 ms/query at 100k ✓** within the ≤50 ms budget; **1M at 796 ms ✗ on numpy** — the GPU gather path is the designed answer and its bench is the one open L3 item. One API addition forced and landed properly: readouts go through `store.vec(idx)` on both engines (PQ reconstructs from codes — classification-grade per J2b).

## 2026-07-26 — D61: Ingest v0 — extraction is viable (0.717 step recall); QA is blocked on RELATION CANONICALIZATION, the symmetric twin of entity individuation
**Pipeline** (`ingest_v0.py`, Haiku-shard extraction per D5): 300 MuSiQue supporting paragraphs → 1,771 triples. **Extraction quality: step-answer recall 0.717, full 2-hop coverage 0.567** (the honest QA ceiling for this subset). Registry ingest with document-as-batch locality worked as designed.
**QA: 0.020 — and the number that explains it is 688 open relations from 1,771 triples.** Nearly every relation string is a singleton ("is fourth album by" / "album by" / "fourth album"), so per-relation prototypes/operators are fit from 1–3 examples (garbage), and oracle-chain mapping picks among 688 near-duplicates. The store machinery is fine; it was handed an unconsolidated relation vocabulary.
**The design insight, logged as the v1 requirement**: RELATIONS need exactly what entities got in docs/08 — individuation's dual, canonicalization: merge relation strings by paraphrase similarity + argument-distribution agreement (same subjects/objects types = same relation), with redirects, calibrated by counting. D38 said relations are store entries; D49 gave entities identity ≠ surface form; D61 completes the symmetry: relation identity ≠ surface phrase. Until that exists, triples-native sources (MQuAKE, Wikidata) are the PoC's ingest format and free-text ingest is bounded by extraction+canonicalization, not by the reasoner.
**Scope honesty**: the 0.020 also folds in oracle-chain mapping noise and single-rule question synthesis; none of it is worth tuning before canonicalization exists.

## 2026-07-26 — D60: v4b — views ARE id-channel content (0.970/0.920/0.000); answer-time ALU is exact (1.000)
**Track I, the user's epistemics thesis made operational** (`gen_world_v4b.py`, `probe_v4b.py`, `results/v4b_probe.json`): 400 attributed conflicts (Meridian Atlas variants of capital facts) live in the SAME store as canonical facts. A view is nothing but a source token in the entry's id set; a source-qualified query adds that token to its query ids and the ordinary overlap rescoring selects the view — **zero new mechanism**. Measured: qualified-view P@1 **0.970**; unqualified queries on conflicted subjects FLAG the conflict (top-2 same subject+relation, different sources) at **0.920** with **0.000 spurious** flags on clean subjects. D40's tiers now have their store-level implementation: contingent knowledge conflicts live side by side, attributed; nothing is silently overwritten; the default behavior is honest disagreement. (One bug cost a rerun: `id_tokens` splits "src:meridian" at the colon — source tokens must be normalization-safe. Token hygiene is now a stated constraint for any channel-content convention.)
**Track F**: 700 compute questions (population/year diffs, comparisons) answered by two walks + symbolic arithmetic at **1.000** — the ALU lives at answer time over symbolic number tokens (D3 vindicated again; numbers never touch the continuous channel). Two honest scope notes: relation used for walking was the gold one — the v0.7 head's argmax gets it right only 0.657 on compute phrasings (multi-label + op-cue detection is v1); op selection (diff vs cmp) is a 3-cue rule, learnable later.

## 2026-07-26 — D59: v0.7 detector — both replicated weaknesses CLOSED by data alone; alias test PASSES at 1.000 with a fair generator
**v0.7** (`train_reasoner_v07.py`, `results/reasoner_v07.json`; architecture unchanged, 1024→256→9): two augmentations — (1) pair-complete synthetic compositions for every co-occurrence-legal relation pair (one nominal template per relation + one outer bank; legality by counting, D54); (2) a 240-question "runs/leads/heads" contrast set (same verbs, city vs company subjects, opposite labels). **K5 frozen-template gate (pre-registered in D48): big_pop 0.500→1.000, cap_mayor 0.467→0.967, mayor_born 0.700→1.000, singles 0.900→0.936, all other cells ≥0.93 — no regressions.** v4 battery: cap_mayor 0.913, hq_loc_cap 0.967, singles 0.993, abstention 0.835→0.855. [CORRECTED, D64/F1: 'true holdouts unchanged' was false — the augmentation had synthesized the cap_mayor pair; superseded by v0.7b which excludes all holdout-chain pairs.] **Bookkeeping**: big_pop is hereby RETIRED as a compositional holdout (the augmentation covers its pair); the compositional-transfer claim rests on cap_mayor, hq_loc_cap, and K6's natural-data result. The pooled-gist entanglement (v0.1's diagnosis) is confirmed to be a DATA-coverage phenomenon, not architectural.
**Aliases (D49 test 2, closed)**: with a uniqueness-enforced generator, alias P@1 = canonical P@1 = 0.990, **ratio 1.000** (`results/alias_j4b.json`). The earlier 0.833 was entirely my colliding truncations — which the resolver correctly flagged rather than resolving. Test 2 PASSED.

## 2026-07-26 — D58: K6 PRE-REGISTERED VERDICT — PASS in both settings, non-overlapping CIs, ~10× lower latency
Final table (docs/09 primary criterion; `results/k6_*.json`):

| setting | ours | B1 matched-scale | note |
|---|---|---|---|
| pooled, all 1,043 edits live | 0.468 (0.602 clean-regime) @ 34 ms/q | 0.040 @ 336 ms/q | B1 = top-5 retrieval + Qwen3-0.6B |
| per-case | **0.683** (0.745/0.774/0.537) | 0.352 @ 316 ms/q | B1 reader sees the ENTIRE store — strongest form |

95% CIs non-overlapping in both settings. Edits land at 0.964; sibling-edit contamination (25.5%) quantified as a regime property. Remaining optional: B1 single-hop recall for the strong-pass gap comparison; MQuAKE-T; 3-phrasing sensitivity. **The architecture claim now stands on an external benchmark it did not help construct, against a matched-resource baseline, under pre-registered criteria.**

## 2026-07-26 — D57: Per-case setting FIXED (0.320 → 0.683) — the store was missing the edits' base facts; bridge starvation named as the tiny-store residual
**The bug** (traced in 4 hops flat): multi-edit MQuAKE chains edit facts sitting on NEITHER the original nor the visible post-edit path (case 4: the chain enters India only after edit 1, and edit 2 rewrites India's capital — whose base fact "India|P36|New Delhi" my per-case store never contained, so the edit was silently skipped and hop-2 coverage went to 0.00). Pooled never suffered this — everything is global — which fully explains pooled > per-case. **Per-case stores must contain every edit's target_true base fact.**
**Result** (`k6_percase_clean.py`, `results/k6_percase_clean.json`): per-case 2×2 over suspect artifacts:

| variant | overall | anatomy |
|---|---|---|
| local artifacts | 0.670 | no-plan 181 (bridge starves) |
| + global rng_cprof | 0.672 | (answer expert was never the problem) |
| + global bridge | 0.682 | no-plan 181→65, exec 111 (genuinely missing intermediates) |
| + both | **0.683** (0.745/0.774/0.537 by hop) | |

**Named residuals**: tiny-store BRIDGE starvation (co-occurrence gates need global/train schema when the store is 10 facts — schema is world knowledge, not case knowledge, so using the train-store bridge is principled, not leakage); ~111 exec failures = genuinely missing intermediate facts (same class as pooled's 107 world-build gaps). B1 per-case (reader sees the ENTIRE case store — strongest baseline form) running for the formal both-settings verdict.

## 2026-07-26 — D56: L1 diagnosis — a quarter of the mass-edit ceiling is the REGIME, not the system; hop-2 divergence is the residual mechanism target
**Findings** (`k6_stage4_l1.py`, `results/k6_l1.json` + inline contamination count):
1. **Sibling-edit contamination**: applying ALL 1,043 test edits at once shadows a gold post-edit path fact for **153/600 (25.5%) of cases** — those golds are unreachable BY CONSTRUCTION in the pooled regime (MQuAKE's labels assume only the case's own edits are active). Effective pooled ceiling ≈ 0.745; our 0.468 is ~63% of achievable. Mass-edit evaluations in the literature share this confound silently; ours is now quantified.
2. **Failure anatomy (pooled, traced walks)**: dominant residual = **diverge-at-hop-2 right after the edited fact** (239 cases; overlaps heavily with contamination), then no-plan (66), wrong-chain (24), gold-fact-missing (107, multi-edit world-build gaps). Single-edit cases: 76 ok vs 87 hop-2 divergences.
3. **Per-case setting: 0.320 PROVISIONAL** — below pooled, unexpectedly. A relaxed-gate rerun (0.307) accidentally flattened the answer-type expert (uniform range profiles), so gate starvation vs artifact remains unresolved; needs one clean pass with case-local range profiles before the docs/09 both-settings verdict can be declared.
**Clean-regime number (a) — measured** (`results/k6_clean_regime.json`): restricting to the 447 uncontaminated cases (ALL 1,043 edits still live as distractors): **2hop 0.740 / 3hop 0.590 / 4hop 0.364, overall 0.602** — vs matched-scale baseline 0.040 and the 34 ms/question latency. This is the honest post-edit architecture number; the pooled 0.468 mixes in the 25.5% regime-invalidated golds. Remaining: (b) per-case clean pass; (c) the 107 world-build gaps.

## 2026-07-26 — D54: First external benchmark — MQuAKE-CF-3k pre-edit multi-hop 0.86/0.87/0.82, after ONE fix: schema by counting, not geometry
**Setup** (`k6_build_world.py`, `k6_stage2_preedit.py`, `results/k6_preedit.json`; protocol docs/09): 3,957 deduped facts (incl. post-edit-chain real facts), 36 Wikidata relations, case-level 80/20 split, heads (~0.4M) trained on train-split questions only, POOLED store (all test facts as mutual distractors), dataset-provided cloze verbalization (zero authorial templates).
**First contact**: 2hop 0.556, 3/4hop ≈ 0 with abstain ~1.0. Diagnosis on train split: detection recall@4 was 0.92–0.99 over 36 relations — the tiny head scales to Wikidata fine. The killer was the v4-calibrated COSINE feasibility gate: MQuAKE entities carry 1–3 facts, participation profiles are near-one-hot, and 97% of gold 3/4-hop chains scored under the 0.35 gate (median 0.062) — a SPARSITY artifact, not type mismatch.
**Fix (D38 doctrine again)**: replace profile-cosine links with a store-derived **co-occurrence gate** — `link_ok(A,B)` iff some entity bridges obj(A)→subj(B); entry gate = subject-has-slot; chain cap 4, candidates 5 (planner parameterized in `v06_pipeline.make_planner`). **Result: 2hop 0.862, 3hop 0.874, 4hop 0.820** (abstain 0.08–0.16), test cases, phrasing 0. Natural-language multi-hop over real facts, frozen encoder, closed-form artifacts, 0.4M learned params.
**Law confirmed on external data**: every learned component transferred; the one hand-calibrated GEOMETRIC threshold did not. Schema knowledge (which relations chain) is counting over the store, not latent geometry.

## 2026-07-26 — D55: Addresses and hand-off content must SEPARATE at supersession — mass-edit propagation 0.177 → 0.468
**The pre-registered headline experiment** (`k6_stage3_edits.py`, `results/k6_postedit.json`): ALL 1,043 test-case counterfactual edits applied at once via `supersede` to the pooled store (the regime where parameter-editing collapses), then post-edit multi-hop.
**Edits LAND: 0.964** single-hop recall at the edited address (supersession + address inheritance works at MQuAKE scale). But first-run propagation collapsed compounding-per-hop (0.388/0.111/0.039): `supersede`'s id-UNION — correct for ADDRESSING ("who replaced X?" still finds the entry) — sent BOTH old and new objects down the walker's hand-off, so hop k+1 retrieved the old world's fact about USA as often as Croatia's. This is the answer to A6/D33's open question: **id-set union pollutes, specifically the hand-off role.**
**Mechanism (landed in codec/ with tests, per D45)**: `MemoryStore.content_ids` — an entry's OWN entities — separated from `ids` (address). `supersede` unions addresses only; `ChannelWalker` hands off content only. D33's law extended: keys/values separate at supersession, and so do addresses/content.
**Post-edit result: 2hop 0.745 / 3hop 0.427 / 4hop 0.244, overall 0.468 @ 34 ms/question**; propagation gap 0.964−0.468 = 0.495. Per-hop decay says residual compounding remains (multi-edit chains, counterfactual-fact addressing) — next diagnosis target.

**B1 verdict (matched-scale baseline, `results/k6_b1_baseline.json`)**: same embeddings, same post-edit pooled store, top-5 retrieval → Qwen3-0.6B reads and answers: **0.066 / 0.015 / 0.039 by hop, 0.040 overall, at 336 ms/question**. Ours is **11.7× more accurate at 10× lower latency**; 95% CIs are nowhere near overlapping (0.468±0.04 vs 0.040±0.016, n≈600). The docs/09 primary criterion is MET in the pooled setting — the honest one — with the per-case setting still to run for the formal both-settings pass; the strong-pass gap comparison needs B1's single-hop edit recall (unmeasured). Fair scope note: B1 is single-shot RAG (retrieval by whole-question similarity, no iteration) — exactly what "matched scale, matched latency class" buys; iterative big-LLM baselines (MeLLo lineage) remain context, not the claim. At matched resources, composition doesn't come for free with a reader — it has to be built, and this is the first external evidence the built version works.

## 2026-07-26 — D52: Individuation — passed under AMENDED criterion [see D64/F3: original registered criterion fails at 0.830 all-collided; amendment is post-hoc]; path-collided 0.948, ambiguity flagged at 1.000
**Result** (`probe_individuation_j4.py` rerun of the D46 protocol, `results/individuation_j4.json`; heads loaded from D44 checkpoints — no training): with the D49 registry at write time, on gold-planned seed-43 hops over the 2× store:

| case class | exec P@1 | n | D46 (surface tokens) |
|---|---|---|---|
| **path-collided** (subject unique, collision on path/answer) | **0.948** ✓ target ≥0.90 | 381 | 0.488 (mixed) |
| clean | 0.978 | 1336 | 0.964 |
| entry-ambiguous (subject NAME collided, no context) | 0.454, **flag-rate 1.000** | 119 | — |

Registry: 8,800 eids over 8,151 surface names — the ~649 cross-world collisions individuated exactly. Planning untouched (chain 1.000 everywhere but the known big_pop 0.420 / cap_mayor 0.95). Seed-41 regression at 2×: within D44 range.

**Amendment (reasoned before the split was measured)**: D46's "collided ≥0.90" target conflated two populations. Entry-ambiguous questions ("population of North Halmelton" with two North Halmeltons and no disambiguating context) are *unanswerable as posed* — the ceiling is a coin flip and the honest metric is the ambiguity FLAG, which scored **1.000 recall**. The ≥0.90 target properly applies to path-collided cases, where it passed.

**What it took (v1.1, one deviation logged)**: the docs/08 write-time profile gate had a cold-start circularity; v1.1 replaces it with **batch locality** — within one source, same name = same entity (discourse prior); across sources, absorption requires evidence (matching functional value/object or neighbor overlap), otherwise same name = new individual. Values act as pseudo-objects so functional conflicts fire on value facts too (born-1987 vs born-1990 splits two Jo Fosvens regardless of ingest order). First attempt also taught two probe-level lessons the hard way: dom/rng signatures scramble if subject/object eids aren't tracked separately (hq-chains died at 0.000 — caught by the seed-41 regression battery), and object-mention resolution without evidence mints spurious eids (10,858 → 8,800 after the fix). Split-repair pass for streaming ingest remains deferred.
**Consequence**: K6 (MQuAKE) is unblocked — its 2,915/3,000 alias-bearing cases are exactly this machinery's territory. Aliases via redirect entries are acceptance test 2, still pending.

## 2026-07-26 — D53: J2/J2b — sparse anchor codes FAIL in the whitened space; the shared basis is BLOCK anchors (PQ), with graded knees in the registered order
**J2 as registered** (`probe_basis_floor_j2.py`, `results/basis_floor_j2.json`): matching-pursuit anchor codes never reach either knee. At m=8 with EVERY train point as an anchor (~110 bits): reconstruction fid 0.684, retrieval 0.395 vs 0.580 full-z, detection agreement 0.905. (Amendment logged: N=65k was impossible — the anchor pool is the 16k corpus; top rung = all-train-points.) **Why**: the whitened space has effective rank ~523 (D10 era) — whitening deliberately spread variance across hundreds of directions, so ≤16 atoms from ANY global dictionary cannot span it. The D51 prediction (interface knee ≪ reconstruction knee) is **unresolvable in this family** — nothing knees — though the graded ORDERING held (detection > retrieval > reconstruction at every N).

**J2b completes it** (`probe_pq_j2b.py`, `results/pq_j2b.json`): product quantization — S subspaces × 256 anchors each, i.e. *block-structured* anchors — at matched bits:

| bits | corpus fid | retrieval P@1 (/0.580) | detection agree |
|---|---|---|---|
| 128 | 0.402 | 0.388 | 0.853 |
| 256 | 0.513 | 0.497 | **0.985** |
| 512 | 0.661 | 0.545 | **1.000** |
| 1024 | 0.823 | **0.578** ✓ knee | 1.000 |

**The graded knees land in exactly the registered order**: detection (the reasoner's actual input channel) is lossless at **512 bits**, retrieval crosses its 0.97× knee at **1024 bits**, reconstruction still hasn't kneed at 1024. **T6 quantified**: model↔KB messages cost ~256–512 bits for reasoning-grade traffic, ~1024 for retrieval-grade, more for decode-grade — a ~60× compression from the fp16 latent at the reasoning tier. **Design conclusion**: the crystallization dial's "minimal shared basis" is per-subspace codebooks, not a global sparse dictionary; global anchors (D6's framing) survive as retrieval geometry landmarks, not as the message code. D31's int8/PQ store-quantization tolerances and this result now tell one story.
**Revisit**: decode-grade knee when GPU eval resumes (deferred metric); learned codebooks only if closed-form PQ proves insufficient downstream.

## 2026-07-25 — D49: Entity-individuation design adopted (symbolic-channel v2) — identity ≠ surface form, as store content
**Full design: [08-individuation.md](08-individuation.md).** Decisions being logged: (1) entities get opaque **eids**; fact entries carry eid sets; numbers/years stay surface tokens (values, not individuals — D3 preserved). (2) Surface→eid **resolution is store content** (registry entries with growable surface forms, participation profile, gist anchor) — extends D38 (schema-in-store) and D40 (surface forms are contingent knowledge). (3) Resolver v1 is **closed-form** (surface overlap → type gate → functional-conflict gate → neighborhood score), calibrated by counting on synthetic unions with known ground truth; no learning. (4) Functional-relation conflicts are evidence of DISTINCTNESS unless the text marks change — the individuation/supersession boundary, made explicit. (5) Late-discovered equivalence = **redirect entries** (never rewrite; same philosophy as supersession). (6) Query-time ambiguity is **flagged, not silently resolved**. Acceptance tests pre-registered in the doc; #1 is the D46 J4 rerun with collided-case execution ≥ 0.90. **Rationale**: D46 measured surface-token identity as the sole store-growth cost; D48 blocked aliases on the same root. **Revisit**: if closed-form resolution fails on MQuAKE's natural names (K6), a learned scorer is the fallback, gated by frozen-template discipline.

## 2026-07-25 — D50: K6 external-eval protocol PRE-REGISTERED — MQuAKE-CF-3k, matched-scale baseline, success criteria fixed before test contact
**Full protocol: [09-k6-protocol.md](09-k6-protocol.md).** Logged commitments: MQuAKE-CF-3k primary (triples-native — no ingest confound; task = post-edit multi-hop, our differentiator; real names exercise D49). Two store settings both reported (per-case AND pooled-with-distractors). Primary comparison = **matched-scale local baseline** (same BGE-M3 retrieval + Qwen3-0.6B reader); published MeLLo/ROME/MEMIT numbers as context only. Success = beat the matched baseline on post-edit multi-hop in both settings, non-overlapping 95% CIs, comparable latency; strong pass adds ≥10-point smaller edit-propagation gap. Verbalization templates committed pre-contact with hash in the manifest; post-contact changes are logged amendments. Threats stated up front (37 relations vs our 9; dirtier signatures; template sensitivity bounded on train split). **Sequencing**: runs after individuation (D49) lands and the training pause lifts.

## 2026-07-25 — D51: J2 basis-floor measurement pre-registered — expression size in bits, three graded knees, one falsifiable prediction
Design in [07-phase3-plan.md](07-phase3-plan.md) §J2. Logged: expression = matching pursuit onto ≤m of N k-means anchors, size = m·log₂(N) bits, symbols outside the basis (D3). Three metrics per (N, m) — reconstruction cos, INTERFACE (retrieval-P@1 + detection-head agreement through ẑ), DECODE (deferred, GPU) — because *which knees first* is the finding. Knee criterion fixed pre-run (smallest N with retrieval ≥ 0.97× full-z at m=8). Novelty tax measured on OOD + K5 post-freeze questions as Δm for iso-fidelity. **Falsifiable prediction, registered now**: the interface knee sits far below the reconstruction knee (from D32 gist-is-topic). Confirmation makes T6's minimal shared core cheap for model↔KB traffic; refutation kills the crystallization dial's cheap end. **Revisit**: n/a — this entry exists so the prediction can't be quietly revised.

## 2026-07-25 — D46: Store growth is FREE except where entities lack individuation (J4 — planning invariant at 2×, execution loss is 100% surface-name collisions)
**Protocol** (`scripts/probe_store_growth.py`, `results/store_growth_j4.json`): v0.6 heads + participation-cluster basis PC trained on seed-41 and FROZEN; store doubled with seed-43's facts (8,859 → 17,715; 649 cross-seed surface-name collisions); every store-side artifact recomputed closed-form over the union (participation vectors, dom/rng signatures, prototypes, operators, range-cluster profiles).

**Result A (seed-41 questions vs 2× store): planning is PERFECTLY growth-invariant — chain-correct delta 0.000 on every composition.** The learned heads never see the store, and the recomputed signatures/prototypes stay aligned under the frozen basis. Execution pays 4–14 points (singles 0.993→0.963; abstention flat at 0.830).
**Result B (seed-43 questions — subjects the heads NEVER saw): full transfer.** Chains 0.953–1.000 matching seed-41's pattern (holdouts included: cap_mayor 0.953, hq_loc_cap 1.000, big_pop 0.427 mirroring its known detection weakness); singles 0.970; abstention 0.840. The reasoner works on new store content with ZERO retraining — the continual-learning claim of D38 §2, measured end-to-end.
**The execution tax is entirely collisions, not crowding**: splitting B's gold-planned cases by whether the subject/answer entities have a cross-world name collision — collided **0.488** (n=205) vs clean **0.964** (n=615). Clean cases at 2× are statistically the 1× rate. The id channel identifies entities by SURFACE TOKENS (`id_tokens`), so two entities named "North Halmelton" are indistinguishable *by construction* — this is the known symbolic-channel design gap (same root as K5's alias exclusion), now measured as the sole scaling cost.
**Design consequence**: the next symbolic-channel upgrade is entity INDIVIDUATION (unique entity ids with surface-form → id resolution as store content, which also buys aliasing), not anything in the continuous machinery.
**Revisit**: when the individuation mechanism lands; rerun this exact probe as its acceptance test.

## 2026-07-25 — D47: The v0.6 results replicate across world seeds (K4 — no seed-41 luck)
**Protocol** (`scripts/probe_multiseed_k4.py`, `results/multiseed_k4.json`): full pipeline (own store artifacts, own cluster basis, own heads) retrained per seed on three independently generated worlds (41/43/44). Headline spread:

| metric | seeds 41 / 43 / 44 |
|---|---|
| single P@1 | 0.993 / 0.988 / 0.988 |
| cap_mayor (holdout) chain | 0.960 / 0.947 / 0.967 |
| hq_loc_cap (holdout) chain | 1.000 / 1.000 / 1.000 |
| big_pop (holdout) chain | 0.420 / 0.440 / 0.407 |
| no_answer abstain | 0.835 / 0.835 / 0.850 |

Every claim in D44 is stable to ±0.02 across seeds — including the negative one: **big_pop's detection failure replicates (0.407–0.440), so it is structural** (population_of under-detection when paired with largest_city_of), not sampling noise. Multi-seed + CI reporting is now part of the standard protocol (K4 ✅).

## 2026-07-25 — D48: Post-freeze templates cost 9 points on singles and expose ONE lexical confusion family (K5)
**Protocol** (`scripts/probe_frozen_templates_k5.py`, `results/frozen_templates_k5.json`): 27 single + 24 hop templates written AFTER every component froze, in registers the generator bank never used (telegraphic, bureaucratic, colloquial-indirect). 360 single + 360 hop questions.
**Results**: singles **0.900** (vs 0.993 on held-out phrasings — the held-out-phrasing eval WAS inflated by shared authorial style, as suspected in the A-track and by the external review). Compositions: chain 1.000 and P@1 0.933–1.000 on **9/12** — the structural machinery (types, unification, walk) is register-indifferent wherever detection holds. The three weak cells are one phenomenon: mayor_born 0.700 and cap_mayor 0.500 both use templates phrasing mayor as "the official who runs / at the top of" — colliding with ceo_of's cue family; big_pop 0.500 is its D44 weakness (actually *above* its in-distribution 0.42).
**Reading**: template-register sensitivity lives entirely in the 265K detection head over a pooled gist; sharper templates → graceful degradation, not collapse. Entity ALIASES remain explicitly out of scope until the D46 individuation mechanism exists (same root cause).
**Revisit**: v0.7 detector (span-fused features or composition-augmented training) should be accepted only if it closes big_pop AND the "runs" confusion under these frozen templates.

## 2026-07-25 — D45: External review integrated (GPT 5.6 Sol) — consolidation over scope
**Context**: independent review of `main@96405b1`. Verdict: research thinking/methodology strong, reproducibility weak, and one sharp engineering finding — **the claimed system and the codebase were not the same thing**: the D43 executor lived in a probe script while `HopEnv.step()` still shipped the defective walk. Accepted almost wholesale; actions below. The review's phrasing of the current claim is adopted as the program's official one: *"the channel-separated planner and executor solve a deliberately adversarial synthetic relational world and generalize to selected unseen compositions"* — not "composition solved."

**Done immediately (this commit):**
1. **Canonical executor** — `codec/walker.py` (`ChannelWalker`): the ONE implementation of the D43 walk + D44 abstention readouts; `probe_soft_planner.py`/`train_reasoner_v06.py` now import it; `HopEnv` docstring marks its executor LEGACY (kept verbatim to reproduce D30–D37) with a warning pointing here. API enforces the finding: `walk(q_ids, chain)` takes no question gist at all.
2. **Provenance house rule** — `codec/manifest.py`: every result JSON now carries `manifest` (commit SHA, dirty flag, seed, command, package versions, GPU, input-artifact hashes, config) and Wilson 95% CIs beside every headline rate. `soft_planner_j3.json` and `reasoner_v06.json` regenerated under the rule; older artifacts keep their docs-side context until next regeneration.
3. **Tests** — `tests/` (16 passing): walker regression built around the two measured failure modes (gist-derailed hops, revisit hand-off), store invariants (supersession address inheritance, empty/dim guards, demote/exclude), env guard rails. Plus: `weights_only=True` on checkpoint loads, `pooler_loss` batch guard, MemoryStore docstring corrected (no timestamps — Sol's catch).
4. **Reproducibility** — `pyproject.toml` with pinned versions + ROCm install caveat; README gains a from-scratch environment path and the conventions block.

**Deferred with reasons:** CI workflow (no GPU runner for the real suite; a lint-only gate adds little — revisit if collaborators join). LICENSE (user's legal call, repo is internal). Repo restructure into `store/planner/runtime` packages (premature while interfaces are moving weekly; `codec/` stays the library home for now).

**Pushback recorded:** (a) MemoryStore's O(N) dense scan is *deliberate* at this phase (D7: prove on modest hardware; 10k entries ≈ 40 MB — the scan is not the experiment). The scale redesign (ANN, quantization — D31 already measured int8/PQ tolerances) is gated on a store-scale track, not retrofitted now. (b) "Benchmark highly constructed" — agreed, and it is the *A-track's own conclusion* (D29–D34 repriced every headline on de-templated worlds); the external-benchmark shots (MQuAKE, MuSiQue, MemoryAgentBench) were already queued and are now promoted to the next-after-J4 slot. (c) "Discoveries promoted to the decision log faster than to the software architecture" — correct and now a standing check: **a D-entry that changes a mechanism must move the mechanism into `codec/` in the same commit.**

## 2026-07-25 — D44: v0.6 hybrid reasoner LANDED — composition transfer at last (0.000 → 0.913/0.967 on 2 of 3 holdouts), ~0.4M learned params
**The rung the reasoner arc was climbing toward** (`scripts/train_reasoner_v06.py`, `results/reasoner_v06.json`, checkpoints `reasoner_v06_det/ans.pt`): every component either learned from data or a measured store readout — zero hand schema anywhere.

| component | what | provenance |
|---|---|---|
| detection | q_gist → which relations (multi-label, UNORDERED), 1024→256→9 | learned; singles + trained comps only |
| answer type | q_gist → participation cluster of the answer, 1024→128→8 | learned (the D41 cosine aprof was mush: truncated chains outscored gold 0.392 vs 0.346) |
| assembly | product of experts: detection log-odds + answer-cluster log-mass under last relation's range; participation-type feasibility gate; chains built ONLY from detected relations (det ≥ 0.2) and MUST contain confident ones (det > 0.5) | D41 unification, no tuned weights (aw=1.0 by construction) |
| execution | D43 channel-separated walk | store arithmetic |
| abstention | plan failure (no legal chain) OR hop-1 relation-mismatch readout (classify retrieved fact as argmax_r cos(z, proto_r+t_r)) | measured: readout alone recall 1.000 / false 0.010 |

**Results** (detector-held-back questions for trained comps; all questions for holdouts; singles on held-out phrasings):
- singles **0.993** (BC policy 0.757; oracle floor 0.743)
- trained compositions: chain **1.000 across all 9**, P@1 0.944–1.000
- **holdout compositions (never seen composed): cap_mayor 0.960/0.913, hq_loc_cap 1.000/0.967** — vs BC 0.000/0.000 through four versions, and vs hand-schema end-to-end 0.353/0.042
- big_pop holdout **0.420** — residual detector failure: population_of is UNDER-detected (p 0.15–0.6) when paired with never-seen-together largest_city_of; the answer-type expert lifts it (0.34→0.42 at aw=1.0; sensitivity 0.46/0.54/0.60 at aw=0.5/1/2, NOT tuned — selecting aw on holdout performance would be leakage)
- no_answer abstain **0.835**, and the leak analysis is the interesting part: 165/200 abstain at PLANNING (no legal chain — D37's type-invalid abstention, now derived), 2 at the hop-1 readout, and the 33 "leaks" are the detector *semantically reinterpreting* ill-posed questions — "the administrative center of Garmelgar Labs" answered with the company's HQ. Arguably correct behavior the benchmark scores as error.

**Two abstention design laws, both measured this session:** (1) the feasibility gate silently REWRITES unanswerable questions into answerable ones unless confidently detected relations are required AND chains are restricted to detected relations — planning failure then becomes the abstention signal; (2) under the D43 walk, id-coverage is dead as an abstention signal (id_weight=1.0 retrieves the subject's wrong-relation fact with perfect coverage) — the readout must be relation classification of the retrieved entry.

**What remains open**: big_pop-style detector entanglement (one relation's cue suppressing another's in a novel pairing — the pooled-gist limitation, v0.1's diagnosis, now isolated to detection probability calibration rather than architecture). Candidate fixes for v0.7: span-level detection features fused with the gist head, or composition-augmented detector training (synthesize nested questions from single-hop templates — no new world knowledge needed).
**Revisit**: after J2/J4; benchmark shots (MQuAKE, MuSiQue) once the world-v4b tracks land.

## 2026-07-25 — D43: Walk execution SOLVED — the walk itself must obey channel separation (gold-chain exec 0.93–1.00, was 0.00–0.76)
**The defect** (found tracing loc_cap_pop, where BOTH planners produced perfect chains and BOTH executed at 0.000): the D30-era walk queries hop k with `question_gist + t_rel`. But a multi-hop question's gist encodes the LAST hop's relation — "population of the capital of the country containing X" is population-flavored — so hop 1's `+ t_located_in` still lands on the subject's *population* fact. Measured: all 20 traced walks diverged at hop 1. A second, independent defect: the hand-off mask `ids(cur) − all_seen_ids` goes EMPTY on revisit compositions (half of v4's loc_cap_pop cases have the subject city as its country's capital — the answer entity is already in the question, so subtracting seen ids deletes the hand-off).

**The fix — the walk is channel separation applied one more time (sixth appearance of the law):**
1. The dense query for hop k is the relation **prototype + operator** (`proto_r + t_r`) — type-level content only. The question's gist never touches intermediate hops.
2. The entity rides the id channel exclusively: `id_weight=1.0`, hand-off mask = `ids(cur) − ids(handed in)` — subtract the *subject side* of the current fact only, keeping the object even when it already appeared in the question.

Gold-chain execution, all 12 v4 compositions (`walk()` in `scripts/probe_soft_planner.py`): 0.933–1.000, mean **0.972** — including loc_cap_pop 0.983 (3-hop, was 0.000) and loc_big 1.000 (the revisit composition that broke D30's hard walk semantics). The old oracle floors (0.0–0.76) were floors of a *defective executor*, not of the task.

**End-to-end (D41 planner ∘ this walk), mean 0.804 vs hand-schema 0.25:** cap_mayor holdout 0.953, hq_loc_cap holdout 0.967, loc_cap_pop 0.983, hq_mayor 0.993. P@1 now tracks chain-correct within 1–5 points everywhere — **planning is the only remaining bottleneck**, and its misses are pure detection failures (hq_loc 0.300/loc_cap 0.467: a spurious third hop appended; cap_pop 0.623: population_of↔mayor_of span confusion). A det-threshold repair was tried and rejected: weakly-detected-but-REAL relations (born_in) are indistinguishable from spurious appends by span-prototype cosine alone — that discrimination is what v0.6's learned detector must supply.
**Revisit**: never for the walk semantics; the detector via v0.6.

## 2026-07-25 — D42: The gist channel IS an interlingua — zero cross-lingual retrieval gap (J5, D40 validated)
**Experiment** (`scripts/probe_crosslingual.py`, `results/crosslingual_j5.json`, `data/crosslingual_queries_v0.json`): 200 v4 single-hop queries translated to French/German (Haiku agent; invented entity names kept verbatim), retrieved against the untouched ENGLISH fact store.

| queries | gist-only P@1 | hybrid (+identities) P@1 | identity coverage |
|---|---|---|---|
| English (same 200) | 0.630 | 0.705 | 1.000 |
| French (n=100) | **0.650** | **0.720** | 0.970 |
| German (n=100) | **0.610** | **0.700** | 0.940 |

Crossing the language boundary costs **nothing** — FR is within noise of (numerically above) the EN baseline on both channels. The two channels transfer for *different reasons*, exactly as D40 predicted: the dense gist transfers because BGE-M3's multilingual training makes meaning language-invariant (the interlingua); the identity channel transfers because names are surface-copied symbols (language-parochial but language-INDEPENDENT for proper nouns — coverage drops only where the translator inflected a name, 3–6%). Baseline note: 0.63–0.70 is the honest de-templated single-hop regime (A1-era numbers), including held-out phrasings.
**Implication for the program**: the store, operators, and planner never see the query language. Multilinguality lives entirely in the frozen encoder — a property we inherit, not one we must engineer. Decoder-side (answering IN French) remains untested and is a codec question, not a store question.
**Revisit**: with morphologically distant languages (agent data was FR/DE only) or if a future encoder swap loses multilingual training.

## 2026-07-25 — D41: Zero-hand-schema planning WORKS — and beats the hand schema on held-out compositions (J3, D38 §1 validated)
**Experiment** (`scripts/probe_soft_planner.py`, `results/soft_planner_j3.json`): rebuild D37's typed-unification planner with NOTHING hand-written — no relation signatures, no cue lexicon, no answer-type table. Everything derives from the store: entity types = **relational-participation vectors** (normalized counts over (relation, role) — "a city is the kind of thing with population/located-in/mayor facts"); relation entries carry data-derived domain/range profiles (mean participation of their subjects/objects), a question-prototype (mean train-question embedding), and the translation operator; detection = noun-chunk/verb spans retrieved against relation prototypes; answer typing = participation-cluster prototypes from training questions.

Soft vs hand schema (D37, `results/typed_planner_v05.json`) on v4 — chain-correct / end-to-end P@1. **Correction 2026-07-25**: the first version of this table compared soft chain-correct against hand END-TO-END numbers; corrected below against the hand schema's actual chain-correct.

| composition | soft chain / P@1 | hand chain / P@1 |
|---|---|---|
| **big_pop** (holdout) | 0.693 / 0.480 | **1.000** / **0.553** |
| **cap_mayor** (holdout) | **1.000** / **0.520** | 0.693 / 0.353 |
| **hq_loc_cap** (holdout) | **1.000** / **0.242** | 0.000 / 0.042 |
| cap_pop | 0.623 / 0.491 | 1.000 / 0.714 |
| hq_mayor | **1.000** / **0.207** | 0.000 / 0.000 |
| hq_pop | **1.000** / **0.589** | 0.367 / 0.222 |
| loc_big / loc_cap / mayor_born | 0.900 / 0.467 / 0.950 | 0.000 / 0.000 / 0.361 |
| loc_cap_pop | 1.000 / **0.000** | 1.000 / **0.000** |
| weak: hq_loc | 0.300 / 0.133 | 0.327 / 0.160 |

Mean chain-correct: soft **0.822** vs hand **0.478** — the hand lexicon simply had no cues for half the compositions (hq_mayor, loc_big, loc_cap at 0.000), which is exactly the rigidity the user flagged when rejecting it. On holdouts, soft wins 2/3 on both metrics and loses only big_pop chain accuracy. Not degenerate: five distinct compositions each get distinct perfect chains. The weak cells (hq_loc, loc_cap) are detection confusions in located_in/headquartered_in span vocabulary — an evidence problem, not a schema problem. Note loc_cap_pop: BOTH planners produce perfect chains and BOTH execute at 0.000 — the 3-hop walk defect is in the shared executor, independent of planning.

**It took three attempts, and both failures localize informatively:**
1. **v1 (surface types) FAILED** — k-means clusters over entity-NAME embeddings are phonological mush for invented names: mean off-diagonal domain-profile cosine **0.862** (indistinct). Diagnostics: detection recall@4 was fine (0.90); the scorer given gold candidates still scored 0.050 — the type signal itself carried nothing. *Types cannot come from what an entity is called.*
2. **v2 (participation types, additive scoring) FAILED degenerately** — with type profiles now crisp, the question-INDEPENDENT compatibility terms dominated the weak detection terms and the planner emitted one globally link-compatible chain for every question (loc_big chain=1.000, all else 0.000).
3. **v3 PASSED** — two structural fixes, both principled: detection scores became per-span softmax posteriors over relations (comparable scale, sharp margins), and type compatibility became a **hard feasibility gate** (min link cosine ≥ 0.35) rather than a score term, with ranking by detection evidence + answer-type match.

**The design law this measured**: in detection∘unification planning, *evidence proposes, types dispose*. The question decides WHICH relations; unification decides only WHETHER an ordering is type-legal. Any scoring shape that lets type-compatibility outrank question evidence collapses to a question-independent argmax. This is the planning-level echo of the channel-separation law: question-dependent signal must dominate question-independent structure.

**Second finding**: relational participation is the correct type system for a store (D38 §2's bootstrap tier 5, confirmed independently). It is store-content (no external ontology), crisp by construction, and available to any new entity after its first few facts.

**Open (execution, not planning)**: P@1 lags chain-correct where walks need demote/exclude finesse (loc_cap_pop: chain 1.000, P@1 0.000 — 3-hop walk bug/limits; loc_big revisit semantics). Walk execution is v0.6's job; the planner it needed now exists with zero hand schema.
**Revisit**: when v0.6 replaces the spaCy span extractor with learned detection.

## 2026-07-22 — D1: Codec-first roadmap
Build and gate the NL↔latent codec before any reasoner/memory work. **Rationale**: every upstream failure is uninterpretable if the interface is unreliable; the codec doubles as the interpretability window. **Revisit**: never (ordering already paid for itself in prior art: LCM's failures were codec-boundary failures).

## 2026-07-22 — D2: Frozen BGE-M3 + whitening + trainable adapter as encoder base
**Rationale**: pretrained semantic organization and multilinguality for free; the sparse lexical output is a built-in identity channel no other embedding model offers; adapter+whitening hedges the retrieval-geometry mismatch (anisotropy) without retraining. **Alternatives**: SONAR (decodable by construction, no identity channel), ICAE/gist compressors (fidelity, no retrieval geometry). **Revisit**: if M1–M3 miss fidelity/robustness targets badly.

## 2026-07-22 — D3: Hybrid latent = dense gist channel + sparse identity channel ✅ confirmed
**Rationale**: resolves the tension between R1 (smooth/continuous, for reasoning and robustness) and R3 (discrete/exact, for values and identities). Reasoner operates on gist; identities stay quasi-symbolic — explicitly **out of the rotation algebra** (user-confirmed 2026-07-22). **Revisit**: M2 ablation quantifies the sparse channel's contribution.

## 2026-07-22 — D4: Block-diagonal rotations as binding operator — **NOT SUPPORTED in the frozen space** (probes ran same day)
Status: **first probes negative; decision deferred, not killed.** Three literatures converged on this family (FHRR/RoPE/RotatE) — strong prior — but in *our* space it doesn't hold up yet. Evidence (`results/rotations_v1.json`, docs/03): with a validated instrument (positive control recovers a known block rotation at cos 0.93 at d=64), block rotations fit to 10 lexical relations beat identity by only ~0.05 cosine and **lose on retrieval**; translation is comparable or better at every dimensionality. Methodological note: the first probe (full `O(1024)`, ~524k params from ~45 pairs) was degenerate and its negative result was an artifact — **positive controls are now mandatory for every geometry probe.**
**Live options before re-deciding**: (1) re-probe at *proposition* altitude — the tested relations were lexical, the reasoner transforms propositions; (2) induce rotational structure via a learned adapter objective rather than assuming frozen BGE-M3 has it; (3) evaluate affine/translation families, accepting the loss of norm preservation.
**Revisit**: after the proposition-altitude probe.

## 2026-07-22 — D10 CONFIRMED by the data-scaling curve (`results/scaling_curve_v0.json`)
Fixed compute (700 steps/point), identical held-out eval set, dense-only decoder:

| n_train | eval entity EM | eval number EM | train entity EM | train−eval gap |
|---|---|---|---|---|
| 549 | 0.000 | 0.062 | 1.000 | +1.000 |
| 1,099 | 0.012 | 0.065 | 1.000 | +0.988 |
| 2,198 | 0.060 | 0.076 | 0.991 | +0.931 |
| 4,397 | **0.113** | **0.147** | 0.585 | **+0.472** |

A textbook memorization→generalization transition: at 549 propositions the decoder memorizes perfectly (train EM 1.000) and generalizes not at all (eval 0.000); by 4,397 it can no longer memorize (train 0.585) and genuinely generalizes (eval 0.113). Eval EM roughly doubles per data doubling and is **still rising steeply at the right edge** — no saturation in view. Together with the linear probe (81% of numeric tokens linearly recoverable), this settles it: the identities are in the latent, and the bottleneck was training data, not representation.
*Caveat*: extrapolation beyond ~2× is unwarranted; such curves usually follow a power law and saturate eventually.

**Extension to 9,465 train (10,479-proposition corpus, 36 domains, same fixed 700 steps)**:

| n_train | eval entity EM | eval number EM | train entity EM | gap |
|---|---|---|---|---|
| 1,183 | 0.024 | 0.083 | 1.000 | +0.976 |
| 2,366 | 0.059 | 0.059 | 0.983 | +0.924 |
| 4,732 | 0.100 | 0.098 | 0.462 | +0.362 |
| **9,465** | **0.124** | **0.199** | 0.385 | **+0.261** |

Still rising (0.024 → 0.124 across 8×) and the gap keeps closing (+0.976 → +0.261). **But the last doubling yielded only +0.024 entity EM vs ~+0.05 for earlier doublings — the curve is bending.**

⚠️ **Confound — the deceleration was NOT data saturation.** Compute was held fixed at 700 steps, so large-data points were *undertrained*: 1,183 propositions get ~41 epochs while 9,465 get ~2.4.

**Disambiguation run — same 9,465 propositions, 12 epochs (~3,550 steps, 5× compute):**

| | 700 steps | **3,550 steps** |
|---|---|---|
| eval entity EM | 0.124 | **0.178** (+44%) |
| eval number EM | 0.199 | **0.278** (+40%) |
| exact reconstruction | 0.000 | **0.008** (first non-zero) |

**The bend was undertraining.** And comparing like-for-like at 12 epochs, doubling the corpus (4,397 → 9,465 train) lifted entity EM **0.115 → 0.178 (+55%)**, number EM **0.174 → 0.278 (+60%)**, cycle cosine **0.467 → 0.579**, and produced the first exact reconstructions. No saturation anywhere in view — D10 is confirmed on both axes, and data and compute must be scaled together.

**Third like-for-like point — 16,079-prop corpus, 56 domains (14,533 train, 12 epochs, 2026-07-22 late)**:

| corpus (12 ep) | eval entity EM | eval number EM | cycle cos |
|---|---|---|---|
| 10,479 / 36 domains | 0.178 | 0.278 | 0.579 |
| **16,079 / 56 domains** | **0.203** | **0.336** | **0.619** |

A 1.53× corpus (and 20 entirely new domains in the eval split) bought +14% entity, +21% number, +0.040 cycle. The curve is still climbing; exact-reconstruction rate returned to 0/250 (from 2/250), consistent with a harder, more diverse eval split rather than regression. Note the whitener/eval split changed with the corpus, so this row is not strictly the same eval set as the rows above — the trend, not the per-row deltas, is the claim.

## 2026-07-22 — D10: Codec fidelity is memorization-bound; scale the corpus before re-judging the sparse channel
**Finding**: decoder v1 reconstructs TRAIN propositions at 99% exact / 100% entity EM but eval at 0% / 11.5% — and a decoder-free ridge probe recovers 81% of held-out *numeric* tokens from the dense latent (2.08× the frequency baseline). The identities are in the embedding; the decoder memorized 4.4k propositions rather than learning to read them. The founding hypothesis is amended: **values are present but hard to decode**, consistent with vec2text.
**Decision**: treat eval fidelity as a data/regularization problem. Next codec run scales the corpus by ~10× (target 50k propositions via background generators), adds regularization/early stopping against the train–eval gap, and only then re-judges the sparse channel.
**Also**: the sparse channel is currently *ignored* (shuffling it changes nothing) — before re-testing, fix (a) gradient pressure (dense alone reaches loss 0.02, so nothing forces identity use — try dense-channel dropout, forcing identity reliance) and (b) scale (sparse prefix norm is 0.27× dense; normalize or learn a gain).
**Revisit**: after the scaled run.

## 2026-07-22 — D14: The routing decision — keep BGE-M3 as backbone; the structure channel is BUILT, not bought
Joint result of the two D12 probes (`results/structure_linear_probe.json`, `results/encoder_bakeoff.json`).

**Encoder bake-off** (5 encoders, own whitened space each; ordering AUC = P(inverting pair sits farther than preserving pair); flagship = does argument_swap sit below paraphrase?):

| encoder | objective class | ordering AUC | swap<para? | num-recall lift | domain purity@10 |
|---|---|---|---|---|---|
| bge_base | retrieval | 0.643 | ✗ | 2.72× | 0.719 |
| all_mpnet | broad contrastive | 0.680 | ✗ | 2.18× | 0.707 |
| **bge_m3** (incumbent) | retrieval | 0.686 | ✗ | **2.71×** | **0.737** |
| nli_mpnet | NLI | 0.747 | ✗ | 2.61× | 0.721 |
| **sup_simcse** | NLI + contradiction hard-negatives | **0.772** | ✗ | 2.59× | 0.709 |

Three facts: (1) **No off-the-shelf encoder orders argument swap correctly** — swap sits at 0.92–0.98 cos in all five; role-blindness at the pooled level is a property of the sentence-embedding genre, not of BGE-M3. (2) **NLI-class objectives genuinely help aggregate ordering** (+0.09–0.13 AUC over retrieval-trained) — the contradiction-as-hard-negative signal moves the geometry the right way, just nowhere near far enough. (3) BGE-M3 remains best on identity retention and domain geometry — its original selling points survive.

**Linear structure probe** (parameter-free, permutation-controlled): the swap displacement in BGE-M3's pooled latent is *systematically aligned* with embed(A)−embed(B): alignment |0.280| vs null 0.046 (6×), sign consistency 75%, though the displacement is only ~16% of a random inter-proposition distance. **Role information survives pooling — tiny but structured.** And negation has a *single consistent linear direction*: 0.373 mean pairwise cosine between difference vectors (null ~0), **100% held-out classification** by projection. Polarity is literally a steering vector.

**Decision (the turns):**
1. **BGE-M3 stays** as the gist+identity backbone (D2 reaffirmed with bake-off evidence).
2. **The structure channel is built, not bought** — no swap fixes it. Build sequence, cheapest-first:
   a. **Axis amplification** (hours): retrain the adapter with objectives that target the *measured* structural axes — amplify the component of z aligned with the polarity direction and the entity-difference direction — instead of naive hinge push/pull, which D11/D12 showed gets satisfied by lexical shortcuts. Category-held-out validation, geometry guardrails, as established.
   b. **Learned structural pooler** (a day): if (a) plateaus, pool BGE-M3's *token-level* embeddings with a small trained attention pooler supervised on the 20-type pairs — token embeddings carry order at full strength; mean-pooling is where it dies to 16%.
   c. Symbolic SRL slots (the D3 mirror) stays the fallback.
3. **Re-diagnosis of D11/D12**: the adapter failures were an *objective* problem, not (as first believed) pure information loss — the hinge loss never had to find the structural axes when lexical detectors were cheaper.
**Revisit**: after (a).

## 2026-07-25 — D40: Canonicality follows epistemic type, not storage location; the gist is the interlingua
Two design positions from discussion (user-driven), amending T6:
1. **Three-tier canonicality.** (i) CONSTITUTIVE — math, logic, type system, epistemic primitives: in our stack these live as SYMBOLIC PROCEDURES (ALU, unification, scoring algebra), which is stronger than weights-canonicality — deterministic and verifiable, immune to parameterized-arithmetic failures. Not overrulable by store writes (constitutive circularity: the store cannot overrule modus ponens with an argument that runs on it); revisable only through the GLACIAL channel with a high evidence bar — which is what actually happened to rotations (D4/D15) and the walk "invariants" (D30): overruled by rebuild, not by write. (ii) SKILLS (weights) — canonical about how, silent about what. (iii) CONTINGENT (store + promoted cache) — store canonical, crystallized copies flaggable-stale (D39's measured tier). **The user's overrulability intuition lands in Track I: a VIEW may locally MASK even constitutive knowledge (counterfactual/fictional contexts) — suspend-in-a-view is cheap, scoped, and safe; revise-globally is gated and glacial. Two operations the architecture keeps distinct, which a monolithic crystal cannot.**
2. **Language agnosticism is inverted from the classical picture**: the continuous gist is the interlingua (BGE-M3 multilinguality — a founding D2 selection reason, not yet cashed); the SYMBOLIC channels are parochial (surface-token identity matching breaks cross-lingually; role_bits and cue prototypes are English-bound). Engineering consequences: canonical entity IDs with per-language surface forms (A6a's alias fix, generalized); per-language parse front-ends behind the role-bit interface; multilingual instances inside relation prototypes (detection-as-retrieval absorbs this natively); language as entry metadata = a VIEW dimension (source language as provenance, translation uncertainty as an epistemic bit); output languages = H2 alignment runs, per the module contracts. Probe queued as J5: cross-lingual retrieval (French/German queries against the English store) with the gist and identity terms measured separately — prediction: gist holds, identity term goes silent, quantifying exactly the symbolic translation gap.

## 2026-07-25 — D39: J1 — the crystallization dial, measured in one system (`results/promotion_j1.json`)
500 hot facts LoRA-distilled into Qwen3-0.6B (plain-QA format, H1 safe config); both poles evaluated on UNSEEN phrasings; 100 of the same facts then superseded in the store.

| | crystallized (weights) | externalized (store) |
|---|---|---|
| accuracy | **0.987** | 0.900 |
| latency/query | 279 ms | **78 ms** |
| after edits | **98% STALE, 0% updated** | 0.78 updated (see below) |

**Finding 1 — the promotion rationale INVERTS in this architecture**: crystallized recall requires autoregressive generation; store addressing is one encoder pass + arithmetic — the store is 3.6× FASTER. Promotion buys hot-set accuracy (+0.087) and store-independence, NOT latency. T6's cache analogy needs this correction: weights are a slower, more accurate, unfixable cache here.
**Finding 2 — staleness measured exactly**: crystallized copies answer the OLD world at 98% with 0% uptake of edits — the frozen-knowledge failure, quantified inside the same system that demonstrates the cure.
**Finding 3 — the store's update rate traced through its fix arc**: threshold targeting 0.51 → D33-spec identity-agreement targeting **0.78** (fired 100/100; 22 residual wrong-targets are same-subject/different-relation entries, eliminated by design once relations-as-entries (D38) gives every entry a relation label → targeting becomes subject ∧ relation = exact). The remaining gap to ~1.0 is scheduled work, not open research.

T6's first probe stands: both dial positions instrumented, the trade quantified (accuracy vs speed vs editability), and the frontier pole's terminal defect (staleness with no backing store) reproduced in miniature.

## 2026-07-25 — D38: Design session — the schema moves into the store; bootstrap tiers; T6 crystallization spectrum
Three corrections/extensions from design discussion (user-driven), logged before implementation:
1. **D37's planner inputs were closed-world schema living in code** (SIG/CUES/ANS_CUE) — the rigidity is not acceptable and the relational markers ("prepositions") are themselves knowledge. **The schema moves into the store**: relations become entries (learned operator vector + SOFT signature profiles over actual subject/object populations + instance provenance + surface cues); types become data-derived clusters refined by relational participation (a "city" IS the kind of thing with population/located/mayor facts); detection becomes RETRIEVAL over relation entries (scales with inventory, no fixed head); unification becomes additive SCORING (exact unification = the crisp-signature limiting case, which is why v0.5 looked magical on world v4); new relations are writes proposed by the ingestion surprisal gate. Validation experiment specified: zero-hand-schema planner on world v4, same holdouts.
2. **Bootstrap hierarchy + stratified timescales** (the chicken-and-egg resolution): geometry (frozen encoder) → coordinates (whitener/anchors, unsupervised) → coarse types (embedding clusters, NO relations needed) → seed relations (~20 instances each) → refined types from participation → alternate (EM over structure). Update tiers: fast = entries/writes; medium = operators/type profiles/cues (ALL closed-form means and clusters — streaming-updatable, no gradients); slow = anchors/whitener/heads (the cascade); glacial = encoder/decoder (H2 align-many). The KB DOES update during training; non-stationarity is guarded by size-invariant policy features (normalized store readouts) + floors re-measurement after slow-tier refits. Anchor minimization reframed: it measures the MANDATORY SHARED CORE (the basis both sides must speak), and its deferral (D6) was correct because types/operators needed the headroom.
3. **T6 added to the vision** (see 00-vision.md): the crystallization spectrum, promotion as cache policy with the store canonical, and the expressivity invariant — basis reduction bounded by full expression over known AND novel content, with expression SIZE as a measured quantity.
First T6 probe: the **promotion/staleness demonstration** — crystallize the store's hot facts into weights via LoRA, measure the latency/accuracy win, then run edits and measure the crystallized copies going stale while store-resident facts update. Both poles of the dial instrumented in one system.

## 2026-07-25 — D37: Composition SOLVED by typed unification — rung 2 passes; the reasoner's final shape (`results/typed_planner_v05.json`; lineage v0.2–v0.4 in `hop_policy_v02/03/04.json`)
The chase, recorded in full because the negative results carry the argument:
- **v0.2** (parse cue features added): holdouts unchanged at 0.000 — representation added, no gradient pressure (training loss was already ~0; the D10 lesson recurring at the policy level).
- **v0.3** (question-gist dropout, the D10/D21 fix): still 0.000 — the shortcut wasn't the gist; it was the CUE-SET lookup itself, which is extensionally perfect on training data because type constraints make every trained hit-pattern unique. Nothing forces a comparative rule when a lookup table achieves zero loss.
- **v0.4** (depth feature fixed — spaCy token views broke identity comparison; the disambiguating feature had been CONSTANT through v0.2–0.3): 0.020. Even with the right feature, live and pressured, BC does not induce the composition rule from 9 compositions.
- **v0.5 — the reframe: the chain is not a learning target. It is COMPUTABLE by type unification**: chain = ordering of detected relations s.t. domain(r₁)=subject type, range(rᵢ)=domain(rᵢ₊₁), range(r_k)=answer type. Subject types come from the store's own facts; answer types from wh-words. Results on the SAME holdouts BC scored 0.000 on: **big_pop chain-correct 1.000, end-to-end 0.553** (gold-chain oracle: 0.600 — the planner matches it); **cap_mayor 0.353**; no-answer abstention **1.000** (type-invalid → structural abstain).

**The law's fifth altitude, now with its constructive converse**: composition is structure; structure is symbolic — and once treated symbolically it is not merely learnable but EXACT. Residual failures are all upstream in the hand-written cue lexicon and answer-typing (chain-correct 0.000 on hq_mayor/loc-chains = detection gaps, not mechanism gaps).

**The reasoner's final shape falls out** (v0.6, next): learned relation DETECTION (the v0.1 head — already beats floors per-relation) ∘ typed chain ASSEMBLY (unification, exact) ∘ store EXECUTION (D27 arithmetic) ∘ learned HALT/ABSTAIN (B2 readouts, 0.97–1.00). Every stage on the substrate that wins it. This is TagOp/QPL's small-model lesson (Track F) applied to the composition level itself, and it is what T1's claim will rest on: the "reasoning" a small system needs is detection + typed planning + retrieval arithmetic — no simulated computation in weights anywhere.

## 2026-07-25 — D36: Composition density does NOT buy transfer — the program law's FOURTH appearance, now at question understanding (`results/hop_policy_v01.json`, world v4)
v0.1: nine trained compositions with shared hops (world v4: 8,859 facts, 9 relations, 12 compositions), three held out. Trained behavior is healthy — five new compositions work (mayor_born 0.613, hq_pop 0.579, hq_loc 0.452), loc_cap/loc_big now BEAT their oracle floors (0.176/0.136 vs 0.140/0.073), abstention holds (0.967, zero false), single 0.755. Mild interference on cap_pop (0.764→0.681) from the enlarged action space.

**Holdout verdict: 0.000 / 0.000 / 0.092.** The damning case is cap_mayor = 0.000 with capital_of trained AS a first hop (cap_pop) and mayor_of trained AS a second hop (hq_mayor) — both pieces, both positions, zero pairing transfer. The only nonzero (hq_loc_cap 0.092) flows through a TRAINED PREFIX (hq_loc). So the failure is localized to **step-0 routing of unseen pairings**, and the mechanism is our own law, fourth appearance: the policy reads the question as a pooled gist, the gist is TOPIC-ONLY (D32), and the NESTING ORDER of "the mayor of the capital of X" is content-conditional structure — precisely what pooled vectors cannot carry (D16: codec; D21/22: decoder binding; D26: memory hops; now: question understanding). BC quantity cannot fix a representational deficit.

**v0.2 design, fixed by this diagnosis**: give the question's structure a structured channel — parse-derived decomposition features (the question's syntactic head chain IS the hop chain: mayor→capital→X), and/or the question's s-vector into the relation head. Prediction to pre-register: with nesting made explicit, cap_mayor transfers (both hops are in-repertoire); big_pop needs largest_city_of to also appear as SOME hop-1 during training or a decomposition feature naming it. Self-imitation stays queued behind this — exploration cannot help a policy that cannot REPRESENT the right first action.

## 2026-07-25 — D35: Reasoner v0 — rung 1 PASSES, abstention transformed, composition transfer ZERO (`results/hop_policy_v0.json`, `checkpoints/hop_policy_v0.pt`)
First trained policy: a **1.19M-parameter MLP applied per step** (weight-tied recurrence — hop count = loop count, T4's instrument), heads = 9-way action (7 relations + HALT + ABSTAIN), features = question gist + current entry gist + B2 store readouts. Teacher-forced BC from gold chains (not oracle successes); big_pop held out as an ENTIRE composition; 30% entity holdout elsewhere.

**Rung 1 (clone + infer, held-out entities): PASSED.** The policy is not handed relation chains — it infers them — and matches or beats the oracle on every trained composition: single 0.743→**0.775**, cap_pop 0.756→**0.764**, ceo_born 0.375→**0.411**. First evidence for T1's mechanism: a tiny learned controller drives store-arithmetic reasoning at least as well as the hand-coded pipeline that taught it.

**Abstention: transformed.** No-answer abstain recall 0.061 → **0.966 with 0.000 false-abstains on answerable queries** — the learned head fully harvests the id-coverage signal (B2, AUC 0.952) that the oracle's fixed threshold wasted. The largest single policy-over-oracle gain in the program.

**Rung 2 (held-out composition): FAILED at 0.000, recorded with full prominence.** big_pop chains (largest_city_of ∘ population_of — both relations individually trained) are misrouted into nearest trained patterns; BC over two 2-hop compositions does not compose. Exactly the DGPO-literature prediction for cloning without coverage or improvement. Minor: loc_cap/loc_big slip slightly below their (already weak) oracle floors — relation-sequence inference errors compound on noisy chains.

**v0.1 design, fixed by this result**: (1) composition-DENSE training world (v4: many compositions over the same relations so composition-space is sampled, plus Track F compute questions); (2) the guided-improvement loop — exploratory rollouts in HopEnv, keep successes, retrain (self-imitation; full RL only if that stalls); (3) then re-test composition holdout — the honest rung-2 claim requires it to pass with compositions STILL held out of the denser world.

## 2026-07-25 — D34: A8 equal-bit control — channel separation IS the mechanism; Track A complete (`results/decoder_v2e_eval.json`)
The reviewer-demanded ablation: identical identity strings, hash-embedded and concatenated INTO the dense channel (z_dim 2048, no symbolic slots, no s), decoder otherwise identical, same training budget. **v2e collapses to dense-only levels**: entity 0.178 / number 0.317 / binding 0.229 (v2t: 0.462/0.720/0.617; dense-only v0: 0.203/0.336) — and degrades under noise (number 0.317 → 0.214 at σ=0.8) exactly where v2t is flat, because the identity information rides the noised channel. Training was healthy (final loss 0.0160 ≈ v0's 0.0162): the information went in; it is not RECOVERABLE from the continuous substrate. **The symbolic channel's win is architecture, not information content** — sixth independent confirmation of the program law, and the codec paper's central ablation. TRACK A IS COMPLETE.

## 2026-07-25 — D33: Sprint tail — edit transparency pays its bill; OOD is a graded cost, not a collapse (`edit_stress_a6b.json`, `ood_codec_a7.json`)
**A6b — supersession at n=200 on the de-templated world: 0.605** (was 0.900 at n=20), chained 0.640; controls hold (0.870) and the adversary's id-union pollution worry measures MINOR (3%). Diagnosis is precise: under varied edit phrasings the threshold-based shadow **fired only 114/200** (match scores p10 0.813 vs threshold 0.88), and **31 of the fired supersedes hit the wrong entry** under collisions. D25's "edits transparent" carries a templated-world qualifier; the fix is specified for store v1: supersession targeting must require subject-identity agreement + same-relation region — channel ownership, not a raw score threshold.

**A7 — real-Wikipedia OOD (n=59 sentences, 75 entities / 112 numbers): graded degradation, no collapse.** Number EM 0.720 → **0.571**, binding 0.617 → **0.429** (multi-number prose saturates the 24 slots, as predicted); entity EM **0.693** (real-world entity tokens are easier than invented syllable names — not like-for-like, but no entity failure); **σ=0.5 noise-invariance HOLDS out of distribution** (0.693/0.580/0.455 — flat). Frame drift visible in samples, consistent with D32. In-distribution tables now cite these as the OOD companion numbers. Method note: the first A7 run scored ~0 — a probe bug (BGE-M3 sparse dicts are keyed by token-ID strings; feeding IDs as identity text makes the decoder hallucinate numerals). The sparse-decode step should move into a shared helper before it bites a third script.

**A4 disposition**: new probes carry bootstrap/rank CIs (A5 shipped with one); the retroactive CI annex over old JSONs is deferred — every decision that hinged on a thin delta has been individually re-examined by the sprint anyway.

**A8 launched** (equal-bit control: identities hash-embedded INTO the dense channel, z_dim 2048, no symbolic slots — the architecture-vs-information ablation). Prediction: v2e loses to v2t especially under noise, because h rides the noised channel. Results next entry.

## 2026-07-25 — D32: A2 — the gist is TOPIC-ONLY; the frame lives in the symbolic channels (`results/frame_cycle_a2.json`)
The adversary's falsification design, executed: decode under true / same-domain-wrong / null gist (true symbols throughout), mask all identities to placeholders in recon AND reference, then compare. **True vs wrong gist: masked-cycle 0.750 vs 0.740 (+0.010); predicate recall 0.762 vs 0.746 (+0.016). Null gist: 0.729/0.742.** With identity anchoring removed from the instrument, the gist's frame contribution is 1–2 points; a null gist still yields 74% predicate recall from symbols+s alone.

**Corrections, banked with full prominence**: D24's "the symbolic channels error-correct the gist" becomes "the symbolic+structure channels carry essentially all reconstruction-relevant content — frame included; the gist supplies topic selection." D28's "including the frame" reading is retracted; its anchor-collapse result survives but now reads as near-tautology (any topic-adjacent gist suffices because topic is all the gist contributes). D19's projector interpretation should be revisited under this lens.

**Design consequences**: (1) the reasoner's working state can be more radically discrete than planned — the continuous channel it must maintain is a topic pointer, not a thought; (2) the codec paper's story sharpens: not "error-correcting decoder" but "a sentence codec whose semantic load rides discrete channels, with a continuous topic hint" — more novel and now measured with an identity-clean instrument; (3) open question worth one probe later: how much of the frame is in s (192-d, trained) vs the tagged sparse heads — s-shuffled masked-cycle would split them.

## 2026-07-25 — D31: Sprint results — halting is free, abstention = identity coverage; the structure channel and identity rule get their natural-text bills; binary store keys are ~free (`halt_signal_b2.json`, `frozen_battery_a5.json`, `store_quant_e1.json`)
**B2 ✅ both halves answered.** HALT: on successful walks every cheap store readout separates done/mid at ~1.00 and done/overstepped at 0.96–0.99 — halting is a trivial READOUT, as the literature triangulation predicted; no learned gate needed. ABSTAIN: margin is useless (0.501) and top-1 weak (0.648), but **identity coverage — the fraction of query ids present in the retrieved entry — hits AUC 0.952**. The reasoner's abstain head is one arithmetic feature.

**A5 ✅ frozen battery (scored once, stands as scored): struct AUC 0.767 (CI 0.702–0.828) on naturally-phrased constructions** vs 0.942 templated. Split verdict: the VALENCE machinery generalizes beyond its training forms ("failed to" −0.240, "hardly" −0.324 — caught harder than trained negation); the losses are preserving types outside the symbolic normalizations — converse predicates 0.523 (D18's "accepted limitation" now has its measured cost), free paraphrase 0.604, unnormalized clefts 0.669 — plus a deontic-modality coverage gap (0.667, marginal). The 0.942 was synthetic-pair inflation; 0.767±0.06 is the honest natural-text number.

**A6a ✅ the identity channel's ROC curve exists after all: 43% false-flag rate on natural reformatting pairs.** Value-transforming reformats ("3 pm"↔"15:00", dozen↔12, m↔cm) are bidirectional strandings BY CONSTRUCTION — D23's rule only defuses subset-style reformatting. On natural text the identity flag must be soft evidence or gain semantic normalization (time/unit/alias resolution); the templated-world "zero false flags" is retired as a general claim.

**E1 ✅ with an asymmetry worth keeping**: int8 store keys are FREE (0.807/0.857 = fp32 at 4×); **binary keys nearly free (0.780/0.841 at 32×, 128B/key — the design point)**; but anchor-code keys (2B) collapse retrieval (0.048 gist-only) even though D28 proved they suffice for DECODE. Decode tolerance ≠ retrieval key resolution: reconstruction leans on symbols; discriminating ~6k near-duplicate keys needs the fine structure. D28's compression implication is hereby scoped to the decode path.

**Sprint scoreboard after this entry**: A1 ✅ A3 ✅ A5 ✅ A6a ✅ B1 ✅ B2 ✅ E1 ✅; A2 in flight; remaining A4 (CI annex — A5 carried its own bootstrap), A6b edit stress, A7 OOD, A8 equal-bit control, C0 spec rewrite.

## 2026-07-25 — D30: A1 de-templating — the adversary was right; the 0.998 floor is RETIRED and the reasoner inherits a real problem (`results/memory_v3.json`, world: `gen_closed_world_v3.py`)
World v3 removes every enumerated crutch: 258 colliding city names + 301 shared surnames, 5 store templates/relation, 12 query phrasings/relation from a different generator (4 held out from all fitting), 6 hop compositions incl. a 3-hop and a revisit pattern, temporal capital pairs, no-answer queries.

**Survived (cut, not killed):**
- **Single-hop translation addressing: 0.85–0.90** (from 0.99) — inside the adversary's predicted band. Critically, **held-out phrasings ≈ seen phrasings** (0.852/0.904 vs 0.867/0.901): once fit across diverse phrasings the operator is phrasing-GENERAL — the earlier 0.99 was template inflation, but the mechanism itself is not template-bound.
- **Identity rescoring earns its keep under collisions**: +0.04–0.05 consistently (with D29's on-manifold result, its role is now measured twice over).

**Broken, recorded with full prominence:**
- **Multi-hop compounds and collapses**: cap_pop 0.808 (≈ single-hop² — consistent with pure error compounding), but ceo_born 0.370 (shared surnames make `hand = ids(entry) − ids(query)` match the wrong person's birth fact), loc_cap 0.270 (city-name collisions poison the first hop), **3-hop 0.000**. The 0.998 stands only as "achievable when identity tokens are globally unique and templates single."
- **Walk semantics are heuristics, not invariants — confirmed by their own test**: on the revisit composition (answer sometimes IS the source city) they *hurt*: 0.187 with demote/exclude vs 0.327 without. D27's "these aren't tuning hacks" claim is formally retracted; they become soft, learnable ACTIONS in the HopEnv (C1), exactly as the plan's contingency specified.
- **No-answer is not readable from top-1 score** (answerable 1.120 vs no-answer 1.091, distributions overlap) — abstention/halting needs a richer signal; feeds B2 directly.

**Why this is the right kind of bad news**: the hand-coded oracle is no longer a solved pipeline the reasoner merely imitates — it is a WEAK baseline with measured failure modes (selective hand-off, collision disambiguation, revisit handling, abstention) that a trained policy has genuine headroom to beat. The gap analysis' E3 warning ("promote-mask needs to be selective, not ids(entry)−ids(source)") is confirmed as the first-order defect. Track C's imitation targets become per-composition floors: {cap_pop 0.808, big_pop 0.600, ceo_born 0.370, loc_cap 0.270, loc_big 0.327 (walk-off), 3-hop 0.000}.

**Corrections banked**: D25/D26/D27 headline numbers now carry the qualifier "templated world"; D27's walk-invariant claim retracted; the D28 anchor-collapse result is untouched by this (different axis) but inherits the same synthetic-register qualifier pending A7.

## 2026-07-25 — D29: Hardening sprint, first results — relation choice is linear (B1); identity rescoring's real job found (A3) (`results/relation_select_b1.json`, `onmanifold_noise_a3.json`)
**B1 — relation selection is linearly separable: 1.000 test accuracy** (6 classes incl. the composed-2-hop class; shuffled-label control at chance 0.205). The reasoner's one unmeasured obligation — map a question latent to a relation-operator choice — is a linear readout on this world. The "ultra-wide" clause of 05-reasoner.md is retired pending one confirmation: re-run on world v3's 12-phrasings-per-relation queries (template-boundness is exactly what the adversary flagged, so this stays provisional until then).

**A3 — the invariance framing dies; the architecture story strengthens.** Against ON-MANIFOLD drift (query latent interpolated toward a same-relation different-entity fact — the reasoner's real error mode), gist retrieval collapses precisely where isotropic noise cost nothing (P@1 0.745 → 0.128 at cos 0.80 → 0.000 at 0.70; isotropic reference was 0.732 at cos 0.55). And identity rescoring — twice predicted to activate and twice flat — activates decisively: **+0.857 at cos 0.80, holding 0.985 where the gist is dead**, still 0.795 at cos 0.55. Corrections to the log: D24's claim narrows to "invariant to off-manifold perturbation" (direction, not magnitude, was doing the work); D25/D27's "rescoring never activates" narrows to "never activates under isotropic noise." The design consequence is clean: the reasoner may emit sloppy gists ONLY because the identity channel catches confusable drift — the two channels are load-bearing together, neither alone. Curiosity noted: mild drift toward a same-relation fact (cos 0.9) improves gist retrieval (0.797 > 0.745) — moving toward the fact-statement region acts like a weak t_rel.

## 2026-07-25 — D28: Expressibility gate (T2) PASSES — and the anchor requirement collapses (`results/expressibility_v0.json`)
Held-out gists replaced by k-means anchor projections (anchors fit on train only), decoded through the shipping codec with identities/s intact. Pre-registered prediction (D24): quality equals baseline wherever approx cos ≥ ~0.78. **Reality is far stronger — quality equals baseline at cos 0.34:**

| gist input | input cos | entity EM | number EM | binding | cycle-vs-TRUE |
|---|---|---|---|---|---|
| true gist | 1.000 | 0.471 | 0.691 | 0.604 | 0.808 |
| nearest anchor alone, N=512 | 0.343 | 0.459 | 0.665 | 0.538 | 0.786 |
| 32-anchor projection, N=4096 | 0.666 | 0.488 | 0.709 | 0.588 | **0.811** |

(All 9 sweep conditions — N ∈ {512, 1k, 4k} × m ∈ {1, 8, 32} — sit within noise of baseline on EM/binding.)

**Readings:**
1. **T2 passes**: `anchors + operators + symbols` is sufficient for expression. A 32-anchor projection is end-to-end indistinguishable from the true gist, *including the frame* (cycle 0.811 vs 0.808); even one anchor in 512 costs only 0.02 cycle.
2. **Why the requirement collapsed**: the architecture already moved the unbounded content (entities, values) to symbols, so the continuous span only has to cover *type space* — frames, templates, topics — which is compact. The anchor budget question was implicitly "how many anchors to span propositions?"; the real question was "how many to span proposition *types*?", and the answer is orders of magnitude smaller. D6's over-provisioning to 100k was insurance against the wrong risk; the user's "low thousands" hunch is confirmed with margin to spare — **hundreds** are close to sufficient.
3. **The codec is an error-corrector** (D24's anchor thesis, extended): from a gist two-thirds of the way to unrelated, symbols+structure regenerate the proposition and re-encoding lands back at the true address. For the reasoner this compounds D24: predicted latents can be *very* coarse — effectively "which anchor neighborhood + which symbols."
4. **Caveat for honesty**: EM/binding are symbol-dominated metrics and could not have failed this gate alone; the frame-sensitive cycle check is what makes the pass meaningful. And this corpus's type diversity (56 domains, single-sentence propositions) bounds the claim — richer discourse types may need a larger span. Revisit at reasoner-scale tasks.

**Anchor minimization (D6's deferred workstream) is now open and cheap**: the N-sweep is flat down to 512 — the breaking point lies BELOW 512 and can be found in one afternoon when it matters.

## 2026-07-25 — D27: The triple-coherent hop — 0.998 with no text and no codec pass; the reasoner's hop primitive is defined (`results/hop_v1.json`)
D26's open question — can anything latent close the hop gap — answered by three challengers against the 0.06 constant-translation floor (all text-free between hops, 400 held-out chains):

| hop mechanism | P@1 |
|---|---|
| B constant translation (control — reproduces D26) | 0.060 |
| B′ ridge linear map, α=0.1 / 1.0 / 10.0 | 0.552 / 0.273 / 0.068 |
| **D triple-coherent: `z₁+t_hop` ⊕ identity hand-off ⊕ walk semantics** | **0.998** |

**D matches the codec loop (0.998 = 0.998) at a fraction of the cost** — no decode, no re-encode. The hop primitive is pure store arithmetic over the triple:

    hop(state) = retrieve( gist   : z_prev + t_relation        ← template level
                           promote: ids(prev_entry) − ids(walk source)
                           demote : ids(walk source)           ← attention moves ON
                           exclude: visited entries )          ← walks don't backtrack

Getting there required two pieces of **walk semantics** now in `MemoryStore.query` (`demote_ids`, `exclude`): without them the naive triple hop self-retrieves (fact₁ contains the handed-off entity too and `z₁+t_hop` stays near z₁ — measured 0.070). These aren't tuning hacks; they are the graph-walk invariants any multi-hop reasoner needs, discovered by the probe failing without them.

**B′ is the theoretically interesting middle**: an input-dependent linear map recovers half the chains (0.552), so entity routing is *partially* linear — and only at light regularization, meaning the routing signal lives in fragile low-variance directions (the same place D10's ridge probe found the identities). D26's law refines: *constant* operators are dead for entity-dependent hops; linear conditioning gets halfway; the identity channel closes it exactly.

**Also settled (negative, twice now)**: identity rescoring on single-hop retrieval does NOT activate under isotropic query noise — Δ ≤ +0.010 even at latent cos 0.55, because whitened gist retrieval itself barely degrades (0.763 → 0.732 at σ=1.5, a remarkable robustness result in its own right, consistent with D24). Rescoring's real role is *structural* — the hop hand-off — not error correction. Stop predicting it will "activate"; it already has the job it was built for.

**For Phase 3**: the reasoner's interface to memory is now specified and measured — continuous relation steering + symbolic identity bookkeeping + walk state. A trained reasoner's job reduces to *emitting* these hop calls (choosing relations, managing the walk) rather than simulating retrieval in weights. Baseline to beat stands at 0.998 hand-coded.

## 2026-07-25 — D26: Memory at 9.9k + 2-hop composition — latent-only hops are DEAD, symbolic hand-off is mandatory, and it's D16's law again (`results/memory_v1.json`)
Closed world scaled 27× (9,900 facts, 7 relations — `data/closed_world_v1.json`), plus 400 two-hop cases ("population of the capital of X") run three ways.

**Scale (D25 gates at 9.9k):** paraphrase P@1 0.794→0.763 (27× the near-duplicates cost 3 points — the whitened gist scales better than predicted); relational translation addressing **improves** to 0.991 (more fit pairs per operator) and reaches **1.000** with identity rescoring. The rescoring-activation prediction from D25 was only *partially* right: on paraphrase queries it is still a no-op (+0.004) even at 9.9k — the activation regime, if it exists, needs noisy query latents (D24), not just scale. Edit gate underpowered at this world's query sampling (n=4) — the 360-world measurement stands.

**2-hop composition — the reasoner question, answered for this space:**

| chain | P@1 |
|---|---|
| hop-1 operator addressing (`z_q + t_cap`) | 0.998 |
| A composed operators, no grounding (`z_q + t_cap + t_hop`) | **0.003** |
| B latent chain WITH retrieval snap (`z(fact₁) + t_hop`) | **0.062** |
| C symbolic hand-off (read capital from fact₁, re-encode, `+ t_pop`) | **0.998** |

A-vs-B: grounding the intermediate (snapping to the true fact latent) barely helps — grounding is not the failure. B-vs-C is the finding: **the hop displacement is content-conditional** — where the answer fact lives depends on the *intermediate entity's identity*, and a fixed translation carries only the relation-template mean. This is D16's law (fixed maps cannot carry entity-dependent structure) recurring at the addressing level, third appearance overall (codec structure channel, decoder binding, now memory hops).

**Consequences:**
1. **Naive latent-only multi-hop reasoning (fixed-operator Coconut-style) is refuted for this space.** The reasoner must interleave continuous ops with **symbolic identity hand-offs between hops** — precisely the triple's division of labor, and the hand-off needs only the identity channel (the capital's name is IN fact₁'s identity slots; no full text decode required in principle).
2. **A hand-coded 2-hop chain runs at 0.998 end-to-end** — this is simultaneously the working QA pipeline the T3/T5 gates were waiting for, and the floor any trained reasoner must beat (D8 spirit: the baseline exists before the model does).
3. One program-wide law, three scales: continuous operators own *type-level* transformations (valence, relation templates); *entity-dependent* information must ride symbolic channels. Phase-3 reasoner design starts from this, not from hope.

**Revisit**: whether a *conditioned* (entity-keyed) hop operator — e.g., translation + identity-gated addressing per hop — can close latent-B without text; that is a reasoner-architecture question now.

## 2026-07-25 — D25: Memory store v0 passes the Phase-2 retrieval gate — translation addressing at 0.99, edits transparent via key/value separation (`results/memory_v0.json`)
First Phase-2 artifact: `codec/memory_store.py` + a deterministic closed world (`scripts/gen_closed_world.py`: 360 facts over invented entities, 5 relations, near-duplicate templates so **identity, not lexical luck, is what retrieval must resolve**; 720 queries whose phrasings share no template with stored facts; 20 supersession edits).

| gate | result |
|---|---|
| paraphrase addressing, P@1 among 360 near-duplicates | gist 0.794, +identity rescore 0.797 |
| relational addressing (`z_query + t_rel`), held-out 70% | raw 0.905 → **0.988** → 0.992 with identity |
| knowledge edit: post-edit queries resolve to NEW object | pre 0.900 → post **0.900**, controls 0.850 unchanged |

**Three findings:**
1. **Relational translation addressing works at store scale** — the T2 one-algebra claim's first store-side confirmation: a closed-form mean displacement (fit on ~22 pairs/relation) lifts P@1 to 0.99. The paraphrase condition's misses are almost all *relation confusion within a subject* (capital vs largest-city), which is exactly what the operator resolves — the reasoner supplying the intended relation at query time is the designed division of labor.
2. **Identity rescoring is a no-op at this scale** (+0.003) — and the reason is instructive: queries name only the *subject*, and every fact about that subject matches equally. Identity discriminates entities; the gist discriminates relations; at 360 facts the gist already handles entities. Expect rescoring to matter at scale or under reasoner-noised query latents (D24 says the gist may be sloppy — that is when the identity term should earn its keep).
3. **Keys and values must separate at supersession.** Naive shadowing targeted perfectly (20/20, zero wrong targets) yet 7/20 post-edit queries drifted to the subject's *other* fact — updates arrive event-phrased ("was MOVED to") while queries keep arriving at the state-phrased address. Fix: `supersede()` gives the new entry the old entry's **address** (key) while its text/identities are the value — post-edit accuracy snapped to exactly pre-edit level. Non-destructive, provenance kept (shadowed entries remain inspectable).

**Still open for the full Phase-2 gate**: sequential-domain forgetting curves (T5) and small+store vs larger-dense (T3) — both need the reasoner or at least a QA head; parked until then. **Revisit**: identity rescoring when the store passes ~10k entries or queries come from a reasoner.

## 2026-07-25 — D24: Under the triple, output quality is invariant to gist noise through σ=0.8 — the symbolic channels are an error-correcting anchor (`results/cycle_noise_decoder_v2t.json`)
The D21 follow-up question was what gist noise costs the *semantic frame*, since EM stays flat by design. Answer: through σ=0.8 (latent cos 0.78 — **twice the training noise range**), nothing measurable. Cycle cos 0.808→0.811, binding 0.604→0.599, EMs flat (n=150). Dense-only v0 had already collapsed to 0.13/0.32 EM at σ=0.5; the triple doesn't budge at σ=0.8.

**Reading**: with identities and structure pinned symbolically, the decoder reconstructs the right proposition from a degraded gist — the side channels error-correct the continuous channel. Together with D21's conflict result (identities dominate gist) this bounds the gist's role under the triple: topic/frame selection, not precision. **For the reasoner (T1) this is the de-risking result of the phase**: a latent reasoner may be *sloppy in the continuous space* — its precision obligations live in the symbolic channels it manipulates by discrete ops (slot exchange, bit flips, symbolic replacement). Noise-tolerance of the thought-vector was R1's whole motivation; it now holds with ~4× margin over what v0 delivered. **Caveat**: the floor wasn't found — σ beyond 0.8 untested, and cycle-vs-clean-z partially reflects identity anchoring itself; a frame-only degradation metric (cycle with identities masked out of the recon before encoding) would isolate the gist's own signal if this ever needs sharpening. **Revisit**: when reasoner-predicted latents replace synthetic noise.

## 2026-07-25 — D23: Identity comparison channel — the codec-level `min` closes D20's caveat (`results/codec_compare_v0.json`, `codec/identity_channel.py`)
D3 assigns literal substitutions to the identity channel; D20 measured the cost of not having one (date_shift scored 0.656 through the structure channel and pinned the margin). Built: `identity_sim(x, y)` over two categories — numeric values (comma/zero-normalized digit groups, compared as multisets) and PROPN entities — and the codec-level comparison `min(struct_sim, identity_sim)`.

**The design problem D20 flagged — reformatting must not false-flag ("around 3" → "approximately 03:00") — has a clean resolution: substitution is a BIDIRECTIONAL mismatch.** Flag a category only when *both* sides hold values the other lacks (a date swap strands 22 on one side and 23 on the other; a reformat strands surplus fragments on one side only). One-sided gain/loss is elaboration/ellipsis — other channels' business.

Result: the three substitution types collapse (date_shift 0.656→**0.024**, location_swap 0.493→**0.018**, quantity_double 0.543→**0.000**) with **zero false flags** — all 8 preserving types sit at identity_sim = 1.000 exactly, including formality (the trap case), contraction, and paraphrase. Codec-level ordering: margin +0.011 → **+0.022** (doubled), pair-level AUC 0.942 → **0.963**. The bottleneck pair is now formality_shift (0.666) vs tense_shift (0.644) — both marked-feature cases where the role channel's quantized slot penalties (2/3 slots = 0.67) set the scale; widening further means finer-grained role scoring, deferred until something needs it. **Revisit**: if Phase-2 retrieval needs a graded (not min) combination.

## 2026-07-24 — D22: Slot-tagged identity prefixes — binding errors cut by a quarter; v2t ships (`results/decoder_v2t_eval.json`)
D21's residual (right values, wrong slots) attacked at encode time: each number-like sparse token is fused with its dependency head ("0.4" → "0.4 bar", `scripts/build_tagged_sparse.py`), so the value arrives pre-bound. Decoder architecture unchanged — slot *content* is the only variable. Measured with the new **binding metric** (`fidelity.binding_pairs/binding_rate`: a number is bound iff its parse-head word appears within ±3 tokens of it in the reconstruction):

| | binding | binding given-present | number EM | number EM @σ=0.5 | entity EM | cycle |
|---|---|---|---|---|---|---|
| v2 (bag slots) | 0.522 | 0.714 | 0.668 | 0.662 | 0.483 | 0.810 |
| **v2t (tagged)** | **0.617** | **0.795** | **0.720** | **0.725** | 0.462 | 0.809 |

Mis-attachment given presence: 28.6% → **20.5%** (−28% relative). Number EM +5 pts, and the gain survives gist noise fully (identity channel is where the tags live). Cost: entity EM −0.021 (borderline noise at n≈236) and exact-rate −0.004; cycle unchanged. Attribution stays clean: shuffled-sparse binding = 0.005 — binding rides entirely on the identity channel.

**Ceiling is coverage, not method**: only 47% of number tokens could be tagged — BGE-M3's lexical head splits comma-formatted numbers into fragments that don't match parse tokens ("4,200" → '4'+'200'). Perfect reconstructions now appear where tags exist; the surviving swaps cluster in untagged values. Next lever when this matters again: emit the identity channel from the validated labels directly (numbers + entities with heads, bypassing BGE-M3's lexical tokenization for the number slots) rather than smarter matching.

**Ship**: decoder_v2t is the shipping codec decoder. **Revisit**: identity-channel-from-labels if number fidelity plateaus below ~0.85.

## 2026-07-22 — D21: Codec v2 — the hybrid latent WORKS; identities ride the symbolic channel and fidelity doubles (`results/decoder_v2_eval.json`)
Decoder conditioned on the full D3 triple `[16 gist prefixes ; 24 sparse identity slots ; 2 s-vector prefixes]`, both D10 fixes applied (per-row max-normalized weights + learned fp32 gain, settled at 1.15; dense-drop p=0.25). 14,533 train / 12 epochs, final loss 0.0071 (v0: 0.0162 — identities make the task easier, as they should).

**Headline vs dense-only decoder_v0 at the same corpus:**

| | entity EM | number EM | exact recon | cycle cos |
|---|---|---|---|---|
| v0 (dense only) | 0.203 | 0.336 | 0.000 | 0.619 |
| **v2 (triple)** | **0.483** | **0.668** | **0.064** | **0.810** |

**Per-channel shuffled attribution** (the eval v1 failed; house rule): shuffling the sparse channel now collapses fidelity to ~zero (entity 0.483→0.000, number 0.668→0.029) — the identity channel is not just used, it is **the** identity carrier, and a *wrong* identity channel actively misleads (worse than v0 baseline, which is what trusting a channel looks like). Gist attribution: +0.08 entity / +0.036 exact. s attribution: +0.055 entity / +0.025 number, and **+0.033 role fidelity** (0.756 vs 0.723 with s shuffled) — first direct evidence the decoder reads binding structure from the s-vector.

**Robustness is transformed — the D3 design intent realized.** Noise hits only the gist; identities ride the symbolic channel unharmed: at σ=0.5 (latent cos ~0.89→0.45 territory) v2 holds entity 0.461 / number 0.662 where v0 fell to 0.125 / 0.317. The R1↔R3 tension (smooth-and-robust vs discrete-and-exact) is resolved **by construction**, which was the founding bet of the hybrid latent.

**Two readings that need care:**
- `zero_dense` (identities+s, null gist) nearly matches full on EM (0.492/0.654) — but EM measures token *presence*, not propositional correctness; exact-recon (0.044 vs 0.064) and the samples show the gist still supplies the frame. Do not read this as "gist unnecessary." Also `zero_dense` > `shuf_dense` on entity: a *wrong* gist drags content off-target where a *null* gist stays neutral — consistent with the null-gist embedding being a genuinely learned "no information" token.
- **The residual failure mode is binding, not presence**: samples show right values in wrong slots ("5 Tesla / 2.3 cm" → "2.3 Gauss / 5 cm"). Number EM counts presence, so 0.668 overstates end-to-end numeric *correctness*. The next fidelity lever is value-to-role binding at generation — richer structure conditioning (more s prefixes, slot-tagged identity prefixes pairing each value with its role) rather than more data.

**Engineering notes that cost a smoke-test cycle** (now standing rules): (1) never drop a channel by zeroing its *projected embeddings* — exact-zero vectors through RMSNorm yield non-finite LoRA grads in backward while the forward loss stays healthy; zero the channel *input* so dropped rows get `proj(0)`, a learned null embedding. (2) bf16 scalar parameters silently stop learning (updates round away below ~1e-3 resolution); keep learned scalars fp32, cast at use.

**Interpolation at v2 measured something better than it intended** (`results/interpolation_decoder_v2.json`): the probe slerps the gist while carrying endpoint A's side channels fixed — under triple conditioning that is a **channel-conflict experiment**, not a traversability one, and the verdict is total: output text stays anchored to A at every t (t=0.5 decodes A's proposition verbatim; roundtrip-vs-z_t decays 0.79 → 0.01 as the gist walks to B). **When gist and identity channel disagree, the identity channel wins outright** — consistent with the ablation, and decisive for Phase 2: *latent operations must update the triple coherently; moving the gist alone moves nothing.* The operator inventory already splits exactly this way (translations on gist; slot exchange / bit flips on the symbolic channels — D15/D18/D20), so the architecture and the algebra converge. The headline "midpoint drop −40%" in that JSON is arithmetic over a polluted endpoint mean — ignore it; the per-t curve is the data. A true v2 traversability probe needs side channels that follow the path (e.g., switch sp/s at t=0.5, or slot-level interpolation), which is Phase-2 territory.

**Follow-ups**: cycle under noise (EM stays flat by design — the gist's semantic frame degradation is what the sweep should measure next); slot-tagged identity prefixes for the binding residue; triple-coherent traversability probe.

## 2026-07-22 — D20: Structure channel v2 — full ordering achieved; the amp channel is a METRIC, not a representation (`results/structure_channel_v2.json`, `axis_amplify_v1.json`, `struct_pooler_v2.json`)
D18's residual defect (formality_shift inverted) is fixed, and the fix was not the one predicted. Three changes, measured under identical code (v1 config re-run for a fair baseline):

| config | corpus | worst-case type margin | pair-level AUC |
|---|---|---|---|
| v1 (pooler v1 + amp v0) | 10,479 | **−0.082** | 0.913 |
| v2 (pooler v2 + amp v1) | 10,479 | +0.014 | 0.945 |
| v2, replicated in a refit space | 16,079 | +0.022 | 0.948 |
| **v2 + role-bits punctuation fix — CANONICAL** | 16,079 | **+0.011** | **0.942** |

The last row is the shipping number. The punctuation fix is a *correctness* fix that cost 0.006 AUC by exposing parse noise the buggy gate had been masking; the reasoning is in "Cache and guardrail plumbing" below. Reproduce with `scripts/probe_role_bits.py` (defaults are the shipping config).

1. **Pooler v2** — trained on all five v1-era preserving types (D18's predicted fix). Necessary but *not sufficient*: it lifted formality's s_cos 0.697 → 0.847, leaving amp as the binding constraint. New honest holdout = three preserving types generated after v1 shipped (cleft, nominalization, contraction/expansion); the v2 pooler scores them **0.912 combined** (canonical), all three above the ordering threshold — transfer to never-trained preserving constructions holds.
2. **Role bits** — extended to re-root three constructions the parse-based extractor mishandled (cleft/pseudo-cleft, light-verb nominalization, raising verbs "X appears to V"), plus two genuine bugs: tense read the participle instead of the leftmost finite auxiliary, and a missing tense was treated as a claim of tenselessness rather than a parse failure. Effect: formality role_sim **0.660 → 0.931**, hedge 0.667 → 0.563 (correct direction — hedging is meaning-changing, now caught by an explicit epistemic bit), every other type unchanged or improved. Clause fingerprints also dropped the verb lemma, which was predicate identity this channel deliberately does not compare.
3. **Amp v1 — the conceptual correction.** v0 capped gain at 2.0 to satisfy a kNN retrieval guardrail. That guardrail was inherited from the adapter lineage (D11/D12), where the map *replaced* the representation. In the shipped channel the amplified vector is a comparison-time copy and the stored gist is never modified, so retrieval geometry cannot be damaged by it. The guardrail that actually binds on a metric is non-degeneracy: unrelated propositions must stay far below preserving pairs — measured at every gain (median 0.002, p95 0.262 at the selected config). Freed of the wrong constraint, selection chose k=8, **g=8.0**: formality amp_cos 0.641 → 0.701, ordering AUC 0.810 → **0.866**.

**Refuted along the way** (kept because it was the leading hypothesis): deflating the preserving-displacement subspace out of the invert bank as *the fix for formality* does not work — at the v0 gain (2.0), formality got slightly worse at every deflation depth (0.641 → 0.617 at k_def=64). Formality's displacement is not separable from the valence subspace by linear projection; the gain change is what moved formality. Precision note: a *weak* form survives — once gain is high, a small deflation is mildly beneficial and the 16k-space selection chose k_def=4 (the shipping `amp_subspace_v1.npz` therefore has 4 preserve directions deflated; the 10k fit had 0). Harmless either way — selection is on trained types only — but the two claims shouldn't be conflated.

**Honest caveat**: the type-level margin is thin (+0.011 canonical). The pair-level statistic is the one to trust: **AUC 0.942**, with 20% of preserving pairs still falling below the changing-pairs' 95th percentile. The blocking pair is formality_shift vs date_shift, and date_shift is an *identity substitution* — by D3 that belongs to the symbolic identity channel, not the structure channel. A codec-level `min(struct_sim, identity_sim)` would drop date/location/quantity substitutions to ~0 and widen this margin without further tuning of the structure channel. **Revisit**: when codec v2 wires the identity channel into comparison.

**Also standing**: the amp subspace is now persisted (`results/amp_subspace_v0.npz` = the D16/v0 config, `_v1.npz` = shipping), the assembly lives in `codec/structure_channel.py` behind one `pair_scores()` API, and `scripts/probe_role_bits.py` only evaluates.

**Replicated in an independently refit space (same day)**: after the corpus grew 10,479 → 16,079 propositions (36 → 56 domains) and the whitener, pair cache, amp subspace and pooler were all refit from scratch, the result held and slightly improved — margin +0.014 → **+0.022**, pair-level AUC 0.945 → **0.948**, transfer 0.910 → **0.915**. The amp subspace itself moved by at most 0.010 amp_cos across the space change, i.e. the valence directions are a property of the encoder, not of one whitener fit.

**Cache and guardrail plumbing fixed while replicating** (each of these would have silently corrupted a later result):
- `prop_relation_emb.npz` keyed only on pair *texts*, but stores *whitened* vectors. A corpus change refits the whitener while leaving every pair text identical — the cache would have served stale coordinates to every downstream probe forever. It now stores a **whitener fingerprint** and self-invalidates; probe outputs record it too, and `fit_amp_subspace.py`'s parity assertion is gated on it (a blind assertion fails spuriously after any refit).
- `codec/role_bits.py::_words` dropped every **sentence-final** token (`"Trenton."` fails `isalpha()`), so a slot filler's comparability depended on where punctuation happened to fall — and sentence-final patients/recipients are the common case. Fixed, at a **measured cost**: margin +0.022 → +0.011, AUC 0.948 → **0.942**. The buggy gate was accidentally *masking* parse disagreements on preserving pairs, so the drop is previously-hidden extractor noise becoming visible, not a real regression. Kept the fix: a channel whose behaviour hinges on punctuation position fails unpredictably on new data. **This localizes the next lever** — ~2 points of parse noise on preserving types (active_passive 0.988→0.969, paraphrase 0.777→0.727) is now the cheapest remaining win, via head normalization or a stronger parser.
- Recipients attached to the direct object rather than the verb ("audited 40 accounts **for** Trenton Bank") were never extracted; both hosts are now searched.
- `scripts/check_role_bits.py` — new unit-form positive control (D8): one proposition written 16 ways. It asserts the channel's *contract* (8 preserving constructions must produce identical bits; role-swap/tense/hedge must separate) and explicitly does **not** assert valence or added/dropped arguments, which are other channels' jobs or measured trade-offs. It found all three bugs above.

## 2026-07-22 — D19: Interpolation probe (eval #3) — the latent is traversable; the decoder projects off-manifold points instead of failing (`results/interpolation_decoder_v0.json`)
Slerp between held-out latent pairs, decode at t ∈ {0, .25, .5, .75, 1}, re-encode, measure round-trip cosine. Endpoints 0.577/0.585 (matches cycle-cos 0.579 — instrument consistent with eval #4); midpoint 0.304 — a **48% relative drop, but V-shaped and smooth, no cliff**. Critically, decoded text stays fluent and proposition-shaped at every t (mean length stable ~16 words; midpoint samples are coherent single-topic propositions blending endpoint content). **Reading**: decoder_v0 acts as a projector onto the proposition manifold — off-manifold inputs (exactly what a reasoner will emit) degrade gracefully in fidelity rather than catastrophically in form. This closes the original seven-probe eval suite.

**Second point (same day, 16k decoder — `results/interpolation_decoder_v0.json`; 10.5k record kept as `_10k.json`)**: the "drop should shrink as fidelity scales" prediction gets a sharper answer than yes/no. Absolute round-trip fidelity lifted across the whole curve (endpoints 0.581 → 0.622, midpoint 0.304 → 0.332), but the **relative** drop is invariant: 48% → 47%. The off-manifold penalty looks like a *constant fraction* — a structural property of the space/decoder pair — while fidelity gains distribute uniformly along the path. Best midpoint sample yet for the projector reading: slerp between a magnetic-field proposition and an Amsterdam-bridge proposition decodes to "The Electromagnetic Bridge crossed the Aardenland Strait in 1895, spanning 6.2 kilometers" — a fluent, single-topic blend. **Revised expectation**: corpus scaling lifts the curve but won't close the relative gap; if anything does, it will be architectural (codec v2 conditioning, or reasoner training through the decoder à la SONAR-LLM). **Revisit**: at codec v2, and if reasoner-predicted latents behave qualitatively worse than slerp points.

## 2026-07-22 — D18: Structure channel v1 SHIPPED — three mechanisms, one residual defect (`results/structure_channel_v1.json`)
Assembly: `struct_sim = min(amp_cos, s_cos, role_sim)` — valence subspace (D16, linear) + trained pooler (D17) + symbolic role bits with shared-vocabulary gating and a tense bit. Role-bits channel solved the binding residue exactly as designed: **argument_swap 0.977 → 0.595, causal_reverse 0.965 → 0.346** (parse-based, deterministic; converse-predicate paraphrases are the known, accepted limitation).

Full 20-type ordering, test pairs: every meaning-changing type ≤ 0.665; every meaning-preserving type ≥ 0.700 — **except formality_shift (0.426)**, the single remaining inversion (type-level ordering ≈ 67/75 pairs = 0.89). Fittingly, the one defect is exactly D13's pathological case (register shift was the most-displaced transformation in raw BGE-M3 space; the channel inherited it). **Known fix, next session**: the pooler held formality/paraphrase out purely to answer the transfer question (answered); the shipping config should *train* on all preserving types — s_cos 0.697 and role_sim 0.660 for formality are trainable artifacts, not information deficits.

Channel roles, final: gist (BGE-M3 dense, whitened) = topic/retrieval; identity (sparse lexical + validated labels) = exact values; **structure (amp ⊕ pooler ⊕ role bits) = what-relates-to-what**. Reasoner-facing operations confirmed so far: valence flips = translations/subspace scaling; role swap = symbolic slot exchange; tense = symbolic bit flip.

## 2026-07-22 — D17: Structural pooler v0/v1 — valence transfer works; role binding resists even token-level learning; residue is two types
(`results/struct_pooler_v0.json`, `_v1.json`) Attention pooler over BGE-M3 ColBERT token vectors, trained on 5 inverting + 3 preserving types, 12 types held out.

**Wins.** (1) **First generalizing learned component**: trained on only negation + comparative_flip from the valence family, separation *transferred* to six never-trained valence types (presence_absence 0.157, success_failure 0.331, superlative_flip 0.366, approval_rejection 0.428, increase_decrease 0.532; quantifier weaker at 0.891) — mean HELD-valence 0.46–0.50 vs HELD-preserve 0.83. The hinge objective generalizes fine *when the signal is in the representation.* (2) Substitution transfer partial: date_shift 0.689–0.717 (never trained; learned from location/quantity). (3) s-space is a genuine structure space, not a topic space (domain purity 0.36 vs 0.72+ in gist space) — channel separation working as designed.

**The residue, precisely.** argument_swap **failed on its own training data** in both runs (0.929 v0; **0.977 v1 — with 32-dim sinusoidal position features concatenated**), causal_reverse followed (0.96). The v0 set-function diagnosis was necessary but not sufficient: with positions available the task becomes "entity-at-position × voice/connective marking" — because active_passive and clause_reorder *also* move entities positionally but must stay together, raw position is USELESS without syntax; the optimizer correctly ignored it and kept the lexical solution. **Role binding needs syntax-bearing token representations, which BGE-M3's contrastively-trained last layer does not provide.**

**Completion options for the structure channel**:
- **(symbolic — recommended)** Role bits as a side-channel: dependency-parse subject/object/connective order for the two residual phenomena (SRL-lite). Mirrors D3 exactly — carry exact things exactly; the two residual types are *about* exactness of binding. Cheap, robust, philosophy-consistent.
- **(neural)** Extract mid-layer XLM-R hidden states (syntax lives mid-stack per BERTology) instead of ColBERT vectors and retrain the pooler — one surgery + one run; keeps the channel fully learned.
- Current shipped structure channel = valence subspace (D16, linear) + pooler v1 (marked/substitution) + whichever binding solution wins.

## 2026-07-22 — D16: The valence family is SOLVED by a 16-dim linear rebalance; the structural family is content-conditional (axis amplification, `results/axis_amplify_v0.json`)
Closed-form spectral map (no gradient descent anywhere): amplify the top-16 subspace of trained inverting-type displacements by 2×. Selection touched only trained types + geometry guardrail; held-out types scored once; random-subspace control run at the same (k, γ).

**What worked — the valence/antonymy family separates as a group:** negation −0.257, presence_absence −0.313, approval_rejection −0.338, success_failure −0.254, superlative_flip −0.232, quantifier_change −0.222, comparative_flip −0.198, increase_decrease −0.182 — while all three trained preserving types moved ≤0.004 and, for the first time, **geometry passed the guardrail: kNN@10 overlap 0.794, Spearman 0.915**. Ordering AUC **0.705 → 0.810 — above every encoder in the bake-off** (best was 0.772) using BGE-M3 plus a 16-dimensional linear tweak. Random-subspace control: no effect (trained 0.810 ≈ before). The polarity steering vector (D15) generalizes into a shared low-dimensional **valence subspace**.

**What didn't — and why, precisely:** held-out types 0.817 → 0.823 (no movement), and notably *argument_swap barely moved (−0.014) despite being in the training bank*. The linear probe already told us why: swap displacement is proportional to embed(A)−embed(B) — it depends on **which entities are involved**. The same holds for date/location/quantity substitution and causal reversal. These displacements live in *content-conditional* directions; no fixed linear subspace (and no fixed MLP — this retroactively explains D11/D12 fully) can amplify a direction that changes per example.

**Taxonomy established:** transformations split into two geometric families —
1. **Valence family** (lexically-marked polarity flips): shared low-dim subspace, linearly separable, operator = translation/subspace amplification. *Solved at v0 level.*
2. **Structural family** (role/value rebinding: swap, causal direction, substitutions): content-conditional displacement, invisible to any fixed map over the pooled vector. Requires binding-aware machinery — token-level pooling (D14 option b) or bilinear/conditional maps.

**Adopted**: the 16-dim valence rebalance ships as `amplify_v0` (config in the JSON); the structure channel build proceeds to option (b) for the structural family only.

## 2026-07-22 — D15: Polarity is a steering vector — first confirmed latent operation, and it is a TRANSLATION
The negation direction generalizes at 100% to held-out pairs and is a single consistent axis. Convergent with every operator probe (translation ≥ rotation everywhere, and translation's wins clustered on lexically-marked transformations): **the operator family for at least the marked transformations is additive/translation, not rotational**. The eventual reasoner algebra should be designed translation-first, with whatever the structure channel yields determining the operator for role-level transformations. This is the first entry in the "confirmed latent operations" inventory: `negate(z) ≈ z − α·μ_not`.

## 2026-07-22 — D12: Breadth does NOT fix it — a post-hoc adapter cannot learn general semantic separation. The fix is architectural.
**Experiment** (`results/adapter_broad.json`): repeat of D11 with **3× the transformation types** (9 inverting + 3 preserving trained, 915 pairs vs 346) and the *same* held-out inverting types, so the runs are directly comparable.

| | narrow (3 types) | broad (9 types) |
|---|---|---|
| trained-invert, after | 0.401 | **0.298** (separates even harder) |
| **held-out invert, after** | **0.901** (was 0.897) | **0.827** (was 0.817) |
| trained-preserve, after | 0.946 ✓ | 0.951 ✓ |
| kNN@10 overlap | 0.457 | 0.550 (still < 0.7) |

Held-out inverting types moved **+0.010 — the wrong direction**. Every one of the five: causal_reverse 0.938→0.931, date_shift 0.754→0.766, location_swap 0.638→0.658, quantity_double 0.858→0.887, tense_shift 0.895→0.892. Tripling breadth bought *nothing*.

**Conclusion**: the adapter learns per-transformation lexical detectors ("not", "approved/rejected", "all/some") and adding types just adds detectors. Recognizing that an *unseen* transformation inverted meaning requires parsing propositional structure — which argument changed, which magnitude — and a bag-of-topics embedding plus an MLP has no compositional representation to generalize over. **D11 option (a) is closed; the fix is architectural.**

**Ranked next steps**:
1. **Try a structure-sensitive base encoder first (cheapest, highest information).** BGE-M3 is retrieval-contrastive — trained to collapse paraphrases, which is exactly backwards here. An NLI/entailment-trained encoder is trained to distinguish P from not-P. One encode pass over the existing 20-type set answers whether the mis-ordering is a property of *this* encoder or of sentence embeddings generally.
2. **Encoder-level fine-tuning** with the separation objective (far more capacity than a post-hoc MLP).
3. **Explicit structural channel** — predicate/argument roles carried symbolically, mirroring how the sparse channel carries identities (D3).

## 2026-07-22 — D13: The latent's transformation ordering is *inverted* relative to semantics (20-type diagnostic)
Magnitudes over all 20 types (`results/prop_rotations_v0.json`) show the frozen latent tracks **surface form, not meaning**:

- Meaning-**preserving** `formality_shift` ("the pump quit working around 3 in the morning" → "the pump ceased operation at approximately 03:00 hours") moves the latent to **cos 0.608 — the largest displacement of all 20 transformations**, inverting and preserving alike.
- Meaning-**inverting** `argument_swap` (who paid whom) sits at **cos 0.975 — the smallest displacement of all 20**.

So rewording a sentence formally moves the representation *further than reversing who did what to whom*. Mean preserving 0.876 vs mean inverting 0.811 — the aggregate leans the right way, but the distributions overlap so heavily that the two most conceptually important cases are exactly inverted. Any reasoner over this latent would treat a paraphrase as a bigger change than a role reversal. This is the sharpest single statement of the D9 problem and the benchmark any replacement encoder must beat.

## 2026-07-22 — D11: A post-hoc adapter on a frozen topic-encoder does NOT learn general semantic separation (D9 attempt 1, negative)
**Experiment** (`results/adapter_v0.json`): residual MLP adapter, hinge losses (push meaning-inverting pairs below 0.5 cos, hold meaning-preserving above 0.9) + a geometry-preservation term on random corpus pairs. Trained on 3 inverting types (negation, argument_swap, comparative_flip) + 1 preserving type (active_passive); **4 transformation types held out entirely**.

| transformation | role | before → after |
|---|---|---|
| negation | train-invert | 0.734 → **0.249** |
| comparative_flip | train-invert | 0.854 → **0.339** |
| argument_swap | train-invert | 0.972 → **0.614** |
| active_passive | train-preserve | 0.946 → 0.946 ✓ |
| causal_reverse | **held out** | 0.937 → 0.941 (+0.004) |
| quantity_double | **held out** | 0.860 → 0.878 (+0.018) |
| tense_shift | **held out** | 0.892 → 0.885 |
| hedge | **held out** | 0.902 → 0.897 |

**Two independent failures.** (1) *No generalization*: trained types separate massively (mean 0.401), held-out inverting types do not move at all (mean 0.901, vs preserve 0.946). The adapter learned per-transformation lexical signatures ("not", "more/less", word order), not semantic difference. (2) *Geometry damaged*: kNN@10 overlap 0.457 and pairwise-cosine Spearman 0.496 — below the >0.7 guardrail, so retrieval structure (D2's reason for BGE-M3) took real damage even with the preservation term.

**Reading**: the capability isn't missing — the adapter separates when it has seen the signature — but a small residual MLP over a frozen *topic* encoder, trained on 346 pairs across 3 types, has no path to a general notion of propositional difference. Different transformations differ along different axes; a general separator would need actual propositional structure (predicate, roles, magnitude, polarity).

**Next tests, in order**: (a) **breadth** — does generalization emerge with many more transformation *types*? (directly testable; data generating now). If yes, this was a data-diversity problem. (b) If not, the fix is architectural, mirroring D3's logic: a **third, structural channel** (roles/polarity/magnitude carried explicitly, as identities are carried symbolically) or encoder-level fine-tuning rather than a post-hoc adapter. (c) Map the separation-vs-geometry Pareto frontier via `w_geom` only once generalization works — trading geometry for memorized separation is not worth tuning.

## 2026-07-22 — D9: The blocker is representational, not algebraic — the adapter must be *trained to separate*, not just whiten
**Finding** (`results/prop_rotations_v0.json`): in frozen BGE-M3 + whitening, semantically decisive propositional edits barely move the latent — argument swap cos 0.974, causal reversal 0.937, comparative flip 0.852, negation 0.734 (the largest mover). Meanwhile the decoder ignores perturbations down to ~0.89 cos by design. **Semantic distinctions the reasoner must make are smaller than the noise the codec is trained to discard**, and meaning-preserving active→passive (0.951) moves the latent *more* than meaning-inverting argument swap (0.974). No binding operator — rotation, translation, or otherwise — can recover a distinction the representation never encoded.

**Decision**: the adapter's job is upgraded from *isotropize* to *separate*. Train it with an explicit contrastive/structural objective on propositional transformation pairs (push negation, argument swap, comparative flip, quantity change apart; keep active↔passive together) before any further algebra work. This is now the Phase-1.5 critical path; the 1,200-pair dataset in `data/relations/prop_*.jsonl` is both the training signal and the eval.
**Success metric**: transformation magnitude drops well below the decoder's noise-tolerance floor (target: meaning-inverting edits at cos < 0.7 while active↔passive stays > 0.9 — i.e. correct *ordering* first, magnitude second).
**Risk**: separating too aggressively could break the retrieval geometry that motivated BGE-M3 (D2). Measure both.

## 2026-07-22 — D8: Every geometry probe ships with a positive control
A probe that cannot detect the effect it is testing for produces confident nonsense. Each fit-a-transform probe must report, alongside its real-data score, its recovery score on synthetic data where the transform is known to exist at the same (dimensionality, sample size). **Rationale**: D4's v0 result was a pure capacity artifact and would have falsely killed a live hypothesis. **Revisit**: never.

## 2026-07-22 — D5: Local-first training; Haiku *subagents* for data generation (revised same day)
**Rationale**: RX 9070 16GB handles BGE-M3 (568M) + ≤1B decoder w/ LoRA at proposition lengths — training stays local. Data generation uses **Haiku subagents spawned in the background from Claude Code sessions** — covered by the user's Anthropic subscription, no separate API billing. Each generation round = parallel subagents with distinct register briefs writing JSONL to `data/propositions/`. The Batch API path ($0.50/$2.50 per MTok) is the documented scale-up option if corpus needs outgrow subagent throughput. Bonsai-27B stays as the zero-cost offline fallback. **Revisit**: if corpus size targets exceed what session-based generation sustains.

## 2026-07-22 — D6: Anchor inventory — over-provision to 100k, minimize later
Start with data-derived k-means anchors, swept N ∈ {1k…100k}. The **100k ceiling** is deliberately generous — expressibility must not confound algebra validation — yet still small vs. LM embedding tables and cheap on our hardware (100k × 1024-d ≈ 400MB fp32). Reported intuitions and prior art (Longman Defining Vocabulary ~2k; dictionary grounding kernels; NSM primes ~65) suggest "low thousands" may ultimately suffice; **minimization is a deferred research axis**, its own workstream after T2 validates. **Rationale**: don't entangle two open questions (does the algebra work? × how small can the basis be?). **Revisit**: after T2 validation.

## 2026-07-22 — D7: Prove on modest hardware before cloud spend
All Phase 1–3 experiments run on the local RX 9070. Cloud scaling (larger decoders, bigger sweeps, longer training) is contingent on the codec + algebra probes showing promise locally. **Rationale**: cheap falsification first; the theses are designed to be testable at small scale. **Revisit**: at each phase gate.
