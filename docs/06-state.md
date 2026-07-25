# Current state — 2026-07-25

**Resume here.** Read this + [decisions.md](decisions.md) (D1–D25) to pick up cold. Everything ran locally on the RX 9070.

## Artifacts

**Data**
- `data/propositions/` — 62 JSONL files → **16,079 clean propositions / 56 domains** (was 10,479 / 36; the 20 `gen4_*` domains were added and merged this session). Canonical: `data/clean_v0.jsonl`, row-aligned with `results/dense_v0.npy` (BGE-M3 dense), `results/whiten_v0.npz` (ZCA, fit n=14,533), `results/sparse_v0.json` (top-24 lexical tokens+weights). Whitener fingerprint `b9714630a986908f` — recorded in probe outputs because amp_cos lives in whitened coordinates.
- `results/snapshot_10k/` — the frozen 10,479-prop space (corpus, dense, whitener, sparse, pair cache, both amp subspaces, pooler v2). Every number in D10/D16–D20 was measured there; keep it to reproduce them.
- `data/relations/prop_*.jsonl` — **23 transformation types, 2,822 pairs** (encoder-agnostic text; reusable forever). Three preserving types added this session as the honest holdout for pooler v2: `prop_cleft` (121), `prop_nominalization` (120), `prop_contraction` (80). `pairs_v0.jsonl` — 600 lexical relation pairs. `*.raw` = pre-validation originals.

**Checkpoints**
- `decoder_v0/` — dense-only soft-prefix decoder, **current best** (16k corpus, 12 ep): entity EM **0.203**, number EM **0.336**, cycle cos **0.619** — the third like-for-like scaling point, still climbing (D10). The 10.5k predecessor (0.178/0.278/0.579, D19 interpolation midpoint 0.304) is preserved in `results/snapshot_10k/decoder_v0/`.
- `decoder_v1/` — dual-channel. **STALE**: trained on the old 4.9k corpus, sparse channel ignored (D10 fixes not applied).
- `struct_pooler_v2.pt` — **shipping** pooler (all 5 v1-era preserving types trained), refit in the 16k space. `_v1` = D18's config, `_v0` = no-position ablation.
- `adapter_narrow/broad.pt` — negative-result hinge adapters (D11/D12), kept for reference.

**Caches** (delete to force rebuild; all deterministic)
- `results/prop_relation_emb.npz` — whitened pair embeddings, current whitener, all 23 types. Rows: x-side order, y positionally aligned. Rebuild: `scripts/probe_prop_rotations.py`.
- `results/token_vecs.npz` — ColBERT token vectors (all pair sides + a 1,500-prop corpus subset). Rebuild: `scripts/train_struct_pooler.py`.

**Structure channel v2 (D20)** — `codec/structure_channel.py`, `StructureChannel.load(ROOT)` defaults to the shipping config:
- amp: 8-dim valence subspace (4 preserve directions deflated), **gain 8.0** (`results/amp_subspace_v1.npz`; `_v0.npz` = the D16 g=2.0 config, geometry-safe for in-place use). **Comparison-time only — never store amp() output.**
- s: `struct_pooler_v2` over token vectors.
- role bits: `codec/role_bits.py` (spaCy parse; voice/cleft/nominalization/raising normalization, clause fingerprints, tense bit, epistemic hedge bit, shared-vocab gating).
- Combination: per-pair `min(amp_cos, s_cos, role_sim)`.

## Eval suite status (vs the docs/02 plan)

| # | probe | status |
|---|---|---|
| 1 | entity/number fidelity | ✓ **0.203 / 0.336 @16k** (was 0.178/0.278 @10.5k), still scaling (D10) |
| 2 | noise robustness | ✓ ~94% @ latent cos 0.89; collapse below ~0.45 |
| 3 | interpolation | ✓ D19 — @16k: endpoints 0.62 → midpoint 0.33, smooth V, fluent at every t; relative drop invariant at ~47% across decoders |
| 4 | cycle consistency (k=1) | ✓ **0.619** @16k (was 0.579) |
| 5 | isotropy | ✓ 0.348 → 0.037 whitened, eff. rank 523/1024 @16k |
| 6 | rotation tolerance | superseded by algebra probes (rotations rejected, D4/D15) |
| 7 | anchor spanning | ✓ v0 (nearest 0.39 / phase-ceiling 0.82 @1k anchors, 16k corpus) |

