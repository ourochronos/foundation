# First run of the `selfcheck` prompt (D163)

One run per rater across `gpt-5.6-sol`, `gemini-3.1-pro-preview` and
`grok-4.5`, on the 14-claim block as it stood after D162.

Superseded immediately because it worked: it flagged rows **1b, 3, 7 and 12**
at quorum, all four were verified against the claim text and rewritten, and
rewriting a claim retires the verdicts that judged its earlier wording (D152).

## What it established

- The four it flagged are **disjoint** from the three that the attack prompt
  flagged in the same block, so this is a defect class the other two prompts
  do not reach.
- The block had already passed verification and survived attack. A table can
  clear both and still hold four claim sentences that contradict their own
  scope conditions.
- Two of the four were written by the author while explicitly holding the
  correct number: D159 measured the wrongness cost at 9.8% of the gain and
  then wrote "costs refusal, *not* the accuracy"; D158 computed greedy
  walking at +0.009 and wrote "the walk does *not*".

## What it does not establish

**One run per rater.** Within-rater stability is unmeasured, and D150 showed a
single adversarial run is a sample rather than a verdict. Treat the counts as
provisional until the prompt has been run repeatedly on identical input, and
until a deliberately planted overreach confirms it is detecting the defect
rather than preferring hedged prose.
