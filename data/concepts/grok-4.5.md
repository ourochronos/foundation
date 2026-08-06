I'll answer the brief directly from the measurements and proposal as written — no repo tour, no consensus-seeking.

● Create plan.md +3
  └ ~/.copilot/session-state/ca1509cf-cc29-4e4c-9724-9586fe1cfa0d/plan.md

## Verdict

**Do not build the four-piece architecture yet.** Slot instantiation is a useful *UI for missingness*, not a new primitive. The load-bearing claim — (d) dissolves the KA bottleneck — is almost certainly false in the form stated. Kill that claim first; keep only demand-paged slot fill as a *retrieval policy* over a tiny hand-seeded frame set.

---

### 1. Slot instantiation is the wrong primitive (right diagnostic, wrong ontology)

The extraction arc’s robust finding is representation mismatch, not “we lacked frames.” Gold is STATED at ~0.64 whether recovered or missed; recall sits at ~0.2 inside a 0.041 F1 noise floor. That says: free text and your store’s triple/claim shape don’t align. Frames make incompleteness *visible*; they do not make the right cuts of the world.

**Why LLM-filled slots do not dissolve KA:**

- Frames failed on *which frames exist and how they compose*, not only on filling `seller`. An LLM that invents `sale.seller` also invents `transaction.counterparty`, `divestiture.vendor`, `closing.transferor`. You re-buy the three-vocabulary simultaneous-closure failure: slot names, types, and entity inventory must cohere or composition is zero.
- exp85’s 0.463 precision is one-slot fill against a *fixed* pair inventory — the frame was free. That is relation classification, not frame acquisition. Suggestive of pull-over-push; not evidence frames bootstrap themselves.
- What KA becomes under LLMs: **schema debt with a fluent amnesiac accountant.** Every acquired frame is a soft commitment that later reasoning treats as hard. Drift is silent until closure lies.

**Right primitive instead:** typed *obligations* against a *frozen, tiny* schema (dozens of frames, not open growth). Instantiation is the runtime; the schema is not learned mid-flight. Acquisition goals fill *values*, almost never *new slot structure*. If structure must grow, that is a separate, slow, human-gated edit — not a fault handler.

---

### 2. Fault taxonomy: case 4 eats the taxonomy

In practice the four-way sort collapses to two observable outcomes: *something came back that type-checks* vs *nothing did*. “Resolvable externally” vs “unresolvable” is not separable without an oracle for exhaustiveness of search.

- Local fetch is real (store hit / miss). Keep it.
- External acquisition has no termination proof. Web/search/ask always admit “maybe one more source.” The system cannot know it has looked enough; it only knows budget expired.
- Therefore “genuinely unresolvable” is almost never identified — it is *budget-exhausted unresolved*, mislabeled as refusal or left as `?`.
- The `?` case is the default for anything not in-store. Taxonomy that makes the modal case a residual is useless operationally.

**Replace with a budgeted tri-state:**

1. **Bound-satisfied** (local or external evidence meets a predeclared acceptor for that slot)
2. **Open under budget** (still spending)
3. **Open, budget zero** (proceed incomplete or stop — policy, not ontology)

No “unresolvable.” Refusal is a *policy on (3)*, not a discovery about the world. The interesting work is **slot acceptors** (what counts as filled), not metaphysical resolvability.

---

### 3. Completeness guarantee: mostly a restatement of the frame problem, with one real scrap

Closure over *declared* deps is complete iff the declarations are. Gaps in declarations are invisible — that *is* the frame problem wearing a lattice badge. Detectable incompleteness is **not** a solution to open-world reasoning; it is a dashboard over a closed theory.

**What it is still worth (narrowly):**

- Relative completeness is a real engineering control: “I can answer with slots {A,B} missing” beats opaque RAG confidence.
- It is worth building **only** if declarations are small, versioned, and adversarial-tested for missing deps. Otherwise you get confident completeness theater.

Falsifiable claim: on tasks where humans can list required slots a priori, filled/total predicts human “ready to decide” better than retrieval score. If it doesn’t beat a dumb checklist, the guarantee is worthless.

---

### 4. Prior art — and the actual white space

**Reinvents, with serial numbers filed off:**

| Piece | Prior |
|---|---|
| Slots/frames | Minsky frames, Schank scripts, FrameNet, PropBank |
| Typed missingness → goals | Open-precondition planning, HTN / partial-order planning |
| Fault → fetch | TMS / JTMS justification gaps; KRR “abduction to explain” |
| Closure over deps | Description logics (TBox classification), datalog magic sets, knowledge-graph materialization |
| Demand paging of concepts | Virtual knowledge graphs; classic OS demand paging as metaphor already used in “memory networks” / toolformer-style tool use |
| Pull ingestion | Active learning; goal-oriented dialogue state tracking (DST); slot-filling SDS |
| LLM fills slots | Contemporary IE-as-structured-gen; DSPy-style signatures; tool-use agents |

