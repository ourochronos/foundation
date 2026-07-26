# Entity individuation — symbolic-channel v2 design (2026-07-25)

**Why now (D46/D48):** the id channel identifies entities by *surface token
sets* (`id_tokens`). Two entities named "North Halmelton" are one entity to
the store — measured as the SOLE cost of doubling the store (collided
execution 0.488 vs clean 0.964, D46). The dual failure — one entity with two
surface forms — blocks aliasing (K5 exclusion). Both are the same missing
mechanism: **identity ≠ surface form**.

**Design position (extends D38/D40):** individuation is STORE CONTENT, not
model knowledge. Surface forms are contingent facts about the world
("this city is called X; also X-upon-Sea"); the binding of forms to
individuals lives in the store like every other contingent fact. Nothing
here trains a model. Numbers and years are VALUES, not individuals — "4200"
is the same 4200 everywhere — and stay surface tokens (D3's split, kept).

## Mechanism

### 1. Entity registry (new entry kind)
One registry entry per individual:

```
eid            opaque id ("e00417"), minted at first mention
surface_forms  growable set of strings ("North Halmelton", "N. Halmelton")
profile        participation vector (derived from the eid's facts; cached,
               recomputed on the medium timescale like all signatures)
anchor         mean gist of the eid's facts (cheap dense context for
               resolution tie-breaks)
redirect       optional eid -> eid (see merges)
```

Fact entries change one field: `ids` becomes a set of **eids + number
tokens** (mixed set; number literals keep surface form).

### 2. Write-time resolution (surface mention → eid)
Closed-form, no learning. For each entity mention in an incoming fact:

1. **Candidates**: registry entries with surface-form token overlap ≥ τ_surf.
   No candidates → mint new eid.
2. **Type gate**: candidate's participation profile must be compatible with
   the mention's role (cos(profile, dom/rng of the incoming relation) ≥
   τ_type). A person-eid named like a city does not absorb city facts.
3. **Functional-conflict gate**: if the incoming fact's relation is
   functional (one object per subject — derivable from the store: max
   objects-per-subject ≈ 1) and the candidate already holds a CONFLICTING
   object: (a) incoming text carries event/supersession phrasing → this is
   an EDIT: same eid, route to `supersede` (existing D33 machinery);
   (b) no event phrasing → these are different individuals: mint new eid.
   This is where individuation and supersession meet, and the ordering
   matters: conflicts are evidence of DISTINCTNESS unless marked as change.
4. **Neighborhood score**: among survivors, prefer the candidate whose
   existing facts share arguments with the incoming fact's other argument
   (one-hop overlap count); tie-break by anchor cosine. Score below τ_nb →
   mint new eid (provisional; merges can repair later).

Thresholds are calibrated on the synthetic unions where ground truth is
known by construction (seed-41 vs seed-43 individuals are distinct;
within-seed repeat mentions are same) — counting, not gradient descent.

### 3. Query-time resolution
`qids_of` yields surface mentions; candidates = eids carrying that form.
Disambiguate with what the planner already computed: the first chain
relation's domain profile (type gate) + anchor cosine to the question gist.
If >1 candidate survives: **execute all, return best-scoring walk flagged
`ambiguous`** — silent disambiguation is how wrong answers happen; the flag
is the honest output and (later) the hook for clarification behavior.

### 4. Walker
Unchanged algorithm; `hand = ids(cur) − ids(handed-in)` becomes eid-set
algebra. This also removes a KNOWN token-granularity fuzz: today "North
Halmelton" hands off {north, halmelton} and "north" collides with every
other North-prefixed name in the mask. Eids make the D43 mask exact.

### 5. Merges (aliases discovered late)
Evidence two eids are one (an explicit equivalence fact "X is also known as
Y", or resolution hindsight): write `redirect: e2 → e1`; e1 absorbs surface
forms; e2's fact entries stay untouched (provenance) and resolve through
the redirect at read time. Same philosophy as supersession: never rewrite
history, redirect the address. Redirect chains are collapsed on the slow
timescale.

## What this does NOT do
- No cross-document coreference resolution ("the company" → eid) — that is
  a codec/ingest concern, out of scope here.
- No learned resolver. If closed-form resolution proves insufficient on
  natural data (K6), a learned scorer becomes a candidate — gated by the
  frozen-template discipline (D48).

## Pre-registered acceptance tests

**Status 2026-07-26 (D52): test 1 PASSED** — path-collided 0.948 (≥0.90 ✓), clean 0.978, entry-ambiguous flagged at 1.000 recall (amendment in D52: entry-ambiguity is unanswerable-as-posed; the flag is the metric). Implementation note: v1.1 uses BATCH LOCALITY in place of the write-time profile gate (cold-start circularity); tests 2–4 pending.
1. **J4 rerun** (`probe_store_growth.py` + resolver at write time):
   collided-case execution ≥ 0.90 (parity with clean 0.964 within CI);
   clean cases within CI of current; planning stays chain-Δ 0.000.
2. **Alias probe**: 200 v4 single queries rephrased onto alias surface
   forms after alias registration; target ≥ 0.90 × canonical-form P@1.
3. **Ambiguity honesty**: constructed set where two same-form, same-type
   eids both support the queried relation and the question underdetermines;
   flag-rate ≥ 0.9 on ambiguous vs ≤ 0.05 spurious flags on clean.
4. **Edit interaction**: D33 edit-stress battery unchanged (supersession
   must not regress when eids replace token sets).

Failure of test 1 falsifies the design's core claim (that individuation is
the whole growth tax); partial success localizes what else surface tokens
were doing.
