I'll inspect the repo context around this schema so the critique is grounded in what's actually being built, then answer the five points directly.

/ Search (glob)
  │ "**/*schema*"
  └ 6 files found

/ Search (glob)
  │ "**/data/**/*"
  └ 21 files found

/ Search (grep)
  │ "claim_relations|under_assumption|act_ref|prop_ref|polarity|marker" in
  │ *.{md,json,jsonc,py,ts,sql}
  └ 235 files found

Pulling the store model and prior schema notes to check whether this extraction layer actually lines up.

● Read 33-schema-v2.md
  │ docs/33-schema-v2.md
  └ 171 lines read

● Read 25-model-v2.md
  │ docs/25-model-v2.md
  └ L1:200 (199 lines read)

● Read 29-extraction-decomposition.md
  │ docs/29-extraction-decomposition.md
  └ L1:150 (150 lines read)

● Read frames.json
  │ data/frames.json
  └ L1:80 (74 lines read)

Checking store identity/conflict rules and whether the schema can actually express nested attribution and claim-objects.

● Read 25-model-v2.md
  │ docs/25-model-v2.md
  └ L200:350 (150 lines read)

● Read conflict.py
  │ foundation/model/conflict.py
  └ L1:120 (120 lines read)

● Read grok-4.5.md
  │ data/schema_v1/grok-4.5.md
  └ L1:100 (100 lines read)

