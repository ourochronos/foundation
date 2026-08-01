# Extraction schema v4 — and why the next step is annotation, not round 4

Round 3 (`data/schema_v3/`) found three more fatal-class problems. They are
subtler than rounds 1 and 2, which is convergence, but they are not cosmetic.
This applies the fixes and then argues that **round 4 is the wrong next move**.

---

## 1. Content addressing cannot carry claim identity

> *"The address of `c1 = (smith, causes, famine)` must be computed over
> something. Include spans and Paper B can never compute store A's address —
> targeting degrades to copy-and-pray. Exclude them and the address depends on
> the identity closure, so one entity merge rehashes every claim transitively
> downstream. The document has wired its two 'solved' components into a circle
> and declared both unproblematic."*

Correct, and it is the v2 bug relocated: v2's edge silently targeted the *wrong*
claim; v3's targets **nothing**, which is worse for being silent.

**The fix is the one this design already uses everywhere else: propose, never
compute.** Cross-document claim reference is a *matching* problem, not an
addressing one. Paper B saying *"Contrary to Smith (2020)"* emits a **citation
with its surface reference**, and a later linking pass proposes
`claim_same_as`, which the closure accepts or rejects under its existing policy.
Identical in shape to entity linking, and for the identical reason.

So claims carry **opaque minted ids**, stable forever, never recomputed.
Merging is inserting `claim_same_as` rows; unmerging is deleting them. Monotone
and reversible, and an entity re-canonicalisation touches the link table rather
than every downstream reference.

## 2. Assertion and mention must separate — the store already does this

> *"If `evidence` is in the hash, identical claims from different documents
> yield different hashes and dedup dies. If it is excluded, merging two stores
> collides two claims with the same id and different evidence."*

The extraction schema had flattened what model v2 deliberately splits into
**assertion** (what is claimed) and **claim act** (someone claiming it, with
evidence). That split exists precisely so one proposition can carry many
independent attestations. Restored:

```jsonc
"assertions": [{"id": "a1", "subject": ..., "predicate": ..., "object": ...,
                "polarity": ..., "modality": ..., "scope": ...}],
"acts":       [{"assertion": "a1", "evidence": {"span": [0, 86]}}]
```

**This is the third time the extractor has failed to express what the store
already models** — after claims-as-objects and nested attribution. The lesson is
procedural: the extraction schema should be *derived* from the store model, not
designed alongside it.

## 3. Encoding non-determinism — the corpus-killer

> *"'If the ban passes, prices will rise' has three legal encodings: modality
> hypothetical, under_assumption, or a reified IMPLIES. 'Smith suggests X may
> cause Y' has two places for the hedge. Two annotators encode the same sentence
> in incomparable shapes; a contradiction checker sees no relation. Nothing
> errors."*

This is the polarity/marker collision generalised, and **reification created
it** — every construct expressible two ways is an ambiguity, and v3 added a
second way to express three things. It answers v3's own Q1: reification closed
the nesting hole and opened an encoding hole.

**Canonical-form rule, decided before annotation:**

1. **Reify only when the source attributes.** A stance verb with a holder
   (*"Smith denied"*, *"the Times reported"*) reifies. Nothing else does.
2. **Conditionals are `under_assumption`**, never reified `IMPLIES`.
3. **Hedges attach to the claim they hedge**, never to the reifying predicate.
   *"Smith suggests X may cause Y"* is `(smith, SAY, claim:c1)` with
   `c1.modality = hedged` — `SUGGEST` is not a stance predicate.

## 4. Stance predicates need a closed commitment table

> *"Cutting `attribution.mode` didn't delete the epistemic taxonomy — §1
> relocated it into the open predicate vocabulary. Annotators will coin
> QUESTION, RETRACT, CONCEDE, DOUBT freely, and each is a semantic change to
> what the gold means even though no bytes change."*

Right — the problem moved rather than dissolved. Stance predicates are a
**closed table with declared commitment semantics**, small and extensible by
deliberate act rather than by annotator coinage:

| predicate | attributor commitment | flips inner polarity |
|---|---|---|
| `SAY` / `REPORT` | neutral | no |
| `ARGUE` / `ASSERT` | pro | no |
| `DENY` | pro | **yes** |
| `DOUBT` / `QUESTION` | anti | no |

## 5. `scope`: absent means UNSTATED, not unrestricted

Round 3 wanted spatial and population scopes (*"in the UK"*, *"in mice"*,
*"in phase III trials"*). Under this project's asymmetry rule that absent means
*unrestricted*, adding any dimension later retroactively falsifies every
annotation — which is why v3 froze the set and why gemini called freezing it
wrong.

**Both are right, and the rule is what is wrong.** Gold should record *what the
text stated*; how to treat silence is a **query-time policy**, not an annotation
fact. So:

- annotation: `scope` is an **open list of typed qualifiers**, recording only
  stated scopes
- query: the engine chooses whether unstated means unrestricted, and that choice
  is revisable without touching gold

That makes new dimensions purely additive and removes the now-or-never trap
entirely — including for modality, which §4 of v3 kept only because of it.

## 6. The schema

```jsonc
{
  "entities": [{"id": "e1", "type": "PER", "mentions": [{"span": [12, 28]}]}],
  "assertions": [
    {"id": "a1",
     "subject": {"entity": "e1"},                  // | {"assertion": "aN"}
     "predicate": {"id": "P937", "span": [30, 39]},
     "object": {"entity": "e2"},                   // | {"literal"} | {"marker"}
                                                   // | {"assertion": "aN"}
     "polarity": {"value": "+", "span": null},
     "modality": {"value": "asserted", "span": null},
     "scope": [{"dimension": "temporal", "span": [41, 48]},
               {"dimension": "assumption", "entity": "e5"}]}
  ],
  "acts": [{"assertion": "a1", "evidence": {"span": [0, 86]}}],
  "citations": [{"from": "a3", "surface": "Smith (2020)", "span": [90, 102]}]
}
```

## 7. Why round 4 is the wrong next move

Three rounds, three fatal-class findings, each subtler than the last. That is
convergence, and the temptation is a fourth round. Against it:

**The remaining failure modes are agreement failures, and review cannot measure
agreement.** Encoding non-determinism (§3) was found by a reviewer *imagining*
two annotators diverging. Whether §3's canonical-form rule actually prevents
that is an empirical question about inter-annotator agreement, and no amount of
reading will answer it. The same is true of the polarity/marker ordering, the
modality three-way, and every "is this annotatable" question the panel has
raised.

**And this project's own record says so.** Twelve experiments, six instruments
that could not move, and the recurring lesson is that measurement finds what
review cannot — years being 1–4 digits, dates manufacturing 104 false
contradictions, negation at 25.1%. None of those came from reading.

**So: a 50-example annotation pilot**, two independent passes over the same
sentences drawn from all four corpora, measuring per-field agreement. It costs
a fraction of the full set, it directly tests the fields the panel flagged as
unannotatable, and disagreements are exactly the encoding ambiguities §3 tries
to legislate away.

Cheap, decisive, and it answers questions a fourth round would only re-ask.
