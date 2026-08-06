# Direction brief: can a schema crystallize, or does it always drift?

**A previous round of yours said no.** Four reviewers agreed that LLM-invented
frames proliferate without closing — `sale.seller`, `transaction.vendor`,
`exchange.merchant` — and one of you called the result *"schema debt with a
fluent amnesiac accountant."* The recommendation was that acquisition should
fill **values** only, and that new slot **structure** be a slow, human-gated
edit.

**The author is overriding that**, with an argument, and wants it attacked
properly rather than deferred to. This brief states his position as strongly as
it can be stated. Your job is to break it.

---

## 1. The position being defended

> *"The data is messy. I want a way to let it be messy but measured. Slots can
> slowly crystallize while remaining malleable. If we track which slots matter,
> the relations' importance can emerge through use. I want new concepts
> discovered and used without human curation being a serious limit on the rate
> of expansion."*

The claim is not that emergence is safe. It is that **the earlier failure was
unopposed emergence, not emergence**. In the measurement that motivated the
objection, 316 claims produced 510 distinct concepts — but nothing in that
pipeline ever merged two terms, pruned an unused one, or scored a term's worth.
Proliferation with no consolidation pressure explodes by construction; that
result does not bound what happens when pressure exists.

## 2. The proposed mechanism

**Three forces, not one.**

- **Proliferate.** Minting a slot is free. Extraction never blocks on an
  unknown relation.
- **Merge by distributional evidence.** Two slots are candidates for
  consolidation when they occupy the same frame position, draw fillers from the
  same type distribution, and are **substitutable in queries without changing
  answers**. The last test is operational — it uses the reasoner to evaluate the
  schema.
- **Prune by usefulness.** Slot usefulness is already defined query-relatively
  as value-of-information: does the answer change if this slot were filled
  differently? A slot that never moves an answer is not earning its place.

**Merging is aliasing, never fusion.** Consolidation is recorded as a
defeasible `slot_sameAs` claim with an acceptance policy, corroboration
requirement and class-size circuit breaker — reversible by deleting a row.
(This pattern is carried over from entity identity in the prior arc, where it
was built and tested; a bad `sameAs` was shown to fuse two people's classes and
flood the conflict detector, so the breakers exist because that was measured.)

## 3. The instrument, which the author considers the hard part

If the schema moves, there is no fixed reference to measure against —
improvement and drift look identical from inside. So:

**A frozen evaluation set that never participates in the emergence.** Held-out
queries with known answers, scored against a schema that is allowed to move.
Rising score as the schema consolidates is learning; falling score is drift.

**Plus a cheap early signal — the growth curve.** The prior explosion was
*superlinear*: concepts outran claims. Crystallization predicts *sublinear*
growth with a **rising alias rate**, as new slots increasingly merge into
existing ones rather than standing alone. Divergence should be visible in days,
not months.

## 4. Sequencing

Your earlier round argued for hand-authored frames first, to isolate the
runtime claim (pull-based operation beats push) from the acquisition claim
(frames can be learned). The author accepts the isolation and rejects the
phasing: **seed frames by hand, but build crystallization from day one and
measure it on its own instrument.** The isolation is satisfied by separate
*measurements*, not separate *phases*, and emergence may not retrofit onto a
system designed without it.

## 5. Context you need

Relevant measurements from the arc now closed:

| finding | number |
|---|---|
| unopposed vocabulary growth | 316 claims → 510 distinct concepts |
| extraction recall, every method | 0.155–0.266, against a 0.041 noise floor |
| missed relations verify as stated at the same rate as recovered ones | 0.636 both; gold independently audited and sound |
| entity-identity aliasing with acceptance policy + circuit breakers | built and tested; confluent batch merge required, incremental accept was not |

Named prior art from your last round: NELL (turned gaps into crawl targets, ran
for years, **drifted**), TAC KBP slot filling (plateaued near F1 0.35), SLD
resolution with tabling, POCL open preconditions, description logics, CYC.

## 6. What to answer

1. **Is the three-force model sufficient?** If not, name the missing force or
   the force that is wrong. Be specific about which of proliferate / merge /
   prune fails first.
2. **NELL drifted — why, mechanically?** Would a frozen held-out evaluation set
   have caught it, and at what lag? If the answer is "only after the damage",
   say what would have caught it sooner.
3. **Is aliasing-not-fusion enough** to keep consolidation reversible, or does
   the alias graph itself become the thing that drifts?
4. **What growth curve distinguishes crystallization from explosion**, over
   what horizon, and how many documents before the signal is trustworthy given
   a 0.041-scale noise floor on everything else measured here?
5. **Sequencing**: crystallization from day one alongside hand-seeded frames,
   or strictly after the runtime is proven? Commit to one.
6. **The cheapest experiment that would show drift EARLY** rather than after
   months — the thing NELL lacked.

Commit to positions. If the author is simply wrong and human gating is
unavoidable, say so plainly and say what the rate limit actually costs.
