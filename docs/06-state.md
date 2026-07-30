# Current state — 2026-07-30 (encoder/anchor probes complete; through D165)

**Fastest orientation**: [decisions.md](decisions.md) D165 → D164 → D158, then
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

**BGE-M3 was the bottleneck, not the method** (D164). Novel-relation transfer
in raw label space: M3 **0.0032** (below chance), EmbeddingGemma **0.1709** —
53×, identical task and head. So D125's basis rescue (0.293 → 0.742) is
substantially evidence that *M3 needed rescuing*, and the basis's measured
value should be expected to shrink under a better encoder.

**Anchors should SEPARATE relations, not cover them** (D165). Top-K
eigenvectors of the between-relation scatter (`lda_between`) beat k-means on
labels on *both* axes. Best cell: EmbeddingGemma, symmetric prefixes,
`lda_between` K=32 — 0.7146 trained / 0.4530 novel. No M3 cell survives on the
global Pareto frontier.

**Orthogonality is not the dial.** Coherence-vs-transfer correlation
−0.002 / +0.051 / +0.170. A perfectly orthogonal random basis caps at 0.287;
a high-coherence content-bearing one reaches 0.425. Content dominates.

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

**Nothing has been adopted.** The encoder swap is *recommended on evidence* and
has not been made. The pipeline still runs BGE-M3 + `whiten_v0` at 1024-d with
`K_BASIS=48` k-means-on-labels.

The gate before changing anything: **confirm D165's ordering end-to-end with
the walker.** All of D164/D165 is identification-level — no store walk, no
thresholds — and D158 measured store filtering at +0.515, so the ordering must
be reconfirmed where the store participates. **Cost ≈ 45 seconds of question
embedding**: the walker path reads only `poc_claims` (encoder-independent) and
embeds questions fresh; it never touches `poc.z`.

If the swap proceeds, in order:

1. the end-to-end walker gate above;
2. `K_BASIS=48` k-means → `lda_between` K=32 — likely wrong on either encoder,
   so worth doing independent of the swap;
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
