# AI/ML claim-extraction instructions (shared by all shard agents)

Input: your assigned `in_K.json` — a JSON array of ~20 arXiv AI/ML paper
records {arxiv_id, title, abstract, authors, published}.

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
6. subject = the principal method/model/topic of the claim, a SHORT noun
   phrase from the abstract; kind = one of result | method | artifact |
   benchmark | conjecture | question.
7. 2-6 claims per abstract; too-vague abstracts get ZERO rather than a
   stretch.

Compose ALL rows first, then ONE Write call to your assigned
`out_K.jsonl` — one JSON object per line:
{"page": "arxiv:<arxiv_id>", "subject": "<topic>", "pid": "P_ASSERTS",
 "kind": "<kind>", "object": "<short label, <=8 words>",
 "statement": "<the full attributed claim sentence>"}

Final text: just "done: N claims from M papers".
