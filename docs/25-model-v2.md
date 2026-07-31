# Data model v2 — Layer 0 closed

Supersedes [23-model-v1.md](23-model-v1.md). v1 was reviewed blind by four
models (`data/model_v1/`); this closes the items that change the canonical form
and therefore every content address — free now, catastrophic once data exists.

## 0. The principle the whole round turned on

Reviewing two rounds of findings together, **almost every flaw found was the
same flaw**: v0 selling content addressing as semantic agreement; v1 leaving
higher-order claims on the syntactic hash; `local:` giving two stores one
address for different people; n-ary reification producing two addresses for one
fact; commitments over syntactic addresses being unable to prove semantic
agreement; claim acts never deduplicating.

Six findings, one root cause.

> **[CORRECTED after the v2 panel.]** This unification is **too strong**, and
> the correction matters more than the claim did. `local:`, n-ary role sets and
> `claim_time` in act hashes are separate design errors that happen to touch
> addressing. Worse, as one reviewer put it, treating them as one root cause is
> *"what licensed the non-fix"* — believing the principle had been applied
> everywhere is precisely why §1 shipped a fix that was never implemented and
> why the event-identity problems below went unexamined. The rule that follows
> is still a good rule. It was not a diagnosis, and using it as one caused real
> damage. This was the exact risk flagged when the round was commissioned, and
> it landed anyway.

So the rule is stated once and every use is checked against it:

> **A content address answers "are these the same bytes?". It can never answer
> "are these the same claim?" or "are these about the same thing?".**

Everything below follows from applying that consistently.

## 1. `act_ref` and `prop_ref` — **RETRACTED**, the dilemma is not dissolved

> **[RETRACTED after the v2 panel — 4 of 4 reviewers, and verified against the
> shipped code.]** This section claimed a fix that is not implemented and,
> as encoded, is actively wrong. `proposition_key` runs the closure only over
> **entity** refs, so a `prop_ref` is left as a raw address and a belief on
> `prop_ref(Ha)` does **not** cover `Hb`. Worse, the encoding put the target in
> an `about` qualifier, which `_tc` drops as unregistered — so beliefs about
> **completely unrelated** propositions pool into one bucket, which corrupts
> agreement rather than merely failing to improve it. The test written for this
> section only checked that two sorts produce different hashes; it never
> exercised the resolution that was the entire point.
>
> The reviewers are also right about the deeper claim. A content address cannot
> be simultaneously commitment-grade and a name for a fibre that moves —
> "putting the mutability in the reading" does not make `H(salt ‖ Ha)` a
> commitment to the fibre of `Hb`. Semantic resolution at query time is
> achievable and worth building; **cross-store proposition-level agreement
> proofs are not available** without a real fibre id, which is a new Layer 0
> kind and should not be minted until it is known to be needed. Commitments
> target acts and assertions only.
>
> The `act_ref` / `prop_ref` split may still be right as a *typed intent* on
> higher-order claims, but it is not a finished fix and this document should
> not have said it was.

### Original section, superseded

v1's review put the problem crisply: *stable addresses cannot name mutable
proposition keys; derived keys cannot be commitment targets.* v1 promised both.

The resolution is that the two referent kinds **differ in how they resolve, not
in what they store**:

| sort | resolves to | closure applied | used by |
|---|---|---|---|
| `act_ref` | exactly that act | **no** | retraction, extraction fidelity |
| `prop_ref` | the whole proposition fibre containing it | **yes** | belief, reliability |

Both are stored as syntactic addresses, so both stay stable and
commitment-grade; the mutability lives in the reading. That fixes the v1 break
case — a belief on `prop_ref(Ha)` covers `Hb` once identity is accepted — and
turns "the same agent believes 0.9 here and 0.2 there" into a **detected
conflict about one proposition** rather than a silent miss.

One sort would have forced every consumer to runtime-dispatch, and a mis-typed
ref would have changed meaning silently instead of failing.

