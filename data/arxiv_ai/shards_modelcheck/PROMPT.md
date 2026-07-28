# Model-as-target re-decision (D99 residue)

Input: your assigned `in_K.json`. Every item is a claim currently typed
`P_EVALUATES_ON` whose object is a **model** (GPT-3, Llama 3, Qwen2.5,
RoBERTa…), not a dataset or benchmark. That combination is wrong by
construction — you evaluate on data, not on a model — so each of these
needs one correct answer instead.

This error is not the extractor being careless: papers genuinely write
"we evaluate on GPT-3", meaning "we evaluate our method applied to
GPT-3". Your job is to recover which relation that sentence really
expresses.

## Choose one

- **`P_BUILDS_ON`** — the paper's method is applied TO this model: it
  adapts, fine-tunes, wraps, steers, or is implemented on top of it. The
  model is the substrate the contribution runs on. `LoRA is evaluated on
  GPT-3` means LoRA adapts GPT-3 → `P_BUILDS_ON`. This is the most
  common correct answer.
- **`P_COMPARES_TO`** — the model is a rival system whose scores the
  paper measures itself against, or (when the paper IS a benchmark) a
  model the paper evaluates and reports on.
- **`DROP`** — the model is incidental: an LLM judge, an annotation
  tool, a data-generation helper, a vendor API queried for a
  measurement, or a passing mention.
- **`UNCERTAIN`** — the item does not give you enough to choose. Keep it
  rather than guessing; a wrong relation is worse than a held one.

## Deciding

`subject` is the paper's own contribution and `typing_why` records what
an earlier pass saw. Ask: **is this model the thing the paper built on,
the thing it competed with, or neither?**

- A benchmark paper listing many models it scored → `P_COMPARES_TO`.
- A method paper naming the one or two models it was implemented on →
  `P_BUILDS_ON`.
- A model used only to grade, label, or generate → `DROP`.

Compose ALL rows first, then ONE Write call to your assigned
`out_K.jsonl` — one JSON object per line, one per input item:
{"sid": "<copy verbatim>", "pid": "<P_BUILDS_ON|P_COMPARES_TO|DROP|
 UNCERTAIN>", "why": "<short>"}

Final text: just "done: N decided, B builds, C compares, D dropped, U uncertain".
