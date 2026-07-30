# Superseded: adjudications of the 11-claim block (D145, D150)

These artifacts judged an **11-claim** table. The current table in
`docs/18-writeup-outline.md` has **10 claims** — the normative "report refusal
as a risk-coverage curve" item was moved into the method section, and the
list shifted underneath every verdict.

Verdicts here key on **index only**. They were written before D152 added
`judged_claims`, so there is no way to recover which claim a given `idx`
referred to. Per D152:

> the stored adversarial verdicts from D145 and D150 are unusable for
> identifying which claims are flagged. Their aggregate statistics (flag
> counts, within-rater ranges, the family effect) remain valid, since those
> never depended on which claim was which.

So: **read the counts, never the mapping.** Anything that needs to know
*which* claim was flagged must come from the re-run on the 10-claim block
(`../attack_r*.json`), which stamps claim text into each artifact.

`claims_grok-4_5.json` is absent from this directory: that rater was already
re-run against the 10-claim block and lives in the parent directory.
