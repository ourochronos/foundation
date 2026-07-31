# Directions brief — a request for strategic disagreement

This is not a request for validation. A research program is being deliberately
reopened at the architecture level, and the author wants **divergent** views on
where to go. Agreement between reviewers is worth nothing here; a reviewer who
names something the others missed, or attacks a premise the author has stopped
questioning, is worth more than three who concur.

The work below is fully documented and version-controlled. **Nothing has to be
preserved.** Sunk cost is explicitly not a consideration. Say "abandon this" if
that is the honest answer.

---

## 1. The goal, stated by the author

> *"I'm interested in trying to build something useful that hasn't been built
> before... I'd really like to work out our layered approach and what we can
> derive completely or map into dependably. I would like to solve efficiently
> ingesting and organizing data and making it useful."*

Not chasing a publication. A paper is acceptable as a by-product, never as the
target.

## 2. The one hard constraint

> *"I'm fine with us reindexing as we build this, but I want the thing we make
> not to have to."*

Reindexing is permitted during development. **The shipped artifact must never
require a global rebuild** — not when new data arrives, not when a new relation
type appears, not when the encoder is swapped. This has been the binding
constraint on every design decision and it should stay binding unless a
reviewer can argue it is the wrong constraint.

## 3. Environment (all local, no cloud)

- Single consumer GPU: **AMD RX 9070, ROCm on WSL2**. 27B-class inference runs
  locally at ~56 tok/s (a llama.cpp HIP fork). No cluster, no large-scale
  pretraining.
- **PostgreSQL + pgvector** as the store.
- **BGE-M3** (1024-d, whitened) is the encoder in use. EmbeddingGemma-300m was
  evaluated head-to-head and rejected (see §5).
- Store currently holds **19,996 claims**: 12,942 Wikipedia/Wikidata, 6,451
  arXiv, 602 HuggingFace model cards.

## 4. What was built

A knowledge substrate plus a reasoner, deliberately separated:

- **Claims store.** Subject–relation–object triples with page provenance,
  append-only, invalidate-never-delete. Identity keyed on entity **title**, not
  on an opaque identifier.
- **An anchor basis.** Relation *labels* are projected into a frozen basis of K
  anchor directions, so a relation the system has never been trained on still
  has coordinates the moment its label is embedded. This is the mechanism that
  was supposed to make the system reindex-free.
- **A per-step residual walker.** Given a question, a learned head predicts the
  order-free **sum** of the relation coordinates needed to answer it. The walker
  then takes the best *available* relation at the current frontier, subtracts
  its coordinate from the target, and repeats. Order and depth therefore come
  from the store's actual edges, not from a plan.
- **An answer-type gate.** `r_asked = argmax_r((target − coordinates already
  walked) · C[r])`; returned objects are compared to that relation's centroid,
  and mismatches are refused.
- **An audit apparatus.** Ten "audit laws" derived from wrong verdicts, a
  claims table where every number must be derivable from cited evidence, and
  blind multi-model adjudication of the project's own claims.

## 5. What survived testing

| finding | number |
|---|---|
| Walker beats a path planner; store supplies order and depth | **0.912** vs 0.534, and stronger planners were built and still lost |
| **1-NN retrieval on relation labels** | **0.975** from two aliases onward |
| The **learned head** doing the same identification | tops out at **0.892**, and the ~0.09 gap **does not close with more data** |
| Naming entities at the *source* during extraction | subjects/claim 0.912 → **0.373** (a free win, shipped) |
| Best novel-relation transfer ever achieved (56 relations, chance 0.018) | **0.453** |
| Answer-type gate on not-applicable questions | **+0.32 / +0.41** refusal, at −0.083 depth-2 correctness |
| Identity is present in the latent | but **absent from the gist** — a compressed summary loses identity specifically |
| Task-partition alignment | the **only** surviving account of why one basis beats another |
| Novel relations are **not** geometrically special | held-out relation coordinates are only **+0.03** harder to reconstruct from trained ones than trained ones are from each other |
| Generalisation and memorisation are **separable channels** | two unrelated manipulations each drove novel transfer to 0.000 while trained accuracy sat unmoved at 0.71–0.73 |

