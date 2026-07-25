# Decision log

Format: date · decision · rationale · revisit-when.

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
