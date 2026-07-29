# Vocabulary-scale audit (2026-07-29)

D123 overturned D112 by re-measuring it at 61 relations instead of 5. That
established a general hazard for this project:

> **A negative result measured on a small relation vocabulary probably does
> not replicate.** Both D112 ("order is not recoverable, composition is
> memorised") and D115 ("over-provisioning does not help") looked
> architectural at n = 5–18 and dissolved or changed shape at n = 61.

Most of the walker arc (D117–D122) was measured on the **AI corpus's five
relations**. This audits what that costs.

## Status of every vocabulary-sensitive conclusion

| entry | measured at | claim | status at n=61 |
|---|---|---|---|
| D110 | 5 | 3 of 10 held-out phrasings collapse | **CONFIRMED and worse** — D127 finds phrasing is the *dominant* failure (−0.719), not a caveat |
| D110 | 5 | answer-type gate as refuser, 0.979 precision | untested; the walker replaced this mechanism entirely |
| D111 | 5 | multi-label vector cannot express `A→A`; arity head fixes it | **untested at 61** — see gap below |
| D111 | 5 | type-level feasibility measures corpus boundary; entity-level fixes it | replicated implicitly (the walker uses entity-level throughout) |
| D112 | 5 | composition is memorised, not composed | **OVERTURNED** (D123): 0.925 held-out pairs vs 0.913 trained |
| D112 | 5 | order is not linearly recoverable | superseded — the walker never asks the query for order |
| D113/D114 | 18 train | the anchor basis is the mechanism, not the bottleneck | **CONFIRMED twice on new tasks** — D125 (novel relations), D128 (phrasing) |
| D115 | 18 train | over-provisioning the basis does not help | **stands, but reframed** — D124/D126/D128 show compression trades against precision, so "does not help" is really "helps one axis, hurts another" |
| D116 | 19 / 800 | distribution match dominates scale | stands for *ranking*; **does not transfer to the walker** (D128) |
| D117 | 5 | store supplies order and depth; 0.912 held-out composition | replicated on wiki (D123, 0.925) |
| D118 | 5 | refusal ≈0.970, wrong ≈0.000 | **REFUTED as general** (D123/D124) — corpus-dependent; wiki gives 0.72–0.98 with wrong 0.017–0.073 |
| D119/D120 | 5 | refusal needs examples at each depth; absolute threshold | partly replicated (D126); the depth-dependence holds, the numbers do not |
| D121 | 5 | degrades by refusing, not by lying | **REFUTED as general** (D126) — on wiki the wrong-rate *grows* with depth (0.049 → 0.206) |
| D122 | 5 | shape-level holdout ≠ composition holdout | **methodological, holds** — and is what made D123 possible |

## The pattern

Everything that survived scaling is **mechanism**: the anchor basis, the
entity-level feasibility gate, the store-supplies-order formulation, the
pair-cleanliness rule.

Everything that failed to survive is a **number attached to a safety
property**: 0.000-wrong, "degrades by refusing", 0.970 refusal. Those were
measured on a sparse five-relation store and D124 explains why they do not
generalise — refusal quality is bounded by store density, because density
supplies plausible wrong continuations.

**This is the single most important thing to carry into any writeup.** The
mechanisms replicate; the safety numbers are regime-specific. Quoting the
latter without the corpus attached would be the most likely way to publish
something misleading.

## Outstanding gap

**D111's `A→A` result has never been retested at 61 relations.** It is the
one structural claim from the five-relation era still standing untested, and
it matters: `A→A` was 79% of real 2-hop shapes on the AI corpus. On wiki,
`instance of > instance of` is the third most common composition, so the
shape is present and the test is constructible. It should be run before the
arity/multiplicity story is repeated anywhere.

## Cheap re-tests worth doing

1. `A→A` on wiki, per above — the only untested structural claim.
2. D110's answer-type gate against the walker's residual refusal, on the same
   populations, to see whether the older mechanism was actually better at
   what it did.
3. D115's over-provisioning at 61 relations *with the trade-off axis in
   mind* — it was measured only on the generalisation side, never on the
   precision side, so its conclusion is half-measured rather than wrong.
