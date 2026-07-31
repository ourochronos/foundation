# Data model v0 — for review, not for commitment

The closed layer is authored once and is expensive to change later, so this is
written to be attacked before anything is built on it.

Design pressure comes from four requirements held simultaneously:

1. **Never rebuild the data.** Derived indexes may be rebuilt freely; claims,
   identity and provenance may not.
2. **Federate.** Independent stores must merge without coordination.
3. **Preserve disagreement.** Contradiction is normal and must survive merge,
   not be resolved at write time.
4. **Stay efficient on one machine.** Postgres + pgvector, ~10⁴–10⁶ claims.

Requirements 2 and 3 are not independent: **merging guarantees contradiction**,
so a federated store that resolves on write is incoherent. Preserving
disagreement is forced, not chosen.

---

## 1. The central move: assertion vs attribution

The single most consequential decision here. A fact splits in two:

- An **assertion** is *what is claimed*. Immutable, content-addressed, no
  author. `(subject, predicate, object, polarity, qualifiers)`.
- An **attribution** is *someone claiming it*. Append-only, references an
  assertion by hash, and carries agent, evidence, time and stated confidence.

Two stores that independently extract the same fact from different sources
produce **the same assertion hash** and **different attributions**. So:

- **Merge is set union.** An append-only set of immutable, content-addressed
  assertions is a grow-only set — the simplest CRDT there is. No coordination,
  no write conflicts, no merge algorithm to get wrong.
- **Agreement becomes countable.** "How many independent agents attribute this
  assertion, from how many distinct sources?" is a `COUNT`, not a heuristic.
  Federation does real epistemic work instead of just increasing volume.
- **Confidence cannot be a column.** It lives on the attribution, because it is
  an opinion held by an agent. A confidence field on the assertion would bake
  one store's epistemics into everybody's data on merge.

## 2. Layer 0 — the grammar (CLOSED, authored once)

Everything here is finite and frozen. Note the distinction that took the panel
to see: **the grammar closes, the vocabularies do not.**

**Sorts** — the complete set of things an object can be:

    entity | text | quantity | time

`quantity` carries a unit; `time` carries an instant-or-interval and a
precision. That is all four.

**Assertion shape:**

    assertion := (subject: entity,
                  predicate: predicate_ref,
                  object: entity | text | quantity | time,
                  polarity: + | −,
                  qualifiers: set of (predicate_ref, value))

**Attribution shape:**

    attribution := (assertion: hash,
                    agent: entity,
                    evidence: (document, content_hash, locator, quoted_span),
                    recorded_at: time,
                    stated_confidence: quantity | null)

**Event kinds** — the complete set:

    asserted | superseded | withdrawn | disputed

Events are append-only and reference assertions by hash. Nothing is ever
deleted or mutated; supersession is an event, not an `UPDATE`.

**Query operators** — the complete set the compiler may emit:

    hop | filter | join | count | compare | aggregate | refuse

That is the whole closed layer. Roughly fifty lines, authored once, frozen.

**Polarity is explicit and load-bearing.** `¬P` present is not the same as `P`
absent: the first is knowledge, the second is ignorance. A store that cannot
distinguish them cannot refuse honestly.

**Modality is deliberately absent** from v0 — "hypothesised", "reported",
"modelled" are expressible as a qualifier or as a property of the attributing
agent. Adding a modality field is easy later; removing one is not. Flagged for
the panel.

## 3. Layers 1–3 — open, append-only

**Entities** are namespaced references, not opaque local ids:

    wikidata:Q42    doi:10.1000/xyz    local:7f3a…    orcid:0000-…

Cross-store identity is **a claim, not a key**:

    (local:7f3a, sameAs, wikidata:Q42, +, {})

...with its own attributions, and therefore contestable and defeasible. This is
the known failure mode of `owl:sameAs` in linked data, where it was treated as
free and became unreliable at scale. Here two stores may disagree about whether
two entities are the same, and nothing is corrupted by the disagreement.

**Consequence**: identity resolution is a **view** (Layer 4) — computed,
disposable, rebuildable — not a property of storage. Merge stays a pure union
because it never has to decide anything.

