No tools needed — this is a judgment call. Positions below.

## 1. Is slot instantiation the right primitive?

Yes — but the acquisition bottleneck is not dissolved, it relocates. LLMs make slot *filling* nearly free; what remains expensive is **frame invocation**: deciding which frame applies to which text or query. That is the same recall problem that pinned you at 0.155–0.266, reappearing one level up. If frame selection is done by embedding similarity or blanket prompting, you'll hit the same wall and this pivot fails for the same reason with a new vocabulary.

The saving move is that demand paging changes the denominator: you never need to invoke frames for the whole corpus, only for the query in hand. That's why the pivot is worth trying — not because the representation is better, but because pull-based operation stops scoring you against every gold triple you didn't ask about.

Also flag this: recovered gold verifies STATED at only 0.636. That means either the verifier is weak or ~36% of your gold is noise. If it's the gold, part of the "recall wall" is an evaluation artifact — gold triples are one canonicalization among many. Check this before attributing everything to representation mismatch.

## 2. The fault taxonomy

As an **ex-ante classifier it is useless**: distinguishing "resolvable externally" from "unresolvable" requires knowing the answer exists before searching, which is undecidable. Case 4 swallows cases 2 and 3.

As **policy it is fine**, if you make it operational: "unresolvable" = "not resolved within budget k attempts," a post-hoc ledger entry, not a prediction. The real failure mode nobody in the brief names: LLMs almost never say "I can't" — they fill. Case 3 will collapse to zero and refusal will never fire unless the fill is *verified against source text* before the slot closes. Fault-as-acquisition works only with a verifier in the loop; without one it's hallucination-as-acquisition.

## 3. Completeness guarantee

It is the frame problem restated, with one genuine advance: **known-unknowns become enumerable**. "Slot `seller` is open" is actionable. But the *number* — filled/total — is fake precision, because slot counts depend on frame granularity, which is arbitrary (is `sale` 3 slots or 9?). Keep "which slots are open"; discard the completeness ratio entirely. Anyone who puts filled/total on a dashboard will optimize frame coarseness, not knowledge.

## 4. Prior art

- **Demand paging = SLD resolution with tabling.** Prolog discovered "reason until unresolved, fetch, continue" fifty years ago. Fault-as-fetch is a tabled goal.
- **Fault sorting = open preconditions in POCL planning** (SNLP/UCPOP): threats, resolvable flaws, unresolvable flaws — the taxonomy is nearly isomorphic.
- **Acquisition agenda = NELL** (Carlson & Mitchell 2010) — coupled learning that turned gaps into crawl targets. It ran for years and drifted. Read its postmortems before building.
- **Slot filling = TAC KBP Slot Filling track**, a decade of shared tasks that plateaued around F1 0.35. Your 0.463 precision on one run is consistent with that ceiling, not above it.
- Closure structures = ATMS/truth maintenance; typed slots = description logics.

The white space is **narrow but real**: nobody has coupled query-driven inference faults to LLM-executed, slot-typed acquisition *with verification against a concrete need*. NELL lacked a reasoner pulling on it; KBP lacked a consumer. The consumer is the novelty. Everything else is reinvention — build it as reinvention, deliberately, and steal the failure analyses.

## 5. The killer experiment

Multi-hop QA (MuSiQue or 2WikiMultihopQA, ~100 questions), **~20 hand-authored frames**, small local model. Loop: reason → fault → one-slot query against the corpus (exp85 machinery) → verify fill is STATED → continue. Include ~30 questions whose answers are *deliberately absent* from the corpus.

Measure two things:
1. **Slot-conditioned recall on required hops.** Kill criterion: if it isn't ≥0.5 — decisively above the 0.2 wall — the representation-mismatch hypothesis is false and the whole pivot dies. This is the direct test of the brief's central claim.
2. **Fault-classification confusion on the absent-answer questions.** If the system claims "resolvable externally" and produces a fill for >half of unanswerable slots, the taxonomy is dead in practice per Q2.

Hand-authoring the frames is the point: it isolates the runtime claim from the acquisition claim. Test on-demand frame *acquisition* only after the runtime survives. One person, one GPU, under a week.

## 6. What to abandon

- **All four discourse corpora.** Zero corroboration means they are the wrong substrate for this task, full stop. Keep only multi-source news.
- **Corroboration as a signal.** 41 triples across everything. It's dead; stop measuring it.
- **REBEL and every pretrained-extractor arm**, the calibration and hybrid-filtering work, and the 29k claim store. Push extraction has now failed twice with numbers.
- **The three existing closure structures.** Do not unify them — that "partial machinery exists" line in the brief is sunk cost wearing a disguise. Build the dependency closure fresh from frame declarations; three heterogeneous closures retrofitted into one operator will cost more than a clean rebuild.
- **Keep exactly two artifacts**: the exp85 one-slot query harness and the STATED verifier (after auditing it against the 0.636 anomaly). Those are the only pieces the new architecture actually consumes.


[stderr] 

Changes    +0 -0
Requests   1 Premium (1m 5s)
Tokens     ↑ 36.3k (36.3k written) • ↓ 3.9k (1.9k reasoning)
Resume     copilot --resume=5696fa82-2fdb-4658-a08f-e90babe07a6f
