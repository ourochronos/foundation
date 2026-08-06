# Frames v0 — the machinery, not the model

A fresh start. The extraction arc is tagged `extraction-arc-v1` and set aside;
what carries forward is the discipline and the measurements, not the code.

**The shift in what is being built.** The last eighteen experiments tried to
make a better extractor. This builds **the machinery a reasoner operates** —
how it discovers what it needs, acquires what it lacks, and reports what it
could not get. The model is the consumer, not the subject.

---

## 1. What survives from the extraction arc

Four measurements, and nothing else:

| finding | why it still matters |
|---|---|
| recall pinned at **0.155–0.266** across every method, against a **0.041** noise floor | push-extraction is not a tuning problem; the ranking of methods was mostly noise |
| missed relations verify as **stated at the same rate as recovered ones** (0.636 both), and exp89 confirmed the gold is sound | the information is in the text and the pipeline does not get it — a representation mismatch |
| blanket extraction: **473 predictions for 87 correct**; a prior system hit the same wall at 29k claims | extract-everything-then-filter has failed twice with numbers |
| corroboration **0** across four discourse corpora | agreement is not a signal these sources can supply |

And one methodological result that outranks all of them: **measure the noise
floor before ranking anything**, and **check an instrument can move before
trusting a null**. Seven instruments in that arc could not move, and six of
those returned clean-looking results.

**Deliberately not carried forward**: the four discourse corpora, corroboration
as a signal, REBEL and the pretrained-extractor arms, the calibration and
hybrid-filter work, the 29k claim store, and the three existing closure
structures. That last one was listed as an asset in the pivot brief and a
reviewer correctly called it *"sunk cost wearing a disguise"* — the dependency
closure gets built fresh from frame declarations.

**Kept**: the one-slot query harness from exp85, and the source verifier — now
constrained to a binary supported/unsupported judgement, because exp89 showed
its STATED-vs-INFERABLE boundary is the unreliable part.

## 2. The primitive

**A slot is a declared structural relation between a concept and its context.**
Not a data field. That framing has a consequence worth stating plainly: **the
slot structure *is* the dependency graph** that closure runs over. Slots and
closure are one mechanism seen from either end, which is why this does not need
the three closure structures inherited from the old arc.

Three properties follow, and the second is the one that makes this worth
building:

**Slots do not all need filling to reason.** They signal what is and is not
known. A partially-filled frame is a usable state, not a failure.

**Slots have query-relative usefulness.** Not all context bears on every
inference. Usefulness is measurable as value-of-information: *does the answer
change if this slot is filled differently?* If not, the slot is irrelevant
**to this query** and its emptiness is not a gap.

This is what rescues completeness from its strongest objection. A reviewer
argued the completeness *ratio* is worse than no guarantee — "3 of 5 filled"
reads as nearly-done when the two missing may be the only ones that matter, and
the number actively suppresses doubt about whether the schema is adequate. That
objection lands on the **ratio**, and the ratio is discarded. What is kept is
*which slots are open*, weighted by whether they matter here.

**Slot counts are never reported.** Frame granularity is arbitrary — is `sale`
three slots or nine? — so any filled/total figure measures the schema author's
taste. Anyone who dashboards it optimises coarseness rather than knowledge.

## 3. Faults

The earlier four-way taxonomy is dead. All four reviewers converged: you cannot
classify "resolvable externally" against "unresolvable" *before* searching,
because resolvability is an empirical outcome, so the unknown case swallows the
others and the modal case becomes the residual.

Replaced with **budgeted operational states**, assigned after the attempt:

    locally supported            the store has it
    acquiring                    an executable action is running
    budget-exhausted, unfilled   searched to a recorded limit, still nothing
    structurally undecidable     no action of any kind would resolve it

The fault **is** the fetch trigger. Nothing is classified in advance.

**Every fill is verified against source before the slot closes.** This is not
optional hygiene. A reviewer named the failure mode exactly: *LLMs almost never
say "I can't" — they fill.* Without a verifier in the loop, the
budget-exhausted state never occurs, refusal never fires, and
fault-as-acquisition is hallucination-as-acquisition.

**Acquisition fills values, not structure.** New slots are a slow, human-gated
schema edit — never a fault handler. This is the concession that keeps the
1970s failure from repeating: an LLM inventing `sale.seller` will also invent
`transaction.vendor` and `exchange.merchant`, and those never close. exp73
measured that exact explosion one level down: 316 claims produced 510 distinct
concepts.

## 4. Refusal is a typed request

The output of budget-exhausted is not a verdict. It is **the specific unfilled
slot, named, typed, and explained** — with the option for the user to supply
the value and requery.

**The human is the last tier of the memory hierarchy.** This is what makes the
taxonomy objection stop mattering: you never have to decide whether something
was knowable, only report precisely what was missing and what was tried. The
slot is the explanation, and an unfillable slot is a question rather than a
dead end.

## 5. What this reinvents, deliberately

Named by reviewers so it is built as reinvention rather than discovered as one:

- **SLD resolution with tabling** — Prolog had demand-paged fault-as-fetch fifty years ago
- **POCL planning open preconditions** (SNLP/UCPOP) — a nearly isomorphic flaw taxonomy
- **NELL** (Carlson & Mitchell, 2010) — turned gaps into crawl targets, ran for years, **drifted**; its postmortems are required reading
- **TAC KBP Slot Filling** — a decade of shared tasks that **plateaued near F1 0.35**. exp85's 0.463 on one run is *consistent with that ceiling*, not above it
- Open-world assumption in description logics; ATMS; CYC

**The narrow claim to novelty**: nobody has coupled query-driven inference
faults to slot-typed acquisition *with verification against a concrete need*.
NELL lacked a reasoner pulling on it; KBP lacked a consumer. **The consumer is
the novelty** — everything else here is deliberate reinvention.

## 6. The first experiment, and why it is shaped this way

Three of four reviewers said do not build this; one said build it, and that one
argument is the only one that survives the others' objections:

> **Demand paging changes the denominator.** Frames are never invoked over the
> whole corpus, only for the query in hand — so the system stops being scored
> against every gold triple nobody asked about.

That is testable, and it is what gets tested first.

**Multi-hop QA** (MuSiQue or 2WikiMultihopQA, ~100 questions), **~20
hand-authored frames**, loop: reason → fault → one-slot query → **verify** →
continue. Roughly 30 questions whose answers are deliberately **absent** from
the corpus.

**Hand-authoring the frames is the point.** It isolates the *runtime* claim
(pull-based operation beats push) from the *acquisition* claim (frames can be
learned on demand). Acquisition is only tested if the runtime survives, which is
the discipline the old arc lacked when it conflated coverage with judgement for
three experiments.

Two kill criteria, registered now:

1. **Slot-conditioned recall on required hops < 0.5** — not decisively above
   the 0.2 wall — and the representation-mismatch hypothesis is false. The
   pivot dies.
2. **The system produces confident fills for more than half of the deliberately
   unanswerable slots** — and verification is not working, so the fault
   machinery is decoration.

A second experiment, held for after: the **schema drift stress test** — one
factual payload written two ways (academic, news), does frame acquisition
produce aligning schemas? That tests the acquisition claim, and only matters if
the runtime survives.
