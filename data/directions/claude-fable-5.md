**1. Kill list.**

Kill the learned head. It is a worse, slower reimplementation of 1-NN retrieval (0.892 vs 0.975), the gap provably doesn't close with data, and your own §5 says generalisation and memorisation are separable channels inside it — meaning it is memorising. Retrieval at 0.975 isn't a baseline the head failed to beat; it *is* the mechanism. Ship it.

Kill the anchor basis as a load-bearing component. Your own evidence dismantles it: novel relations are not geometrically special (+0.03), overcompleteness fails in both directions, orthogonality/redundancy/coherence/interpolability all refuted, and every geometric account of basis quality has gone 0-for-3. The reindex-free property never came from anchors — it comes from **freezing the encoder**. A whitened raw label embedding is already a frozen coordinate system for unseen relations. The K-anchor projection is a lossy compression whose only surviving justification ("task-partition alignment") is one refutation away from the 0-for-4 that pattern predicts. Drop it and check nothing degrades; I bet nothing does.

Kill title-keyed identity. Append-only stores live or die on stable identity, and titles are neither unique (disambiguation) nor stable (renames). This is the one decision in §4 that will force a global rebuild later — i.e., it violates your own hard constraint. Fix it now while 20K claims is cheap.

Kill the explanatory research program itself. Ten audit laws and blind adjudication are admirable hygiene, but post-hoc geometric theory has zero hit rate here. Stop asking *why* the basis works; the honest answer is it barely does anything beyond nearest-neighbor.

Keep: the walker (0.912 vs 0.534 is your best result and it's a claim about the *store*, not the geometry), source-time entity naming, the refusal gate, append-only provenance.

**2. The one thing to build.**

An LLM-fronted, retrieval-grounded walker: your local 27B *names* the relations a question needs (as text, order-free), each name is 1-NN'd into the frozen label space (the 0.975 channel), and the walker consumes that multiset against the store's actual edges with residual removal by set-subtraction rather than vector subtraction. No learned head, no anchor basis, no training loop. Weeks of work, one GPU.

**The killing experiment, run first:** on the exact benchmark where the head scores 0.892, does LLM-naming + 1-NN identify the required relation multiset at ≥0.93? If it lands below the head, the whole "retrieval is the mechanism" thesis dies and the head earns its place back. Second kill shot: replace coordinate subtraction in the walker with multiset removal; if end-to-end accuracy drops materially, coordinate composition was real after all and I'm wrong about §1.

**3. Prior art, honestly.**

The residual walker is TransE-style translational composition executed against real edges — the closest existing system is **CQD** (Arakelyan et al., 2021: complex query answering by decomposing into pretrained link-predictor calls, which also beat learned end-to-end models), plus **GQE/Query2Box/BetaE** for coordinate-space query composition, **PRA/DeepPath/MINERVA** for store-grounded walking, **CBR-KBQA** (Das et al.) for retrieval-beats-learned on KBQA, and **GraphRAG/Wikidata** as the crowded incumbents on the substrate side. The claims-with-provenance store is Wikidata's own data model.

Genuine white space, narrowly: **calibrated refusal over an append-only, frozen-encoder claims store on consumer hardware**. Nobody ships "answers only what its edges license, refuses the rest, and never rebuilds." The novel part is the refusal frontier plus the never-reindex operational contract — not the geometry, not the walker, not the layers. That's a real, useful, unbuilt artifact. Say it plainly: the coordinate-composition science is reinvention; the *artifact* is not.

**4. Concrete substrate choices.**

Abandon encyclopedic breadth — Wikipedia-derived facts are where you lose to a 27B's parametric memory every time. Pick a vertical where facts churn and provenance matters: your arXiv corpus (papers→methods→results→supersedes) or biomedical (**Hetionet/PrimeKG**, which have real relation diversity and gold multi-hop queries). Ingest **Wikidata's ontology (P-entities and constraints) only**, not its facts — it's a free, closed relation-category layer someone else maintains.

Schema: `claims(claim_id, subject_id, relation_label_text, object_id_or_literal, source_span, ingested_at, invalidated_by)` plus `vectors(claim_id, encoder_version, vec)` as a *separate versioned table*. Never-reindex is satisfied by storing raw text as ground truth and treating embeddings as disposable, versioned annotations: a new encoder appends a column-family, old vectors are never touched, queries pin an encoder version. HNSW is append-friendly; this constraint is easier than the anchor machinery pretended.

Type system: yes, and hand-authored. Your §6 point 4 already told you the layers aren't derivable — so stop deriving. Write the closed layers by hand: ~5 relation categories, ~30 answer types for the gate, a small type lattice on entities. Fifty lines of ontology, frozen, done once. The §7 cut (closed-enumerable vs open-append-only) is correct, but the closed layers are *authored artifacts*, not derivation targets. Entities and relation labels are the open layers; everything above them is a config file.

**5. The premise you would attack.**

That composition happens in coordinate space. Every geometric hypothesis you tested died; the one component whose job is arithmetic on coordinates (the head) loses to lookup; novel relations aren't geometrically special; the walker's win over planners is evidence about *the store constraining search*, not about subtraction being meaningful. The program's live evidence is consistent with vectors being nothing but fuzzy string-matching on labels — a soft join key — while the store's edge structure does all the reasoning. You've kept coordinates at the center of the architecture out of habit, not evidence. The multiset-removal ablation in §2 is the direct test: if it holds accuracy, the coordinate space demotes to an index and the architecture simplifies enormously. (Runner-up premise: title-keyed identity, per §1 — it's the constraint-violation you shipped yourself.)

`TOP-PICK: Delete the learned head and the anchor basis, and run the two-part ablation — LLM-naming + 1-NN vs the head, and multiset-removal vs vector-subtraction in the walker — to test whether coordinates do anything beyond nearest-neighbor lookup; then ship the refusal-calibrated, append-only, frozen-encoder claims store as the artifact.`


[stderr] 

Changes    +0 -0
Requests   1 Premium (1m 9s)
Tokens     ↑ 35.7k (35.7k written) • ↓ 4.3k (2.0k reasoning)
Resume     copilot --resume=e059c26c-61ae-4279-9b7a-08462bc76481
