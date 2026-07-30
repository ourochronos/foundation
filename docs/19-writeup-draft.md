# What survives contact with a real corpus

*Reindex-free knowledge, honest refusal, and the conditions under which each holds.*

Draft — 2026-07-30. Every figure traces to a `run_manifest` in `results/`;
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
and the ten audit laws that produced them the most reusable. The last of
those laws came from an adjudication result we did not expect: **four of
four claims that had never been adversarially audited failed when they
finally were, against two of ten that had.**

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

**Half of that commitment is now known to be wrong, and the half that
survives is the more interesting one.** It rested on a single comparison — the
walker at 0.912 against a path planner at 0.534 — and three adversarial raters
unanimously observed that beating one planner does not establish that no
planner could. They were right, and running it changed the claim (D158):

| | held-out correct |
|---|---|
| walker (greedy, store options) | 0.912 |
| exhaustive planner, **allowed** to consult the store | **0.903** |
| exhaustive planner, **denied** the store | 0.388 |

An exhaustive planner that consults the store for which chains are walkable
**matches the walker**, inside its confidence interval. Deny it the store and
it collapses. So *"the store supplies what makes this work"* is confirmed
overwhelmingly — availability filtering is worth **+0.515** — while *"and it
must be a step-by-step walk"* is refuted: greedy walking is worth **+0.009**,
inside noise.

**What the walker is for, then, is cost rather than accuracy.** Enumerating
every chain is 30 candidates on this 5-relation vocabulary, 3,782 at 61
relations, and 226,981 at depth 3; the walker is linear in branching and
depth and never enumerates. That is a real argument and we have not tested it,
so it is the honest form of the claim and Section 6 lists it as unestablished.

Reading our own code during this also found that the 0.534 was a literal
pasted into `exp24_walker.py` from a different script. Recomputed in-run on the
same questions, scorer and head, that planner scores **0.814** — so the gap we
reported as 0.378 is really 0.098. Nothing was fabricated; a number was
carried across scripts and compared as though it shared a protocol.

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

**Behaviourally it costs accuracy, the cost is asymmetric, and it grows with
depth.** Measured against a full rebuild — which is what reindexing would buy:

| | parametric head | 1-NN retrieval |
|---|---|---|
| new **entity**, known relation (depth 1) | +0.058 | +0.247 |
| new **relation** (depth 1) | **+0.191** | **+0.771** |
| depth-2 over appended content | **+0.249** | +0.666 |

At depth 1 a new entity is nearly free and a new relation is not: an entity is
a new node the walk can reach, whereas a relation is a new *direction* the
head was never trained to emit. **"Nearly free" is a depth-1 statement and
does not survive one more hop** — the depth-2 penalty is 0.249, larger than
either depth-1 figure. We stated this for a while without the depth
qualification; an adjudicator caught it (D153).

## 3. Can it learn?

Two different operations, two different answers.

**Addition.** Withhold 30% of subject-relation pairs (1,657 of them), append
them with artifacts frozen, and ask the same 1,200 questions before and
after. Of the questions the store **properly refused** beforehand, **432 of
432 (1.000)** are correct afterwards, with regression on previously-correct
questions at 0.003 (D133, `results/exp38_update.json`).

That number is conditional on honesty, and the store was not often honest: of
the 1,179 questions it could not answer, it properly refused only **0.366**
and confabulated the rest. Section 5 is about fixing that.

**One caveat we owe the reader**, because an adversarial rater found it and we
had not: the artifacts are frozen *by construction* in this experiment, but
the fingerprint check that proves nothing mutated was run in a **separate**
append experiment. Nothing rules out mutation during this one except the
design of the code. Moving the check inside the update path is specified and
unrun (D154).

**Revision.** Using MQuAKE-CF-3k's counterfactual rewrites applied through the
store's real supersession path, on the benchmark's human-written questions
(D141, `results/exp44_supersession.json`):

| | revision | **stale** | broke (→refuse) | wrong |
|---|---|---|---|---|
| edit the fact only | 0.469 | **0.002** | 0.274 | 0.255 |
| **+ the edges its new target needs** | **0.733** | 0.014 | **0.077** | 0.176 |

Revision is **two operations**, and the difference is 0.26 of coverage.
Editing a fact mid-chain leaves the rest of the chain expecting the *old*
target's outgoing edges; supplying those edges takes revision from 0.469 to
0.733 and breakage from 0.274 to 0.077, and nearly flattens the depth
gradient — 0.607/0.450/0.365 becomes 0.770/0.764/0.673 (D146). The cost is a
small rise in staleness (0.002 → 0.014) traceable to entity ambiguity, where
`edit()` correctly refuses to guess which entity a downstream subject means.

