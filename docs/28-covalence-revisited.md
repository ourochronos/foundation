# Covalence, re-read against what has since been measured

Surveyed at D69 when this project had no measurements. Eight experiments later
several of its lessons are things we independently re-derived the hard way, and
a few are gaps we still have. Re-read now because the alias barrier (exp75) and
the extraction-precision problem (exp76) are both things Covalence names
directly.

Source: `docs/reference/covalence-survey.md`; Ourochronos/Covalence, Rust
GraphRAG over pgvector+AGE, stalled clean May 2026.

---

## 1. Lessons it learned first, which we then re-measured

**"Blanket LLM extraction is a dead end — 29k flat claims = noise + 90% of API
cost."** exp76 measured exactly this without meaning to: Gemma emitted **473
predictions for 87 correct answers** against REBEL's 394 for the same 87. The
generative model produces more output for the same yield, and Covalence had
already paid for that finding. Its remedy is one we do not have:

- **novelty gating** — admit a statement only if its embedding is far enough
  from what is stored, rather than extracting everything and filtering after.
  Post-hoc filters "are never complete", which is precisely why exp71 needed an
  explicit skip option and still kept half of what it saw.

**"Make the stored unit a SELF-CONTAINED, coref-resolved statement."** This is
the alias barrier of exp75 named at the right layer. We attacked surface
variation *after* extraction with a conservative alias merge (41 → 43
corroborated triples); Covalence resolves it *before* storage, so the unit that
enters the store already says "Anthony Bourdain" rather than "Bourdain", "the
chef", or "he". `biu-nlp/f-coref` (94k downloads) and `lingmess-coref` are
available and cheap.

**"Belief change = INVALIDATION, never deletion."** Convergent — we reached the
same place independently (append-only, supersession as an event). No change
needed.

## 2. Ideas we do not have, ranked by what they would fix

**(a) Typed claim-relations, not just conflict kinds.** Covalence types the
edge between two claims: `CONFIRMS / CONTENDS / CONTRADICTS / SUPERSEDES /
CORRECTS`. Our conflict kinds — polarity, functional, existential, subsumption,
opposition — describe *why* a clash occurs; theirs describe *what relation
holds*, and the two are orthogonal rather than competing. Two gaps follow
immediately: we have no `CONTENDS` (partial disagreement, weaker than
contradiction) and no `CORRECTS` (a claim that supersedes by fixing rather than
replacing). Note also that **`CONFIRMS` is corroboration as an edge** rather
than as a count — which would have survived the four zeros, because an edge can
be asserted by a reader even where repetition does not occur.

**(b) "Unknown ≠ 50%".** Subjective-logic opinion tuples carry
belief/disbelief/**uncertainty**/base_rate. Our model can say a claim is
asserted, denied, or absent, and `SOME`/`NONE` cover existential ignorance
about *objects* — but there is no way to state ignorance about a *proposition*
as distinct from disbelief in it. For a store whose entire purpose is refusing
to overclaim, that is a real hole.

**(c) Algorithm isolation — the sharpest one, and a live privacy bug.**
Covalence computes public scores **only over public subgraphs**, on the ground
that *confidence is a side channel*. Our §8 disclosure design reasons about
which claims are released and about set-level identifiability, and says nothing
about **derived values leaking their inputs**: a confidence, count or ranking
computed over private+public data and then published discloses the private
part. Given the stated goal is a sovereign personal store feeding ZK
aggregation, this belongs with the disclosure rules and is currently absent.
Their **dual synthesis** — public views generated independently rather than
redacted from private ones — is the structural fix, and redaction-after-the-fact
is the failure mode it avoids.

**(d) Clearance on every row with most-restrictive inheritance.** A derived
claim inherits the strictest clearance of its premises. We have `premise`
evidence chains already, so the inheritance rule is nearly free and would make
§8's disclosure function computable over derived claims rather than only over
stored ones.

## 3. The warning worth heeding most

**"Stacking five epistemic frameworks caused belief OSCILLATION."** Covalence
found that epistemic sophistication has a *complexity budget* and that
exceeding it made beliefs unstable rather than nuanced. This project has added
mechanisms steadily — opposition, nested frames, existentials, events, salted
commitments — and every one was individually justified by a measurement. That is
exactly how a budget gets exceeded without any single step looking wrong.

Concretely: of the items above, (a) and (c) address measured problems and (b)
and (d) are cheap and structural, but adopting all four plus coref plus novelty
gating in one pass is the shape of the mistake they are reporting.

**And the process lesson lands too**: *"velocity without an operator is a stall
mode — 26 agent-driven waves in a month, then silence."* This session has run
twelve experiments in a day.

## 4. What I would take, in order

1. **Coref before storage** (`f-coref`) — fixes a measured barrier, no new
   epistemics, and directly testable by re-running exp75.
2. **Novelty gating at extraction** — addresses the 473-for-87 precision
   problem that both projects have now measured independently.
3. **Algorithm isolation + clearance inheritance** — a real privacy hole in a
   design whose stated endpoint is private aggregation; cheap because the
   premise chains exist.
4. **Typed claim-relations** — richer than our conflict kinds and orthogonal to
   them, but it is an epistemics change and should wait for 1–3 to land.
5. **Subjective-logic tuples** — deferred deliberately. Highest complexity cost,
   least measured need, and the exact framework whose stacking Covalence blames
   for oscillation.
