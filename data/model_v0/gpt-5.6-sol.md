1. **The fatal flaw: merge is not set union.** Only assertions are globally content-addressed. Predicates, attributions, and events are not federation-safe.

   Concrete corruption:

   - Store A defines predicate `status` as marital status.
   - Store B defines `status` as HTTP status.
   - Both assert `(local:x, status, "200", +, {})`.
   - The hashes match despite different meanings, and the predicate rows collide on primary key.

   Attribution merge is also non-idempotent: both stores begin with `id = 1`, and `UNIQUE (..., locator)` does not deduplicate rows where `locator IS NULL` because PostgreSQL treats NULLs as distinct.

   More seriously, lifecycle events target assertions rather than attributions. If Alice and Bob both attribute assertion A and Alice withdraws hers, the model can either withdraw A globally—incorrectly suppressing Bob—or leave Alice counted. It cannot represent the intended operation.

   Use globally stable predicate identities and make claim acts themselves immutable merge objects:

   ```sql
   CREATE TABLE predicate_version (
     uri           text NOT NULL,
     definition_hash bytea NOT NULL,
     definition    text NOT NULL,
     domain_sort   text NOT NULL,
     range_sort    text NOT NULL,
     PRIMARY KEY (uri, definition_hash)
   );

   CREATE TABLE claim_act (
     hash          bytea PRIMARY KEY,
     assertion     bytea NOT NULL REFERENCES assertion(hash),
     claimant      text NOT NULL,
     evidence_hash bytea NOT NULL,
     locator       text NOT NULL DEFAULT '',
     quoted_span   text NOT NULL,
     mode          text NOT NULL, -- asserts/reports/hypothesizes/predicts
     claim_time    timestamptz,
     confidence    numeric
   );

   CREATE TABLE claim_act_event (
     hash          bytea PRIMARY KEY,
     target        bytea NOT NULL REFERENCES claim_act(hash),
     kind          text NOT NULL,
     actor         text NOT NULL,
     replacement   bytea REFERENCES claim_act(hash),
     recorded_at   timestamptz NOT NULL
   );
   ```

   Local ingestion time and extractor identity should be separate observations, not part of source agreement. Otherwise two extractors reading one document become “two independent agents.”

2. **The closed query-operator set forces a change immediately, not within a year.** It cannot express anti-joins, projection, ordering, top-k, union, temporal overlap, or recursion explicitly. “Which three authors published the most papers after 2020?” requires projection, ordering, and limit. “Which entities have no attributed birth date?” requires `NOT EXISTS`, whose open-world semantics cannot be hidden inside `filter`.

   Fix it now: remove query operators from the frozen data grammar. Version the query IR like ordinary software.

   If “closed layer” means only persistent claim grammar, add a `proposition`/`assertion_ref` sort now. Claims about reports, predictions, retractions, and other claims will otherwise require reifying assertion hashes as fake entities.

3. **Delete the generic Datalog-style incremental derivation system.** At this size, inverse predicates are query rewrites, and occasional transitive predicates can use recursive SQL or predicate-specific materialized views. A generic algebra engine introduces truth-maintenance, cycle, provenance, and explosive-closure problems before any demonstrated workload requires it.

4. **The seven open questions**

   1. **Assertion/attribution split:** Right distinction; wrong merge claim. Assertions may be content-addressed, but predicate semantics, claim acts, evidence, and lifecycle objects must also have globally stable identities. Content equality is syntactic, not semantic: `1 m` and `100 cm`, or two local refs later resolved as identical, will not deduplicate.

   2. **Modality:** **Wrong.** Modality belongs on the claim act, not on the assertion or claimant. “Alice predicted P” and “Alice observed P” may share proposition P but are epistemically different acts. An agent property cannot express that distinction, and an assertion qualifier incorrectly changes the proposition hash.

   3. **Qualifiers:** Open qualifier vocabulary is right; unconstrained JSON is wrong. Qualifier predicates need typed ranges, cardinality, canonicalization rules, and temporal semantics. Functional-conflict detection based on byte-identical qualifier JSON silently misses overlapping intervals and semantically equivalent values.

      ```sql
      CREATE TABLE assertion_qualifier (
        assertion     bytea NOT NULL,
        predicate_uri text NOT NULL,
        value_sort    text NOT NULL,
        value_hash    bytea NOT NULL,
        value         jsonb NOT NULL,
        PRIMARY KEY (assertion, predicate_uri, value_hash)
      );
      ```

   4. **Identity:** Namespaced refs are right; unconditional `sameAs` equivalence closure is **wrong**. A defeasible edge cannot safely generate an equivalence relation: one low-quality edge can collapse two large components. Build policy-versioned identity hypotheses and retain mappings, rather than substituting canonical IDs:

      ```text
      identity_view(policy_v7, left, right, accepted, support, conflicts)
      ```

      Query-time closure is secondary; unsafe closure semantics break correctness first.

   5. **Layer 0 change:** The closed query IR already requires it. Fix now rather than migrate. For the data grammar, proposition-valued claims are the likely first migration; add them now.

   6. **First failure at 10⁶ claims:** Qualifier-sensitive conflict queries and attribution fan-out. There is no index supporting `(subject, predicate, canonical_qualifier_set)`, so functional-conflict detection repeatedly scans all values for popular subject/predicate pairs. JSON extraction and repeated event anti-joins compound it.

   7. **Derived edges:** Derive inverses by query rewriting. Do not eagerly derive general transitive closure: dense hierarchies and cycles can produce quadratic rows and complicated provenance. Materialize only measured, predicate-specific closures.

