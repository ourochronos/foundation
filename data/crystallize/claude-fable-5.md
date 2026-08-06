**1. Is the three-force model sufficient? No — merge fails first, and a fourth force (split) is missing.**

The merge test is circular and starved. "Substitutable in queries without changing answers" is evaluated by the reasoner over a KB built at 0.155–0.266 recall. At that fill rate most slots are mostly holes, and two sparse slots are *trivially* substitutable — neither moves any answer. Your merge criterion has its highest false-positive rate exactly where minting is most frequent: young, thin slots. Prune has the mirror defect: VOI against the *current query workload* crystallizes the schema to the queries you happen to ask, silently killing rare-but-critical slots.

The missing force is **split**: nothing detects that an accepted alias conflates two distributions *after* acceptance. Aliasing makes reversal mechanically possible; no force ever triggers it. Add post-merge monitoring of within-alias filler-distribution divergence, or merge is a ratchet.

**2. NELL, mechanically.** Coupled bootstrapping: promoted instances became training evidence for the extractors that promote instances. Errors compounded because the *category definition was the mutable thing* — each bad promotion shifted what the category meant, which licensed the next bad promotion. A frozen aggregate held-out set would have caught it **only after the damage**: drift in NELL was per-category, and one rotting category barely moves aggregate F1. What catches it sooner: **per-slot held-out slices** plus tracking the type-distribution of *newly* promoted fillers against the slot's historical fillers (KL over a sliding window). The filler distribution moves before the answers do.

**3. Aliasing is not enough.** Two failure modes. (a) **Transitive closure**: pairwise-plausible edges chain a↔b↔c where a and c fail the substitutability test; the breaker is class-size, but the criterion is pairwise while the harm is closure-wide. Never use an alias transitively without re-testing the closure. (b) **Epistemic irreversibility**: deleting the row doesn't un-compute the VOI scores, subsequent merges, and prune decisions made *while the alias was live*. Without provenance tainting of downstream decisions, reversal is cosmetic. Your own arc already measured this — confluent batch merge was required because incremental accept was order-dependent. Same disease, one level up.

**4. Growth curve — and a trap the brief walks into.** Sublinear concept growth is **not** evidence of crystallization: any natural text stream gives Heaps-law sublinear vocabulary growth (~n^0.5) with zero consolidation. The superlinear 510/316 result was anomalous; regression to sublinear proves nothing. The real signals: (i) alias rate — fraction of newly minted slots absorbed within k documents — *rising*; (ii) **active** (non-aliased, non-pruned) slot count plateauing while claims grow linearly. Horizon: at ~1.6 concepts/claim you need roughly 10× the prior corpus — 3,000–5,000 claims, order 2,000+ documents — before per-slot filler statistics clear a 0.041-scale noise floor. Days-not-months is achievable only if ingestion runs at hundreds of docs/day.

**5. Sequencing: day one. Committed.** The author is right that emergence doesn't retrofit — but for an unglamorous reason: the *provenance and alias-aware query machinery* must be load-bearing in the runtime's design, and the frozen eval set is only frozen if you collect it before the schema ever moves. Build crystallization from day one, but run **merge in shadow mode** initially: log every merge the policy *would* accept, score it against the frozen set, flip actuation on only when shadow precision is measured. That's still day-one construction; it's not phasing.

**6. Cheapest early drift detector: canary pairs.** Plant ~20 synthetic slot pairs that are superficially mergeable — same frame position, overlapping filler types — but known-distinct, with held-out queries where merging flips the answer. The moment the policy aliases a canary, consolidation pressure has exceeded evidence. Cost: hours to author, zero runtime overhead, signal in days. Pair it with the per-slot KL monitor from Q2 and a **time-slice replay**: re-answer frozen queries about day-1 documents under the day-N schema; those answers must not change. NELL had none of these; all three are cheap.

**Bottom line:** the author is not simply wrong, and human gating is not required — but as specified, his merge force will fire confidently on sparse slots where its evidence is weakest, and nothing ever un-merges. Add split pressure, taint provenance, shadow-mode the merges, plant canaries. With those four amendments this is worth building; without them it's the amnesiac accountant with an eraser he never uses.


[stderr] 

Changes    +0 -0
Requests   1 Premium (1m 1s)
Tokens     ↑ 36.2k (36.2k written) • ↓ 3.6k (2.0k reasoning)
Resume     copilot --resume=bedaea7d-6d88-4035-a13a-e4d7db5d47b4
