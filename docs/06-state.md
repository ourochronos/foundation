# Current state — 2026-07-30 (encoder arc CLOSED, swap declined; through D173)

**Fastest orientation**: [decisions.md](decisions.md) D173 → D172 → D158, then
"where a pivot lands" at the bottom. **Nothing is running.** Working tree clean
apart from three soak-log files that rewrite themselves.

This document separates **findings** from **plans** deliberately. A change of
direction discards plans; the findings below were paid for and stay true
whatever gets built next.

---

## Resume points

| what | where |
|---|---|
| repo — M3 stack as measured, before any Gemma work | git tag `m3-baseline-20260730` |
| repo — encoder + anchor probes complete (this state) | git tag `probes-20260730` |
| store dump, restore-**verified** | `~/backups/foundation-20260730/` + its `RESTORE.md` |
| live store | pg `poc` (19,996) + `poc_claims` (19,996) |
| rebuild from scratch | `scripts/rebuild_poc.sh` then `python -m foundation replay-edits` |

**Restoring the store needs `CREATE EXTENSION vector` first.** `pg_dump -t`
does not carry extensions, and without it the restore silently yields
`poc_claims` present and `poc` **missing** — with perfectly healthy row counts
on the table that did restore. Found by test-restoring rather than by reading
the dump. Checksums to verify against are in `RESTORE.md`.

**Caches**: 2.2 GB of `results/*_emb.npz`, gitignored and rebuildable; 381 MB
of that is the exp55/exp56 encoder work. Each carries a content assert and
refuses to load against a changed text list rather than misaligning (D120).
Deleting them costs minutes, not correctness.

---

## Findings that survive a pivot

**Mechanically reindex-free, now measured where the claim is made.** Basis,
coordinates and head hash byte-identical across an append (D131) *and* across
an update (D157) — the latter added because a rater noted the fingerprint
evidence lived in a different experiment. The guard was then tested by making
it fire: a 1e-6 perturbation flips the hash, the run aborts, nothing written.

**The store does the reasoning work; the walk does not** (D158). An exhaustive
planner allowed to consult the store for walkability matches the walker
(0.9032 vs 0.9123, inside CI); denied the store it collapses to 0.3883.
Availability filtering **+0.515**, greedy walking **+0.009**. The walker's
remaining justification is cost, not accuracy — untested where enumeration is
expensive. The 0.534 baseline this claim rested on was a literal pasted from
another script; recomputed in-run it is 0.8138.

**BGE-M3 was the bottleneck for IDENTIFICATION** (D164). Novel-relation
transfer in raw label space: M3 **0.0032** (below chance), EmbeddingGemma
**0.1709** — 53×, identical task and head. So D125's basis rescue
(0.293 → 0.742) is substantially evidence that *M3 needed rescuing*.
**⚠ Does not carry end-to-end, and the swap was DECLINED (D172).** With the
store participating the encoders cross on the refusal frontier (D170), and
with the answer-type gate active on both arms M3 wins every axis — including
depth-2 answering by 0.112. Three gates, three failures to carry.

**Anchors should SEPARATE relations, not cover them — AT IDENTIFICATION LEVEL
ONLY** (D165). Top-K eigenvectors of the between-relation scatter
(`lda_between` K=32) beat k-means on labels on both axes, 0.7146 trained /
0.4530 novel. **⚠ REFUTED end-to-end at D169** — it loses at every threshold
and at matched coverage, on both encoders, once the store participates. Kept
here because the *identification* result is real and the mechanism (D168) is
what explains the whole arc; it is not a pipeline recommendation.

**Orthogonality is not the dial.** Coherence-vs-transfer correlation
−0.002 / +0.051 / +0.170. A perfectly orthogonal random basis caps at 0.287;
a high-coherence content-bearing one reaches 0.425. Content dominates.

**A basis works in proportion to how well its PARTITION matches the task, and
that buys generalisation only** (D168). Corrupting the class assignment while
holding method, K, head and targets fixed gives r = **−0.91 / −0.89**, mean
drop 0.150 — while **trained accuracy does not move at all** (Gemma 0.7146 →
0.7279 across the full corruption range). A trained relation does not care
which directions the basis spans; an unseen one needs the basis to point where
its label will land.

Four accounts of *why* a basis works were tested and only that one survives:
derive-from-the-adjacent-layer is **refuted** (D166 — all four profile
strategies lose at every K, −0.117 on Gemma); orthogonality r≈0 (D165);
non-redundancy with the encoder r≈0 (D167, whose highest-capture basis is near
the bottom). The ordering questions > labels > entity profiles is alignment,
not abstraction level.

