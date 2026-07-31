# References — prior art, and what each one closes off

Assembled from the four-model directions panel (`data/directions/`) plus
additions of my own for the federation and epistemics threads, which the panel
was not asked about.

**Verification status.** System and paper *names* and what they do are from
panel output and my own recall; author/year attributions are my recall and
have **not** been checked against the sources. Spot-check any of these before
citing them in writing. Marked `[panel]` if a rater named it, `[mine]` if
added here, `[both]` if independently named by a rater and by me.

---

## 1. The thing we built already exists: latent relation composition

This is the closest prior art to the anchor basis + residual walker, and it is
the most deflating section on the page.

| work | what it is | what it closes off for us |
|---|---|---|
| **TransE** (Bordes et al., 2013) `[panel]` | relation as translation: `h + r ≈ t` | our residual subtraction is this, executed against real edges instead of a scoring function |
| **RotatE, ComplEx** `[panel]` | relation as rotation / complex bilinear | the rotational family we rejected in Phase 1 — rejected there too, for different reasons |
| **GQE** (Hamilton et al., 2018) `[panel]` | embed conjunctive graph queries into a vector space | coordinate-space query composition, i.e. our "sum of relation coordinates" |
| **Query2Box** (Ren et al., 2020) `[panel]` | queries as boxes, handles disjunction | the sum-of-coordinates target has a well-studied better form |
| **BetaE** (Ren & Leskovec, 2020) `[panel]` | beta distributions, handles negation | ditto, with negation |
| **CQD** (Arakelyan et al., ICLR 2021) `[panel]` | decompose a complex query into **pretrained link-predictor calls**; beats learned end-to-end models | **this is our result.** "Decompose and use retrieval per step rather than learn the whole composition" is CQD's thesis, published |
| **CBR-KBQA** (Das et al., ~2021) `[panel]` | case-based retrieval beats learned models on KBQA | **also our result.** Retrieval-beats-learned-head is a known finding in this exact setting |

**Read this honestly**: our walker-beats-planner result (0.912 vs 0.534) and our
retrieval-beats-head result (0.975 vs 0.892) are both *reproductions* of
published findings, not discoveries. That does not make them worthless — they
are strong, independently-obtained confirmations on our own corpus, and they
are what licenses the pivot. It does mean neither is a contribution.

## 2. Store-grounded walking — the half of our work that survives

| work | what it is |
|---|---|
| **PRA** — Path Ranking Algorithm (Lao & Cohen) `[panel]` | features from typed paths in the graph |
| **DeepPath** `[panel]`, **MINERVA** (Das et al., 2018) `[panel]` | RL agents that walk KG edges to answer queries |
| **GraftNet**, **PullNet** `[panel]` | pull a question-specific subgraph, then reason over it |
| **MultiHopKG** `[panel]` | multi-hop reasoning over KGs with reward shaping |

The common thread — *let the graph's actual edges constrain the search* — is
what our walker result is evidence for, and it is well established. The open
question these leave is not "does it work" but "what does it cost to keep
current."

## 3. Substrate, provenance and immutability — where the pivot is heading

| work | what it is | relevance |
|---|---|---|
| **Wikidata / Wikibase** `[both]` | typed triples, qualifiers, references, open property vocabulary | the claims-with-provenance data model, already built and maintained; also a free source of a closed-ish predicate catalog with domain/range constraints |
| **RDF-star / RDF 1.2** `[panel]` | statements about statements | the mechanism for attaching conditions and confidence to a claim without inventing one |
| **Nanopublications** (Groth et al., ~2010) `[panel]` | atomic assertion + provenance + publication info, content-addressed, citable | **very close to the "condition-carrying claim" idea** — it is the unit we would be re-inventing |
| **PROV-O** (W3C) `[panel]` | provenance ontology: entity / activity / agent | the vocabulary for "who asserted this, from what, when" |
| **SHACL** `[panel]` | shape constraints over RDF | declared domain/range validation on append, without pretending the ontology is complete |
| **Datomic**, event sourcing, **CQRS** `[panel]` | immutable facts + time; derived read models rebuilt from the log | the architectural pattern that makes "never rebuild the data, freely rebuild the indexes" standard practice rather than a novelty |
| **Graphiti / Zep** `[panel]` | bitemporal, incrementally-updated KG memory for agents | closest live product to what we would build; check what it does *not* do before claiming white space |
| **GraphRAG** (Microsoft) `[panel]`, **HippoRAG**, **LightRAG**, LlamaIndex property graphs, Neo4j+vectors `[panel]` | ingest → entity/relation graph → retrieve over it | the crowded incumbent space; most rebuild community summaries or re-embed when the corpus moves — that gap is the operational white space |
| **OpenIE, ReVerb, NELL** `[panel]` | open information extraction, never-ending learning | extraction-side prior art; NELL is also the cautionary tale about unbounded self-ingestion |
| **FEVER** `[panel]` | claim verification against evidence | evaluation design for "is this claim supported by its evidence" |

