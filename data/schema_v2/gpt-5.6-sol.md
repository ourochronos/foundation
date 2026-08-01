## 1. The fatal flaw

`claim_relations` has only document-local claim IDs, so the central cite/dispute repair does not work across documents or federated stores.

Paper B says, “Contrary to Smith (2020), tax cuts increase revenue.” Smith’s claim is `c1` in store A; Paper B cannot target it unless it copies the claim locally. After merging, both stores may contain `c1`, and the edge can silently target the wrong claim. Copying instead creates two propositions with different evidence and identity.

The same missing act/proposition distinction breaks nesting. A list cannot represent:

> The Times reported [that Smith denied [X]].

`[Times, Smith]` loses who performed which act, and `denied` is neither `author` nor `reported`. Although the document claims support for `act_ref` and `prop_ref`, neither is legal in the shown claim object.

Use globally stable IDs and explicit nesting:

```sql
document(id uuid, source_uri text, revision text, content_hash bytea);

proposition(id uuid, subject_id uuid, predicate_id text, object jsonb);

claim_act(
  id uuid,
  proposition_id uuid,
  holder_id uuid,
  act_type text,          -- assert, deny, report, ask
  parent_act_id uuid,     -- Times report -> Smith denial
  document_id uuid,
  evidence_start int,
  evidence_end int
);

claim_edge(
  from_act_id uuid,
  edge_type text,
  to_act_id uuid,
  external_target jsonb  -- DOI/document locator when target is not imported
);
```

## 2. What forces a CLOSED-layer change within a year

**Modality and illocution.** The current schema turns all of these into the same positive claim:

- “X causes Y.”
- “X may cause Y.”
- “If Z, X causes Y.”
- “Does X cause Y?”
- “Smith hopes X causes Y.”

Adding modality later requires rereading every positive claim because absence currently means assertion. Fix it now with source-grounded operators such as `asserted`, `possible`, `conditional`, `questioned`, and `desired`, each with an anchored scope.

The claimed layer separation is also not implemented: entity type, predicate ID, frame ID, polarity, and attribution kind are normalization fields embedded in the supposedly permanent annotation.

## 3. Where it is over-built

Delete the **school→assumption-scope projection** outright.

“Keynesians believe X” does not mean “X is true given Keynesian assumptions.” If Keynesians assert X and Monetarists assert not-X, projecting each into separate assumption scopes makes contradiction detection declare coexistence precisely where the text records disagreement. It relocates the original annotation ambiguity into an unsound closure rule.

Also delete per-field duplicate cue strings. Store one authoritative evidence span plus optional operator spans; repeated quoted strings are neither stable identifiers nor useful independent supervision.

## 4. The final-section questions

1. **No.** Cue anchoring does not protect the investment. A quote is not an anchor when identical text occurs twice, documents are revised, or evidence is discontinuous. Store document revision plus offsets; retain quote text only for integrity checking.

2. **Wrong.** “John did not fail to leave” contains sentence-level negation but entails that John left. “Not every student passed” cannot be represented by one binary polarity over `student/pass`. Negation and quantifiers require explicit scope; `NONE` as an object marker does not solve this.

3. **Wrong.** `cites` is a source/act relation; `supports` and `disputes` are stance acts, not homogeneous proposition relations. A flat list loses holder, time, qualification, evidence, nesting, and external targets. Model citation separately and represent stance as an attributed act targeting another act or proposition.

4. **Missing and annotation-invalidating:** modality, conditionals, questions, commands/desires, quantifier scope, cross-document target identity, and nested speech acts. Add them before annotation. At minimum, every extracted proposition needs an assertion-status operator and every relation target needs a globally resolvable reference.

5. **Yes.** Exhaustive per-decision cues, mention clustering, closed entity typing, predicate normalization, frame assignment, and claim-edge classification in one pass are too expensive. They also contradict the stated separation of source extraction from normalization.

6. **Halve document count, not semantic coverage.** Fully annotate a representative half. If fields must be cut, remove entity types, predicate IDs, frame IDs, mention coreference, and duplicate cues. Keep raw argument spans, proposition structure, operator scope, attribution acts, evidence, and cross-claim targets.

7. **There is no seventh open question.** The final section contains six numbered questions.

## 5. What breaks first at scale

**One million assertions on one Postgres instance:** contradiction candidate generation. Unrestricted claims and school-projected scopes create large self-joins on common subject/predicate keys; popular entities become hot partitions, and pair counts approach quadratic. JSONB claim blobs and duplicated quote strings then amplify index and table bloat. Store normalized acts, propositions, spans, and edges; generate candidates only from indexed canonical keys and explicit compatible scope dimensions.

**Merging two million-assertion stores:** identity corrupts first. `c1`, `e1`, predicate IDs, frame versions, and document-local quoted evidence have no federated namespace. Edges can resolve to unrelated claims before entity deduplication even begins. Use UUIDs, immutable document/version IDs, vocabulary-version namespaces, provenance on every act, and external target locators; never rewrite local IDs during merge.1. The fatal flaw

