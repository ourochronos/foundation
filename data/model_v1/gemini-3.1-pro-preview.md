1. **The fatal flaw**
Truth-conditional qualifiers and polarity inside the `assertion` hash permanently fracture the identity of the proposition, destroying zero-knowledge aggregation and deduplication at Layer 0. 
Because continuous variables (time, space) alter the hash, identical beliefs expressed with slight variations create disjoint assertion graphs.
*Example:* 
Alice asserts: `(Bob, located_in, Paris, +, {time: "12:00-13:00"})` → Hash A
Charlie asserts: `(Bob, located_in, Paris, +, {time: "12:15-13:15"})` → Hash B
Because Hash A != Hash B, a ZK circuit cannot aggregate "confidence that Bob is in Paris" by simply summing claims pointing to a single hash. The aggregator must reveal the plaintext of A and B to discover they overlap. Furthermore, if polarity is in the hash, the proposition `(Bob, located_in, Paris, +)` and its contradiction `(Bob, located_in, Paris, -)` have no cryptographic link.
*The fix:* The assertion must be the pure semantic triad.
`assertion := (subject, predicate_uri, object)`
`claim_act := (assertion_hash, claimant, polarity, truth_conditional_qualifiers, evidence, mode, claim_time)`

2. **What forces a change to the CLOSED layer**
The `mode` enum in Layer 0. The stated goal of the system is to be "a sovereign knowledge base holding preferences, motivations and interaction history." Yet the closed `mode` enum (`asserts | reports | observes | infers | predicts | hypothesises`) only describes epistemic states of *fact*. It cannot express intent, desire, or preference. "I want to visit Paris" cannot be modelled without lying about the mode.
*Fix now:* Either open the enum to URIs, or add `prefers`, `intends`, and `queries`.

3. **Where it is over-built**
The per-assertion `subject_is` reassignment mechanism for entity splits (§6). Delete it outright.
If `local:x` splits into `x1` and `x2`, and 100,000 assertions referenced `local:x`, your model requires minting 100,000 new `claim_act` rows of `(A_i, subject_is, local:x1, +, {})` to fix the graph. Nobody will ever do this; it is an O(N) write-amplification masquerading as an append-only log. Entity splits must be handled in Layer 4 via set-based policy rules (e.g., "All claims about `local:x` from claimant C map to `x1`"), not by re-wiring individual assertions.

4. **The seven open questions**
*   **1. Proposition key vs closure maintenance:** It relocates the problem. Layer 4 now has to constantly compute overlap graphs on continuous variables to maintain equivalence classes, which is O(N²) worst-case churn on every new edge.
*   **2. Registered set vs per-predicate overlap:** Wrong. Overlap semantics must be per-predicate. Spatial overlap for `owns_land` means conflict (if exclusively owned); spatial overlap for `travelled_through` does not. You cannot register generic overlap rules independent of the predicate.
*   **3. One sort or two for `claim_ref`:** Two. You must strictly type them. Disputing a fact targets the `assertion_hash`. Disputing an extraction (e.g., "the OCR failed") targets the `claim_act_hash`. Fusing them destroys the type signature of higher-order predicates.
*   **4. Conflates / subject_is split mechanism:** Wrong. It requires impossible per-claim reassignment volume. (See §3).
*   **5. Tractable identifiability computation:** Needs to be conservative-by-default. Dynamic k-anonymity over sparse graph queries is NP-hard. Use static allow-lists or static release templates; you cannot compute safety at query time.
*   **6. What is still missing for ZK:** ZK circuits require fixed-size inputs. A variably-sized `truth_conditional_qualifiers` object inside the assertion makes it impossible to build a static constraint circuit for conflict detection.
*   **7. What is impossible for an agent:** Expressing goals and user desires. The closed grammar makes personal preferences impossible to distinguish from factual beliefs.

5. **What breaks first at scale**
*   **10^6 assertions on one Postgres instance:** Layer 4 incremental closure maintenance. Inserting a single high-centrality `sameAs` claim will trigger a cascading update of materialized Proposition Keys that locks rows and stalls the write path.
*   **Merging two stores of that size:** Network/Memory exhaustion from propagating redundant assertion hashes. Because slight timestamp variations in truth-conditional qualifiers yield entirely unique assertion hashes, the stores will gossip millions of mathematically distinct but semantically identical records before Layer 4 can even attempt to deduplicate them.


[stderr] 

Changes    +0 -0
Requests   1 Premium (47s)
Tokens     ↑ 23.6k • ↓ 1.1k (3.7k reasoning)
Resume     copilot --resume=fdc187d1-263b-42cf-bdcd-ece59a6210b3
