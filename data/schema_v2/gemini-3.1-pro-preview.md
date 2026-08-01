**1. The fatal flaw**
The schema claims to fix nested attribution and claims-about-claims in Section 2, but the JSON in Section 5 explicitly forbids it. The `object` field is restricted to `{"entity": "e2"} | {"literal": ...} | {"marker": "NONE"}`. You cannot put a claim ID in the object position. 

Furthermore, a flat `attribution` list cannot express nested reporting. For *"The Times reported that Smith denied X"*, applying both to the base claim `X` destroys the graph. Does the Times deny X? If you use `claim_relations` for "Smith denied X" (by making the denial a claim), you cannot attach the Times's reporting to that relation, because `claim_relations` cannot take attributions.

*Alternative:* Allow claims as objects, and make attribution recursive, not a list.
```jsonc
"object": {"claim": "c1"} // added to the union

"attribution": {
  "holder": "e3", 
  "kind": "reported", 
  "source": {"holder": "e4", "kind": "reported"} // recursive nesting
}
```

**2. What forces a change to the CLOSED layer within a year**
`under_assumption` as a closed frame reference (`"f:keynesian"`). You cannot pre-enumerate the world's theoretical assumptions, paradigms, or conditionals. New papers invent new assumptions. If it is closed, annotators will either drop precision by shoehorning into existing frames, or the vocabulary will require constant updates, breaking the "authored once" rule. Fix it now by making it an entity reference to the ontology, just like the subject and object.

**3. Where it is over-built**
Mechanical alignment of quotes for `cues` to replace character offsets. Discarding offsets in favor of `{"cue": "not"}` or `{"cue": "worked at"}` creates an impossible string-matching problem for the consumer. A 10,000-word document contains hundreds of instances of "not", "he", or "in". Re-aligning these to the text will hallucinate or fail silently on duplicate tokens. Delete the quotes for short cues and restore `[start, end]` token indices or byte offsets.

**4. The open questions in the final section**
1. **Wrong.** It destroys the investment. Anchoring to a string like `"cue": "not"` without an offset means the consumer cannot know *which* "not" in the document triggered the extraction. The ambiguity is moved to a fundamentally broken text-search step.
2. **Fails on lexical/morphological negation.** *"Bourdain was childless"* or *"Bourdain lacked children"*. Is "childless" the predicate, or does it trigger `marker: "NONE"`? Does "lacked" trigger `polarity: "-"` or is it just `polarity: "+"` with a surface cue of "lacked"?
3. **Wrong.** It needs attribution and scoping. If Smith says *"Theory A contradicts Theory B"*, the dispute itself is a claim held by Smith, not an objective universal relation. A flat list of relations bypasses the entire attribution architecture you just built for claims.
4. **Pronoun/Coreference resolution bounds.** If the text says *"He argued X"*, and the schema only captures the quote `"He"`, discarding offsets means you lose the deterministic link to the entity mention `e1` ("Anthony Bourdain") that the annotator saw. You are forcing the downstream consumer to re-run coreference resolution.
5. **Annotating `claim_relations` is too expensive.** It imposes an O(N^2) cognitive load. To find if `c10` disputes anything, the annotator must cross-check it against `c1` through `c9`.
6. **Cut `claim_relations`.** Extract the claims, polarities, and scopes accurately. Let downstream graph algorithms compute support/dispute edges by finding claims with identical predicates/objects but clashing polarities.
*(Note: Only 6 questions were provided in the document).*

**5. What breaks first at scale**
* **10^6 assertions on one Postgres instance:** Graph traversal queries. Asking "What does the Times actually believe?" requires walking through nested attributions, resolving `claim_relations`, and computing scope intersections over JSONB arrays. This will trigger massive table scans and choke the database. You will have to materialize the belief graph.
* **Merging two stores of that size:** Claim identity collapse. `c1` and `c2` are document-local IDs. Merging requires global claim resolution, not just entity resolution. If Store A and Store B both extracted *"Bourdain worked at Les Halles"*, deduplicating them means you must recursively rewrite every `claim_relations` edge and attribution array that pointed to the old discarded ID.


[stderr] 

Changes    +0 -0
Requests   1 Premium (38s)
Tokens     ↑ 21.9k (17.8k cached) • ↓ 1.1k (3.2k reasoning)
Resume     copilot --resume=93509a01-3b96-4d5f-87c0-bca46c81dec5
