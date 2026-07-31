I'll answer from the brief alone—committed positions, no hedging toward consensus.

● List directory .
  └ 32 files found

# Strategic review

## 1. Kill list

**Abandon the coordinate-composition program wholesale** — anchor basis, residual subtraction in relation-coordinate space, and the learned head that predicts target sums. §5–§6 already killed the theory that made it interesting: overcomplete bases collapse or zero out, orthogonality/coherence/redundancy/interpolability are all refuted, novel-relation transfer stalls at 0.453, and post-hoc geometry stories are 0-for-3. The walker “win” (0.912 vs 0.534) is evidence that **the store’s edges supply order and depth**, not that vectors compose. Treating residual coordinate walking as the reasoner is cargo-culting a planner objective the store already made unnecessary.

**Kill the learned head specifically.** 1-NN on relation labels is 0.975; the head tops at 0.892 and the gap does not close with data. That is not “needs more capacity”; it is the wrong inductive bias for a problem nearest-neighbor already solved.

**Kill anchor bases as the reindex-free mechanism.** A frozen K-direction projection was supposed to give free coordinates to unseen relations. Held-out relations are only +0.03 harder to reconstruct, yet transfer is still mediocre and every account of *why* a basis works died. You do not need a better basis; you need to stop routing novelty through a continuous basis.

**Keep, stripped of geometry mythology:** append-only claims with invalidate-never-delete; identity fixed at extraction (0.912→0.373 subjects/claim is real); greedy frontier expansion driven by available edges; the audit apparatus as process, not as a product layer. The answer-type gate is a useful refusal heuristic — keep it as a centroid/type check on **discrete relation ids**, not as proof the coordinate program works.

If only one sentence: **latent relation composition is a dead end given §6; stop improving it.**

## 2. The one thing to build

**A schema-closed, instance-open typed claim graph with store-native multi-hop retrieval — no relation geometry.**

- **Closed once:** a versioned catalog of relation *types* (and a small set of structural roles: entity, literal, time, source). New relation *labels* map into the catalog by alias/1-NN/LLM propose→human-or-audit accept; acceptance is an append-only schema migration that does **not** touch existing claim rows or embeddings.
- **Open forever:** entities, spans, page provenance, claim text. New claims = new rows + optional new entity titles. Embeddings are **per-claim or per-entity, append-only**; swapping the encoder means dual-write new columns, never rebuild as a precondition for queries (query path can prefer the newest available vector column).
- **Reasoner:** NL → typed hop program (relation ids + answer type constraints) executed as graph expansion in Postgres, with dense retrieval only to seed frontiers and rank terminal objects. The walker stays as an algorithm over **edges**, not over subtracted anchor coordinates.
- **Local fit:** one GPU for extraction/embedding/LLM planning; pgvector for seeds; SQL recursive CTEs or a small Python expander for hops.

**First kill experiment (one weekend):** Freeze a catalog of ~150–300 relation types covering your current store by clustering/merging the existing labels (no anchors). Hold out 40 surface labels never seen at catalog-build time. Measure (a) alias/1-NN→catalog routing accuracy, (b) depth-1/2 answer accuracy on questions that need those labels, (c) whether any residual-coordinate baseline still wins on the same split. **Kill criterion:** if catalog routing <0.9 on held-out labels *or* typed graph walk does not beat your current residual walker by ≥0.05 on depth-2 *and* match refusal quality, the “closed schema + store walk” thesis is wrong and you should stop — but you should not go back to anchors; you should question multi-hop KG usefulness on this corpus size instead.

## 3. Prior art, honestly

**Crowded, not empty.** You are adjacent to:

- **KG embeddings & query geometry:** TransE/RotatE/ComplEx, Query2Box, BetaE, CQD — learn composition in latent space; they retrain and chase benchmarks you already outgrew philosophically.
- **GraphRAG / LlamaIndex property graphs / Neo4j+vectors / Microsoft GraphRAG:** ingest → chunk/entity graph → retrieve paths; most quietly re-embed or rebuild community summaries when the corpus moves.
- **OpenIE / NELL / ReVerb, Wikidata+SPARQL, RDF stores:** typed triples, open entities, closed-ish properties; reasoning is query languages, not residual walkers.
- **Text-to-Cypher / Text-to-SPARQL, PullNet, GraftNet, PathRanking:** NL → graph ops; the durable half of your walker result lives here.
- **Embedding routers & schema linking** (text-to-SQL literature): mapping novel phrases onto a fixed catalog — this is what your 0.975 1-NN already is.
- **BGE-M3, ColBERT, claim verification pipelines** (FEVER-like): retrieval and evidence tables, not novel geometry.

**White space (narrow):** a **personal, fully local, append-only research substrate** that treats **relation types as a migrated schema** and **never requires global re-embedding or basis refit**, with audit-grade provenance and refusal — optimized for one machine and ~10⁴–10⁶ claims, not for leaderboard multi-hop QA. The novel part is **not** “compose unseen relations in a frozen anchor basis”; that niche is either empty because it does not work or occupied by KG embedding papers that accepted retraining. Genuine novelty, if any: **engineering the closed/open cut so encoder swaps and schema extensions are both append-only**, plus your audit laws as a productized trust layer. Everything else is reinvention.

