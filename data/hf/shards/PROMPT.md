# HuggingFace model-card claim-extraction instructions (shared by all shard agents)

Input: your assigned `in_K.json` — a JSON array of 20 HF model records
{id, pipeline_tag, downloads, license, card_md}. `card_md` is the full
model-card markdown (may be tens of thousands of chars; tables common).

Extract ATTRIBUTED CLAIMS about each model. Cards are SELF-REPORTED
marketing-adjacent documents — the attribution frame must make that
visible ("The model card states/reports/claims ..."), and precision
beats recall throughout.

1. A claim must be stated by the card itself (or, for the one registry
   claim, by the registry metadata fields) — never inferred, never from
   your background knowledge of the model.
2. Self-contained: readable alone; name the model and any dataset/metric
   explicitly; no dangling "this/it/our".
3. Attribution frame: "The <model> card states/reports/claims ..." —
   "reports" for empirical numbers, "states" for factual properties
   (architecture, size, languages, training data), "claims" for
   superiority/quality assertions without numbers.
4. BENCHMARK DISCIPLINE (cards are table-heavy — this rule does the
   work): a metric claim MUST carry benchmark/dataset name AND metric
   AND setting exactly as the card gives them. Prefer the card's
   headline/summary numbers (2-3 per card max) over exhaustive table
   dumps. Never strip qualifiers. A bare number without its benchmark
   is not extractable.
5. REGISTRY CLAIM (exactly one per model, kind=artifact): license and
   pipeline tag from the metadata fields, attributed to the registry:
   "The Hugging Face registry lists <id> under license <license>
   (pipeline: <pipeline_tag>)." Skip downloads/likes — dated
   observations, not claims.
6. LINEAGE (kind=lineage): base model, distillation/fine-tune parentage,
   training corpora — only when the card names them.
7. subject = the model's common name as the card uses it (short);
   kind = one of task | size | license | benchmark | lineage | method |
   result. 2-8 claims per card; thin cards get the registry claim and
   whatever little they state — never a stretch.

Compose ALL rows first, then ONE Write call to your assigned
`out_K.jsonl` — one JSON object per line:
{"page": "hf:<id>", "subject": "<model name>", "pid": "P_ASSERTS",
 "kind": "<kind>", "object": "<short label, <=8 words>",
 "statement": "<the full attributed claim sentence>"}

Final text: just "done: N claims from M cards".
