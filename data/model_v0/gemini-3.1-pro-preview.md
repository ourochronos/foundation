**1. The fatal flaw**
The CRDT set-union breaks completely on locally-minted entities due to isomorphic subgraph duplication. By baking the subject string into the immutable hash, you lock arbitrary local IDs into the assertion identity.

Example:
Store A extracts: `A1 = (local:event_9, date, 2026-10-01)`.
Store B extracts: `B1 = (local:x42, date, 2026-10-01)`.
They merge. Hashes differ. Set union keeps both. Later, someone asserts `(local:event_9, sameAs, local:x42)`. The hashes *still* differ. The `COUNT(DISTINCT agent)` for the date is 1 for A1 and 1 for B1. Your agreement counting silently fails, and attributions for the exact same conceptual fact do not pool.

*Alternative:* Identity resolution cannot just be a view; it must rewrite or alias hashes at the attribution counting layer, or attributions must link to the `sameAs` closure rather than the raw assertion hash. 

**2. What forces a change to the CLOSED layer within a year**
Higher-order claims. You will need to make an assertion about another assertion (e.g., "Assertion X caused Assertion Y", or "Assertion X is an outlier"). The closed list of object sorts (`entity | text | quantity | time`) cannot express this. 

Fix it now. Add `assertion_hash` to the Sorts enum. 

**3. Where it is over-built**
Delete `assertion_event` entirely. 

An assertion is an immutable Platonic fact; it cannot be "withdrawn" or "superseded". An *agent* withdraws or supersedes their *attribution* of that fact. "Disputed" is already computed at query time via polarity or functional conflicts, making the event redundant.

*Schema alternative:*
```sql
ALTER TABLE attribution ADD COLUMN superseded_by_attribution bigint REFERENCES attribution(id);
-- A withdrawal is just superseding with NULL. 
```

**4. The seven open questions**

1. **Assertion/attribution split:** Wrong for locally-generated entity IDs (see Fatal Flaw). It only works for globally agreed-upon namespaces (like Wikidata). 
2. **Modality:** Wrong to omit. If Alice claims "X might be Y" and Bob claims "X is Y", putting "might" in qualifiers changes the assertion hash, fracturing the claim space. Modality belongs on the `attribution`, not the `assertion`.
3. **Qualifiers:** Right cut, but the sorting/canonicalization requirement for JSONB will break deduplication the moment a schema evolves or a nested array is introduced. 
4. **Namespaced entity refs + sameAs:** Wrong. Query-time closure becomes the bottleneck. You cannot do a recursive CTE across millions of `sameAs` links on every read. It must be materialized asynchronously.
5. **What forces a Layer 0 change:** The inability to point to an `assertion` as an object (higher-order claims), and the lack of a `boolean` or `list` sort.
6. **10⁶ claims on Postgres:** Recursive `sameAs` traversals will time out the query path before you hit Postgres's IO limits. 
7. **Deriving transitive/inverse edges:** Wrong. Deriving a deep transitive closure (e.g., `part_of` or `located_in` across geography) in Datalog/SQL at query time on a 1M row table will result in multi-second latencies. You must store (materialize) them in Layer 4.

**5. What breaks first at scale**
*At 10⁶ assertions on one instance:* The JSONB index. Extracting and casting `(object->>'v')` dynamically for range queries on quantities or times requires a functional index for every type of value. The single JSONB column will force sequential scans for complex quantity/time bounds.
*Alternative:* Split the object column by sort: `object_entity text`, `object_text text`, `object_time tstzrange`, `object_quantity float8`.

*Merging two stores of 10⁶:* Canonicalization desync. If Store A's JSON parser orders `{a: 1, b: 2}` and normalizes floats as `1.0`, while Store B normalizes as `1`, their SHA256 hashes diverge. You will get massive silent duplication of assertions. You cannot rely on application-layer JSON normalization across federated instances written in different languages.


[stderr] 

Changes    +0 -0
Requests   1 Premium (36s)
Tokens     ↑ 22.9k • ↓ 991 (2.4k reasoning)
Resume     copilot --resume=ca27ebc9-b0f4-4d57-b591-64dac691d010