**Predicates** are rows in an open vocabulary with a closed card shape:

    predicate := (id, name, aliases[], definition,
                  domain_sort, range_sort,
                  algebra: {symmetric, transitive, functional, inverse_of},
                  category)

A new predicate is a new row. No refit, no basis, no retraining — the
never-reindex property for relations comes from *appending a row*, which is
what the anchor basis was built to avoid and never needed to.

`functional` does real work: it is how contradiction is detected without
explicit negation (§5).

## 4. Layer 4 — views (derived, disposable, rebuildable)

Everything fitted lives here and nothing outside depends on it for identity or
truth:

- embeddings, keyed by `(target, model_id)` — a new encoder appends rows
- ANN indexes (HNSW is append-friendly)
- the `sameAs` equivalence closure
- derived edges from predicate algebra (transitivity, inverses) — Datalog-style
  incremental evaluation, *derived not stored*
- materialised "current best answer" projections

**This layer is what makes the never-reindex constraint honest.** Layers 0–3
never rebuild. Layer 4 rebuilds whenever it likes, because it is a cache.
Blurring these two is what forced the anchor basis into existence.

## 5. Contradiction — detected, never resolved

Three detectable forms, all computable at query time from declared information:

1. **Polarity conflict** — identical `(s, p, o, quals)` with `+` and `−`.
2. **Functional conflict** — same `(s, p, quals)`, different `o`, where the
   predicate card declares `functional`.
3. **Constraint violation** — declared disjointness or a domain/range rule
   (Layer 5), checked on append and recorded as a `disputed` event rather than
   a rejection.

A query returns **all** surviving answers with their attribution sets and
qualifiers. It never picks. The renderer's job is to say *"A according to
these sources under these conditions; B according to those"* — and when
attributions are thin or evidence is absent, to refuse.

This is where the project's refusal machinery earns its place, generalised
from "refuse a type-mismatched answer" to "refuse to collapse a real
disagreement."

## 6. Worked examples

**(a) Ordinary fact, two independent sources.** One assertion row, two
attribution rows. Agreement is `COUNT(DISTINCT agent) = 2`.

    A₁ = (wikidata:Q42, place_of_birth, wikidata:Q350, +, {})
      ← attribution(agent=local:extractor_v3, doc=wiki:Douglas_Adams, span=…)
      ← attribution(agent=remote:alice, doc=britannica:…, span=…)

**(b) A fact that stopped being true.** Two assertions, both permanently true
*of their intervals*. Neither supersedes the other; the qualifier does the
work.

    A₂ = (wikidata:Q76, position_held, us_president, +, {valid_time: 2009…2017})
    A₃ = (wikidata:Q6279, position_held, us_president, +, {valid_time: 2021…2025})

**(c) Genuine disagreement.** `functional` on `date_of_birth` makes these
conflict without any negation. Both are kept; the query returns both, with who
says which.

    A₄ = (local:x, date_of_birth, 1907-05-22, +, {})   ← agent=source_A
    A₅ = (local:x, date_of_birth, 1907-05-23, +, {})   ← agent=source_B

**(d) Our own audit law #10, as data.** The condition rides on the assertion,
so the number can never be quoted without it.

    A₆ = (exp63, gate_cost, -0.083, +,
          {under_assumption: residual_r_asked, at_depth: 2})

**(e) Federated merge with an identity disagreement.** Store B independently
asserts A₁ (same hash, dedupes on union) but also asserts that its local entity
is the same as ours. We may accept, reject or hold both — it is a claim.

    (remote:b:e88, sameAs, wikidata:Q42, +, {})  ← agent=remote:bob

## 7. Schema sketch