## 4. Query compilation — the LM's actual job

| work | relevance |
|---|---|
| **Text-to-SQL / Text-to-SPARQL / Text-to-Cypher** `[panel]` | the LM compiles a question into an executable typed query; it does not answer |
| **Schema linking** (text-to-SQL literature) `[panel]` | mapping a novel phrase onto a fixed catalog — **this is exactly what our 0.975 1-NN result is**, and it is a solved subproblem with a literature |
| constrained decoding / function calling `[panel]` | how to make the compiled query well-formed by construction |

## 5. Federation and merge — added here, not covered by the panel

The panel was never asked about distributed stores. These are the pieces that
matter if knowledge is to be shared and synthesised across independent stores.

| work | relevance |
|---|---|
| **CRDTs** (Shapiro et al., 2011) `[mine]` | conflict-free replicated data types; **an append-only set of immutable claims is a grow-only set (G-Set), the simplest CRDT there is** — merge is set union, no coordination, no conflict at the storage layer |
| **Content addressing** (Merkle DAGs, IPFS, git) `[mine]` | claim identity = hash of its content, so two stores that independently extract the same claim produce the same id; deduplication and merge become free |
| **Solid / linked-data pods** `[mine]` | federated personal data stores with URI identity and access control; the governance model for "my store, your store, shared queries" |
| **Linked Data / owl:sameAs, IRI minting** `[mine]` | the standing hard problem of federated identity: two stores mint different ids for the same entity. Note `owl:sameAs` is widely misused in practice — a **defeasible, provenanced identity claim** is the safer form |
| **Dataset versioning / RDF named graphs** `[mine]` | scoping claims to a source store, so merges stay attributable |

## 6. Epistemics — belief, conflict, and not resolving it

| work | relevance |
|---|---|
| **ATMS / JTMS** (de Kleer, 1986) `[mine]` | assumption-based truth maintenance: hold **multiple mutually inconsistent contexts simultaneously** and label each belief with the assumption sets under which it holds. This is the closest formal ancestor of "carry both claims with their conditions" and it is largely abandoned in modern systems |
| **AGM belief revision** (Alchourrón, Gärdenfors, Makinson, 1985) `[mine]` | the formal theory of revising a belief set on contradiction — and the reason to *not* do it: AGM resolves, we want to preserve |
| **Paraconsistent logic** `[mine]` | logics where a contradiction does not entail everything; the formal license for storing `P` and `¬P` without the store becoming useless |
| **Dempster–Shafer, subjective logic** `[mine]` | combining evidence from sources with differing reliability, with explicit ignorance — relevant if confidence is ever computed rather than asserted |
| **Argumentation frameworks** (Dung, 1995) `[mine]` | attack relations between claims, with well-defined semantics for what survives; a principled alternative to scoring |
| **Datalog / semi-naive evaluation** `[mine]` | deriving edges from declared rules (transitivity, inverses) incrementally as facts are appended — the mechanism for "axioms" that does not require refitting anything |

## 7. Encoder migration — the constraint, restated as an engineering problem

| work | relevance |
|---|---|
| **HNSW** `[mine]` | incremental insert; append-friendly ANN index, no global rebuild to add vectors |
| **Matryoshka representation learning** `[mine]` | nested-dimension embeddings; truncation without retraining. EmbeddingGemma has this |
| blue/green index generations, Elasticsearch aliases `[panel]` | dual-write, query both, backfill, retire — zero-downtime index replacement is **routine operations practice**, which is the panel's strongest argument that "never reindex" was over-generalised |

## 8. Not recommended, and why — graph neural networks

`[mine]` **GraphSAGE** (Hamilton et al., 2017), **GAT**, **R-GCN** and the message-passing family learn node and edge representations *fitted to a particular graph*. Three reasons to stay out for now:

1. They are the same bet as the anchor basis, one layer up — a learned representation over structure. That bet is 0-for-9 in this project.
2. Representations shift when the graph grows. Inductive variants (GraphSAGE) reduce but do not remove this, and it is precisely the global-refit failure mode the constraint exists to prevent.
3. Fitted node embeddings do not survive federation: two stores with different subgraphs produce incompatible representations, so nothing can be shared but raw claims.

**Graph *theory*, as distinct from GNNs, is directly load-bearing** — typed path
search, reachability under type constraints, bounded-depth enumeration for
query planning, the relation algebra (transitivity, inverse, functionality) as
derivation rules, and the CRDT/lattice algebra that makes federated merge
sound. Use the algorithms; skip the learned representations.