/ Search (grep)
  │ "attribution|claim_ref|object.*prop|nested|act_ref|holder" in **/*.{md,py} (docs, foundation)
  └ 19 files found

1. **Fatal flaw**

§2 says nested attribution and claims-as-objects are fixed. They are not.

Text: *“The Times reported that Smith denied that climate change causes famine.”*

Needed:
- `P` = causes(climate_change, famine)
- `A1` = Smith **denies** `P`
- `A2` = Times **reports** `A1`

Schema can only emit something like:
```json
{"subject":"climate_change","predicate":"causes","object":"famine",
 "polarity":{"value":"?"},
 "attribution":[{"holder":"Times","kind":"reported"},
               {"holder":"Smith","kind":"reported"}]}
```
Object has no `claim`/`act`/`prop` variant. Attribution is a flat list with only `author|reported`. `denies` is neither kind nor a `claim_relations` type (`disputes|supports|cites`).

If `polarity:"-"`: Times is stored as reporting ¬P — false.  
If `polarity:"+"`: Smith’s denial vanishes.  
If two claims + `disputes`: you still can’t say Times reports Smith’s denial rather than disputes P itself.

The expensive round-1 finding was relocated into `attribution[]` + `claim_relations`, which cannot express the only corroboration genre (reportage). Same shape as the v1 failure the doc claims to have fixed.

Worse: the doc justifies this with store `act_ref`/`prop_ref`, which model v2 **retracted** as unimplemented and actively wrong for agreement. Extraction is being aligned to a store fiction.

---

2. **CLOSED layer forced change (<1 year)**

**Epistemic modality / hedging as a truth-conditional scope** (and secondarily conditionals).

Under your own rule *absent qualifier = unrestricted*, every unscoped claim is a full assert. News/science are mostly:
- “X may cause Y”
- “evidence is consistent with Y”
- “if rates rise, Y”

Annotate without `modality` / `condition` now → all enter as bare asserts → false corroboration and false conflicts. Adding them later retroactively falsifies the gold. **Fix now** (even a tiny closed set: `asserts|hedges|possible|denied_as_speech`), or admit the gold is assert-only and useless for reportage.

Also: `under_assumption` closed over `frames.json` (political lattice) will not survive philosophy/law/science. That inventory will fork or empty out within a year; treat frames as **per-domain, versioned, optional**, not one global CLOSED enum baked into Layer 0.

---

3. **Over-built — delete**

| Delete | Why |
|---|---|
| `claim_relations` in this gold | Discourse linking is a separate pass; news corroboration needs repetition, not `however→disputes`. Expensive, low agreement, wrong corpus. |
| `predicate.id` (P937) in annotation | Contradicts §4 “source-grounded only.” Surface+cue is gold; PID is normalisation. |
| `under_assumption` on the general schema | Almost never in news; political frames don’t transfer; school→scope is already “code not annotation.” |
| Per-field cue bureaucracy on every slot | One evidence quote + optional negation cue pays for itself; cue-on-predicate/cue-on-attribution/cue-on-relation is annotator thrash. |
| Bundled document-global `entities[]` coref as blocking gold | Gemini was right: one bad cluster nukes every claim score. Mentions on claims + later coref pass. |

Minimal gold that matches the actual goal:
```json
{"mentions":[{"id":"m1","text":"Smith","quote":"..."}],
 "claim":{
   "subj":"m1","pred_surface":"denied","obj":{"claim_span":"..."},
   "neg_cue":null,
   "holder_mention":"m2","holder_cue":"reported that",
   "evidence":"..."
 }}
```
No PIDs, no frames, no claim_relations, claim-object via span/ref.

---

4. **§7 answers**

1. **Cue/span anchoring protects investment?** **Wrong** as stated. It moves ambiguity into cue choice *and* the schema still freezes derived fields (`polarity.value`, `predicate.id`, `kind`, `f:keynesian`). Spans protect only what you don’t also normalise in-line. Half source-grounded is not source-grounded.

2. **Polarity/marker unambiguous?** **No.** Fails on:
   - *“Bourdain never had children.”* (`never` = neg cue → `−`+SOME, or temporal+NONE?)
   - *“It is not the case that Bourdain had children.”* (sentential neg ≡ NONE, procedure forces `−`)
   - *“Bourdain is childless.”* (no neg cue, no “no/none” token)
   - *“Bourdain had no three children.”* / *“does not have three children.”* (already in doc — boundary is still annotator-discretion)
   - *“Few of Bourdain’s shows failed.”* (neg+quantifier interaction)  
   Equivalent paraphrases get opposite gold → same training contamination §3 claimed to kill.

3. **`claim_relations` set / flat list?** **Wrong** minimal set for reportage (`denies`/`qualifies`/`retracts` are attitudes, not discourse). Flat list is not enough: edges need their own holder/scope (*author* disputes vs *cited party* disputes). For this project’s measured goal, **cut the whole thing** from annotation; don’t enlarge it.

4. **Missing, forces re-read:** Nested speech / claim-as-object (claimed fixed, isn’t); **modality/hedge**; **conditionals**; document-source vs holder vs mentioned-speaker; questions/imperatives (are they claims?). Any one of the first three invalidates “absent = unrestricted” gold.

5. **Still too expensive:** Joint entity-cluster + triple + polarity + multi-attribution + frame scope + claim_relations + universal cues in one pass. Also closed-frame tagging without a stable multi-domain inventory.

6. **Halve the budget:** Cut `claim_relations`, `under_assumption`, `predicate.id`, multi-holder lists, entity typing beyond coarse tags. Keep: mention spans, surface predicate, args, single holder+cue if present, neg cue, evidence quote. One attitude embedding slot (`object: claim_ref | entity | literal | NONE`).

(There are **six** questions in §7, not seven.)

---

5. **What breaks first at scale**

**10⁶ assertions, one Postgres**
- Scope-overlap joins: pairwise `valid_time` × lattice-entailment on `under_assumption` with absent=unrestricted → conflict checks degrade toward O(n²) on hot proposition keys; lattice calls make it worse.
- Quote-heavy rows (evidence + every cue) blow up heap/TOAST long before CPU; corroboration `COUNT(DISTINCT claimant)` over normalised keys thrash without a materialised proposition-key table.
- First operational break: **conflict/agreement queries on high-degree entities** (countries, orgs, “inflation”), not insert throughput.

**Merge two 10⁶ stores**
- Document-local `e1`/`c1` mean nothing across stores; without prior entity registry merge you get either zero joins or `local:`-style false fusion (already a Layer-0 wound).
- Divergent frame inventories / predicate definition versions → silent non-overlap (exp69/73 shape) while raw row union “succeeds.”
- Absent scopes on both sides → **mass false conflicts** on merge (every bare claim overlaps every scoped claim).
- `claim_relations` are intra-document pointers; cross-store they are garbage or require a second identity layer you don’t have.

Merge breaks **first** on entity identity + absent-scope conflict flood; single-node breaks first on scoped conflict/agreement over celebrity entities.

---

**Concrete alternative (assertion vs act, actually nested):**
```json
{"acts":[
  {"id":"a1","holder":"m_Smith","attitude":"denies","cue":"denied",
   "prop":{"id":"p1","s":"m_cc","p_surf":"causes","o":"m_famine",
           "neg_cue":null,"mod":"asserts"}},
  {"id":"a2","holder":"m_Times","attitude":"reports","cue":"reported that",
   "prop":{"act_ref":"a1"}}
]}
```
Gold = acts + surface props + attitudes + spans. PIDs, frames, links, disputes: later additive passes.


[stderr] 

Changes    +0 -0
Requests   1 Premium (1m 50s)
Tokens     ↑ 139.2k (95.7k cached) • ↓ 5.6k (3.2k reasoning)
Resume     copilot --resume=0d64bd65-7965-416d-9658-608632a893f6
