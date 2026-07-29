# What survives contact with a real corpus

*Reindex-free knowledge, honest refusal, and the conditions under which each holds.*

Draft — 2026-07-29. Every figure traces to a `run_manifest` in `results/`;
the decision entries behind each are cited as D-numbers in `docs/decisions.md`.

---

## Abstract

We built a knowledge store that can be appended to without recomputing
anything, and a reasoner that answers multi-hop questions over it by walking
the store rather than by predicting an answer. We then spent most of our
effort trying to break both, and report what survived.

The mechanical claim holds outright: appending new relations and entities
leaves every fitted artifact byte-identical, verified by fingerprint. The
behavioural claims hold **under conditions we had to discover by
measurement**, and several of our own earlier conclusions were overturned by
our own later experiments. On human-written multi-hop questions the system
answers **0.450** of depth-2 questions correctly under held-out phrasing.
Given a knowledge update it absorbs additions near-perfectly (**432/432**
conditional on having honestly refused beforehand) and revisions at
**0.459**, where the safety-critical figure is that it goes stale on only
**0.002**. Its refusal behaviour, which is the property the design exists to
provide, turns out to be bounded by store density and required a component
we had removed.

We think the negative results and the corrections are the most useful part,
and the eight audit laws that produced them the most reusable.

---

## 1. What this is

The system has three pieces:

- **A store** of claims, append-only, where invalidation shadows rather than
  deletes. Entities are individuated by a closed-form resolver; a claim's
  relation is a Wikidata-style property with a text **label**.
- **A walker** that answers a question by traversing the store. It predicts
  one order-free *sum of relation coordinates*, then repeatedly takes the
  best-matching relation **among those actually available at the current
  frontier**, subtracts it, and continues until the residual is spent.
- **A refusal rule**: the walk declines when the residual cannot be spent, or
  when the returned objects do not match the type the asked relation expects.

The design commitment that shapes everything else is that **order and depth
come from the store, not from the model**. The walker never learns "this
question is two hops"; it walks until there is nothing left to explain. That
is what makes depth unbounded in principle and what makes the reasoner's
behaviour a function of the store's contents (D117).

Relation coordinates come from a relation's **label**, projected into a frozen
basis. This is why a relation that has never been trained on still has
coordinates the moment it arrives — the property the reindex-free claim rests
on (D113, D116, D125).

## 2. The reindex-free claim, split in two

**Mechanically it holds.** We froze the basis, the relation coordinates and
the head, fingerprinted all three, appended 15 new relations and 652 new
subjects, and re-hashed. **Byte-identical.** Nothing is re-projected,
refitted or retrained when new content arrives (D131,
`results/exp36_append.json`).

**Behaviourally it costs accuracy, and the cost is asymmetric.** Measured
against a full rebuild — which is what reindexing would buy:

| | parametric head | 1-NN retrieval |
|---|---|---|
| new **entity**, known relation | +0.058 | +0.247 |
| new **relation** | **+0.191** | **+0.771** |
| depth-2 over appended content | +0.249 | +0.666 |

A new entity is nearly free; a new relation is not. An entity is a new node
the walk can reach, whereas a relation is a new *direction* the head was never
trained to emit.

## 3. Can it learn?

Two different operations, two different answers.

**Addition.** Withhold 30% of subject-relation pairs, append them with
artifacts frozen, ask the same questions before and after. Of the questions
the store **properly refused** beforehand, **432 of 432 (1.000)** are correct
afterwards, with regression on previously-correct questions at 0.003 (D133,
`results/exp38_update.json`).

That number is conditional on honesty, and the store was not often honest: of
the 1,179 questions it could not answer, it properly refused only **0.366**
and confabulated the rest. Section 5 is about fixing that.

**Revision.** Using MQuAKE-CF-3k's counterfactual rewrites applied through the
store's real supersession path, on the benchmark's human-written questions
(D141, `results/exp44_supersession.json`):

| | revision | **stale** | broke (→refuse) | wrong |
|---|---|---|---|---|
| all cases | 0.459 | **0.002** | 0.348 | 0.190 |
| single-rewrite | 0.235 | 0.000 | 0.497 | 0.268 |
| multi-rewrite | 0.578 | 0.004 | 0.270 | 0.149 |

