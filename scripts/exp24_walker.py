"""Per-step residual walker: let the STORE decide order and depth (D117).

The longest-standing gap since D112. Everything in D113-D116 was single-hop,
and the path-planning formulation it replaces has three known defects, all
measured:

  * D111 — a multi-label relation vector is a SET; it cannot say "twice",
    and A->A is 79% of real 2-hop shapes.
  * D112 — ORDER does not transfer to unseen compositions. Three mechanisms
    failed: an additive prototype is order-blind by construction, asymmetric
    scalars scored 0.460 (BELOW chance, having learned relation salience
    rather than position), and position-specific heads memorised at 1.000
    and transferred at 0.513.
  * D112 — depth is a CLASS (the arity head), so 3-hop would be R^3.

The one thing that has ever delivered order on real data is the store
itself: D111's entity-level `path_ok` lifted held-out composition accuracy
from ~0.41 to 0.534 by discarding paths that are not walkable for that
subject.

So this stops asking the query for order at all:

  1. predict ONE point = the SUM of the relation coordinates involved
     (order-free by construction — D112 proved that is all the query
     reliably carries);
  2. at each step, among only the relations actually available from the
     current frontier, take the one best matching the RESIDUAL;
  3. subtract it and continue; stop when no available relation improves the
     match.

Order comes from walkability, depth from when the residual is spent — so
neither is a trained class, and both are unbounded. Relation coordinates are
label embeddings, so the vocabulary stays open (D113/D116).

Evaluated on D111's hops world against the same held-out compositions, so
the baseline is directly comparable: 0.534 correct / 0.433 wrong.

Usage: .venv/bin/python scripts/exp24_walker.py
"""
from __future__ import annotations

import collections
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

SEED, MAX_STEPS = 0, 4
LABELS = {"P_CITES": "cites", "P_INTRODUCES": "introduces",
          "P_EVALUATES_ON": "evaluates on", "P_BUILDS_ON": "builds on",
          "P_COMPARES_TO": "compares to"}

world = json.loads((ROOT / "data" / "real_world_ai_hops.json").read_text())
facts, queries, hops = world["facts"], world["queries"], world["hops"]
HOLD = set(world["holdout_compositions"])
HELD_PH = set(world["held_out_phrasings"])
RELS = sorted({f["relation"] for f in facts})
d = np.load(ROOT / "results" / "real_world_ai_emb.npz")
Zq = d["Zq"]
Zh = np.load(ROOT / "results" / "real_world_ai_hop_emb.npz")["Zh"]

lcache = ROOT / "results" / "exp24_label_emb.npz"
if lcache.exists():
    Zlab = np.load(lcache)["Zlab"]
else:
    Zlab = P.unit(P.embed_texts([LABELS[r] for r in RELS]))
    np.savez(lcache, Zlab=Zlab)
RC = {r: Zlab[i] for i, r in enumerate(RELS)}     # relation coordinates
print(f"{len(RELS)} relations, {len(hops)} hop questions, "
      f"held-out compositions {sorted(HOLD)}", flush=True)

kb = KB(backend="pg", table="poc")
gold = collections.defaultdict(set)
for c in kb.claims:
    if c["pid"] in RELS and c["page"].startswith("arxiv:"):
        gold[(c["subject"], c["pid"])].add(c["object"])
# What relations are available from a frontier — the adjacency index is what
# makes this O(neighbourhood) rather than O(corpus).
avail = collections.defaultdict(set)
for (s, r) in gold:
    avail[s].add(r)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

# Train the SUM head on singles (seen phrasings) + seen compositions only.
Xs, Ys = [], []
for i, q in enumerate(queries):
    if q["kind"] == "single" and q["phrasing_idx"] not in HELD_PH:
        Xs.append(Zq[i])
        Ys.append(RC[q["relation"]])
for i, h in enumerate(hops):
    if h["kind"] not in HOLD:
        Xs.append(Zh[i])
        Ys.append(RC[h["chain"][0]] + RC[h["chain"][1]])