```sql
-- ---------- Layer 2: predicates (open vocabulary, closed card shape) -------
CREATE TABLE predicate (
  id            text PRIMARY KEY,           -- 'place_of_birth'
  name          text NOT NULL,
  aliases       text[] NOT NULL DEFAULT '{}',
  definition    text NOT NULL,
  domain_sort   text NOT NULL,              -- sort enum
  range_sort    text NOT NULL,
  symmetric     boolean NOT NULL DEFAULT false,
  transitive    boolean NOT NULL DEFAULT false,
  functional    boolean NOT NULL DEFAULT false,
  inverse_of    text REFERENCES predicate(id),
  category      text,                       -- structural/causal/temporal/...
  added_at      timestamptz NOT NULL DEFAULT now()
);

-- ---------- Layer 3: assertions (immutable, content-addressed) ------------
CREATE TABLE assertion (
  hash          bytea PRIMARY KEY,          -- sha256 of canonical form
  subject       text NOT NULL,              -- namespaced entity ref
  predicate     text NOT NULL REFERENCES predicate(id),
  object_sort   text NOT NULL,
  object        jsonb NOT NULL,             -- sort-tagged value
  polarity      boolean NOT NULL,
  qualifiers    jsonb NOT NULL DEFAULT '[]' -- sorted [[pred, value], ...]
);
CREATE INDEX ON assertion (subject, predicate);
CREATE INDEX ON assertion (predicate, (object->>'v'));

-- ---------- provenance (append-only, one row per claimant) ----------------
CREATE TABLE attribution (
  id            bigserial PRIMARY KEY,
  assertion     bytea NOT NULL REFERENCES assertion(hash),
  agent         text NOT NULL,              -- namespaced entity ref
  document      text NOT NULL,
  doc_hash      bytea NOT NULL,
  locator       text,                       -- page/section/offset
  quoted_span   text NOT NULL,              -- quote-never-reconstruct
  recorded_at   timestamptz NOT NULL DEFAULT now(),
  confidence    real,                       -- the AGENT's, nobody else's
  UNIQUE (assertion, agent, doc_hash, locator)
);
CREATE INDEX ON attribution (assertion);

-- ---------- events (append-only; supersession is never an UPDATE) --------
CREATE TABLE assertion_event (
  id            bigserial PRIMARY KEY,
  assertion     bytea NOT NULL REFERENCES assertion(hash),
  kind          text NOT NULL,              -- asserted|superseded|withdrawn|disputed
  supersedes    bytea REFERENCES assertion(hash),
  agent         text NOT NULL,
  reason        text,
  recorded_at   timestamptz NOT NULL DEFAULT now()
);

-- ---------- Layer 4: views (disposable, model-versioned) -----------------
CREATE TABLE embedding (
  target        text NOT NULL,              -- entity ref | predicate id | assertion hash
  target_kind   text NOT NULL,
  model_id      text NOT NULL,              -- 'bge-m3@whiten_v0'
  vec           vector NOT NULL,
  PRIMARY KEY (target, target_kind, model_id)
);
```

**Canonicalisation is the part that quietly breaks content addressing**, so it
is specified rather than assumed: sort qualifiers by `(predicate, value)`;
serialise as JSON with sorted keys, no whitespace, UTF-8 NFC; normalise
numbers to shortest round-trip form; normalise times to UTC ISO-8601 with
explicit precision; then `sha256`. Two stores must produce identical bytes for
the same claim or merge silently stops deduplicating.

## 8. Query path

    question
      → LM compiles to typed query IR       (closed operator set)
      → predicate mentions   → 1-NN over predicate cards      (the 0.975 channel)
      → entity mentions      → retrieval over entity names
      → execute as typed graph expansion in SQL, bounded depth
      → group answers, detect conflicts (§5), gather attributions
      → LM renders with provenance, or refuses

The LM appears exactly twice — compiling in, rendering out. It is never the
knowledge, and it never sees a fact that is not quoted from a stored span.

## 9. Open questions for the panel

1. **Is the assertion/attribution split right**, and is content-addressing the
   assertion the right merge primitive — or does it fail on some claim shape?
2. **Modality**: absent from v0. Is that a mistake that will force a Layer 0
   change later?
3. **Qualifiers as an open vocabulary with a closed shape** — right cut, or
   should the qualifier kinds themselves be closed?
4. **Namespaced entity refs + `sameAs` as a defeasible claim**, with resolution
   pushed to a rebuildable view. Does this survive real federation, or does
   query-time closure become the bottleneck?
5. **What forces a Layer 0 change within a year?** The closed layer is supposed
   to be authored once — name the thing that breaks it.
6. **What breaks first at 10⁶ claims** on one Postgres instance?
7. Is there a reason **not** to derive transitive/inverse edges rather than
   store them?
