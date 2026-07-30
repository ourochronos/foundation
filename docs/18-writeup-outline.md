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
| 1b | At a 25% append ratio the new-**entity** penalty is **under 0.10** and the new-**relation** penalty is **over 0.15**, for the parametric head — **at depth 1 only** | parametric head; 25% append ratio; ratio-dependence untested; **depth-1 figures do not carry to depth 2** | entity +0.058, relation +0.191 at depth 1; **depth-2 +0.249**, where "near-free" fails outright; retrieval +0.247 / +0.771 / +0.666 (D131) | **falsified if** either depth-1 penalty crosses its bound at this ratio, the ordering (entity < relation) reverses, or the depth-2 penalty is under 0.10 |
| 1c | **The store learns**: questions it properly refused before an update are answered correctly after it | conditional on prior honest refusal; it refused only 0.366 of what it could not answer | addition **432/432** (1.000); the 0.366 and the 21 already-answerable both come off the transition matrix (D133) | **falsified if** any of the 432 stays refused or turns wrong after the update |
| 1d | The store **revises** rather than going stale: after a superseding edit it **almost never** keeps asserting the old fact | edits applied through the real `kb.edit()` path; conditional on having answered correctly before | **stale 0.002** — 1 of 431, not zero; revision 0.459; failure is refusal (0.348) and wrong answers (0.190), not staleness (D141) | **falsified if** staleness exceeds refusal or wrong-answering as a failure mode; single-edit cases revise at only 0.235 because editing one link leaves the chain expecting the old target's onward edges |
| 1e | Revision is **two operations**: editing a fact alone revises **0.469** of previously-correct answers, editing it *and* supplying the edges its new target needs revises **0.733** | same cases, same frozen head, within-experiment comparison | revision 0.469 → **0.733**, breakage 0.274 → **0.077**, staleness 0.002 → 0.014 (D146) | **falsified if** supplying downstream edges fails to reduce breakage — it reduced it by 0.197 |
| 2 | Composition generalises to relation pairs never seen composed | measured **at 61 relations**; the contrast is a 5-relation world where held-out composition *order* transfers at chance; **the threshold in between is untested** — "≥60" is interpolation. Pair-clean holdout | depth 2: held-out **0.925** vs trained 0.913 — **+0.011**, inside a ±0.02 band and on the better side. Depth 3: 0.626 vs 0.683, a gap of 0.057 (D123) | **falsified if** the depth-2 gap exceeds 0.02 in either direction. "Parity" is stated as a margin because it carried no threshold until a rater asked for one (D153) |
| 3 | Order and depth can come from the store rather than from learning | **one corpus, one walker formulation** — not general | held-out compositions 0.534 → 0.912 (D117); **the 0.534 is pasted from exp18, not computed in-run** | **falsified if** *any* planner formulation reaches 0.912 on the same pairs — three raters unanimously flagged that only one weak planner was ever compared (D154) |
| 4 | Depth extrapolates without depth-specific training, for *answering* — **at 3 hops, and not beyond** | answering only; **one** depth measured zero-shot | 3-hop **0.849** with no 3-hop in training, vs 0.961 trained (D119) | *refusal* does not extrapolate (D120); and **depth 4 refutes it** — 0.289 raw / 0.149 basis (D126) |
| 5b | On the **mixed** benchmark, refusal needs the answer-type gate | law #9 population: chain_break + not_applicable + absent_entity | not_applicable **0.050 → 0.693** with the gate; chain_break 0.337 → 0.650; **depth-1** answerable wrongness 0.118 → 0.045 and **depth-2** 0.175 → 0.102; **correct** falls 0.110 while **total answered** falls 0.183 — the extra 0.073 removed were wrong answers (D134) | probe ceiling is 0.965, so 0.693 is threshold placement, not the limit |
| 6 | Refusal quality falls as store density rises | correlation, not a demonstrated mechanism | refusal vs branching **−0.79 / −0.83 / −0.91** across three populations (D124) | **falsified if** the correlation vanishes where branching varies and confusability does not — a test D137's revisit (a) already owed and two raters independently named (D154) |
| 7 | Compression buys generalisation and costs precision | descriptive across three experiments — **the same corpus**, separately tuned thresholds (0.6 / own / 0.4); none tests both halves | novel relations 0.293 → **0.742** (D125); phrasing 0.149 → **0.313** at wrongness 0.036 → 0.245 (D128); depth-4 0.289 → **0.149** (D126) | **falsified if** a representation wins both axes under **one** threshold protocol — unanimously flagged as a post-hoc pattern (D154) |
| 8 | Alias supply explains **most** of retrieval's advantage over a parametric head — **and not all of it** | depth-1 relation identification, known relations; the plateau is measured on 8 high-alias relations only | gap 0.229 → 0.042 over 2→10 aliases (exp43, 34 rel); then **flat at ≈0.09** over 10→18 (exp51, 8 rel: 0.087 → 0.091, tail slope +0.0015/alias vs noise ±0.026); no head config reached 1-NN at 2 aliases — 0.691 vs 0.925 (exp49) (D139, D148, **D155**) | **falsified if** the gap resumes falling past 18 aliases, or a head reaches 1-NN at any supply. *"Not a permanent loss of information" was withdrawn at D155 when this falsifier was run — the head plateaus at 0.892 while 1-NN sits at 0.975 from two aliases onward.* |

