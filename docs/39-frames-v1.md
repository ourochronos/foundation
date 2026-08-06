# Frames v1 — crystallization, roles, and what actually gets built

Supersedes the open questions in [37-frames-v0.md](37-frames-v0.md). Two panel
rounds (`data/concepts/`, `data/crystallize/`) and two design additions from the
author. **This is the document to resume from.**

---

## 1. State

- The extraction arc is closed and tagged **`extraction-arc-v1`** (exp66–exp89).
  Not deleted, not carried forward.
- Nothing of the new arc is built yet. This doc plus `37` is the whole design.
- Carried forward from the old arc: exp85's one-slot query harness, and the
  source verifier — **constrained to binary supported/unsupported**, because
  exp89 showed its STATED-vs-INFERABLE boundary is the unreliable part.

## 2. The measurement that constrains everything

**Recall 0.155–0.266 against a 0.041 noise floor**, with missed relations
verifying as stated at the same rate as recovered ones (gold independently
audited at exp89 and sound).

That number is not just motivation, it is a **binding constraint on the
crystallization design**, and it took a panel round to see why: at 0.2 recall
most slots are mostly empty, and **two empty slots are trivially substitutable**
— neither moves any answer. So the merge criterion has its highest
false-positive rate exactly where minting is most frequent.

**Consequence: crystallization cannot be evaluated until fill rates rise.** Not
for isolation reasons — because the signal does not exist yet. This is what
settles the sequencing argument, and it settles it on grounds neither the author
nor the panel stated.

## 3. Crystallization: the position, and the amendments it needs

**The author's position, retained**: the earlier explosion (316 claims → 510
concepts) was *unopposed* emergence, not emergence. Nothing there ever merged,
pruned, or scored a term. Three forces oppose it — proliferate freely, merge by
distributional evidence, prune by value-of-information — and human curation
should not be the rate limit on discovering new concepts.

**Panel verdict**: not simply wrong, but merge fails first and worst, and four
amendments are required.

| # | amendment | why |
|---|---|---|
| 1 | **A split force** — monitor within-alias filler divergence (KL, sliding window) after acceptance | without it merge is a ratchet: aliasing makes reversal *possible* and nothing ever *triggers* it |
| 2 | **Provenance tainting** — downstream decisions made while an alias was live must be invalidatable | deleting the row does not un-compute the VOI scores, later merges and prunes it licensed; reversal is otherwise cosmetic |
| 3 | **Shadow mode** — log every merge the policy *would* accept, score it, actuate only when shadow precision is measured | resolves the sequencing dispute; fable's "day one" and gpt's "strictly after" are this same mechanism named twice |
| 4 | **Canary pairs** — ~20 planted, superficially mergeable, known-distinct slot pairs with queries where merging flips the answer | trips in days rather than months; NELL had nothing like it |

**Never use an alias transitively without re-testing the closure.** Pairwise
plausible edges chain `a↔b↔c` where `a` and `c` fail substitutability — this is
the mechanism by which NELL walked predicates across semantic boundaries.

**Prune has the mirror defect and needs the same caution**: under low recall,
*"never moves an answer"* means *"never extracted"*. Prune deletes the
incomplete, not the useless.

### The signal that does NOT work

Slot-count growth curves. Killed three ways: **Heaps' law** gives sublinear
vocabulary growth in any text stream with zero consolidation, so sublinear is
the default rather than evidence; **malignant conflation is also sublinear**,
since everything collapsing into `is_related_to` shrinks the vocabulary; and a
**rising alias rate is what over-merging produces**, making it anti-evidence.

### The signals that do

