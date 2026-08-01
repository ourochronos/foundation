**1. The fatal flaw**

The round-1 finding this revision exists to fix — *nested attribution and claims-as-objects* — is not fixed. It is claimed fixed in §2 and then not implemented in §5.

- `attribution` is a **flat list**. *"The Times reported that Smith denied that he met Epstein"* becomes `[{holder: Times, kind: reported}, {holder: Smith, kind: reported}]`, which is (a) indistinguishable from *"Smith reported that the Times denied…"* — the list has no embedding order semantics — and (b) unable to express *denied* at all, because `kind` was collapsed to `author|reported`. Denial flips truth-commitment; `reported` doesn't. The unanimous round-1 cut of `attribution.mode` deleted the stance dimension, and the nesting "fix" quietly depends on it. You cannot recover "denied" from the stored `cue` string later without re-adjudicating every document ("Smith said he did not X" vs "Smith denied X" have different cues, same stance; "Smith dismissed X" has neither).
- `object` is `{entity | literal | marker}` — **no claim ref**. *"The UN reports that [climate change causes famine]"* still cannot put a claim in object position. §2 boasts the store has `act_ref`/`prop_ref` and "the extractor could not emit what the store could hold." That sentence is still true of v2. The only claim-to-claim channel is `claim_relations` with a closed set of three, and a `claim_relation` carries no attribution and no evidence quote — so *"Smith argues that c2 refutes c1"* (routine in philosophy, 1 of the 5 corpora) is inexpressible: the relation itself is a claim, and relations can't be claimed, attributed, or disputed.

Concrete alternative — reify attribution and relations as claims, which is grok's position and it was right:

```jsonc
{"id": "c3", "subject": "e_times", "predicate": {"id": "REPORT", "cue": "reported"},
 "object": {"claim": "c2"}},
{"id": "c2", "subject": "e_smith", "predicate": {"id": "DENY", "cue": "denied"},
 "object": {"claim": "c1"}},
{"id": "c1", "subject": "e_smith", "predicate": {"id": "P26?met", "cue": "met"}, ...}
```

One mechanism gives you nesting, denial, claims-as-objects, and attributable claim-relations; `attribution` and `claim_relations` both become sugar over it.

**2. What forces a CLOSED-layer change within a year: quotes instead of offsets, and missing modality.**

- §4's entire protection argument is *"the cue is 'not' at [34,37]"*. §5 then deletes offsets because small models emit them badly. That is a **model limitation leaking into the gold format** — the one layer defined as "never changes" is defined by what a 1.5B model can emit in 2026. Quoted strings are not anchors: "he said", "however", "not" occur dozens of times per document; abstracts repeat in intros; boilerplate repeats in reportage. "Aligned mechanically" will mis-anchor silently, corrupting the layer that everything else derives from. Fix now: annotate offsets (or quote + occurrence index) in gold; let *models* emit quotes and align at scoring time. Gold format ≠ model output format.
- **Modality/hedging is absent.** "May cause", "suggests", "is consistent with" — pervasive in the four academic corpora. By the document's own asymmetry rule, absent qualifier = full commitment, so adding a `modality` field later retroactively falsifies every annotation. By its own logic this is keep-now-or-never. Fix now — or better, kill the asymmetry itself (see §4, Q4).

**3. Over-built: `under_assumption` and the closed frame inventory. Delete them.**

§1 already rescued exp72 by making school→scope projection *code over claim-acts*. The frame inventory then re-solves the same problem in annotation, requiring an authored ontology of intellectual positions (`f:keynesian`) before annotating anything — a fourth vocabulary, the exact thing exp73 says kills corroboration, now merely relocated from open-string to who-maintains-this-inventory. Genuine source-side conditionalising ("Given Keynesian assumptions, X") is rare enough to encode as an ordinary claim with an entity-holder until data proves otherwise. Also over-built: `predicate.id` (P937) inside the annotation target — §4's own table puts predicate ids in the *normalisation* layer, and §1 made entity linking a later pass; predicate linking inline contradicts both. Record `surface`+`cue` only; normalise later.

