**Verdict: the author is wrong.** Automatic minting can remain unrestricted, but automatic consolidation cannot safely become authoritative. Human gating is unavoidable at the point where a proposed slot or alias may affect reasoning.

1. **The three-force model is insufficient.** **Merge fails first.** “Substitutable in existing queries” establishes observational equivalence under today’s workload, not semantic identity. Two relations can share frame position, filler types, and current answers while differing in direction, modality, time, jurisdiction, causality, or provenance. Worse, invented frame positions make the test circular.

   Pruning by query-relative usefulness is also wrong: it deletes rare, future-useful distinctions and optimizes the schema toward its current query distribution. The missing force is **contrastive falsification**: actively seek contexts and counterexample queries that distinguish an alias pair. Promotion must require surviving those tests, followed by human adjudication for high-impact aliases.

2. **NELL drifted through positive feedback.** Promoted beliefs trained later extractors; correlated patterns masqueraded as corroboration; broadened predicates admitted noisier instances; those instances then supported still broader patterns. Confidence rose inside a mutually reinforcing evidence loop.

   A frozen set would detect only drift represented in its predicates, domains, and query shapes—and only after enough bad promotions changed answers. Off-support drift could remain invisible indefinitely. Once used to steer acceptance, that set is no longer genuinely held out. Earlier detection requires promotion-frontier audits: provenance-separated evidence, adversarial minimal pairs, and a shadow reasoner comparing each proposed alias against the unmerged schema before activation.

3. **Aliasing is not meaningfully reversible by deleting a row.** The alias graph becomes the drifting object. A false edge changes equivalence classes, query results, usefulness scores, subsequent alias evidence, and pruning decisions. Deleting it cannot undo downstream decisions derived from it.

   Reversibility requires immutable raw claims, schema versioning, complete dependency provenance, and deterministic recomputation from the pre-alias state. Class-size breakers only limit catastrophic component growth; they do not stop long chains of individually plausible false edges.

4. **No slot-count growth curve distinguishes crystallization from aggressive corruption.** Sublinear canonical growth plus rising alias rate is exactly what an over-merging system produces. The useful curve is cohort survival: for aliases accepted during week \(t\), measure later split/rollback rate and performance on newly arriving domains and contrastive queries after 30 and 90 days. Crystallization requires falling mint rate **and** stable out-of-sample alias precision; alias rate alone is anti-evidence.

   The 0.041 noise floor cannot be converted directly into a document threshold because documents are not independent alias decisions. Detecting a rise from 0.041 to roughly 0.082 needs about **500 independent evaluations per cohort**; with sparse relation opportunities and 0.155–0.266 recall, plan on at least **several thousand documents per domain**, 30 days for an early signal, and 90 days for survival evidence.

5. **Sequence strictly after proving the runtime.** Run emergence as a recorded shadow experiment from day one, but do not let it alter production reasoning, pruning, or acquisition priorities. Otherwise failures in learned structure contaminate the runtime measurement and make causal attribution impossible. “Separate metrics” do not isolate coupled systems.

6. **The cheapest early-drift experiment:** replay a fixed document stream through two reasoners—seeded schema versus automatically aliased schema. For every proposed alias, generate or hand-author one distinguishing minimal-pair query, then score it immediately and again on the next temporal batch. Also inject known-near-synonym traps such as `employer`/`client`, `seller`/`owner`, and `birthPlace`/`nationality`. Stop when false-alias incidence or answer regression exceeds a preregistered bound.

Human review need not gate every claim. It gates structural activation. At 2–5 minutes per candidate, the observed 510 concepts cost roughly **17–43 reviewer-hours** for an initial pass. That is the actual rate limit; removing it does not eliminate the cost—it converts it into latent schema corruption.


[stderr] 

Changes    +0 -0
Requests   0 Premium (48s)
Tokens     ↑ 21.7k (21.7k written) • ↓ 1.9k (1.0k reasoning)
Resume     copilot --resume=c3ea88f4-846e-43f7-bc42-5cdc405cc6e5
