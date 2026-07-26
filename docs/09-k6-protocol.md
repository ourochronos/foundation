# K6 protocol — first external benchmark (pre-registered 2026-07-25)

Written BEFORE any test-set contact. Changes after first contact are
amendments, logged in decisions.md with the reason (A5 discipline).

## Choice: MQuAKE-CF-3k (primary), MQuAKE-T (secondary)

**Why MQuAKE over MuSiQue/MemoryAgentBench for the first shot:**
- Facts arrive as (subject, relation, object) triples — no natural-text
  proposition extraction stage, which we haven't built and which would
  confound the store/reasoner evaluation with an ingest component.
- Its task IS our differentiator: multi-hop questions whose answers must
  change after knowledge edits (ripple effects) — supersession + hop
  machinery end-to-end, the thing parameter-editing methods (ROME/MEMIT
  lineage) measurably fail at.
- Real entity names force the individuation/alias machinery (docs/08) on
  natural data — MQuAKE runs AFTER individuation lands, as its first
  non-synthetic test.
- MuSiQue stays queued (Track D1) for the reading-comprehension axis once
  an ingest path exists; MemoryAgentBench FactConsolidation stays the
  consolidation-stream shot (G5).

## System under test
- Frozen BGE-M3 + whitening (fit on OUR corpus — no MQuAKE-side refit).
- Store built from each case's fact set; **two settings, both reported**:
  (a) *per-case store* (comparable to MeLLo-style baselines),
  (b) *pooled store* (all cases' facts + edits in one store — distractor
  pressure + cross-case name collisions; the honest setting).
- Edits applied via `supersede` (address inheritance, D33).
- Relation inventory: MQuAKE's ~37 Wikidata relations. Operators fit
  closed-form from verbalized (question, fact) pairs of the TRAIN split.
  Detection + answer-type heads retrained on train-split questions only
  (deferred until the training pause lifts — everything else in this
  protocol is train-free prep).
- Verbalization: one fixed template per relation, written before test
  contact, committed with this doc's hash in the result manifest.

## Metrics (theirs + ours)
1. Multi-hop accuracy after edits (MQuAKE's primary), per hop-count.
2. Pre-edit multi-hop accuracy (sanity: the store answers the unedited
   world).
3. Edit-wise consistency: single-hop edited-fact recall (did the edit
   land) vs multi-hop propagation (did it ripple) — the gap is the
   headline number in the editing literature.
4. Abstention honesty on MQuAKE's unanswerable-after-edit cases (where an
   edit removes the chain): flag rate ≥ 0.8 at ≤ 0.05 false-abstain.
5. Wall-clock per question on the RX 9070 (matched-latency reporting).

## Baselines
- **(B1) Matched-scale retrieval+LLM** (the primary comparison, run
  locally): BGE-M3 retrieval (same embeddings, same store content, edits
  as appended text with recency preference) → Qwen3-0.6B reads top-k and
  answers. Same encoder, same parameter scale as our decoder — isolates
  the architecture (operators/typed planning/supersession) from capacity.
- **(B2) MeLLo** published numbers, as context (different base models —
  reported, not claimed against).
- **(B3) Parameter-editing published numbers (ROME/MEMIT on MQuAKE)** as
  context for the ripple-effect gap.

## Pre-registered success criteria
- **Pass**: beat B1 on post-edit multi-hop accuracy in BOTH store settings
  with non-overlapping 95% CIs, at comparable or better latency.
- **Strong pass**: additionally, edit-propagation gap (metric 3) smaller
  than B1's by ≥ 10 points absolute.
- **Informative fail**: lose to B1 → per-stage attribution (detection /
  planning / execution / supersession) using the D46-style split before
  any redesign. Every outcome gets a decisions.md entry.

## Known threats, stated up front
- 37 relations is 4× our detection head's output space; typed unification
  has only been tested at 9 relations with clean signatures — Wikidata
  domains/ranges are dirtier.
- Verbalization templates are a free parameter we control; committing them
  pre-contact and reporting template-sensitivity (3 alternates on the train
  split only) bounds the garden of forking paths.
- Some MQuAKE questions need relations our store treats as non-functional;
  functional-conflict logic (docs/08 §2.3) must not misfire as spurious
  supersession — covered by acceptance test 4 there.

## Prep that respects the training pause (can run now)
Download + license check, case-format loader, verbalization templates,
store-ingest script, B1 harness skeleton, per-case/pooled store builders.
Head training and the actual runs wait.
