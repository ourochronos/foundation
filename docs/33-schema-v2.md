# Extraction schema v2 — revised against the panel, for a second review

Round 1 (`data/schema_v1/`) produced four unanimous cuts, one finding that
invalidates the premise of the previous draft, and a genuine four-way split on
the architecture. This is the revision. **Changes are justified by the review
comment that forced them**, so the second round can check whether each fix
actually fixes the thing.

---

## 1. What round 1 settled

**Unanimous — `attribution.mode` is deleted.** All four ranked it worst.
*"No stable annotation rule. Every document reports; 'Keynes argued' is
historical assert AND report."* Collapsed to a two-way `author | reported`,
which is refinable later by relabelling — additive, unlike the reverse.

**Unanimous — "Keynesians hold X" is the CLAIMANT, not a scope.** The
annotation test is syntactic: *is there a reporting or stance frame in the
text?* Then `holder`. `under_assumption` is reserved for the source
conditionalising on its own account — *"Given Keynesian assumptions, X"*.

And the part that rescues exp72: **the school→scope projection is code, not
annotation.** The closure can project claim-acts-by-school into assumption
scopes at query time, so scoped coexistence survives without annotators ever
choosing between two overlapping encodings.

**3/4 — linking leaves the annotation target.** `link_proposal` and
`link_confidence` are *"linker skill, not extractor skill; the closure decides
anyway"* and linking is a separate, cheaper, **additive** pass that never
invalidates a claim.

**4/4 — `flags` is annotator scratch, never gold.**

## 2. The finding that changes the premise

> *"Your own measurement says discourse **cites and disputes, it does not
> repeat** — and the schema has no way to say 'claim c2 disputes c1'. For four
> of your five corpora, the signal you measured as existing is inexpressible in
> the schema you're about to annotate against."*

This is the round's most expensive catch. exp70 measured that papers **cite**;
exp72 measured that positions **dispute**; both are claim-to-claim relations,
and the v1 schema could not encode either. Annotating five corpora against it
would have produced a gold set unable to express the one signal actually
present in four of them.

Two more of the same shape: **claims must be addressable as objects**
(*"The UN reports that [climate change causes famine]"*), and **attribution
must nest** (*"The Times reported that Smith denied X"* — routine in reportage,
which is our only corroboration domain).

Note the store already supports all three — model v2 added `act_ref` and
`prop_ref` sorts precisely for claims-about-claims. **The extractor could not
emit what the store could hold**, and I wrote both.

## 3. Two latent bugs, each caught by one reviewer

**The `polarity`/`marker` collision.** *"Bourdain had no children"* had two legal
encodings: `polarity:"-"` + `marker:SOME`, or `polarity:"+"` + `marker:NONE`.
Two encodings of one sentence in a gold set is not low agreement, it is
**training-signal contamination — the model is penalised for a correct
answer** — and it corrupts the exact channel (negation, 25.1% of philosophy)
that motivates the whole project.

Fixed by decision procedure, written before annotation:
> `polarity` records **only** the presence of a sentence-level negation cue over
> the relation. `marker` records **only** quantification of the object
> (`NONE` = no such object exists). *"Bourdain had no children"* is
> `polarity:"+"`, `marker:"NONE"` — there is no negation cue on the relation.
> *"Bourdain does not have three children"* is `polarity:"-"` with a literal
> object.

**`under_assumption` as free text is a fourth open vocabulary.** exp73 measured
that leaving one of three vocabularies open kills corroboration outright (316
claims → 510 concepts). *"Two annotators will never write the same assumption
string; scope overlap will silently never fire."* My own measurement predicted
this and I designed it in anyway. It is now **an entity reference or a closed
frame inventory, never a string.**

**And the asymmetry that makes scope decisions final**: under "absent qualifier
= unrestricted", adding a scope field later **retroactively falsifies** every
old annotation, because they silently claimed unrestricted. Scope fields are
keep-now-or-never; everything else is additive.