**So the layer stack is real as an ONTOLOGY and not a derivation order for
representations.** The type/context distinction and the relation categories
stand; what they are not is a recipe for choosing basis directions. And
over-provisioning is relocated rather than killed — superposed categories want
a **sparse overcomplete dictionary**, which the K sweeps never tested (always
undercomplete; a dense K ≥ d collapses toward raw label space at 0.171 against
the K=32 basis at 0.453).

**Relation-as-offset fails** — anchors from `emb(obj) − emb(subj)` are worst or
near-worst on both encoders. With D4 (rotations unsupported) and D26 (constant
translation 0.060), "relations are geometric operators in this space" is now
three independent negatives.

**Better encoder ⇒ anchor strategy matters less.** Random-to-best spread: ~31×
on M3, ~1.6× on Gemma. The basis was doing repair work.

**Adjudication as a method** (D144 → D163):
- Claims that never faced a prompt fail when they finally do — **5 of 5**,
  against 2 of 10 for claims that had.
- Verification and attack find largely different things; neither subsumes the
  other, and a verification pass returning zero may be measuring hedging.
- `selfcheck` (claim sentence vs its **own** scope, no evidence shown) catches
  a class the other two miss — 4 flagged in a block that had just passed both,
  disjoint from attack's 3. Validated on matched pairs: 4/4 known-bad, 0/4
  repaired.
- Keep the panel **odd**: a fourth rater moved 1 verdict of 14, and only by
  turning a majority into a tie.

**Audit law #10**, earned here and tested as a prediction: *a claim must carry
the condition its number was measured under, in the claim sentence itself; a
scope condition qualifies a claim, it does not retract one.* The flag rate
halved (6/14 → 3/14) and rater instability fell with it.

**The recurring defect is the summarising sentence, not the number.** Numbers
are checked by tests, by `claim_numbers.py`, by four families of raters. The
sentence summarising them is checked by nothing, and it is where D160, D161,
D162, D164 and D165 each found their error.

**An identification-level result is not a pipeline result, and D169 is the
proof.** `lda_between` won by a wide margin in isolation and inverted once the
store participated — because D158 already measured the store as supplying
+0.515 against the walk's +0.009, so a basis optimised to separate relations
in the abstract is solving a problem the store solves better. **Anything
measured without the store carries a "not a recommendation" marker until
gated.** Three entries were written before that gate ran.

**Verify a number you are about to build on as hard as an adjudicator's
flag.** D172 reported the gate costing −0.243 on depth-2 answering, called it a
live defect, and a follow-up experiment was agreed. Re-reading D134 to
understand *why* found that I had computed `r_asked` from the raw target rather
than `target − coordinates already walked`; two-thirds of the "defect" was
mine (D173). No test catches this — both forms yield plausible numbers. What
caught it was pausing to understand the mechanism before optimising it, and
**reimplementing from a description rather than from the reference code** is
the specific way it went wrong.

**A threshold rule must not put refusal inside a minimum it maximises.** D169's
first pass used "maximise the worst trained population" with unanswerable
*refusal* in the min — which makes abstaining a way to win, and pushed one arm
to a point where it answered 31% of novel questions at 98% precision while the
other answered 79% at 95%. Reported as a −0.44 loss; actually two points on a
frontier. The tell was the abstain column, not the verdict.

**Check the intervention against its OWN control before any cross-arm claim.**
Three scripts in a row printed a confident verdict comparing the wrong pair:
exp52 tested the best planner first, so a *store-filtered* planner matching the
walker printed "the model can plan without the store"; exp53 called a
trade-off "as stated" on a wrongness cost that was 9.8% of the gain; exp62
announced "GATE RECOVERS IT" having never checked gate-ON against gate-OFF —
the gate had made both encoders worse and merely damaged one less. D172's
two-step structure (control first, cross-arm only if the control passes) is the
fix, and it converted what would have been a lucky right answer into an
argued one. **Treat the verdict string as the least trustworthy line in any of
these scripts.**

---

## Standing facts from earlier phases

**Identity — three declarations**, because no single default fits every source
(D92/D101):

| what makes two mentions the same thing | field | source type |
|---|---|---|
| a page's canonical form is its TITLE | `page_title` | arXiv (page is an ID) |
| a link target is canonical for the page it names | `object_page` | citations |
| community vocabulary is one entity by name | `object_global` | shared resources |

**Resource axis: ACCEPTED (D106)** — frozen 50-audit, both raters 0.82
[0.69–0.90], κ 0.806, against a *stated standard* (family-level resource names ·
`P_EVALUATES_ON` covers training corpora · a benchmark types the models it
scores as `P_COMPARES_TO` · descriptive subjects permitted where no method is
named). A number without its standard is what made two careful raters differ
by 22 points.

**Audit laws #1–#5** come from the extraction arc (D93–D106); #6–#9 from the
reasoner arc; #10 above. All ten are listed in `docs/19-writeup-draft.md` §8.