## 2. Existentials: `SOME` and `NONE`

Two gaps found from opposite directions turned out to be one missing construct:

- *"Alice has no children"* is **not** `(alice, has_child, bob, −)`. Polarity
  negates one triple; it cannot say no object exists. A personal store needs
  this on day one — no allergies, no dietary restrictions.
- Safely decomposing a composite predicate (`grandmother_of` implies *some*
  parent) needs the positive form, and naming that parent would fabricate one.

So the object may be `SOME` or `NONE`, canonicalised under their own head so
they can never collide with a real value, and **retaining the sort** — "no
children" and "no birth date" are different claims.

Conflict rules, and note they hold for **any** predicate rather than only
functional ones. `has_child` admits many objects, and *"no children"* still
contradicts *"child is Bob"*; routing existentials through the functional rule
would have missed exactly the claims this construct exists for.

- `(s,p,NONE,+)` conflicts with any `(s,p,o,+)` of overlapping scope
- `(s,p,SOME,+)` conflicts with `(s,p,NONE,+)` of overlapping scope
- `(s,p,SOME,+)` is entailed by any `(s,p,o,+)` and reports nothing

## 3. n-ary facts: events with role-derived identity

"Alice sold the house to Bob for $10 in 2020" reifies at least two ways, and
under v1 those produced different addresses — so federation failed on **every**
n-ary fact, silently.

An event becomes an entity whose id is a content address over its role
bindings, in the `event:` namespace (exempt from store-scoping precisely
because a content hash is globally unique by construction).

**Identity comes from a declared subset of roles, not all of them.** Two
extractors rarely recover the same coverage: one gets seller/item/time, another
also gets the price. Hashing everything would make those different events;
hashing the roles the event type declares as *identifying* makes them the same
event with different amounts known. Extra roles become ordinary claims about
that entity. An event missing part of its key is **refused**, because guessing
an identity fabricates one rather than admitting ignorance.

This also gives comparative preference — `prefers A over B` — a shape, which
binary triples do not have and a personal store needs.

## 4. Predicates carry their definition version

v1 keyed predicate identity on `(uri, definition_hash)` and then stored only
the uri in assertions, so two definitions under one uri were indistinguishable
despite the document claiming merge-safety. The predicate slot is now
`[uri, definition_address | null]`. A bare uri is still allowed and
canonicalises with an **explicit null**: it records that the claim named no
definition version, rather than pretending it named one.

## 5. Salted commitments, and how deletion becomes possible

A content address is **binding but not hiding**. The claims in a personal store
come from tiny spaces — enumerate the diagnosis codes, hash each against the
shared seed vocabulary, match the published log. Shared vocabulary is what
makes proposition keys work across stores, so the seeds programme and
unsalted commitments are directly at war.

    content_addr  = H(kind ‖ schema_version ‖ canonical_bytes)   -- private
    public_commit = H(salt ‖ content_addr)                       -- published

**Salt destruction is the deletion mechanism**, which append-only otherwise
makes impossible. Destroying the payload and its salt leaves a commitment
nobody can open or dictionary-attack, while the address itself survives so
references do not dangle and the record still shows something was asserted and
later erased. A person's agent needs this for facts about third parties,
coerced entries, and legal erasure — and it has to be Layer 0 or it never
happens.

## 6. Domain separation

Every address is `H(content_kind ‖ schema_version ‖ payload)`. Without it an
assertion digest and a claim-act digest are drawn from one space and
substitutable, and a payload hashed under v1 is reinterpretable under v2. Both
are standard commitment failures and both are unfixable once addresses
circulate.

## 7. `local:` is not a namespace

Every store mints `local:owner` for a different person, so a union silently
fuses two subjects — or falsely deduplicates their claims when the objects
coincide. Since the ref is frozen into an immutable address it cannot be
disambiguated afterwards, so reserved namespaces are refused at the door and
`mint_namespace()` produces store-scoped ones.

