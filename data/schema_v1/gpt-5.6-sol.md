**Recommendation: discard this schema before annotation.** Its central mistake is mixing source-grounded extraction, ontology normalization, and store insertion into one gold object. Those layers will evolve at different rates, so this design does not actually protect the annotation investment.

1. **The field you will regret is `scope.under_assumption`.** It conflates reported belief, theoretical framing, hypothetical conditions, and genuine truth conditions. Annotators cannot reliably infer which interpretation the author intended.

   Highest to lowest annotation cost per downstream value:

   1. `flags`
   2. `under_assumption`
   3. `link_confidence`
   4. `attribution.mode`
   5. `link_proposal`
   6. entity `type`
   7. normalized `valid_time` / `valid_place`
   8. coreference clustering and `surface`
   9. normalized `predicate`
   10. claimant/holder
   11. subject and object
   12. polarity
   13. evidence spans

   Free-text flags should never be gold. Confidence is a model property, not an annotation target.

2. **What is structurally missing is source anchoring for each decision and recursive propositions.** A single `evidence_span` cannot preserve the annotation when predicate normalization, linking, scope representation, or attribution taxonomy changes. Record argument spans, relation span, polarity cue, attribution cue, and qualifier spans separately.

   Assertions also need IDs so claim acts and conditions can target propositions. Otherwise nested attribution—“A reports that B denies X”—and explicit conditionals eventually force a schema rewrite.

3. **“Keynesians hold that X” makes Keynesians the claimant, not an assumption.** Reported commitment does not alter X’s truth conditions. Use `under_assumption` only when the source independently expresses a conditional frame: “Given Keynesian assumptions, X.”

   Annotate both only when both have separate textual evidence—for example, “Keynesians claim that, under assumption A, X.” Never derive one from the other.

4. **Monolithic bundled inference is not sound.** Field-level scores remain computable, but error attribution becomes meaningless: a missing entity can suppress a claim, attribution, and scope simultaneously, while scoring makes these appear as four independent failures.

   Use one shared fine-tuned backbone if desired, but invoke separately scorable tasks with explicit intermediate inputs: mentions/coreference → source-level propositions → normalization/linking. Bundle execution operationally, not semantically.

5. **The strongest alternative is an optimized prompted model producing source-anchored propositions, followed by deterministic or separately trained normalization.** The existing Gemma comparison does not justify fine-tuning because the prompt was knowingly unoptimized.

   Settle this before gold annotation with a small, adjudicated pilot containing negation, nested attribution, conditionals, coreference, and domain shift. Compare optimized constrained prompting, the proposed fine-tune, and a staged system by claim recall, polarity/claimant accuracy, calibration, cross-domain degradation, and corrected claims per annotator-hour. If prompting is competitive on the hard slices, do not train the transducer.

6. **The smallest durable schema is:**

```jsonc
{
  "mentions": [{"id": "m1", "spans": [[12, 30], [51, 59]]}],
  "assertions": [{
    "id": "a1",
    "subject": "m1",
    "relation_span": [60, 68],
    "predicate": "P937", // optional normalization
    "object": {"mention": "m2"},
    "polarity": "-",
    "polarity_cue_span": [56, 59],
    "qualifiers": [{"kind": "time|place|condition", "span": [70, 82]}],
    "evidence_spans": [[51, 82]]
  }],
  "claim_acts": [{
    "assertion": "a1",
    "claimant": "m3",
    "mode": "asserts|reports|infers|predicts",
    "cue_span": [31, 40]
  }]
}
```

Cut copied surface strings, entity types, links, confidence, free-text flags, and free-text assumptions. Derive them later. Keep normalized predicates nullable and retain relation spans so the ontology can change without destroying the gold set.Recommendation: discard this schema before annotation. Its central mistake is mixing source-grounded
 extraction, ontology normalization, and store insertion into one gold object. Those layers will
evolve at different rates, so this design does not actually protect the annotation investment.

 1. The field you will regret is scope.under_assumption. It conflates reported belief, theoretical
framing, hypothetical conditions, and genuine truth conditions. Annotators cannot reliably infer
which interpretation the author intended.
 Highest to lowest annotation cost per downstream value:
 1. flags
 2. under_assumption
 3. link_confidence
 4. attribution.mode
 5. link_proposal
 6. entity type
 7. normalized valid_time / valid_place
 8. coreference clustering and surface
 9. normalized predicate
 10. claimant/holder
 11. subject and object
 12. polarity
 13. evidence spans
 Free-text flags should never be gold. Confidence is a model property, not an annotation target.
 2. What is structurally missing is source anchoring for each decision and recursive propositions. A
 single evidence_span cannot preserve the annotation when predicate normalization, linking, scope
representation, or attribution taxonomy changes. Record argument spans, relation span, polarity cue,
 attribution cue, and qualifier spans separately.
 Assertions also need IDs so claim acts and conditions can target propositions. Otherwise nested
attribution—“A reports that B denies X”—and explicit conditionals eventually force a schema rewrite.
 3. “Keynesians hold that X” makes Keynesians the claimant, not an assumption. Reported commitment
does not alter X’s truth conditions. Use under_assumption only when the source independently
expresses a conditional frame: “Given Keynesian assumptions, X.”
 Annotate both only when both have separate textual evidence—for example, “Keynesians claim that,
under assumption A, X.” Never derive one from the other.
 4. Monolithic bundled inference is not sound. Field-level scores remain computable, but error
attribution becomes meaningless: a missing entity can suppress a claim, attribution, and scope
simultaneously, while scoring makes these appear as four independent failures.
 Use one shared fine-tuned backbone if desired, but invoke separately scorable tasks with explicit
intermediate inputs: mentions/coreference → source-level propositions → normalization/linking.
Bundle execution operationally, not semantically.
 5. The strongest alternative is an optimized prompted model producing source-anchored propositions,
 followed by deterministic or separately trained normalization. The existing Gemma comparison does
not justify fine-tuning because the prompt was knowingly unoptimized.
 Settle this before gold annotation with a small, adjudicated pilot containing negation, nested
attribution, conditionals, coreference, and domain shift. Compare optimized constrained prompting,
the proposed fine-tune, and a staged system by claim recall, polarity/claimant accuracy,
calibration, cross-domain degradation, and corrected claims per annotator-hour. If prompting is
competitive on the hard slices, do not train the transducer.
 6. The smallest durable schema is:

 {
   "mentions": [{"id": "m1", "spans": [[12, 30], [51, 59]]}],
   "assertions": [{
     "id": "a1",
     "subject": "m1",
     "relation_span": [60, 68],
     "predicate": "P937", // optional normalization
     "object": {"mention": "m2"},
     "polarity": "-",
     "polarity_cue_span": [56, 59],
     "qualifiers": [{"kind": "time|place|condition", "span": [70, 82]}],
     "evidence_spans": [[51, 82]]
   }],
   "claim_acts": [{
     "assertion": "a1",
     "claimant": "m3",
     "mode": "asserts|reports|infers|predicts",
     "cue_span": [31, 40]
   }]
 }

Cut copied surface strings, entity types, links, confidence, free-text flags, and free-text
assumptions. Derive them later. Keep normalized predicates nullable and retain relation spans so the
 ontology can change without destroying the gold set.


[stderr] 

Changes    +0 -0
Requests   0 Premium (42s)
Tokens     ↑ 20.8k (20.8k written) • ↓ 2.0k (1.0k reasoning)
Resume     copilot --resume=844fd3a4-84cf-4a3c-a4b4-76160ba8e532