**Staleness is essentially zero** — the store does not keep asserting a
superseded fact, which is the number that had to come out near zero given
invalidate-never-delete is a founding commitment. Revision is much harder than
addition, but it fails by *refusing*, not by clinging.

Single edits are worse than multiple, which inverts expectation and is
structural: editing one link mid-chain leaves the rest of the chain expecting
the old target's outgoing edges. Change a person's citizenship and the chain
still needs the *new* country's head of state; if that edge is absent the walk
breaks. This is a property of editing graph-structured knowledge, not of our
walker.

## 4. Composition and depth

**Composition generalises**, measured with a **pair-clean** holdout — training
excludes every chain containing a held-out relation pair, at every depth. On
61 relations, held-out pairs score **0.925** against trained pairs' 0.913 at
depth 2 (D123). Controls confirm the walk is not forced: branching is 6.4
relations per step, shuffling relation coordinates collapses accuracy to
0.001, and a random target of the same magnitude gives 0.000.

Parity holds **at depth 2 only**; at depth 3 it is 0.626 against 0.683.

**On human-written questions**, using MQuAKE's own chain lengths and its three
phrasings per case (D138, `results/exp42_natural.json`):

| depth | trained phrasing | **held-out human phrasing** |
|---|---|---|
| 2 | 0.586 | **0.450** |
| 3 | 0.686 | 0.632 |
| 4 | 0.761 | 0.703 |

**0.450 at depth 2 under held-out human phrasing is the honest headline of
this work.** It is the first measurement against language nobody on the
project wrote, and it is materially below every templated number we had
previously reported.

## 5. Refusal, which is the point

The design exists to refuse rather than guess. Getting that right took four
attempts and exposed a methodological failure that invalidated most of our
earlier refusal numbers.

**The benchmark was wrong.** Every unanswerable population we built until late
in the project was a **chain-break** — a multi-hop walk dying partway. Those
are easy to enumerate from the store and they flatter the system, because a
dead chain leaves an obviously unspent residual. The commonest real
unanswerable question — *this relation does not apply to this entity* — was
never tested. On it, refusal was **0.050** (D133).

**The fix was a component we had removed.** An answer-type gate compares the
returned objects against the range of the relation the *question* asked for,
read off the target rather than the walked path. Re-adopting it (D134,
`results/exp39_typegate.json`):

| | gate off | gate on |
|---|---|---|
| not-applicable refusal | 0.050 | **0.693** |
| chain-break refusal | 0.337 | 0.650 |
| answerable wrongness | 0.118 | **0.045** |
| answerable correct | 0.875 | 0.765 |

**The correction that matters most for anyone citing our earlier numbers**: on
the mixed benchmark our selective-prediction figure is **AURC 0.4734**, where
the chain-break-only benchmark gave 0.1322. **We had overstated it ~3.6×.**

**Refusal is bounded by store density.** Refusal falls monotonically with the
number of relations available at the break step (correlation −0.79 to −0.91),
and the mechanism is *ambiguity, not noise*: on wrongly-answered questions the
chosen relation's gain is genuinely high (median 1.198 against 1.390 for
correct ones). Two principled fixes — a multiple-comparisons correction and an
ambiguity margin — both moved along the precision/coverage frontier without
shifting it (D124).

**Thresholds are per-store.** The type gate's threshold can be computed from
store statistics alone (the p25 of within-relation type fit, needing no
labelled data), and it tracks the right property: MQuAKE's tighter ranges give
0.672 against wiki's 0.453. But it does **not** transfer — wiki evaluated at
MQuAKE's value drops coverage from 0.751 to 0.142 (D142). Thresholds are a
function of the store, and the store is available.

## 6. What we cannot claim

- **Not free-form language.** Questions are templated or benchmark-supplied.
- **Not entity generalisation.** We hold out relations, pairs, phrasings and
  instances — never entities.
- **Not depth-unbounded in practice.** Depth behaviour is corpus-dependent: it
  decayed on one corpus and *improved* on another.
