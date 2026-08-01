# Design-commitment review: the extraction schema

**This is not a code review.** The artifact under review is a *schema*, and the
commitment it represents is a hand-corrected training/gold set annotated
against it. A schema change after annotation invalidates the annotation, so
this is the most expensive thing in the project to get wrong and the cheapest
to get wrong *now*.

The author's framing: *"we need to make sure that the design is something that
will last, since it'll be the sunk cost."*

Please answer as if the annotation budget is real and non-renewable.

---

## 1. Where this came from — the measurements, so you can check the reasoning

Thirteen experiments, most of which refuted something. The ones that shape this
schema:

| finding | measurement |
|---|---|
| extraction recall is the ceiling on everything | REBEL 0.222P / 0.155R vs human gold (Re-DocRED); every corroboration and conflict count in the project is a lower bound |
| beam count is a free 33% recall gain | 0.168 → 0.223 at beams 3→5, F1 peak |
| purpose-built beats generative — **on an unoptimised prompt** | REBEL P 0.222 vs Gemma 4 12B P 0.185, same docs, same vocabulary. The prompt was a first draft never iterated; this comparison is confounded and is one reason for the benchmark below |
| **REBEL cannot express negation, and inverts it** | *"Paris is not the capital of Germany"* → `(Germany, capital, Paris)`. It asserts the exact falsehood |
| negation is not a tail case | 25.1% of philosophy triples, 12.4% economics, 8.5% news come from sentences with a proposition-reversing cue. Predicted rarer in reportage; **refuted** |
| corroboration exists only in reportage | 0 across four discourse corpora; 41 corroborated triples in multi-source news. Discourse *cites and disputes*, it does not repeat |
| three vocabularies must close **simultaneously** | predicates + frames closed, entities open → still 0 corroboration (316 claims → 510 distinct concepts) |
| scoped coexistence works | opposed positions carrying `under_assumption` produce 0 conflicts scoped, 18 unscoped |

Two prior-art systems by the same author hit the same wall independently:
**Covalence** (blanket LLM extraction is a dead end; coref-resolved
self-contained statements) and **plasmon** (a fine-tune with ~1.5MB of training
data, which pushes negation into the object string so `allowed` and
`not allowed` become unrelated tokens).

## 2. What is proposed

**Fine-tune a 1.5–3B model** (LoRA, 16GB consumer GPU — the hardware path is
proven by plasmon) as a transducer with task prefixes: decompose, compose,
query. Chosen because it is **the only option that can learn polarity,
attribution and scope**, none of which any off-the-shelf extractor emits.

**Bundle inference, decompose the output.** The measurability argument that
made per-stage pipelines attractive is preserved by the *schema*, not by the
topology: one model emits a structured result whose fields correspond to
stages, and each field is scored against its own gold.

```jsonc
{
  "entities": [
    {"id": "e1", "surface": ["Anthony Bourdain", "Bourdain", "the chef"],
     "type": "PER", "link_proposal": "wikidata:Q311865",
     "link_confidence": "high"}
  ],
  "claims": [
    {"subject": "e1",
     "predicate": "P937",            // closed vocab, NULLABLE with surface fallback
     "object": {"entity": "e2"},     // | {"literal": ...} | {"marker": "SOME"|"NONE"}
     "polarity": "+" | "-",
     "scope": {"valid_time": {...}, "valid_place": ..., "under_assumption": "..."},
     "attribution": {"holder": "e3", "mode": "asserts|reports|infers|predicts"},
     "evidence_span": [412, 486],
     "flags": ["ambiguous: animal or action"]}
  ]
}
```

Decisions already taken, with reasons:

- **window state yes** → extraction unit becomes the *document*, since coref is
  context-dependent; sentence-keyed dedup would be wrong
- **tool calls propose, never apply** → querying the store mid-extraction breaks
  input→output determinism; identity is a defeasible claim in the store model,
  so extraction emits `link_proposal` and the closure decides
- **one model, task prefixes, scored separately** → decompose misses, compose
  invents; one aggregate hides both

## 3. What it connects to

The store (model v2) has: content-addressed immutable **assertions**
`(subject, predicate, object, polarity, truth_conditional_qualifiers)`;
**claim acts** `(assertion, claimant, evidence, mode, time)`; a defeasible
identity closure; a predicate lattice with subsumption and opposition; and
scope overlap where an absent qualifier means unrestricted.

**An unresolved mapping question, raised by the author against his own design:**
when a source says *"Keynesians hold that X"*, is `Keynesians`

- the **claimant** of a claim act (someone asserting X), or
- an **`under_assumption` qualifier** on the assertion (X holds within that
  frame), or
- both?

exp72 used the qualifier reading and scoped coexistence worked. But the claimant
reading is what `claim_act` exists for. Getting this wrong means annotating
thousands of examples against the wrong target.

## 4. What to answer

1. **Which field will we regret?** Name the one that proves unannotatable, has
   poor inter-annotator agreement, or turns out to mean two different things.
   Rank the fields by *annotation cost per unit of downstream value*.
2. **What is missing that a schema change would later force?** The test is not
   "what would be nice" but "what will invalidate the annotation when added".
3. **Attribution vs claimant (§3).** Answer it directly. If both, say what
   distinguishes them at annotation time.
4. **Is "bundle inference, decompose output" sound**, or does a single model
   trained on a joint objective produce fields that are individually scorable
   but not individually *meaningful*?
5. **Steelman not doing this.** What is the strongest case for prompt
   engineering an existing model, or a per-stage pipeline of off-the-shelf
   parts, and what evidence would settle it?
6. **What is the smallest schema that still works?** Every field multiplies
   annotation cost. Which would you cut, and what breaks?

Commit to positions. Disagreement between you is more useful than consensus,
and a recommendation to abandon this is a legitimate answer.
