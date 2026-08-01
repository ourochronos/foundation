**1. The fatal flaw: content addresses are built on the one thing that isn't stable — entity identity — and §2's cross-store targeting cannot actually happen.**

The address of `c1 = (smith, causes, famine)` must be computed over *something*. Two options, both broken:

- **Address includes spans/doc-context:** then Paper B, extracted from Paper B's text, can never compute store A's address for Smith's claim. The extractor has never seen store A; it reconstructs Smith's claim from B's paraphrase, and paraphrase ≠ byte-identical normalized form. The link is never made. §2's "targeting without copying" quietly degrades to "copy and pray for hash collision," and dedup returns false negatives pervasively. Merge doesn't mis-target — it never targets, which is worse because it's silent.
- **Address excludes spans, computed over canonical entity ids + predicate + object + polarity + modality:** then the address depends on the identity closure. Store A has `smith_j` and `j_smith` as separate entities; c1 references `smith_j`; store B holds `addr(c1)`. The closure later merges the two entities → c1's canonical form changes → its content address changes → every reference in store B dangles. Because claims reference claims, this cascades Merkle-style: one entity merge rehashes every claim transitively downstream. §5 makes `under_assumption` depend on this same closure, so the document has wired its two "solved" components (addressing, identity) into a circle and declared both unproblematic. **This is the relocated flaw.** The v2 bug was an edge silently targeting the wrong claim; v3's is an edge silently targeting nothing, plus retroactive address churn.

Fix concretely: mint opaque, immutable assertion IDs and make coreference a first-class, revocable assertion — never derive identity from content:

```sql
claims(assertion_id uuid PRIMARY KEY,   -- minted at extraction, never recomputed
       doc_sha text, local_handle text, ...);
claim_same_as(a uuid, b uuid, basis text, confidence real);  -- merge = insert rows; unmerge = delete rows
```

A merge is then monotone and reversible; entity re-canonicalization touches `claim_same_as`, not every downstream reference.

**Second fatal-class problem: encoding non-determinism silently defeats contradiction detection.** *"If the ban passes, prices will rise"* has three legal encodings in §6: (a) `modality: hypothetical` on the prices claim; (b) `under_assumption: {entity: ban_passes}`; (c) reified `(c_ban, IMPLIES, claim:c_prices)`. *"Smith suggests X may cause Y"* has two places for the hedge: predicate `SUGGEST` or `modality: hedged` on the inner claim, or both. Two annotators, or two stores, encode the same sentence in incomparable shapes; a contradiction checker comparing `(X, causes, Y, hedged)` against `(smith, SUGGEST, claim:(X, causes, Y, asserted))` sees no relation. Nothing errors. This is the answer to the document's own Q1 and it is a corpus-killer for a gold standard.

**2. What forces a CLOSED-layer change within a year: the stance predicates.**

Cutting `attribution.mode` didn't delete the epistemic taxonomy; §1 relocated it into the *open* predicate vocabulary. `DENY` flips truth-commitment; `REPORT` doesn't; `ARGUE` commits the attributor. Any consumer doing entailment or contradiction needs a closed table mapping each reifying predicate to commitment semantics. Within months of annotating the four corpora you will need `QUESTION`, `RETRACT`, `PREDICT`, `CONCEDE`, `DOUBT`, `FAIL_TO_REPLICATE` — each with different commitment behavior — and annotators will coin them freely because predicates have nullable ids. Every coinage is a semantic change to what the gold layer *means* even though no bytes change. Fix now, it's cheap:

```sql
stance_predicates(pred_id text PRIMARY KEY,
  attributor_commitment text CHECK (attributor_commitment IN ('pro','anti','neutral')),
  flips_inner_polarity boolean);
-- DENY: anti,true   REPORT: neutral,false   ARGUE: pro,false
```

Closed enum, extendable by adding rows with defined semantics — not by annotator improvisation.

Secondary: `valid_time` is a span with no normalized value. Temporal reasoning will demand normalization; that's a re-pass over gold. Accept that migration (normalization can be added mechanically without re-reading, unlike modality).

**3. Over-built: delete `under_assumption` from `scope` entirely.**

