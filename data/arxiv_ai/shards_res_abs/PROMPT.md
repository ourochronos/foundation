# Resource-axis extraction (docs/15, D95)

Input: your assigned `in_K.json` — ~20 papers with {arxiv_id, title,
abstract, body_window}. `body_window` is cleaned paper text: the
introduction plus the experimental section, which is where papers name
things they did NOT invent.

Your job is ONLY those things: the shared resources a paper uses. You are
not extracting the paper's contributions — a different pass does that.

## What counts as a resource

Something that exists independently of this paper and that other papers
also use:

- **benchmarks / datasets** — GSM8K, MMLU, ImageNet, ALFWorld, CoNLL-2003
- **base models** — Qwen2.5, Llama 3, GPT-4o, DeBERTa-v3
- **adopted methods/algorithms** — PPO, GRPO, LoRA, chain-of-thought
- **baselines it compares against** — named systems from other work

NOT resources: the paper's own contribution; generic terms (transformer,
neural network, attention, fine-tuning, accuracy, F1); software and
infrastructure (PyTorch, CUDA, NVIDIA, GPUs, JSON, GitHub); section
labels and artifacts of the text (RQ1, IV-B, Table 3, MLP, III).

## Relations

- `P_EVALUATES_ON` — the paper evaluates/tests/trains on this dataset or
  benchmark
- `P_BUILDS_ON` — the paper builds on, fine-tunes, or extends this base
  model or prior method
- `P_COMPARES_TO` — the paper compares against this as a baseline

## CANONICAL NAMING — the point of this pass

A resource named by fifty papers must come out as ONE name. Write the
**canonical short name the community uses**, not the paper's phrasing.

- `GSM8K` — not "the GSM8K benchmark", "GSM-8K", "GSM8k"
- `MMLU` — not "MMLU benchmark"; but `MMLU-Pro` IS a different resource
- `Qwen2.5` — not "Qwen-2.5", "qwen2.5"; drop size/variant suffixes
  (`Qwen2.5-7B-Instruct` → `Qwen2.5`) UNLESS the paper's point is about
  that specific size
- `Llama 3` — not "LLaMA-3", "Llama3"
- `PPO` — not "Proximal Policy Optimization (PPO)"; use the acronym when
  the acronym is what the field says
- `chain-of-thought` — lower-case for unbranded techniques

Strip articles, the words "benchmark"/"dataset"/"model", version
punctuation, and parenthetical expansions. When a name genuinely has no
community-standard form, use the paper's own form verbatim and be
consistent within your shard.

## RESOURCE-NAME GRANULARITY (declared policy — D100)

Resources are recorded at **FAMILY level**, not exact-artifact level:
`Qwen2.5-7B-Instruct` -> `Qwen2.5`, `AIME 2024` -> `AIME`,
`Claude-Sonnet-4.5` -> `Claude`, `CBraMod-small` -> `CBraMod`.

This is a deliberate trade and it is the reason the axis exists. Keeping
`Qwen2.5-3B`, `Qwen2.5-7B` and `Qwen2.5-32B` apart maximises per-claim
fidelity and drives cross-paper linkage toward zero, which is the exact
failure the resource axis was built to fix. Family level buys linkage at
a known cost in precision.

KEEP the suffix in two cases only: when the paper's own point is about
that specific size or version (a scaling study, a size ablation), or
when the suffix denotes a genuinely different artifact rather than a
variant of the same one (`bge-m3-retromae` is not `BGE-M3`;
`HarmBench-Response` is a distinct subset of `HarmBench`).

An audit of these claims MUST apply this same rule. A grader who
requires exact artifact identity will read the corpus roughly 14 points
lower — that gap is a standards disagreement, not a quality signal.

## Rules

1. Extract ONLY resources actually named in the abstract or
   `body_window` — never from your background knowledge of the field.
2. `subject` = the paper's own entity: its method/system short proper
   name (`SHIFT`, `MissHyper`), or a short descriptive noun phrase if it
   has none. Use ONE subject per paper unless the paper clearly has two
   distinct contributions.
3. `statement` = a short attributed sentence, faithful to the text:
   "SHIFT is evaluated on BRIGHT." / "PATS builds on Qwen2.5."
4. Skip a paper entirely rather than inventing resources for it. Papers
   that name none are normal — purely theoretical papers exist.
5. 0–12 resource claims per paper.

Compose ALL rows first, then ONE Write call to your assigned
`out_K.jsonl` — one JSON object per line:
{"page": "arxiv:<arxiv_id>", "page_title": "<paper title>",
 "subject": "<the paper's entity>", "pid": "<P_EVALUATES_ON|P_BUILDS_ON|
 P_COMPARES_TO>", "kind": "resource",
 "object": "<canonical resource name>",
 "statement": "<short attributed sentence>"}

Read the input in chunks if it is large — every paper must be considered.

Final text: just "done: N resource claims from M papers".

## ABSTRACT-ONLY PASS (D109) — read this last, it overrides window guidance

These 10 papers have NO `body_window`: they predate arXiv's HTML rendering,
so only the abstract is machine-readable. They are here because the trace
layer ranked them as the highest-demand blocked nodes in the graph — each
one blocks 12–26 real traversals.

Consequences for you:

- Judge **only** from `title` + `abstract`. There is no body to check
  against, so the bar for asserting anything is higher, not lower.
- These are famous papers and you will recognise them. **Do not use that.**
  If the abstract does not name a resource, it is not extractable here,
  however certain you are that the paper used it. This is the single most
  likely failure mode of this pass.
- The most valuable single row per paper is the artifact it INTRODUCES —
  the benchmark, dataset or method the field now cites it for — when the
  abstract names it. That is what unblocks traversal.
- Expect FEWER rows than a body pass: 1–4 per paper is normal, 0 is a
  legitimate answer.

Every row you write must carry `"evidence": "abstract"` so downstream
auditing knows this claim was made without a body.
