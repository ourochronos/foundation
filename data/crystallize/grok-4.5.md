Attacking the position directly — crystallization fails for structural reasons, not missing knobs.

● Create plan.md +3
  └ ~/.copilot/session-state/02f54f03-5bf8-4b17-9845-36ad55344223/plan.md

## Verdict

**The author is wrong.** Unopposed emergence was not the only failure mode. The three-force model still lacks a force that binds *meaning* independent of the corpus and the queries that already exist. Human gating on **structure** remains unavoidable; let acquisition fill values. Crystallization-from-day-one will measure its own self-consistency and call that learning.

---

### 1. Three-force model: not sufficient

**Merge fails first.** Then prune. Proliferate is fine as a valve; it is not the bug.

**Why merge fails:**
- “Same frame position + same filler type distribution + query-substitutable” is **co-occurrence geometry**, not synonymy. `sale.seller` and `employment.employer` both take PERSON in agent-ish positions; early sparse data will alias them.
- **Query-substitutability is circular.** The reasoner only sees queries you already run. Two slots that agree on today’s query bag and diverge on tomorrow’s are merged “correctly” by the instrument and wrong by the world. Merge optimizes for the frozen eval’s blind spots.
- **Distributional sameness under 0.15–0.27 recall is noise-dominated.** With most relations missed, type histograms are truncated samples. Merge will confidently join under-observed slots.

**Why prune fails second:**
- VoI is query-relative. A slot that never moves *current* answers is often the one you need for the next product question. Prune encodes **present query parochialism** as ontology truth.
- Under low recall, “never moves an answer” ≈ “never extracted,” not “semantically idle.” Prune deletes the incomplete, not the useless.

**Missing force:** a **type/role axiom layer that does not emerge** — human- or DL-authored constraints (domain/range, disjointness, cardinality, frame roles) that *veto* merges and protect rare slots. Without a non-emergent semantic governor, merge+prune are a clustering loop over a moving, undersampled graph. That is not crystallization; it is k-means with delete.

---

### 2. NELL drifted — mechanically

NELL’s loop: extract → promote by corpus redundancy + mutual exclusion/type checks that were themselves partly induced → use promotions as beliefs for further extraction. **Errors entered the belief store and became features for the next round.** Couplings: (a) promotion threshold too weak vs. polysemy and pattern drift, (b) no hard separation between *candidate lexicon* and *committed schema*, (c) downstream consumers (and internal consistency metrics) adapted to the polluted ontology, so “accuracy” on drifting categories looked stable.

**Frozen held-out set:** would have caught *some* of it, **late and partially**.
- Lag: **weeks to months**, not days. Early drift is local synonymy and sense split; held-out queries still hit on surface forms and high-frequency facts. Score falls only after enough aliases poison join paths or after category drift moves the answer set.
- What it would **not** catch early: systematic merge of near-roles (`athletePlaysFor` vs `worksFor`), sense collapse, and growth of latently wrong structure that still answers yesterday’s questions.

**What would have caught it sooner:**
1. **Committed-schema freeze + candidate quarantine** — nothing enters the reasoner’s schema without human or axiom gate; candidates never feed extraction features.
2. **Pairwise merge audit rate** — sample proposed `slot_sameAs` weekly against a fixed human panel; reject rate is the leading indicator.
3. **Contradiction/circuit-breaker trip rate per merge** (you already saw bad `sameAs` flood conflicts) — treat trip rate rise as stop-the-line, not as “need more corroboration.”
4. **Sense-probe battery**: fixed minimal pairs that *must* disagree (`seller`≠`buyer`, `employer`≠`employee`) scored after every merge batch.

NELL lacked (1) and (3) as hard stops; a held-out QA set alone is a lagging indicator.

---

### 3. Aliasing-not-fusion is not enough

Reversible rows ≠ reversible semantics.

**The alias graph becomes the drift object.**
- Transitive closure of defeasible `slot_sameAs` yields **soft fusion at query time**. Delete one edge and the component may stay glued via alternate paths. Reversibility is only real if you reason over *evidence-weighted* components with path provenance and can roll back a *batch* (you already learned incremental accept was wrong for entities — same applies harder to slots).
- **Downstream artifacts harden aliases:** cached query plans, embeddings, extracted triples keyed by slot id, user-facing facets, eval baselines “updated” to match. Row deletion does not unteach those.
- **Acceptance policy + corroboration + class-size breaker** prevent *one* failure mode (runaway entity fuse). They do not prevent **slow correct-looking collapse** of distinct roles that share filler types and never trip class-size.
- Alias graphs accrete **quasi-synonym cliques** (`seller`~`vendor`~`merchant`~`provider`~`party`). Each link is locally plausible; the clique is a new uncontrolled type. Drift moved from vocabulary cardinality to **component geometry**.

