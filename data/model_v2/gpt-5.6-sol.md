I’m tracing the claimed invariants through the schema and implementation, especially identity closure, event keys, commitments, and merge behavior.

/ Search (glob)
  │ "**/data/model_v1/**/*"
  └ 5 files found

/ Search (glob)
  │ "foundation/model/**/*"
  └ 8 files found

/ Search (glob)
  │ "**/*model*v2*.md"
  └ 1 file found

/ Search (grep)
  │ "prop_ref|event:|public_commit|SOME|NONE|overlap_op|claim_time" in *.py
  └ 6 files found

● Inspect repository files and status (shell)
  │ git --no-pager status --short && find . -maxdepth 3 -type f | sort | head -200
  └ 237 lines…

✗ Read 24-model-v1.md
  │ docs/24-model-v1.md
  └ Path does not exist

● Read conflict.py
  │ foundation/model/conflict.py
  └ 285 lines read

● Read identity.py
  │ foundation/model/identity.py
  └ 148 lines read

● Read test_canonical.py
  │ tests/test_canonical.py
  └ 414 lines read

● Read 25-model-v2.md
  │ docs/25-model-v2.md
  └ 162 lines read

● Read test_conflict.py
  │ tests/test_conflict.py
  └ 324 lines read

● Read canonical.py
  │ foundation/model/canonical.py
  └ 440 lines read

The central repair does not compose: proposition references are hashes with no semantic resolution path, while identity acceptance itself is merge-order-dependent. I’m reducing both to executable counterexamples and checking the scale path.The central repair does not compose: proposition references are hashes with no semantic resolution
path, while identity acceptance itself is merge-order-dependent. I’m reducing both to executable
counterexamples and checking the scale path.

✗ Execute semantic and merge counterexamples (shell)
  │ .venv/bin/python - <<'PY'
  │ from foundation.model.canonical import hexid
  │ from foundation.model.conflict import Claim, proposition_key, conflicts
  │ from foundation.model.identity import Closure
  │ ha=hexid('s.a:p1','date_of_birth','time',{'t':'1907-05-22','p':'day'})…
  └ Permission denied and could not request permission from user

/ Search (grep)
  │ "def merge|merge\(|claim_time|CREATE TABLE|postgres|Postgres|assertion" in *.py (foundation)
  └ 14 lines found

/ Search (glob)
  │ "docs/*model*.md"
  └ 3 files found

/ Search (grep)
  │ "claim_time|mode|qualifier registry|event_address|prop_ref" in *.md (docs)
  └ 9 lines found

● Read kb.py
  │ foundation/kb.py
  └ L1:220 (220 lines read)

/ Search (grep)
  │ "claim_time|mode|qualifier|Claim act|claim act|merge" (docs/23-model-v1.md)
  └ 191 lines found

/ Search (grep)
  │ "CREATE INDEX|_claims|UNIQUE|PRIMARY KEY" (foundation/kb.py)
  └ 86 lines found

/ Search (grep)
  │ "prop_ref|act_ref|event_address|resolve|fibre" in *.py (foundation/model)
  └ 9 lines found

1. **The fatal flaw**

`prop_ref` does not implement the promised proposition fibre. It stores an assertion hash, but identity closure operates on entity references, not hashes. If:

```text
Ha = hash(s.alice:p1, born_on, 1907-05-22)
Hb = hash(s.bob:p9,   born_on, 1907-05-22)
sameAs(s.alice:p1, s.bob:p9)
```

then the base proposition keys converge, but `prop_ref(Ha)` and `prop_ref(Hb)` remain different values. `proposition_key()` explicitly canonicalises only `entity` objects. There is no hash-to-assertion dereference or fibre resolver anywhere.

The confidence encoding is worse: `about` is not truth-conditional, so `proposition_key()` drops it. Consequently “belief 0.9 about Ha” and “belief 0.9 about an unrelated Hx” pool even without closure; differing belief values can conflict regardless of their targets.

Typed references are also not enforced. Addresses carry an algorithm tag but no visible content-kind tag, and `norm_address()` cannot determine whether an `act_ref` points to an act. The tests actually put an assertion address in an `act_ref`.

