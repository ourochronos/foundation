# Externalized knowledge & continuous learning

## Concept

Declarative knowledge lives in an **external associative store**, not in reasoner weights. The reasoner keeps procedural skill (how to reason, how to query); the store holds facts. Addressing goes through the latent algebra: a query is constructed by rotating an anchor by a relation (`capital-of ∘ France → address near Paris`), making the store **relationally** addressable, not merely similarity-addressable — the "dynamic embedding" idea. Values are latents (hence decodable/inspectable), optionally paired with source text.

This is the path to continuous learning: acquiring knowledge = writing entries (non-destructive, no catastrophic forgetting, instantly effective, locally editable), not fine-tuning.

## Surprisal-gated writes

Write what surprised you: entries are stored when prediction error is high — the same signal that (a) halts recurrence in the reasoner and (b) triggers memory writes. Precedent: Titans ([arXiv:2501.00663](https://arxiv.org/abs/2501.00663)) uses gradient-based surprise to gate test-time memorization. Open policy questions: consolidation/TTL, dedup, contradiction handling (later fact supersedes? provenance-weighted?).

## Prior art map

| Work | Relation to this project |
|------|--------------------------|
| kNN-LM, RETRO | retrieval improves LMs; similarity-only addressing |
| Product-key memories; Memory Layers at Scale ([arXiv:2412.09764](https://arxiv.org/abs/2412.09764)) | trainable sparse KV memory scales factual capacity favorably vs. dense params |
| Titans | surprise-gated test-time memory |
| RotatE lineage | relational addressing algebra |

Differentiator here: one algebra serves *expression* (codec latents), *reasoning* (operations the reasoner applies), and *addressing* (store queries) — three uses, one geometry. Fast-moving area: re-survey at phase start.

## Risks

- **Retrieval precision is the ceiling**: wrong recalls poison reasoning downstream. Phase gate measures precision *before* reasoner integration.
- **Knowing-what-to-query floor**: some knowledge must remain parametric for the model to know a query is needed. Measure the floor, don't assume zero.
- **Store hygiene**: bloat, duplicates, contradictions accumulate without policies.

## Evaluation plan (Phase 2)

1. Closed-world synthetic facts: QA accuracy with/without store; small+store vs. larger dense (T3).
2. Knowledge-editing style tests: inject/override a fact at inference; measure immediate + persistent use.
3. Sequential-domain stream: acquisition and forgetting curves with frozen weights (T5).