| 11* | Claim adjudication itself is noisy | two independent raters | Cohen's kappa **+0.333** (D140) | single-rater verdicts in D130/D135 were correspondingly noisier than they appeared |

| 12 | Entities are free for the head and expensive for retrieval | subjects held out of training questions; claims remain in the store | head −0.029 (d1) / −0.010 (d2) / +0.001 (na); retrieval −0.328 / −0.288 (D149) | **falsified if** the head's gap exceeds 0.05 on any of the three *question* populations in this corpus — it did not on any; a second **corpus** was not tested |

**Row 5 was deleted at D156, and that is the point of the table.** It read
*"the system refuses rather than guessing — 5821/6000 = 0.970"*, and two of
three adversarial raters called it **UNFALSIFIABLE**: the scope restricted it
to chain-break unanswerables on a sparse store, a population where refusal
could not have come out low, and then absorbed its failure on the mixed
benchmark by pointing at row 5b. They were right, and the scope was ours —
it conceded the population was unrepresentative and kept the claim anyway
"because it is what the earlier claim rested on". A claim retained for
historical reasons with its failure absorbed into its own scope is the
hedging failure the adversarial prompt exists to catch. The *fact* survives
in the narrative: D118's 0.970 came from a population that could not have
produced a low number, which is exactly why the mixed benchmark (law #9)
had to be built and why row 5b superseded it.

`*` **row 11 is in the paper and has never been adjudicated, deliberately.**
Its evidence is the behaviour of the adjudicators themselves, so judging it
in the same run that generates its evidence would be circular. It is due to
be judged in a later round against the frozen artifact this round produces,
and until then it carries the mark rather than an implied clean bill.

## Machine-readable claims (SINGLE SOURCE OF TRUTH)

`scripts/adjudicate.py` reads this block directly, and every claim's
`row` names the table row above that it renders. D150 recorded why the
block exists: the adjudicator used to keep its own copy, the two
drifted, and an entry asserted an adjudication that never happened.
Two artifacts holding the same claims will diverge, and the divergence
is invisible because both look current.

**That fix was incomplete, and D153 found how.** This section used to
say the table above "is a rendering of it" — while the table held 14
rows and the block held 10 claims. Five rows had never faced either
adjudication prompt, and the file told the reader they had. The
divergence survived because nothing checked it: the first test written
for this compared *counts*, and passed, because 10 rows happened to
match 10 claims once the lettered rows were filtered out.

So the correspondence is now declared per claim and enforced by
`tests/test_claim_alignment.py`. A row with no claim behind it must be
marked `*` in the table — meaning **in the paper, never adjudicated** —
which is an honest state a reader can see, and the only alternative the
test permits.

```json
[
 {
  "row": "1",
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
  "row": "1b",
  "claim": "Appending is behaviourally near-free for new ENTITIES but not for new RELATIONS, AT DEPTH 1: head new entity +0.058, new relation +0.191. At DEPTH 2 the penalty is +0.249 and 'near-free' does not hold at all.",
  "scope": "PARAMETRIC HEAD ONLY, against a full rebuild at one freeze/append ratio. Retrieval is worse on every one of them (+0.247 entity, +0.771 relation, +0.666 depth-2). FALSIFIED IF the entity penalty exceeds the relation penalty at depth 1, or if the depth-2 penalty is under 0.10",
  "src": [
   "results/exp36_append.json",
   [
    "results"
   ]
  ]
 },
 {
  "row": "1c",
  "claim": "The store LEARNS: of the questions it properly REFUSED before an update, 432 of 432 (1.000) are answered correctly after it. Separately, it properly refused only 432 of the 1179 it could not answer (0.366); 21 of the 1200 were already answerable.",
  "scope": "UNITS, because the artifact holds two counts: `n_update_pairs` is 1657 withheld subject-relation PAIRS and `n_flip_questions` is the 1200 QUESTIONS asked about them, which the transition matrix runs over. The stored `learned_rate` 0.36 is 432/1200 (of everything evaluated) where the claim's 0.366 is 432/1179 (of what it could not answer) — three denominators answering three questions, now all named in the artifact. Frozen means FINGERPRINT-VERIFIED IN THIS EXPERIMENT (`mechanical_check_passed`): basis, coordinates and head are hashed at T0 and re-hashed after the update, and the run aborts on any difference. That closes the falsifier an adversarial rater named — the check previously lived only in a separate append run (D157). The 1.000 is conditional on prior honest refusal. FALSIFIED IF any of the 432 stays refused or turns wrong after the update, or any artifact fingerprint changes across it",
  "src": [
   "results/exp38_update.json",
   [
    "mechanical_check_passed",
    "fingerprints",
    "transition_flip",
    "learned_rate",
    "learned_ci95",
    "regression_stays",
    "control_never",
    "n_update_pairs",
    "n_flip_questions"
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
  "row": "1d",
  "claim": "The store REVISES rather than going stale: after a superseding edit it almost never keeps asserting the old fact — 1 of 431 previously-old-answering cases stays old (0.002). Revision is 0.459; the dominant failure is refusal (0.348) and wrong answers (0.190), not staleness.",
  "scope": "edits applied through the real kb.edit() path; conditional on having answered correctly before the edit; single-edit cases revise at only 0.235. Staleness is NOT zero and the claim does not say it is: the matrix contains one old->old case, which is the falsifier's own example and is reported rather than rounded away. FALSIFIED IF staleness exceeds refusal or wrong-answering as a failure mode",
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
  "row": "1e",
  "claim": "Revision is two operations: editing a fact alone revises 0.469 of previously-correct answers with 0.274 breakage; editing it AND supplying the edges its new target needs revises 0.733 with 0.077.",
  "scope": "same cases, same frozen head, within-experiment comparison. FALSIFIED IF supplying downstream edges fails to reduce breakage \u2014 it reduced it by 0.197",
  "src": [
   "results/exp46_revision_fix.json",
   [
    "conditions",
    "verdict"
   ]
  ]
 },
 {
  "row": "2",
  "claim": "Composition generalises to relation pairs never seen composed: at depth 2 held-out pairs score 0.9245 against trained pairs' 0.9135, a difference of +0.011 in the held-out pairs' FAVOUR.",
  "scope": "'parity' is stated as a margin, not a word: held-out is within 0.02 of trained and on the better side of it. Measured AT 61 relations (exp29). The contrasting failure is exp18, whose world file holds 5 relations: there, held-out composition ORDER transfers at 0.513 against 1.000 on seen pairs \u2014 chance. The threshold in between is untested, so any '>=60' is interpolation. Pair-clean holdout; the margin holds at depth 2 ONLY and breaks at depth 3 (0.626 vs 0.683, a gap of 0.057). FALSIFIED IF the depth-2 gap exceeds 0.02 in either direction",
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
   ],
   [
    "data/real_world_ai_hops.json",
    [
     "facts#distinct:relation",
     "holdout_compositions"
    ]
   ]
  ]
 },
 {
  "row": "3",
  "claim": "Order and depth can come from the STORE rather than from learning: letting walkability decide which relation is available next takes held-out composition accuracy from 0.534 to 0.912.",
  "scope": "ONE corpus and ONE walker formulation \u2014 not general. `exp24_walker.py` reads a single world (data/real_world_ai_hops.json); the earlier claim of 'two corpora' was not supported by its own evidence and is corrected here. Worse, the 0.534 baseline is NOT computed in this run: it is a literal pasted from exp18, so identical scoring across the two scripts is assumed rather than verified. Isolates neither depth nor order learning: it removes the need to learn them here, and does not show they cannot be learned. FALSIFIED IF any path-planning formulation reaches 0.912 on the same held-out pairs \u2014 three raters unanimously flagged that only one weak planner was ever compared, and Task 4 of the current plan recomputes the baseline in-run and adds a stronger one",
  "src": [
   "results/exp24_walker.json",
   [
    "selected",
    "held_out_correct_ci95",
    "baseline_d112_path_planner",
    "scope"
   ]
  ]
 },
 {
  "row": "4",
  "claim": "Depth extrapolates without depth-specific training for ANSWERING at 3 hops: 0.849 with no 3-hop in training, against 0.961 when 3-hop IS trained.",
  "scope": "ONE depth was measured zero-shot. It does NOT extend: at depth 4 (exp32, different corpus) correct falls to 0.289 raw and 0.149 under the anchor basis, so the property is demonstrated at 3 hops and refuted at 4. Answering only \u2014 refusal does not extrapolate. FALSIFIED IF zero-shot 3-hop answering falls below trained 3-hop by more than 0.15",
  "src": [
   "results/exp26_threehop.json",
   [
    "zero_shot_depth",
    "trained_on_3hop"
   ]
  ],
  "extra": [
   [
    "results/exp32_depth4.json",
    [
     "results"
    ]
   ]
  ]
 },
 {
  "row": "5b",
  "claim": "On a MIXED unanswerable benchmark the answer-type gate lifts not-applicable refusal from 0.050 to 0.693, and cuts DEPTH-1 answerable wrongness from 0.118 to 0.045 (depth-2, separately, 0.175 to 0.102).",
  "scope": "the wrongness figures are per depth and the claim now says which — an earlier version stated a bare 'answerable wrongness' that was depth-1 only. Depth-1 CORRECT falls 0.110 while TOTAL answered falls 0.183 (the extra 0.073 were wrong answers). Probe ceiling is 0.965, so 0.693 is threshold placement rather than the limit. FALSIFIED IF the gate raises wrongness at any depth, or lifts not-applicable refusal by less than it costs in correct answers",
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
  "row": "6",
  "claim": "Refusal quality falls as store DENSITY rises: within-population correlation between branching factor and refusal is -0.79, -0.83 and -0.91 across three unanswerable populations.",
  "scope": "a CORRELATION across branching strata, not a demonstrated mechanism. The ambiguity reading rests on a gain-median overlap (answerable 1.390 vs unanswerable 1.198, margin separation 0.143) that is consistent with ambiguity and does not establish it. FALSIFIED IF the correlation vanishes on a population where branching varies and confusability does not \u2014 D137 found exactly that boundary and it is why the claim says density rather than options",
  "src": [
   "results/exp30_refusal_diag.json",
   [
    "branching_stratified_refusal",
    "ambiguity_test",
    "residual_separation"
   ]
  ]
 },
 {
  "row": "7",
  "claim": "Compression buys generalisation and costs precision: a frozen low-dimensional basis takes novel-RELATION answering 0.293 -> 0.742 and novel-PHRASING 0.149 -> 0.313, while raising phrasing wrongness 0.036 -> 0.245 and dropping depth-4 answering 0.289 -> 0.149.",
  "scope": "DESCRIPTIVE across three experiments, and an earlier version of this scope said they were on 'different corpora' \u2014 they are NOT. exp31, exp32 and exp34 all read the same store (KB table `poc`) at 61/61/60 relations. The real confound is that each derived its OWN threshold (0.6, its own, 0.4), so the comparison is across tuning regimes rather than across corpora. No single experiment tests both halves, which makes this a pattern fitted to results rather than a prediction tested against them. FALSIFIED IF a representation wins on both axes at once under ONE threshold protocol \u2014 three raters unanimously flagged exactly this, and Task 5 of the current plan runs it",
  "src": [
   "results/exp31_novelrel.json",
   [
    "basis_threshold_sweep",
    "raw_baseline",
    "basis_selected_thr"
   ]
  ],
  "extra": [
   [
    "results/exp32_depth4.json",
    [
     "results"
    ]
   ],
   [
    "results/exp34_aliaspretrain.json",
    [
     "basis_2x2",
     "results"
    ]
   ]
  ]
 },
 {
  "row": "8",
  "claim": "Alias supply explains MOST of retrieval's advantage over a parametric head, and not all of it: the gap falls 0.229 -> 0.042 over 2 to 10 aliases, and on the population where supply reaches 18 it stops falling at ~0.09 (0.087 at 10, 0.091 at 18, tail slope +0.0015/alias). The residual is a capability difference, not a supply shortfall.",
  "scope": "depth-1 relation identification on KNOWN relations. THREE populations, three roles: the 2->10 curve is exp43's 34 relations; the 2->18 curve is exp51's 8 relations (those carrying 20+ aliases); the no-configuration-closes-it result is exp49's 56 relations. The plateau is measured ONLY on the 8-relation set, whose gap runs 0.030-0.052 HIGHER than the 24-relation control at every shared alias count \u2014 so the level does not transfer, and the larger population cannot be swept past 12 because its relations lack the aliases. The earlier claim that this is 'not a permanent loss of information' was WITHDRAWN at D155 when this falsifier was run. FALSIFIED IF the gap resumes falling past 18 aliases, or a head reaches 1-NN at any supply",
  "src": [
   "results/exp51_aliasplateau.json",
   [
    "results",
    "tail_gaps",
    "tail_slope_per_alias",
    "gap_at_max_alias",
    "noise_half_width",
    "mean_abs_gap_diff_on_overlap"
   ]
  ],
  "extra": [
   [
    "results/exp49_fair_head.json",
    [
     "one_nn",
     "best_head",
     "gap_to_1nn"
    ]
   ],
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
  "row": "12",
  "claim": "Entities are free for the parametric head and expensive for retrieval: subjects held out of training score 0.766 against seen subjects' 0.795 at depth 1, while retrieval drops from 0.854 to 0.526.",
  "scope": "subjects held out of TRAINING QUESTIONS only; their claims remain in the store and stay walkable. FALSIFIED IF the head's gap exceeds 0.05 on any of the three QUESTION populations within this corpus (depth-1, depth-2, not-applicable) \u2014 it did not on any: -0.029, -0.010, +0.001. A second CORPUS was not tested",
  "src": [
   "results/exp50_entity.json",
   [
    "results",
    "gaps",
    "largest_gap",
    "n_held_subjects"
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
