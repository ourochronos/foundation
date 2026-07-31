# Composite predicates, granularity, and what a query actually is

Two questions, and they turn out to share an answer: *some predicates are
compositions of others — do compositions reference their components or get
stored as components, and where is granularity decided?* And: *what does a
query look like?*

---

## 1. Granularity is decided by the source, never by the schema

The tempting design is to normalise: store only primitive predicates and
derive the rest, so `grandmother_of` is never stored and always rewritten to
`mother_of ∘ parent_of`.

**It is wrong here, and for a reason this project has already paid to learn.**
A source that says "X is Y's grandmother" does not say *which* parent the
relation runs through. Decomposing at ingest requires inventing that, and
inventing what a source did not assert is the exact failure the canonicaliser
already refuses when it rejects `("2009", precision="day")` rather than
zero-filling to January the 1st.

So the rule is the same one, generalised:

> **Store what was claimed, at the granularity it was claimed. The schema's job
> is to hold any granularity and to declare how granularities relate — never to
> pick one.**

Composite predicates are therefore first-class. `grandmother_of` is a real
predicate with a real card, not sugar over a path.

## 2. Two relations between predicates, and only one direction of each is safe

| relation | meaning | example |
|---|---|---|
| **subsumption** `⊑` | every S is also a T | `mother_of ⊑ parent_of` |
| **composition** `⊒ ∘` | a path implies a composite | `mother_of ∘ parent_of ⟹ grandmother_of` |

Both are declared as ordinary claims about predicates, so they are
attributable, disputable and mergeable like everything else — no new
primitive:

    (mother_of,      subsumed_by,   parent_of,  +, {})
    (grandmother_of, implied_by_path, [mother_of, parent_of], +, {})

**The asymmetry is the whole design.** For each relation, one direction adds no
information and the other invents:

- **Compose / generalise (fine → coarse): SOUND.** From `mother_of(A,B)` and
  `parent_of(B,C)`, `grandmother_of(A,C)` follows. From `mother_of(A,B)`,
  `parent_of(A,B)` follows. Nothing is invented.
- **Decompose / specialise (coarse → fine): INVENTS.** From
  `grandmother_of(A,C)` all that follows is *∃y: mother_of(A,y) ∧
  parent_of(y,C)* — and `y` cannot be named. From `parent_of(A,B)`,
  `mother_of(A,B)` does not follow at all.

So the engine may always move **up** the lattice and may **never** move down.
That single rule answers "how do we query cleanly" for this whole class:

- asking for `parent_of` **must** also return `mother_of` and `father_of`
  claims — they are more specific and therefore entail the question
- asking for `mother_of` **must not** return `parent_of` claims — that would be
  the model inventing a gender the source never gave

## 3. Never materialise. Rewrite the query.

The v1 review argued hard for deleting the predicate algebra, and the argument
was concrete: one wrong `transitive` flag composed with one wrong `sameAs`
manufactures unbounded derived garbage that then floods the conflict detector.

That argument is **entirely about materialisation**, and it is correct about
materialisation. It does not touch query rewriting:

- derived facts are **never stored**, so they can never enter the conflict
  detector, never merge, never propagate to a peer, and never need retracting
- the blast radius of a wrong composition claim is **one query**, not the store
- a derived answer is returned **labelled as derived**, carrying its premise
  chain, so the person can see the composition that produced it and reject it

This is also why `evidence := premise(claim_ref[])` earns its place: a derived
answer is exactly a claim whose evidence is a premise chain rather than a
quoted span.

**Bounded, and bounded explicitly**: composition depth is capped per query, the
lattice is checked for cycles at registration, and a query that hits either
limit says so rather than silently returning less.

## 4. The hole this opened: the grammar cannot express existentials

Working through decomposition surfaced a real gap, and it has a mirror image
already noted in the v1 review:

- **positive existential** — `grandmother_of(A,C)` entails *some* intermediate
  parent exists, but the grammar has no way to say "there exists a y such
  that…" without minting an entity for `y`, which fabricates a person.
- **negative existential** — "Alice has no children" is **not**
  `(alice, has_child, bob, −)`. Polarity negates one triple; it cannot say no
  object exists. A personal KB needs "no allergies", "no dietary restrictions"
  on day one.

These are the same missing construct in two polarities, and the grammar needs
one addition rather than two:

    object := ... | SOME | NONE          -- existential markers, per sort

