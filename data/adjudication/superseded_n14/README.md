# The 14-claim round (D154) — the one that produced the falsifiers

Sixteen runs: verification once per rater and attack three times per rater,
across `gpt-5.6-sol`, `gemini-3.1-pro-preview`, `grok-4.5` and
`claude-fable-5`. All sixteen carry `judged_claims` and all sixteen passed the
D152 alignment check when they were aggregated, so **every verdict here is
attributable to the exact claim text it judged** — unlike `../superseded_n11/`,
where only the counts survive.

Aggregated into `results/adjud_quorum.json`, which stores the claim texts
alongside the verdicts and is therefore self-describing.

## What this round established (D154)

- **4 of 4** claims that had never been adjudicated were flagged, two
  unanimously; **2 of 10** that had been through it before were flagged.
- Attack flagged **6 of 14** at quorum; verification flagged **0 of 14**.
  Neither prompt subsumes the other.
- The author-family effect is a property of the **prompt**: `claude-fable-5`
  returned 14/14 SUPPORTED under verification (the only clean sheet) and
  flagged 5 under attack, agreeing with the independent quorum on five of six.
- Within-rater instability is **one rater**: sol [6, 7, 4] against ranges of
  1, 1 and 2.

## Why they are superseded

Claim 12 changed. **D155 ran the falsifier these raters named for it** — "the
gap could plateau above zero beyond ten aliases" — and they were right: the
gap flattens at ≈0.09 from 10 to 18 aliases, so *"not a permanent loss of
information"* was withdrawn and the claim rewritten.

That is the loop working, not a filing error. The adjudication named a
falsifier, the falsifier was run, the result changed the claim, and changing
the claim retired the verdicts that judged its earlier wording.

## What is owed

A re-adjudication on the revised block. Five falsifiers from this round are
still unrun (claims 2, 6, 8, 10, 11), and five verification flags are still
unfixed — all one shape, a claim sentence generalising past the condition its
number was measured under. Until that re-run, **the project has no current
adjudication**, which is an honest state and is recorded here rather than
implied by an empty directory.
