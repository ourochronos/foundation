# Writeup outline — what we can honestly claim (2026-07-29)

Working title: **What survives contact with a real corpus: reindex-free
knowledge, honest refusal, and the conditions under which each holds.**

The strongest material here is not a headline number. It is that most of the
positive results carry a **scope condition** that was discovered by
measurement rather than assumed, and that several of our own conclusions were
overturned by our own later experiments. That is the paper.

---

## The claims table

Each row: the claim, the **condition it holds under**, the number, and what
would falsify it. A claim without its condition is not publishable.

| # | Claim | Holds under | Number | Falsified by |
|---|---|---|---|---|
| 1 | The store is **mechanically** reindex-free: appending mutates no fitted artifact | verified byte-identical (basis, coordinates, head weights) across an append (D131) | fingerprints unchanged | — demonstrated, not inferred |
| 1b | At a 25% append ratio the new-**entity** penalty is **under 0.10** and the new-**relation** penalty is **over 0.15**, for the parametric head | parametric head; 25% append ratio; ratio-dependence untested | entity +0.058, relation +0.191, depth-2 +0.249; retrieval +0.247 / +0.771 (D131) | **falsified if** either penalty crosses its bound at this ratio, or the ordering (entity < relation) reverses at any ratio | retrieval is far worse (+0.771 on new relations); refusal does not survive appending (0.748 answered-anyway vs 0.558 rebuilt) |
| 1c | **The store learns**, and revision is two operations: editing a fact alone revises **0.469** of previously-correct answers, editing it *and* supplying the edges its new target needs revises **0.733** | same cases, same frozen head, within-experiment comparison | addition 432/432 conditional on prior honest refusal (D133); revision 0.469 → **0.733**, breakage 0.274 → **0.077**, staleness 0.002 → 0.014 (D146) | **falsified if** supplying downstream edges fails to reduce breakage — it reduced it by 0.197 |
| 1d | The store **revises** rather than going stale: after a superseding edit it does not keep asserting the old fact | edits applied through the real `kb.edit()` path; conditional on having answered correctly before | **stale 0.002**; revision 0.459; failure is refusal (0.348) and wrong answers (0.190), not staleness (D141) | single-edit cases revise at only 0.235 because editing one link leaves the chain expecting the old target's onward edges |
| 2 | Composition generalises to relation pairs never seen composed | measured **at 61 relations**; fails at 5; **the threshold in between is untested** — "≥60" is interpolation, not measurement. Pair-clean holdout; parity at depth 2 only | depth 2: 0.925 vs 0.913 trained. Depth 3: 0.626 vs 0.683 — not parity (D123) | small vocabularies: fails at 5 relations (D112); pair-clean holdout unbuildable there (D122) |
| 3 | Order and depth can come from the store rather than from learning | measured on **two corpora, one walker formulation** — not general | held-out compositions 0.534 → 0.912 (D117) | untested outside this walker; isolates neither depth nor order learning |
| 4 | Depth extrapolates without depth-specific training, for *answering* | answering only | 3-hop **0.849** with no 3-hop in training (D119) | *refusal* does not extrapolate (D120) |
| 5 | The system refuses rather than guessing | **chain-break** unanswerables, **sparse** stores | 0.970 refusal (D118) — **this population is unrepresentative**, see 5b | dense stores 0.72–0.98 (D123/D124); and the simple case was never in it |
| 5b | On the **mixed** benchmark, refusal needs the answer-type gate | law #9 population: chain_break + not_applicable + absent_entity | not_applicable **0.050 → 0.693** with the gate; chain_break 0.337 → 0.650; answerable wrongness 0.118 → 0.045; **correct** falls 0.110 while **total answered** falls 0.183 — the extra 0.073 removed were wrong answers (D134) | probe ceiling is 0.965, so 0.693 is threshold placement, not the limit |
| 6 | Refusal quality falls as store density rises | correlation, not a demonstrated mechanism | refusal vs branching −0.79 to −0.91 (D124) | "ambiguity is the mechanism" is an interpretation of the gain overlap (1.198 vs 1.390) |
| 7 | Compression buys generalisation and costs precision | descriptive across three experiments; none tests both halves | novel relations 0.742/0.293 (D125); depth-4 0.149/0.289 (D126); phrasing 0.313/0.149 (D128) | a representation winning on both axes |
| 8 | Retrieval beats a parametric head by **data-efficiency**, not by preserving information the head destroys | depth-1 relation identification, known relations; gap is alias-supply dependent | **within one population** (exp43, 34 relations) the gap closes 0.230 → 0.042 from 2 to 10 aliases; **on a second** (exp49, 56 relations) no head config at 2 aliases reached 1-NN — best 0.691 vs 0.925 (D148, D139) | **falsified if** a head at 2 aliases reaches 1-NN — none did at 512–2048 hidden across three objectives; and on **new** relations retrieval collapses to 0.229 vs the head's 0.782 (D131) |

