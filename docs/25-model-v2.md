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

## 7d. Corroboration needs THREE closed vocabularies, not one (exp69→exp73)

The seed argument kept getting stronger and kept being incomplete. Four corpora
and four zeros later, the shape is clear:

| level closed | result |
|---|---|
| nothing (three corpora, disjoint predicates) | 0 shared triples, 0 under an oracle entity aligner (exp69) |
| entities only, one domain (558 AI papers) | 0 of 1207 — papers cite rather than repeat (exp70) |
| **predicates** closed (philosophy) | 0 of 144 — positions disagree rather than concur (exp72) |
| **predicates + frames** closed (politics, axis-generalised) | **0 of 387** (exp73) |

exp73 is the informative one because it closed two of three vocabularies and
still measured nothing. 316 claims produced **510 distinct concepts** — 256
subjects and 283 objects, with subjects repeating at all only 33 times. Almost
no two claims *can* be the same proposition regardless of how well predicates
and frames are aligned.

**So corroboration requires the predicate, frame and entity vocabularies to be
closed simultaneously.** Closing any two buys nothing, which is why every
partial fix so far has returned exactly zero rather than a smaller number.

And the entity vocabulary cannot be closed by matching. Of 36 near-duplicate
concept pairs, `belief`/`beliefs` and `central-bank`/`central-banks` must merge
while `anarchism`/`minarchism` and `classical-economics`/`neoclassical-economics`
must not — string similarity ranks them identically. **Entity canonicalisation
is an authored registry with explicit aliases**, the same conclusion §7 reached
for predicates and the v2 review reached for the closed layer generally.

## 7e. Corroboration — **REOPENED** (the closure was premature)

> **[REOPENED at exp74.]** The status panel called the closure below "premature
> by exactly one experiment" and named the falsifier: multi-source news. It was
> run. **117 events, 420 articles, 8,802 corroborated entity co-mention pairs**
> — against zero in all four prior corpora. Median 5 *event-specific* shared
> entities per event, so the signal is agreement about one event rather than
> generic frequent terms.
>
> **What this shows, precisely**: the *entity substrate* for corroboration
> exists in reportage and did not in discourse. **What it does not show**: that
> extracted triples corroborate. The measurement is co-mention agreement, which
> is corroboration at its most generous, and it was deliberately chosen so that
> a zero would be decisive — running a model would have conflated extractor
> variance with genuine non-repetition. It is an upper bound, and it is *not*
> like-for-like with the triple-level zeros below.
>
> So the honest statement is: **the genre hypothesis survived its first real
> test.** Discourse does not repeat; reportage does. The next step is extraction
> over news to see whether triples corroborate where entities do, and
> `min_sources` is back to unproven rather than deleted.
>
> **[CONFIRMED at exp75 — triples, not just entities.]** REBEL over the same
> news corpus: **41 triples asserted by ≥2 independent sources**, 4.18% of
> extracted triples, versus **0** in four discourse corpora. Below exp74's 5.0%
> co-mention bound, as agreeing on a *relation* should be harder than
> co-mentioning two entities. Conservative alias merging moves it 41 → 43, so
> surface variation is a *locatable* barrier rather than an unbounded one.
>
> **And the ontology conclusion in §7d was wrong.** Closing the entity and
> predicate vocabularies was called "an ontology-building project" and the line
> was shut on that basis. It is not: **REBEL's relation vocabulary IS Wikidata
> properties** (`presenter`, `country`, `participant`), so the predicate
> vocabulary closes with no authoring at all — one of the three vocabularies
> exp73 proved necessary, obtained off the shelf. This project never looked for
> purpose-built extraction models until prompted; a survey of them belongs
> before any conclusion that something requires authoring.
>
> REBEL's failure mode is corroborating evidence rather than a limitation: on
> "Compatibilists hold that free will is compatible with determinism" it
> returns **nothing**, declining instead of inventing, because it is trained on
> factual relations between named entities. Its competence domain is exactly
> the genre where corroboration lives.
>
> Retained below because the mechanisms it identified for each zero — papers
> cite rather than repeat, positions disagree rather than concur — are still
> the right explanations for *those* corpora.