**Staleness is 0.002, which is not zero and we no longer write it as though
it were.** The transition matrix holds exactly one `old->old` case out of 431.
The store essentially does not keep asserting a superseded fact — the number
that had to come out near zero given invalidate-never-delete is a founding
commitment — but "does not" was an absolute an adversarial rater was right to
challenge (D153). Revision is much harder than addition, and it fails by
*refusing*, not by clinging.

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
depth 2 (D123). We state that as a margin rather than as the word "parity",
which carried no threshold until a rater asked for one: held-out is **+0.011**
against trained, inside a ±0.02 band and on the better side of it. Controls
confirm the walk is not forced: branching is 6.4 relations per step, shuffling
relation coordinates collapses accuracy to 0.001, and a random target of the
same magnitude gives 0.000.

The margin holds **at depth 2 only**; at depth 3 it is 0.626 against 0.683, a
gap of 0.057.

The contrasting failure is a 5-relation vocabulary, where held-out composition
*order* transfers at 0.513 against 1.000 on seen pairs — chance. Nothing was
ever measured between 5 and 61, so any "≥60 relations" threshold is
interpolation and we do not state one.

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

Depth extrapolates without depth-specific training **at three hops** — 0.849
zero-shot against 0.961 when 3-hop is trained — and **not beyond**: at depth 4
on a different corpus it falls to 0.289. We wrote "depth extrapolates" without
the bound for several revisions, and our own depth-4 data refuted it the whole
time (D119, D126, D153).

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

We previously reported **0.970 refusal** on the chain-break population as
evidence that the system refuses rather than guesses. We have since deleted
that claim rather than rescoped it. Two adversarial raters called it
unfalsifiable, on the grounds that it was measured on a population where
refusal could not have come out low and its scope then absorbed the failure by
pointing at the mixed benchmark — and the scope was ours, conceding in writing
that the population was unrepresentative while keeping the claim anyway
(D156). The 0.970 belongs in this paragraph, as the reason law #9 exists, and
nowhere else.

**The fix was a component we had removed.** An answer-type gate compares the
returned objects against the range of the relation the *question* asked for,
read off the target rather than the walked path. Re-adopting it (D134,
`results/exp39_typegate.json`):

| | gate off | gate on |
|---|---|---|
| not-applicable refusal | 0.050 | **0.693** |
| chain-break refusal | 0.337 | 0.650 |
| **depth-1** answerable wrongness | 0.118 | **0.045** |
| **depth-2** answerable wrongness | 0.175 | 0.102 |
| answerable correct | 0.875 | 0.765 |

**The correction that matters most for anyone citing our earlier numbers**: on
the mixed benchmark our selective-prediction figure is **AURC 0.4734**, where
the chain-break-only benchmark gave 0.1322. **We had overstated it ~3.6×.**

**Refusal is bounded by store density.** Refusal falls monotonically with the
number of relations available at the break step, at correlations of −0.79,
−0.83 and −0.91 across three populations (D124). We have written that the
mechanism is *ambiguity rather than noise*, on the evidence that wrongly
answered questions choose a relation whose gain is genuinely high (median
1.198 against 1.390 for correct ones). **That reading is an interpretation of
an overlap, not a demonstrated mechanism**, and two adversarial raters made
the same objection our own log had already recorded: branching and
confusability covary in every population we measured, and the experiment that
separates them — same node set, options added in a confusable and a
non-confusable arm — is named in D137's revisit list and has never been run.
A later result makes the objection sharper rather than weaker: adding reverse
edges doubles the option set and costs **nothing**, because reverse
coordinates never compete with a forward question (D137). Two principled fixes
— a multiple-comparisons correction and an ambiguity margin — both moved along
the precision/coverage frontier without shifting it.

**Thresholds are per-store.** The type gate's threshold can be computed from
store statistics alone (the p25 of within-relation type fit, needing no
labelled data), and it tracks the right property: MQuAKE's tighter ranges give
0.672 against wiki's 0.453. But it does **not** transfer — wiki evaluated at
MQuAKE's value drops coverage from 0.751 to 0.142 (D142). Thresholds are a
function of the store, and the store is available.

## 5b. Later corrections worth their own space