Use typed, dereferenceable references:

```sql
CREATE TABLE assertion (
    id              bytea PRIMARY KEY,
    predicate_id    bytea NOT NULL REFERENCES predicate_definition(id),
    subject_ref     text NOT NULL,
    object_json     jsonb NOT NULL,
    qualifiers_json jsonb NOT NULL
);

CREATE TABLE claim_act (
    id           bytea PRIMARY KEY,
    assertion_id bytea NOT NULL REFERENCES assertion(id),
    claimant_ref text NOT NULL,
    mode_id      text NOT NULL,
    claim_time   timestamptz
);

CREATE TABLE assessment (
    act_id              bytea PRIMARY KEY REFERENCES claim_act(id),
    target_assertion_id bytea NOT NULL REFERENCES assertion(id),
    dimension_id        text NOT NULL,
    value_json          jsonb NOT NULL
);
```

External identifiers should be typed, e.g. `assertion:sha256:...` and `act:sha256:...`. Resolve an assessment by dereferencing `target_assertion_id`, then computing that assertion’s current proposition key.

The proposed event identity directly violates the document’s root principle. Equal role bytes do not imply the same event:

```text
sale(seller=Alice, item=House, time=2020)
sale(seller=Alice, item=House, time=2020)
```

Two instalments, corrections, auctions, or legally distinct transactions collapse into one entity. Conversely, aliases in key roles produce different hashes for the same event because identity closure is not applied. Use occurrence IDs and treat role-derived fingerprints as matching evidence, not identity:

```sql
CREATE TABLE event_occurrence (
    id uuid PRIMARY KEY,
    minting_store uuid NOT NULL,
    event_type_id bytea NOT NULL
);

CREATE TABLE event_role (
    event_id uuid REFERENCES event_occurrence(id),
    role_definition_id bytea NOT NULL,
    value_json jsonb NOT NULL
);

CREATE TABLE event_match_candidate (
    left_event uuid,
    right_event uuid,
    method text,
    score numeric
);
```

2. **What forces a CLOSED-layer change within a year**

Incomplete and repeated events will force it. Real extraction routinely sees “Alice sold a house” without time or item, and routinely sees two events with the same alleged key. Refusing incomplete events loses ordinary personal-memory data; hashing a non-unique key corrupts identity.

Fix it now by separating immutable occurrence identity from semantic event matching. Otherwise every `event:` reference and every assertion about it must later be rewritten.

Negative existentials also need closure now: `(SOME, −)` and `(NONE, +)` are equivalent, but receive different addresses. Either reject negative polarity on existential markers or canonicalise both into one form.

3. **Where it is over-built**

Delete salted public commitments. There is no publication protocol, adversary model, key/salt custody system, or ZK proof format to support them. Salt destruction is not deletion if the assertion address remains available through references or logs; that unsalted address is still dictionary-attackable. Legal erasure also cannot be promised merely by deleting a salt.

Store encrypted private payloads and destroy per-record encryption keys when deletion is required. Add public commitments only when an actual transparency or proof protocol specifies what is published and retained.

4. **The seven open questions**

1. **Subsumption-blind conflict:** Wrong to defer as stated. Predicate definition identity, versioned lattice edges, and exact contradiction semantics must be specified now. Execution can remain Layer 4.
2. **Derived scope:** “Intersection” alone is wrong. Time can intersect; place may compose through containment; assumptions usually accumulate conjunctively; some predicates transform scope. Define composition per qualifier and derivation rule.
3. **Lattice cycles:** Rejecting all cycles is wrong. Collapse declared equivalence cycles into one SCC; reject cycles involving strict subsumption. Bounded traversal is not a correctness solution.
4. **Merge quarantine and conflict budgets:** Required before federation, not after. Quarantine must precede closure mutation and expose a deterministic proposed delta.
5. **Claim-act deduplication:** The stated problem is wrong. Identical content-addressed acts deduplicate during set union even with `claim_time`; independently performed acts should remain distinct. Do not deduplicate merely because assertion and claimant match.
6. **Open `mode` registry:** Wrong without namespaced, versioned definitions. Use stable mode-definition IDs and permit unknown modes as opaque values. Because mode enters act addresses, settle the encoding now.
7. **Qualifier registry:** “Unknown always overlaps” is correct only for conservative conflict detection. Unknown qualifiers must still distinguish propositions for agreement; currently they are dropped and unrelated scoped claims pool. Preserve them in proposition identity while treating overlap as unknown/possible.

