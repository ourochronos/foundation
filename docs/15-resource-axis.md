# The resource axis — pre-registered protocol (2026-07-27)

Registered BEFORE the run, per D64. Criteria and predictions frozen at
commit time. Follows D94, which located the problem: papers' subjects are
their own new methods and never join, while the entities papers actually
share sit in object position and were never extracted as entities.

## Feasibility, measured before designing

Over the AI slice's retained fulltext, cleaned of arXiv page furniture
(`foundation/fulltext.py`; the raw extract stays immutable, cleaning
happens on read):

- **93 of 467 papers are `/abs/` fallbacks with no body** — the fetch
  fell back when no HTML render existed, so their "fulltext" is an
  abstract page of third-party widgets. Excluded from this pass and
  recorded as a corpus-quality fact.
- Over the remaining **374 papers**: 1,091 candidate names appear in >1
  paper, **560 in ≥3, 260 in ≥5, 103 in ≥10, 38 in ≥20** — against
  **zero** shared method-name subjects (D94). Head is genuinely
  resource-like (Qwen3 57, Qwen2.5 46, SFT 35, AdamW 34, LoRA 33,
  GPT-4o 28, GRPO 27) mixed with junk a regex cannot reject (MLP, III,
  RQ1, IV-B, NVIDIA, JSON) — which is precisely the judgement the fleet
  exists to make.
- A leading window misses benchmarks, which live in experimental setup:
  `resource_window()` returns intro + experiment regions and triples
  benchmark coverage (39 → 116 mentions of a fixed 21-benchmark probe
  list) at ~8k chars per paper.

## What gets extracted

Three relations, each naming a resource the paper did not invent:

- `P_EVALUATES_ON` — evaluated on this benchmark/dataset
- `P_BUILDS_ON` — built on / fine-tuned from this base model or prior method
- `P_COMPARES_TO` — compared against this baseline

`subject` = the paper's own entity under D94's naming rule. `object` =
the resource's **canonical short name as the community writes it**
(`GSM8K`, not "the GSM8K benchmark"; `Qwen2.5`, not "Qwen-2.5"). No
`object_page` — resources have no page, so they must join through
consistent naming alone via the registry's exact-form index. **That is
the experiment**: whether naming discipline at extraction is sufficient
to make one entity out of a resource named by fifty papers.

## Pre-registered criteria

1. **Cross-paper population**: ≥100 resource objects shared by ≥3
   distinct papers.
2. **Resource-claim precision ≥0.80** on a frozen 50-claim audit graded
   against each paper's own window text. This is a **NEW instrument**,
   declared rather than an amendment: these claims come from body text,
   so the abstract-graded D92 instrument does not apply and is left
   untouched.
3. **Name fragmentation**: for the 20 most-shared resources, ≥0.90 of
   their mentions resolve to a single eid. Variants that split
   (`Qwen2.5` / `Qwen-2.5` / `Qwen2.5-7B`) are the failure mode.
4. **No collateral damage**: existing claims untouched, soak battery
   green, suite green.

## Predictions (recorded now, scored later)

1. Cross-paper structure will exceed the method layer by one to two
   orders of magnitude — the method layer was exactly 0.
2. **Fragmentation, not precision, will be the binding constraint.**
   Extraction will get the facts right and the names inconsistent.
3. Benchmarks will join better than base models, because benchmark
   names are standardized while model names carry version and size
   suffixes that papers cite differently.

## What each outcome means

- **All criteria pass** → the resource axis is the cross-paper
  substrate; store-aware linking (D94's Arm B, untested) finally has a
  population to be re-tested against, with balanced language and the
  corrected two-sided decline bound.
- **1 and 2 pass, 3 fails** → expected per prediction 2; the fix is an
  alias/normalization layer over resources, which is the D61 relation-
  canonicalization debt in its entity form. Still adoptable.
- **2 fails** → body-text extraction is not reliable enough at this
  window size; fall back to abstract-only resources and accept a
  thinner axis.

## Constraints

- Raw fulltext is immutable; cleaning is read-time only.
- `statement` stays extractive and faithful to the window it came from.
- Extractor proposes, `codec/individuation.py` disposes.