## 4. Concrete substrate choices

**Datasets (ingest for structure, not bulk):**

1. **Wikidata truthy subset filtered to your active entity neighborhood** — supplies a real closed property catalog and types; use it to *bootstrap the relation schema*, not as dump-and-pray volume.
2. **arXiv abstracts + section-level claims only in 2–3 domains you actually read** — depth beats another 50k random papers; multi-hop usefulness shows up inside a domain.
3. **Your own notes / papers / HF cards you care about** — the product is personal utility; if it does not help *you* find and refuse, the metric suite is theatre.
4. Avoid another general Wikipedia crawl until typed walk quality plateaus; 13k wiki claims already taught the geometry lessons.

**KB schema (never-reindex):**

- `entities(title PK, canonical_title, types[], created_at)` — identity by title/alias table, not opaque ids as sole key; aliases append-only.
- `relation_types(id, name, namespace, domain_types[], range_types[], aliases[], version, superseded_by)` — **closed, enumerable, migrated**.
- `claims(id, subject_title, relation_id, object_title | object_literal, polarity, valid_from, invalid_at, source_doc, span, extract_run)` — append-only; invalidation is a timestamp, never DELETE.
- `embeddings(subject_id, model_id, dim, vec, created_at)` — **composite key includes model_id**; new encoder = new rows.
- `docs` + `doc_chunks` for provenance and lexical retrieval.
- Indexes: `(subject_title, relation_id)`, `(relation_id, object_title)`, pgvector on claim-text and entity-gist under each `model_id`. No global “relation basis” table that must be recomputed.

**Models:**

- **Build on:** BGE-M3 (keep; you already beat a “stronger” encoder on the tasks that matter), llama.cpp 27B-class for extraction and NL→typed plan, Postgres recursive queries.
- **Train:** at most a small classifier or cross-encoder for *catalog linking* and answer-type check — not a residual head over anchors. Prefer no training if 1-NN + rules hold.
- **Avoid:** training another composition head, SAE/dictionary “basis discovery,” encoder swaps as a research lever, large pretraining, anything that needs a cluster.

**Type system:** Yes, warranted — and it should be **boring**. Finite algebraic types for values: `EntityRef | Literal(JSON) | Time | Quantity`. Finite relation catalog with optional domain/range. Structural categories (causal/temporal/…) as **tags on relation_types**, not as separately embedded layers you derive. Worldviews/lenses as **named query filters or source priors**, not representation layers. Axioms as **validated rules** (Horn-ish constraints) over the typed graph, checked on append.

**§7 closed/open cut:** Directionally right, **wrong altitude**. Do **not** try to close “entities → relations → categories → worldviews → axioms” as representation layers. Close **relation types + value sorts + a handful of structural tags**. Leave entities, claim text, sources, and lens parameters open. Categories/worldviews/axioms are organizational views and checks over the graph, not embedding strata. Adjacent-layer derivation already failed; stop trying to *derive* layers — **declare** the small closed sets and **map** everything else.

## 5. The premise you would attack

**Attack: “the shipped artifact must never reindex” as currently operationalized through frozen relation geometry.**

The constraint is emotionally right (a system that demands global rebuilds when the world moves is not a system you will run) and **technically misplaced**. You bound yourself to invent reindex-freedom *inside* a continuous relation basis — the one place §6 shows composition and novelty do not behave. That forced anchors, residual heads, and a research surface where every elegant geometric fix died.

Reindex-freedom should mean: **(1)** claims and invalidations are append-only, **(2)** embeddings are versioned columns/rows so encoder change is dual-write not downtime, **(3)** relation novelty is schema migration + alias map, not a new direction in a shared basis that must preserve old coordinates’ compositional meaning. Under that reading, occasional **local** recompute (one entity’s neighbors, one model_id’s vectors) is fine; **global geometric refit** is what you forbid.

Secondary premise I would also drop: that a separable “reasoner” must live in coordinate space above the store. §5 says the store already won the planning problem. The reasoner should be a **query planner over typed edges** (LLM-assisted at the boundary), not a second geometry. Retrieval at 0.975 vs head at 0.892 does not mean “no learning ever”; it means **do not learn the thing nearest neighbor already is**. Learn only where the store cannot vote — extraction quality, catalog proposal, refusal calibrated to answer types.

---

TOP-PICK: Scrap relation-coordinate composition entirely and spend the next weeks on a closed relation catalog + append-only typed claims + store-native multi-hop, with the held-out label→catalog routing kill test as the gate.


[stderr] 

Changes    +0 -0
Requests   1 Premium (1m 25s)
Tokens     ↑ 50.9k (26.6k cached) • ↓ 3.6k (1.1k reasoning)
Resume     copilot --resume=99484a80-b0ba-4ef7-9b4a-ffdcdd3b442b
