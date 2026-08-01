I’m testing the headline against the actual experiment definitions and measurement denominators, then I’ll make a single direction call.

/ Search (glob)
  │ "**/README*"
  └ 8 files found

/ Search (glob)
  │ "foundation/model/*.py"
  └ 6 files found

/ Search (glob)
  │ "**/*experiment*"
  └ 1 file found

/ Search (grep)
  │ "five of six|corrobor|near-vacu|min_sources|181/181|8000|8,000|scoped"
  └ 13 files found

● Read README.md
  └ L1:240 (59 lines read)

/ Search (glob)
  │ "results/*"
  └ 243 files found

/ Search (glob)
  │ "scripts/*.py"
  └ 177 files found

/ Search (glob)
  │ "tests/test_*.py"
  └ 12 files found

/ Search (grep)
  │ "near-vacu|vacuous|answerable|min_sources|superordinate|sibling|scope stripped|oracle" in
  │ *.{py,json,md}
  └ 9 lines found

● Read exp69_corroboration.json
  │ results/exp69_corroboration.json
  └ 77 lines read

● Read exp73_axes.json
  │ results/exp73_axes.json
  └ 45 lines read

● Read exp61_refusal_frontier.json
  │ results/exp61_refusal_frontier.json
  └ 282 lines read

● Read exp68_query.json
  │ results/exp68_query.json
  └ 54 lines read

● Read exp72_scoped_conflict.json
  │ results/exp72_scoped_conflict.json
  └ 22 lines read

● Read exp67_adversarial.json
  │ results/exp67_adversarial.json
  └ 101 lines read

/ Search (grep)
  │ "D6[7-9]|D7[0-3]|five of six|near-vacu|vacuous" in *.md (docs)
  └ 9 lines found

● Read exp68_query.py
  │ scripts/exp68_query.py
  └ L1:320 (237 lines read)

● Read exp73_axes.py
  │ scripts/exp73_axes.py
  └ L1:300 (178 lines read)

● Read 26-status-brief.md
  │ docs/26-status-brief.md
  └ L1:220 (97 lines read)

● Read exp66_federation.json
  │ results/exp66_federation.json
  └ 23 lines read

● Read exp66_federation.py
  │ scripts/exp66_federation.py
  └ L1:280 (253 lines read)

● Read exp72_scoped_conflict.py
  │ scripts/exp72_scoped_conflict.py
  └ L1:300 (178 lines read)

1. **“Five of six work” is false.** At most five code paths execute.

   - **Dedup:** 100% comes from cloning the same rows into two synthetic stores, then supplying deterministic slug links. It tests serialization consistency—not entity resolution, heterogeneous extraction, or false merges.
   - **Conflict detection:** only **3** conflicts existed under the original rules. The other 15 appear after opposition pairs were authored from the same corpus and then passed back into detection. There is no gold precision/recall denominator.
   - **Scoped coexistence:** zero is nearly forced because each position receives its own assumption frame; the corpus has zero multi-position propositions. This does not test overlapping or nested real scopes.
   - **Refusal:** zero wrongness is guaranteed by exact lookup with no generative step. It is a regression property, not calibrated refusal; its only substantive policy refuses 98.1% of answerable questions.
   - **Expansion:** 181/181 tests two hand-written subsumptions against stored edges; the sibling-leak population is mostly synthetic.

   None of the five is validated as a useful end-user mechanism. Canonical typed values and deterministic lookup are the credible results.

2. **Closing corroboration is premature as an empirical conclusion, though further generic ontology work should stop.** All four corpora were selected from genres where independent repetition is structurally scarce, while exact-triple matching confounds actual concurrence with normalization failure.

   The cheapest decisive experiment is a manually adjudicated upper bound: sample 100 claims from one observational domain, have annotators identify independently sourced semantic duplicates, then oracle-normalize predicate, frame, and entities. Measure agreement before and after normalization. If the oracle-normalized set still has negligible independent concurrence, close corroboration. If it rises materially while automatic matching stays zero, the current experiments measured ontology recall—not corroboration.

3. **Do not build the proposed generic document pipeline.** It would combine an unmeasured extractor, authored vocabularies, and self-scored retrieval into a polished self-confirming demonstration.

   Build a narrow **requirements/policy contradiction auditor** first, using oracle-authored claims before adding extraction. Test it on 50 genuine conflict pairs and 100 hard non-conflicts involving versions, jurisdictions, nested assumptions, precision differences, and merely related predicates. Kill the direction if it cannot reach roughly 90% precision and 70% recall without corpus-derived opposition rules. Only then wire ingestion.