**4. The open questions — note there are six, not seven.**

1. **No, as implemented.** Without offsets it is not anchoring at all (see 2). And "what counts as the cue" is a real residue for discontinuous/lexical negation: "fails to", "lacks", "never", "it is false that". Ship a cue inventory with the guidelines or agreement dies here.
2. **Not unambiguous.** *"Bourdain never had children."* "Never" is a negation cue over the relation → `polarity:"-"`, object "children" → `marker:SOME`. But *"Bourdain had no children"* → `polarity:"+"`, `marker:NONE`. Synonymous sentences, different gold — the training-signal contamination §3 claims to have fixed, relocated one word over. Also unhandled: negation in subject position ("No economist accepts X").
3. **Wrong set and wrong shape.** Missing `attributes/reports` (needed for the §2 examples) and, in the citing corpora, `cites` without stance is nearly signal-free — exp70's own finding is that citation carries dispute. Flat is not enough because relations need attribution and evidence (see 1). Reify as claims; keep `claim_relations` only as a derived view.
4. **Modality (see 2), attribution stance (see 1), and subject quantification.** All three fail the "forces re-reading" test in the bad direction. Separately: the asymmetry principle itself — "scope is keep-now-or-never, everything else is additive" — is **wrong twice** and was used to decide what didn't need fixing. (a) The retroactive-falsification problem is dissolved by one line of null-semantics: `"scope": null // = unannotated, NOT unrestricted`, plus a per-record `annotated_fields` list. Absent-means-unknown is a convention, not a schema property. (b) "Everything else is additive" is false: the two-way `kind` is not refinable from cues (see 1), and quotes→offsets is not additive either.
5. **Yes: `predicate.id` at annotation time, and the frame inventory** (see 3). Entity `type` is also marginal — linking will supersede it.
6. **Cut:** `scope` entirely (with the null convention above, it's safely deferrable — the asymmetry was the only argument against deferral), frames, predicate ids, entity types. **Keep:** polarity+cue, marker, attribution with a three-way `author|reported|denied` stance, claim-refs in object position, evidence with offsets. The negation channel and claim-to-claim structure are the measured signal; everything else is deferrable.

**5. What breaks first at scale.**

*10⁶ assertions, one Postgres:* the database is bored — 10⁶ rows is nothing. What breaks is **corroboration recall**: entities are document-local mention clusters (`e1`) with linking deferred, so the cross-document join key is effectively (surface-string, predicate-surface). exp73's 316→510 fragmentation recurs store-wide; scope overlap and duplicate detection fire ~never. Second: the query-time school→scope projection over the dispute graph is a recursive traversal recomputed per query — materialise it or it becomes the slow path for every corroboration question.

*Merging two such stores:* identity failure. Claim ids and entity ids are store-local — fine, namespace them — but (a) the two **closed frame inventories fork** (`f:keynesian` vs `f:keynesianism`) and nothing in any record carries a vocabulary version, so closed-vocab refs are unresolvable across stores; (b) `claim_relations` edges dangle — store A's `c2 disputes c1` cannot find store B's propositionally-identical claim because claims have **no content-addressable identity**. Fix now, it's cheap:

```sql
prop_key TEXT GENERATED ALWAYS AS
  (sha256(pred_norm || subj_link_or_surface || obj_canonical || polarity || marker)) STORED
-- merge: dispute edges re-hang on prop_key, not on store-local claim ids
```

Without this, the second store merge is a re-annotation project wearing a migration's clothes.


[stderr] 

Changes    +0 -0
Requests   1 Premium (1m 52s)
Tokens     ↑ 36.1k (36.1k written) • ↓ 7.4k (4.5k reasoning)
Resume     copilot --resume=e734a9f6-53c8-4900-a478-6ca1f7d14a16
