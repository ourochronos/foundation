# Data model v1 — identity, dimensional confidence, and designing for the actual goal

Supersedes [22-model-v0.md](22-model-v0.md). v0 was reviewed by four models
blind (`data/model_v0/`) and **all four found the same fatal flaw**; §1 states
it plainly. This revision also takes on the purpose the substrate is actually
for, which arrived after v0 was written and changes what must be settled now.

Standing instruction for this revision: *"lean towards a bit of early
optimization... we're trying to build a substrate, and it's much harder to
change later than now."* So the rule here is **fix now, migrate never** — a
thing is deferred only if deferring it is genuinely reversible.

---

## 0. What this is for

Near term: research aggregation and synthesis. That is the test corpus, not
the goal.

The goal is **the way a person is understood by their agents** — a sovereign
knowledge base holding preferences, motivations and interaction history, which
an agent uses to represent that person faithfully. Data lives on a
private/public gradient with disclosure governed by sensitivity,
identifiability and intended use. The end state is that **a person's
intentions stay private while still shaping the world around them, without
requiring their attention**, via zero-knowledge aggregation.

**The substrate is the same for both**, which is the first thing worth
checking and it holds: claims with provenance, conditions, contradiction,
append-only history. The personal case differs in four ways and each one
changes a decision below:

| personal-KB property | consequence for the model |
|---|---|
| claims are mostly **inferred**, not quoted | evidence cannot require a quoted span (§5) |
| preferences **change constantly** | `valid_time` is load-bearing, not decorative |
| the **subject is an authority** on themselves | policy must be able to compare agent to subject (§8) |
| disclosure is **set-dependent** | no per-row ACLs; disclosure is computed over a release set (§8) |
| aggregate proofs over private claims | **content addresses are commitments** — hash choice must be agile (§9) |

---

## 1. The v0 flaw, and the fix

**Content addressing dedupes *syntactic* identity. v0 sold it as *semantic*
agreement.** With globally-agreed refs it works; with `local:` refs — the
common case, and precisely what federation exists to reconcile — it fails:

    Store A:  (local:a1, date_of_birth, 1907-05-22, +, {})
    Store B:  (local:b9, date_of_birth, 1907-05-23, +, {})
    both:     ... sameAs wikidata:Q152

Union gives two assertions, **zero detected conflicts**, and agreement of 1
each rather than one recorded contradiction. v0's functional-conflict rule
keys on identical subject strings and never fires. v0 also said the identity
view was disposable and nothing depended on it; that was backwards.

**Fix — two levels of identity:**

- **Assertion hash**, over raw refs. Immutable, content-addressed, the merge
  and dedup primitive. A commitment (§9). Unchanged from v0.
- **Proposition key**, over equivalence-class representatives. Derived, lives
  in Layer 4, recomputed when the closure moves. **Agreement and contradiction
  are computed over this**, never over the hash.

Storage integrity does not depend on Layer 4; *interpretation* does. The
closure is materialised and incrementally maintained, with an acceptance
policy (§7) — because one bad `sameAs` fuses two people's classes and floods
the conflict detector with spurious disputes.

**Conflict detection also needs overlap, not equality** (v0 was exact-match
brittle: `(X, member_of, Y, −, {})` never conflicted with
`(X, member_of, Y, +, {valid_time: 1980–})`, so any agent could make its claims
undisputable by adding one qualifier). So qualifiers split in two:

- **Truth-conditional qualifiers** — a *registered* set with declared overlap
  semantics (`valid_time`, `valid_place`, `under_assumption`). They enter the
  hash and participate in conflict logic. Two claims conflict when their
  qualifier scopes **overlap**, not when they match.
- **Annotation** — everything else. Moves to the claim act, out of the
  proposition entirely.

## 2. Confidence is dimensional — so it stops being a column

v0 had `confidence real` on the attribution, and the panel split on deleting
it. The right question kills the debate: **in what context are they
confident, and about what?** A single float silently collapses at least four
independent things:

| dimension | about | held by |
|---|---|---|
| **extraction fidelity** | does the source actually *say* this? | the extractor |
| **belief** | is it *true*? | anyone |
| **source reliability** | is this agent trustworthy — **in what domain?** | the reader |
| **identity confidence** | are these entities really the same? | anyone |

An extractor can be certain a paper says X while holding no view on whether X
is true. Compressing that into one number destroys the distinction that
matters most for an epistemics-first store.

**So confidence is not a field. It is a claim about a claim** — which needs
the `assertion_ref` sort (§3) that three of four reviewers demanded anyway:

    (act_7,          extraction_fidelity, 0.92, +, {})
    (A_1,            believed,            0.70, +, {by_lights_of: local:me})
    (local:source_X, reliability,         0.40, +, {in_domain: biography})

