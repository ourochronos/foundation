# A purpose-built transducer — what to bundle, and what bundling costs

If we fine-tune, the interface is ours to define, and the temptation is to
bundle everything: coref, window state, structured output, tool calls. Most of
that is right. One part of it directly contradicts
[29-extraction-decomposition.md](29-extraction-decomposition.md), and that needs
answering rather than ignoring.

## 1. The tension, and its resolution

§29 argued that stages must stay **separable** because 0.155 recall is a product
and one number cannot say which stage to fix. A single bundled model is the
opposite: one box, one number, exactly the position that made REBEL's score
uninterpretable.

**The resolution is that measurability lives in the output schema and the gold,
not in the pipeline topology.** If the model emits a *structured* result whose
fields correspond to the stages, every stage is still scored separately even
though one model produced them all:

- mention spans → scored against mention gold
- coref ids → scored against coref gold
- predicate → scored against relation gold
- polarity → scored against negation gold
- attribution and scope → scored against gold we build

So: **bundle inference, decompose the output.** That keeps joint modelling's
real benefit — a decision informed by every other decision, no error propagation
between stages — while keeping the error budget legible. What we must *not* do
is bundle into an unstructured triple list, which is exactly what REBEL and
plasmon both emit and exactly why neither can be diagnosed.

## 2. The output schema

Every field earns its place from something measured, not from completeness:

```jsonc
{
  "entities": [
    {"id": "e1", "surface": ["Anthony Bourdain", "Bourdain", "the chef"],
     "type": "PER",                       // closed type vocabulary
     "link_proposal": "wikidata:Q311865", // PROPOSAL, never applied - see §4
     "link_confidence": "high"}
  ],
  "claims": [
    {"subject": "e1",
     "predicate": "P937",                 // closed vocabulary, or null + surface
     "object": {"entity": "e2"},          // or {"literal": ...} | {"marker": "NONE"}
     "polarity": "-",                     // exp78: 25.1% of philosophy needs this
     "scope": {"valid_time": {...}, "under_assumption": "compatibilism"},
     "attribution": {"holder": "e3", "mode": "reports"},
     "evidence_span": [412, 486],         // quote-never-reconstruct
     "flags": ["ambiguous: animal or action"]}   // plasmon's note:, generalised
  ]
}
```

**`polarity` is the field the whole exercise justifies.** No off-the-shelf
extractor emits it; REBEL asserts the falsehood a negated sentence denies; and
plasmon pushes negation into the object string so `allowed` and `not allowed`
become unrelated tokens. Two independent projects hit the same wall, and a
fine-tune is the only route through it.

**`flags` is the refusal principle applied to extraction.** A model that marks
ambiguity instead of silently resolving it is the extraction-time version of a
store that refuses rather than guessing — and it is the one plasmon idea worth
taking wholesale.

**`predicate: null` plus a surface form must be allowed.** Forcing every
relation into the closed vocabulary is how an extractor with no escape hatch
produces confident wrong labels; exp71 needed a skip option and still kept only
half its input.

## 3. Window state: yes, with a consequence

Feeding previous-window output into the next window is the right way to get
coref and entity consistency across a document — it makes the model's context
the coref state, which is what the task needs anyway.

**The consequence is that the unit of extraction becomes the document, not the
sentence.** The same sentence in two documents will legitimately yield different
entity ids, because coref is context-dependent. That is correct behaviour, but
it means a claim's content address cannot be a function of its sentence alone,
and any caching or dedup keyed on sentence text is wrong. Worth stating now:
the project has a determinism law, and this satisfies it at document scope while
breaking it at sentence scope.

Error propagation is the real cost — a wrong entity in window 1 poisons the
rest. Mitigation is cheap and should be in the schema from the start:
`link_confidence`, and letting a later window *revise* an earlier entity rather
than inheriting it silently.

## 4. Tool calls: propose, never apply

Letting the model query the store mid-extraction is attractive — it is entity
linking against our own vocabulary, which is the third of the three vocabularies
exp73 proved must close.

**But it breaks input→output determinism**: the same document extracted before
and after an unrelated ingest would produce different claims, because the store
changed underneath. Dedup, content addressing and reproducible re-runs all
depend on that not happening.

**The fix is already in the model.** Identity is a *defeasible claim*, not a
key. So extraction emits `link_proposal` and the closure decides, with its
existing acceptance policy and circuit breakers. Extraction stays a pure
function of the document; linking stays revisable; and a bad link can be
retracted without re-extracting anything. Tool calls become an *optimisation* of
the proposal's quality, not a load-bearing dependency.

## 5. One model or two

**One model, task prefixes** — plasmon's arrangement, and right for the same
reason: the schema is shared, the data volume is small, and decompose and
compose are inverse tasks whose shared representation should help both.

Two caveats:

- **Score them separately.** They have opposite failure modes — decompose
  misses claims, compose invents them — and one aggregate number would hide both.
- **Compose needs a hard constraint decode is unlikely to give.** "No facts
  beyond the input triples" is quote-never-reconstruct, and a fine-tune reduces
  violations without eliminating them. Whatever the model emits, the renderer
  should still be checked against the input triples mechanically before output.

## 6. What this makes the bottleneck

Not the model, the hardware, or the schema. **The training set** — and it is the
same artifact as the gold set, since attribution, scope and polarity have no
public benchmark (§29).

Which sets the order of work:

1. **Fix the schema** (§2) — cheap, and everything downstream is shaped by it.
2. **Run the prompt benchmark** — {REBEL, Gemma 4, Haiku} × prompt variants on
   Re-DocRED. It establishes the no-training baseline a fine-tune must beat, and
   the winning prompt becomes the **teacher** that drafts training data.
3. **Build gold on the fields nothing else measures** — polarity, attribution,
   scope. Teacher-drafted, human-corrected, held out from training.
4. **Then fine-tune**, and hold that gold out permanently — a self-reinforcing
   loop with no external anchor has no signal that would reveal drift.
