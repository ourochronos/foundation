# AI/ML claim extraction — ARM B (source-local consolidation + store linking)

Input: your assigned `in_K.json` — 20 arXiv paper records {arxiv_id,
title, abstract, ...} each carrying a `store_candidates` list: entities
the knowledge store ALREADY holds that may be relevant to that paper.

Do everything Arm A does, then one additional step.

## Step 1 — name the paper's ENTITIES (unchanged from Arm A)

For each paper, first decide the small set of things the paper is
*about*: the method or model it introduces, the benchmark or dataset it
uses or releases, the task, the artifact. **Typically 1–3 per paper;
rarely more than 4.**

Write each as the SHORTEST NAME THAT STANDS ALONE — the name the authors
would use in a later paper. Prefer the bare proper name.

- Good: `SHIFT`, `MissHyper`, `MedGame`, `CultureTalk-ID`, `MMLU-Pro`
- Bad: `SHIFT retrieval performance`, `MedGame user perception`

If the method has no proper name, use a short descriptive noun phrase
and REUSE IT VERBATIM across every claim about it.

## Step 2 — link each entity to the store, or decline

For each entity you named, look at that paper's `store_candidates`.
Each candidate shows `eid`, `name`, `source` (the page it came from),
`source_kind`, and `similarity`.

**Link ONLY when the candidate denotes THE SAME THING as your entity —
not a related topic, not the same research area, not a similar-sounding
concept.** The test is substitution: could an expert swap one name for
the other in a sentence without changing what is being talked about?

DECLINE — write no link — in all of these cases:

- **Related but distinct.** `PATS` and `Group-in-Group Policy
  Optimization` are both LLM-agent training methods. They are NOT the
  same method. Do not link them.
- **A general concept vs a specific technique.** A Wikipedia article for
  *Memory*, *topology*, or *power set* is a general subject; a paper's
  `cue-anchored memory for agents` or `topological pressure` is a
  specific technical object. **These are never the same entity.** Treat
  a `Wikipedia article` candidate as almost certainly wrong for a
  paper's method or benchmark.
- **Same words, different field.** `finite-sample toolkit` (statistics)
  and `finite set` (set theory) share vocabulary and nothing else.
- **The paper's own title.** A paper is not its method. Never link a
  method entity to the paper that introduces it.
- **Any uncertainty at all.** Declining costs almost nothing — the store
  can merge two records later. A wrong link silently pools two different
  things' facts and every future answer inherits the error. **When in
  doubt, decline.**

`similarity` is a hint about which candidates are worth reading. It is
NOT evidence of identity — high similarity frequently means "same
words," and some of the highest-scoring candidates in this list are
exactly the traps described above. Judge by meaning, never by score.

It is entirely normal and correct for a paper to link ZERO entities.
Most new methods genuinely are new.

## Extraction rules (unchanged from D92 — precision beats recall)

1. A claim must be ASSERTED by the abstract itself — never inferred,
   never from your background knowledge.
2. Self-contained: name methods/models/datasets explicitly; no dangling
   "this/we/it/our".
3. Attributed frame matching the abstract's own strength.
4. BENCHMARK DISCIPLINE: a metric claim MUST carry the dataset AND the
   setting verbatim. Never strip qualifiers.
5. ARTIFACT CLAIMS: releases become kind=artifact with name, size and
   license when stated.
6. kind = result | method | artifact | benchmark | conjecture | question.
7. 2-6 claims per abstract; too-vague abstracts get ZERO.

**The `statement` field is written from the abstract ALONE.** Never let
a store candidate change the wording of a claim, and never import a fact
from the store into a statement. The store informs only which NAME you
use as `subject` and whether you attach a `link`.

Compose ALL rows first, then ONE Write call to your assigned
`out_K.jsonl` — one JSON object per line:
{"page": "arxiv:<arxiv_id>", "page_title": "<paper title>",
 "subject": "<one of the entity names you chose>", "pid": "P_ASSERTS",
 "kind": "<kind>", "object": "<short label, <=8 words>",
 "statement": "<the full attributed claim sentence>",
 "link": "<eid you are linking this subject to, or omit entirely>",
 "link_reason": "<one clause, only when link is present>"}

Omit `link` entirely when declining. Never invent an eid — a link must
be copied from that paper's own `store_candidates`.

Final text: just "done: N claims from M papers over E entities, L links".