**Original seven-probe suite is closed.** Structure-channel scorecard (D20, at 16,079 props): full type-level ordering, worst-case margin **+0.011**, **pair-level AUC 0.942**, transfer to 3 never-trained preserving types **0.912**. (Replicates across an independently refit space: at 10,479 props it was +0.014 / 0.945 / 0.910. The final numbers include a role-bits punctuation fix that cost 0.006 AUC and exposed ~2 points of previously-masked parse noise — see D20.)

## The corpus cascade (run in this order after ANY corpus change)

Everything downstream of the whitener has to be refit — the amp subspace and pair cache live in whitened coordinates. Ran end-to-end this session at 16,079 props; the structure channel survived and improved (D20 replication).

1. `scripts/baseline_isotropy.py` — rebuilds `clean_v0.jsonl` + `dense_v0.npy` + `whiten_v0.npz`. ⚠️ **overwrites v0 names in place** — snapshot first (see `results/snapshot_10k/`).
2. `scripts/extract_sparse.py` — re-derives `sparse_v0.json` row-aligned.
3. `scripts/probe_prop_rotations.py` — rebuilds the pair cache in the new space. Both caches now self-invalidate: `prop_relation_emb.npz` stores a **whitener fingerprint** (it holds whitened vectors, and a corpus change refits the whitener while leaving every pair text identical — text-only keying silently served stale coordinates), and `token_vecs.npz` keys on its text list, which includes a corpus subset.
4. `scripts/probe_axis_amplify_v1.py --persist` (+ `fit_amp_subspace.py` for the v0 config).
5. `scripts/train_struct_pooler.py --split v2` — the negative pool is drawn from the corpus.
6. `scripts/probe_role_bits.py` — confirm the ordering survives.
7. `scripts/train_decoder_v0.py --epochs 12` — the expensive one and the actual fidelity payoff (D10: scale data **and** compute together — fixed-compute curves lie).

**Status**: all 7 steps complete at 16,079 props. Step 7 delivered the third like-for-like fidelity point (0.203/0.336/0.619 — table in D10).

## Codec v2 — LANDED (D21)

