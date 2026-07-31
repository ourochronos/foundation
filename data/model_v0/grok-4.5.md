Analyzing the model for concrete failure modes before answering.

● Check workspace context (shell)
  │ pwd && ls -la
  └ 37 lines…

1. **The fatal flaw**

Contradiction detection does not compose with identity, and the predicate card is not merge-safe — together they make “preserve disagreement under federation” false.

Concrete case:

- Store A: `(local:a1, date_of_birth, 1907-05-22, +, {})` with `date_of_birth.functional = true`
- Store B: `(local:b9, date_of_birth, 1907-05-23, +, {})` with the same predicate id
- On merge, B also contributes `(local:b9, sameAs, local:a1, +, {})`

§5 only flags functional conflict for identical subject strings. After union you have two births and a `sameAs` claim; no polarity/functional conflict row exists. Layer-4 closure may later glue `local:a1 ≡ local:b9` for display, but nothing in the stored model records a dispute. If the renderer answers under one id, disagreement vanishes; if under both, agreement counts split. Either way detection silently fails exactly when federation did real work.

Worse, make B’s predicate card `functional = false` (or different `inverse_of` / range_sort). `predicate.id` is a global PK with non-CRDT payload. Merge cannot set-union cards; whichever card wins changes which conflicts exist. Assertions are G-set; the algebra that interprets them is not. So merge either rejects the vocabulary, overwrites it, or forks semantics — all corrupt “contradiction is data.”

Secondary break of the same family: two extractors reify one n-ary fact differently

```text
(a, sold, house, +, {to: b, price: 10})  vs  (a, sold_to, b, +, {item: house, price: 10})
```

Different hashes, no dedupe, `COUNT(agent)` never sees agreement. Content-addressing merges bytes, not claims.

---

2. **What forces a CLOSED-layer change within a year**

You will need **assertions (or attributions) as first-class objects** — a fifth sort or a nested-term form.

Events (`withdrawn` / `disputed` / `supersedes`) are a side channel: not content-addressed, not attributable like claims, `bigserial`-keyed, and unable to express “C says B’s withdrawal was wrong” or “paper D retracts assertion H.” Audit, retraction, and federated dispute *about* claims will arrive immediately in any real corpus. Encoding them only as `assertion_event` rows means either lying (“disagreement is in the claim graph”) or migrating Layer 0 when you reify events into data.

**Fix now**, cheaply:

```text
sorts     += assertion_ref | attribution_ref
object    |= hash-of-assertion | hash-of-attribution
```

Then supersession is an assertion, mergeable and disputable. Accepting a future migration here is accepting a rewrite of every event and every query that treats lifecycle as non-knowledge.

(Also freeze merge rules for predicate cards now, or “authored once” is fiction — see §1.)

---

3. **Where it is over-built**

Delete from the closed/core model:

- **`assertion_event` as its own kind system.** Four event kinds duplicate polarity, dispute, and time qualifiers. If you add assertion-refs, events are ordinary claims; if you refuse assertion-refs, you still should not freeze `asserted|superseded|withdrawn|disputed` in Layer 0 — they are product workflow, not grammar.
- **Query operators (`hop|filter|join|…|refuse`) in Layer 0.** That is a compiler IR, not a storage grammar. Freezing it “authored once” couples the DB to one LM query dialect. Data model closes over assertion/attribution shapes only.
- **`embedding` in the schema sketch / Layer-4-as-if-core.** Disposable by your own rule; do not ship it beside `assertion`. It answers a retrieval product question you do not have until the claim store works.
- **Predicate `category`, `aliases`, and full algebra flags on day one.** `functional` (scoped — see below) is the only algebra that earns its keep for §5. Transitive/symmetric/inverse materialization is solving OWL-ish graph completion you will not run seriously at 10⁴–10⁶ before the identity/conflict bugs land.
- **`stated_confidence real` on every attribution.** Nobody calibrates it across agents; it will be null or noise. Agreement is already `COUNT(DISTINCT agent)` over evidence. Add confidence later as an optional qualifier on the attribution record if a source actually states one.

---

4. **The seven open questions**

1. **Split: right direction, wrong completeness.** Assertion vs attribution is correct; confidence on attribution is correct; merge-as-union of assertion hashes is correct *only for byte-identical claims*. It fails on reification variance (qualifiers vs roles), object sort drift (`time` vs `text` “1907-05-22”), and any subject not already the same string. Content-addressing is the right primitive for immutable payloads, **wrong** as the sole epistemic merge key without a normal form for time, measure, and core qualifier roles. **Wrong** as stated if you believe independent extractors will collide hashes in the wild at useful rates.