| 11 | Claim adjudication itself is noisy | two independent raters | Cohen's kappa **+0.333** (D140) | single-rater verdicts in D130/D135 were correspondingly noisier than they appeared |

| 12 | Entities are free for the head and expensive for retrieval | subjects held out of training questions; claims remain in the store | head −0.029 (d1) / −0.010 (d2); retrieval −0.328 / −0.288 (D149) | **falsified if** the head's gap exceeds 0.05 on any population — it did not on three |

## Machine-readable claims (SINGLE SOURCE OF TRUTH)

`scripts/adjudicate.py` reads this block directly. The prose table
above is a rendering of it. D150 recorded why: the adjudicator used
to keep its own copy, the two drifted, and an entry asserted an
adjudication that never happened. Two artifacts holding the same
claims will diverge, and the divergence is invisible because both
look current.

```json
[
 {
  "claim": "The store is MECHANICALLY reindex-free: appending new content mutates no fitted artifact.",
  "scope": "verified byte-identical basis, coordinates and head weights across an append",
  "src": [
   "results/exp36_append.json",
   [
    "mechanical_check_passed",
    "fingerprints",
    "n_new_relations",
    "n_new_subjects"
   ]
  ]
 },
 {
  "claim": "Appending is behaviourally near-free for new ENTITIES but not for new RELATIONS.",
  "scope": "PARAMETRIC HEAD ONLY, against a full rebuild at one freeze/append ratio: head new entity +0.058, new relation +0.191. Retrieval is worse on both (+0.247, +0.771)",
  "src": [
   "results/exp36_append.json",
   [
    "results"
   ]
  ]
 },
 {
  "claim": "The store LEARNS: of the questions it properly REFUSED before an update, 432 of 432 (1.000) are answered correctly after it. Separately, it properly refused only 432 of the 1179 it could not answer (0.366); 21 of the 1200 were already answerable. Both figures derive from the transition matrix.",
  "scope": "artifacts are frozen by construction in this experiment but are FINGERPRINT-VERIFIED only in D131's separate append run; the 1.000 is conditional on prior honest refusal",
  "src": [
   "results/exp38_update.json",
   [
    "transition_flip",
    "learned_rate",
    "learned_ci95",
    "regression_stays",
    "control_never",
    "n_update_pairs"
   ]
  ],
  "extra": [
   [
    "results/exp36_append.json",
    [
     "mechanical_check_passed",
     "fingerprints"
    ]
   ]
  ]
 },
 {
  "claim": "The store REVISES rather than going stale: after a superseding edit it does not keep asserting the old fact. Staleness is 0.002; revision is 0.459; the failure is refusal and wrong answers, not staleness.",
  "scope": "edits applied through the real kb.edit() path; conditional on having answered correctly before the edit; single-edit cases revise at only 0.235",
  "src": [
   "results/exp44_supersession.json",
   [
    "matrix_all",
    "revision_rate_all",
    "matrix_single",
    "revision_rate_single",
    "matrix_multi",
    "revision_rate_multi",
    "supersession_sanity",
    "edits_applied"
   ]
  ]
 },
 {
  "claim": "Composition generalises to relation pairs never seen composed, at parity with trained pairs at depth 2.",
  "scope": "measured AT 61 relations; fails at 5; the threshold in between is untested, so any '>=60' is interpolation. Pair-clean holdout; parity at depth 2 only, degrading at depth 3 (0.626 vs 0.683)",
  "src": [
   "results/exp29_wikiwalker.json",
   [
    "n_relations",
    "n_pairs",
    "n_held_pairs",
    "results",
    "controls",
    "branching"
   ]
  ],
  "extra": [
   [
    "results/exp18_compose.json",
    [
     "ordering",
     "scope"
    ]
   ]
  ]
 },
 {
  "claim": "Depth extrapolates without depth-specific training for ANSWERING (3-hop 0.849 with no 3-hop trained).",
  "scope": "answering only; refusal does not extrapolate",
  "src": [
   "results/exp26_threehop.json",
   [
    "zero_shot_depth",
    "trained_on_3hop"
   ]
  ]
 },
 {
  "claim": "On a MIXED unanswerable benchmark the answer-type gate lifts not-applicable refusal from 0.050 to 0.693 and cuts answerable wrongness from 0.118 to 0.045.",
  "scope": "depth-1 CORRECT falls 0.110 while TOTAL answered falls 0.183 (the extra 0.073 were wrong answers); depth-2 wrongness 0.175->0.102; probe ceiling 0.965 so 0.693 is threshold placement",
  "src": [
   "results/exp39_typegate.json",
   [
    "results",
    "not_applicable_refusal",
    "aurc_mixed",
    "type_fit_threshold"
   ]
  ]
 },
 {
  "claim": "Retrieval beats a parametric head by DATA-EFFICIENCY, not by preserving information the head destroys. Within one population the gap closes from 0.230 at 2 aliases to 0.042 at 10; and on a second population no head configuration at 2 aliases (512-2048 hidden, three objectives) reached 1-NN.",
  "scope": "the CURVE is exp43's 34-relation population; the no-configuration-closes-it result is exp49's 56-relation population — two populations, two roles, not one curve. FALSIFIED IF a head at 2 aliases reaches 1-NN, or the gap fails to shrink with alias supply",
  "src": [
   "results/exp49_fair_head.json",
   [
    "one_nn",
    "d129_head",
    "grid",
    "epoch_sweep",
    "best_head",
    "gap_to_1nn"
   ]
  ],
  "extra": [
   [
    "results/exp43_scaling.json",
    [
     "alias_curve"
    ]
   ],
   [
    "results/exp36_append.json",
    [
     "results"
    ]
   ]
  ]
 },
 {
  "claim": "Entities are free for the parametric head and expensive for retrieval: subjects held out of training score 0.766 against seen subjects' 0.795 at depth 1, while retrieval drops from 0.854 to 0.526.",
  "scope": "subjects held out of TRAINING QUESTIONS only; their claims remain in the store and stay walkable. FALSIFIED IF the head's gap exceeds 0.05 on any population — it did not on three",
  "src": [
   "results/exp50_entity.json",
   [
    "results",
    "gaps",
    "largest_gap",
    "n_held_subjects"
   ]
  ]
 },
 {
  "claim": "Revision is two operations: editing a fact alone revises 0.469 of previously-correct answers with 0.274 breakage; editing it AND supplying the edges its new target needs revises 0.733 with 0.077.",
  "scope": "same cases, same frozen head, within-experiment comparison. FALSIFIED IF supplying downstream edges fails to reduce breakage — it reduced it by 0.197",
  "src": [
   "results/exp46_revision_fix.json",
   [
    "conditions",
    "verdict"
   ]
  ]
 }
]
```

