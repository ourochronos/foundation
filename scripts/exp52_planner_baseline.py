"""Does order and depth have to come from the store? (D154, claim 3)

The falsifier all three adversarial raters named, unanimously: *"another
path-planning formulation could reach 0.912; comparison against one 0.534
planner does not rule that out."* Reading the code afterwards made it worse —
`exp24_walker.py` stores

    "baseline_d112_path_planner": {"correct": 0.534, "wrong": 0.433, ...}

as a **literal pasted from exp18**, so the headline comparison assumes
identical scoring across two scripts rather than verifying it. That is D147's
defect sitting under the most load-bearing architectural claim in the project.

So: recompute the baseline in-run, and decompose what the store actually
contributes. Four arms, one scorer, one question set, one head.

  * **P1 rank-then-permute** — D112's formulation. Take the top-k relations by
    detection score against the predicted sum, permute them into chains, take
    the best-fitting. No store involvement.
  * **P2 exhaustive, model-only** — enumerate EVERY chain over R^1 and R^2
    (30 at R=5), score each against the predicted sum, execute the best from
    the subject. Order and depth both come from the model. This is the
    strongest form of the alternative the raters asked for.
  * **P3 exhaustive, store-filtered** — the same enumeration, restricted to
    chains actually walkable from this subject, best by fit. Order from the
    model, *availability* from the store.
  * **W the walker** — greedy step-by-step against the residual, options taken
    from the frontier. Order and depth both from the store.

**The decomposition is the point.** If P2 matches W the claim is simply wrong
and the walker beat a weak baseline. If P3 matches W but P2 does not, then the
store's contribution is **availability filtering rather than step-by-step
walking** — which refutes the claim as stated while explaining why the design
works, and is the outcome that would teach the most. If both trail W, the
claim survives an attack it has never faced.

Scoring is L2 against the un-normalised sum, never cosine: the magnitude is
what encodes depth, and a scale-invariant score would hand the planners a
depth cue the walker has to earn (the D117 lesson, inverted).

Every arm gets an abstain threshold swept on SEEN compositions only and
selected by the walker's own pre-stated rule — smallest threshold whose seen
wrong-rate is <= 0.02 (law #6). A planner denied an abstain mechanism the
walker has would be a strawman, which is the thing this experiment exists to
avoid building.

Reuses exp24's caches; no new embedding run.

Usage: .venv/bin/python scripts/exp52_planner_baseline.py
"""
from __future__ import annotations

import collections
import itertools
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import v06_pipeline as P                                        # noqa: E402
from codec.manifest import run_manifest, wilson_ci               # noqa: E402
from foundation.kb import KB                                     # noqa: E402

SEED, MAX_STEPS, TOPK = 0, 4, 3
LABELS = {"P_CITES": "cites", "P_INTRODUCES": "introduces",
          "P_EVALUATES_ON": "evaluates on", "P_BUILDS_ON": "builds on",
          "P_COMPARES_TO": "compares to"}

world = json.loads((ROOT / "data" / "real_world_ai_hops.json").read_text())
facts, queries, hops = world["facts"], world["queries"], world["hops"]
HOLD = set(world["holdout_compositions"])
HELD_PH = set(world["held_out_phrasings"])
RELS = sorted({f["relation"] for f in facts})
Zq = np.load(ROOT / "results" / "real_world_ai_emb.npz")["Zq"]
Zh = np.load(ROOT / "results" / "real_world_ai_hop_emb.npz")["Zh"]
Zlab = np.load(ROOT / "results" / "exp24_label_emb.npz")["Zlab"]
RC = {r: Zlab[i] for i, r in enumerate(RELS)}
assert len(Zlab) == len(RELS), "label cache misaligned with the relation list"

kb = KB(backend="pg", table="poc")
gold = collections.defaultdict(set)
for c in kb.claims:
    if c["pid"] in RELS and c["page"].startswith("arxiv:"):
        gold[(c["subject"], c["pid"])].add(c["object"])
avail = collections.defaultdict(set)
for (s, r) in gold:
    avail[s].add(r)
print(f"{len(RELS)} relations, {len(hops)} hop questions, "
      f"held-out compositions {sorted(HOLD)}", flush=True)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

# identical head, identical training data, identical seed as exp24 — the only
# thing that varies across arms is how the predicted sum is turned into a walk
Xs, Ys = [], []
for i, q in enumerate(queries):
    if q["kind"] == "single" and q["phrasing_idx"] not in HELD_PH:
        Xs.append(Zq[i])
        Ys.append(RC[q["relation"]])
