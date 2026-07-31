● Inspect repo layout (shell)
  │ ls /home/zonk1024/projects/foundation; ls /home/zonk1024/projects/foundation/model 2>/dev/null |
  │ head; find /home/zonk1024/projects/foundation -maxdepth 2 -name "*.py" | head -30
  └ 57 lines…

● List model package (shell)
  │ ls /home/zonk1024/projects/foundation/foundation/model/ 2>/dev/null; wc -l
  │ /home/zonk1024/projects/foundation/foundation/model/*.py 2>/dev/null
  └ 13 lines…

● Read canonical.py
  │ foundation/model/canonical.py
  └ 440 lines read

● Read conflict.py
  │ foundation/model/conflict.py
  └ 328 lines read

● Read identity.py
  │ foundation/model/identity.py
  └ 148 lines read

● Read predicates.py
  │ foundation/model/predicates.py
  └ 118 lines read

**1. The fatal flaw: event identity re-imports the two bugs the document says it fixed.**

`event_address()` hashes `norm_text(event_type)` — a bare, unversioned string. §4 exists because "two definitions under one uri were indistinguishable"; the event type is a uri with a definition (its role schema and its identifying-role set) and gets no `definition_address`. Worse, the identifying-role *set* is a caller parameter, not part of the address. Concretely:

- Store A's `sale` type declares identifying = {seller, item, buyer}. Store B's declares {seller, item, buyer, time}. Same fact, different ids. Federation fails on every n-ary fact — the exact v1 failure §3 claims to close, relocated from "reification shape" into "type declaration," which the document treats as unproblematic.
- With time *out* of the key: Alice sells the house to Bob in 2015, buys it back, sells it to him again in 2020 → **one event id, two facts fused**. The 2015 and 2020 prices attach as claims about one entity and surface as a spurious functional conflict. That is merge-corrupting data, not merely missing dedup.
- With time *in* the key: extractor A recovers `("2020","year")`, extractor B `("2020-06-15","day")` → `canon_value` yields different bytes → different ids for the same sale. The refusal rule then means most real extractions either get refused or mint singleton identities.

Second silent failure, in the shipped code: §1 promises "belief 0.9 here and 0.2 there" becomes a *detected* conflict about one proposition. It doesn't. `proposition_key` routes `prop_ref` through `canon_value` → raw address; `closure.canonicalise` applies only to entity refs. Belief on `prop_ref(Ha)` and belief on `prop_ref(Hb)` (same fibre) group under different keys and never meet. The v1 flaw "higher-order claims on the syntactic hash" is fixed for *resolution* and unfixed for *conflict and agreement over the higher-order claims themselves*.

Third: `(alice, parent_of, NONE, +)` vs `(alice, mother_of, carol, +)`. Flat contradiction. `conflicts()` groups by literal predicate; `_subsumption_conflicts` requires one *negative* claim. Both positive → silently missed. The existential construct and the lattice don't compose, and this is exactly the claim class §2 says the construct exists for.

**2. What forces a CLOSED-layer change: the event address preimage.** Within a year someone adds a role to an event type's identifying set (to fix the recurring-sale fusion above) and every circulating `event:` id — baked into assertion content addresses — is orphaned. Fix now; it's the same fix §4 already made for predicates:

```python
body = {"t": [type_uri, typedef_address],      # versioned, like predicates
        "k": sorted(identifying_role_names),   # the key-set is part of identity
        "r": sorted([name, canon_value(*roles[name])] for name in identifying)}
```

Also note `event_address` bypasses `digest_of` — no domain separation, no algo-tag migration path, violating §6 and the ALGOS design in the same file. Second candidate: `text` carries no language tag; a personal store hits bilingual data in month one, and adding `lang` to `canon_value` changes every text-object address. Add `[  "text", value, lang|null ]` now.

**3. Over-built: §5, salted commitments and salt-destruction deletion. Delete it from Layer 0.** Nothing publishes anything yet, and the mechanism is self-defeating as specified: a per-assertion salt means two stores holding the *same* claim publish *different* commitments, so public commitments can never demonstrate agreement — which §0 itself lists as a v1 flaw ("commitments... unable to prove semantic agreement"). The repair relocates that flaw into the published layer and calls it privacy. When publishing exists you'll want equality-provable commitments (Pedersen over the canonical bytes, or ZK membership), and salt is a column you add then; nothing about today's addresses depends on it. The "must be Layer 0 or never" argument is false — `commit()` is already a free-standing function touching no address format. Secondary deletion: `Lattice.compose`/`paths_for` — nothing consumes composition, and `SOME`-via-decomposition has no query path.

**4. The seven open items:**
1. Subsumption-blind conflicts: the doc is out of sync — `_subsumption_conflicts` is already implemented. "Layer 4, fixable any time" is right, but see §1: it misses positive-existential-vs-positive-subsumed today.
2. Derived scope = intersection: **half wrong.** Intersect `valid_time`/`valid_place`; `under_assumption` must be the **union** of the steps' assumptions — intersecting assumptions strengthens a derived claim beyond its premises.
3. Cycle rejection at registration: **wrong under federation.** Two acyclic stores union to a cycle; which edge gets rejected depends on replay order, so merged stores disagree on the lattice and hence on conflicts. Reject deterministically (drop the edge whose declaring claim has the greater content address) or bound at query time.
4. Merge quarantine/budgets first: right, and it should be next, not open — nothing in Layer 4 is testable at scale without the merge path.
5. Act storage "strictly doubles on every merge": **wrong as stated.** `claim_time` is in the hash, so re-syncing the same peer is idempotent (identical bytes, identical address); acts only "double" when merging genuinely disjoint histories, which is data, not overhead. Non-issue; close it.
6. `mode` as open registry: **wrong.** Sorts are safely open because an unknown sort can be ignored; an unknown *mode* cannot — a peer that treats an unrecognized retract-like mode as annotation resurrects retracted claims. Closed enum; grow it with `schema_version`.
7. Unregistered-overlaps default: right, keep it — but state the purchased cost: junk qualifiers now *create* conflicts instead of evading them, so conflict-budget quarantine (item 4) is a dependency, not an independent item.

**5. What breaks first at scale.** Single store, 10⁶ assertions: `Closure.rep()` scans every ref in `_parent` per call (`min(m for m in self._parent if self._find(m)==root)`). `proposition_key` calls it per claim → agreement/conflict over 10⁶ claims with 10⁵ refs is ~10¹¹ operations. Postgres is fine; this Python layer dies first. Fix: cache representative per root, invalidate on union — O(1) amortized.

Merging two 10⁶ stores: the claimed CRDT property holds only for Layer 0 and the document quietly extends it to the system. **Closure acceptance is not confluent.** `max_class_size` and `require_agents` make fusion depend on edge replay order: merge A then B versus B then A accepts different `sameAs` sets → different representatives → different proposition keys → the two merged stores report different agreements and different conflicts *from identical claim sets*. Everything the system is for lives above the CRDT. Fix concretely: batch acceptance — union all candidate edges, apply all blocks, then replay edges in content-address order; same edge set → same closure, regardless of merge history. `is_blocked`'s O(|A|·|B|) pairwise scan per accept is the second cliff; index blocks by root.


[stderr] 

Changes    +0 -0
Requests   1 Premium (2m 50s)
Tokens     ↑ 223.6k (166.1k cached, 57.5k written) • ↓ 9.5k (6.4k reasoning)
Resume     copilot --resume=7bf9be3c-7961-4016-a285-5ae4eeae1b49