## Predictions the paper makes but has not tested

Stated separately from the claims because they are falsifiable and **unfalsified
— we simply have not run them**. Putting them among the results would be the
hedging failure D145 caught.

- **A third store's p25-of-within-relation-fit will order it correctly for
  range tightness** relative to wiki (0.562) and MQuAKE (0.778), and a
  threshold moved onto it will cost coverage. Two stores cannot establish
  this: the bound we quoted (>0.30 coverage cost) was read off the same two
  stores it describes, which is a description rather than a falsifier. Three
  adversarial raters called the claim unfalsifiable **after** we sharpened it
  once, and they were right (D142, D145, D150).

## What we cannot claim

Stated as prominently as the claims, because these are the ones a reader
would otherwise assume:

- **Not free-form language.** Every question is templated. Phrasing
  robustness is the dominant unsolved failure: an unseen alias for a *known*
  relation costs −0.719 (D127), and neither representation fixes it (D128).
- **Not depth-unbounded in practice.** Coverage decays 0.934 → 0.693 → 0.289
  from depth 2 to 4, and on a dense store the wrong-rate *grows* with depth
  (D126).
- ~~Not entity generalisation.~~ **Now tested and it holds for the head**:
  subjects held out of training score 0.766 against seen subjects' 0.795 at
  depth 1 (gap −0.029). It does *not* hold for retrieval (−0.328), because a
  question's text carries the entity name and a new entity moves the query
  away from its bank neighbours (D149).
