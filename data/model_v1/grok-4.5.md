Analyzing the data model on its own terms and pressure-testing identity, conflict, disclosure, and scale.

● Web Search (MCP: github-mcp-server) · content-addressed knowledge graphs sameAs equivalence class…
  └ {"type":"output_text","text":{"value":"Let's break down the complex area of c...

Checking one concrete edge case on qualifier hashing vs proposition keys before writing the review.

✗ Write structured break-notes for review (shell)
  │ cat > /tmp/model_break_notes.txt << 'EOF'
  │ Fatal chain:
  │ 1. assertion_hash includes raw subject refs + truth-conditional quals
  │ 2. proposition_key canonicalizes entity refs via sameAs closure for conflict/agreement
  │ 3. claim_ref points at assertion_hash (immutable)…
  └ Permission denied and could not request permission from user

1. **The fatal flaw**

Belief/confidence targets `claim_ref` → assertion hash (raw refs). Agreement/conflict targets proposition keys (closure reps). Semantic unification therefore does **not** apply to the thing §2 exists for.

```
A: (local:a1, dob, 1907-05-22, +, {})     → hash Ha
B: (local:b9, dob, 1907-05-22, +, {})     → hash Hb
both sameAs Q152
L4: one proposition, agreement=2
also: (Ha, believed, 0.9, +, {by: Alice})
     (Hb, believed, 0.2, +, {by: Alice})
```

Alice’s beliefs never meet. Reader asking “does Alice believe Q152’s dob?” gets two answers or a silent miss. Same for `extraction_fidelity` and `premise([Ha])` chains: inference graphs fork on syntax that L4 already collapsed. You fixed conflict by moving it to a derived key; you left every higher-order claim on the immutable hash. Higher-order claims are most of the personal-KB load (§0). The v0 flaw is not fixed — it is stacked one level up.

Stable content addresses cannot name mutable proposition keys; derived keys cannot be commitment targets. The design needs one of: (i) belief only as a fold over the current fiber of hashes for a prop key (lose “claim about a claim” as a first-class row), or (ii) reification of an accepted *interpretation snapshot* with its own address (Layer 4 becomes write-path, not a view). As written, both are forbidden.

---

2. **What forces a CLOSED-layer change within a year**

**Truth-conditional qualifiers in the assertion hash, with a global registered overlap algebra.**

First real corpus will need per-predicate scope (employment `valid_time` vs diagnosis `valid_time` vs `under_assumption` that is another claim_ref). Overlap of free-form assumptions is not a closed operator; it is entailment. You will want quals *out* of the hash or typed by predicate — either rewrites every assertion address.

Also forced: **`claim_ref` as one sort**. Retraction needs acts; belief-in-fact needs a proposition-stable target you do not have. When you split the sort (or add `proposition_ref`), every nested `premise`/`claim_ref` encoding changes → global address migration.

**Fix now:** assertion = (prop_skeleton without policy-relative ids), act carries claimant/mode/evidence; introduce explicit `Interpretation` or make “about proposition” a query-time fold. Accept migration later only if you freeze hashes as pure syntactic commits and never promise semantic targeting of them — document currently promises both.

---

3. **Where it is over-built**

- **§9 Merkle log + Poseidon agility as substrate requirements.** Personal-KB + research aggregation do not need circuit-friendly hashes on day one. `(algo_id, digest)` is cheap; the append-only Merkle selective-disclosure story is speculative scaffolding. Keep tagged digests; delete the Merkle/ZK protocol obligations from v1 storage.
- **`mode` enum on every act** (`predicts|hypothesises|…`). Almost all ingest is `asserts|infers|reports`. Mode-as-predicate claim about the act is enough; a closed enum in Layer 0 is premature ontology.
- **Canonical seed “signed package” process** in the data model. Seeds are ops/policy, not grammar. Alignment-as-claim already covers it.
- **`disclose(...)` k-anonymity over arbitrary claim sets** as a core primitive. No tractable general algorithm; you will ship purpose-scoped allowlists and redaction rules. Delete set-identifiability from the model; keep sensitivity tags + purpose gates.

---

4. **The seven open questions**

1. **Relocates.** Prop key fixes exact-string functional clash only inside one accepted closure. Problem becomes: policy-relative closures ⇒ incomparable agreement; higher-order claims don’t follow the key (fatal flaw). Closure maintenance is the new single point of semantic truth and is not merge-safe across acceptance policies.

2. **Wrong as global registry only.** Overlap must be per-predicate (or per-qualifier-type with predicate hooks). Global `valid_time` overlap is fine; `under_assumption` is not interval algebra. Registered set without per-predicate hooks will be wrong by month three.

3. **Two.** Retraction/supersession → act; fidelity/belief-about-world → proposition fiber (or interpretation id), not raw assertion. One sort guarantees category errors (`retract(assertion)` vs `retract(act)`).

4. **Does not hold on messy cases.** Classic: shared `local:x` for J. Smith (senator) + J. Smith (coach), 400 assertions, ~30% truly ambiguous. Nobody writes 400 `subject_is`. Without bulk “all P-assertions from source S → x1” reparsing, splits won’t happen; detector keeps fighting on `x`. Need *reparse rules* as claims (pattern → subject), not only per-assertion `subject_is`.

5. **Conservative-by-default; no general tractable k-anon** on open-domain claim graphs. Do: typed release profiles, mandatory suppressions, small closed world for demographics. “Compute identifiability of arbitrary candidate_set” is research, not v1.

6. **Missing for ZK later:** canonical field ordering and length-hiding; witness for “this hash is in the Merkle tree” vs “this proposition is supported under policy P” (policy is not in the log); nulls/open quals; claim_ref cycles in premises; which closure/acceptance was used. Hash tags alone are not enough for “private intentions shape aggregates.”

7. **Makes hard/impossible:** (a) non-monotonic “I no longer want this to shape agents” without residual inference from premise chains still in the log; (b) counterfactual / simulated self (“agent tries policy without committing”); (c) indexical now-self vs past-self as first-class without exploding `valid_time` on every preference; (d) “forget this source” as effective deletion under append-only + premise DAG; (e) real-time preference that is procedural (“interrupt if I go quiet”), not propositional.

---

5. **What breaks first at scale**

**10^6 assertions, one Postgres:**

Not raw inserts — **qualifier-overlap × functional checks × closure**. Naive “all functional pairs in an eq-class with overlapping quals” is nasty once a celebrity/org class absorbs 10^4 aliases and 10^5 assertions. Incremental sameAs (union-find) is fine; **materialized prop keys + overlap indexes** are mandatory or conflict detection becomes full batch. Second failure: recursive `premise` walks for audit (personal-KB path) without strict depth/cycle caps.

**Concrete shape that survives longer:**

```text
assertion(id, pred, pol, qual_bloom, raw_hash)  -- id = hash
edge_s(id, entity_raw)
entity_eq(rep, member, epoch)                   -- UF snapshot
prop_key(id, pred, pol, sub_rep, obj_rep, qual_norm_hash)
func_conflict = self-join prop_key on
  (pred functional ∧ sub_rep ∧ qual_overlap) ∧ obj disagree
```

**Merge of two 1e6 stores:**

Breaks on **acceptance-policy fork**, not byte union. Union of assertion tables is trivial (content-addressed). Then: sameAs edges union → eq-class collapse storms; one bad bridge `sameAs` fuses two large people-classes → O(n²) spurious functional conflicts (document notes this; at 1e6 it is an outage, not a warning). Prop keys must be recomputed for every touched class; agreement metrics reset. `subject_is` / beliefs from each side disagree about the same syntactic ids. **First operational break: conflict-detector flood + prop-key rebuild after identity bridge**, not disk.

**Different design for merge:** never auto-apply foreign `sameAs` into the conflict index. Quarantine external identity edges; prop keys stay on raw refs until a local, budgeted “promote bridge” job rebuilds only named classes. Cross-store agreement is a *report* over a chosen epoch, not a continuous global view.

---

**Alternative fragment (addresses fatal flaw):**

```text
// Layer 0 — stable
assertion  = hash(subj_raw, pred, obj_raw, pol, quals)   // commit only
claim_act  = hash(assertion, claimant, mode, evidence, t)

// Layer 4 — epoch E = (eq_version, accept_policy_id)
prop_key   = hash(rep_E(subj), pred, rep_E(obj), pol, qual_norm)
fiber(E, pk) -> {assertion_hash}   // all syntactic variants

// belief is NOT a row about Ha; it is a claim about (pk, E) OR a fold:
believe(agent, pk, E, v)   // addresses interpretation, published as
                           // act over interpretation_commit = hash(E, pk)
// retraction stays on claim_act hash
```

Without something shaped like `fiber` + interpretation commits, dimensional confidence and premise audit are theater on top of still-broken identity.


[stderr] 

Changes    +0 -0
Requests   1 Premium (2m 0s)
Tokens     ↑ 86.9k (55.9k cached) • ↓ 4.3k (1.8k reasoning)
Resume     copilot --resume=adea12ce-73e3-445b-8465-6ff31b077b20