**White space (thin, but real):** not frames, not closure, not LLM slot-fill alone — the **coupling of (i) a frozen micro-TBox, (ii) budgeted acceptors per slot, (iii) ingestion gated strictly by open obligations, measured against the known ~0.2 recall wall.** Nobody has cleanly shown that *pull IE under obligation* beats push IE on the same gold when the schema cannot grow. That experiment is the white space. Architecture cosplay around four closures is not.

If you cannot state a metric where obligation-gated pull beats exp-style push by >2× noise floor (≈0.08 F1) on held-out STATED relations, there is **no** white space — only nostalgia with GPUs.

---

### 5. Kill experiment (one person, one GPU, days)

**Name: Obligation-Pull vs Push on a 15-frame micro-schema**

**Setup (2–4 days):**

1. Hand-author **≤15 frames**, ≤6 slots each, from one corpus slice where gold STATED relations already exist (reuse one news multi-source set — the only non-zero corroboration cell). **No LLM-authored frames.**
2. For N documents, run two pipelines with the **same** LLM and decode settings:
   - **Push:** blanket extract into claims; map into frames post hoc (your prior failure mode, calibrated).
   - **Pull:** start from document-type → seed frame instances with empty slots; only ask the model (or retrieve spans) for **open slots**; no unsolicited triples.
3. Score: slot-F1 and relation-F1 against gold; also **schema invention rate** (model proposes out-of-ontology slots — count and kill).
4. Repeat 12 runs for noise (you already know 0.041 F1 / 2/12 hard fail).

**Kill criteria (pre-registered):**

- Pull does not beat Push by **≥0.10 F1** on slot fill for gold-STATED slots, **or**
- ≥15% of “filled” pull slots fail a dumb span-grounding check (quote must be in doc), **or**
- When you allow one ablation — **LLM may mint one new slot type per doc** — precision collapses by ≥0.15 (shows KA bottleneck moved, not dissolved).

If pull wins only when frames were hand-fit to the gold, you have tautology, not a system. If pull ties push inside noise, abandon the pivot as architecture; keep pull as a prompting trick at most.

**Informative failure modes:** pull wins precision / loses recall → useful policy, not a reasoner. Pull ties and mints slots → (d) is false. Local-fetch helps, external-acquisition branch adds nothing after k=1 search → drop external half of taxonomy.

---

### 6. Abandon from the eighteen-experiment arc

**Abandon hard:**

- Blanket / hybrid / windowed / calibrated **push extraction** as a path to a general claim store (473-pred / 87-correct pattern; 29k wall). Do not extend REBEL hybrids.
- **Simultaneous open vocabularies** (predicate × frame × entity) and any workstream whose success requires closing all three without a freeze.
- **Corroboration-across-papers** as a store-filling strategy (measured **0**). Stop building multi-doc agreement features for scientific discourse.
- Unified “query depends on” mega-closure joining predicate lattice + premise chains + identity until a micro-schema pull experiment passes. Partial machinery stays on ice, not in the critical path.
- Any dashboard or ranking among extractors whose Δ sits inside **0.041 F1** — treat as noise, delete league tables from decision docs.
- Passive claim-store-as-index product assumption: fill-then-query.

**Keep only as fixtures, not as product:**

- Gold with STATED labels (the 0.636 finding is the gem — use it as eval, not as training fuel for more extractors).
- Multi-source **news** triple set (41) as the only corroboration-positive cell for the kill experiment.
- Noise-floor protocol (byte-identical 12-run).
- exp85-style **enumerated fill-or-NONE** as a baseline arm inside the kill test — not as a system.

**Carry-forward habit to kill:** “we already have three closure structures, so unify them.” That is sunk-cost architecture. Unify nothing until pull-vs-push is decided.

---

## Bottom line

- **Primitive:** obligations over a frozen micro-schema, not open slot-instantiation-as-ontology.
- **Faults:** drop unresolvable; use budget + acceptors.
- **Completeness:** real as a relative dashboard; fake as epistemology.
- **Novelty:** only obligation-gated pull IE under frozen schema — everything else is 1975+KRR+tools.
- **Next:** the 15-frame pull-vs-push kill test; if it dies, discard the pivot, not another extractor variant.

I would bet the kill test fails the “LLM dissolves KA” clause and weakly passes pull-as-policy. Build for that outcome.


[stderr] 

Changes    +3 -0
Requests   1 Premium (1m 3s)
Tokens     ↑ 51.5k (25.6k cached) • ↓ 2.4k (69 reasoning)
Resume     copilot --resume=ca1509cf-cc29-4e4c-9724-9586fe1cfa0d
