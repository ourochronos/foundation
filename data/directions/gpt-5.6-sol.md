I’m grounding the recommendation in existing dynamic-KB, incremental-indexing, and claim-provenance systems before committing to a direction.I’m grounding the recommendation in existing dynamic-KB, incremental-indexing, and claim-provenance
systems before committing to a direction.

● Web Search (MCP: github-mcp-server) · Current knowledge graph RAG systems GraphRAG HippoRAG Light…
  └ {"type":"output_text","text":{"value":"Let’s break down the landscape of curr...

● Web Search (MCP: github-mcp-server) · Authoritative current open datasets suitable for scientific…
  └ {"type":"output_text","text":{"value":"Here is an authoritative summary of cu...

● Web Search (MCP: github-mcp-server) · Current prior art for incremental evolving knowledge graphs…
  └ {"type":"output_text","text":{"value":"Here’s an overview of recent and signi...

● Web Search (MCP: github-mcp-server) · Current systems and papers for versioned vector indexes, on…
  └ {"type":"output_text","text":{"value":"Here's an up-to-date guide to the curr...

## 1. Kill list

Abandon the entire coordinate-composition program.

- **Delete the learned head.** It loses to 1-NN by 0.083 and the gap does not shrink with data. It is learning an inferior approximation to retrieval.
- **Delete the anchor basis.** It has produced neither reliable transfer nor a surviving causal account of basis quality. A best novel-relation score of 0.453 is unusable infrastructure.
- **Delete residual subtraction and coordinate answer typing.** A sum of relation vectors erases order, branching, quantification and path identity. Let the graph represent composition.
- **Delete title-based entity identity.** Titles collide, change and vary by language. This will eventually corrupt provenance.
- **Delete the centroid gate.** Its refusal gain is purchased with a material correctness loss. Use predicate range constraints and evidence-based abstention instead.
- **Stop investigating task-partition alignment.** It is an observation about a failed representation family, not a foundation worth explaining.

Keep only the immutable claims, provenance, source-side entity naming, audit discipline and the empirical result that graph execution beats predicted paths.

## 2. The one thing to build

Build **TrialLedger**: a local, provenance-complete evidence ledger joining clinical-trial registrations, published outcome claims, corrections and retractions.

A question such as “Does intervention X reduce outcome Y?” should compile into a typed graph query, execute deterministically, and return the registered outcome, reported estimate, population, publication span, subsequent corrections and disagreements. The LLM compiles; it does not answer. Predicate definitions and examples are retrieved at query time, so unseen predicates become usable by appending a relation card rather than training a representation.

The first killing experiment:

1. Select 120 trial/publication pairs containing NCT identifiers.
2. Build with predicates for interventions, primary outcomes and effect estimates.
3. After freezing it, append previously absent predicates for adverse events, secondary outcomes, corrections and retractions.
4. Ask 150 manually checkable questions: 50 original-schema, 50 new-schema and 50 unanswerable.
5. Compare against direct constrained SQL generation by the local 27B model.

Kill TrialLedger if it fails to achieve at least 90% provenance-correct execution, exceeds 5% unsupported answers, or fails to beat direct SQL generation by ten percentage points on the new-schema questions. Do not respond by training another latent head.

## 3. Prior art, honestly

Most components already exist:

- **Wikibase, RDF-star, Nanopublications and PROV-O** model qualified assertions and provenance.
- **Datomic, event sourcing and CQRS** treat durable facts as immutable events with rebuildable projections.
- **Graphiti/Zep** provides incrementally updated, bitemporal knowledge-graph memory.
- **Text-to-SQL, function calling and constrained semantic parsing** already compile language into executable operations.
- **Trialstreamer, RobotReviewer, EBM-NLP and Evidence Inference** extract structured clinical evidence.
- **ClinicalTrials.gov/AACT** already exposes structured trial registrations.
- **Elasticsearch aliases and ordinary blue/green deployments** already solve zero-downtime index replacement.

This is a crowded integration space. The white space is narrow: a local-first system that joins *registered intent* to *published claims and later corrections*, preserves evidence spans, evaluates unsupported-answer behavior, and treats schema and model migration as normal operations. Neither embeddings nor an ontology stack are the novelty.

## 4. Concrete substrate choices

Use a focused corpus, not more miscellaneous Wikipedia and model-card triples:

- **ClinicalTrials.gov/AACT:** structured interventions, outcomes, dates and identifiers.
- **PubMed plus PMC Open Access:** publication metadata and legally usable full text.
- **Crossref:** DOI identity, corrections, expressions of concern and retraction links.
- **OpenAlex:** citation expansion only; do not ingest it indiscriminately.
- **Evidence Inference and EBM-NLP:** evaluation data, not ground truth to copy into production.

The durable schema should resemble:

```text
entity(entity_id, kind_id)
entity_name(entity_id, text, language, valid_time, source_id)
predicate(predicate_id)
predicate_version(predicate_id, version, definition, domain_rule, range_rule)
assertion(assertion_id, subject_id, predicate_id, object, polarity,
          modality, valid_time, recorded_at, extractor_version)
evidence(evidence_id, document_id, content_hash, locator, quoted_span)
assertion_evidence(assertion_id, evidence_id)
assertion_event(assertion_id, event_type, recorded_at, reason, supersedes)
schema_event(event_id, predicate_id, event_type, payload, recorded_at)
```

Use opaque identifiers. Renames create aliases; corrections and retractions append events; predicate splits create mappings without rewriting old assertions. Keep extraction confidence separate from confidence that a scientific claim is true.

The type system should close only the **storage and execution grammar**: entity, assertion, evidence, document, agent, interval, quantity, unit, negation, modality and query operators. Domain classes, predicates and relation categories remain open vocabularies. SHACL-like domain/range rules can reject impossible query plans without pretending the ontology is complete.

The §7 split is wrong. Entities, relations, categories, lenses and axioms are all semantically open. The genuinely closed layer is the claim grammar, provenance semantics and query intermediate representation. “Worldviews” are versioned query policies, not higher representations.

Use the existing local 27B model for constrained extraction and query compilation. Use raw BGE-M3 plus PostgreSQL full-text search only to retrieve entity and predicate cards; embeddings must never define identity. Store embeddings in model-versioned columns or tables. Train nothing initially. Avoid whitening, bespoke relation heads, graph neural networks, embedding-space adapters and further encoder bake-offs.

## 5. The premise I would attack

The absolute never-reindex constraint is wrong.

An arbitrary encoder replacement changes the meaning of every vector. There are only four responses: retain the old encoder forever, compare incompatible spaces, learn an unreliable cross-space mapping, or recompute old embeddings. The current architecture has spent its complexity budget trying to deny this fact.

Replace the constraint with:

> Durable claims are never rebuilt, serving never stops, and every derived index can migrate incrementally with bounded resources and rollback.

Maintain old and new index generations, dual-write new claims, query both during migration, backfill in the background, measure parity, then retire the old generation. That may touch every row eventually, but it is not a stop-the-world rebuild. Requiring less is not robustness; it is forced semantic stagnation.

TOP-PICK: Build TrialLedger around immutable evidence assertions and executable typed queries, while replacing “never reindex” with zero-downtime versioned index migration.1. Kill list

Abandon the entire coordinate-composition program.

 - Delete the learned head. It loses to 1-NN by 0.083 and the gap does not shrink with data. It is
learning an inferior approximation to retrieval.
 - Delete the anchor basis. It has produced neither reliable transfer nor a surviving causal account
 of basis quality. A best novel-relation score of 0.453 is unusable infrastructure.
 - Delete residual subtraction and coordinate answer typing. A sum of relation vectors erases order,
 branching, quantification and path identity. Let the graph represent composition.
 - Delete title-based entity identity. Titles collide, change and vary by language. This will
eventually corrupt provenance.
 - Delete the centroid gate. Its refusal gain is purchased with a material correctness loss. Use
predicate range constraints and evidence-based abstention instead.
 - Stop investigating task-partition alignment. It is an observation about a failed representation
family, not a foundation worth explaining.

Keep only the immutable claims, provenance, source-side entity naming, audit discipline and the
empirical result that graph execution beats predicted paths.

2. The one thing to build

Build TrialLedger: a local, provenance-complete evidence ledger joining clinical-trial
registrations, published outcome claims, corrections and retractions.

A question such as “Does intervention X reduce outcome Y?” should compile into a typed graph query,
execute deterministically, and return the registered outcome, reported estimate, population,
publication span, subsequent corrections and disagreements. The LLM compiles; it does not answer.
Predicate definitions and examples are retrieved at query time, so unseen predicates become usable
by appending a relation card rather than training a representation.

The first killing experiment:

 1. Select 120 trial/publication pairs containing NCT identifiers.
 2. Build with predicates for interventions, primary outcomes and effect estimates.
 3. After freezing it, append previously absent predicates for adverse events, secondary outcomes,
corrections and retractions.
 4. Ask 150 manually checkable questions: 50 original-schema, 50 new-schema and 50 unanswerable.
 5. Compare against direct constrained SQL generation by the local 27B model.

Kill TrialLedger if it fails to achieve at least 90% provenance-correct execution, exceeds 5%
unsupported answers, or fails to beat direct SQL generation by ten percentage points on the
new-schema questions. Do not respond by training another latent head.

3. Prior art, honestly

Most components already exist:

 - Wikibase, RDF-star, Nanopublications and PROV-O model qualified assertions and provenance.
 - Datomic, event sourcing and CQRS treat durable facts as immutable events with rebuildable
projections.
 - Graphiti/Zep provides incrementally updated, bitemporal knowledge-graph memory.
 - Text-to-SQL, function calling and constrained semantic parsing already compile language into
executable operations.
 - Trialstreamer, RobotReviewer, EBM-NLP and Evidence Inference extract structured clinical
evidence.
 - ClinicalTrials.gov/AACT already exposes structured trial registrations.
 - Elasticsearch aliases and ordinary blue/green deployments already solve zero-downtime index
replacement.

This is a crowded integration space. The white space is narrow: a local-first system that joins
registered intent to published claims and later corrections, preserves evidence spans, evaluates
unsupported-answer behavior, and treats schema and model migration as normal operations. Neither
embeddings nor an ontology stack are the novelty.

4. Concrete substrate choices

Use a focused corpus, not more miscellaneous Wikipedia and model-card triples:

 - ClinicalTrials.gov/AACT: structured interventions, outcomes, dates and identifiers.
 - PubMed plus PMC Open Access: publication metadata and legally usable full text.
 - Crossref: DOI identity, corrections, expressions of concern and retraction links.
 - OpenAlex: citation expansion only; do not ingest it indiscriminately.
 - Evidence Inference and EBM-NLP: evaluation data, not ground truth to copy into production.

The durable schema should resemble:

 entity(entity_id, kind_id)
 entity_name(entity_id, text, language, valid_time, source_id)
 predicate(predicate_id)
 predicate_version(predicate_id, version, definition, domain_rule, range_rule)
 assertion(assertion_id, subject_id, predicate_id, object, polarity,
           modality, valid_time, recorded_at, extractor_version)
 evidence(evidence_id, document_id, content_hash, locator, quoted_span)
 assertion_evidence(assertion_id, evidence_id)
 assertion_event(assertion_id, event_type, recorded_at, reason, supersedes)
 schema_event(event_id, predicate_id, event_type, payload, recorded_at)

Use opaque identifiers. Renames create aliases; corrections and retractions append events; predicate
 splits create mappings without rewriting old assertions. Keep extraction confidence separate from
confidence that a scientific claim is true.

The type system should close only the storage and execution grammar: entity, assertion, evidence,
document, agent, interval, quantity, unit, negation, modality and query operators. Domain classes,
predicates and relation categories remain open vocabularies. SHACL-like domain/range rules can
reject impossible query plans without pretending the ontology is complete.

The §7 split is wrong. Entities, relations, categories, lenses and axioms are all semantically open.
 The genuinely closed layer is the claim grammar, provenance semantics and query intermediate
representation. “Worldviews” are versioned query policies, not higher representations.

Use the existing local 27B model for constrained extraction and query compilation. Use raw BGE-M3
plus PostgreSQL full-text search only to retrieve entity and predicate cards; embeddings must never
define identity. Store embeddings in model-versioned columns or tables. Train nothing initially.
Avoid whitening, bespoke relation heads, graph neural networks, embedding-space adapters and further
 encoder bake-offs.

5. The premise I would attack

The absolute never-reindex constraint is wrong.

An arbitrary encoder replacement changes the meaning of every vector. There are only four responses:
 retain the old encoder forever, compare incompatible spaces, learn an unreliable cross-space
mapping, or recompute old embeddings. The current architecture has spent its complexity budget
trying to deny this fact.

Replace the constraint with:

 Durable claims are never rebuilt, serving never stops, and every derived index can migrate
incrementally with bounded resources and rollback.

Maintain old and new index generations, dual-write new claims, query both during migration, backfill
 in the background, measure parity, then retire the old generation. That may touch every row
eventually, but it is not a stop-the-world rebuild. Requiring less is not robustness; it is forced
semantic stagnation.

TOP-PICK: Build TrialLedger around immutable evidence assertions and executable typed queries, while
 replacing “never reindex” with zero-downtime versioned index migration.


[stderr] 

Changes    +0 -0
Requests   0 Premium (3m 28s)
Tokens     ↑ 52.1k (21.4k cached, 30.7k written) • ↓ 5.1k (3.4k reasoning)
Resume     copilot --resume=f4b72712-4b9c-4cd7-bc48-45bff01beb7e