So: aliasing is necessary bookkeeping and insufficient control. Without an external role taxonomy that forbids certain edges, the graph is where drift lives.

---

### 4. Growth curve: weak discriminator

**Claimed signal:** sublinear distinct *roots* + rising alias rate ⇒ crystallization.

**Why it lies:**
- **Merge-happy explosion looks identical:** superlinear raw mints + aggressive aliasing ⇒ sublinear roots + high alias rate while meaning collapses. The curve measures **compression**, not **correct compression**.
- Under 0.041-scale noise and ~0.2 recall, early alias rate is dominated by **frequency bias** (everything merges into a few hub slots that appear in queries), not true synonymy.

**Horizon:** you will *see a curve* in **days**; you will not have a **trustworthy** crystallization signal before roughly:

- **≥ 5k–10k claims** (order-of-magnitude above the 316 blow-up), and  
- **≥ several hundred held-out queries** that were fixed *before* any merge policy ran, and  
- **stable alias accept rate + stable held-out score for ≥ 2–3 consecutive merge batches** with **human audit reject rate on merges &lt; ~5%**.

Until then, “sublinear + rising aliases” is consistent with both crystallization and **silent role collapse**. Do not green-light autonomy on the growth curve alone. Minimum falsifier: held-out score **and** merge-audit precision must rise together; curve without audit is vanity.

---

### 5. Sequencing: **strictly after runtime is proven**

Commit: **hand-seeded frames + proven pull-based runtime first. Crystallization only as a quarantined side process that cannot feed the reasoner until the runtime claim is closed.**

Why not “day one with separate measurements”:
- Emergence **contaminates** the runtime measurement. Slot ids, join keys, and VoI all move; you cannot attribute gains to pull-vs-push vs schema churn.
- “Emergence may not retrofit” is rhetoric. Quarantined candidate graphs retrofit cleanly; **committed** evolving schemas do not. Build crystallization offline against logs of a frozen schema. If it cannot win there, it must not sit on the write path on day one.
- Entity-identity lesson already said **confluent batch merge, not incremental**. That is a phased design. Same discipline for slots.

Cost of human structure gate: **rate of new *frames/roles***, not rate of facts. Facts stay uncapped (values). New roles: human bandwidth — typically **tens of well-typed slots per week**, not hundreds of LLM coinages per day. That cost is the product. Paying it avoids schema debt that no alias table amortizes.

---

### 6. Cheapest experiment that shows drift early (what NELL lacked)

**72-hour merge-poison test, fully quarantined:**

1. Freeze a seed schema S₀ and a held-out query set Q (answers labeled under S₀).  
2. Run extraction with **free minting** into a **candidate** store only — reasoner still uses S₀.  
3. Turn on automatic `slot_sameAs` proposals (distributional + query-subst on a *training* query bag disjoint from Q).  
4. **Batch-apply** accepts under the author’s policy into a shadow schema S₁ (alias graph only).  
5. Score daily:  
   - (a) Q accuracy under S₀ (control; must be flat),  
   - (b) Q accuracy under S₁ (alias expansion at query time),  
   - (c) **forced-discrimination probes**: 30–50 human pairs that must *not* alias,  
   - (d) merge-auditor precision on a random 50 proposals/day,  
   - (e) conflict-detector trip rate after each batch.  

**Early drift signature (within days, ≪ months):** (b) flat or down while (e) up; or (b) up on Q but (c)/(d) fail — i.e. **eval set gaming**. Growth curve sublinear + (d) low precision = compression drift, not crystallization.

**Kill criterion:** any batch with audit precision &lt; 0.9 on non-aliases, or any must-not-alias probe collapsed, or conflict flood per the entity-identity breaker pattern → stop; do not put crystallization on the write path.

NELL lacked: **quarantine, batch identity for schema, must-not-alias probes, and a kill switch tied to merge audit** — not merely a leaderboard.

---

## Bottom line

Proliferation was inevitable without pressure; **pressure without a non-emergent semantic governor produces measured drift**. Merge is the first broken force; the alias graph inherits the drift; held-out QA is lagging; growth curves cannot tell learning from collapse. **Human gating on slot structure is unavoidable.** Cap structure by hand; let values be messy and measured. Build crystallization only as a shadow experiment after the runtime is proven — and demand the 72-hour poison test before it ever writes a committed edge.


[stderr] 

Changes    +3 -0
Requests   1 Premium (59s)
Tokens     ↑ 51.5k (27.1k cached) • ↓ 2.4k (76 reasoning)
Resume     copilot --resume=02f54f03-5bf8-4b17-9845-36ad55344223
