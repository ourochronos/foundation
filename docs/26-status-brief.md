# Status brief — a direction call, with a claim that deserves attacking

Since the last panel round the model was implemented and walked over real data
across eight experiments. A direction call is now due, and the recommendation
rests on a summarising claim ("five of six mechanisms work") of exactly the
kind this project has repeatedly gotten wrong — a previous round found that one
such claim *licensed a non-fix*. Please test it rather than accepting it.

---

## 1. What exists

`foundation/model/` — ~1,100 lines, 176 tests:

- **`canonical.py`** — canonical form and content addressing. Domain-separated
  addresses `H(kind ‖ schema_version ‖ payload)`, algorithm-tagged so a move to
  a ZK-friendly hash does not orphan every reference. Sorts: `entity`, `text`,
  `quantity`, `time`, `act_ref`, `prop_ref`, plus `SOME`/`NONE` existentials.
  Refuses ambiguous namespaces (`local:`) and refuses to invent precision
  (`("2009", "day")` raises rather than becoming 2009-01-01).
- **`identity.py`** — union-find closure over accepted `sameAs`, deterministic
  representatives, fusion circuit breakers, confluent batch merge.
- **`conflict.py`** — proposition keys over class representatives, scope
  overlap with nested assumption frames, polarity / functional / existential /
  subsumption / opposition conflicts, agreement folded over evidence.
- **`predicates.py`** — subsumption (up-only), opposition (symmetric),
  composition; never materialised, only used to rewrite queries.
- **`query.py`** — typed expansion, adjudication structure, refusal.

## 2. What was measured on real data

| mechanism | result |
|---|---|
| dedup / merge | 100% of propositions carry both stores (8,000 real claims) |
| conflict detection | 18 real philosophical oppositions found, 3 before `oppose` existed |
| scoped coexistence | 0 conflicts scoped; opposition visible only when scope stripped |
| refusal | 0.000 wrongness on 4 unanswerable populations incl. a plausible near-miss |
| query expansion | 0/181 → 181/181 superordinate recall, 0 sibling leaks |
| **corroboration** | **0 across four corpora** |

Bugs real data found that four rounds of expert review did not: years are 1–4
digits (`476` broke the canonicaliser); dates written as entities manufactured
**104 false contradictions** about real people's birthdays; a functional
predicate called `1953` and `1953-04-11` disputed birth dates.

## 3. The corroboration result, and why it was closed

Four corpora, four zeros, each with its own mechanism:

- three corpora in one store share **0** triples — disjoint predicate
  vocabularies, and still 0 under an *oracle* entity aligner
- 558 same-domain AI papers: **0 of 1207** — papers cite rather than repeat
- philosophy, predicates closed: **0 of 144** — positions disagree rather than
  concur
- politics, predicates *and* frames closed, axis-generalised: **0 of 387**

Diagnosis: 316 claims produced **510 distinct concepts**. Corroboration needs
the predicate, frame and entity vocabularies closed **simultaneously**; closing
any two buys nothing. Closing entities from the corpus's own page titles was
measured and covers 11% of concepts, with dangerous near-misses
(`full-employment`~`unemployment`). That makes it an ontology-building project
— crowded prior art — so the line was closed rather than pursued.

Consequence: the `min_sources` refusal policy refuses **98.1%** of answerable
questions and is currently unusable on published text.

## 4. The recommendation being put to you

**Stop chasing corroboration; wire the working parts into an end-to-end
pipeline** — document → extraction into closed vocabularies → store with
provenance and frames → query → attributed answer or refusal.

Reasoning: nothing is wired together (the live store still runs the *old*
model, and every experiment built a throwaway pipeline — which is how a
sampling bug and a date-as-entity bug both survived); it is the shippable
artifact ("compatibilists hold X, hard determinists hold ¬X, here are the
spans, and I will not tell you which is right"); and observational data, the
one place corroboration should exist, cannot be tested without an ingestion
path.

## 5. What to answer

1. **Attack "five of six mechanisms work."** Which of those five is weaker than
   its number suggests? Note several were measured against the store's own
   contents, and two were called near-vacuous by the author already.
2. **Was closing corroboration right, or premature?** If premature, what is the
   cheapest experiment that would change the verdict?
3. **Is the pipeline the right next build?** If not, what — and what is the
   first experiment that could kill your alternative?
4. **Is there a use for the machinery that works** which this brief has not
   considered? Conflict detection, scoped coexistence and calibrated refusal
   all function; corroboration does not. What is that combination good for?
5. **What should be thrown away?** Eight experiments in, which parts are
   sunk cost being carried forward?

Be concrete and commit to positions. Disagreement between you is more useful
than consensus.
