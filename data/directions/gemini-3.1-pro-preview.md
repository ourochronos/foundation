### 1. Kill list

Abandon the **learned head** and the **per-step residual walker**. 

The learned head maxes out at 0.892 while simple 1-NN achieves 0.975. The data tells you there is nothing left to learn there. More importantly, abandon the residual walker's coordinate-subtraction arithmetic. You are assuming frozen LLM embedding spaces possess strict algebraic compositionality (target - relation = next step). They do not, which is why your novel transfer peaked at an abysmal 0.453 and all your post-hoc explanations in §6 failed. Vector spaces are for fuzzy matching, not strict logic. 

### 2. The one thing to build

**A Type-Gated Subgraph Navigator.** 
Stop predicting vector coordinates to navigate. Instead, map incoming queries via 1-NN to a *closed, finite set of relation categories* (the structural/causal/temporal layer), and use those inferred categories to symbolically filter standard graph traversals in PostgreSQL. 

**The kill experiment:** Inject 1,000 adversarial claims where entities share identical relation labels but belong to conflicting structural categories (e.g., biological vs. social hierarchies). If the navigator cannot traverse the correct path solely by symbolic type-gating—without resorting to vector arithmetic—kill the project.

### 3. Prior art, honestly

You are reinventing continuous Knowledge Graph Question Answering (KGQA) and differentiable graph walkers (see MINERVA, MultiHopKG, and TransE/ComplEx). The idea of walking a graph by subtracting relation embeddings from a target vector is straight out of the 2010s knowledge graph embedding playbook.

The genuine **white space** is your hard constraint: a zero-reindex, append-only reasoning system on frozen embeddings. Standard KGQA requires complete retraining when the ontology expands. Solving multi-hop reasoning over a dynamic ontology without retraining a global representation is the only novel frontier here.

### 4. Concrete substrate choices

**Datasets:** Drop Wikipedia and arXiv. They are too messy to validate a reasoning engine. Ingest **biological pathways (Reactome)** or **functional package dependencies (Hackage)**. These are strictly typed, highly causal, and will immediately expose flaws in structural reasoning.
**Schema:** `(subject_id, subject_type_id, relation_1nn_id, object_id, object_type_id, provenance)` 
**Type System & Layers:** Your intuition in §7 is structurally sound but operationally backward. **Entities and relations are OPEN** (unbounded, mapped via 1-NN). **Categories, worldviews, and axioms are CLOSED** (finite, enumerable, never refitted). The type system should be a rigid relational schema at the axiom/category layer, which open text embeddings are forcefully mapped into.
**Models:** Keep BGE-M3 purely for 1-NN mapping. Use your local 27B model for zero-shot extraction. Train nothing.

### 5. The premise you would attack

**I attack the premise that composition should happen in a coordinate space.**

You are stubbornly trying to do logical arithmetic inside a frozen embedding space. You observed that "1-NN retrieval on relation labels" crushes learned mapping, yet you are still trying to force vectors to do the heavy lifting of multi-hop composition. You should completely decouple *mapping* from *reasoning*. Use embeddings strictly as a translation layer to map open-world text into your closed ontology. Once mapped, execute composition as a purely symbolic, relational graph traversal in the database. Vector arithmetic will never give you dependable, out-of-distribution logical derivation.

TOP-PICK: Abandon vector arithmetic for graph traversal and build a reasoning engine that maps open text into a strictly finite, closed type-system using 1-NN, executing composition entirely via symbolic SQL traversals.


[stderr] 

Changes    +0 -0
Requests   1 Premium (23s)
Tokens     ↑ 21.6k • ↓ 818 (1.6k reasoning)
Resume     copilot --resume=fb770aa4-9e9b-47dc-9430-39601e29a6ba
