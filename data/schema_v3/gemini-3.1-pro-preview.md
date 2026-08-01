1. **The fatal flaw**
The schema embeds `evidence` as a 1:1 key inside the claim object. Section 2 states that stored claims use content-addressing to allow cross-document targeting and merge deduplication. If `evidence` is included in the hash, identical claims from different documents yield different hashes, defeating deduplication entirely. If `evidence` is excluded from the hash, merging Store A (Doc 1) and Store B (Doc 2) creates a collision: two claims with the exact same ID but different `evidence` spans. The single `evidence` object forces the merge to either overwrite and silently drop one document's provenance, or fail.

*Alternative:*
Separate the platonic assertion from its document manifestation.
```jsonc
"assertions": [
  {"id": "hash123", "subject": {"entity": "e1"}, "predicate": "P937", "object": {"entity": "e2"}}
],
"mentions": [
  {"assertion": "hash123", "evidence": {"span": [0, 86]}, "scope": ...}
]
```

2. **What forces a change to the CLOSED layer**
The `scope` object. It hardcodes `valid_time` and `under_assumption`. Within a year, you will need geographic scope ("in the UK") and demographic/contextual scope ("in mice", "in phase III trials"). These are not "assumptions", they are physical or bounding contexts. Fix it now by making `scope` an open list of typed qualifiers: `scope: [{"dimension": "spatial", "entity": "e_uk"}]`.

3. **Where it is over-built**
`marker: "NONE" | "SOME"` in the `object` field. The distinction between "x does not have children" (`polarity: "-"`) and "x has 0 children" (`marker: "NONE"`) is pedantic noise that downstream queries will be forced to collapse anyway. Delete `marker` outright and use polarity with an entity, or a literal quantity.

4. **The seven open questions in the final section**
*(Note: There are only 5 questions in your text. Here are the answers to them.)*
1. **Wrong.** Reification closes nesting but destroys provenance. A reified claim points to a content-address, which strips the `evidence` span, making it impossible to know *which* instance of the claim Smith denied without complex graph traversals.
2. **Wrong.** The procedure only checks if the *object* is quantified to nothing. It silently fails on subject quantification: "Nobody passed the test." The schema has no way to express a `NONE` marker on the subject.
3. Spatial, geographic, and demographic contexts. Without them, you will merge "Minimum wage increases unemployment [in rigid labor markets]" with generic assertions, forcing a complete re-annotation.
4. **Wrong.** The three-value set conflates probability with conditionality. "It is highly unlikely to work" is an *assertion* of low probability, not a "hedge". "If X, then Y" is conditional, not "hypothetical".
5. Yes. `predicate.span`. Annotators/models spending cycles isolating the exact surface string for a relation that is already bound to a canonical ID (`P937`) adds zero analytical value. Drop `predicate.span`.
*(6 & 7: Do not exist in the document).*

5. **What breaks first at scale**
* **10^6 assertions on one Postgres instance:** Queries for reified claims. Extracting "who denied X" requires recursive CTEs or self-joins on `subject = ... AND object.claim_id = ...`. At a million rows, arbitrary depth self-joins without a dedicated graph index will trigger massive table scans and timeout.
* **Merging two stores of that size:** Graph validation deadlocks. Content addresses for reified claims (`c3` hashes `c2`, which hashes `c1`) require topological sorting to validate and insert. A million-row merge with cross-store references will thrash memory attempting to resolve deep acyclic dependency chains before it can write the first root claim.


[stderr] 

Changes    +0 -0
Requests   1 Premium (37s)
Tokens     ↑ 21.5k (17.7k cached) • ↓ 899 (3.1k reasoning)
Resume     copilot --resume=e83c6168-ddf3-408d-99e7-55e8d98f409d