- **Not a free lunch on refusal.** Two principled fixes moved along the
  precision/coverage frontier without shifting it (D124).
- **Not honest by default.** Without the answer-type gate the walker
  confabulates on 0.623 of what it cannot answer, and answers 0.950 of
  not-applicable questions (D133/D134). Honesty is a component that had to
  be added, not a property the design provided.
- **Not measured on a representative refusal population until D134.** Every
  refusal number D118–D132 used chain-break unanswerables only, which
  overstated selective prediction ~3.6× (law #9).

## Method contributions (arguably the most reusable part)

**Report refusal as a risk–coverage curve, not a rate.** This is a
recommendation about reporting rather than an empirical claim — D145's
adversarial pass correctly observed that nothing could contradict it — so it
belongs here and not in the claims table. The substance behind it: on the
mixed benchmark AURC is 0.4734 where the chain-break-only benchmark gave
0.1322, so a single refusal rate at a chosen threshold overstated selective
prediction ~3.6× (D134). Every refusal figure this project published before
that correction was a point on an unreported curve.


Eight audit laws, each earned by a wrong verdict we published to ourselves
first. The last three came from this arc:

- **#6** A refusal threshold cannot be calibrated on a population that does
  not exhibit the failure (D111).
- **#7** You cannot measure refusal without unanswerable questions — a
  store-derived benchmark is answerable by construction, so every refusal
  metric on it is vacuous (D118). Grade them by *failure mode*, not just
  presence (D119).
- **#8** A length check is not an alignment check. Hash-order-dependent set
  iteration silently misaligned cached embeddings and produced a conclusion
  we had to withdraw (D119 → D120).

Plus **D122's rule**: a shape-level holdout is not a composition holdout;
report pair-cleanliness alongside every composition number. This is what made
D123 possible and what invalidated the depth-3 numbers before it.

## Corrections we made to ourselves

Worth a short section, because it is unusual and it is the evidence that the
scope conditions are real rather than decorative:

- D112 "composition is memorised" → **overturned** by D123 (vocabulary-size
  artifact).
- D119 "no threshold separates, the fix is architectural" → **withdrawn** by
  D120 (an alignment bug).
- D125 "make the anchor basis the default" → **qualified** by D126 (wrong
  default for depth).
- D118's ~0.000-wrong → **rescoped** to sparse stores by D123/D124.
- D127's "vocabulary pretraining is the highest-value fix" → **refuted** by
  D128 one experiment later.

## Structure

1. The reindex-free store and why appending is the hard part
2. The walker: order and depth from the store, not the query
3. Scaling: what changes between 5 and 61 relations (the vocabulary hazard)
4. Refusal: how to measure it, and why density bounds it
5. The compression trade-off as a single axis
6. Negative results and corrections
7. Limits: phrasing, entities, free-form language

## Before any of this is written

- Run `A→A` at 61 relations (`docs/17` gap) — the last untested structural
  claim from the five-relation era.
- Decide whether the AI corpus appears at all. It supplies the strongest
  safety numbers and they are the ones that do not generalise; including them
  without the density condition would be the single most misleading thing in
  the paper.
- Fix a frozen artifact set: one commit, one results directory, one table
  generator, so every number in the text traces to a `run_manifest`.