## 7b. Seeds are a precondition (measured at exp69)

v1 §7 argued that vocabulary canonicalisation should be seeded. exp69 measured
it: the three corpora already in this store share **zero** triples pairwise,
and zero under an oracle entity aligner, because their predicate vocabularies
do not intersect at all. Federation between stores with disjoint vocabularies
is epistemically a no-op — the merge succeeds and nothing is learned. The seed
package is therefore load-bearing infrastructure rather than a convenience, and
it belongs ahead of any further corpus work.

## 7c. Connection is not corroboration — and it changes which corpus to use

exp69 and exp70 chased the missing agreement signal to its root, and the answer
is not what the seed argument assumed.

| measurement | result |
|---|---|
| three corpora, shared triples | **0**, and 0 under an oracle entity aligner |
| same-domain corpus (558 AI papers), subjects in >1 paper | **0 of 504** |
| objects in >1 paper | 90 of 950 (9.5%) — `mmlu`, `gsm8k`, `llama-3`, `lora` |
| entities appearing as both subject and object | 252 |
| papers linked into one component by a unified namespace | **125 of 253** |
| triples corroborated, even undirected, under that registry | **0 of 1207** |

So a shared registry **does** work, for what it can do: it connects half the
corpus into one traversable component. It simply does not produce agreement.
**A registry buys shared entities; corroboration needs shared assertions**, and
those are different things.

**The deeper reason is structural and it disqualifies the research corpus for
this purpose.** A paper exists to report something new. Two papers referencing
one model say *different* things about it — that is the point of publishing.
Scientific literature **cites rather than repeats**, so the corroboration
machinery has almost nothing to count no matter how well entities are resolved.

That is a real steer rather than a setback. Corroboration arises where
independent observers state the *same* thing: encyclopedic sources (wiki
measured 3.89%), replications, overlapping structured databases — and most
directly, **the personal case this substrate is actually for**. An agent
observing "prefers aisle seats" on Monday and again in March has genuine
independent corroboration of one proposition, which is exactly the shape
`agreement()` was built to count and exactly what the paper corpus cannot
supply.

**Consequence for sequencing**: the seed registry is still worth building, but
for *traversal* rather than agreement, and the corroboration and refusal
machinery should be exercised against personal-style observational data rather
than against papers.

## 8. Still open — deliberately, and not in Layer 0

- **Conflict detection is subsumption-blind.** `(X, mother_of, Y, +)` versus
  `(X, parent_of, Y, −)` is a flat contradiction that the detector cannot see,
  because it groups on the literal predicate string rather than over the
  lattice. Layer 4; fixable any time.
- **Derived scope** is unspecified; a composition's validity should be the
  intersection of its steps'.
- **Lattice cycles** must be rejected at registration or bounded at query time.
- **Merge quarantine and per-class conflict budgets** — the v1 review's
  strongest operational point, and the first thing the merge path will need.
- **Claim acts never deduplicate**, because `claim_time` enters their hash.
  Possibly correct — they *are* distinct acts — but it means act storage
  strictly doubles on every merge, and that cost is now stated rather than
  discovered.
- **`mode` as an open registry** rather than a closed enum, consistent with
  sorts, predicates and qualifiers. Cheap; not yet done.
- **Qualifier registry** with `overlap_op` declared per qualifier, and the
  critical default that an **unregistered qualifier always overlaps** — if
  unknown defaulted to disjoint, any agent could make its claims undisputable
  by attaching one junk qualifier, which is v0's bug through a side door.

## 9. What is implemented and tested

`foundation/model/`, 145 tests. `canonical.py` (sorts, existentials, versioned
predicates, event addresses, domain separation, salted commitments,
namespaces), `identity.py` (closure, deterministic representatives, fusion
circuit breakers), `conflict.py` (proposition keys, scope overlap, existential
and functional conflicts, evidence-based agreement).
