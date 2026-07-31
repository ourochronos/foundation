## 1. **The fatal flaw**

Federation is already corrupt before proposition-key computation: `local:` identifiers have no store namespace.

```text
Store A: (local:owner, date_of_birth, 1970-01-01, +, {})
Store B: (local:owner, date_of_birth, 1980-01-01, +, {})
```

These are different people, but union treats them as one subject and reports a contradiction. If both dates matched, their assertions would falsely deduplicate. Claimants and predicate-local identifiers have the same problem.

The split repair also fails because `subject_is` targets an assertion rather than a claim act. Suppose a conflated record represents twins, both genuinely born in Paris:

```text
A = (local:x, born_in, Paris, +, {})

act_1: source S1 uses x for twin x1
act_2: source S2 uses x for twin x2
```

Both acts share assertion `A`. `(A, subject_is, x1)` rewrites the interpretation of both acts; assigning both `x1` and `x2` makes the assertion ambiguous rather than preserving what each source meant. Deduplication has erased the distinction that the repair needs.

There is also a direct predicate-version bug: predicate identity is `(uri, definition_hash)`, but assertions store only `predicate_uri`. Two definitions under one URI therefore become indistinguishable despite the text claiming otherwise.

Fix all three in the committed encoding:

```sql
entity_ref(namespace_uri, local_id)

predicate_ref(uri, definition_hash)

assertion(
    subject_ref,
    predicate_uri,
    predicate_definition_hash,
    object_value,
    polarity,
    scope
)

referent_resolution(
    claim_act_hash,
    argument_role,       -- subject, object, qualifier:place, ...
    original_entity_ref,
    resolved_entity_ref,
    resolution_act_hash
)
```

Every address also needs domain separation:

```text
address := (content_kind, schema_version, hash_algorithm, digest)
digest  := H(content_kind || schema_version || canonical_payload)
```

## 2. **What forces a change to the CLOSED layer within a year**

The closed `evidence` sum and singular evidence field will break first. Real personal-agent evidence will include conversation turns, tool results, user corrections, imported records, model executions, signatures, and several pieces of evidence for one act. `observation(channel, occurred_at)` cannot preserve enough information, while repeatedly expanding a closed union changes canonical encoding and hashes.

Fix it now:

```sql
evidence_record(
    evidence_hash,
    evidence_type_uri,
    encoding_version,
    canonical_payload
)

claim_act_evidence(
    claim_act_hash,
    evidence_hash,
    ordinal,
    role              -- support, derivation, contradiction, context
)
```

Make evidence types an open registry and commit claim acts to an ordered list of evidence references. Accepting a later migration would invalidate content addresses, so this is not safely deferrable.

## 3. **Where it is over-built**

Delete the append-only Merkle log. It does not establish the claimed property:

- A log over assertion hashes omits claim acts, retractions, accepted identity state, and disclosure policy.
- Two logs cannot be merged into one canonical root without rebuilding or defining another accumulator.
- Inclusion in a private store proves neither truth nor authorization.
- A raw content hash is binding but not hiding; low-entropy claims are dictionary-guessable.

Choose an epoch-based authenticated structure only after the proof statement is known. Also delete vocabulary-adoption gossip from the data model; explicit mappings and versioned seed packages are sufficient.

## 4. **The seven open questions**

1. **No.** The proposition key relocates the problem into policy-relative dynamic connectivity. There is no single closure when stores accept different `sameAs` acts. Negative `sameAs` also does not inherently “reverse” a positive edge.

   Derived results must be snapshot-scoped:

   ```sql
   identity_snapshot(snapshot_id, policy_hash, accepted_through)
   identity_member(snapshot_id, entity_ref, component_id)
   normalized_assertion(snapshot_id, assertion_hash, normalized_key)
   ```

   Never expose a representative-dependent proposition key as durable identity.

2. **Per-predicate is required.** A global overlap rule is wrong. Missing `valid_time` might mean unrestricted, unknown, or inapplicable depending on the predicate. `under_assumption` requires logical compatibility, not interval intersection. Each predicate version needs a conflict key and a versioned scope algebra.

3. **Two semantic sorts.** Use `assertion_ref` and `claim_act_ref`, possibly encoded as one tagged wire union. Retraction must reject assertion references; extraction fidelity should normally target acts; belief targets assertions. One untagged sort forfeits type checking.

