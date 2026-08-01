I'll ground the review in the repo's actual schema and experiments, then answer the six questions with committed positions.

● Explore repo structure (shell)
  │ ls -la && find . -maxdepth 3 -type f \( -name "*.md" -o -name "*.json" -o -name "*.jsonc" -o
  │ -name "*.py" -o -name "*.yml" \) 2>/dev/null | head -80
  └ 117 lines…

Reading the core design docs that define the schema commitment.

● Read 25-model-v2.md
  │ docs/25-model-v2.md
  └ 1 line read

● Read 31-transducer-design.md
  │ docs/31-transducer-design.md
  └ 141 lines read

● Read 29-extraction-decomposition.md
  │ docs/29-extraction-decomposition.md
  └ 157 lines read

● Read 32-transducer-brief.md
  │ docs/32-transducer-brief.md
  └ 119 lines read

● Read schema_v0.json
  │ data/schema_v0.json
  └ 756 lines read

Pulling model-v2 claim/assertion semantics and related decision notes.

● Read decisions.md
  │ docs/decisions.md
  └ L1:150 (148 lines read)

● Read 25-model-v2.md
  │ docs/25-model-v2.md
  └ L1:200 (199 lines read)

/ Search (grep)
  │ "under_assumption|claim_act|claimant|attribution|polarity|scope" in docs/**/*.{md,json}
  └ 23 files found

/ Search (grep)
  │ "exp72|under_assumption|claimant|Keynesian" in **/*.{md,py,json,log}
  └ 120 files found

● Read exp72_scoped_conflict.json
  │ results/exp72_scoped_conflict.json
  └ L1:100 (22 lines read)

● Read exp72_scoped_conflict.py
  │ scripts/exp72_scoped_conflict.py
  └ L1:120 (120 lines read)

/ Search (grep)
  │ "under_assumption|claim_act|claimant|truth_conditional|attribution|qualifier" in
  │ docs/25-model-v2.md
  └ 5 lines found

● Find claim act implementation (shell)
  │ rg -n "claim_act|under_assumption|ClaimAct|truth_conditional|polarity" foundation/ --type py |
  │ head -60; ls foundation/model/
  └ 9 lines…

● Read conflict.py
  │ foundation/model/conflict.py
  └ L1:150 (148 lines read)

● Read 25-model-v2.md
  │ docs/25-model-v2.md
  └ L200:350 (150 lines read)

● Read 23-model-v1.md
  │ docs/23-model-v1.md
  └ L1:200 (199 lines read)

/ Search (grep)
  │ "claimant|Claim\(|under_assumption|assertion|claim act|ClaimAct" in foundation/**/*.py
  └ 21 lines found

Checking Claim structure and nested-attribution edge cases that could force a later schema rewrite.

● Read conflict.py
  │ foundation/model/conflict.py
  └ L150:250 (100 lines read)

● Read 28-covalence-revisited.md
  │ docs/28-covalence-revisited.md
  └ L1:80 (80 lines read)

● Read 30-plasmon-revisited.md
  │ docs/30-plasmon-revisited.md
  └ L1:80 (80 lines read)

# Design-commitment review: extraction schema

**Bottom line:** Keep the schema commitment, but **cut it hard** and **split assertion from act**. Do not annotate the bundled claim object as drawn. Do not start full fine-tune gold until a 300-example probe kills the prompt/hybrid alternatives.

---

### 1. Which field will we regret?

**`attribution.mode` (`asserts|reports|infers|predicts`).**

It has no stable annotation rule. Every document “reports”; “Keynes argued” is historical assert *and* report; “models imply” is infers *or* asserts. You will burn budget, get κ ≈ noise, and train a head that memorizes verb surface forms.

**`scope` as a free-form bag is the structural regret** — especially free-text `under_assumption` dual-used with `holder` (see §3). exp72’s 0 scoped conflicts is near-forced once every position gets its own frame (v2 panel already said this).

**Cost / downstream value (worst → best):**

| rank | field | cost/value |
|---|---|---|
| 1 | `attribution.mode` | high cost, near-zero reliable value |
| 2 | `link_proposal` + `link_confidence` | linker skill, not extractor skill; closure decides anyway |
| 3 | `entity.type` | cheap-ish, mostly recoverable later |
| 4 | `valid_time` / `valid_place` | expensive specialist skill; defer |
| 5 | free-text `under_assumption` without a closed frame list | high cost, high value *only* if closed |
| 6 | `flags` | fine as human overflow, worthless as train target |
| 7 | `holder` / claimant | expensive, load-bearing |
| 8 | `predicate` (closed, nullable + surface) | expensive, load-bearing |
| 9 | `polarity` | moderate cost, **highest** value |
| 10 | `evidence_span` | moderate cost, audit-critical |
| 11 | entity `id` + `surface[]` | necessary substrate |

