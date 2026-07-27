# Extraction-time identity — pre-registered protocol (2026-07-27)

Registered BEFORE any run, per the D64 criteria-drift rule. Criteria,
instruments, and predictions below are frozen at commit time.

> **RESULT (D94, same day).** Arm A **PASSED** every criterion —
> subjects/claim 0.912 → **0.373**, singleton rate 0.935 → **0.114**,
> statement precision **0.88 [0.76–0.94]** vs baseline 0.82 [0.69–0.90]
> (no regression), claims/paper *up*. Arm B **FAILED**: it linked
> nothing at all, 148 entities → 148 declines, cross-paper rate 0.000.
> The reason is that the shared entities are not in subject position —
> papers' subjects are their own new methods. Full analysis, plus two
> registered defects in this document's own instrument, in D94.
>
> **Criterion defect found by the run, corrected here for any re-run:**
> `decline rate > 0` is one-sided. It catches an extractor that links
> everything; it does NOT catch one that links nothing, which passes at
> 1.000 and makes every other Arm B criterion vacuous. The correct
> bound is **`0 < decline rate < 1`**. Any future linking arm must also
> use balanced prompt language — Arm B's decline-heavy wording is a
> confound, so this run tested the prompt's caution, not the model's
> ability to link.

## What provoked it

User proposal: rather than treating identity as a downstream
pre-processor, let the extracting model consult the store while reading
a source, so it can reuse identities and relations the store already
holds. Counter-consideration raised in the same breath: source-specific
deterministic preprocessing still earns its keep.

## What the corpus actually shows (measured 2026-07-27, before design)

**The fragmentation is at CLAIM level, not paper level.** D92 reported
"zero subjects spanning more than one paper" over the AI slice. That
understated it. Over 514 arXiv papers / 1,403 `P_ASSERTS` claims:

| quantity | value |
|---|---|
| claims per paper | mean 2.73, median 3 |
| distinct subjects per paper | mean 2.55, median 3 |
| **distinct subjects per claim** | **0.933** |
| subjects used by exactly one claim, within their own paper | **1,244 / 1,309 (95%)** |

Every claim coins its own subject. There is essentially no entity
structure in the slice at all — not "papers name their own methods" but
"each claim names its own thing." One paper (arXiv:2607.21570) carries
five distinct eids for one system: *MedGame interactive platform*,
*MedGame framework*, *MedGame Bench dataset*, *MedGame user perception*,
and the paper title. Same shape for SHIFT (4), van Benthem (3),
LoRA-STORM/NSGDM (2), DLMRec (2).

**Consequence for the design: the dominant term needs no store.** Most
of the missing structure is *within a single source document*, where
consolidation is a shard-local operation — stateless, parallel-safe,
reproducible, no self-confirming loop.

## Retrieval feasibility (probed before design, `scratchpad/probe_lookup.py`)

Embedded all 14,649 entity canonical forms (BGE-M3 dense) and queried
with 25 real AI subjects. Dense lookup DOES surface the right entity —
and cannot be trusted on score alone:

- true same-entity, same paper: 0.68 – 0.87
- **false cross-domain bleed at the same or higher scores**: *topological
  pressure* → *topology* (Wikipedia, 0.775); *coding theory connection* →
  *approximation theory connection* (0.782); *finite-sample toolkit* →
  *finite set* / *finite simple groups* (0.687 / 0.644); *voluntary
  memory in agents* → *Long-term working memory* (0.648, on the **Child
  prodigy** page); *std normalization ablation* → *Renormalization
  procedure* (Quantum field theory, 0.613)
- genuine relatedness that is NOT identity: *PATS policy-centric
  training* → *Group-in-Group Policy Optimization for LLM Agent
  Training* (0.760, different paper — related work, not the same thing)

**The score distributions overlap; no threshold separates them.** This
is D41's law restated at ingest: evidence proposes, types dispose —
compatibility is a feasibility GATE, never a score term. A raw-cosine
linker is the additive version that collapsed in J3 v2.

## Arms

Shared: 100 held-out AI papers (5 shards × 20). To avoid self-linking,
the experiment store is rebuilt WITHOUT the held-out papers' own
`P_ASSERTS` claims. Their **citation** claims stay in — a paper whose
title is already an object of someone's `P_CITES` is the realistic
incremental-ingest case, not contamination.