4. **It does not hold.** Per-assertion reassignment is wrong because several acts can share one assertion while intending different referents. Resolution must target an act and argument position. Bulk rules can reduce curation volume, but exceptions remain inherently per-act.

5. **Conservative by default.** Universal identifiability computation is not tractable because it depends on an adversary’s external knowledge. K-anonymity alone is inadequate. Use approved release schemas, minimum cohort sizes, query budgets, differential privacy where appropriate, and refusal when background knowledge cannot be bounded.

6. **§9 is not enough; its commitment claim is wrong.** Content hashes are not hiding commitments. ZK aggregation additionally needs randomized commitments, authenticated epoch roots, key ownership, revocation semantics, circuit-compatible canonical values, nullifiers/replay protection, and an explicit leakage model. Hash agility does not retrofit these properties.

7. **Actual erasure is impossible.** A personal agent must support “forget this,” legal deletion, compromise recovery, and removal of mistakenly collected intimate data. Retraction leaves plaintext and guessable hashes forever. Use encrypted retention segments with erasable keys, tombstones outside the immutable proof history, and explicit retention classes.

## 5. **What breaks first at scale**

**At \(10^6\) assertions on one Postgres instance:** identity maintenance. Materializing pairwise closure is quadratic; joining two 100,000-member components can create \(10^{10}\) closure rows. Storing only union-find representatives avoids that cost but cannot efficiently handle rejected or retracted identity edges. Every component change also invalidates proposition keys and conflict indexes. Interval-overlap conflict joins become the next bottleneck unless scopes are typed columns with predicate-specific GiST indexes rather than generic qualifier payloads.

**Merging two \(10^6\)-assertion stores:** unscoped local identifiers corrupt data immediately. After namespacing is fixed, accepted cross-store identity edges trigger component reconstruction and mass renormalization. A single bridge between large components can invalidate hundreds of thousands of derived keys. The two ordered Merkle logs also have no canonical merge operation.

Store raw assertions append-only, but rebuild normalized views by identity snapshot. Partition normalization and conflict results by `snapshot_id` and predicate family; do not incrementally mutate one supposedly canonical global closure.1. The fatal flaw

Federation is already corrupt before proposition-key computation: local: identifiers have no store
namespace.

 Store A: (local:owner, date_of_birth, 1970-01-01, +, {})
 Store B: (local:owner, date_of_birth, 1980-01-01, +, {})

These are different people, but union treats them as one subject and reports a contradiction. If
both dates matched, their assertions would falsely deduplicate. Claimants and predicate-local
identifiers have the same problem.

The split repair also fails because subject_is targets an assertion rather than a claim act. Suppose
 a conflated record represents twins, both genuinely born in Paris:

 A = (local:x, born_in, Paris, +, {})

 act_1: source S1 uses x for twin x1
 act_2: source S2 uses x for twin x2

Both acts share assertion A. (A, subject_is, x1) rewrites the interpretation of both acts; assigning
 both x1 and x2 makes the assertion ambiguous rather than preserving what each source meant.
Deduplication has erased the distinction that the repair needs.

There is also a direct predicate-version bug: predicate identity is (uri, definition_hash), but
assertions store only predicate_uri. Two definitions under one URI therefore become
indistinguishable despite the text claiming otherwise.

Fix all three in the committed encoding:

 entity_ref(namespace_uri, local_id)

 predicate_ref(uri, definition_hash)

 assertion(
     subject_ref,
     predicate_uri,
     predicate_definition_hash,
     object_value,
     polarity,
     scope
 )

 referent_resolution(
     claim_act_hash,
     argument_role,       -- subject, object, qualifier:place, ...
     original_entity_ref,
     resolved_entity_ref,
     resolution_act_hash
 )

Every address also needs domain separation:

 address := (content_kind, schema_version, hash_algorithm, digest)
 digest  := H(content_kind || schema_version || canonical_payload)

2. What forces a change to the CLOSED layer within a year

The closed evidence sum and singular evidence field will break first. Real personal-agent evidence
will include conversation turns, tool results, user corrections, imported records, model executions,
 signatures, and several pieces of evidence for one act. observation(channel, occurred_at) cannot
preserve enough information, while repeatedly expanding a closed union changes canonical encoding
and hashes.

