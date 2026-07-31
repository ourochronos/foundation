1. **The fatal flaw**
N-ary event identity derived from a subset of roles makes disagreements invisible. If an event's identity is `H(role1 ‖ role2)`, then a disagreement on `role2` produces two completely different event entities rather than a conflict on one entity. 
**Concrete example:** Event type `Sale` defines identifying roles `seller`, `buyer`, and `item`. 
Alice asserts: `Sale(seller: Alice, buyer: Bob, item: House)` → hashes to `Event_A`.
Charlie asserts: `Sale(seller: Alice, buyer: Charlie, item: House)` → hashes to `Event_B`.
Because they disagree on the buyer, they are talking about two different content addresses. The system silently accepts both as separate events instead of flagging a conflict that the same house was sold by the same person at the same time to two different buyers. 
**Alternative:** Event IDs must be random/unguessable (UUIDs or sequential), and all roles are standard functional claims against that ID:
`E1 = uuid()`
`(E1, type, Sale, +)`
`(E1, seller, Alice, +)`
`(E1, buyer, Bob, +)`
Conflicts are then caught by standard functional predicate rules if `E1` and `E2` are later fused, or via separate uniqueness constraints (e.g., `item` can only be sold once at `time`).

2. **What forces a change to the CLOSED layer**
**Salted commitments break federated consensus.** If `public_commit = H(salt ‖ content_addr)`, then Alice and Bob independently making the exact same claim will generate different salts, and therefore different `public_commit` hashes. They will never deduplicate or join in the public layer. If they share the salt to fix this, then salt destruction (deletion) is impossible because you cannot cryptographically guarantee Bob deleted his copy of the salt. You must fix this now by deleting salted commitments from Layer 0. True cryptographic deletion on an append-only log is a myth; handle privacy via transport/storage ACLs and handle legal erasure via explicit `Tombstone` acts.

3. **Where it is over-built**
**The `act_ref` vs `prop_ref` distinction in the storage schema.** The document explicitly admits that both are stored as syntactic addresses and the mutability "lives in the reading." If they are structurally identical at rest (just a hash pointing to a record), bifurcating them into two distinct types at Layer 0 is redundant. Delete the distinction in the schema. Store a single `Ref(hash)`. Whether a query resolves it strictly (for retraction) or traverses the identity closure (for belief) is a query-time execution mode, not a static storage type. 

4. **The seven open questions**
*   **Conflict detection is subsumption-blind:** **Wrong.** If Layer 0 accepts `(X, mother_of, Y, +)` and `(X, parent_of, Y, -)`, the state is already corrupted. Subsumption must be enforced at the write-gate, or your database is functionally incoherent to other consumers.
*   **Derived scope:** Must be the intersection of its components. If step A is valid [t1, t3] and step B is valid [t2, t4], the composition is valid [t2, t3].
*   **Lattice cycles:** Reject at registration. Bounding at query time introduces non-deterministic query results depending on arbitrary depth limits.
*   **Merge quarantine and conflict budgets:** Accept immediately. Without per-class conflict budgets, a malicious peer can DoS a node by flooding it with unresolvable conflicts.
*   **Claim acts never deduplicate:** **Wrong.** Remove `claim_time` from the act identity hash. Time is metadata of the *receipt* or *sync*, not the act's canonical identity. If Alice asserts X twice, it is one assertion.
*   **`mode` as an open registry:** **Wrong.** Modes (belief, intent, retraction) govern foundational processing rules. If open, two federated instances will use different modes for the same semantic, breaking federation. Closed enum only.
*   **Qualifier registry (unknown defaults to overlap):** Correct. Failing open to overlap ensures conflicts are aggressively flagged rather than silently creating parallel, non-conflicting realities.

5. **What breaks first at scale**
*   **10^6 assertions on one Postgres instance:** The `prop_ref` closure. Resolving "the whole proposition fibre containing it" requires a recursive CTE (graph traversal) over the identity lattice. Executing this recursion on every read and every insertion's conflict-check will table-scan and timeout well before 1 million rows.
*   **Merging two 10^6 stores:** Claim act explosion. Because `claim_time` prevents deduplication (as noted in question 5), merging two stores that have partially synced before will duplicate every act that took a different network path or was recorded with a millisecond variance. 1M + 1M will yield 3M acts, scaling geometrically until OOM.


[stderr] 

Changes    +0 -0
Requests   1 Premium (49s)
Tokens     ↑ 21.8k • ↓ 1.1k (3.9k reasoning)
Resume     copilot --resume=b995f111-dbd7-426e-b828-3dcc839f550b
