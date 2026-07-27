# HF model-card claim-veto instructions (pooled checkers)

Input: a POOL of shards. For each shard K in your pool, read
`in_K.json` (model records with card_md) and `out_K.jsonl` (extracted
claims). Judge every claim against its model's card_md (match via
`page` = "hf:" + record.id) and the record's metadata fields.

Veto a claim ONLY on a clear violation (numbers match PROMPT.md rules).
Do not veto for style. When in doubt, the claim lives.

1. NOT STATED: the card (or, for registry claims, the metadata fields)
   does not state it — inferred, background knowledge, or contradicts
   the card.
2. NOT SELF-CONTAINED: dangling reference; model/dataset/metric the
   claim turns on is unnamed.
3. STRENGTH MISMATCH: "reports/shows" for what the card merely claims
   without evidence, or factual framing of a marketing superlative.
4. BENCHMARK VIOLATION: metric number without benchmark name AND metric
   AND setting as the card gives them; dropped qualifier; number not
   actually in the card.
5. REGISTRY/ARTIFACT ERROR: license/pipeline mis-stated vs the metadata
   fields, or size/name mis-stated vs the card.
6. MALFORMED/DUPLICATE: subject not the model's short name, object >8
   words, or the row duplicates another claim for the same model.

Output: compose ALL veto rows first, then ONE Write call to your
assigned `veto_X.jsonl` — one JSON object per line:

{"page": "<page>", "subject": "<subject>", "pid": "P_ASSERTS",
 "object": "<object>", "rule": <N>, "reason": "<short, cite the card's
 actual wording where it decides the case>"}

`page`/`subject`/`object` copied VERBATIM from the claim row (match
keys). An empty veto file is a valid result.

Final text: just "checked N claims across M shards, vetoed V".
