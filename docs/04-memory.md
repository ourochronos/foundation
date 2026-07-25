# Externalized knowledge & continuous learning

## Concept

Declarative knowledge lives in an **external associative store**, not in reasoner weights. The reasoner keeps procedural skill (how to reason, how to query); the store holds facts. Addressing goes through the latent algebra: a query is constructed by **translating** a query latent by a relation operator (`z_question + t_capital_of → address of the answer fact`) — rotations were the original design and were empirically rejected (D4/D15); translations are confirmed at store scale (D25: P@1 0.905 → 0.988 on held-out queries). The store is **relationally** addressable, not merely similarity-addressable — the "dynamic embedding" idea. Entries are triple latents `[gist ; identities ; s]` plus source text (decodable/inspectable via the codec).

## Design facts established by D25 (`codec/memory_store.py`)

- **Channel ownership at retrieval** mirrors D3: the gist discriminates *relations*, the identity channel discriminates *entities*. Identity rescoring measured ~0 at 360 entries (the gist suffices); it is retained because reasoner-generated query latents will be noisy (D24) and stores will be larger.
- **Keys ≠ values at supersession**: updates arrive event-phrased while queries arrive at the state-phrased address the superseded entry occupied. `supersede()` transfers the old entry's address to the new entry; shadowed entries persist for provenance. Post-edit retrieval = pre-edit exactly (0.900).
- Relation operators are closed-form mean displacements, fit from ~20 (question, fact) pairs each — cheap enough to fit per-relation on the fly. They scale: 0.991 P@1 at 9,900 entries, 1.000 with identity rescoring (D26).
- **Multi-hop addressing requires symbolic hand-off between hops** (D26): hop displacements are content-conditional (the answer's address depends on the intermediate ENTITY), so composed/chained fixed translations fail (0.003/0.062). Same law as D16, at a new altitude.
- **The hand-off needs only the identity CHANNEL, not the codec** (D27): `hop = retrieve(gist: z+t_rel; promote: handed-off ids; demote: source ids; exclude: visited)` scores **0.998** — equal to the decode/re-encode loop, at store-arithmetic cost. Walk semantics (`demote_ids`, `exclude` in `MemoryStore.query`) are required invariants: without them the hop self-retrieves. Ridge-linear hops reach 0.552 (entity routing is partially linear, in low-variance directions) — the identity channel is what closes it.

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