for i, h in enumerate(hops):
    if h["kind"] not in HOLD:
        Xs.append(Zh[i])
        Ys.append(RC[h["chain"][0]] + RC[h["chain"][1]])
X, Y = torch.tensor(np.stack(Xs)), torch.tensor(np.stack(Ys))
torch.manual_seed(SEED)
head = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, 1024))
opt = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-4)
for _ in range(40):
    for b in torch.randperm(len(X)).split(512):
        opt.zero_grad()
        ((head(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
        opt.step()
head.eval()
print(f"sum-head trained on {len(Xs)} rows (identical to exp24)", flush=True)

# every chain of length 1 or 2, with its coordinate sum precomputed
CHAINS = [c for k in (1, 2) for c in itertools.product(RELS, repeat=k)]
CHAIN_VEC = {c: sum(RC[r] for r in c) for c in CHAINS}
print(f"planner search space: {len(CHAINS)} chains over lengths 1-2")


def execute(subject, chain):
    """Follow a fixed chain from a subject; empty frontier means it died."""
    frontier = {subject}
    for r in chain:
        nxt = set()
        for s in frontier:
            nxt |= gold.get((s, r), set())
        if not nxt:
            return set()
        frontier = nxt
    return frontier


def walkable(subject, chain):
    """Would this chain survive execution? Used only by the store-filtered arm."""
    return bool(execute(subject, chain))


def fit(target, chain):
    """L2 to the un-normalised sum. Cosine would discard the depth cue."""
    return float(np.linalg.norm(target - CHAIN_VEC[chain]))


def plan_rank_permute(subject, target, thr):
    """P1 — D112: top-k relations by detection score, then permute."""
    scored = sorted(((float(target @ RC[r]), r) for r in RELS), reverse=True)
    cand = [r for _, r in scored[:TOPK]]
    best, best_d = None, thr
    for k in (1, 2):
        for c in itertools.permutations(cand, k):
            d = fit(target, c)
            if d < best_d:
                best, best_d = c, d
    return (list(best), execute(subject, best)) if best else ([], set())


def plan_exhaustive(subject, target, thr, store_filtered):
    """P2/P3 — enumerate every chain; optionally keep only walkable ones."""
    best, best_d = None, thr
    for c in CHAINS:
        if store_filtered and not walkable(subject, c):
            continue
        d = fit(target, c)
        if d < best_d:
            best, best_d = c, d
    return (list(best), execute(subject, best)) if best else ([], set())


def walk(subject, target, min_gain):
    """W — exp24's greedy residual walk, reproduced verbatim."""
    resid = target.copy()
    frontier, path = {subject}, []
    for _ in range(MAX_STEPS):
        options = set()
        for s in frontier:
            options |= avail.get(s, set())
        if not options:
            break
        best, best_g = None, min_gain
        for r in options:
            g = float(resid @ RC[r])
            if g > best_g:
                best, best_g = r, g
        if best is None:
            break
        nxt = set()
        for s in frontier:
            nxt |= gold.get((s, best), set())
        if not nxt:
            break
        frontier, path = nxt, path + [best]
        resid = resid - RC[best]
    return path, frontier


ARMS = {
    "W_walker": lambda s, t, p: walk(s, t, p),
    "P1_rank_permute": lambda s, t, p: plan_rank_permute(s, t, p),
    "P2_exhaustive_model_only": lambda s, t, p: plan_exhaustive(s, t, p, False),
    "P3_exhaustive_store_filtered": lambda s, t, p: plan_exhaustive(s, t, p, True),
}
# the walker's parameter is a per-step gain FLOOR; the planners' is a whole-chain
# distance CEILING, so they sweep opposite directions and cannot share a grid
GRID = {"W_walker": [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]}
for a in ARMS:
    if a != "W_walker":
        GRID[a] = [0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0]


def evaluate(arm, idxs, param):
    fn = ARMS[arm]
    with torch.no_grad():
        pr = head(torch.tensor(Zh[idxs])).numpy()
    tal, exact = collections.Counter(), 0
    by = {"A->A": collections.Counter(), "A->B": collections.Counter()}
    for j, i in enumerate(idxs):
        h = hops[i]
        shape = "A->A" if h["chain"][0] == h["chain"][1] else "A->B"
        path, got = fn(h["subject"], pr[j], param)
        exact += path == h["chain"]
        o = ("abstain" if (not path or not got) else
             ("correct" if facts[h["answer_fact"]]["object"] in got
              else "wrong"))
        tal[o] += 1
        by[shape][o] += 1
    n = max(sum(tal.values()), 1)
    a = tal["correct"] + tal["wrong"]
    return {"exact_chain": round(exact / n, 4),
            "correct": round(tal["correct"] / n, 4),
            "wrong": round(tal["wrong"] / n, 4),
            "abstain": round(tal["abstain"] / n, 4),
            # reported because the two populations differ in shape: seen holds
            # A->A chains and held-out holds none, and P1's `permutations`
            # structurally cannot emit (r, r) while `product` can. A threshold
            # tuned on seen is therefore tuned partly on a shape the eval set
            # does not contain.
            "by_shape": {k: {kk: round(vv / max(sum(by[k].values()), 1), 4)
                             for kk, vv in by[k].items()} for k in by},
            "n_by_shape": {k: sum(by[k].values()) for k in by},
            "precision": round(tal["correct"] / a, 4) if a else 0.0, "n": n}


held_i = [i for i, h in enumerate(hops) if h["kind"] in HOLD]
seen_i = [i for i, h in enumerate(hops) if h["kind"] not in HOLD]
rs = np.random.default_rng(SEED)
# 3000 because that is exp24's sample size, and the threshold rule is
# sensitive to it: on 1200 the walker's seen wrong-rate reads 0.022 against
# exp24's 0.0157, crosses the <= 0.02 bar, and the selection falls through to
# a grid endpoint that costs it half its accuracy. A tuning rule that flips
# on a resample is a finding about the rule, and it is reported below.
seen_s = sorted(rs.choice(seen_i, min(3000, len(seen_i)), replace=False))
print(f"held-out {len(held_i)}, seen sample {len(seen_s)}", flush=True)

# Reproduction check, and the whole point of this experiment applied to
# itself: exp24's walker number is the thing every arm is compared against,
# so verify it here rather than trusting it the way exp24 trusted exp18's.
EXP24 = json.loads((ROOT / "results" / "exp24_walker.json").read_text())
MG24 = EXP24["selected_min_gain"]
repro = evaluate("W_walker", held_i, MG24)
want = round(EXP24["selected"]["held_out"]["correct"], 4)
print(f"\nreproduction check — walker at exp24's min_gain={MG24}: "
      f"{repro['correct']:.4f} vs stored {want:.4f}")
assert abs(repro["correct"] - want) < 1e-3, (
    f"this script's walker does not reproduce exp24 ({repro['correct']:.4f} "
    f"vs {want:.4f}); every comparison below would be against a different "
    f"walker than the one the claim was made about")
print("  reproduces — the arms below are comparable to exp24's number")

results, chosen = {}, {}
for arm in ARMS:
    print(f"\n--- {arm}: threshold sweep on SEEN compositions only ---")
    sweep = {}
    for p in GRID[arm]:
        s_ = evaluate(arm, seen_s, p)
        sweep[p] = s_
        print(f"  param {p:<5} seen correct {s_['correct']:.3f}  "
              f"wrong {s_['wrong']:.3f}  abstain {s_['abstain']:.3f}",
              flush=True)
    # The walker's own pre-stated rule, applied identically to every arm:
    # most coverage subject to seen wrong <= 0.02. The walker's parameter is a
    # gain FLOOR so more coverage means the smallest; the planners' is a
    # distance CEILING so it means the largest.
    #
    # When nothing clears the bar, fall back to the LOWEST seen wrong-rate
    # rather than a grid endpoint. The first version fell back to an endpoint
    # and handed the walker its worst operating point the moment a resample
    # nudged its wrong-rate from 0.0157 to 0.022 — a comparison decided by the
    # fallback rather than by the arms.
    ok = [p for p in sorted(sweep) if sweep[p]["wrong"] <= 0.02]
    if ok:
        sel = min(ok) if arm == "W_walker" else max(ok)
    else:
        floor = min(sweep[p]["wrong"] for p in sweep)
        tied = [p for p in sorted(sweep) if sweep[p]["wrong"] == floor]
        sel = tied[0] if arm == "W_walker" else tied[-1]
        print(f"  (no param met wrong <= 0.02; fell back to the lowest "
              f"wrong-rate {floor:.4f} at {sel})")
    chosen[arm] = sel
    results[arm] = {"selected_param": sel, "seen": sweep[sel],
                    "held_out": evaluate(arm, held_i, sel),
                    "sweep_seen": {str(k): v for k, v in sweep.items()}}
    h = results[arm]["held_out"]
    print(f"  selected {sel} -> HELD-OUT correct {h['correct']:.3f}  "
          f"wrong {h['wrong']:.3f}  abstain {h['abstain']:.3f}  "
          f"exact-chain {h['exact_chain']:.3f}")

W = results["W_walker"]["held_out"]["correct"]
print(f"\n{'arm':32} {'held correct':>13} {'wrong':>7} {'exact':>7} "
      f"{'vs walker':>10}")
for arm in ARMS:
    h = results[arm]["held_out"]
    print(f"{arm:32} {h['correct']:13.4f} {h['wrong']:7.4f} "
          f"{h['exact_chain']:7.4f} {h['correct'] - W:+10.4f}")

lo, hi = wilson_ci(int(W * results["W_walker"]["held_out"]["n"]),
                   results["W_walker"]["held_out"]["n"])
best_planner = max((a for a in ARMS if a != "W_walker"),
                   key=lambda a: results[a]["held_out"]["correct"])
BP = results[best_planner]["held_out"]["correct"]
P2 = results["P2_exhaustive_model_only"]["held_out"]["correct"]
P3 = results["P3_exhaustive_store_filtered"]["held_out"]["correct"]
print(f"\nwalker {W:.4f} CI95 [{lo:.4f}, {hi:.4f}]; "
      f"best planner {best_planner} {BP:.4f}")
print(f"exp24 recorded the D112 planner as 0.534 — recomputed here at "
      f"{results['P1_rank_permute']['held_out']['correct']:.4f}")

# Order matters here, and the first version had it wrong: it tested the best
# planner first, so a STORE-FILTERED planner matching the walker printed "the
# model can plan without the store" — which is the opposite of what that arm
# shows. The model-only arm is the one that can refute the store's role.
if P2 >= lo:
    verdict = (f"REFUTED — model-only planning reaches {P2:.4f}, inside the "
               f"walker's CI. The store is not needed for order or depth.")
elif P3 >= lo:
    verdict = (f"REFUTED AS STATED, AND EXPLAINED — store-filtered planning "
               f"reaches {P3:.4f}, inside the walker's CI, while model-only "
               f"planning reaches {P2:.4f}. Walking step-by-step is NOT "
               f"required; consulting the store for what is walkable is. The "
               f"store's contribution is AVAILABILITY FILTERING, worth "
               f"{P3 - P2:+.4f}, and the walker's greediness is worth "
               f"{W - P3:+.4f}.")
else:
    verdict = (f"SURVIVES — no planner formulation reached the walker "
               f"({BP:.4f} vs {W:.4f}); the claim now rests on an "
               f"exhaustive search rather than one weak baseline.")
print(f"\n=== VERDICT ===\n  {verdict}")

out = {
    "manifest": run_manifest(seed=SEED, config={"MAX_STEPS": MAX_STEPS,
                                                "TOPK": TOPK,
                                                "labels": LABELS,
                                                "grid": GRID}),
    "n_relations": len(RELS), "n_chains_searched": len(CHAINS),
    "n_held_out": len(held_i), "n_seen_sample": len(seen_s),
    "results": results, "selected_params": chosen,
    "walker_correct": round(W, 4), "walker_ci95": [round(lo, 4), round(hi, 4)],
    "best_planner": best_planner, "best_planner_correct": round(BP, 4),
    "exp24_pasted_d112_value": 0.534,
    "d112_recomputed": results["P1_rank_permute"]["held_out"]["correct"],
    "verdict": verdict,
    "scope": ("Recomputes the D112 planner baseline IN-RUN, because exp24 "
              "stored it as a literal pasted from exp18 and the comparison "
              "therefore assumed identical scoring across two scripts. Four "
              "arms share one head, one seed, one question set and one "
              "scorer; only the way a predicted sum becomes a walk varies. "
              "P2 vs P3 is the decomposition that matters: both enumerate "
              "every chain, and only P3 may consult the store for which "
              "chains are walkable, so the difference between them IS the "
              "store's contribution. Fit is L2 against the un-normalised sum "
              "because magnitude encodes depth. Every arm gets an abstain "
              "threshold swept on SEEN compositions only and selected by the "
              "walker's own pre-stated rule (law #6); denying the planners "
              "an abstain mechanism the walker has would build a strawman."),
}
(ROOT / "results" / "exp52_planner_baseline.json").write_text(
    json.dumps(out, indent=1))
print("\n[done] results/exp52_planner_baseline.json")
