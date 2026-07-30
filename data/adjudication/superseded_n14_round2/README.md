# Round 2 on the 14-claim block (D161) — the round that halved the flag rate

Twelve runs: verification once and attack three times, across a **three-rater
odd panel** (`gpt-5.6-sol`, `gemini-3.1-pro-preview`, `grok-4.5`). The fourth
rater was dropped on D154's evidence that it moves one verdict of fourteen and
only by turning a 2-of-4 majority into a tie.

Aggregated into `results/adjud_quorum_round2.json`, which stores the claim
texts alongside the verdicts and is self-describing.

## What this round established

- **Attack flagged 3 of 14, down from 6 of 14** on the previous round. The
  claims changed between rounds; the prompt did not. D156's law #10 predicted
  exactly this and the prediction is the result.
- **Within-rater instability fell too**: the unstable rater went from
  [6, 7, 4] (range 3) to [5, 5, 4] (range 1), and another from [5, 5, 6] to
  [2, 1, 2]. Sharper claims are apparently easier to judge *consistently*, not
  merely more often correctly.
- **Row 11 — the last claim that had never been adjudicated — failed both
  prompts**, completing D154's tally at five of five.

## The three flags, all valid, two of them self-inflicted the same day

- **claim 9 (confusability)** — said refusal is governed by the most confusable
  option "not by how many options there are", while its own evidence shows the
  confusable arm falling 0.8485 → 0.7758 with the maximum pinned at 0.5001.
  **Audit law #10 broken in a claim written the same day the law was written.**
- **claim 11 (alias plateau)** — D155 withdrew "not a permanent loss of
  information"; the replacement said "the residual is a capability difference,
  not a supply shortfall", which is the same unsupported inference in weaker
  words. Nothing was measured past 18 aliases. Unanimous.
- **claim 12 (adjudication is noisy)** — said the two prompts flag disjoint
  sets, and was refuted **by the round judging it**, in which this very claim
  drew both a verification and an attack flag.

All three were verified against source and the claims rewritten, which is why
these artifacts are superseded.

## What is owed

A re-run on the revised block. Do not read the flag *counts* above as applying
to the current claim text — three of the fourteen have changed.
