## 1. Fatal flaw: both headline guarantees are defined over raw refs, but truth lives modulo identity

Dedup-by-hash and conflict detection both key on the literal subject string. Under federation, most subjects are `local:` refs, so the two things the design brags about — countable agreement, detectable contradiction — silently fail for exactly the entities federation exists to reconcile.

Concrete break:

```
Store A:  (local:a:p1, date_of_birth, 1907-05-22, +, {})   ← agent source_A
Store B:  (local:b:p9, date_of_birth, 1907-05-23, +, {})   ← agent source_B
Both:     (local:a:p1, sameAs, wikidata:Q152 …)  (local:b:p9, sameAs, wikidata:Q152 …)
```

After union: four assertions, zero conflicts. §5's functional-conflict rule ("same `(s,p,quals)`") never fires because the subjects differ at the base layer. The contradiction is only visible through the Layer-4 sameAs closure — a *disposable cache*. So contradiction detection is not "computable from declared information"; it is computable modulo an identity view the document explicitly says nothing depends on. Symmetrically, if both stores said 05-22, agreement is `COUNT = 1` per assertion, not 2. Content-addressing dedupes syntactic identity and the document sells it as semantic agreement.

Same flaw, second face: **conflict detection requires exact qualifier-set equality.** `(Q42, member_of, X, −, {})` never polarity-conflicts with `(Q42, member_of, X, +, {valid_time: 1980–})`. Any agent that adds one innocuous qualifier makes its claims undisputable by rule 1 and 2. Contradiction detection is exact-match brittle in a system whose whole premise is uncoordinated writers.

Third face, a schema bug rather than a philosophy bug: `assertion_event` references the assertion, not an attribution. **You cannot withdraw your own claim.** Agent X retracting its extraction emits `withdrawn` against a hash that three other agents also attribute. Under merge, "surviving answers" is undefined: does remote:bob's `withdrawn` kill my local answer? Grow-only event sets are a CRDT; their interpretation here is not even specified, let alone monotone.

Fix concretely:

```sql
ALTER TABLE assertion ADD COLUMN qual_hash bytea
  GENERATED ALWAYS AS (sha256_of_canonical(qualifiers)) STORED;
CREATE INDEX ON assertion (subject, predicate, qual_hash);   -- functional-conflict probe

ALTER TABLE assertion_event
  ADD COLUMN attribution bigint REFERENCES attribution(id);  -- withdraw a CLAIM, not a fact
```

And state plainly: agreement counting and conflict detection are defined **over the identity view**, and the view (a union-find over accepted `sameAs` claims, incrementally maintained) is therefore load-bearing, not optional.

## 2. What forces a Layer-0 change within a year

**The evidence shape.** `quoted_span NOT NULL` plus single-document evidence forbids attributing any *inferred* claim: an extractor that combines two sentences, a reasoner applying transitivity, an agent asserting `sameAs` from name+dob match. None of these have a quoted span. Within months you will either fake spans (corrupting quote-never-reconstruct) or NULL-ify the constraint (a Layer-0 migration). Fix now:

```sql
CREATE TABLE evidence (
  attribution  bigint NOT NULL REFERENCES attribution(id),
  kind         text NOT NULL,          -- 'span' | 'premise'
  document     text, doc_hash bytea, locator text, quoted_span text,
  premise      bytea REFERENCES assertion(hash),
  CHECK ((kind='span' AND quoted_span IS NOT NULL) OR (kind='premise' AND premise IS NOT NULL))
);
```

Second forcer: **the four sorts.** Geo coordinates arrive the first time anyone ingests "born in" alongside "located at 48.86°N 2.35°E". You'll smuggle it into `text` and lose queryability, or migrate. Cheaper: make sorts an open registry with a closed *encoding contract* (canonical bytes + comparison op), same move you already made for predicates. The grammar closes; the sort vocabulary shouldn't.

The event-attribution link (above) is the third. Fix all three now; they're cheap pre-build and brutal post-build.

## 3. Over-built: delete the predicate algebra and the Datalog layer

`symmetric`, `transitive`, `inverse_of`, and the "Datalog-style incremental evaluation" of derived edges solve an ontology-reasoning problem this system will not have at 10⁴–10⁶ claims with an LM at both ends. Almost no real predicate is safely transitive; one wrong `transitive` flag composed with one wrong `sameAs` manufactures unbounded derived garbage that then floods the conflict detector. Keep `functional` (it earns its keep in §5). Delete the rest; a bounded-depth recursive CTE at query time covers the rare genuine case (`located_in`). Also delete `refuse` from the closed operator set — refusal is render-time policy, not query algebra, and every entry removed from the frozen layer is risk removed.

## 4. The seven questions

1. Split: **right.** Content-addressing as *the* merge primitive: **wrong as stated.** It's a dedup optimization; agreement must be counted over the identity view (§1), or federation does no epistemic work for local entities — the common case.
2. Modality absent: **right.** Qualifier + agent property covers it; not a Layer-0 forcer. Resist the panel member who wants it.
3. **Wrong cut.** Open qualifiers destroy both hashing and conflict detection (§1). Split them: truth-conditional qualifiers (`valid_time`, `under_assumption`, …) are a *closed, registered* set that participates in hash and conflict logic with defined overlap semantics; everything annotation-like belongs on the attribution, not the assertion.
4. Direction right, conclusion evasive. It survives federation **only if** the closure is a materialized, incrementally-maintained view that dedup-for-counting and conflict detection consult. Query-time closure is fine; pretending nothing depends on the view is not.
5. Evidence shape, sorts, event-attribution link (§2). Fix all three now.
6. Nothing — 10⁶ rows is small for Postgres. See §5 below for what actually degrades.
7. **No good reason to store them** — deriving is right, precisely because derived edges have no honest attribution. But mostly moot: delete the machinery (§3).

## 5. What breaks first at scale

**Single store, 10⁶ assertions:** Postgres shrugs. First real degradation is the functional-conflict probe — "same `(s,p)`, differing `o`, equal quals" over jsonb has no usable index; add the `qual_hash` column above or every conflict check is a re-parse scan. Second: per-query fan-out over sameAs equivalence classes; without a materialized `canonical_entity(ref → class_id)` table, every query multiplies by class size. Random-bytea PK insert scatter is noise at this scale.

**Merging two 10⁶ stores — two silent failures, both worse than slowness:**

- **Canonicalization drift.** One disagreement — a float shortest-round-trip edge case, an NFC-vs-NFD slip, `-0.083` vs `-8.3e-2` — and dedup silently stops. Assertion count roughly doubles, attribution counts split, agreement metrics quietly halve, nothing errors. Ship a conformance vector: N canonical-form/hash test pairs both stores must reproduce byte-identically *before* union is permitted. This is a protocol artifact, not a paragraph in §7.
- **sameAs fusion bombs.** The `owl:sameAs` failure the document cites doesn't disappear because resolution moved to a view — it arrives via merge as one bad claim (`remote:b:e88 sameAs wikidata:Q42`, wrong Q42) that fuses two people's equivalence classes and makes the conflict detector emit thousands of spurious functional conflicts against every `date_of_birth`, `place_of_birth`, `spouse` in both classes. The view needs an acceptance policy (per-agent trust, class-size and conflict-rate circuit breakers) from day one. That policy is the actual hard federation problem; the union of immutable sets was never it.


[stderr] 

Changes    +0 -0
Requests   1 Premium (1m 53s)
Tokens     ↑ 37.9k (37.9k written) • ↓ 7.3k (4.4k reasoning)
Resume     copilot --resume=0dee5378-2d1c-4f5b-98ae-1d7351a032d4
