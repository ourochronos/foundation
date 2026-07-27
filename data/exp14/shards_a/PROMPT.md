# AI/ML claim extraction — ARM A (source-local entity consolidation)

Input: your assigned `in_K.json` — a JSON array of 20 arXiv AI/ML paper
records {arxiv_id, title, abstract, authors, published}.

This is the D92 extraction task with ONE structural change. Read the
extraction rules first; then the naming rule, which is the point of this
arm.

## Step 1 — name the paper's ENTITIES, before writing any claim

For each paper, first decide the small set of things the paper is
*about*: the method or model it introduces, the benchmark or dataset it
uses or releases, the task, the artifact. **Typically 1–3 entities per
paper; rarely more than 4.**

Write each entity as the SHORTEST NAME THAT STANDS ALONE — the name the
authors themselves would use in a later paper. Prefer the bare proper
name.

- Good: `SHIFT`, `MissHyper`, `MedGame`, `CultureTalk-ID`, `MMLU-Pro`
- Bad: `SHIFT retrieval performance`, `SHIFT fine-grained
  reconstruction`, `MedGame user perception`, `MedGame framework`

If the paper's method has no proper name, use a short descriptive noun
phrase and REUSE IT VERBATIM across every claim about it — e.g.
`prompt-contrastive editing`, not `prompt-contrastive region discovery`
in one claim and `contrastive edit localization` in the next.

## Step 2 — attach every claim to one of those entities

Each extracted claim's `subject` MUST be one of the entity names you
just wrote for that paper, copied character-for-character. A claim that
does not belong to any of them means you missed an entity — go back and
add it, do not invent a one-off subject.

**A paper with 4 claims about its method should produce 4 claims sharing
ONE subject**, differing in `object` and `statement`. Claims sharing a
subject is the expected, correct outcome — not a duplicate.

## Extraction rules (unchanged from D92 — precision beats recall)

1. A claim must be ASSERTED by the abstract itself — never inferred,
   never from your background knowledge.
2. Self-contained: readable alone; name methods/models/datasets
   explicitly; no dangling "this/we/it/our".
3. Attributed frame matching the abstract's own strength: "The paper
   proves/shows/reports/introduces/proposes/claims ..." — "shows" only
   if shown; "proposes/introduces" for new methods; "reports" for
   empirical numbers; "claims" when the abstract asserts without
   evidence language.
4. BENCHMARK DISCIPLINE: a metric claim MUST carry the dataset AND the
   setting verbatim from the abstract ("reports 78.4 on MMLU-Pro
   (5-shot)"). If the abstract gives a number without its dataset or
   drops the setting, extract at the weaker strength the abstract
   supports or SKIP. Never strip qualifiers ("under condition C", "up
   to", "on average") — a dropped condition is a defect.
5. ARTIFACT CLAIMS: model/dataset/code releases become kind=artifact
   claims with name, and size/license when stated.
6. kind = one of result | method | artifact | benchmark | conjecture |
   question.
7. 2-6 claims per abstract; too-vague abstracts get ZERO rather than a
   stretch.

**The `statement` field is unchanged by this arm**: it stays faithful to
the abstract exactly as before. Only the `subject` naming changes.

Compose ALL rows first, then ONE Write call to your assigned
`out_K.jsonl` — one JSON object per line:
{"page": "arxiv:<arxiv_id>", "page_title": "<paper title>",
 "subject": "<one of the entity names you chose>", "pid": "P_ASSERTS",
 "kind": "<kind>", "object": "<short label, <=8 words>",
 "statement": "<the full attributed claim sentence>"}

Final text: just "done: N claims from M papers over E entities".