**Regret name:** `mode`. Delete before any gold is written.

---

### 2. What is missing that forces later invalidation?

Three holes that **cannot be patched by adding an optional field later** without rewriting labels:

1. **Assertion ≠ claim-act (store already knows this; schema forgot).**  
   One `claims[]` row collapses `(s,p,o,polarity,scope)` with `(holder, mode, evidence)`. Nested discourse — *“The Times reported that Keynesians hold that X”* — needs **two acts** (or act-about-act) over one assertion. A flat `attribution.holder` cannot grow into that; every row must be re-sliced.

2. **Document-default claimant is unrepresented.**  
   Who is the claimant when there is no “X said”? If you later add `source_id` / outer reporter as a first-class act, bare claims with `holder: null` become ambiguous (null = author? null = world? null = unknown?). Bake **`source_act` default** in now: every assertion is introduced by at least one act whose claimant is the document unless an in-text holder overrides/nests.

3. **Hedge/modality ≠ polarity.**  
   “Paris is not…” vs “Paris may not be…” vs “No evidence that Paris is…”. Binary `+/-` will absorb hedges as negations or drop them. When you add `certainty` / `hedge`, polarity labels on hedged sentences are wrong and must be redone. Add **`commitment: factual | hedged | questioned`** (or force hedged spans into `flags` with a hard rule: *do not assign +/- under hedge* — refuse the triple). Silence here guarantees rework.

Honorable mention (cheaper if absent-means-unrestricted stays law): per-mention spans for coref. Surfaces-only is migratable; don’t block on it.

**Not missing in a breaking way:** Wikidata links, types, compose/query outputs.

---

### 3. Attribution vs claimant — direct answer

**They are different. Default is claimant, not `under_assumption`. Not both.**

| signal in text | annotate as | why |
|---|---|---|
| Agentive speech/attitude: *hold, argue, say, claim, deny, write* | **`claim_act.claimant`** (+ evidence span) | Someone performed an act; agreement/provenance live here |
| Frame-conditional: *under/in [theory/model/assumption], assuming…* | **`under_assumption`** on the **assertion** | Truth-conditional restrictor; drives scope overlap |
| School as collective agent: *“Keynesians hold that X”* | **claimant = Keynesians only** | They are cast as holders of a belief about the world |
| Explicit dual: *“In the Keynesian framework, X”* said by no agent | **under_assumption only**; claimant = document | Frame, not speech act |

**Annotation test (one question):**  
*If the holder were wrong about the world, is the sentence still true as a description of their position?*  
- Yes → claimant (report of a view).  
- No — the sentence is only evaluating X inside a model → `under_assumption`.

**exp72 dual-tagging was a convenient confound**, not a design answer. Scoped coexistence should be a **policy over claimants in a Frames registry** (or a derived promotion: `if claimant ∈ Frame then copy to under_assumption` at ingest), not something annotators double-enter. Double entry will drift and destroy IAA.

**Document author** is always the outer `reports` act. In-text holder is inner. Schema must allow nesting or an act chain; a single optional `attribution` block does not.

---

### 4. Is “bundle inference, decompose output” sound?

**Sound as a regression harness. Unsound as the error-budget instrument §29 promised.**

- Field F1 on joint output is **conditional on the claim being emitted**. Polarity@extracted can look great while the model systematically drops negated sentences — the failure mode you care about. Scorable ≠ stage-capable.
- Joint training makes errors **correlated**. “Individually meaningful” fields require that a correct polarity not depend on a memorized (predicate, cue) co-occurrence with that subject. You will not see that from per-field F1.
- Opposite failure modes of decompose/compose are real; prefixes help. They do not make decompose’s internal latent stages modular.

**Verdict:** Keep structured output and per-field scores as **release gates**. Do **not** skip the §29 isolated stage measurements (BioScope polarity, GAP coref, Re-DocRED RE, AIDA linking). Those answer “what to fix”; joint field F1 only answers “did we regress.”

If you only get one diagnostic: **score polarity and holder on gold spans forced as input** (given entities+predicate, predict +/- and holder). That is the meaningful head test. End-to-end joint F1 is not.