5. **What breaks first at scale**

**At \(10^6\) assertions:** identity resolution fails first. `Closure.rep()` scans every known reference to find a representative on every call, making proposition-key generation effectively quadratic. Conflict detection then performs all pairs within each `(canonical subject, predicate)` group, also quadratic for hot groups. The implementation additionally loads claims and rebuilds indexes/identity state in Python rather than querying indexed PostgreSQL structures.

Materialise `entity_ref → component_id`, index proposition keys, and detect conflicts through indexed joins or predicate-specific constraints rather than pairwise Python loops.

**Merging two \(10^6\)-assertion stores:** raw hash insertion is manageable; interpretation is not. The same merged claim set can produce different identity closure depending on whether `sameAs` or `different_from` is processed first: `block()` does not split an already-fused class, while processing the block first prevents fusion. That makes federation non-convergent.

Build each closure version deterministically from the complete active identity claim set, with `different_from` constraints applied before component construction. Do not mutate a union-find incrementally as merge truth. After that, recompute only proposition keys and conflicts for affected components; a global two-million-row closure/conflict rebuild will otherwise dominate the merge. 1. The fatal flaw

prop_ref does not implement the promised proposition fibre. It stores an assertion hash, but
identity closure operates on entity references, not hashes. If:

 Ha = hash(s.alice:p1, born_on, 1907-05-22)
 Hb = hash(s.bob:p9,   born_on, 1907-05-22)
 sameAs(s.alice:p1, s.bob:p9)

then the base proposition keys converge, but prop_ref(Ha) and prop_ref(Hb) remain different values.
proposition_key() explicitly canonicalises only entity objects. There is no hash-to-assertion
dereference or fibre resolver anywhere.

The confidence encoding is worse: about is not truth-conditional, so proposition_key() drops it.
Consequently “belief 0.9 about Ha” and “belief 0.9 about an unrelated Hx” pool even without closure;
 differing belief values can conflict regardless of their targets.

Typed references are also not enforced. Addresses carry an algorithm tag but no visible content-kind
 tag, and norm_address() cannot determine whether an act_ref points to an act. The tests actually
put an assertion address in an act_ref.

Use typed, dereferenceable references:

 CREATE TABLE assertion (
     id              bytea PRIMARY KEY,
     predicate_id    bytea NOT NULL REFERENCES predicate_definition(id),
     subject_ref     text NOT NULL,
     object_json     jsonb NOT NULL,
     qualifiers_json jsonb NOT NULL
 );

 CREATE TABLE claim_act (
     id           bytea PRIMARY KEY,
     assertion_id bytea NOT NULL REFERENCES assertion(id),
     claimant_ref text NOT NULL,
     mode_id      text NOT NULL,
     claim_time   timestamptz
 );

 CREATE TABLE assessment (
     act_id              bytea PRIMARY KEY REFERENCES claim_act(id),
     target_assertion_id bytea NOT NULL REFERENCES assertion(id),
     dimension_id        text NOT NULL,
     value_json          jsonb NOT NULL
 );

External identifiers should be typed, e.g. assertion:sha256:... and act:sha256:.... Resolve an
assessment by dereferencing target_assertion_id, then computing that assertion’s current proposition
 key.

The proposed event identity directly violates the document’s root principle. Equal role bytes do not
 imply the same event:

 sale(seller=Alice, item=House, time=2020)
 sale(seller=Alice, item=House, time=2020)

Two instalments, corrections, auctions, or legally distinct transactions collapse into one entity.
Conversely, aliases in key roles produce different hashes for the same event because identity
closure is not applied. Use occurrence IDs and treat role-derived fingerprints as matching evidence,
 not identity:

 CREATE TABLE event_occurrence (
     id uuid PRIMARY KEY,
     minting_store uuid NOT NULL,
     event_type_id bytea NOT NULL
 );

 CREATE TABLE event_role (
     event_id uuid REFERENCES event_occurrence(id),
     role_definition_id bytea NOT NULL,
     value_json jsonb NOT NULL
 );

 CREATE TABLE event_match_candidate (
     left_event uuid,
     right_event uuid,
     method text,
     score numeric
 );

 2. What forces a CLOSED-layer change within a year