with conflict rules that follow directly:

- `(s,p,NONE,+)` conflicts with any `(s,p,o,+)` of overlapping scope
- `(s,p,SOME,+)` conflicts with `(s,p,NONE,+)` of overlapping scope
- `(s,p,SOME,+)` is entailed by any `(s,p,o,+)` and adds nothing when one exists

`SOME` is what a safe decomposition produces, so the same construct that lets a
personal KB say "no allergies" is the one that lets the engine decompose
without inventing a person. That is a strong signal it is the right primitive
rather than two patches.

## 5. The second hole: derived claims must not inflate agreement

`agreement()` currently counts `DISTINCT claimant` over a proposition. A
derived claim has a claimant. So a store that derives the same conclusion three
ways — or three agents in one store each deriving it once — produces an
agreement of 3 from **one** underlying source.

That is not a small bug. Agreement is the entire epistemic payoff of
federation, and this lets it be manufactured locally at zero cost.

> **Agreement counts independent evidence, not claims.** A claim whose evidence
> is `premise(...)` contributes **the sources of its premises, transitively** —
> never itself.

So the fold is over the transitive closure of premises down to `span` and
`observation` leaves, deduplicated by document. Two agents who both derived a
fact from the same paper are one source, not two, which is what "independent"
was supposed to mean all along.

## 6. What a query actually is

Not a neighborhood dump reconciled by the model. That is RAG with extra steps,
and it puts the reasoning back in the model — the thing every measurement in
this project says to take *out*.

    question
      1. COMPILE   NL -> typed plan. Entities by retrieval; predicates by 1-NN
                   over predicate cards (the 0.975 channel); a bounded typed
                   path expression with an expected answer sort.
      2. EXPAND    execute over real edges. Up-lattice rewrite only (§2),
                   composition as rewrite not materialisation (§3), depth
                   capped, limits reported when hit.
      3. GATHER    for each candidate: the whole proposition fibre — every
                   assertion under the closure, its acts, agents, evidence,
                   scopes, and detected conflicts.
      4. STRUCTURE the store does NOT pick. It returns an adjudication:
                   candidates, independent source counts (§5), the scope each
                   holds under, conflicts, derivation chains, and whether
                   support is thin enough to warrant refusal.
      5. RENDER    the LM writes prose over that structure, quoting spans.
                   It never sees a fact that is not quoted or derived, and it
                   never resolves a conflict the store surfaced.

The LM appears exactly twice — compiling in, rendering out. **The store never
resolves and the model never invents**, which is the same division of labour
the walker result argued for, applied to a store instead of a path.

**Neighborhood fetch is a fallback, and must be labelled one.** When
compilation fails or scores low, dumping a k-hop neighbourhood and asking the
model to make sense of it is a reasonable exploratory mode — but the answer is
then the model's reasoning, not the store's, and the response has to say so.
Silently falling back is how a system that claims to answer only what its edges
license starts quietly inventing.

## 7. Other holes found while writing this

- **n-ary facts have no canonical reification.** "Alice sold the house to Bob
  for $10 in 2020" can be reified as `(alice, sold, house, {to, price, time})`
  or `(alice, sold_to, bob, {item, price, time})`. Different hashes, no dedup,
  agreement never sees agreement — federation fails on every n-ary fact. Likely
  fix: **event entities with content-addressed identity derived from their role
  bindings**, so two extractors that find the same event mint the same id. This
  also gives comparative preference (`prefers A over B`) a shape, which binary
  triples do not have and a personal KB needs.
- **Conflict detection is subsumption-blind.** `(X, mother_of, Y, +)` and
  `(X, parent_of, Y, −)` is a flat contradiction, and the detector groups by
  exact predicate so it never sees it. Conflict must group over the lattice,
  not over the literal predicate string.
- **Derived claims have unspecified scope.** If each step of a composition
  carries `valid_time`, the composite's validity is the *intersection*, and
  nothing says so.
- **Claim acts never dedupe**, because `claim_time` enters their hash. Two
  stores extracting the same fact from the same document produce distinct acts
  forever. That may be correct — they *are* distinct acts — but it means act
  storage strictly doubles on every merge and that cost has never been stated.
- **Lattice cycles** — `A ⊑ B` plus `B ⊑ A`, or a composition loop — must be
  rejected at registration or bounded at query time.
