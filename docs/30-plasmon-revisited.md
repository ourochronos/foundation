# Plasmon — a fourth extraction option, and where its data stops short

`Ourochronos/valence-plasmon` — "NL↔triples transduction layer", Python, last
touched March 2026. Read because the live question is how to get trustworthy
extractions efficiently, and plasmon is *exactly* that problem approached a way
this project had not considered.

## 1. What it is

**Fine-tune a small model (1.5–4B) for three transduction modes**, with task
prefixes, LoRA on the same RX 9070:

- `[DECOMPOSE]` NL → triples
- `[COMPOSE]` triples → NL
- `[QUERY]` NL question → graph operation plan

It is not a design sketch. There is ~1.5 MB of decompose training data across
ten batches, plus compose, query and validation sets, plus working
`train.py` / `evaluate.py` / `inference.py` / `serve.py` and a GGUF export path.

**Its three modes are [24-composition-and-queries.md](24-composition-and-queries.md)
§6 arrived at independently** — "the LM appears exactly twice, compiling in and
rendering out", plus a query compiler. Two projects reaching the same division
of labour without contact is worth more than either reaching it alone.

Its Decompose "challenges" list is also
[29-extraction-decomposition.md](29-extraction-decomposition.md)'s stage
breakdown in prose: ambiguity, granularity, predicate selection, coreference.
And its evaluation metrics — triple F1 against gold, predicate accuracy, entity
normalisation — are exp76.

## 2. Why it is a genuine fourth option

The options so far were: prompt a generalist (Gemma, Haiku), adopt a
purpose-built model (REBEL, GLiNER, ReLiK), or author an ontology. Fine-tuning
is different in one decisive respect:

**It is the only option that can learn *our* schema.** REBEL cannot express
polarity at any beam width — exp29 verified it emits the falsehood a negated
sentence denies, and exp78 measured 25.1% of philosophical triples coming from
negated sentences. No off-the-shelf extractor emits attribution or scope
either, and those are what `under_assumption` and scoped coexistence run on. A
fine-tuned model can be taught all three, because the target format is ours to
define.

Cost is that the training data must exist. Which is the same artifact
[29](29-extraction-decomposition.md) already said we must build: attribution and
scope have **no public benchmark**, so we need gold there regardless. **The gold
set and the training set are the same artifact**, and that changes the
cost-benefit materially — it is one build serving evaluation and training both.

## 3. Where plasmon's data stops short of what we need

Read the actual JSONL rather than the design doc, and three gaps matter:

**Negation is pushed into the object string.** `"No Friday deploys"` becomes
`(Friday deploys, policy, not allowed)`. The denial survives as an opaque token
inside an object, so `not allowed` and `allowed` are unrelated strings rather
than a detected contradiction. That is **the same blind spot as REBEL**, reached
by a different route — which is evidence the gap is genuinely non-obvious rather
than an oversight in either project.

**Predicates are open vocabulary.** `scheduled`, `is_ready_for`, `policy`,
`frequency`, `states` — invented per example. exp69 and exp73 measured what that
costs: with predicates unclosed, corroboration is impossible by construction.
Training on this data would teach a model to produce exactly the fragmentation
we measured.

**Confidence is a scalar.** `[confidence:high, weight_hint:0.85]`. Model v1 §2
argued that collapses at least four independent dimensions — extraction
fidelity, belief, source reliability, identity confidence. Notably the same org
has an `our-confidence` repo described as *dimensional* confidence scoring, so
that critique appears to have been reached later there too.

Also worth flagging: parts of `data/validation/decompose.jsonl` are degenerate —
`(belief:4c8e41f9db9b, states, <the entire input paragraph>)` is not
decomposition into atomic triples, it is the input wrapped in a triple. As a
validation set that would score a model well for doing nothing.

## 4. What to take

**Take the approach.** Fine-tuning a 1.5–3B model is the only route to polarity,
attribution and scope in one pass, and plasmon proves the hardware path works on
this exact GPU with working code.

**Take two data-design ideas.** The `note:` field — `note:ambiguous—animal or
action` — is the refusal principle applied to extraction: a model that *flags*
ambiguity instead of silently resolving it. And the edge-case batch design,
deliberately building syntactic-ambiguity cases rather than sampling for them.

**Do not take the data as-is.** Open predicates and object-string negation are
the two things measurement has already shown to be fatal, and training on them
would bake both in.

**The self-reinforcing loop needs a guard.** "Better transduction → richer graph
→ more training data → better transduction" is also the shape of error
amplification: a model trained on its own output drifts, and Covalence's own
lesson was belief *oscillation* from stacked epistemics. Any nightly-retraining
loop needs held-out human gold that never comes from the model, or there is no
signal that would reveal drift.

## 5. Consequence for the extraction plan

The benchmark grid stands — {REBEL, Gemma 4, Haiku} × prompt variants, on
Re-DocRED — because it establishes what is achievable *without* training, which
is the baseline any fine-tune must beat to be worth its cost.

But it gains a fourth arm to plan for, and a sharper purpose: whatever prompt
wins the grid becomes the **teacher** that generates fine-tuning data, and the
gold we must build for attribution and scope is the same set that evaluates it.