Incomplete and repeated events will force it. Real extraction routinely sees “Alice sold a house”
without time or item, and routinely sees two events with the same alleged key. Refusing incomplete
events loses ordinary personal-memory data; hashing a non-unique key corrupts identity.

Fix it now by separating immutable occurrence identity from semantic event matching. Otherwise every
 event: reference and every assertion about it must later be rewritten.

Negative existentials also need closure now: (SOME, −) and (NONE, +) are equivalent, but receive
different addresses. Either reject negative polarity on existential markers or canonicalise both
into one form.

 3. Where it is over-built

Delete salted public commitments. There is no publication protocol, adversary model, key/salt
custody system, or ZK proof format to support them. Salt destruction is not deletion if the
assertion address remains available through references or logs; that unsalted address is still
dictionary-attackable. Legal erasure also cannot be promised merely by deleting a salt.

Store encrypted private payloads and destroy per-record encryption keys when deletion is required.
Add public commitments only when an actual transparency or proof protocol specifies what is
published and retained.

 4. The seven open questions
 5. Subsumption-blind conflict: Wrong to defer as stated. Predicate definition identity, versioned
lattice edges, and exact contradiction semantics must be specified now. Execution can remain Layer
4.
 6. Derived scope: “Intersection” alone is wrong. Time can intersect; place may compose through
containment; assumptions usually accumulate conjunctively; some predicates transform scope. Define
composition per qualifier and derivation rule.
 7. Lattice cycles: Rejecting all cycles is wrong. Collapse declared equivalence cycles into one
SCC; reject cycles involving strict subsumption. Bounded traversal is not a correctness solution.
 8. Merge quarantine and conflict budgets: Required before federation, not after. Quarantine must
precede closure mutation and expose a deterministic proposed delta.
 9. Claim-act deduplication: The stated problem is wrong. Identical content-addressed acts
deduplicate during set union even with claim_time; independently performed acts should remain
distinct. Do not deduplicate merely because assertion and claimant match.
 10. Open mode registry: Wrong without namespaced, versioned definitions. Use stable mode-definition
 IDs and permit unknown modes as opaque values. Because mode enters act addresses, settle the
encoding now.
 11. Qualifier registry: “Unknown always overlaps” is correct only for conservative conflict
detection. Unknown qualifiers must still distinguish propositions for agreement; currently they are
dropped and unrelated scoped claims pool. Preserve them in proposition identity while treating
overlap as unknown/possible.
 12. What breaks first at scale

At (10^6) assertions: identity resolution fails first. Closure.rep() scans every known reference to
find a representative on every call, making proposition-key generation effectively quadratic.
Conflict detection then performs all pairs within each (canonical subject, predicate) group, also
quadratic for hot groups. The implementation additionally loads claims and rebuilds indexes/identity
 state in Python rather than querying indexed PostgreSQL structures.

Materialise entity_ref → component_id, index proposition keys, and detect conflicts through indexed
joins or predicate-specific constraints rather than pairwise Python loops.

Merging two (10^6)-assertion stores: raw hash insertion is manageable; interpretation is not. The
same merged claim set can produce different identity closure depending on whether sameAs or
different_from is processed first: block() does not split an already-fused class, while processing
the block first prevents fusion. That makes federation non-convergent.

Build each closure version deterministically from the complete active identity claim set, with
different_from constraints applied before component construction. Do not mutate a union-find
incrementally as merge truth. After that, recompute only proposition keys and conflicts for affected
 components; a global two-million-row closure/conflict rebuild will otherwise dominate the merge.


[stderr] 

Changes    +0 -0
Requests   0 Premium (2m 9s)
Tokens     ↑ 211.7k (148.2k cached, 63.5k written) • ↓ 6.0k (3.1k reasoning)
Resume     copilot --resume=afb0cccf-f1cf-442e-bfda-5fb47f3623ad
