# Extraction, decomposed — what the parts are, and how to compare them separately

Extraction has been treated as one black box for twelve experiments, and it
returns **recall 0.155**. That single number is the *product* of several stages,
so it says nothing about which stage to fix. Worse, a serial pipeline
multiplies: four stages at a respectable 0.90 / 0.80 / 0.85 / 0.70 already cap
end-to-end recall at **0.43**, and we sit well below even that — which means
either one stage is much worse than typical or there is loss outside the four.
There is no way to tell from one number.

So the first move is not a better extractor. It is **an error budget**.

---

## 1. The stages

Grouped by what they do to the text, with the ones we currently do implicitly
or not at all marked.

| # | stage | question it answers | our status |
|---|---|---|---|
| 1 | **segmentation** | what span is a claim extracted *from*? | per-sentence, never examined |
| 2 | **mention detection** | which spans are entities? | implicit inside REBEL |
| 3 | **coreference** | which mentions are the same thing *in this document*? | **absent** |
| 4 | **entity linking** | what canonical id is this mention? | **absent** — surface forms only |
| 5 | **relation extraction** | which relation holds between which pair? | REBEL / Gemma |
| 6 | **predicate canonicalisation** | which closed-vocabulary predicate is it? | free from REBEL, mapped for Gemma |
| 7 | **attribution & scope** | *who holds it*, under what assumption, when, where? | Gemma prompt only, unmeasured |
| 8 | **polarity** | is the relation asserted or **denied**? | **absent from REBEL** |
| 9 | **evidence span** | which text supports it? | page-level, not span-level |
| 10 | **novelty gating** | is this already known? | **absent** (Covalence's lesson) |
| 11 | **admission** | should this enter the store at all? | skip-option only |

**Stage 8 is not a gap — it is a fabrication bug, and it was verified rather
than assumed:**

    "Paris is not the capital of Germany."       -> ('Germany', 'capital', 'Paris')
    "Lyon has never been the capital of France." -> ('France',  'capital', 'Lyon')

REBEL does not merely drop the negation; it emits **the exact falsehood the
sentence denies**, as a confident positive assertion. Downstream this is worse
than a miss in every direction: the fabricated claim enters the store, is
attributed to a real source with a real span, and then **conflicts with the true
claim** — so a system built to surface disagreement reports one that does not
exist, sourced to a document that says the opposite.

This is the same shape as the date-as-entity bug of exp67, which manufactured
104 false contradictions about real people's birthdays, and it is the reason
stage 8 cannot be an optional add-on. **Any relation extractor that ignores
negation needs a polarity pass in front of the store, not behind it.** For a
corpus of argumentative text — where "X does not follow from Y" is the normal
sentence — the rate matters enormously and is currently unmeasured.

## 2. What can be measured separately, and against whose gold

Availability probed, not assumed:

| stage | public gold | notes |
|---|---|---|
| 2 mention detection | **CoNLL-2003** (23k dl), OntoNotes, Few-NERD | mature, uncontroversial |
| 3 coreference | **GAP**, OntoNotes/CoNLL-2012 | GAP is pronoun-focused; OntoNotes is full coref |
| 4 entity linking | **`cyanic-selkie/aida-conll-yago-wikidata`** | AIDA-CoNLL linked to **Wikidata** — exactly our target id space |
| 5 relation extraction | **Re-DocRED**, TACRED | already in use (exp76/77) |
| 6 predicate canon. | derivable from 5 | REBEL's vocabulary *is* Wikidata properties |
| 8 polarity | **BioScope**, SFU-Review-SP-Neg | negation cue + scope, annotated |
| **7 attribution & scope** | **NOTHING FOUND** | see below |

**The stage this project cares most about is the one with no benchmark.**
Attribution — "Keynesians argue that…", the thing that becomes
`under_assumption` and makes scoped coexistence work — has no off-the-shelf
gold we can find. PARC3/PolNeAR-style corpora did not surface. Two consequences:
it is the stage where we must build our own gold, and it is the stage where we
cannot compare against prior art, which is also the honest place to look for
whatever is actually novel here.

## 3. Model options per stage

| stage | candidates | note |
|---|---|---|
| 2 | **GLiNER2** (546k dl, caller-specified labels), spaCy, flair | GLiNER lets the *label set* be closed at inference — directly serves a closed entity-type vocabulary |
| 3 | **`biu-nlp/f-coref`** (94k), `lingmess-coref` (39k) | f-coref is the speed-oriented one; lingmess the accurate one |
| 4 | **ReLiK** entity-linking, BLINK, GENRE | ReLiK links into Wikipedia and pairs with its RE model |
| 5 | **REBEL** (Wikidata PIDs, ~400M), ReLiK-RE, LLM+closed vocab | measured: REBEL P 0.202 / R 0.223 at beams=5 |
| 7 | LLM only | no purpose-built option found |
| 8 | negation-cue taggers, or LLM | REBEL cannot express it at all |
| 10 | embedding-distance gate over the store | no model needed |

## 4. Architecture: serial, joint, or hybrid

**Serial** (2→3→4→5→…) is fully decomposable: every stage swappable, every
stage separately measurable, and the error budget is legible. Cost is
compounding — a mention lost at stage 2 is unrecoverable at stage 5.

**Joint** models fold stages together. REBEL folds 2+5+6; ReLiK folds 4+5. Less
error propagation, but the folded stages become unmeasurable and unswappable —
which is exactly the position we are in now and why 0.155 is uninterpretable.

**The useful rule** is that stages should be joined where they are *mutually
informing* and kept separate where they are not:

- **4+5 genuinely benefit from joining** — knowing an entity is a *company*
  constrains which relations are plausible, and knowing the relation constrains
  the linking. ReLiK exists because of this.
- **3 belongs before everything** — coref is document-scoped and feeds every
  later stage. Covalence's "self-contained, coref-resolved statement" puts it
  first for exactly this reason, and exp75's alias barrier is what happens when
  it is missing.
- **7, 8, 10 are separable and should stay separate** — attribution, polarity
  and novelty are orthogonal to which entities and relation are present, and
  keeping them separate is what makes them individually measurable. They are
  also the three where we would be building rather than adopting.

Which suggests a **hybrid**: coref first, then a joint linking+RE core, then
independent attribution / polarity / novelty passes over its output.

## 5. The experiment this implies, before any building

**Measure the error budget.** Run each stage against its own gold, in isolation,
and see where 0.155 actually goes:

1. mention detection on CoNLL-2003 — is stage 2 the loss?
2. coref on GAP — how much would adding stage 3 recover?
3. entity linking on AIDA-Wikidata — what does canonicalisation cost?
4. relation extraction on Re-DocRED — already have it: 0.202 / 0.223
5. polarity on BioScope — quantify the hole REBEL leaves

Then compare the **product of the stage scores** against the measured
end-to-end 0.155. If the product is much higher, the loss is in the joins
(segmentation, cross-sentence relations, vocabulary mismatch) rather than in
any component, and swapping components would be wasted effort.

That is one measurement per stage, all against external gold, and it converts
"extraction is bad" into "stage N is bad" — which is the difference between
research and guessing.
