**Verdict: do not build the proposed architecture.** Slot filling may be a useful local representation, but it is the wrong system primitive. The proposal relocates the acquisition bottleneck from extracting facts to inventing correct frames, dependencies, and stopping rules—arguably the harder problem.

1. **Slot instantiation**

LLMs do not dissolve knowledge acquisition. They turn it into **schema acquisition and evidence adjudication**:

- Which frame applies?
- Which slots exist?
- What counts as a valid filler?
- When are two frames equivalent?
- Which dependencies were omitted?
- Which source should win?

A model can fill a supplied `sale.seller` slot more reliably than extract every relation, but the crucial knowledge was already encoded in choosing `sale` and declaring `seller`. Exp85’s precision is consistent with constrained answering reducing output entropy; it is not evidence that frames can be acquired on demand.

Use **evidence-backed proof obligations** as the primitive instead: “To establish conclusion C, establish propositions P₁…Pₙ, each with provenance.” Slots can implement some obligations, but must not define what reasoning is allowed to notice.

2. **Fault taxonomy**

“Externally resolvable” and “unresolvable” are not epistemic categories an agent can reliably classify. Resolvability depends on budget, access, time, source quality, and future discoveries. The fourth case therefore swallows the distinction.

Replace the taxonomy with operational states:

- locally supported;
- unsupported, with an executable acquisition action;
- searched under a recorded budget and still unsupported;
- structurally undecidable from the current model.

Refusal should follow policy and exhausted budget, not a prediction of metaphysical unresolvability. A fault without a concrete next action—query, corpus, person, or measurement—is merely uncertainty relabeled.

3. **Completeness**

Filled/declared slots is useful workflow telemetry, not a completeness guarantee. It measures **conformance to a schema**, while hiding errors in frame selection and dependency declaration. A confidently complete wrong frame is more dangerous than an obviously incomplete answer.

This is still a modest advance if reported honestly as “declared-obligation coverage.” It becomes a regression if surfaced as reasoning completeness. Require two separate measures: obligation coverage and evidence support. Neither implies that the obligation set is sufficient.

4. **Prior art and white space**

This reinvents semantic frames and scripts, FrameNet-style roles, description-logic restrictions, backward chaining, truth-maintenance systems, planning with open preconditions, blackboard systems, active information acquisition, and especially **Soar’s impasse-generated subgoals**. Demand-driven retrieval also resembles database magic sets and query-driven data integration.

There is little conceptual white space. The potentially publishable contribution is empirical: whether modern models can generate and execute acquisition actions from typed failures **without oracle-authored schemas**, while remaining calibrated and cost-effective. That is a control-policy benchmark, not a new knowledge architecture.

5. **Kill experiment**

Build a 100-case benchmark from the existing texts. Each case requires answering a question whose decisive evidence is present but whose necessary frame or dependency is withheld.

Run four conditions:

1. direct retrieval and answering;
2. model-generated question decomposition;
3. oracle frame plus model-filled slots;
4. model-induced frame, dependencies, and slot acquisition.

Blindly score final correctness, cited evidence entailment, required-dependency recall, false “complete” declarations, and acquisition cost. Repeat each case enough to expose the measured 0.041 noise floor.

**Kill criterion:** if oracle frames materially outperform induced frames, or induced frames falsely declare completeness on more than 10% of wrong answers, reject the architecture. That result would locate the bottleneck in schema induction rather than slot filling. Do not rescue it by hand-authoring better frames; that would concede the central claim.

6. **What to abandon**

Discard the triple-store ingestion pipeline, extraction-model comparisons, corroboration machinery, and the assumption that the predicate lattice should become the new system’s ontology. Do not unify the predicate lattice, premise chains, and identity closure merely because they exist.

Drop the four discourse corpora as acquisition benchmarks: their zero corroboration shows they test the wrong environmental assumption. Retain multi-source news only as an adversarial comparison, not as the target domain.

Preserve only the gold evidence spans, failure cases, fabricated controls, run-to-run variance protocol, and cost measurements. Recast them into the kill benchmark. Everything else is sunk cost.


[stderr] 

Changes    +0 -0
Requests   0 Premium (34s)
Tokens     ↑ 21.7k (21.7k written) • ↓ 1.3k (406 reasoning)
Resume     copilot --resume=5bb1b909-3923-4c85-b202-a4eacdc79c3b