5. **What breaks first at scale**

   **One store, 10⁶ assertions:** not PostgreSQL itself. The first failure is the query shape:

   - functional conflict detection lacks a qualifier-set index;
   - JSONB values prevent efficient typed range and temporal-overlap queries;
   - “surviving” assertions require unresolved event semantics and repeated anti-joins;
   - attribution joins and `COUNT(DISTINCT agent)` dominate popular assertions;
   - a single pgvector index cannot generally cover multiple model dimensions without model-specific partial indexes.

   Add typed value columns or tables, a canonical `qualifier_set_hash`, and indexes such as:

   ```sql
   CREATE INDEX assertion_conflict_idx
     ON assertion (subject, predicate, qualifier_set_hash, polarity);

   CREATE INDEX claim_act_assertion_claimant_idx
     ON claim_act (assertion, claimant);
   ```

   **Merging two stores of that size:** volume is not the first problem. Merge fails on bare predicate IDs, colliding `bigserial` keys, nullable uniqueness, canonicalization-version drift, and assertion-wide withdrawal semantics. Make every federated object use a globally namespaced ID or canonical hash, include canonicalization/schema versions in the hash domain, and make repeated import provably idempotent. 1. The fatal flaw: merge is not set union. Only assertions are globally content-addressed.
Predicates, attributions, and events are not federation-safe.
 Concrete corruption:
 - Store A defines predicate status as marital status.
 - Store B defines status as HTTP status.
 - Both assert (local:x, status, "200", +, {}).
 - The hashes match despite different meanings, and the predicate rows collide on primary key.
 Attribution merge is also non-idempotent: both stores begin with id = 1, and UNIQUE (..., locator)
does not deduplicate rows where locator IS NULL because PostgreSQL treats NULLs as distinct.
 More seriously, lifecycle events target assertions rather than attributions. If Alice and Bob both
attribute assertion A and Alice withdraws hers, the model can either withdraw A globally—incorrectly
 suppressing Bob—or leave Alice counted. It cannot represent the intended operation.
 Use globally stable predicate identities and make claim acts themselves immutable merge objects:
 CREATE TABLE predicate_version (
   uri           text NOT NULL,
   definition_hash bytea NOT NULL,
   definition    text NOT NULL,
   domain_sort   text NOT NULL,
   range_sort    text NOT NULL,
   PRIMARY KEY (uri, definition_hash)
 );

 CREATE TABLE claim_act (
   hash          bytea PRIMARY KEY,
   assertion     bytea NOT NULL REFERENCES assertion(hash),
   claimant      text NOT NULL,
   evidence_hash bytea NOT NULL,
   locator       text NOT NULL DEFAULT '',
   quoted_span   text NOT NULL,
   mode          text NOT NULL, -- asserts/reports/hypothesizes/predicts
   claim_time    timestamptz,
   confidence    numeric
 );

 CREATE TABLE claim_act_event (
   hash          bytea PRIMARY KEY,
   target        bytea NOT NULL REFERENCES claim_act(hash),
   kind          text NOT NULL,
   actor         text NOT NULL,
   replacement   bytea REFERENCES claim_act(hash),
   recorded_at   timestamptz NOT NULL
 );
 Local ingestion time and extractor identity should be separate observations, not part of source
agreement. Otherwise two extractors reading one document become “two independent agents.”
 2. The closed query-operator set forces a change immediately, not within a year. It cannot express
