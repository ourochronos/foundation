# Roadmap

Phases are gated by measurements, not dates. Everything past Phase 1 is provisional and expected to be revised by probe results.

## Phase 0 — Environment & docs ✅

ROCm 7.2 + PyTorch 2.13 on RX 9070; Bonsai-27B local via PrismML llama.cpp fork (56 tok/s); vision documented.

## Phase 1 — Codec v0 + evaluation harness ✅ (see [06-state.md](06-state.md))

Built and measured: encoder wrapper, whitening, noise-trained soft-prefix decoder, **all 7 eval probes closed** (interpolation ran last, D19). Key outcomes: identities ARE in the dense latent (D10 — fidelity is data-bound and scaling: 0.178/0.278 EM at 10.5k props); decoder conditioning + robustness verified; the latent is traversable — off-manifold midpoints decode fluently, degrading in fidelity not in form (D19). Sparse-channel wiring deferred to codec v2 (D10 fixes pending).

## Phase 1.5 — Algebra probes ✅ GATE RESOLVED: rotations REJECTED; structure channel built instead

Rotations failed at lexical and proposition altitude with validated instruments (D4); the actual blocker was representational (D9/D13). Resolution: **translation-first algebra** (D15) + a three-mechanism **structure channel** (D14–D18, D20: linear valence subspace + trained token pooler + symbolic role bits, combined per-pair by `min`). **v2 achieves the full ordering** — every meaning-changing type below every meaning-preserving type, pair-level AUC 0.942, and it transfers to preserving constructions it never trained on (0.912). Operator inventory: valence = translation/subspace scaling, role swap = slot exchange, tense = bit flip, hedge = bit flip.

**Codec v2 landed (D21)**: the full triple `[gist ; identities ; structure]` doubles fidelity (0.483/0.668/0.810 vs 0.203/0.336/0.619 dense-only) with noise-immune identities — the D3 hybrid-latent bet confirmed end-to-end. Residual: value-to-role binding at generation. **Next before Phase 2**: slot-tagged identity prefixes (binding), identity-channel routing for substitutions (D20 caveat) — queue in [06-state.md](06-state.md). Phase 2's working latent is the triple.

## Phase 2 — Binding algebra + external memory prototype

Anchor inventory (data-derived first), relation operators (**translation-first per D15 — not rotations**; role-level ops from the structure channel), associative store, surprisal-gated writes. Spec: [04-memory.md](04-memory.md).

**Gate**: retrieval precision on closed-world synthetic facts; knowledge-edit and forgetting curves vs. a no-store baseline.

## Phase 3 — Latent reasoner prototype

Ultra-wide weight-tied recurrent core over frozen codec latents; supervised first on encoded text-CoT trajectories; surprisal halting. Spec: [05-reasoner.md](05-reasoner.md).

**Gate (T1)**: matches text-CoT baseline on ProsQA-style / synthetic multi-step tasks at FLOP parity.

## Phase 4 — Integration & continuous learning (T3, T5)

Small reasoner + store vs. larger dense model; sequential-stream learning without weight updates.
