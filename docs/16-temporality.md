# Temporality — design notes, not yet built (2026-07-28)

Captured while the reasoning is fresh so the next session starts from a
position rather than a blank page. **Nothing here is implemented.** The
one claim that IS measured is the view mechanism this design leans on
(D60), and it is cited as such.

## The question that started it

*"How much is time a concept rather than a specific UTC second?"*

In this corpus, mostly a concept. Papers assert relative to a **state of
the field**: "before instruction tuning", "as of Qwen3", "prior work
used GANs", "recent frameworks such as X". Almost none of that reduces
to an instant. Wikipedia facts do the opposite — `P569` birth dates are
points, and a person is born at a moment.

So the corpus holds **two kinds of time**, and a `timestamp` column
models only one of them. Building the point-in-time version first would
be building for the minority case, and the columns to do it already sit
unused in the PgStore DDL, which is evidence it was never the blocker.

## The idea: time is a VIEW, not a column

D60 measured something that generalises further than it was used for. A
*view* is nothing but a source token in an entry's id set; a
source-qualified query adds that token to its query ids and the ordinary
overlap rescoring selects the view. **Zero new mechanism** — measured at
0.970 qualified-view P@1, conflict flagging 0.920 with 0.000 spurious.

The observation: **"according to Meridian Atlas" and "as of 2024" are
the same kind of qualifier.** Both say *under which frame is this
assertion being made*. One is provenance, one is time, and the store
already has a working, measured mechanism for the first.

So: a temporal token in the id set, exactly like a source token.

```
claim:  Qwen2.5 --P_EVALUATES_ON--> MMLU     ids: {…, t:2024, src:arxiv:…}
query:  "what did people evaluate on in 2024"  query ids: {…, t:2024}
```

**Why this is better than a column here**, specifically:

- A token does not have to be a point. `t:2024`, `t:pre-instruct-tuning`
  and `t:post-chatgpt` are all just tokens, so **fuzzy conceptual
  intervals cost nothing** — which is the majority case in this corpus.
- Conflicting-across-time facts land on the *same* machinery as
  conflicting-across-source facts: they sit side by side, attributed,
  and the default behaviour is honest disagreement rather than silent
  overwrite (D40 tiers, D60).
- It composes: `{t:2024, src:arxiv:2501.x}` is "what that source said
  then", with no new query language.
- It is append-only, so it does not touch the reindex-free property
  (B1/B1b — nothing old is re-projected).

## What must be decided before building

1. **Token vocabulary.** Free-form tokens will fragment exactly the way
   relation strings did at D61 (688 relations from 1,771 triples) and
   resource names did before the granularity policy. Time needs a
   declared granularity the way resources got one: probably year plus a
   small closed set of named eras, with the same "declare it in the
   prompt AND the audit instrument" rule (D102).
2. **Which time.** At minimum three are distinguishable and they are not
   interchangeable: when the source was *published*, when the claim was
   *ingested*, and when the claim is *asserted to hold*. The corpus has
   good data for the first (arXiv `published`, and revid-pinned wiki
   provenance), free data for the second, and almost none for the third.
   **Start with publication time** — it is free, unambiguous, and
   already on every paper record.
3. **Does anyone ask?** No trace evidence yet that temporal queries are
   wanted; the trace layer (D108) is the instrument that would show it.
   Deferred deliberately on those grounds — capability without demand is
   how the tail-typing filters got built twice before being measured.

## Prior art already in the repo

- **D60 / v4b**: views as id-channel content — the mechanism this reuses,
  with numbers.
- **D40**: contingent-knowledge tiers; conflicting facts coexist,
  attributed.
- **Supersession** (`edit`, `invalidated_by`, replay-edits): a working
  *transaction-time* story already — an edit does not delete, it
  shadows, and the shadowed row is still there.
- **Bi-temporal columns** in PgStore's DDL (`validity`, `invalidated_by`,
  `source_ref`): present, deliberately unused, "cheap as columns, brutal
  to retrofit".
- **`source_ref = title@revid`** on wiki claims: point-in-time provenance
  that already works.

## The trap to avoid

Token hygiene is a stated constraint (D60): `id_tokens` splits on
punctuation, which once silently broke `src:meridian` into two tokens
and cost a rerun. Any `t:` convention must be normalisation-safe before
a single claim is written with it.

## Smallest honest first step, when demand appears

Attach `t:<year>` from the arXiv `published` field to resource claims —
free, no extraction, no judgement — then ask the trace layer whether
anyone qualifies a query with it. If nobody does, the concept was not
the blocker and this document was cheap. If they do, the vocabulary
question in (1) becomes the real work.
