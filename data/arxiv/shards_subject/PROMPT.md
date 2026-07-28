# Subject canonicalisation pass (D98 fix, applying D94's naming rule)

Input: your assigned `in_K.json` — ~50 papers, each with its `title`,
`abstract`, the `current_subjects` a previous pass used, and how many
claims hang off them.

For each paper, decide **the one name its claims should be filed under**.
This is D94's rule, which measurably collapsed subject fragmentation on
the abstract pass and was never applied here.

## The rule

Write **the shortest name that stands alone** — the name the authors
would use in a later paper, or that another paper would use when citing
this one. Prefer the bare proper name.

- Good: `SHIFT`, `MissHyper`, `MedGame`, `CultureTalk-ID`, `MoE²-LoRA`
- Bad: `SHIFT retrieval performance`, `MedGame user perception`

If the paper's contribution has no proper name, use a short descriptive
noun phrase — `prompt-contrastive editing`, `sidewalk segmentation` —
not a sentence and not a topic area.

## What to fix

`current_subjects` is frequently wrong in specific ways. Repair them:

- **stopwords and article fragments** — `"The"`, `"A"`, `"This"` are not
  names. Read the title and abstract and supply the real one.
- **title fragments** — `"Fast ANNS"` from *Fast and Efficient
  Approximate Nearest Neighbor Search…*, `"Pixels for Programs?"` from a
  title that is a question. A paper's title is not its method's name; if
  the method has no name, describe it briefly instead.
- **descriptions masquerading as names** — `"Document packet splitting
  system"` is acceptable only if the paper truly names nothing.
- **trailing punctuation**, quotes, LaTeX residue (`$M^3$-Gen` →
  `M³-Gen`), and citation markers.

If `current_subjects` already holds a good short proper name, keep it
**verbatim** — do not improve names that are already right.

## Judgement call

Some papers introduce a benchmark AND a method. Pick the one the paper
leads with, which is nearly always the one in the title.

Compose ALL rows first, then ONE Write call to your assigned
`out_K.jsonl` — one JSON object per line, one per input paper:
{"page": "<copy verbatim>", "subject": "<the canonical name>",
 "changed": true|false, "why": "<short, only when changed>"}

Every input paper gets exactly one output row.

Final message: just "done: N pages, C changed".
