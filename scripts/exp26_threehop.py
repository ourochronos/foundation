"""Depth 3: is depth really unbounded, and does refusal survive it? (D119)

D117 claimed depth is not a trained class — the walk stops when the residual
is spent, so 3-hop should be a longer walk rather than R^3. That claim has
never been tested. D118 added refusal but calibrated it entirely at depth 2.

Two things are on trial, and they can fail independently:

  1. DEPTH EXTRAPOLATION. The sum head has only ever seen targets of
     magnitude ~1 (singles) and ~2 (2-hop). A 3-hop target has magnitude ~3,
     which is extrapolation, not interpolation. The headline condition
     therefore trains on NO 3-hop data at all — if depth is genuinely
     unbounded, that has to work. A second condition trains on some 3-hop
     compositions and holds others out, to separate "cannot extrapolate
     magnitude" from "cannot do 3 hops".

  2. REFUSAL AT DEPTH. Unanswerable 3-hops are built GRADED by where the
     chain dies:
       break@2 — first relation walkable, second yields nothing
       break@3 — first two walkable, third yields nothing   <- the hard one,
                 because two thirds of the residual is legitimately spent
                 before the walk stalls, so the unexplained signal is small
     Chains with no first hop at all are excluded, per D118: the walker
     abstains on those trivially and they inflate the refusal rate for free.

D118's threshold (0.40) was calibrated at depth 2 and is applied here
UNCHANGED, because whether a refusal threshold transfers across depth is
exactly the question audit laws #6 and #7 tell us not to assume.

Usage: .venv/bin/python scripts/exp26_threehop.py
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

SEED, MAX_STEPS, MIN_GAIN = 0, 5, 0.2
D118_THR = 0.40
CAP_ANS, CAP_UNANS = 4000, 3000

NP1 = {"P_CITES": "the works {s} cites",
       "P_INTRODUCES": "the method introduced by {s}",
       "P_BUILDS_ON": "what {s} builds on",
       "P_COMPARES_TO": "the baselines {s} compares against",
       "P_EVALUATES_ON": "the benchmarks {s} evaluates on"}
NP2 = {"P_CITES": "the works cited by {np}",
       "P_INTRODUCES": "the methods introduced by {np}",
       "P_BUILDS_ON": "what {np} build on",
       "P_COMPARES_TO": "the baselines {np} compare against",
       "P_EVALUATES_ON": "the benchmarks {np} evaluate on"}
Q = {"P_CITES": "What do {np} cite?",
     "P_INTRODUCES": "What do {np} introduce?",
     "P_BUILDS_ON": "What do {np} build on?",
     "P_COMPARES_TO": "What do {np} compare against?",
     "P_EVALUATES_ON": "What do {np} evaluate on?"}

world = json.loads((ROOT / "data" / "real_world_ai_hops.json").read_text())
facts, queries, hops = world["facts"], world["queries"], world["hops"]
HOLD2 = set(world["holdout_compositions"])
HELD_PH = set(world["held_out_phrasings"])
RELS = sorted({f["relation"] for f in facts})
Zq = np.load(ROOT / "results" / "real_world_ai_emb.npz")["Zq"]
Zh = np.load(ROOT / "results" / "real_world_ai_hop_emb.npz")["Zh"]
Zlab = np.load(ROOT / "results" / "exp24_label_emb.npz")["Zlab"]
RC = {r: Zlab[i] for i, r in enumerate(RELS)}

kb = KB(backend="pg", table="poc")
gold = collections.defaultdict(set)
for c in kb.claims:
    if c["pid"] in RELS and c["page"].startswith("arxiv:"):
        gold[(c["subject"], c["pid"])].add(c["object"])
avail = collections.defaultdict(set)
for (s, r) in gold:
    avail[s].add(r)


def step(nodes, r):
    out = set()
    for s in nodes:
        out |= gold.get((s, r), set())
    return out


def text3(s, chain):
    r1, r2, r3 = chain
    return Q[r3].format(np=NP2[r2].format(np=NP1[r1].format(s=s)))


# ---- answerable 3-hop chains, enumerated from the store ----
rng = np.random.default_rng(SEED)
subjects = sorted(avail)
ans3 = []
for s in subjects:
    for r1 in sorted(avail[s]):
        m1 = step({s}, r1)
        if not m1:
            continue
        rs2 = sorted(set().union(*(avail.get(x, set()) for x in m1)))
        for r2 in rs2:
            m2 = step(m1, r2)
            if not m2:
                continue
            rs3 = sorted(set().union(*(avail.get(x, set()) for x in m2)))
            for r3 in rs3:
                m3 = step(m2, r3)
                if m3:
                    ans3.append({"chain": [r1, r2, r3], "subject": s,
                                 "answers": sorted(m3)[:200],
                                 "text": text3(s, [r1, r2, r3])})
print(f"{len(ans3)} answerable 3-hop questions enumerated", flush=True)
kinds3 = collections.Counter(">".join(a["chain"]) for a in ans3)
print(f"  over {len(kinds3)} distinct 3-compositions; top: "
      f"{kinds3.most_common(4)}")
if len(ans3) > CAP_ANS:
    ans3 = [ans3[i] for i in rng.choice(len(ans3), CAP_ANS, replace=False)]

# ---- unanswerable 3-hops, graded by where the chain dies ----
unans = {"break@2": [], "break@3": []}
for s in subjects:
    for r1 in sorted(avail[s]):
        m1 = step({s}, r1)
        if not m1:
            continue
        for r2 in RELS:
            m2 = step(m1, r2)
            if not m2:
                for r3 in RELS:                       # dies at hop 2
                    unans["break@2"].append(
                        {"chain": [r1, r2, r3], "subject": s,
                         "text": text3(s, [r1, r2, r3])})
                continue
            for r3 in RELS:
                if not step(m2, r3):                  # dies at hop 3
                    unans["break@3"].append(
                        {"chain": [r1, r2, r3], "subject": s,
                         "text": text3(s, [r1, r2, r3])})
for k in unans:
    if len(unans[k]) > CAP_UNANS:
        idx = rng.choice(len(unans[k]), CAP_UNANS, replace=False)
        unans[k] = [unans[k][i] for i in idx]
    print(f"{len(unans[k])} unanswerable ({k})")

cache = ROOT / "results" / "exp26_emb.npz"
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    Za, Zb2, Zb3 = z["Za"], z["Zb2"], z["Zb3"]
    # A LENGTH check is not enough: set iteration over strings depends on
    # per-process hash randomisation, so a rebuilt list can have the same
    # items in a different ORDER and silently misalign with its embeddings.
    # Compare the texts themselves.
    assert list(z["ta"]) == [a["text"] for a in ans3], "cache misaligned"
    assert list(z["tb2"]) == [u["text"] for u in unans["break@2"]], "misaligned"
    assert list(z["tb3"]) == [u["text"] for u in unans["break@3"]], "misaligned"
else:
    Za = P.unit(P.embed_texts([a["text"] for a in ans3]))
    Zb2 = P.unit(P.embed_texts([u["text"] for u in unans["break@2"]]))
    Zb3 = P.unit(P.embed_texts([u["text"] for u in unans["break@3"]]))
    np.savez(cache, Za=Za, Zb2=Zb2, Zb3=Zb3,
             ta=np.array([a["text"] for a in ans3]),
             tb2=np.array([u["text"] for u in unans["break@2"]]),
             tb3=np.array([u["text"] for u in unans["break@3"]]))
print(f"embeddings {Za.shape} answerable", flush=True)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402


def train(include_3hop_kinds):
    Xs, Ys = [], []
    for i, q in enumerate(queries):
        if q["kind"] == "single" and q["phrasing_idx"] not in HELD_PH:
            Xs.append(Zq[i])
            Ys.append(RC[q["relation"]])
    for i, h in enumerate(hops):
        if h["kind"] not in HOLD2:
            Xs.append(Zh[i])
            Ys.append(RC[h["chain"][0]] + RC[h["chain"][1]])
    n3 = 0
    for j, a in enumerate(ans3):
        if ">".join(a["chain"]) in include_3hop_kinds:
            Xs.append(Za[j])
            Ys.append(sum(RC[r] for r in a["chain"]))
            n3 += 1
    X, Y = torch.tensor(np.stack(Xs)), torch.tensor(np.stack(Ys))
    torch.manual_seed(SEED)
    hd = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, 1024))
    opt = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(X)).split(512):
            opt.zero_grad()
            ((hd(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
            opt.step()
    hd.eval()
    return hd, n3


def walk(subject, target):
    resid, frontier, path = target.copy(), {subject}, []
    for _ in range(MAX_STEPS):
        options = set()
        for s in frontier:
            options |= avail.get(s, set())
        best, best_g = None, MIN_GAIN
        for r in options:
            g = float(resid @ RC[r])
            if g > best_g:
                best, best_g = r, g
        if best is None:
            break
        nxt = step(frontier, best)
        if not nxt:
            break
        frontier, path = nxt, path + [best]
        resid = resid - RC[best]
    return path, frontier, (float(np.linalg.norm(resid))
                            / (float(np.linalg.norm(target)) + 1e-9))


def run(hd, rows, Z, thr, answerable, eval_kinds=None):
    with torch.no_grad():
        pr = hd(torch.tensor(Z)).numpy()
    c = collections.Counter()
    mags, exact = [], 0
    for j, a in enumerate(rows):
        if eval_kinds is not None and ">".join(a["chain"]) not in eval_kinds:
            continue
        mags.append(float(np.linalg.norm(pr[j])))
        path, got, unexp = walk(a["subject"], pr[j])
        if not path or not got or unexp > thr:
            c["abstain"] += 1
            continue
        if not answerable:
            c["wrong"] += 1
            continue
        exact += path == a["chain"]
        c["correct" if set(got) & set(a["answers"]) else "wrong"] += 1
    n = max(sum(c.values()), 1)
    return {"n": n, "correct": c["correct"] / n, "wrong": c["wrong"] / n,
            "abstain": c["abstain"] / n, "exact_chain": exact / n,
            "pred_magnitude_mean": float(np.mean(mags)) if mags else 0.0}


ALLK = sorted(kinds3)
rk = list(np.random.default_rng(1).permutation(ALLK))
HOLD3 = set(rk[: max(1, len(rk) // 3)])
print(f"\n{len(ALLK)} 3-compositions; {len(HOLD3)} held out when training "
      f"on 3-hop")

for tag, inc, evalk in (
        ("ZERO-SHOT DEPTH (no 3-hop trained)", set(), None),
        ("trained on 2/3 of 3-compositions", set(ALLK) - HOLD3, HOLD3)):
    hd, n3 = train(inc)
    A = run(hd, ans3, Za, D118_THR, True, evalk)
    B2 = run(hd, unans["break@2"], Zb2, D118_THR, False)
    B3 = run(hd, unans["break@3"], Zb3, D118_THR, False)
    print(f"\n=== {tag} ({n3} 3-hop training rows) ===")
    print(f"  predicted |target| on 3-hop questions: "
          f"{A['pred_magnitude_mean']:.2f}   (singles ~1.0, 2-hop ~1.7 "
          f"after summing unit vectors)")
    print(f"  ANSWERABLE 3-hop   correct {A['correct']:.3f}  "
          f"wrong {A['wrong']:.3f}  abstain {A['abstain']:.3f}  "
          f"exact chain {A['exact_chain']:.3f}  (n={A['n']})")
    print(f"  UNANS break@2      refused {B2['abstain']:.3f}  "
          f"answered {B2['wrong']:.3f}  (n={B2['n']})")
    print(f"  UNANS break@3      refused {B3['abstain']:.3f}  "
          f"answered {B3['wrong']:.3f}  (n={B3['n']})")
    globals()[f"RES_{tag[:4]}"] = (A, B2, B3)

A0, B20, B30 = globals()["RES_ZERO"]
A1, B21, B31 = globals()["RES_trai"]
lo, hi = wilson_ci(int(A0["correct"] * A0["n"]), A0["n"])
print(f"\nzero-shot-depth answerable correct CI95 [{lo:.3f}, {hi:.3f}]")
print(f"depth-2 reference (D118): answerable correct 0.881 / wrong 0.071, "
      f"unanswerable refused 0.970, at this same threshold {D118_THR}")

out = {
    "manifest": run_manifest(seed=SEED, config={"MIN_GAIN": MIN_GAIN,
                                                "MAX_STEPS": MAX_STEPS,
                                                "d118_threshold": D118_THR}),
    "n_answerable": len(ans3), "n_3compositions": len(ALLK),
    "held_out_3compositions": sorted(HOLD3),
    "zero_shot_depth": {"answerable": A0, "unans_break2": B20,
                        "unans_break3": B30},
    "trained_on_3hop": {"answerable_heldout_kinds": A1,
                        "unans_break2": B21, "unans_break3": B31},
    "depth2_reference_d118": {"correct": 0.881, "wrong": 0.071,
                              "unans_refused": 0.970},
    "scope": ("D118's threshold (0.40, calibrated at depth 2) applied "
              "UNCHANGED, to test whether a refusal threshold transfers "
              "across depth. Unanswerable 3-hops are graded by where the "
              "chain dies; chains with no first hop are excluded per D118. "
              "Answerable correctness is set-overlap with the true 3-hop "
              "answer set, same lenient convention as D111-D118."),
}
(ROOT / "results" / "exp26_threehop.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp26_threehop.json")

# ---------------------------------------------------------------------------
# Refusal failed on break@3 (0.267 refused) while catching break@2 (0.907).
# The mechanism is not subtle: D118 thresholds the FRACTION of the residual
# left unexplained, and that fraction is depth-dependent. One missing hop
# out of two leaves ~1/2 unexplained; one missing hop out of three leaves
# ~1/3. A threshold tuned at depth 2 cannot fire at depth 3.
#
# But "one missing hop" is one missing UNIT VECTOR at every depth. So the
# scale-free quantity is the ABSOLUTE residual norm, not the fraction. This
# tests one absolute threshold across BOTH depths — including re-checking
# D118's depth-2 populations, because a fix that quietly breaks the result
# it was derived from is not a fix.
# ---------------------------------------------------------------------------
hd0, _ = train(set())


def abs_run(hd, rows, Z, thr, answerable, subj_key="subject"):
    with torch.no_grad():
        pr = hd(torch.tensor(Z)).numpy()
    c = collections.Counter()
    for j, a in enumerate(rows):
        path, got, _f = walk(a[subj_key], pr[j])
        resid_abs = float(np.linalg.norm(
            pr[j] - sum(RC[r] for r in path))) if path else float(
                np.linalg.norm(pr[j]))
        if not path or not got or resid_abs > thr:
            c["abstain"] += 1
        elif not answerable:
            c["wrong"] += 1
        else:
            c["correct" if set(got) & set(a["answers"]) else "wrong"] += 1
    n = max(sum(c.values()), 1)
    return {"correct": c["correct"] / n, "wrong": c["wrong"] / n,
            "abstain": c["abstain"] / n, "n": n}


# depth-2 populations, rebuilt exactly as D118 so the check is like-for-like
h2 = [h for h in hops if h["kind"] in HOLD2]
Zh2 = Zh[[i for i, h in enumerate(hops) if h["kind"] in HOLD2]]
for h in h2:
    h["answers"] = [facts[h["answer_fact"]]["object"]]
u2 = json.loads((ROOT / "results" / "exp25_refusal.json").read_text())
Zu2 = np.load(ROOT / "results" / "exp25_unans_emb.npz")["Zu"]

print("\nABSOLUTE residual threshold — one number across both depths")
print(f"{'thr':>5} | {'d2 ans corr':>11} {'d2 UNANS ref':>12} | "
      f"{'d3 ans corr':>11} {'d3 brk@2 ref':>12} {'d3 brk@3 ref':>12}")
best_abs = None
for t in (0.4, 0.6, 0.8, 1.0, 1.2, 1.4):
    a2 = abs_run(hd0, h2, Zh2, t, True)
    a3 = abs_run(hd0, ans3, Za, t, True)
    b2 = abs_run(hd0, unans["break@2"], Zb2, t, False)
    b3 = abs_run(hd0, unans["break@3"], Zb3, t, False)
    print(f"{t:5.1f} | {a2['correct']:11.3f} {'—':>12} | "
          f"{a3['correct']:11.3f} {b2['abstain']:12.3f} {b3['abstain']:12.3f}")
    if best_abs is None and b3["abstain"] >= 0.80:
        best_abs = (t, a2, a3, b2, b3)

if best_abs:
    t, a2, a3, b2, b3 = best_abs
    print(f"\nselected absolute threshold {t} "
          f"(smallest with break@3 refusal >= 0.80)")
    print(f"  depth-2 answerable  correct {a2['correct']:.3f}  "
          f"wrong {a2['wrong']:.3f}  abstain {a2['abstain']:.3f}")
    print(f"  depth-3 answerable  correct {a3['correct']:.3f}  "
          f"wrong {a3['wrong']:.3f}  abstain {a3['abstain']:.3f}")
    print(f"  break@2 refused {b2['abstain']:.3f}   "
          f"break@3 refused {b3['abstain']:.3f}")
    out["absolute_threshold"] = {"threshold": t, "depth2_answerable": a2,
                                 "depth3_answerable": a3,
                                 "unans_break2": b2, "unans_break3": b3}
else:
    print("\nno absolute threshold reached 0.80 refusal on break@3")
    out["absolute_threshold"] = None
(ROOT / "results" / "exp26_threehop.json").write_text(json.dumps(out, indent=1))
print("[done] absolute-threshold results appended")

# ---------------------------------------------------------------------------
# Neither threshold works, and the sweep says why: at depth 3 the head
# UNDER-predicts magnitude (2.05 where ~3 is right, having only ever seen
# ~1 and ~2). A correct 3-hop walk therefore ends with an absolute residual
# about the size of a genuinely broken one, so the two are not separable.
# The fractional measure hides this by being scale-invariant, which is
# exactly why it stops firing as depth grows.
#
# That predicts the fix is not a threshold at all: give the head depth-3
# magnitudes and the residual should separate again. Testing that
# distinguishes "refusal cannot survive depth" from "refusal needs to have
# SEEN the depth" — very different claims, and only the second is fixable
# by data.
# ---------------------------------------------------------------------------
hd3, _n = train(set(ALLK) - HOLD3)
print("\nsame sweeps with the 3-hop-TRAINED head (held-out 3-compositions "
      "only for answerable)")
print(f"{'thr':>5} | {'d3 ans corr':>11} {'d3 brk@2 ref':>12} "
      f"{'d3 brk@3 ref':>12}   [absolute residual]")
hk = [a for a in ans3 if ">".join(a["chain"]) in HOLD3]
Zhk = Za[[j for j, a in enumerate(ans3) if ">".join(a["chain"]) in HOLD3]]
rows_abs = {}
for t in (0.6, 0.8, 1.0, 1.2, 1.4):
    a3 = abs_run(hd3, hk, Zhk, t, True)
    b2 = abs_run(hd3, unans["break@2"], Zb2, t, False)
    b3 = abs_run(hd3, unans["break@3"], Zb3, t, False)
    rows_abs[t] = {"ans": a3, "b2": b2, "b3": b3}
    print(f"{t:5.1f} | {a3['correct']:11.3f} {b2['abstain']:12.3f} "
          f"{b3['abstain']:12.3f}")
sep = {t: rows_abs[t]["ans"]["correct"] + rows_abs[t]["b3"]["abstain"]
       for t in rows_abs}
bt = max(sep, key=sep.get)
print(f"\nbest joint operating point thr={bt}: answerable "
      f"{rows_abs[bt]['ans']['correct']:.3f} correct, break@3 refused "
      f"{rows_abs[bt]['b3']['abstain']:.3f}, break@2 refused "
      f"{rows_abs[bt]['b2']['abstain']:.3f}")
out["threehop_trained_absolute"] = {str(k): v for k, v in rows_abs.items()}
out["threehop_trained_best_thr"] = bt
(ROOT / "results" / "exp26_threehop.json").write_text(json.dumps(out, indent=1))
print("[done] 3-hop-trained absolute sweep appended")
