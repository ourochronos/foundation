I'll inspect the model and experiment evidence directly so the five answers are grounded, not restatements of the brief.

● List directory .
  └ 33 files found

/ Search (glob)
  │ "foundation/model/**/*"
  └ 12 files found

/ Search (glob)
  │ "**/*experiment*"
  └ 1 file found

/ Search (grep)
  │ "corroborat|min_sources|five of six|oppose|scoped" in **/*.{py,md}
  └ 38 files found

● Read query.py
  │ foundation/model/query.py
  └ L1:120 (113 lines read)

/ Search (glob)
  │ "results/**/*"
  └ 257 files found

● Read 26-status-brief.md
  │ docs/26-status-brief.md
  └ 97 lines read

● Read exp69_corroboration.py
  │ scripts/exp69_corroboration.py
  └ L1:120 (120 lines read)

● Read exp72_scoped_conflict.py
  │ scripts/exp72_scoped_conflict.py
  └ L1:100 (100 lines read)

/ Search (grep)
  │ "0 of|corroborat|min_sources|false contradict|near-vacuous|refusal|scoped" in
  │ **/*.{md,json,log,txt}
  └ 493 files found

Pulling the experiment result JSONs next to stress-test the “five of six work” claim.

● Read exp69_corroboration.json
  │ results/exp69_corroboration.json
  └ 77 lines read

● Read exp68_query.json
  │ results/exp68_query.json
  └ 54 lines read

● Read exp67_adversarial.json
  │ results/exp67_adversarial.json
  └ L1:150 (101 lines read)

● Read exp70_registry.json
  │ results/exp70_registry.json
  └ L1:100 (34 lines read)

● Read exp73_axes.json
  │ results/exp73_axes.json
  └ L1:100 (45 lines read)

● Read exp72_scoped_conflict.json
  │ results/exp72_scoped_conflict.json
  └ 22 lines read

Checking extraction and store wiring so the “what to throw away” answer is concrete.

● Read conflict.py
  │ foundation/model/conflict.py
  └ L1:100 (100 lines read)

● Read exp71_extract_positions.py
  │ scripts/exp71_extract_positions.py
  └ L1:80 (80 lines read)

/ Search (grep)
  │ "old model|min_sources|throwaway|live store|backend|class KB" in **/*.{py,md}
  └ 76 files found

● Count model lines and list exp scripts (shell)
  │ wc -l foundation/model/*.py tests/test_*.py 2>/dev/null; ls scripts/exp6*.py scripts/exp7*.py
  │ 2>/dev/null | head -40
  └ 34 lines…

## Verdicts

### 1. Attack “five of six”
**Conflict detection is the soft number.**  
18 “real” oppositions: **15/18 only appear after hand-authored `oppose` pairs** added because polarity/functional saw 3. `multi_position_propositions = 0` — positions never hit the same key; you mostly fired lattice edges you installed. Scoped 0 is the dual tautology (different `under_assumption` ⇒ no conflict by rule).

Near-vacuous co-travelers: **refusal 0.000 wrong** and **answerable 1.0** are store self-lookup (exp68 says so); **dedup 100%** is dual-representation plumbing. **Expansion 181/181** is real but on *your* lattice. Honest score: **~1.5 / 6**, not 5/6.

### 2. Corroboration close
**Right to kill ontology-chasing; premature to kill the mechanism.**  
Wiki already has multi-source (exp69: **286**; exp67: **1.6%**). Zeros are genre + open entity vocab, not a law of nature. `min_sources=2` is unusable on argumentative text; that is a **policy/genre** failure.

**Cheapest verdict-flip:** lock Wikidata PIDs + QIDs on 200 bio pages; run **two independent extractors**; measure dual-extractor proposition overlap and true multi-page overlap. Still ≈0 → corroboration dead as product pillar. Non-trivial → keep as **extraction-stability** signal, drop as independent-truth quorum.

### 3. Pipeline next?
**No.** Full doc→answer productizes untested extraction and a fitted opposition toy. Blood was at **canonical/time/entity** (104 false birthday conflicts), not missing glue.

**Build instead:** one shared ingest contract + **labeled false-conflict / missed-opposition harness** on fixed wiki bios + held-out phil (no new `oppose` edges mid-eval).  
**Kill criterion:** after time/entity fixes, **>5% of detected conflicts are false** on the bio gold set → drop conflict-as-feature; ship provenance + no-edge refusal only.

### 4. Use without corroboration
**Stance ledger / contested-claim map** (law, standards, theology, policy): who holds what under which frame, spans attached, hard refuse to pick a winner. Corroboration is the wrong ask.

Second use the brief skips: **consistency linter** on extractors and LLM answers (P vs ¬P, scope stripping, answer-without-edge) — user-supplied corpus; multi-source quorum optional.

### 5. Throw away
- `min_sources≥2` as design center on open/argument text  
- Cross-corpus federation / registry-for-corroboration (exp69–70–73 path)  
- Axis-up generalisation as a corroboration bet  
- Dual live store + per-exp throwaway pipelines  
- Selling hand-seeded `oppose` graphs as “discovery”  
- Fusion-breaker theatre until classes actually blow up (exp67 B2 untestable)  
- Scoreboard framing that licenses shipping

**Keep:** canonical strictness, scope-overlap rule, up-only expansion, no-edge refusal, attributed multi-answer shape.


[stderr] 

Changes    +0 -0
Requests   1 Premium (1m 21s)
Tokens     ↑ 190.8k (139.4k cached) • ↓ 3.8k (2.3k reasoning)
Resume     copilot --resume=25f5cd8f-f8b8-4edf-b22b-ce88840cf815
