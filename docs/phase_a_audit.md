# Phase A — trust recovery audit (2026-07-27, D68)

Two store bugs, audited BEFORE fixing (instrumentation commit `f0e1f97`;
fixes land in a separate later commit).

- **Bug 1** — `PQStore._scores()` GPU cache keyed on entry COUNT;
  `supersede()` mutates codes in place → count unchanged → stale cache can
  score pre-edit codes. Silent edit-failure on the GPU path.
- **Bug 2** — both stores mask shadowed/excluded candidates to `-inf` then
  take top-k WITHOUT filtering to finite: if every candidate is masked,
  selection returns garbage entries at `-inf` and a multi-hop chain
  continues instead of terminating.

## Step 0 — static triage

Store-class / supersession usage read from each generating script (grep +
code reading; ChannelWalker's internal `exclude=visited` counted even where
scripts don't pass `exclude`).

| artifact (number) | generating script | store class | supersedes? | still implicated? |
|---|---|---|---|---|
| k6_percase_clean.json (0.670/0.685) | k6_percase_clean.py | MemoryStore (per-case, N≈5–15) | YES (per-case edits) | **Bug 2 YES** (tiny N: masked can reach N); Bug 1 no (no PQStore) |
| k6_b1_percase.json (0.352) | k6_b1_percase.py | **none** — contexts hand-assembled from text dicts; no store query executes | n/a | **NO** (neither bug reachable) |
| k6_b1_baseline.json (0.040) | k6_b1_baseline.py | MemoryStore (pooled ~5k) | YES | NO for Bug 1; Bug 2 statically impossible (top-5, no exclude; finite ≥ N−1043 ≫ 5) |
| k5b_probe.json (0.975 / cap_mayor 0.933 / hq_loc_cap 0.933 / big_pop 0.000) | probe_k5b.py | MemoryStore via v06_pipeline (N=8,859) | NO | **NO** (no supersession; walk masks ≤3 of 8,859) |
| reasoner_v07.json (v0.7b battery) | train_reasoner_v07.py | MemoryStore via v06_pipeline | NO | **NO** (same bound) |
| store_pq_l3.json (battery parity; 100k=24 ms; 1M=796 ms CPU) | probe_store_pq_l3.py | **PQStore** (pooled ~5k) + bench stores | YES (1,043, battery section) | **Bug 1: evidence says no** (see below); Bug 2 statically impossible pooled; replayed to confirm zero firings |
| k6_postedit.json (0.468) / k6_clean_regime.json (0.604) / k6_phrasing_sens.json (0.405–0.468) | k6_stage3_edits.py (+exec heads) | MemoryStore (pooled 3,957+1,043) | YES | NO — Bug 2 statically impossible: finite ≥ 3,957−3 at every hop |
| k6_preedit.json (0.862/0.874/0.820) | k6_stage2_preedit.py | MemoryStore (pooled) | NO | NO |
| individuation_j4.json (0.948 path-collided) | probe_individuation_j4.py | MemoryStore (17,715) | NO | NO |
| d49_tests34.json (ripple 0.920) | probe_d49_tests34.py | MemoryStore (8,859) | YES (150) | NO — finite ≥ 8,859−153 |
| v4b_probe.json (views 0.970/0.920; ALU 1.000) | probe_v4b.py | MemoryStore (9,259) | NO | NO |
| earlier suite (soft_planner_j3, reasoner_v06, store_growth_j4, multiseed_k4, frozen_templates_k5, alias_j4b, canon_m1, basis_floor_j2, pq_j2b, crosslingual_j5) | various | MemoryStore | NO (except none) | NO — no supersession; pooled N ≫ masked |

**Bug 1 scope conclusion**: exactly ONE headline artifact ever instantiated
`PQStore` (store_pq_l3.json). Three independent lines of evidence say the
stale-cache pattern could not have fired in the recorded run:
1. The run was launched `CUDA_VISIBLE_DEVICES=""` (session record); its
   manifest lacks the `versions.gpu` key, which `run_manifest()` writes only
   when `torch.cuda.is_available()` — i.e. the artifact itself records that
   the GPU path was off, so `_scores()` used the NumPy branch, which reads
   `self.codes` directly (always fresh).
2. Call-order: the script applies ALL supersessions before the first
   `_scores()` call; a cache built lazily afterward is post-mutation.
3. Replay with the stale-pattern counter (below).
Bug 1 is a REAL landmine for any interleaved query/supersede workload — the
PoC's live regime — which is why it must be fixed; it just has not touched
a recorded number.

**Bug 2 scope conclusion**: exhaustion requires masked ≥ N−k. Only the
per-case K6 stores (N as low as ~5, up to 4 shadowed + 3 visited) can reach
it. Direction-of-error note: a garbage `-inf` continuation lands on an
arbitrary wrong entry and scores as a MISS — Bug 2 can deflate the 0.670,
not inflate it; the replay counter quantifies whether it fired at all.

## Step 2 — replay (instrumented, unfixed code)

Conditions matched to originals (L3 replay CPU-forced to match the
recorded run). Counters: `queries`, `deficit_lt_k` (finite < k),
`zero_finite`, `pq_cache_uses`, `pq_stale_cache_uses`, `supersedes`.

**Per-case replay** (`k6_percase_clean.py`, audit on): all four variants
reproduce the artifact EXACTLY (0.670/0.675/0.682/0.685). Counters over
7,507 store queries: `deficit_lt_k` = 79 (finite < k — benign: top-1 still
valid, walker consumes only r[0]); **`zero_finite` = 2** — Bug 2 fired
twice: two walks continued on a garbage −inf entry instead of terminating.
Bound on the headline: ≤ 2 of 600 cases (≤ 0.4 pts), and both fire-paths
score as MISSES either way (a correctly-terminated walk is also a miss for
P@1) — so the 0.670 NUMBER is unaffected; what the bug corrupted was honest
termination, not the score. (Note: the `supersedes` counter instruments
PQStore only; MemoryStore supersessions ran but are uncounted — immaterial
to either bug.)

**L3 replay** (`probe_store_pq_l3.py`, CPU-forced to match the recorded
run): battery reproduces identically (0.740/0.427/0.215); bench within
timing noise (24.5 ms @100k, 713 ms @1M). Counters: `pq_scores_calls` =
2,211, **`pq_cache_uses` = 0, `pq_stale_cache_uses` = 0** (GPU cache never
even constructed — CPU branch, as the manifest's missing `gpu` key said),
`supersedes` = 1,043, `zero_finite` = 0.

## Step 3 — audit table

| number | artifact | store | GPU path populated | supersession between scoring calls | Bug 1 fired | Bug 2 fired | verdict |
|---|---|---|---|---|---|---|---|
| 0.670 / 0.685 per-case | k6_percase_clean.json | MemoryStore | n/a | yes (per-case edits before walks) | n/a | **2 / 7,507 queries** (≤0.4 pts, miss-either-way) | **trustworthy** |
| 0.352 B1 per-case | k6_b1_percase.json | none | n/a | n/a | no | no | **trustworthy** |
| 0.040 B1 pooled | k6_b1_baseline.json | MemoryStore | n/a | yes, before queries | n/a | statically impossible | **trustworthy** |
| K5b: 0.975 / cap_mayor 0.933 / hq_loc_cap 0.933 / big_pop 0.000 | k5b_probe.json | MemoryStore | n/a | none | n/a | statically impossible | **trustworthy** |
| v0.7b battery | reasoner_v07.json | MemoryStore | n/a | none | n/a | statically impossible | **trustworthy** |
| PQ battery 0.740/0.427/0.215; 24 ms @100k; 796 ms @1M (CPU) | store_pq_l3.json | PQStore | **no** (counter: 0 cache uses; manifest: no gpu key) | yes — all before first scoring call | **0 firings** | 0 firings | **trustworthy** |
| 0.468 / 0.604 / 0.405–0.468 pooled post-edit family | k6_postedit / clean_regime / phrasing_sens | MemoryStore | n/a | yes, before queries | n/a | statically impossible (N≈4,900, masked ≤1,046+3) | **trustworthy** |
| 0.862/0.874/0.820 pre-edit; 0.948 individuation; 0.920 ripple; views/ALU; earlier suite | various | MemoryStore | n/a | none or bounded | n/a | statically impossible | **trustworthy** |

**Blast radius: empty.** No verdict is *retracted* and none is *needs-rerun*.
The composition-transfer claim (K5b cells + K6) runs entirely through
unimplicated paths; the 0.670 carries a quantified ≤0.4-pt Bug-2 exposure
that cannot have inflated it (both fire modes score as misses). Bug 1 has
never touched a recorded number — its danger is entirely prospective
(interleaved query/supersede, i.e. the PoC's live regime), which is why the
fix still matters.

## Provenance caveat (constraint 5)

All headline manifests record `dirty: true` (K2 adopted mid-program; the
commit-then-run rule only landed in D64). For every implicated artifact the
generating script was committed IN THE SAME COMMIT as the artifact itself,
and the replay reproduces the artifact's numbers from that script at HEAD —
reported as REPLAY EVIDENCE, not as the original run's history. Rows where
that reproduction fails are verdicted needs-rerun.

## Out-of-scope observations (for later phases, per constraints)

- `run_manifest()` does not record environment variables; `CUDA_VISIBLE_DEVICES`
  materially changes code paths and is only inferable from the `gpu` key's
  absence. Manifest phase should record relevant env.
- The `exec(head)` script-chaining pattern makes static triage harder than
  it should be (three levels deep in places) — already flagged for the
  restructure phase.
- `store.query` direct callers outside ChannelWalker (several probes index
  `r[0]` unguarded) would crash loudly on the fixed empty-return — correct
  behavior, but the callers should be swept in the fix step.