Assumptions are propositions, not entities. "Assuming linear dose-response" is a claim; forcing it through entity identity closure (§5) shoehorns exactly the way the rejected closed-frame inventory did, one level down. The document already built the right mechanism and then didn't use it: `(c1, CONDITIONAL_ON, claim:c_assumption)` is plain reification. §5 exists only to preserve exp73's requirement label, not to solve a problem this system has. Also delete `marker: SOME` — it encodes bare existential quantification that `{"literal": ...}` or an unquantified entity object already carries; it will be used ~never and inconsistently.

**4. The final section poses five questions, not seven.** Either two were cut without renumbering the framing or the count was never checked; either way, answered as listed:

1. **No.** It closes syntactic nesting and opens encoding non-determinism (see flaw #2 above). The problem moved to exactly where the question suspects: claim vs. qualifier vs. modality vs. assumption, with three legal encodings of one conditional and no tiebreak rule in the document.
2. **Not decidable.** Breakers: *"There is no evidence that X causes Y"* — the negation scopes the evidential, not the relation; rule 2 fires and gold records `(X, causes, Y, "-")`, i.e. asserted non-causation. Data corruption, silent. *"The study failed to replicate the effect"* — is "failed to" a cue over the relation (rule 2) or lexical negation resolving into the predicate (rule 3)? Rules 2 and 3 give different outputs and nothing orders them here, because rule 3's trigger ("inside the lexeme") is itself the judgment call. *"Rarely causes"* — quantified to *almost* nothing; neither NONE nor a polarity fits. Add a rule 0: negation over evidentials/attitude verbs reifies (`(study, FAIL_TO_SHOW, claim:...)`), never sets polarity.
3. **Quantification, by the document's own §4 argument.** "Most smokers develop X" annotated today with no quantifier field silently claims *all* under the absent-qualifier-means-unrestricted rule. `NONE|SOME` markers concede quantity exists and can't extend without re-reading every document. This is keep-now-or-never by the identical asymmetry used to justify modality. Add `quant: none|some|most|all|unspecified` on the object now, replacing `marker`. Second: the modality-attachment rule under reification (which claim carries the hedge) is unstated; every reified annotation made before it's stated is ambiguous gold.
4. **Yes, it is `attribution.mode` returning — twice.** Once as `hedged|hypothetical` (the "visible lexical cue" defense fails on *"is consistent with"* vs *"suggests"* vs *"may"* — annotators will not agree on hedged vs hypothetical for "would be expected to"), and once as the open stance-predicate vocabulary of §1, which has the same agreement problem but no longer has an enum anyone can audit. Collapse to two values, `asserted|non-asserted`, or keep three and accept κ ≈ what killed round 1's mode.
5. **Yes: `under_assumption` (delete, see #3), `marker: SOME` (delete), and per-field `span` on `modality`** — a modality cue span will be annotated inconsistently (which of three hedges in the sentence?) and nothing consumes it; keep spans for polarity cues only.

**5. What breaks first at scale.**

*10^6 assertions, one Postgres:* not row count — that's trivial. Two things: (a) claim→claim reference chains make every contradiction/provenance query a recursive CTE over an unbounded reification graph; without a materialized transitive-closure table this is the first query to fall over, at depth ~4–5 on hot entities. (b) If content addressing stays: one identity-closure update on a high-degree entity (a canonical author, a common chemical) rewrites the addresses of every claim referencing it *and* every claim transitively referencing those — write amplification proportional to reification depth × entity degree, inside one transaction or with dangling refs in between.

*Merging two 10^6 stores:* the circular dependency breaks first. Content addresses are comparable only after entity identity is aligned across stores; identity alignment is the merge's hardest step and runs *on* the claims. So merge needs stable addresses, and addresses need the merged identity. With the minted-ID + `claim_same_as` design above, merge is: concatenate both stores unchanged (immutable IDs can't collide or churn), then run identity alignment as pure insertion of `same_as` rows — incremental, resumable, and reversible when the aligner is wrong, which at 10^6 × 10^6 it will be.


[stderr] 

Changes    +0 -0
Requests   1 Premium (2m 1s)
Tokens     ↑ 35.5k (35.5k written) • ↓ 7.4k (4.2k reasoning)
Resume     copilot --resume=479f2320-c892-426f-9c65-4e51f37dad92
