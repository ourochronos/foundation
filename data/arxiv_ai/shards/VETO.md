# AI/ML claim-veto instructions (pooled checkers; D83 recipe)

Input: a POOL of shards. For each shard K in your pool, read
`in_K.json` (the paper records with abstracts) and `out_K.jsonl` (the
extracted claims). Judge every claim against its paper's ABSTRACT (match
via the `page` field, `arxiv:<arxiv_id>`).

Veto a claim ONLY on a clear violation of one of these rules (numbered
to match PROMPT.md's extraction rules). Do not veto for style. When in
doubt, let the claim live — the downstream frozen audit measures
precision; the veto's job is removing DEFECTS, not enforcing taste.

1. NOT ASSERTED: the abstract does not assert the claim — it is
   inferred, imported from background knowledge, or contradicts the
   abstract's wording.
2. NOT SELF-CONTAINED: dangling "this/we/it/our" with no referent, or
   the method/model/dataset the claim turns on is not named.
3. STRENGTH MISMATCH: the attribution verb overstates the abstract
   ("proves/shows" where the abstract proposes, studies, suggests, or
   conjectures; unconditional phrasing where the abstract conditions).
4. BENCHMARK VIOLATION: a metric number without its dataset AND setting
   as the abstract gives them, or a dropped qualifier that changes the
   claim ("up to", "on average", "under condition C", model scale,
   shot count).
5. ARTIFACT ERROR: an artifact claim mis-states name, size, or license,
   or asserts a release the abstract does not state.
6. MALFORMED/DUPLICATE: subject is not a short noun phrase from the
   abstract, object exceeds ~8 words, or the row duplicates another
   claim from the same paper.

Output: compose ALL veto rows first, then ONE Write call to your
assigned `veto_X.jsonl` — one JSON object per line:

{"page": "<page>", "subject": "<subject>", "pid": "P_ASSERTS",
 "object": "<object>", "rule": <N>, "reason": "<short, quote the
 abstract's actual wording where it decides the case>"}

`page`/`subject`/`object` must be copied VERBATIM from the claim row —
they are the match keys for applying the veto. If a shard's claims are
all clean, it simply contributes no rows. An empty veto file is a valid
result.

Final text: just "checked N claims across M shards, vetoed V".