## 6. What was REFUTED — the longer and more informative list

Read this section as the real state of knowledge.

1. **Rotational alignment** between representation spaces — rejected; translation-first replaced it.
2. **Over-provisioning the basis** — refuted twice. A sparse overcomplete dictionary (the instrument superposition theory actually calls for) *loses by −0.270*, with two regimes and nothing between them: a near-lossless code scores exactly what raw label space scores, a genuinely sparse one scores 0.000. A dense overcomplete projection collapses back to raw.
3. **Swapping to a stronger encoder** — declined. EmbeddingGemma-300m had a **53×** advantage on isolated identification and still lost on the store, on the refusal frontier, and on the answer-type gate.
4. **The layer stack as a derivation order** (entities → relations → categories → worldviews → axioms) — refuted. The stack is real as an *ontology*; it is not a recipe for deriving representations, and adjacent-layer derivation failed.
5. **Orthogonality** of relation anchors as a design target — refuted.
6. **Redundancy** as the account of basis quality — refuted.
7. **Anchor coherence** as the account — refuted.
8. **Interpolability** as the account of novel transfer — refuted; it correlates *negatively* with transfer inside 11 of 14 strategy families.
9. **"Compression destroys information permanently"** — withdrawn; the gap plateaus rather than growing.

**Post-hoc explanations in this program have gone 0-for-3 once tested.** Fit to
existing numbers has carried no evidential weight whatsoever.

## 7. The author's live architectural question

The intuition being chased is a **layered** system: entities → relations →
relation categories (structural / causal / temporal / functional / social) →
worldviews or lenses → a meta layer over lenses → axioms. Experiment says this
is a valid *ontology* but not a derivation order.

The author's framing of what matters:

> *"what we can derive completely or map into dependably"*

— i.e. which layers are **finite, closed and enumerable once** (derive
completely, never refit) versus which are **open and unbounded** (must be
mapped into by an encoder, and must therefore be append-only).

## 8. What is being asked

Answer these five. Be concrete, be willing to be wrong, and **do not hedge
toward the middle**. Where you disagree with the author's framing, say so
directly — that is the most valuable thing you can produce here.

1. **Kill list.** What in §4–§5 should be abandoned outright rather than
   improved? Be specific and give the reason. If the learned head should go,
   say so. If the anchor basis should go, say so. If the whole
   coordinate-composition program is a dead end given §6, say that.

2. **The one thing to build.** Name a single concrete system worth building
   next, and — critically — **the first experiment that could kill it**. Prefer
   something buildable by one person on one consumer GPU in weeks.

3. **Prior art, honestly.** What already exists that this would be reinventing?
   Name real systems, papers, or products. Then say where the genuine **white
   space** is, if any. If the honest answer is "this space is crowded and the
   novel part is X only", say that.

4. **Concrete substrate choices.** Datasets worth ingesting (and why *those*);
   a KB schema sketch that satisfies the never-reindex constraint; which models
   to build on versus train versus avoid. Include what a **type system** should
   look like if one is warranted, and whether the closed/open layer split in §7
   is the right cut.

5. **The premise you would attack.** Name the assumption the author has stopped
   questioning. Candidates worth considering, non-exhaustively: that the shipped
   artifact must never reindex; that a knowledge store and a reasoner should be
   separable; that relation labels should be embedded at all; that composition
   should happen in a coordinate space rather than in the store's type graph;
   that retrieval at 0.975 beating a learned head at 0.892 means the learned
   component should not exist.

Return your answer as prose under five headings matching the five questions.
Then finish with a single line:

`TOP-PICK: <one sentence naming the single highest-value next move>`