- **Not honest by default.** Without the answer-type gate the walker
  confabulates on the majority of what it cannot answer. Honesty is a
  component we added, not a property the design provided.
- **Not a free lunch on refusal.** Every refusal gain we found cost coverage.

## 7. Negative results and corrections

We report these prominently because they are the evidence that the scope
conditions above are real rather than decorative.

**Overturned by our own later work:**
- *"Composition is memorised, not composed"* — an artifact of a 5-relation
  vocabulary. At 61 relations it composes (D112 → D123). We now treat a
  negative result measured on a small relation vocabulary as unreliable by
  default.
- *"No threshold separates, so the fix is architectural"* — an artifact of a
  hash-order bug that silently misaligned cached embeddings (D119 → D120).
- *"Phrasing is the dominant failure, −0.719"* — specific to alias
  substitution; on human paraphrases the cost is −0.054 to −0.135 (D127 →
  D138).
- *"Coverage decays with depth"* — corpus-specific; reversed on MQuAKE
  (D121/D126 → D138).
- *"Make the anchor basis the default"* — better for novel relations, worse at
  depth; the choice is task-dependent (D125 → D126).

**Things that did not work:**
- **Combining signals never beat the better component**, three times: two
  refusal fixes (D124), a six-signal confidence score that ranked worse than
  the residual alone (D132), and a retrieval/fallback hybrid whose two routers
  both lagged the per-cell best (D136). The hybrid's failure has a mechanism
  worth stating: the components differ in *what they return when wrong*, so a
  router picks which failure mode it inherits.
- **Vocabulary pretraining did not transfer** to the walker (D128).
- **Encoder fine-tuning was not indicated** — 1-NN retrieval with no head
  scores 0.925 where the trained head scores 0.614, so the information was
  already in the embedding (D129).

## 8. Method: the audit laws

Each was earned by a wrong verdict we had already written down. The last four
came from this work.

- **#6** A refusal threshold cannot be calibrated on a population that does
  not exhibit the failure.
- **#7** You cannot measure refusal without unanswerable questions. A
  store-derived benchmark is answerable by construction, so every refusal
  metric on it is vacuous. Grade them by *failure mode*, not just presence.
- **#8** A length check is not an alignment check. Hash-order-dependent set
  iteration silently misaligned cached embeddings and produced a conclusion we
  had to withdraw.
- **#9** An unanswerable population must include the **simple** case, not only
  the structurally interesting one.

Plus two rules of the same kind: **a shape-level holdout is not a composition
holdout** (report pair-cleanliness alongside every composition number), and
**evidence for a verdict must not be narrower than evidence for the claim**.

**On adjudication.** We had three independent models audit this paper's claims
against the raw numbers, blind to our reasoning. **Fleiss' κ = +0.135** —
slight agreement. Individual raters flagged 0, 2 and 2 of ten claims, and
flagged *different* ones; the same rater flagged between zero and seven across
runs. We therefore adjudicate by **2-of-3 quorum**, and we note that
"adjudicated" should never be read as "verified" (D140, D143). One of the
three raters shares a model family with the author, which is a real
independence limitation.

The adjudicators caught, among other things, a stale figure that survived a
full session of self-review, a denominator that was wrong by 21, and a claim
that quietly generalised beyond its measurement.

## 9. Reproduction

Every experiment is a standalone script in `scripts/` writing a JSON to
`results/` with a `run_manifest` and an explicit `scope` string. Figures in
this text are quoted at the stored precision or rounded **down** at a
boundary — the headline is stored as 0.4505 and quoted as 0.450, not 0.451. Caches are
content-verified against their text lists, and a cached re-run must reproduce
identical numbers — that reproducibility is itself the regression test for
audit law #8.

---

### Open, and honestly so

Phrasing robustness to genuine paraphrase is a modest cost we can measure but
not yet reduce. Entity generalisation is untested. Refusal on a dense store
remains bounded by ambiguity with no fix that shifts the frontier. And the
0.451 headline is a number we would like to be much larger before anyone
depends on it.
