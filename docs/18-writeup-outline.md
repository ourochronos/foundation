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
| 3 | The **store** supplies what makes multi-hop answering work; the step-by-step **walk** does not | one corpus, R=5, depth 2. At R=5 enumeration is 30 candidates, so the walker's remaining case is **cost, not accuracy** — untested | store-filtered planner **0.9032** vs walker 0.9123 (inside CI); same planner denied the store **0.3883**. Availability filtering **+0.515**, greedy walking **+0.009**. D112's planner recomputed in-run is **0.8138**, not the 0.534 exp24 pasted (D117 → **D158**) | **falsified if** a model-only planner reaches the walker's CI, or store-filtered planning fails to match it where enumeration is affordable |
| 4 | Depth extrapolates without depth-specific training, for *answering* — **at 3 hops, and not beyond** | answering only; **one** depth measured zero-shot | 3-hop **0.849** with no 3-hop in training, vs 0.961 trained (D119) | *refusal* does not extrapolate (D120); and **depth 4 refutes it** — 0.289 raw / 0.149 basis (D126) |
| 5b | On the **mixed** benchmark, refusal needs the answer-type gate | law #9 population: chain_break + not_applicable + absent_entity | not_applicable **0.050 → 0.693** with the gate; chain_break 0.337 → 0.650; **depth-1** answerable wrongness 0.118 → 0.045 and **depth-2** 0.175 → 0.102; **correct** falls 0.110 while **total answered** falls 0.183 — the extra 0.073 removed were wrong answers (D134) | probe ceiling is 0.965, so 0.693 is threshold placement, not the limit |
| 6 | Refusal is governed by the **most confusable option available**, not by how many options there are | chain-break unanswerables, one corpus, depth 2; count is not zero, just weaker | with branching held identical, refusal tracks **max cosine r=−0.954** vs mean −0.774 and count **−0.485**; one confusable option refuses **0.8485**, eight non-confusable ones **0.8848**. Reconciles D124's correlation with D137's free reverse edges (D124/D137 → **D160**) | **falsified if** refusal tracks option count better than max cosine on any store, or the arms fail to separate on cosine (+0.1539; the run aborts otherwise) |
| 7 | Compression buys generalisation and costs **refusal** — not the accuracy of what it enables | one store, **one threshold rule for both arms** (law #6); phrasing leg still uncontrolled | novel-relation answering **0.005 → 0.742** while wrong moves only 0.153 → 0.167 — raw's low score is raw *refusing* (abstain 0.842). At matched coverage **+0.741 correct for +0.072 wrong**, a tenth of the gain; costs land on refusal (**−0.706** novel, **−0.569** known) and known answering (−0.141) (D125/D126 → **D159**) | **falsified if** the wrongness cost on the population it helps is commensurate with the gain there, or the refusal collapse disappears under matched tuning |
| 8 | Alias supply explains **most** of retrieval's advantage over a parametric head — **and not all of it** | depth-1 relation identification, known relations; the plateau is measured on 8 high-alias relations only | gap 0.229 → 0.042 over 2→10 aliases (exp43, 34 rel); then **flat at ≈0.09** over 10→18 (exp51, 8 rel: 0.087 → 0.091, tail slope +0.0015/alias vs noise ±0.026); no head config reached 1-NN at 2 aliases — 0.691 vs 0.925 (exp49) (D139, D148, **D155**) | **falsified if** the gap resumes falling past 18 aliases, or a head reaches 1-NN at any supply. *"Not a permanent loss of information" was withdrawn at D155 when this falsifier was run — the head plateaus at 0.892 while 1-NN sits at 0.975 from two aliases onward.* |

| 11 | Claim adjudication is noisy in a **specific** way: instability is one rater, and the two prompts disagree completely | a frozen prior round — 16 runs, 4 families, 3 adversarial repetitions each | flags per identical run **6/7/4** (range 3) against ranges of 1, 1, 2; verification flagged **0 of 14** at quorum where attack flagged **6 of 14**, two claims only by attack and one only by verification (D140 → **D154**) | **falsified if** within-rater variation is comparable across raters, or the two prompts flag overlapping sets |

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

**Row 11 carried a `*` — "in the paper, never adjudicated" — until D160.** Its
evidence is the behaviour of the adjudicators themselves, so judging it in the
run that generated its evidence would have been circular. That round has now
closed and frozen (`results/adjud_quorum.json`), so the claim is judged against
a *prior* round and the mark is gone. The raters judging it are still the same
families whose earlier behaviour it describes, which is a residual
self-reference worth stating and not worth pretending away.

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
  "claim": "The STORE supplies what makes multi-hop answering work, and the step-by-step WALK does not: an exhaustive planner allowed to consult the store for which chains are walkable scores 0.9032 against the walker's 0.9123 (inside its CI), while the same planner denied the store scores 0.3883. Availability filtering is worth +0.515; greedy walking is worth +0.009.",
  "scope": "ONE corpus, R=5, depth 2 \u2014 and at R=5 exhaustive enumeration is 30 candidates, so the walker's remaining justification is COST rather than accuracy and that is untested here (R=61 would be 3,782 candidates at depth 2 and 226,981 at depth 3). The earlier form of this claim said order and depth must come from the store rather than from a planner; the first half is confirmed overwhelmingly and the second is REFUTED (D158). It also quoted a 0.534 planner baseline pasted from exp18, which recomputed in-run is 0.8138 \u2014 the reported gap was inflated almost fourfold. Every arm shares one head, one seed, one scorer and one threshold rule, and the walker arm reproduces exp24's stored 0.9123 to four decimals or the script aborts. FALSIFIED IF a model-only planner reaches the walker's CI on any corpus, or if store-filtered planning fails to match it where enumeration is affordable",
  "src": [
   "results/exp52_planner_baseline.json",
   [
    "results",
    "walker_correct",
    "walker_ci95",
    "best_planner_correct",
    "d112_recomputed",
    "exp24_pasted_d112_value",
    "n_chains_searched",
    "verdict"
   ]
  ],
  "extra": [
   [
    "results/exp24_walker.json",
    [
     "selected",
     "held_out_correct_ci95",
     "baseline_d112_path_planner",
     "scope"
    ]
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
  "claim": "Refusal is governed by the MOST confusable option available at the break step, not by how many options there are. With branching held identical across arms, refusal tracks the maximum cosine between an available relation and the asked one at r=-0.954, against -0.774 for the mean and -0.485 for the count; ONE confusable option refuses 0.8485 while EIGHT non-confusable ones refuse 0.8848.",
  "scope": "chain-break unanswerables, one corpus, depth 2, raw 1024-d at D123's fixed THR=0.8. The walker takes ONE option by greedy argmax, which is why the maximum rather than the count governs \u2014 and why D124 saw refusal fall with branching (more options raises the maximum) and D137 found reverse edges free (they never do). Count is NOT zero: the confusable arm pins its maximum at 0.50 for every k, so its slope isolates the pure count effect at -0.073 over three doublings. Cases are restricted to break steps offering at least 8 options, which biases toward high-branching questions and is reported rather than hidden; the corpus cannot support a wider sweep, since only 0.2% of frontiers offer 16+. FALSIFIED IF refusal tracks option COUNT better than maximum cosine on any store, or if the arms fail to separate on cosine (checked, +0.1539, and the run aborts otherwise)",
  "src": [
   "results/exp54_confusability.json",
   [
    "refusal_by_arm",
    "max_cosine_by_arm",
    "correlations_across_cells",
    "one_confusable_vs_many_non",
    "manipulation_separation",
    "slope_per_doubling",
    "n_cases"
   ]
  ],
  "extra": [
   [
    "results/exp30_refusal_diag.json",
    [
     "branching_stratified_refusal",
     "ambiguity_test"
    ]
   ]
  ]
 },
 {
  "row": "7",
  "claim": "Compression buys generalisation and costs REFUSAL, not the accuracy of what it enables. Under one threshold protocol, a frozen K=48 basis takes novel-relation answering from 0.0054 to 0.7419 while its wrong-rate moves only 0.1531 to 0.1667 \u2014 raw's low score is raw REFUSING (abstain 0.8415), not raw erring. At matched coverage the gain is +0.7407 correct for +0.0723 wrong, a tenth of the gain; the real costs are refusal on novel unanswerables (-0.7060), refusal on known ones (-0.5685) and known-relation answering (-0.1409 at 9x the wrong-rate).",
  "scope": "ONE store, ONE threshold rule for both arms, derived on TRAINED populations only (law #6) \u2014 this is the controlled comparison three raters unanimously asked for, and it changes exactly one thing against exp31, which ran its raw arm at an inherited THR=0.8 and swept only its basis arm. An earlier version of this scope said the evidence spanned 'different corpora'; exp31, exp32 and exp34 all read the same table, so the confound was always tuning (D156). Reported at each arm's own threshold AND at matched coverage, with answerable and unanswerable never averaged together \u2014 the first summary of this experiment did average them and reported a figure describing neither (D159). The PHRASING leg is NOT covered: it needs exp34's alias populations, a different question set. FALSIFIED IF the basis's wrongness cost on the population it helps is commensurate with its gain there, or if the refusal collapse disappears under matched tuning",
  "src": [
   "results/exp53_compression_controlled.json",
   [
    "at_own_threshold",
    "selected_thresholds",
    "matched_coverage",
    "summary_at_matched_coverage",
    "verdict"
   ]
  ],
  "extra": [
   [
    "results/exp31_novelrel.json",
    [
     "basis_threshold_sweep",
     "raw_baseline",
     "basis_selected_thr"
    ]
   ],
   [
    "results/exp32_depth4.json",
    [
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
  "row": "11",
  "claim": "Claim adjudication is noisy in a specific, measurable way: instability is concentrated in ONE rater (flags per identical run 6/7/4, range 3, against ranges of 1, 1 and 2 for the other three), and the two prompts disagree completely at quorum — verification flagged 0 of 14 while attack flagged 6 of 14, with two claims flagged only by attack and one only by verification.",
  "scope": "measured on a FROZEN PRIOR ROUND (results/adjud_quorum.json, D154): 16 runs, four families, three adversarial repetitions per rater, per-rater majority before quorum. Judging this claim is no longer circular because the evidence is a round that has already closed — but the raters judging it ARE the same families whose earlier behaviour it describes, and that is disclosed rather than hidden. Cohen's kappa is not quoted: with skewed marginals it tracks the table's messiness rather than rater reliability. FALSIFIED IF within-rater variation is comparable across raters rather than concentrated, or if the two prompts flag overlapping sets",
  "src": [
   "results/adjud_quorum.json",
   [
    "stability",
    "verification",
    "flagged",
    "quorum_raters",
    "n_claims"
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
