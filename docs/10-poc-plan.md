# PoC plan — "foundation" research-memory service (agreed with user 2026-07-27, D76)

User decisions: **gates first, then demo** · **CLI interface** ·
**Wikipedia + ArXiv slice** corpus · **templates + citations** answers
(decoder stays out of the loop).

## What the PoC is

A CLI tool over the measured stack: ingest a subject area from Wikipedia
(Math + Epistemology neighborhood, ~2–5k pages) plus one ArXiv slice;
answer multi-hop questions with per-answer provenance and honest statuses
(answered / ambiguous / abstain / conflict); supersede facts and show the
ripple; serve "according to X" views; produce grounded subject briefs.
Continual ingest runs on a schedule with invariance checks — the system
*keeps learning* (T7 ladder live) or the PoC has failed its own point.

## Phase G — close the gates (BEFORE assembly; targets unchanged)

- **G1. M1 → ≥0.85**: extraction v3 with the four D75 rules baked into the
  prompt (a work must be a titled artifact; inception binds to the thing
  created; "lived c. X" is not a birth date; founder/owner direction) plus
  a VETO-ONLY checker agent validating each (statement, pid) against
  exactly those rules (vetoes can only null, never add — the D72
  precision lesson). Audit: fresh 100-sample, labels committed before the
  score is computed (D75 procedure).
- **G2. M3 recall → ≥0.5 raw**: full-article text (not 8k), same statement
  discipline; precision must hold ≥0.6 and links ≥0.8 (no
  trade-one-gate-for-another). Conflict detector rebuilt FUNCTIONAL-ONLY
  (D74) in the same pass.
  *Instrument amendment (D78, committed before the scoring run it judges)*:
  the precision gate is scored on INFOBOX-COMPLETE pids
  (P569/P570/P19/P20/P26/P27), where the infobox enumerates the full value
  set and a non-match is genuinely wrong. For multi-valued pids the infobox
  truncates by design — the frozen 25-fp audit found 24/25 all-pid "fps"
  were true facts absent from the infobox (the one real error was on a
  functional pid). All-pid precision remains in every artifact as the
  lower bound. Same move as D74's functional-only conflicts: score
  correctness where ground truth is complete, not coverage of a
  deliberately truncated summary box.
- **G3. M2 recoverability**: pairwise-F1 ≥0.80 vs the registry partition,
  beating the surface-only baseline by ≥15 points (registered targets).
- **G4. M5 grounded synthesis**: subject_brief with per-sentence citations;
  entailment-judged faithfulness ≥0.9 (n=50), distractor-subgraph refusal
  ≥0.8, planted-dispute surfacing ≥0.8.
- **G5. M7 soak STARTS now**: nightly cron ingest + J4-invariance checks;
  runs through Phase B; weekly headline metrics within CI of day-0.
  Starting early means the PoC ships with weeks of soak evidence.

## Phase B — build (after G1–G4 green)

- **Package restructure** (earned at last): `foundation/` — store backends,
  registry, reasoner, ingest, `cli.py`. Probes stay in `scripts/` as the
  lab notebook; the batteries become the regression suite.
- **CLI**: `foundation ingest <topic|arxiv-id> [--depth]`, `ask`, `edit`,
  `views`, `brief`, `status` (store size, soak health, gate regression).
- **Corpus**: Wikipedia neighborhood (2–5k pages, verified-envelope scale)
  + ONE ArXiv slice (math.LO or similar, abstracts+intros first) ingested
  as CLAIMS with provenance — attributed statements, Track I views across
  papers, functional-only conflicts. ArXiv is the stretch axis: its
  acceptance is extraction precision ≥0.6 on a 50-claim audit, not the
  full gate battery.
- **Answers**: store entries rendered with citations; briefs = LLM reads
  retrieved entries with enforced per-sentence citation (G4 machinery).
- **Demo script = acceptance test**: `scripts/demo.sh` runs the five acts
  (ingest → ask → edit-ripple → views → brief) against a FRESH database;
  green run + gate regressions within CI = PoC done.

## Out of scope (logged so drift is visible)

Decoder prose, federation protocol (schema stays ready), self-imitation,
multimodal, open-vocabulary relation induction, big_pop-class detector
generalization (coverage-fixable, not a PoC blocker).

## Risks, named

ArXiv claim extraction is the honest stretch (prose is harder than
encyclopedia leads; mitigated by abstracts-first and the veto checker);
gate G2 may trade against precision (both gates enforced simultaneously);
agent-fleet reliability at scale (mitigation measured: ~13-page shards,
single-Write discipline, gap re-sharding as standard procedure).