**Depth is a real variable but a weak one.** Three entries had each explained
a depth effect locally, and we hypothesised they were one finding — that
depth is merely a proxy for how many options the walk faces. A joint fit
refutes it: depth's coefficient shrinks only 8% when branching is added
(+0.213 → +0.195), so the two are near-independent. But **both effects are
small** (~0.19 log-odds per SD against a 0.718 base rate), which is the real
lesson: those three depth curves were local explanations of a modest effect,
and no unifying story exists to be found (D147). The stratification we first
designed to test this failed — the bands did not hold branching fixed — and
we report that rather than its numbers.

**Retrieval's advantage is mostly data-efficiency, and the residual is
real.** We originally concluded that a parametric head "destroys information"
retrieval preserves, on a single head at one capacity with an objective that
did not match the evaluation metric. Giving the head a fair fight (three
objectives × three capacities × three schedules) lifted it from 0.614 to
0.691, and *within one population* the gap shrinks from **0.229** at two
aliases per relation to 0.042 at ten — so we restated the advantage as
data-efficiency and withdrew "destroys information" (D148).

**Then we ran the falsifier, and had to withdraw half of that too.** Two
adversarial raters observed that a curve which stops at ten aliases cannot
distinguish "converging to zero" from "converging to 0.04". On the only
population where alias supply can be pushed to eighteen, **the gap stops
closing**:

| aliases | 2 | 6 | 10 | 14 | 18 |
|---|---|---|---|---|---|
| head | 0.757 | 0.844 | 0.890 | 0.882 | 0.892 |
| 1-NN | 0.975 | 0.975 | 0.977 | 0.967 | 0.983 |
| **gap** | 0.218 | 0.131 | **0.087** | 0.085 | **0.091** |

The tail slope is **+0.0015 per alias** — flat, if anything rising — against a
95% half-width of 0.026. The mechanism is the head's ceiling rather than
retrieval's climb: 1-NN sits at 0.975 from two aliases onward and never moves
while the head tops out at 0.892. Alias supply explains **most** of the gap
and not all of it; the residual is a capability difference (D155).

Two honest limits on that result. The plateau is measured on 8 relations, and
those 8 have a gap **0.030–0.052 larger** than the 24-relation control at
every shared alias count, so the level does not transfer. And the larger
population cannot be swept past twelve, because its relations do not have the
aliases — the experiment that would settle it there **cannot be run on this
corpus**. A floor is demonstrated where it is measurable and remains untested
where the original claim was made.

The confound also ran opposite to our prediction. We expected a smaller
relation vocabulary to make identification easier and shrink the gap; it
widened it. The likely reason is a selection effect on which relations carry
many aliases — a relation with twenty surface forms is one people describe
many different ways, so extra aliases bring confusability along with signal.
**"Collect more aliases" is not a uniform lever**: it works hardest on the
relations that need it least.

**Compression's cost is refusal, not the answers it enables.** We had written
that a frozen low-dimensional basis buys generalisation and pays for it in
precision, fitted across three experiments — which we described as three
corpora until we checked and found they were one store under three separately
derived thresholds. Tuning both representations by the same rule (D159):

| on novel relations, same threshold | correct | wrong | abstain |
|---|---|---|---|
| raw 1024-d | 0.005 | 0.153 | **0.842** |
| basis K=48 | **0.742** | 0.167 | 0.092 |