anti-joins, projection, ordering, top-k, union, temporal overlap, or recursion explicitly. “Which
three authors published the most papers after 2020?” requires projection, ordering, and limit.
“Which entities have no attributed birth date?” requires NOT EXISTS, whose open-world semantics
cannot be hidden inside filter.
 Fix it now: remove query operators from the frozen data grammar. Version the query IR like ordinary
 software.
 If “closed layer” means only persistent claim grammar, add a proposition/assertion_ref sort now.
Claims about reports, predictions, retractions, and other claims will otherwise require reifying
assertion hashes as fake entities.
 3. Delete the generic Datalog-style incremental derivation system. At this size, inverse predicates
 are query rewrites, and occasional transitive predicates can use recursive SQL or
predicate-specific materialized views. A generic algebra engine introduces truth-maintenance, cycle,
 provenance, and explosive-closure problems before any demonstrated workload requires it.
 4. The seven open questions
 1. Assertion/attribution split: Right distinction; wrong merge claim. Assertions may be
content-addressed, but predicate semantics, claim acts, evidence, and lifecycle objects must also
have globally stable identities. Content equality is syntactic, not semantic: 1 m and 100 cm, or two
 local refs later resolved as identical, will not deduplicate.
 2. Modality: Wrong. Modality belongs on the claim act, not on the assertion or claimant. “Alice
predicted P” and “Alice observed P” may share proposition P but are epistemically different acts. An
 agent property cannot express that distinction, and an assertion qualifier incorrectly changes the
proposition hash.
 3. Qualifiers: Open qualifier vocabulary is right; unconstrained JSON is wrong. Qualifier
predicates need typed ranges, cardinality, canonicalization rules, and temporal semantics.
Functional-conflict detection based on byte-identical qualifier JSON silently misses overlapping
intervals and semantically equivalent values.
 CREATE TABLE assertion_qualifier (
   assertion     bytea NOT NULL,
   predicate_uri text NOT NULL,
   value_sort    text NOT NULL,
   value_hash    bytea NOT NULL,
   value         jsonb NOT NULL,
   PRIMARY KEY (assertion, predicate_uri, value_hash)
 );
 4. Identity: Namespaced refs are right; unconditional sameAs equivalence closure is wrong. A
defeasible edge cannot safely generate an equivalence relation: one low-quality edge can collapse
two large components. Build policy-versioned identity hypotheses and retain mappings, rather than
substituting canonical IDs:
 identity_view(policy_v7, left, right, accepted, support, conflicts)
 Query-time closure is secondary; unsafe closure semantics break correctness first.
 5. Layer 0 change: The closed query IR already requires it. Fix now rather than migrate. For the
data grammar, proposition-valued claims are the likely first migration; add them now.
 6. First failure at 10⁶ claims: Qualifier-sensitive conflict queries and attribution fan-out. There
 is no index supporting (subject, predicate, canonical_qualifier_set), so functional-conflict
detection repeatedly scans all values for popular subject/predicate pairs. JSON extraction and
repeated event anti-joins compound it.
 7. Derived edges: Derive inverses by query rewriting. Do not eagerly derive general transitive
closure: dense hierarchies and cycles can produce quadratic rows and complicated provenance.
Materialize only measured, predicate-specific closures.
 5. What breaks first at scale
 One store, 10⁶ assertions: not PostgreSQL itself. The first failure is the query shape:
 - functional conflict detection lacks a qualifier-set index;
 - JSONB values prevent efficient typed range and temporal-overlap queries;
 - “surviving” assertions require unresolved event semantics and repeated anti-joins;
 - attribution joins and COUNT(DISTINCT agent) dominate popular assertions;
 - a single pgvector index cannot generally cover multiple model dimensions without model-specific
partial indexes.
 Add typed value columns or tables, a canonical qualifier_set_hash, and indexes such as:
 CREATE INDEX assertion_conflict_idx
   ON assertion (subject, predicate, qualifier_set_hash, polarity);

 CREATE INDEX claim_act_assertion_claimant_idx
   ON claim_act (assertion, claimant);
 Merging two stores of that size: volume is not the first problem. Merge fails on bare predicate
IDs, colliding bigserial keys, nullable uniqueness, canonicalization-version drift, and
assertion-wide withdrawal semantics. Make every federated object use a globally namespaced ID or
canonical hash, include canonicalization/schema versions in the hash domain, and make repeated
import provably idempotent.


[stderr] 

Changes    +0 -0
Requests   0 Premium (1m 58s)
Tokens     ↑ 22.6k (22.6k written) • ↓ 5.1k (3.6k reasoning)
Resume     copilot --resume=f245a4f2-d87d-4e35-b534-31af4a5f0f99