2. **Modality absent: not a Layer-0 mistake** if modality lives on the agent profile or as an open qualifier (`epistemic: reported`). **Wrong** to later bolt a closed modality enum onto the assertion tuple — that double-counts agent policy and forces migration. Keep it off the assertion.

3. **Qualifiers: wrong cut.** Fully open qualifier predicates with identity inside the hash make canonicalisation and conflict undefined across stores. Close the small set that affects identity and contradiction:

```text
qual_kind := valid_time | invalid_time | location | degree | under_assumption | according_to | rank
qualifiers := set of (qual_kind, value)   -- value still typed by sort
```

Everything else is either a separate assertion or an attribute of the attribution (provenance), not part of assertion identity. Open *values*, closed *roles*.

4. **Namespaced refs + defeasible `sameAs`: survives federation only if all conflict rules run modulo an equivalence view.** As written, storage-level §5 does not. Query-time full closure is not the first bottleneck at 10⁶; **incorrect non-detection** is. Materialize equivalence classes in Layer 4 and define:

```text
functional_conflict ≡
  ∃ s1,s2 in same class, same p, same closed-quals, o1 ≠ o2, functional(p)
```

Without that definition, the identity story is decorative.

5. **Forces Layer 0 within a year:** assertion/attribution as object sorts (retraction/dispute/aboutness), **or** predicate-card merge semantics entering the closed grammar, **or** closed temporal/identity qualifier roles. The first is the one you should take now; see §2.

6. **At 10⁶ on one Postgres:** not row count. First pain is **query plans that expand `sameAs` + multi-hop + gather attributions + conflict check** over `qualifiers jsonb` with weak indexes, and **near-duplicate assertion fanout** (same fact, different hashes) blowing up “current answers.” Secondary: FK/`predicate` coordination on ingest. 10⁶ bare assertions with `(subject,predicate)` indexes is otherwise easy.

7. **Derive transitive/inverse: correct — do not store in Layers 0–3.** No reason to persist them as facts; materialize in Layer 4 only for hot paths. **Wrong** only if you pretend deep transitive closure at query time over dense relations without bounds — bound depth in the IR, keep derived edges disposable.

---

5. **What breaks first at scale**

**10⁶ on one Postgres**

- Survives as bulk storage.
- Breaks first: **read path** — per-question graph expansion with conflict detection and attribution assembly once entity links and qualifier filters enter; `qualifiers jsonb` and `object jsonb` resist the selective indexes §5 needs (functional collisions, time overlap).
- Fix shape (concrete):

```sql
-- closed qualifier roles as columns / side tables, not opaque jsonb in the hash input only
CREATE TABLE assertion_qual (
  assertion bytea REFERENCES assertion(hash),
  kind text NOT NULL,  -- valid_time|...
  value jsonb NOT NULL,
  PRIMARY KEY (assertion, kind, value)
);
-- functional collision aid (only for predicates marked functional)
CREATE INDEX assertion_functional
  ON assertion (subject, predicate, polarity)
  WHERE /* predicate.functional joined or denorm bit */ true;
```

Also replace `bigserial` on `attribution` / events with **content-addressed ids** (`sha256` of canonical attribution payload). Surrogate ids are store-local and already wrong for federation at any size.

**Merging two stores of 10⁶**

- Assertion hash union is fine when bytes match.
- Breaks first: **(1) predicate card conflicts** (semantics of the whole graph flip or merge aborts); **(2) near-duplicate explosion** (same facts, different qualifier/object canonical forms → ~2× claims, agreement metrics collapse); **(3) `sameAs` bridges** turning two locally consistent functional worlds into one web where §5 still does not fire; **(4) attribution/event surrogate keys and `recorded_at DEFAULT now()`** (ingest time is not evidence time; merge rewrites identity of provenance rows).
- Merge is not “set union of four tables.” You need explicit CRDTs:

```text
assertion    : G-set by hash
attribution  : G-set by attribution_hash
predicate    : per-id observed card versions as assertions about predicates
               e.g. (pred:date_of_birth, card_functional, true, +, {})
               — never a single mutable row
sameAs       : ordinary assertions; closure = Layer 4 only
```

Until predicate algebra and conflict-mod-equivalence are claims/views with freeze-able rules, two large stores do not merge into one epistemology; they merge into a quieter, larger mess.


[stderr] 

Changes    +0 -0
Requests   1 Premium (1m 49s)
Tokens     ↑ 54.4k (26.5k cached) • ↓ 4.5k (2.2k reasoning)
Resume     copilot --resume=c5033193-a3f2-40c0-a09f-0cb6c3f107d3