4. **The machinery fits consistency auditing, not epistemic truth aggregation.** Requirements, contracts, regulations, architecture decisions, and configuration policies routinely contain authoritative but scoped assertions. Provenance identifies who imposed an obligation; scopes represent version, jurisdiction, component, or deployment assumptions; conflict detection exposes incompatible obligations; refusal prevents inventing a resolution. Corroboration is unnecessary because three documents repeating a requirement does not make it truer.

5. **Throw away the generic epistemic-KB framing and its unsupported machinery:** `agreement` as epistemic support, `min_sources`, generic entity closure, unvalidated fusion circuit breakers, predicate composition, and speculative hash-agility/ZK provisions. Remove generic authored opposition ontologies unless a chosen domain supplies them independently.

   Retain typed canonicalization, provenance spans, explicit scopes, simple proposition identity, exact retrieval, and narrowly defined contradiction rules. Treat everything else as replaceable—not as a platform that has earned continuation. 1. “Five of six work” is false. At most five code paths execute.
 - Dedup: 100% comes from cloning the same rows into two synthetic stores, then supplying
deterministic slug links. It tests serialization consistency—not entity resolution, heterogeneous
extraction, or false merges.
 - Conflict detection: only 3 conflicts existed under the original rules. The other 15 appear after
opposition pairs were authored from the same corpus and then passed back into detection. There is no
 gold precision/recall denominator.
 - Scoped coexistence: zero is nearly forced because each position receives its own assumption
frame; the corpus has zero multi-position propositions. This does not test overlapping or nested
real scopes.
 - Refusal: zero wrongness is guaranteed by exact lookup with no generative step. It is a regression
 property, not calibrated refusal; its only substantive policy refuses 98.1% of answerable
questions.
 - Expansion: 181/181 tests two hand-written subsumptions against stored edges; the sibling-leak
population is mostly synthetic.
 None of the five is validated as a useful end-user mechanism. Canonical typed values and
deterministic lookup are the credible results.
 2. Closing corroboration is premature as an empirical conclusion, though further generic ontology
work should stop. All four corpora were selected from genres where independent repetition is
structurally scarce, while exact-triple matching confounds actual concurrence with normalization
failure.
 The cheapest decisive experiment is a manually adjudicated upper bound: sample 100 claims from one
observational domain, have annotators identify independently sourced semantic duplicates, then
oracle-normalize predicate, frame, and entities. Measure agreement before and after normalization.
If the oracle-normalized set still has negligible independent concurrence, close corroboration. If
it rises materially while automatic matching stays zero, the current experiments measured ontology
recall—not corroboration.
 3. Do not build the proposed generic document pipeline. It would combine an unmeasured extractor,
authored vocabularies, and self-scored retrieval into a polished self-confirming demonstration.
 Build a narrow requirements/policy contradiction auditor first, using oracle-authored claims before
 adding extraction. Test it on 50 genuine conflict pairs and 100 hard non-conflicts involving
versions, jurisdictions, nested assumptions, precision differences, and merely related predicates.
Kill the direction if it cannot reach roughly 90% precision and 70% recall without corpus-derived
opposition rules. Only then wire ingestion.
 4. The machinery fits consistency auditing, not epistemic truth aggregation. Requirements,
contracts, regulations, architecture decisions, and configuration policies routinely contain
authoritative but scoped assertions. Provenance identifies who imposed an obligation; scopes
represent version, jurisdiction, component, or deployment assumptions; conflict detection exposes
incompatible obligations; refusal prevents inventing a resolution. Corroboration is unnecessary
because three documents repeating a requirement does not make it truer.
 5. Throw away the generic epistemic-KB framing and its unsupported machinery: agreement as
epistemic support, min_sources, generic entity closure, unvalidated fusion circuit breakers,
predicate composition, and speculative hash-agility/ZK provisions. Remove generic authored
opposition ontologies unless a chosen domain supplies them independently.
 Retain typed canonicalization, provenance spans, explicit scopes, simple proposition identity,
exact retrieval, and narrowly defined contradiction rules. Treat everything else as replaceable—not
as a platform that has earned continuation.


[stderr] 

Changes    +0 -0
Requests   0 Premium (51s)
Tokens     ↑ 162.5k (110.3k cached, 52.2k written) • ↓ 3.3k (1.7k reasoning)
Resume     copilot --resume=d0d4f879-caf7-4a11-8927-492b3afa24dc