---

### 5. Steelman not doing this

**Strongest case:** The fine-tune is solving the wrong bottleneck with the most expensive artifact.

1. **Confounded premise.** REBEL > Gemma was on a first-draft prompt. Purpose-built may still win on bare RE; it does not prove generative cannot learn polarity/attribution with a real prompt + constrained decode.
2. **Hybrid is the §29 recommendation you abandoned without the error budget.**  
   `coref → ReLiK/REBEL →` small polarity tagger (or LLM classify on triple+sentence) `→` LLM attribution only. Gold needed shrinks to **holder + polarity on candidate triples**, not full document transduction.
3. **Plasmon already failed negation structurally on small data** (negation shoved into object strings). 1.5–3B LoRA with a few thousand hand fixes risks schema cosplay, not epistemics.
4. **Recall is the ceiling** (0.155–0.223). A richer schema on a weak emitter produces beautifully typed misses. Beams bought 33% recall for free; that class of gain is not in the gold schema.

**Evidence that settles it (run before annotation scale-up):**

| result on a frozen 300-example probe | decision |
|---|---|
| Iterated prompt (Gemma/Haiku) polarity F1 ≥ 0.85 **and** holder F1 ≥ 0.70 | **Do not fine-tune.** Prompt + constrain. |
| REBEL+polarity-guard recovers ≥ 90% of negation-inversion errors on exp78-style set | Polarity is a **bolt-on**, not a transducer justification |
| Product of off-the-shelf stage scores ≫ end-to-end joint | **Hybrid pipeline**; gold only for stages with no public benchmark (holder/scope) |
| 500-example LoRA loses to prompted 12B on held-out polarity+holder | Data regime insufficient; abandon small-FT path |
| LoRA wins by ≥ 8 F1 on holder+polarity joint and holds under document shift (news↔phil) | **Then** scale gold and fine-tune |

Until those numbers exist, full gold against a 1.5–3B joint transducer is **premature sunk cost**.

---

### 6. Smallest schema that still works

```jsonc
{
  "entities": [
    {"id": "e1", "surface": ["Anthony Bourdain", "Bourdain", "the chef"]}
  ],
  "assertions": [
    {"id": "a1",
     "subject": "e1",
     "predicate": "P937",          // null allowed
     "predicate_surface": "worked in",
     "object": {"entity": "e2"},   // | literal | SOME | NONE
     "polarity": "+",              // omit row if commitment != factual
     "under_assumption": null,     // closed frame id or null only
     "commitment": "factual"}      // factual | hedged | questioned
  ],
  "acts": [
    {"assertion": "a1",
     "claimant": "e3",             // default: "doc:{doc_id}"
     "evidence_span": [412, 486]}
  ]
}
```

**Cut now:** `mode`, `link_*`, `type`, `valid_time`/`valid_place`, `flags` as model targets, compose/query from the gold program, dual holder+assumption on the same span.

**What breaks if cut further:**
- no `polarity` → store poisoning (non-negotiable)
- no `claimant` / acts → discourse and agreement die; exp72-class work becomes impossible
- no `evidence_span` → fidelity un-auditable; quote-never-reconstruct is theater
- no entity surfaces → alias barrier returns
- no nullable predicate + surface → forced wrong PIDs (exp71 lesson)

**Optional later without invalidation** (if absent = unrestricted / unknown): time/place qualifiers, link proposals as side channel, type tags from GLiNER, mode as a *separate* cheap pass with its own tiny guide — not in v1 gold.

---

### Commitment

1. **Rewrite the schema to `entities / assertions / acts` before any annotation.**  
2. **Delete `mode` and link fields from v1 gold.**  
3. **Claimant ≠ under_assumption; schools default to claimant; frames registry may promote at ingest.**  
4. **Add `commitment` so hedges don’t contaminate polarity.**  
5. **Cap annotation at a 300-ex probe; run the settlement table in §5; only then scale.**  
6. Treat joint field F1 as a gate, not a diagnosis.

If the probe shows prompted hybrid clears polarity+holder bars, **abandon the fine-tune path entirely** and keep this minimal schema only as the store ingest contract. The expensive thing is labels, not LoRA.


[stderr] 

Changes    +0 -0
Requests   1 Premium (2m 10s)
Tokens     ↑ 317.4k (252.9k cached) • ↓ 6.3k (2.8k reasoning)
Resume     copilot --resume=4e4c5ecb-d2df-413d-8bf0-42a7a541790b