### Superseded: corroboration is CLOSED as a line of work

The obvious next move after §7d was to close the entity vocabulary from the
corpus's own page titles. Measured first: **177 titles cover 11% of extracted
concepts and 20% of mentions**, and fuzzy matching reaches only 33 of 454
unmatched. Worse, its near-misses are wrong in the dangerous direction —
`full-employment`~`unemployment` scores as similar and means the opposite;
`rule-consequentialism`~`consequentialism` is subsumption, not identity.

Closing entities at the required fidelity is therefore an **ontology-building
project** — an authored registry of 500+ concepts with aliases and a
subsumption graph — which is precisely the crowded prior art in
[21-references.md](21-references.md), not a gap worth filling here.

**So the finding is stated and the line is closed**: corroboration-based
confidence is not obtainable from published discourse. Four corpora, four
zeros, with a mechanism for each — papers *cite rather than repeat*, positions
*disagree rather than concur*, encyclopedias state one settled view, and
free-form concepts prevent two claims from ever being one proposition. The
`min_sources` refusal policy that depends on it refuses 98.1% of answerable
questions (exp68) and should be understood as waiting for observational data,
where repetition is structural, rather than as broken.

**[CORRECTED after the status panel — 4 of 4 reviewers, and verified in the
diff.] The scoreboard below is wrong and the correction is the finding.**

The charge is circularity in conflict detection. exp72 declared a set of
opposed predicate pairs *"used only to MEASURE the gap in S3, **never to patch
it**"* — and one turn later `oppose()` was seeded with exactly those pairs. So
the 15 newly-detected oppositions are precisely the 15 measured as invisible
and then authored edges for. That is not detection; it is **retrieval of
authored disagreement**, with no gold precision or recall denominator. Worse,
as one reviewer put it, conflict detection and corroboration *"stand or fall on
the same missing artifact"* — both need an authored ontology — and the
scoreboard scored one "works" and the other "closed".

The other four fare little better under scrutiny. Dedup's 100% cloned one
extraction into two stores, so canonical forms were identical **by
construction** (the realistic drift case already gives 90.5%). Refusal's 0.000
wrongness is guaranteed by exact lookup with no generative step. Expansion's
181/181 ran against a two-line lattice written for that test. Scoped
coexistence's 0 is close to forced, since every position gets its own frame.

**Replace the scoreboard with the distinction that actually matters:**

| validated against EXTERNAL reality | validated against our own artifacts |
|---|---|
| canonicalisation — survived `476`, 104 false birthdays, precision mismatches | conflict detection (edges authored from the corpus) |
| dedup under drift — 90.5% at full precision divergence | dedup at 100% (clone of one extraction) |
| | refusal (self-lookup, no generative step) |
| | query expansion (hand-written lattice) |
| | scoped coexistence (one frame per position) |

Two results survive contact with something that did not come from us. The rest
are code paths that execute.

**And the single largest unmeasured quantity, eight experiments in: extraction
fidelity.** 176 tests cover the model and *zero* cover whether the extractor's
triples match human labels, while the extractor discards half of every corpus.

The superseded scoreboard follows for the record:

| mechanism | status on real data |
|---|---|
| dedup / merge | 100% (exp66) |
| conflict detection | works, incl. 18 real oppositions once `oppose` existed (exp72) |
| scoped coexistence | 0 false conflicts scoped, opposition visible unscoped (exp72) |
| refusal | 0.000 wrongness on four unanswerable populations (exp68) |
| up-lattice query expansion | 0/181 → 181/181, zero sibling leaks (exp68) |
| **corroboration** | **0 across four corpora — closed above** |

Five of six work. The sixth never had data that could feed it.

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
