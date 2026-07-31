## 1. The fatal flaw

**The commitment layer inherits the exact flaw §1 claims to fix, plus a new one: content-address commitments are binding but not hiding.**

§9 says "content addresses are already commitments." Two problems, one per property a ZK commitment needs:

- **Semantic identity relocated, again.** ZK aggregation must prove things like "N stores agree that P." But agreement lives on the *proposition key* (Layer 4, store-local, dependent on each store's acceptance policy for `sameAs`), while commitments and the Merkle log are over the *assertion hash* (syntactic, `local:` refs baked in). Store A commits to `(local:a1, dob, 1907-05-22)`, Store B to `(local:b9, dob, 1907-05-22)`. No circuit can prove they agree without one store revealing its closure — which is private identity-resolution data. The v0 flaw (syntactic sold as semantic) has been repaired in the conflict detector and relocated verbatim into §9, which the document treats as settled.
- **Deterministic hashes of low-entropy claims are dictionary-attackable.** A personal KB's claims are drawn from tiny spaces: `(local:me, has_condition, wikidata:Q12206, +)` — enumerate the ICD codes, hash each with the canonical seeds' shared URIs (which §7 explicitly maximizes!), match against the published Merkle log. Selective disclosure leaks everything popular. Shared vocabulary and unsalted commitments are directly at war; the doc pushes both.

Fix, concretely — split content address from public commitment:

```
content_addr  = (algo, H(canonical_bytes))          -- private; dedup & merge key
public_commit = (algo, H(salt ‖ prop_key_bytes))    -- salted, over the SEMANTIC key,
                                                    -- Merkle log built on THIS
salt stored privately per assertion; revealed selectively in proofs
```

Also a claim-shape it cannot express: **existential negation**. "Alice has no children" ≠ `(alice, has_child, bob, −)`. Polarity negates a triple; there is no way to say no object exists. A personal KB needs "no allergies," "no dietary restrictions" on day one. Add a per-sort `NONE` marker with the conflict rule `(s,p,NONE,+)` conflicts with any `(s,p,o,+)` of overlapping scope.

## 2. What breaks the CLOSED layer within a year

**The truth-conditional qualifier registry — and the document breaks it itself, before shipping.** §1 registers `{valid_time, valid_place, under_assumption}`. §2's own examples then use `by_lights_of` and `in_domain` as qualifiers. Either they're truth-conditional (they are — reliability *in biography* is a different proposition from reliability *in chemistry*) and the closed set is already too small, or they're annotations and `(source_X, reliability, 0.40)` in one domain contradicts the value in another via `functional`. Qualifiers enter the hash, so extending the set is a Layer-0 event.

Fix now, same move as sorts: qualifiers become an open registry with a closed contract — each registration ships `(uri, value_sort, canonical_encoding, overlap_op)`:

```sql
CREATE TABLE qualifier_def (
  uri text, definition_hash bytea,
  value_sort text NOT NULL,
  overlap_op text NOT NULL,   -- 'interval_intersects' | 'equals' | ...
  PRIMARY KEY (uri, definition_hash));
```

Critical default: an *unregistered* qualifier must be treated as **always overlapping** in conflict detection. If unknown defaults to disjoint, any agent makes its claims undisputable by attaching one junk qualifier — v0's exact bug, reintroduced through the side door.

Second break, accept the migration: the frozen **byte** canonicalisation. Poseidon hashes field elements, not bytes; adopting it requires a second frozen encoding (bytes→field elements) that §7 doesn't specify and the conformance vector doesn't test. `(algo_id, digest)` labels the fork; it does not prevent it — every `claim_ref`, confidence claim, and Merkle leaf targeting a SHA-256 address must be bridged when the algo changes. Ship the byte layer now, write the field-encoding spec into the conformance vector now, accept that the Merkle log gets rebuilt.

## 3. Over-built — delete these

- **§7 emergence-by-adoption gossip.** Predicate-usage gossip, adoption weighting, seed-candidacy pipeline — for a federation that will have single-digit instances for years. The doc itself admits it's an unsolved social process. Seeds + alignment-claims capture the value; the gossip machinery is speculative infrastructure. Delete.
- **§9(c) Merkle log, now.** It will be rebuilt when the algebraic hash and salted commitments arrive (see §1 above), so building it over unsalted SHA-256 leaves buys nothing and creates a leaking artifact. Defer; it's genuinely reversible, which by the document's own rule means it shouldn't be decided now.
- **The six-value `mode` enum's finer half.** `infers` vs `hypothesises` vs `predicts` will never be assigned consistently by extractors. Make mode a URI (open registry), seed three values, or the closed enum becomes CLOSED-layer break #3.

## 4. The seven questions

1. **It relocates the problem, and only half-fixes it.** Within one store: yes, workable, *if* conflicts are derived views keyed `(closure_version, prop_key)` and never stored as facts — retracting one `sameAs` must invalidate them for free. Across stores: **wrong** to imply agreement is comparable — proposition keys are functions of each store's acceptance policy, so "agreement of 3" is store-relative. See flaw #1.
2. **Per-qualifier, not per-predicate.** Overlap is a property of the qualifier's value space (intervals intersect the same way under any predicate). Per-predicate overlap is wrong and would make registration combinatorial. Declare `overlap_op` at qualifier registration; done.
3. **Two sorts.** Retraction targets acts, confidence targets assertions, and they have disjoint referent spaces; one sort means every consumer runtime-dispatches and a mis-typed ref silently changes meaning instead of failing. It's in the closed layer — one sort now becomes migration later. Two, now.
4. **Doesn't hold up: `subject_is` is half a mechanism.** Real case: conflated author, 200 assertions, 40 with the entity in *object* position (`(paper_9, authored_by, local:x)`) and some in qualifier values. No reassignment path exists for those. Add `object_is` (and qualifier-value reassignment) or the split leaves the object-position claims permanently ambiguous with no way to even mark them. The volume worry is backwards — real splits involve dozens of claims and per-claim reassignment is exactly what a curator does; the ambiguous-by-default behaviour carries the rest.
5. **Conservative-by-default; and the k-anonymity framing is wrong.** For a single-subject sovereign store, k-anonymity is a category error — there is no cohort; the release is already linked to the person by the fact of the request. What §8 actually needs is sensitivity × purpose × audience policy plus an explicit model of what the audience already knows (inference-attack budget), which is intractable in general — so refuse-by-default with allowlisted release shapes. Set-composition matters for the *aggregator*, not the sovereign store.
6. Missing: (a) hiding — salted commitments (flaw #1); (b) the field-element encoding spec; (c) semantic (proposition-level) commitments so cross-store agreement is provable; (d) **revocation** — a Merkle log proves membership; proving a claim was *retracted* needs the log to commit to act-level supersession too, or every proof is stale-able.
7. **Deletion.** Append-only + content-addressed + Merkle-logged makes destruction impossible, and a person's agent needs it: recorded facts about *third parties*, coerced entries, legal erasure. Payload/commitment separation (store hashes in the log, encrypted payloads addressable and destroyable) must be Layer 0 or it never happens. Also: comparative preference ("prefers A over B") has no natural shape in binary triples — needs a seeded n-ary/event pattern before the personal corpus arrives.

## 5. What breaks first at scale

**10^6 assertions, one Postgres:** not storage — 10^6 is small. Two things break: (a) **meta-claim fanout** — §2 turns every act into 2–5 more assertions (fidelity, belief, reliability…), each with its own act; 10^6 facts is 4–6×10^6 rows before content, and reliability lookups become recursive graph walks inside every policy/ranking query. (b) **Overlap-based conflict detection** — equality-based conflict is a unique index; overlap is a range join. Within a fused equivalence class (one bad `sameAs` on a hub entity — the doc's own scenario), it's pairwise per functional predicate: O(n²) in class size, and retracting the `sameAs` forces full recompute of the class. Mandatory mitigations: `tstzrange` + GiST exclusion per (prop_subject, predicate) for functional predicates, and conflicts as an incrementally-maintained materialized view.

**Merging two 10^6 stores:** acts never dedupe (`claim_time` is in the hash), so acts and their meta-claim trees strictly double. The real break is **acceptance-policy evaluation × closure reconciliation**: 10^6 foreign claims each needing a policy decision that consults reliability-claims (graph traversal per row), then the union of two `sameAs` sets — accepted under *different* policies — fuses classes neither store had, triggering proposition-key recompute and the spurious-dispute flood §1 warns about, at merge scale rather than one-bad-edge scale. Design the merge as staged: import to a quarantine partition, batch-evaluate policy with a materialized reliability snapshot, apply `sameAs` deltas class-by-class with a per-class conflict budget that quarantines (not accepts) any class whose dispute count spikes. That budget mechanism doesn't exist in the document and is the first thing the merge path actually needs.


[stderr] 

Changes    +0 -0
Requests   1 Premium (2m 27s)
Tokens     ↑ 38.7k (38.7k written) • ↓ 9.4k (5.9k reasoning)
Resume     copilot --resume=464a7184-5203-47b3-bde1-68b34849ff9a