---

## Plans — direction-contingent, discard freely

**Nothing has been adopted, and the gate has now run — it refuted half of what
was recommended.** The pipeline still runs BGE-M3 + `whiten_v0` at 1024-d with
`K_BASIS=48` k-means-on-labels, and on current evidence it should stay there.

**`lda_between` K=32 is refuted end-to-end (D169)** — it loses at every
threshold and at matched coverage, on both encoders. D165's finding is a
statement about *identification*, not a pipeline recommendation.

**The encoder swap is a TRADE, not an upgrade (D170).** The two curves cross at
≈0.52 novel-unanswerable refusal: Gemma answers more below it, M3 refuses
better above it. Saturated, M3 reaches 0.785 correct / 0.205 wrong and Gemma
0.866 / 0.094 — higher ceiling at half the error rate, but refusal collapses
faster. **Gemma is better at answering and worse at knowing when not to**, and
this system is built around refusing rather than guessing.

**The arc is CLOSED and the swap is DECLINED (D172).** The answer-type gate
was the deciding experiment and it has run. On D134's own mixed benchmark the
gate reproduces for both encoders (not-applicable refusal +0.322 M3, +0.405
Gemma) — and with it enabled on both, **M3 wins every axis**: not_applicable
−0.013, chain_break −0.065, depth-1 answering −0.053, depth-2 answering −0.173.
Dominance, not a trade.

So Gemma's 53× identification advantage did not survive the store (D169), the
refusal frontier (D170), or the gate (D172). **Three gates, three failures to
carry.** The pipeline stays on BGE-M3 + `whiten_v0` at 1024-d with
`K_BASIS=48` k-means-on-labels — now a *confirmed* configuration rather than a
default nobody had challenged.

**The depth-2 gate cost was mostly my bug (D173).** D172 reported the gate
costing −0.243 on M3's depth-2 answering and called it a live defect; before
building the follow-up I re-read D134 and found I had computed `r_asked` from
the raw target instead of `target − coordinates already walked`. At depth 2
that is argmax over `C[r1]+C[r2]`, recovering neither hop. Corrected, the cost
is **−0.083** (M3) and −0.078 (Gemma) — real but modest, bought for +0.322 of
not-applicable refusal. The depth-aware-gate proposal is **withdrawn**.
D172's swap-declined conclusion and D171's chain-break null both survive the
fix unchanged, and every depth-1 and refusal number is bit-identical before and
after, which is the check that the fix was surgical.

If the swap ever proceeds, in order:

1. ~~the answer-type gate under Gemma~~ **done at D172 — swap declined**;
2. ~~`K_BASIS=48` → `lda_between` K=32~~ **withdrawn at D169**;
3. the codec identity producer. EmbeddingGemma is dense-only, so M3's sparse
   lexical channel has no successor. `codec/decoder.py` already consumes
   `{tokens, weights}` from a **separate** producer, so this is one script
   rather than a redesign — and a Gemma-vocabulary producer removes the
   current cross-tokenizer bridge (M3/XLM-R re-tokenised into Qwen3 at
   `max_sub=4`);
4. store `vector(1024)` → parallel `vector(768)` table — needed **only** for
   the store's own retrieval path, not for reasoning.

**Owed regardless of direction**: a re-adjudication of the current 14 claims
(four changed after the last round, so D161's counts do not describe the
current text), and a decision on folding `selfcheck` into the standard round —
three prompts × three raters × repetitions is a real cost increase and should
be chosen rather than drifted into.

**Open from earlier threads**: the walker's cost-vs-accuracy case at R=61
(D158); the phrasing leg of the compression claim (D159); max-cosine as a
per-question refusal predictor rather than a population correlation (D160);
regularised LDA and a swept entity-subspace size (D165).

---

## Where a pivot lands

Most of the above is **encoder- and basis-level**, so any direction that keeps
the store and the walker keeps all of it. What is genuinely contingent:

- **If the reasoner design changes**, D158 is load-bearing: the store supplies
  +0.515 and the walk +0.009, so anything replacing the *walk* has a low bar
  and anything replacing the *store's role* has a very high one.
- **If the codec leg is dropped**, the swap simplifies — dense-only stops
  mattering and step 3 disappears.
- **If the corpus changes**, every number in D164/D165 is one seed, one random
  draw of 12 held-out relations, one corpus. The orderings are large enough to
  survive noise; the magnitudes are not portable.
- **The paper** (`docs/18`, `docs/19`) is current through D163 and describes
  the **M3** stack. It does not mention the encoder work at all — deliberately,
  since nothing has been adopted. If we pivot, the paper needs no retraction;
  if we adopt Gemma, §1, §5b and §8 all move.