Raw's 0.005 is not raw getting novel relations wrong — **it is raw refusing
them**. Compression converts those refusals into correct answers while the
wrong-rate barely moves. At matched coverage the gain is **+0.741 correct for
+0.072 wrong**, a tenth of the gain. The real costs land elsewhere: refusal on
unanswerable novel questions falls **0.706** (the basis answers 37% of them
against raw's 6%), refusal on known unanswerables falls 0.569, and
known-relation answering falls 0.141 at nine times the wrong-rate.

So the axis was pointing at the wrong quantity. **A frozen basis makes a novel
relation answerable and makes the system less able to tell when it should not
answer at all** — which is a more useful thing to know, and follows from the
same numbers, once answerable and unanswerable populations are not averaged
together.

The full picture across three axes still reverses the original
recommendation:

| axis | retrieval | head |
|---|---|---|
| unseen **phrasings** | **0.925** | 0.691 |
| new **relations** | 0.229 | **0.782** |
| new **entities** | 0.526 | **0.766** |

Retrieval wins on the one axis that is not about novelty and loses on both
that are, because a bank can only return targets it already holds. **Entity
generalisation holds for the head** — subjects held out of training score
0.766 against seen subjects' 0.795, and the head's gap stays under 0.05 on
all three question populations — which closes a limitation we previously
listed as untested. A second *corpus* was not tested (D149).

## 6. What we cannot claim

- **Not free-form language.** Questions are templated or benchmark-supplied.
- **Not depth-unbounded in practice.** Depth behaviour is corpus-dependent: it
  decayed on one corpus and *improved* on another, and zero-shot extrapolation
  is demonstrated at three hops and refuted at four.
- **Not honest by default.** Without the answer-type gate the walker
  confabulates on the majority of what it cannot answer. Honesty is a
  component we added, not a property the design provided.
- **Not a free lunch on refusal.** Every refusal gain we found cost coverage.
- **Not established that the walk must be step-by-step.** A store-filtered
  exhaustive planner matches the walker (0.903 vs 0.912). The walker's
  remaining justification is that it does not enumerate — real, and untested
  at a vocabulary where enumeration is expensive (§1).
- **Not a demonstrated mechanism for the density bound.** Branching and
  confusability covary in everything we measured (§5).
- **Not the compression trade-off as we first stated it.** Two of its three
  legs now hold under one threshold protocol, but the cost is refusal rather
  than the accuracy of what compression enables (§5b). The phrasing leg is
  still uncontrolled.

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
- *"A head destroys information retrieval preserves"* — withdrawn once the
  head was trained fairly (D129 → D148), then **half-restored** when the alias
  curve was run to eighteen and plateaued at 0.09 (D148 → D155). This one
  reversed twice, and the second reversal came from an adversarial rater's
  falsifier rather than from us.
- *"Compression buys generalisation and costs precision"* — the trade-off is
  real and was **mislocated**. Under one threshold protocol the wrongness cost
  on the population compression helps is a tenth of the gain; what it actually
  costs is refusal (D125/D126 → D159). The scope also claimed three corpora
  where there was one store.
- *"Order and depth must come from the store rather than from a planner"* —
  the store half is confirmed overwhelmingly, the planner half is refuted: an
  exhaustive planner that consults the store matches the walker (D117 →
  D158). The comparison that established the original claim also quoted a
  baseline pasted from another script, which understated the alternative by
  0.28.

**Things that did not work:**
- **Combining signals never beat the better component**, three times: two
  refusal fixes (D124), a six-signal confidence score that ranked worse than
  the residual alone (D132), and a retrieval/fallback hybrid whose two routers
  both lagged the per-cell best (D136). The hybrid's failure has a mechanism
  worth stating: the components differ in *what they return when wrong*, so a
  router picks which failure mode it inherits.
- **Vocabulary pretraining did not transfer** to the walker (D128).
- **Encoder fine-tuning is still not indicated, for a changed reason.** We
  first said the information was already in the embedding because 1-NN scored
  0.925 where a head scored 0.614. A fairly trained head reaches 0.691, and
  with enough aliases 0.892 — so the original argument was too strong. What
  survives is narrower and better supported: no head we could train at any
  capacity, objective or alias supply matched retrieval on known relations
  (D129 → D148 → D155).

## 8. Method: the audit laws

Each was earned by a wrong verdict we had already written down. Five came
from an extraction arc that preceded this work; five came from this one.

- **#1** Evidence for a verdict must never be narrower than evidence for the
  claim. We graded an 8k extraction window of a 40k source; all three rater
  disputes lived in the missing 32k.
- **#2** A locator's failure to find evidence is never itself evidence. Any
  stage that can delete must abstain instead.
- **#3** An adjudicator is a second rater, not an oracle. We once accepted
  five of its corrections unverified, one turn after writing the law against
  exactly that; one was a hallucination.
- **#4** Every convention declared to the extractor must be declared to the
  auditor. Carrying four unstated conventions across moved agreement
  0.740 → 0.940 on the same claims with the same labels.
- **#5** A frozen label may be amended only on new evidence, with the
  evidence recorded and the direction disclosed — never to move a number
  toward a gate.
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
- **#10** A claim must carry the condition its number was measured under, in
  the claim sentence itself. **A scope condition qualifies a claim; it does
  not retract one.** Nine flags across two adjudication rounds had this shape,
  and in every one the scope was honest while the claim sentence overreached
  — "appending is near-free" with the depth in scope, "depth extrapolates"
  with the single measured depth in scope. A document accurate line by line
  still misleads the reader who stops at the claim, which is every reader
  (D156).

Plus one rule of the same kind that has not earned a number: **a shape-level
holdout is not a composition holdout** — report pair-cleanliness alongside
every composition number.

**On adjudication, and a result about auditing itself.** We had independent
models from four families (OpenAI, Google, Anthropic, xAI) audit these claims
against the raw numbers, blind to our reasoning, under two prompts: *"is this
claim supported?"* and *"attack this — what would falsify it, does the
evidence rule that out, is the scope doing work or absorbing failure?"*

**The strongest result is about which claims fail.** Five claims sat in our
table having never faced either prompt — a drift we did not detect until a
test written to catch it passed by comparing counts. Four of those five were
then adjudicated. **All four were flagged, two unanimously.** Of the ten
claims that had been through adjudication before, two were flagged. The claims
that skipped the loop were carrying the defects, and carrying worse ones: not
arithmetic, but a single baseline, a single population, a pattern fitted after
the fact (D153, D154).

**Verification pressure and adversarial pressure fail in opposite directions,
and only running both catches either.** On a 14-claim table, verification
flagged **zero** at quorum while attack flagged **six**. Neither subsumes the
other: two claims were flagged only by attack, one only by verification. We
have a clean mechanism for it too — one claim was flagged as overreach under
verification, we "fixed" it by adding a qualification, and the adversarial
pass then judged that same claim unfalsifiable. The repair produced vacuity.

**A verification pass that finds nothing may be measuring hedging.** Twice we
reported that four families flagged *zero* claims and read it as support.
Sharpening the claims to carry specific numbers — a specific number can be
checked and can be wrong — took the same prompt from zero flags to five. The
prompt never changed. "Four families passed it unanimously" should not be
reported without stating how falsifiable the claims were.

Three cautions we can quantify. **Raters are unstable across identical runs,
and it is one rater**: on three repetitions of the same input, one flagged 6,
7 and 4 of fourteen while the other three varied by 1, 1 and 2. Majority-of-3
therefore does nearly all its work on a single family. **A same-family rater
is more lenient only under verification** — it returned 14/14 supported, the
only clean sheet, and then flagged five under attack, agreeing with the
independent quorum on five of six; we had previously reported this leniency as
general, and it is not. And **keep the panel odd**: re-deriving quorum with a
fourth rater moved one verdict of fourteen, and only because four raters turn
a 2-of-4 majority into a tie. We report quorum counts rather than κ, which
with skewed marginals tracks the table's messiness rather than the raters'
reliability.

**What adjudication cannot do.** Two of the worst defects in our table fell to
an afternoon of reading rather than to four families of raters: a scope that
said "three different corpora" when all three experiments read the same store,
and a baseline pasted from another script rather than computed. Neither is
visible in the JSON an adjudicator receives. **Adjudicators check whether a
claim follows from the evidence shown to them; they cannot check whether the
evidence is what the claim says it is** (D156).

"Adjudicated" should not be read as "verified".

## 9. Reproduction

Every experiment is a standalone script in `scripts/` writing a JSON to
`results/` with a `run_manifest` and an explicit `scope` string. Figures in
this text are quoted at the stored precision or rounded **down** at a
boundary — the headline is stored as 0.4505 and quoted as 0.450, not 0.451.
Caches are content-verified against their text lists, and a cached re-run must
reproduce identical numbers — that reproducibility is itself the regression
test for audit law #8.

The claims table is a single machine-readable block that the adjudicator reads
directly, and every stored verdict stamps the claim text it judged, so editing
a claim visibly retires the verdicts that judged its earlier wording. Both
mechanisms exist because we published an adjudication of text that had never
been adjudicated, twice, in adjacent decision entries (D151, D152).

---

### Open, and honestly so

Phrasing robustness to genuine paraphrase is a modest cost we can measure but
not yet reduce. Refusal on a dense store remains bounded by ambiguity with no
fix that shifts the frontier, and the experiment that would show ambiguity is
the mechanism has not been run. Whether order and depth must come from the
store, rather than merely can, rests on a comparison against one weak planner.
And the 0.450 headline is a number we would like to be much larger before
anyone depends on it.

Four falsifiers named by adversarial raters are specified and unrun. We are
reporting them here rather than waiting, because a paper that lists the
experiments most likely to break it is more useful than one that runs them
first and mentions only the survivors.
