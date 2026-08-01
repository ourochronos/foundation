# Extraction schema v3 — everything is a claim

Round 2 (`data/schema_v2/`) was unanimous and correct: **v2 claimed in §2 to fix
nested attribution and claims-as-objects, and did not implement either in §5.**
The `object` union had no claim reference and `attribution` was a flat list.

The fix all four converged on collapses the schema instead of extending it.

---

## 1. Reification: one mechanism replaces three

*"The Times reported that Smith denied that climate change causes famine"*
becomes three ordinary claims:

    c1: (climate_change, causes, famine)
    c2: (smith,  DENY,   claim:c1)
    c3: (times,  REPORT, claim:c2)

`attribution` and `claim_relations` **disappear as constructs**. They were
special cases of a claim whose object is another claim, and modelling them
separately is what made nesting inexpressible. One mechanism now gives nesting,
denial, claims-as-objects, and — the thing v2 could not do at all —
**attributable, disputable claim-relations**: *"Smith argues that c2 refutes
c1"* is just `(smith, ARGUE, claim:c4)` where `c4 = (c2, REFUTES, claim:c1)`.

This also restores something round 1 broke. Cutting `attribution.mode` was
unanimous and right about **epistemic mode** (`asserts|infers|predicts` has
poor agreement) — but it took **stance** with it, and *denied* flips
truth-commitment where *reported* does not. Round 2 caught that the nesting fix
silently depended on the field that was cut. With reification, stance is simply
the **predicate** of the reifying claim (`DENY`, `REPORT`, `ARGUE`), where it is
a lexical judgement with a visible cue rather than an epistemic taxonomy.

## 2. Claim references must be content addresses, not document ids

> *"Paper B says 'Contrary to Smith (2020), tax cuts increase revenue.' Smith's
> claim is `c1` in store A; Paper B cannot target it unless it copies the claim
> locally. After merging, both stores may contain `c1`, and the edge can
> silently target the wrong claim."*

This is the `local:` namespace bug one level up, and the store already solved
it. **`c1` is a document-local handle used only within one extraction; the
stored form is the assertion's content address**, which is globally stable by
construction. Cross-document and cross-store targeting then works without
copying, and a merge cannot mis-target.

## 3. Gold format ≠ model output format

v2 deleted character offsets because *"1.5–3B models are demonstrably bad at
emitting character offsets"*. Round 2 called that correctly:

> *"That is a model limitation leaking into the gold format. The one layer
> defined as 'never changes' is defined by what a 1.5B model can emit in 2026.
> Quoted strings are not anchors — 'he said', 'however', 'not' occur dozens of
> times per document."*

So: **gold carries offsets. Models may emit quotes. Alignment happens at
scoring time**, where a mis-alignment is a scoring miss rather than silent
corruption of the layer everything derives from.

## 4. Modality, added because the asymmetry makes it now-or-never

*"may cause"*, *"suggests"*, *"is consistent with"* are pervasive in the four
academic corpora and absent from v2. Under this project's own rule that an
absent qualifier means unrestricted, **adding modality later retroactively
falsifies every annotation** by having silently claimed full commitment. By its
own logic it is keep-now-or-never, so it is kept:

    modality := asserted | hedged | hypothetical

Three values, each with a visible lexical cue, chosen to be annotatable rather
than philosophically complete.

## 5. `under_assumption` becomes an entity reference

v2 made it a closed frame inventory to avoid being a fourth open vocabulary.
Round 2: *"you cannot pre-enumerate the world's theoretical assumptions; new
papers invent new assumptions,"* and a closed list forces annotators to shoehorn
or forces constant vocabulary edits.

**It is an entity reference** — open like all entities, but canonicalised by the
same identity closure that already handles entity variation. That keeps exp73's
requirement (not a free string) without pretending frames are enumerable.

## 6. The schema

```jsonc
{
  "entities": [
    {"id": "e1", "type": "PER",
     "mentions": [{"span": [12, 28]}, {"span": [204, 212]}]}
  ],
  "claims": [
    {"id": "c1",                                  // document-local handle only
     "subject": {"entity": "e1"},                 // | {"claim": "cN"}
     "predicate": {"id": "P937", "span": [30, 39]},   // nullable id + surface span
     "object": {"entity": "e2"},                  // | {"literal": ...}
                                                  // | {"marker": "NONE"|"SOME"}
                                                  // | {"claim": "cN"}
     "polarity": {"value": "+", "span": null},    // span = the negation cue
     "modality": {"value": "asserted", "span": null},
     "scope": {"valid_time": {"span": [41, 48]},
               "under_assumption": {"entity": "e5"}},
     "evidence": {"span": [0, 86]}}
  ]
}
```

That is the whole thing. No `attribution`, no `claim_relations`, no
`link_proposal`, no `flags`, no `mode` enum — reification absorbed the first
two and rounds 1–2 cut the rest.

## 7. The polarity/marker procedure, restated and stress-tested

Round 2 broke v2's version with *"Bourdain was childless"* and *"lacked
children"*. Revised rule, and the ordering is what makes it decidable:

1. If the object is **quantified to nothing** — no such object exists —
   `marker: NONE`, and polarity is whatever the relation itself carries.
2. Otherwise, `polarity: "-"` **iff a negation cue scopes the relation**.
3. **Lexical negation resolves to the predicate first.** *"childless"* and
   *"lacked children"* are `(x, has_child, marker:NONE, polarity:"+")` — the
   negation is inside the lexeme, not a cue over a relation, and it quantifies
   the object.

## 8. Questions for round 3

1. **Does reification actually close the nesting hole**, or does it move the
   problem into deciding what is a claim versus a qualifier?
2. **Is the polarity/marker ordering (§7) decidable?** Break it again.
3. **What is now missing that would force re-reading every document?** Third
   time asked, because rounds 1 and 2 each found something.
4. **Is modality's three-value set annotatable**, or is it round 1's
   `attribution.mode` returning under a new name?
5. **Is anything left that is still too expensive for its value?**