## 4. The architectural split, and how it is resolved

Round 1 split four ways on "bundle inference, decompose output":

- **gemini: no** — a hallucination cascade; a bad `e1` makes every claim
  referencing it structurally unscorable
- **fable: yes** — joint training correlates *errors*, not semantics; it is a
  metric problem, solved by **alignment-forgiving scoring** (score claims under
  the best entity-id remapping)
- **grok: split assertion from act**
- **gpt: discard** — it mixes *source-grounded extraction*, *ontology
  normalisation* and *store insertion*, and those **evolve at different rates**

gpt's objection is the one that survives, and it points at the fix rather than
away from it. The schema must separate what changes at different speeds:

| layer | changes when | example |
|---|---|---|
| **source-grounded** | never — it is what the text says | spans, cues, surface forms |
| **normalisation** | when a vocabulary evolves | predicate id, entity link, frame id |
| **insertion** | when the store model changes | assertion/act split |

**So annotate the source-grounded layer and derive the rest.** Recording *"the
polarity cue is 'not' at [34,37]"* survives any change in how polarity is
represented; recording `polarity:"-"` does not survive a move to three values.
This is what actually protects the annotation investment, and it makes fable's
and gpt's positions compatible: bundle inference, decompose the output, **and
anchor every decision to a span.**

## 5. The schema

```jsonc
{
  "entities": [
    {"id": "e1", "mentions": [{"text": "Anthony Bourdain", "quote": "..."},
                              {"text": "the chef", "quote": "..."}],
     "type": "PER"}                       // closed type set; linking is a later pass
  ],
  "claims": [
    {"id": "c1",
     "subject": "e1",
     "predicate": {"id": "P937", "surface": "worked at", "cue": "worked at"},
     "object": {"entity": "e2"},          // | {"literal": ...} | {"marker": "NONE"}
     "polarity": {"value": "+", "cue": null},        // cue = the negation token
     "scope": {"valid_time": {"quote": "in 1998"},
               "under_assumption": "f:keynesian"},   // CLOSED frame ref, never a string
     "attribution": [{"holder": "e3", "kind": "reported", "cue": "argued that"}],
     "evidence": {"quote": "..."}         // quoted text; offsets aligned mechanically
    }
  ],
  "claim_relations": [
    {"from": "c2", "type": "disputes", "to": "c1", "cue": "however"}
  ]
}
```

Changes from v1, each traceable: `mode` → two-way `kind`; `attribution` is a
**list**; claims have **ids** and can be relation targets; `claim_relations`
added; `link_proposal`/`link_confidence`/`flags` removed; every decision carries
a **cue or quote**; `under_assumption` is a closed reference; offsets replaced
by quoted strings, since *"annotators disagree on boundaries and 1.5–3B models
are demonstrably bad at emitting character offsets."*

## 6. The sequencing insight, which changes what happens next

> *"You need the annotated gold either way — for evaluation. **The schema is the
> sunk cost, the model is not.** Annotate first, benchmark both, decide
> second."*

The fine-tune-versus-prompt question does **not** need answering before
annotation, because the gold is required to settle it. So the model choice is
deferred and the schema is the only commitment being made now — which is what
this review is for.

## 7. What to answer this round

1. **Does the cue/span anchoring (§4) actually protect the investment**, or does
   it just move the ambiguity into "what counts as the cue"?
2. **Is the polarity/marker decision procedure (§3) unambiguous?** Give a
   sentence it fails to classify.
3. **`claim_relations`** — is `disputes|supports|cites` the right minimal set,
   and is a flat list enough, or does it need scoping too?
4. **What is still missing** that would invalidate annotation when added? Same
   test as before: not "nice to have" but "forces re-reading every document".
5. **Is anything here still too expensive** for the value it returns?
6. **What would you cut if the annotation budget were halved?**