Four things the column collapsed are now explicit: *what* it is about
(the object), *which dimension* (the predicate), *in what context* (the
qualifier — the user's question, answered structurally), and *whose view*
(the attributing agent). It is disputable, mergeable and federated like
everything else, and nobody's confidence silently becomes everybody's.

## 3. Layer 0 — the grammar (revised)

**Sorts** — now five, and the fifth pays for itself three times over:

    entity | text | quantity | time | claim_ref

`claim_ref` points at an assertion or a claim act by content address. It is
required independently by **retraction** ("D retracts H"), **confidence**
(§2), and **entity splits** (§6). Three separate requirements landing on one
primitive is the strongest available argument for adding it now.

**Sorts are an open registry with a closed encoding contract.** The same move
already made for predicates: the grammar closes, the vocabulary does not. A
new sort ships a canonical byte encoding and a comparison operator. Geographic
coordinates will arrive the first time anyone ingests "located at 48.86°N,
2.35°E", and v0 would have forced them into `text` or forced a migration.

**Assertion** (a proposition; no author):

    assertion := (subject, predicate_uri, object, polarity,
                  truth_conditional_qualifiers)

**Claim act** (someone claiming it — v0's "attribution", renamed because it is
an *act* and now content-addressed so it can be referred to and disputed):

    claim_act := (assertion_hash, claimant, evidence, mode, claim_time)

**`mode` is added**, and on the act rather than the assertion — the version
two reviewers argued for and the one I had not considered. "Alice *predicted*
P" and "Alice *observed* P" share proposition P and are epistemically
different acts. Putting mode on the assertion would have fractured the
proposition; putting it on the act preserves it.

    mode := asserts | reports | observes | infers | predicts | hypothesises

**Removed from Layer 0:** the query operator set. It was never storage
grammar, it is compiler IR, and it could not express anti-join, ordering or
top-k — so it forced a migration immediately rather than in a year. Version it
like ordinary software.

**Events are no longer a side channel.** With `claim_ref`, retraction and
supersession are ordinary claims — mergeable, attributable, and disputable.
v0's `assertion_event` table targeted the assertion rather than the act, which
meant *you could not withdraw your own claim* without appearing to withdraw
everyone's.

## 4. Predicates must be merge-safe

v0 keyed predicates on a bare id, so Store A's `status` (marital) and Store
B's `status` (HTTP) collided on primary key with matching hashes and different
meanings.

    predicate := (uri, definition_hash, definition, domain_sort, range_sort,
                  functional, category)

Identity is `(uri, definition_hash)`. Changing a definition mints a new
identity; old assertions keep pointing at the definition they were made under.
Vocabulary alignment between stores is — as everywhere else here — a claim.

**The rest of the algebra is deleted.** `symmetric`, `transitive`,
`inverse_of` and the Datalog derivation layer go; `functional` stays because
it earns its keep in conflict detection. Almost no real predicate is safely
transitive, and one wrong `transitive` flag composed with one wrong `sameAs`
manufactures unbounded derived garbage that then floods the conflict detector.
Bounded-depth recursive SQL covers the rare genuine case.

## 5. Evidence: inference is first-class

v0 required a quoted span, which forbids every *inferred* claim — an extractor
combining two sentences, a reasoner applying transitivity, an agent inferring
`sameAs` from name and birth date. **In the personal-KB case almost every
claim is inferred**, so this is not an edge case; it is the main path.

    evidence := span(document, doc_hash, locator, quoted_span)
              | premise(claim_ref[])
              | observation(channel, occurred_at)

`premise` makes inference chains explicit and walkable, which is what makes an
agent's understanding of its user *auditable by that user* — the thing that
distinguishes this from a model with opinions about someone. Quote-never-
reconstruct still holds for `span`; it was never applicable to inference.

## 6. Entities shift: merge, split, and conflation

Append-only makes merges easy and **splits hard**, because the split
discovers that existing immutable assertions were about the wrong thing.

**Merge** — assert `sameAs`; the closure absorbs it; disputing the `sameAs`
reverses it. Nothing is rewritten.

**Split** — `local:x` turns out to be two people. Assertions already reference
`local:x` and cannot be rewritten. So:

    (local:x, conflates, local:x1, +, {})
    (local:x, conflates, local:x2, +, {})
    (A_i,     subject_is, local:x1, +, {})      ← a claim ABOUT an assertion

Old assertions stand, unmodified and still true *as recorded*: someone did
assert that of `local:x`. What changes is the **interpretation**, which lives
in Layer 4 where change is free. `conflates` blocks the closure from treating
`x1` and `x2` as one.

**Blends** are the general case and fall out for free: reassignment is
per-assertion, so some claims go left, some right, and **some stay
unassigned** — surfaced as *ambiguous subject* rather than silently guessed.
Refusing to guess is the honest behaviour and the model should not be able to
hide it.

**Propagation is not curation.** Mutations propagate as *claims*, and each
instance applies its own acceptance policy (§7). There is no other
federation-safe answer: you cannot force a peer to accept your identity
resolution. The cost is bounded — a merge or split invalidates only the
affected equivalence classes, so the closure updates incrementally rather than
globally.

## 7. Two canonicalisations, and only one of them may be emergent

These get conflated and they must not be:

**Encoding canonicalisation** — the bytes for a given claim. **Frozen,
never emergent, conformance-tested.** If two stores disagree on one edge case
(NFC vs NFD, `-0.083` vs `-8.3e-2`) dedup silently stops, assertion counts
roughly double and agreement metrics quietly halve, with nothing raising. So
the protocol ships a **conformance vector**: N canonical-form/hash pairs a
partner must reproduce byte-identically *before union is permitted*. A
protocol artifact, not a paragraph in a spec.

**Vocabulary canonicalisation** — which URI means "born in". **Seeded and
emergent, and that is the right design** — and exp69 later upgraded this from
plausible to **measured**. Three real corpora in one store (12,942 wiki, 6,451
arXiv, 602 model-card claims) share **zero** triples pairwise, and still zero
under an *oracle* entity aligner that perfectly unifies every entity appearing
in two of them. Their predicate vocabularies do not intersect at all, so
corroboration between them is impossible by construction rather than merely
rare: the set union succeeds flawlessly and yields zero agreement and zero
conflict.

**That makes the seed vocabulary a PRECONDITION for federation, not an
optimisation.** Two stores can merge perfectly and learn nothing from each
other, and no amount of entity resolution repairs it — the oracle aligner is
the ceiling for any resolver and it buys nothing. A new corpus is worth
ingesting only if it is extracted *into* a shared vocabulary against shared
entities. Two mechanisms:

- **Canonical seeds.** A signed, versioned package of uncontroversial entities
  and predicates (`person`, `located_in`, `United States`). No instance should
  rediscover these, and shared seeds mean most claims land on shared URIs from
  day one — which is what makes the proposition key useful across stores
  instead of every entity being `local:`.
- **Emergence by adoption.** Instances gossip predicate usage; a locally-minted
  predicate adopted widely becomes a candidate for the next seed version.
  Alignment between vocabularies is a claim like everything else.

Being straight about the hard part: adoption-weighted vocabulary convergence
is a **social process with technical assistance**, not an algorithm. Linked
data has not solved it in twenty years. Seeds plus alignment claims capture
most of the practical value without requiring the hard part to be solved.

## 8. Disclosure — a function over sets, never a flag on a row

The sharing model must handle sensitivity, identifiability and intended use.
**Per-row ACLs are the standard mistake** and they fail on composition: three
individually-innocuous claims can identify a person jointly. So:

    disclose(candidate_set, purpose, audience) -> released_set | refusal

with inputs:

- **sensitivity** — derived from predicate and subject, with explicit override
- **identifiability of the release set** — computed over the *set*, k-anonymity
  style, because this is exactly what per-row schemes cannot see
- **purpose and audience** — properties of the request, not of the data

**Subject authority**: policy must be able to compare claimant to subject.
When the subject of a claim is the store's owner, their own assertion outranks
any agent's inference about them. An agent that cannot be corrected by the
person it represents is not representing them.

This reuses the refusal machinery the project already has, generalised once
more: refuse a type-mismatched answer → refuse to collapse a disagreement →
**refuse to disclose past the boundary**.

## 9. Designing now for zero-knowledge aggregation

The end goal — private intentions shaping outcomes without revealing
themselves — imposes exactly two requirements that are cheap now and
impossible later.

**(a) Content addresses are already commitments.** A claim's hash is a binding
commitment to its content; that is what a ZK circuit needs to reason about a
claim without seeing it. Content addressing is now paying for itself three
times: dedup, merge, and commitment.

**(b) Hash agility, decided now.** SHA-256 is expensive inside a circuit;
practical ZK systems use algebraic hashes (Poseidon and relatives). Every
content address must therefore carry its algorithm:

    address := (algo_id, digest)

Without this, changing hash function means rewriting every content address in
every store — the exact global rebuild the whole design exists to forbid.
**This is the single clearest example of the standing instruction**: one byte
today, unfixable later.

**(c) Append-only Merkle log** over assertion hashes. Nearly free over a
grow-only set, and it buys **selective disclosure** — proving a claim is in
the store, or that the store has some property, without revealing the rest.
That is the mechanism by which a sovereign store participates in aggregation
while staying sovereign.

Deliberately **not** decided now: the proof system, the aggregation protocol,
whether differential privacy is a better fit than ZK for a given query. Those
are reversible. Hash identity is not.

## 10. Open questions for the next review round

1. Does the **proposition key** actually fix agreement and conflict, or does
   it relocate the problem into closure maintenance?
2. **Truth-conditional qualifiers with overlap semantics** — is a registered
   set with declared overlap right, or does overlap need to be per-predicate?
3. Is `claim_ref` **one sort or two** (assertion vs act)? Retraction targets
   acts; confidence-in-a-fact targets assertions.
4. Does the **conflates / subject_is** split mechanism hold up on a real
   messy case, or does it need per-claim reassignment at a volume nobody will
   ever do?
5. **Identifiability over a release set** is the hard part of §8 — is there a
   tractable computation, or does this need to be conservative-by-default?
6. What in §9 is still **not** enough for ZK aggregation later?
7. What does this model make **impossible** that a person's agent would need?