- **Arm 0 — baseline.** The existing extractions of those same 100
  papers. Already measured; no run needed.
- **Arm A — source-local consolidation.** Prompt requires naming a small
  entity set for the paper FIRST, then attaching every claim to one of
  those entities. No store access. Everything else identical to the D92
  prompt.
- **Arm B — store-aware linking.** Arm A plus a per-paper candidate list
  precomputed from the paper's own title+abstract against the experiment
  store (top-k entity forms, each **tagged with its source page** so
  Wikipedia general concepts are visibly not arXiv methods). The
  extractor may attach `link: <eid>` to a subject, or decline. It never
  invents an eid and never merges two existing eids.

Candidates are precomputed from the source, so the fleet stays parallel
and each shard input records the exact candidate list it was given —
extraction remains reproducible from the shard inputs alone.

## Instruments

1. **Entity structure** (mechanical): subjects/claim, claims/entity,
   entities/paper, cross-paper subject rate.
2. **Statement precision** — the D92 frozen-audit instrument applied
   **verbatim, unchanged**: 50 claims, seed 17, graded against the source
   abstract on the same threshold. *The `statement` field stays strictly
   source-faithful in every arm; only `subject`/`object`/`link` may be
   store-informed.* This is the criteria-drift guard: no existing
   instrument is amended, so arms stay comparable to D92's numbers.
3. **Link precision** — a NEW instrument for a new claim type. 50
   proposed links, frozen labels, judged "does this subject denote the
   same entity as the linked eid?" Sol adjudication before the D-entry
   closes.
4. **False-merge controls** (D8 house rule — every probe ships a
   positive control for the effect it tests):
   - *natural decoys*: cross-domain candidates (Wikipedia entities) are
     present in every candidate list and unremoved. Any AI-method →
     Wikipedia-general-concept link is a false merge; count them.
   - *planted decoys*: 2 per shard, a confusable-but-distinct entity
     injected into the candidate list. If the instrument cannot catch a
     planted merge, it cannot certify the natural rate.

## Pre-registered acceptance criteria

**Arm A passes** if all three hold:
- subjects/claim **≤ 0.60** (from 0.933);
- statement precision CI overlaps Arm 0's — **no regression**;
- no new defect family appears in the audit.

**Arm B passes** if all four hold:
- cross-paper subject rate **> 0.10** of subjects (from 0.000);
- **link precision ≥ 0.90** on the frozen 50-link audit;
- **zero** AI→Wikipedia false merges, and every planted decoy declined;
- decline rate **> 0** — if the extractor links every candidate offered,
  the gate is decorative and the arm fails regardless of precision.

Either arm may pass alone. Arm A passing while Arm B fails is a
publishable outcome: it would say identity belongs at the source, not at
the store.

## Predictions (recorded now, scored later)

1. Arm A captures **most** of the entity-structure gain, because 95% of
   the deficit is within-source.
2. Arm B adds cross-paper linkage but is where precision risk
   concentrates; its failures will be *related-work* links (topic
   neighbours mistaken for identity) rather than random noise.
3. Cross-domain bleed will appear at a measurable non-zero rate even with
   provenance tags visible, because the probe shows the embedding cannot
   separate those cases.

## What each outcome would mean

- **A passes, B passes** → adopt both; identity proposal moves into
  extraction, resolver stays authoritative.
- **A passes, B fails** → adopt A only; store-awareness needs a typed
  gate (relational participation, D41) before it is safe. Cheapest good
  outcome.
- **A fails** → the naming behaviour is not promptable and the fix is
  architectural (a consolidation pass, not an instruction).
- **B's decline rate is 0** → treat any B precision number as unearned;
  re-run with planted decoys weighted up.

## Standing constraints this run must not violate

- `statement` stays extractive and source-faithful (G4/D81
  quote-never-reconstruct, applied to ingest: text faithful, symbols
  canonical).
- The extractor proposes; `codec/individuation.py` disposes. No arm
  writes an eid the resolver did not mint, and ambiguity still flags
  rather than merging (D49/D52 — a false merge is unrecoverable, a false
  split is repairable by redirect).
- Shard inputs remain frozen once a fleet has run over them.