claim_relations has only document-local claim IDs, so the central cite/dispute repair does not work
across documents or federated stores.

Paper B says, “Contrary to Smith (2020), tax cuts increase revenue.” Smith’s claim is c1 in store A;
 Paper B cannot target it unless it copies the claim locally. After merging, both stores may contain
 c1, and the edge can silently target the wrong claim. Copying instead creates two propositions with
 different evidence and identity.

The same missing act/proposition distinction breaks nesting. A list cannot represent:

 The Times reported [that Smith denied [X]].

[Times, Smith] loses who performed which act, and denied is neither author nor reported. Although
the document claims support for act_ref and prop_ref, neither is legal in the shown claim object.

Use globally stable IDs and explicit nesting:

 document(id uuid, source_uri text, revision text, content_hash bytea);

 proposition(id uuid, subject_id uuid, predicate_id text, object jsonb);

 claim_act(
   id uuid,
   proposition_id uuid,
   holder_id uuid,
   act_type text,          -- assert, deny, report, ask
   parent_act_id uuid,     -- Times report -> Smith denial
   document_id uuid,
   evidence_start int,
   evidence_end int
 );

 claim_edge(
   from_act_id uuid,
   edge_type text,
   to_act_id uuid,
   external_target jsonb  -- DOI/document locator when target is not imported
 );

2. What forces a CLOSED-layer change within a year

Modality and illocution. The current schema turns all of these into the same positive claim:

 - “X causes Y.”
 - “X may cause Y.”
 - “If Z, X causes Y.”
 - “Does X cause Y?”
 - “Smith hopes X causes Y.”

Adding modality later requires rereading every positive claim because absence currently means
assertion. Fix it now with source-grounded operators such as asserted, possible, conditional,
questioned, and desired, each with an anchored scope.

The claimed layer separation is also not implemented: entity type, predicate ID, frame ID, polarity,
 and attribution kind are normalization fields embedded in the supposedly permanent annotation.

3. Where it is over-built

Delete the school→assumption-scope projection outright.

“Keynesians believe X” does not mean “X is true given Keynesian assumptions.” If Keynesians assert X
 and Monetarists assert not-X, projecting each into separate assumption scopes makes contradiction
detection declare coexistence precisely where the text records disagreement. It relocates the
original annotation ambiguity into an unsound closure rule.

Also delete per-field duplicate cue strings. Store one authoritative evidence span plus optional
operator spans; repeated quoted strings are neither stable identifiers nor useful independent
supervision.

4. The final-section questions

 1. No. Cue anchoring does not protect the investment. A quote is not an anchor when identical text
occurs twice, documents are revised, or evidence is discontinuous. Store document revision plus
offsets; retain quote text only for integrity checking.
 2. Wrong. “John did not fail to leave” contains sentence-level negation but entails that John left.
 “Not every student passed” cannot be represented by one binary polarity over student/pass. Negation
 and quantifiers require explicit scope; NONE as an object marker does not solve this.
 3. Wrong. cites is a source/act relation; supports and disputes are stance acts, not homogeneous
proposition relations. A flat list loses holder, time, qualification, evidence, nesting, and
external targets. Model citation separately and represent stance as an attributed act targeting
another act or proposition.
 4. Missing and annotation-invalidating: modality, conditionals, questions, commands/desires,
quantifier scope, cross-document target identity, and nested speech acts. Add them before
annotation. At minimum, every extracted proposition needs an assertion-status operator and every
relation target needs a globally resolvable reference.
 5. Yes. Exhaustive per-decision cues, mention clustering, closed entity typing, predicate
normalization, frame assignment, and claim-edge classification in one pass are too expensive. They
also contradict the stated separation of source extraction from normalization.
 6. Halve document count, not semantic coverage. Fully annotate a representative half. If fields
must be cut, remove entity types, predicate IDs, frame IDs, mention coreference, and duplicate cues.
 Keep raw argument spans, proposition structure, operator scope, attribution acts, evidence, and
cross-claim targets.
 7. There is no seventh open question. The final section contains six numbered questions.

5. What breaks first at scale

One million assertions on one Postgres instance: contradiction candidate generation. Unrestricted
claims and school-projected scopes create large self-joins on common subject/predicate keys; popular
 entities become hot partitions, and pair counts approach quadratic. JSONB claim blobs and
duplicated quote strings then amplify index and table bloat. Store normalized acts, propositions,
spans, and edges; generate candidates only from indexed canonical keys and explicit compatible scope
 dimensions.

Merging two million-assertion stores: identity corrupts first. c1, e1, predicate IDs, frame
versions, and document-local quoted evidence have no federated namespace. Edges can resolve to
unrelated claims before entity deduplication even begins. Use UUIDs, immutable document/version IDs,
 vocabulary-version namespaces, provenance on every act, and external target locators; never rewrite
 local IDs during merge.


[stderr] 

Changes    +0 -0
Requests   0 Premium (1m 4s)
Tokens     ↑ 21.8k (21.7k written) • ↓ 3.3k (2.1k reasoning)
Resume     copilot --resume=e90a52de-5049-4b40-9133-788b88ed7106