X = torch.tensor(np.stack(Xs))
Y = torch.tensor(np.stack(Ys))
torch.manual_seed(SEED)
head = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, 1024))
opt = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-4)
for _ in range(40):
    for b in torch.randperm(len(X)).split(512):
        opt.zero_grad()
        # MSE on the UN-normalised sum. A cosine loss is scale-invariant and
        # would throw away exactly the magnitude that encodes "twice" — the
        # first version of this experiment did that and reproduced D111's
        # same-relation failure verbatim.
        ((head(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
        opt.step()
head.eval()
print(f"sum-head trained on {len(Xs)} rows "
      f"(singles + seen compositions only)", flush=True)


def walk(subject, target, min_gain):
    """Greedy residual walk. Order and depth both come from the store."""
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
            break                      # residual spent: STOP
        nxt = set()
        for s in frontier:
            nxt |= gold.get((s, best), set())
        if not nxt:
            break
        frontier, path = nxt, path + [best]
        resid = resid - RC[best]      # one unit, so repeats survive
    return path, frontier


def evaluate(idxs, min_gain, label):
    with torch.no_grad():
        pr = head(torch.tensor(Zh[idxs])).numpy()   # magnitude is meaningful
    tal = collections.Counter()
    by = {"A->A": collections.Counter(), "A->B": collections.Counter()}
    exact = 0
    for j, i in enumerate(idxs):
        h = hops[i]
        shape = "A->A" if h["chain"][0] == h["chain"][1] else "A->B"
        path, got = walk(h["subject"], pr[j], min_gain)
        exact += path == h["chain"]
        o = ("abstain" if (not path or not got) else
             ("correct" if facts[h["answer_fact"]]["object"] in got
              else "wrong"))
        tal[o] += 1
        by[shape][o] += 1
    n = sum(tal.values())
    a = tal["correct"] + tal["wrong"]
    return {"exact_chain": exact / n, "correct": tal["correct"] / n,
            "by_shape": {k: {kk: vv / max(sum(by[k].values()), 1)
                             for kk, vv in by[k].items()}
                         for k in by},
            "wrong": tal["wrong"] / n, "abstain": tal["abstain"] / n,
            "precision": tal["correct"] / a if a else 0.0, "n": n}


held_i = [i for i, h in enumerate(hops) if h["kind"] in HOLD]
seen_i = [i for i, h in enumerate(hops) if h["kind"] not in HOLD]
rs = np.random.default_rng(SEED)
seen_s = list(rs.choice(seen_i, min(3000, len(seen_i)), replace=False))

# `min_gain` is the stop threshold: how much a relation must explain of the
# remaining residual to be worth walking. Chosen on SEEN compositions ONLY —
# and per audit law #6 that population must actually exhibit the failure, so
# its wrong-rate is printed alongside rather than assumed.
print(f"\nstop-threshold sweep (chosen on SEEN compositions)")
print(f"{'min_gain':>9} {'seen corr':>10} {'seen wrong':>11} "
      f"{'held corr':>10} {'held wrong':>11} {'held prec':>10}")
sweep = {}
for mg in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
    s_ = evaluate(seen_s, mg, "seen")
    h_ = evaluate(held_i, mg, "held")
    sweep[mg] = {"seen": s_, "held": h_}
    print(f"{mg:9.2f} {s_['correct']:10.3f} {s_['wrong']:11.3f} "
          f"{h_['correct']:10.3f} {h_['wrong']:11.3f} {h_['precision']:10.3f}",
          flush=True)

# Same pre-stated rule as D110/D111: smallest threshold whose SEEN wrong-rate
# is <= 0.02.
MG = next((mg for mg in sorted(sweep) if sweep[mg]["seen"]["wrong"] <= 0.02),
          max(sweep))
S, H = sweep[MG]["seen"], sweep[MG]["held"]
print(f"\nselected min_gain={MG} (smallest with seen wrong <= 0.02)")
for tag, D in (("seen", S), ("HELD-OUT", H)):
    for shape, c in D["by_shape"].items():
        if c:
            print(f"  {tag:9s} {shape}  correct {c.get('correct',0):.3f}  "
                  f"wrong {c.get('wrong',0):.3f}  "
                  f"abstain {c.get('abstain',0):.3f}")
print(f"  seen compositions   exact {S['exact_chain']:.3f}  correct "
      f"{S['correct']:.3f}  wrong {S['wrong']:.3f}  abstain {S['abstain']:.3f}")
print(f"  HELD-OUT comps      exact {H['exact_chain']:.3f}  correct "
      f"{H['correct']:.3f}  wrong {H['wrong']:.3f}  abstain {H['abstain']:.3f}"
      f"  precision {H['precision']:.3f}")
lo, hi = wilson_ci(int(H["correct"] * H["n"]), H["n"])
print(f"  held-out correct CI95 [{lo:.3f}, {hi:.3f}]")
print(f"\n[D158] the D112 planner baseline this script used to quote here "
      f"(0.534) was pasted from exp18 and is NOT comparable: recomputed "
      f"in-run on these questions it scores 0.8138. See "
      f"results/exp52_planner_baseline.json.")

out = {
    "manifest": run_manifest(seed=SEED, config={"MAX_STEPS": MAX_STEPS,
                                                "labels": LABELS}),
    "selected_min_gain": MG, "sweep": {str(k): v for k, v in sweep.items()},
    "selected": {"seen": S, "held_out": H},
    "held_out_correct_ci95": [round(lo, 4), round(hi, 4)],
    # D158: this used to hold {"correct": 0.534, ...} as a literal pasted
    # from exp18 and compared as though the two scripts shared a protocol.
    # Recomputed in-run, D112's formulation scores 0.8138 on these questions,
    # so the gap this experiment reported was inflated almost fourfold. The
    # value is withdrawn rather than corrected in place: exp52 computes it.
    "baseline_d112_path_planner": {
        "WITHDRAWN": "pasted from exp18, not comparable; see D158",
        "recomputed_in_exp52": 0.8138,
        "source": "results/exp52_planner_baseline.json"},
    "scope": ("Order and depth come from the store, not from a trained "
              "class: the head predicts one order-free SUM of relation "
              "coordinates, and the walk takes the best AVAILABLE relation "
              "against the residual at each step. Held-out compositions were "
              "never trained. Relation coordinates are label embeddings, so "
              "the vocabulary is open. Same hops world and held-out "
              "compositions as D111/D112."),
}
(ROOT / "results" / "exp24_walker.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp24_walker.json")

# ---------------------------------------------------------------------------
# Honesty check on the metric. "Correct" means the gold object is IN the
# returned frontier, and a walk over a high-fan-out relation like P_CITES can
# return a large set — in which case containing the right answer is weak
# evidence. D111/D112 scored the same way so the comparison is fair, but the
# absolute number is only meaningful alongside the set sizes it was won with.
# ---------------------------------------------------------------------------
def sizes(idxs, min_gain):
    with torch.no_grad():
        pr = head(torch.tensor(Zh[idxs])).numpy()
    ns, hit_small = [], collections.Counter()
    for j, i in enumerate(idxs):
        h = hops[i]
        _, got = walk(h["subject"], pr[j], min_gain)
        ns.append(len(got))
        if got:
            ok = facts[h["answer_fact"]]["object"] in got
            for cap in (1, 5, 20):
                if len(got) <= cap and ok:
                    hit_small[cap] += 1
    n = len(idxs)
    return (float(np.mean(ns)), float(np.median(ns)),
            {c: hit_small[c] / n for c in (1, 5, 20)})


print("\nanswer-set sizes at the selected threshold")
for tag, idxs in (("seen", seen_s), ("HELD-OUT", held_i)):
    mean_n, med_n, small = sizes(idxs, MG)
    print(f"  {tag:9s} mean |answer| {mean_n:7.1f}  median {med_n:5.0f}   "
          f"correct AND |answer|<=1 {small[1]:.3f}  <=5 {small[5]:.3f}  "
          f"<=20 {small[20]:.3f}")
    out.setdefault("answer_sets", {})[tag] = {
        "mean": round(mean_n, 2), "median": med_n,
        "correct_and_within": {str(k): round(v, 4) for k, v in small.items()}}
(ROOT / "results" / "exp24_walker.json").write_text(json.dumps(out, indent=1))
print("[done] answer-set diagnostics appended")
