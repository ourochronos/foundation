# AI/ML claim-extraction instructions (shared by all shard agents)

Input: your assigned `in_K.json` — a JSON array of ~20 arXiv AI/ML paper
records {arxiv_id, title, abstract, authors, published}.

## Step 1 — name the paper's ENTITIES before writing any claim (D94)

Decide the small set of things the paper is *about*: the method or model
it introduces, the benchmark or dataset it uses or releases, the task,
the artifact. **Typically 1–3 per paper; rarely more than 4.**

Write each as the SHORTEST NAME THAT STANDS ALONE — the name the authors
would use in a later paper. Prefer the bare proper name.

- Good: `SHIFT`, `MissHyper`, `MedGame`, `CultureTalk-ID`, `MMLU-Pro`
- Bad: `SHIFT retrieval performance`, `MedGame user perception`

If the method has no proper name, use a short descriptive noun phrase
and REUSE IT VERBATIM across every claim about it.

Every claim's `subject` MUST be one of those names, copied
character-for-character. **Claims sharing a subject is the expected,
correct outcome — not a duplicate.** Without this rule 95% of subjects
were used exactly once and the store had no entity structure at all;
with it, subjects-per-claim fell 0.912 → 0.373 at no cost to precision
(D94).

## Step 2 — extract the claims

Extract ATTRIBUTED CLAIMS from each abstract. Rules (precision beats
recall; violations poison downstream):

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
   claims with name, and size/license when stated ("The paper releases
   the 7B-parameter X model under Apache-2.0").
6. subject = one of the entity names chosen in Step 1, verbatim; kind =
   one of result | method | artifact | benchmark | conjecture | question.
7. 2-6 claims per abstract; too-vague abstracts get ZERO rather than a
   stretch.

Compose ALL rows first, then ONE Write call to your assigned
`out_K.jsonl` — one JSON object per line:
{"page": "arxiv:<arxiv_id>", "page_title": "<paper title>",
 "subject": "<one of the Step-1 entity names>", "pid": "P_ASSERTS",
 "kind": "<kind>", "object": "<short label, <=8 words>",
 "statement": "<the full attributed claim sentence>"}

`page_title` carries the paper's title so ingest can canonicalize it —
a page's canonical form is its TITLE, not its identifier (D92).

Final text: just "done: N claims from M papers over E entities".