Fix it now:

 evidence_record(
     evidence_hash,
     evidence_type_uri,
     encoding_version,
     canonical_payload
 )

 claim_act_evidence(
     claim_act_hash,
     evidence_hash,
     ordinal,
     role              -- support, derivation, contradiction, context
 )

Make evidence types an open registry and commit claim acts to an ordered list of evidence
references. Accepting a later migration would invalidate content addresses, so this is not safely
deferrable.

3. Where it is over-built

Delete the append-only Merkle log. It does not establish the claimed property:

 - A log over assertion hashes omits claim acts, retractions, accepted identity state, and
disclosure policy.
 - Two logs cannot be merged into one canonical root without rebuilding or defining another
accumulator.
 - Inclusion in a private store proves neither truth nor authorization.
 - A raw content hash is binding but not hiding; low-entropy claims are dictionary-guessable.

Choose an epoch-based authenticated structure only after the proof statement is known. Also delete
vocabulary-adoption gossip from the data model; explicit mappings and versioned seed packages are
sufficient.

4. The seven open questions

 1. No. The proposition key relocates the problem into policy-relative dynamic connectivity. There
is no single closure when stores accept different sameAs acts. Negative sameAs also does not
inherently “reverse” a positive edge.
 Derived results must be snapshot-scoped:
 identity_snapshot(snapshot_id, policy_hash, accepted_through)
 identity_member(snapshot_id, entity_ref, component_id)
 normalized_assertion(snapshot_id, assertion_hash, normalized_key)
 Never expose a representative-dependent proposition key as durable identity.
 2. Per-predicate is required. A global overlap rule is wrong. Missing valid_time might mean
unrestricted, unknown, or inapplicable depending on the predicate. under_assumption requires logical
 compatibility, not interval intersection. Each predicate version needs a conflict key and a
versioned scope algebra.
 3. Two semantic sorts. Use assertion_ref and claim_act_ref, possibly encoded as one tagged wire
union. Retraction must reject assertion references; extraction fidelity should normally target acts;
 belief targets assertions. One untagged sort forfeits type checking.
 4. It does not hold. Per-assertion reassignment is wrong because several acts can share one
assertion while intending different referents. Resolution must target an act and argument position.
Bulk rules can reduce curation volume, but exceptions remain inherently per-act.
 5. Conservative by default. Universal identifiability computation is not tractable because it
depends on an adversary’s external knowledge. K-anonymity alone is inadequate. Use approved release
schemas, minimum cohort sizes, query budgets, differential privacy where appropriate, and refusal
when background knowledge cannot be bounded.
 6. §9 is not enough; its commitment claim is wrong. Content hashes are not hiding commitments. ZK
aggregation additionally needs randomized commitments, authenticated epoch roots, key ownership,
revocation semantics, circuit-compatible canonical values, nullifiers/replay protection, and an
explicit leakage model. Hash agility does not retrofit these properties.
 7. Actual erasure is impossible. A personal agent must support “forget this,” legal deletion,
compromise recovery, and removal of mistakenly collected intimate data. Retraction leaves plaintext
and guessable hashes forever. Use encrypted retention segments with erasable keys, tombstones
outside the immutable proof history, and explicit retention classes.

5. What breaks first at scale

At (10^6) assertions on one Postgres instance: identity maintenance. Materializing pairwise closure
is quadratic; joining two 100,000-member components can create (10^{10}) closure rows. Storing only
union-find representatives avoids that cost but cannot efficiently handle rejected or retracted
identity edges. Every component change also invalidates proposition keys and conflict indexes.
Interval-overlap conflict joins become the next bottleneck unless scopes are typed columns with
predicate-specific GiST indexes rather than generic qualifier payloads.

Merging two (10^6)-assertion stores: unscoped local identifiers corrupt data immediately. After
namespacing is fixed, accepted cross-store identity edges trigger component reconstruction and mass
renormalization. A single bridge between large components can invalidate hundreds of thousands of
derived keys. The two ordered Merkle logs also have no canonical merge operation.

Store raw assertions append-only, but rebuild normalized views by identity snapshot. Partition
normalization and conflict results by snapshot_id and predicate family; do not incrementally mutate
one supposedly canonical global closure.


[stderr] 

Changes    +0 -0
Requests   0 Premium (1m 19s)
Tokens     ↑ 23.4k (23.4k written) • ↓ 5.2k (3.8k reasoning)
Resume     copilot --resume=f5a37f3d-0e2d-454c-8eb6-a218cf798ffb
