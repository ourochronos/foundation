# Relation typing pass (D97 fix)

Input: your assigned `in_K.json` — ~60 items. Each is a resource a paper
mentions, plus the actual sentences (`contexts`) where the paper names
it. The resource itself is already decided. **Your only job is to decide
HOW the paper uses it — or that it should not have been extracted.**

Judge from the `contexts` alone. `current_pid` is a previous pass's guess
and is wrong often enough that you should ignore it until you have made
your own decision.

## The four verdicts

- **`P_EVALUATES_ON`** — the paper runs on it: an evaluation benchmark, a
  test set, or a corpus it trains/fine-tunes on. Signals: appears in an
  experimental-setup list, a datasets table, "we evaluate on…", "we train
  on…", a results-table column header.
- **`P_BUILDS_ON`** — the resource is *inside* the paper's system: a base
  model it fine-tunes, a backbone, an algorithm it adopts. Signals:
  "built on…", "we adopt…", "initialised from…", "X-based model",
  "backbone", "we use LoRA to adapt…".
- **`P_COMPARES_TO`** — the resource is a rival the paper measures itself
  against. Signals: a baselines list, "compared against…", a row in a
  results table that is not the paper's own method.
- **`DROP`** — the mention does not support any of the three.

## DROP is a real answer and you should use it

Drop when the context shows only:

- **a related-work mention** — "recent frameworks such as X show that…",
  "prior work X takes the opposite approach". Being discussed is not
  being used. This is the single most common error in the current data.
- **background about the field** — "generative AI, from GANs to diffusion
  models, presents a promising…" names GANs without the paper using them.
- **a generic term** — transformer, VAE, GAN, neural network, attention,
  fine-tuning. Not artifacts.
- **an incidental role** — a resource used as an LLM *judge*, an
  annotation tool, or a vendor whose API was queried, is none of the
  three relations.
**NEVER drop on a missing mention.** If the context says `*** no mention
located ***`, emit **`UNCERTAIN`** and the claim is kept for review. The
locator that builds these contexts is imperfect and has already thrown
away two claims whose evidence was demonstrably in the source (D98). A
tool's failure to find evidence is not evidence of absence, and a stage
that can delete must abstain instead.

## Distinctions that are being got wrong right now

- A **backbone or base model** is `P_BUILDS_ON`, never `P_EVALUATES_ON`.
  You evaluate on data; you build on models.
- **Training data** is `P_EVALUATES_ON` (that pid covers train and test),
  but a **data source** the paper assembled its own dataset from is
  `P_EVALUATES_ON` only if the paper reports results on it.
- A **harness, framework, or tool** the paper merely supports or runs
  inside is `DROP` unless the paper's contribution is built from it.
- A **benchmark evaluating other models** (when the paper IS the
  benchmark) types those models as `P_COMPARES_TO`.

Compose ALL rows first, then ONE Write call to your assigned
`out_K.jsonl` — one JSON object per line, one per input item, same order:
{"sid": "<copy verbatim>", "pid": "<P_EVALUATES_ON|P_BUILDS_ON|
 P_COMPARES_TO|DROP|UNCERTAIN>", "why": "<short — quote the deciding words>"}

Every input item gets exactly one output row.

Final text: just "done: N typed, E evaluates, B builds, C compares, D dropped, U uncertain".
