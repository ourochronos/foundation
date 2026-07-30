# Superseded: the 10-claim block — the round that earned the D153 fixes

These five artifacts judged a **10-claim** block. The current block has 14
claims and every one of the flags below has been acted on, so the artifacts
are superseded *because they worked*, not because they were discarded.

Unlike `../superseded_n11/`, these carry `judged_claims`, so every verdict
here remains attributable to the exact claim text it judged. They are kept as
the evidence for D153's central finding.

## Verification (`claims_*`, 4 raters, 1 run each) — 5 of 10 flagged

The same prompt returned **zero** defects across four families at D144 and
**0 of 11** at D150. What changed is not the prompt: D150 sharpened the claims
to carry specific numbers, and a specific number can be checked and can be
wrong. The earlier unanimous passes were measuring hedging.

| claim | raters | what they caught |
|---|---|---|
| 1b appending near-free | grok | +0.058/+0.191 are **depth-1 only**; depth 2 is +0.249 |
| 2 composition | fable, gemini | "fails at 5" cited no artifact containing a 5 |
| 4 depth extrapolates | grok | one depth measured; depth 4 refutes it (0.289/0.149) |
| 8 retrieval vs head | gemini, sol, grok | gap is 0.229 not 0.230; "does not destroy information" is inferred, never measured |
| 12 entities free | gemini | "three populations" are three *question* populations in one corpus |

## Attack (`attack_r1_gpt-5_6-sol`, 1 rater, 1 run) — 8 of 10 flagged

Stopped after one run: the block was already known to be changing, and
spending 11 more premium calls on text due for revision is the mistake D150
and D152 were both written about. Read it as a preview, not a quorum —
**D150 measured a single rater varying by 5 of 11 across identical runs**, so
one adversarial run is a sample.

Its flags split cleanly by kind, which is the point worth keeping:
verification found **arithmetic** defects, attack found **design** ones —
absent equivalence margins, unsupplied leakage checks, aggregate comparisons
standing in for paired ones. Two it named that verification missed entirely
were confirmed against source and fixed: staleness is 0.002 rather than zero
(the matrix holds one `old->old` case), and "at parity" carried no
equivalence margin (held-out 0.9245 vs trained 0.9135, now stated as
+0.011 within a ±0.02 band).
