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
| 1 | A knowledge store can be appended to without reindexing, and new content is immediately queryable | relation vocabulary ≥ ~50; relation has a **label**; anchor-basis representation | novel relation 0.742 correct / 0.167 wrong (D125) | a corpus where new relations arrive without usable labels |
| 2 | Composition generalises to relation pairs never seen composed | ≥ ~60 relations; **pair-clean** holdout | 0.925 vs 0.913 trained (D123); replicated at 0.842 vs 0.868 under alias phrasing (D127) | small vocabularies — at 5 relations it fails (D112) and a pair-clean holdout cannot even be built (D122) |
| 3 | Order and depth need not be learned — the store supplies both | any | held-out compositions 0.534 → 0.912 when order comes from walkability (D117) | — replicated on two corpora |
| 4 | Depth extrapolates without depth-specific training, for *answering* | — | 3-hop at 0.851 with no 3-hop in training (D119) | *refusal* does not extrapolate (D120) |
| 5 | The system refuses rather than guessing | **sparse** stores only | 0.970 refusal, ~0.000 wrong (D118) | dense stores: 0.72–0.98 refusal, 0.017–0.073 wrong (D123/D124) |
| 6 | Refusal quality is bounded by store density | — | refusal vs branching correlation −0.79 to −0.91 (D124) | a density-invariant refusal signal; two principled candidates failed |
| 7 | Compression buys generalisation and costs precision | — | basis vs raw: novel relations 0.742/0.293, depth-4 0.149/0.289, phrasing 0.313/0.149 (D125/D126/D128) | a representation that wins on both axes |

## What we cannot claim

Stated as prominently as the claims, because these are the ones a reader
would otherwise assume:

- **Not free-form language.** Every question is templated. Phrasing
  robustness is the dominant unsolved failure: an unseen alias for a *known*
  relation costs −0.719 (D127), and neither representation fixes it (D128).
- **Not depth-unbounded in practice.** Coverage decays 0.934 → 0.693 → 0.289
  from depth 2 to 4, and on a dense store the wrong-rate *grows* with depth
  (D126).
- **Not entity generalisation.** Every experiment holds out relations,
  pairs, phrasings or instances. Novel *entities* were never tested.
- **Not a free lunch on refusal.** Two principled fixes moved along the
  precision/coverage frontier without shifting it (D124).

## Method contributions (arguably the most reusable part)

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