- **Filler entropy per slot** — bounded under crystallization, drifting toward
  the global entity distribution under conflation ("the slots are eating
  everything"). The sharpest single discriminator.
- **Active slot count plateauing while claims grow linearly.**
- **Cohort survival** — for aliases accepted in week *t*, their later
  split/rollback rate and out-of-sample performance at 30 and 90 days.
- **Canary trips** — binary, immediate.

**Timescale, corrected**: canaries give days. Statistical crystallization
evidence needs 2,000–5,000 documents and 30–90 days. And the cost being avoided
was priced: reviewing 510 concepts at 2–5 min each is **17–43 reviewer-hours**.
Removing that limit converts it into latent schema corruption rather than
eliminating it.

## 4. Concept formalization — and why it resolves the merge objection

**The author's signal**: watch for a concept's slot structure to stop churning.

Made precise: **concept maturity is slot-set stability under increasing
instance count.** If a concept's instances grow 10× and its slot set does not
change, it has formalized. If slots keep appearing, it has not.

This is better than any global curve because it is per-concept and directly
interpretable — and it is immune to the Heaps'-law confound, which is a property
of aggregate vocabulary rather than of individual concepts.

**And it answers the panel's central objection.** Merge fails on young, thin
slots because they are trivially substitutable. Young thin slots are, by
definition, **not formalized**. So:

> **Merges actuate only between slots of formalized concepts.**

Immature concepts still accumulate merge *proposals* in shadow, which is where
the evidence for their eventual maturity comes from. The objection dissolves
without adding a mechanism — it is the author's own signal used as the gate.

## 5. Roles and polymorphism

**The author's requirement**: `PERSON` is itself a concept with slots; it also
*slots into* other types; not every use of `PERSON` uses the same slots; some
relations are aspects of a `PERSON` or of a subtype.

**Inheritance is the wrong mechanism** — it is rigid, and the requirement is
explicitly that different uses activate different slots, which inheritance
handles badly.

**Slot applicability is role-relative, not type-relative.** A concept carries a
full slot inventory; a frame activates a *subset* determined by the role the
concept plays in it. `PERSON`-as-seller and `PERSON`-as-employer are the same
concept with different active slot sets. That is polymorphism without a
hierarchy.

Prior art to build against rather than rediscover: **role modelling** (Bachman;
DCI), **facets** in frame systems, and especially **Pustejovsky's Generative
Lexicon**, whose qualia structure is exactly about a concept's aspects being
selectively activated by context ("fast car" vs "fast typist").

Two things fall out:

**It unifies with slot usefulness.** The active slot set for a query *is* the
useful-slot set. Role activation and value-of-information are the same
mechanism approached from either end.

**It sharpens merge.** A reviewer objected that `sale.seller` and
`employment.employer` both take `PERSON`, so type signatures will not
discriminate them. Under role-relative slots the signature is not `PERSON` but
`PERSON`-as-seller versus `PERSON`-as-employer, which activate different slot
subsets — strictly more discriminating, and it reduces exactly the false merges
the panel predicted.

## 6. Store versus log

**Schema evolution is append-only log; the current schema is a fold over it.**

Everything about how the schema moved — mints, alias proposals, actuations,
prunes, splits, canary trips — goes to the log. The store holds only the current
schema and the claims. The split is not an optimisation; it is what makes three
required properties possible:

- **Auditability** — the log *is* the audit trail, and it is where filler
  entropy, cohort survival and growth curves are computed. The instrument lives
  in the log, not the store.
- **Reversibility** — replay the log without a bad alias to get the schema that
  should have existed. This is what amendment 2 (provenance tainting) actually
  requires: deterministic recomputation from a pre-alias state.
- **Cheapness** — early evolution is high-volume and mostly noise. None of it
  needs to be queryable.

It also gives fable's **time-slice replay** for free: re-answer frozen day-1
queries under the day-*N* schema; answers must not change.

## 7. What gets built, in order

1. **Frame/slot core + the one-slot query harness.** ~20 hand-authored frames.
   Roles as slot-subset activation from the start (§5) — it does not retrofit.
2. **The runtime experiment.** Multi-hop QA (MuSiQue / 2WikiMultihopQA, ~100
   questions), loop: reason → fault → one-slot query → **verify** → continue,
   with ~30 deliberately unanswerable questions.
   **Kill criteria, registered**: slot-conditioned recall on required hops
   **< 0.5** kills the representation-mismatch hypothesis; confident fills on
   **more than half** the unanswerable slots means verification is not working
   and the fault machinery is decoration.
3. **Crystallization in shadow, from day one** — the evolution log, canary
   pairs, filler-entropy monitoring, formalization tracking. Logged and scored,
   **never actuating**, until §2's fill-rate constraint is met.
4. **Actuation**, gated on formalized concepts only (§4), once shadow precision
   has been measured.

## 8. Open questions

- What counts as "formalized"? The stability threshold and the instance-count
  multiplier are unset, and picking them post-hoc would be fitting the metric to
  the outcome. Register them before step 3.
- Does role-relative activation survive contact with real frames, or do roles
  proliferate the way slots did?
- The verifier is the load-bearing component of the whole fault mechanism and
  its measured agreement with a second judge was only ~46%. That needs its own
  test before step 2 relies on it.