The D3 triple works end-to-end: `[gist ; identities ; s]` doubles fidelity over dense-only (entity 0.203→**0.483**, number 0.336→**0.668**, exact 0→**0.064**, cycle 0.619→**0.810**) and makes identity fidelity **noise-immune by construction** (σ=0.5: 0.461/0.662 vs v0's 0.125/0.317). Shuffled attribution proves the sparse channel is THE identity carrier (shuffling it → ~0). s-vector contributes +0.033 role fidelity — the decoder reads binding from it. **Residual failure mode = value-to-role binding** (right numbers, wrong slots — samples in D21); next lever is slot-tagged identity prefixes, not more data. Artifacts: `checkpoints/decoder_v2/`, `results/decoder_v2_eval.json`, `results/s_vecs_v0.npy` (+ meta; rebuild via `scripts/compute_s_vecs.py`).

**Engineering note (cost a smoke-test cycle)**: zeroing *projected prefix embeddings* to drop a channel sends exact-zero vectors through every RMSNorm and yields non-finite LoRA gradients in backward (forward loss stays finite — 246 inf/NaN grads measured). Drop by zeroing the channel's *input* instead, so dropped rows get `proj(0)` — a learned in-distribution null embedding. Also: bf16 scalar parameters silently stop learning (updates round away below ~1e-3); keep learned scalars fp32 and cast at use.

## Slot-tagged identities — LANDED (D22); decoder_v2t SHIPS

Binding given-present 0.714 → **0.795** (mis-attachment −28% relative), number EM 0.668 → **0.720** (0.725 under σ=0.5 gist noise — the tags live in the noise-immune channel); entity −0.021 (≈noise), cycle flat. Ceiling is **coverage**: only 47% of number tokens taggable (BGE-M3 splits comma numbers); next lever if number fidelity plateaus = build identity slots from the validated labels directly, bypassing BGE-M3 lexical tokenization. Artifacts: `checkpoints/decoder_v2t/`, `results/decoder_v2t_eval.json`, `results/sparse_tagged_v0.json`, binding metric in `codec/evals/fidelity.py`.

## Next queue (priority order)

1. ~~Value-to-role binding~~ — landed (D22).
2. ~~Codec-level min(struct, identity)~~ — landed (D23): `codec/identity_channel.py`, bidirectional-mismatch rule, zero false flags; margin +0.011→**+0.022**, pair-AUC 0.942→**0.963** (`results/codec_compare_v0.json`, `scripts/probe_codec_compare.py`). Bottleneck now formality vs tense (both marked-feature cases).
3. ~~Cycle-under-noise~~ — landed (D24): output quality INVARIANT to gist noise through σ=0.8 (2× training range); symbolic channels error-correct the gist. De-risks T1: the reasoner may be sloppy in continuous space (`results/cycle_noise_decoder_v2t.json`).
4. ~~Interpolation at v2~~ — ran; it turned into a **channel-conflict experiment** (side channels fixed at A while gist slerps to B) and the identity channel won outright: output stays A's proposition at every t (D21 note). Design implication for Phase 2: **latent ops must update the triple coherently — moving the gist alone moves nothing.** A true v2 traversability probe needs path-following side channels.
4. **Phase 2 opened — memory store v0 PASSES the retrieval gate (D25)**: `codec/memory_store.py` + closed world (`data/closed_world.json`); relational translation addressing 0.988, edits transparent via key/value separation at supersession. Remaining for the full gate: forgetting curves (T5) and small+store vs larger-dense (T3) — both need at least a QA head; next concrete steps are scaling the store (~10k entries, where identity rescoring should activate) and reasoner-noised query latents (D24 bridge).
5. Then per roadmap: cycle k>1, anchor sweep at scale, memory-addressing refinement using the confirmed operator inventory (valence = translation, role-swap = slot exchange, tense = bit flip, hedge = bit flip — D15/D18/D20). The reasoner-facing latent is now the working triple.

## Instrument checks (run after touching the structure channel)

| script | what it asserts | cost |
|---|---|---|
| `scripts/check_role_bits.py` | one proposition written 16 ways: 8 preserving constructions must produce identical bits; role-swap/tense/hedge must separate. Valence and added/dropped arguments are reported but **not** asserted (other channels' jobs / measured trade-offs). | seconds, CPU |
| `scripts/check_structure_channel.py` | end-to-end through the public API on unseen text — the only path that doesn't read caches. Each mechanism must fire on the case it owns. Identity edits reported, not asserted. | ~1 min, GPU |

Between them they caught three silent-corruption bugs during the D20 replication; see D20's plumbing notes.

## Loose ends / known debt

- `decoder_v1` stale; sparse-channel fixes (D10) unapplied.
- v0 artifact names are reused by the rebuild pipeline — version before the cascade or the D10/D16/D20 numbers stop being reproducible.
- Known limitation (accepted, D18): converse-predicate paraphrases legitimately flag as role-different.
- Structure-channel margin is thin (+0.011 type-level); trust the pair-level AUC (0.942), and see queue item 3 for the principled widening.
- **Cheapest remaining structure win**: ~2 points of parse noise on preserving types (active_passive 0.969, paraphrase 0.727) — head normalization or a stronger parser than `en_core_web_sm`. Run `scripts/check_role_bits.py` after any change to the extractor.
- `scripts/validate_relation_pairs.py` — generated preserving pairs must be validated before use (the first nominalization batch had 118/120 rows with invented trailing facts; the recipe-driven regeneration passed 120/120).
- Probe house rules standing (D8 + method notes): positive controls for fit-a-transform probes; per-channel shuffled attribution; noise reported as latent cosine; hold out whole categories; **and (new, D20) check that a guardrail matches the artifact's actual role — a retrieval guardrail on a comparison-time metric blocks the right answer.**
