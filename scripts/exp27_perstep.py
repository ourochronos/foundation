"""Per-step refusal: refuse when a REQUIRED relation was never walked (D120).

D119 scoped refusal to depth 2. The global residual conflates two things —
"the store could not answer this" and "the head mis-estimated the magnitude"
— and the second term grows with depth, so no threshold on it (fractional or
absolute) separates a correct 3-hop walk from one that died at the last hop.

The fix stops asking magnitude to carry the signal at all. Two mechanisms,
each used for what it has been measured to be good at:

  SUM head (D117)      — direction and order. Order comes from walkability,
                         which is the one thing that has ever worked on real
                         data.
  PRESENCE head (new)  — a per-relation multi-label score: which relations
                         does this question REQUIRE? This is D110's detection
                         head reused, and D112 showed its recall is strong
                         (both relations in the top-2 on 81.7% of held-out
                         compositions). Its weakness was ORDER, and this
                         design never asks it for order.

Refusal rule: **refuse if a relation the question requires was never
walked.** Scale-free by construction — presence is an independent sigmoid
per relation, not a magnitude — so it should not decay with depth the way
D119's residual did. That is the claim under test.

Evaluated at BOTH depths on all five populations, with a SINGLE threshold,
because a refusal rule that needs re-tuning per depth is what D119 already
rejected.

Usage: .venv/bin/python scripts/exp27_perstep.py
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

world = json.loads((ROOT / "data" / "real_world_ai_hops.json").read_text())
facts, queries, hops = world["facts"], world["queries"], world["hops"]
HOLD2 = set(world["holdout_compositions"])
HELD_PH = set(world["held_out_phrasings"])
RELS = sorted({f["relation"] for f in facts})
ridx = {r: i for i, r in enumerate(RELS)}
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


# Populations rebuilt inline — same construction as D118/D119, so every
# number here is comparable to those runs. The templates must match exactly
# or the cached embeddings are meaningless, which the asserts below check.
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
Q3 = {"P_CITES": "What do {np} cite?",
      "P_INTRODUCES": "What do {np} introduce?",
      "P_BUILDS_ON": "What do {np} build on?",
      "P_COMPARES_TO": "What do {np} compare against?",
      "P_EVALUATES_ON": "What do {np} evaluate on?"}
NPa = {"P_CITES": ["the works {s} cites", "the papers referenced by {s}"],
       "P_INTRODUCES": ["the method introduced by {s}", "what {s} proposes"],
       "P_BUILDS_ON": ["what {s} builds on", "the model {s} is based on"],
       "P_COMPARES_TO": ["the baselines {s} compares against",
                         "the systems {s} is measured against"],
       "P_EVALUATES_ON": ["the benchmarks {s} evaluates on",
                          "the datasets {s} is tested on"]}
Qa = {"P_CITES": ["What do {np} cite?", "What prior work do {np} draw on?"],
      "P_INTRODUCES": ["What do {np} introduce?",
                       "What method do {np} propose?"],
      "P_BUILDS_ON": ["What do {np} build on?", "What are {np} based on?"],
      "P_COMPARES_TO": ["What do {np} compare against?",
                        "Which baselines do {np} use?"],
      "P_EVALUATES_ON": ["What do {np} evaluate on?",
                         "Which datasets are {np} tested on?"]}
CAP_ANS, CAP_UNANS = 4000, 3000
rng = np.random.default_rng(SEED)
subjects = sorted(avail)

ans3 = []
for s in subjects:
    for r1 in sorted(avail[s]):
        m1 = step({s}, r1)
        if not m1:
            continue
        for r2 in sorted(set().union(*(avail.get(x, set()) for x in m1))):
            m2 = step(m1, r2)
            if not m2:
                continue
            for r3 in sorted(set().union(*(avail.get(x, set()) for x in m2))):
                m3 = step(m2, r3)
                if m3:
                    ans3.append({"chain": [r1, r2, r3], "subject": s,
                                 "answers": sorted(m3)[:200],
                                 "text": Q3[r3].format(
                                     np=NP2[r2].format(
                                         np=NP1[r1].format(s=s)))})
if len(ans3) > CAP_ANS:
    ans3 = [ans3[i] for i in rng.choice(len(ans3), CAP_ANS, replace=False)]

unans = {"break@2": [], "break@3": []}
for s in subjects:
    for r1 in sorted(avail[s]):
        m1 = step({s}, r1)
        if not m1:
            continue
        for r2 in RELS:
            m2 = step(m1, r2)
            if not m2:
                for r3 in RELS:
                    unans["break@2"].append({"subject": s, "answers": [],
                                             "chain": [r1, r2, r3],
                                             "text": Q3[r3].format(
                                                 np=NP2[r2].format(
                                                     np=NP1[r1].format(s=s)))})
                continue
            for r3 in RELS:
                if not step(m2, r3):
                    unans["break@3"].append({"subject": s, "answers": [],
                                             "chain": [r1, r2, r3],
                                             "text": Q3[r3].format(
                                                 np=NP2[r2].format(
                                                     np=NP1[r1].format(s=s)))})
for k in unans:
    if len(unans[k]) > CAP_UNANS:
        idx = rng.choice(len(unans[k]), CAP_UNANS, replace=False)
        unans[k] = [unans[k][i] for i in idx]

u2 = []
for kind in sorted({h["kind"] for h in hops}):
    r1, r2 = kind.split(">")
    for s in sorted(x for x in avail if r1 in avail[x]):
        if step(step({s}, r1), r2) or not gold.get((s, r1)):
            continue
        for a in range(len(NPa[r1])):
            for b in range(len(Qa[r2])):
                u2.append({"subject": s, "answers": []})
rng2 = np.random.default_rng(SEED)
if len(u2) > 6000:
    u2 = [u2[i] for i in rng2.choice(len(u2), 6000, replace=False)]

h2 = [{"subject": h["subject"], "chain": h["chain"],
       "answers": [facts[h["answer_fact"]]["object"]]}
      for h in hops if h["kind"] in HOLD2]
Zh2 = Zh[[i for i, h in enumerate(hops) if h["kind"] in HOLD2]]
z26 = np.load(ROOT / "results" / "exp26_emb.npz", allow_pickle=True)
Za, Zb2, Zb3 = z26["Za"], z26["Zb2"], z26["Zb3"]
Zu2 = np.load(ROOT / "results" / "exp25_unans_emb.npz")["Zu"]
# CONTENT asserts, not length: set iteration over strings is hash-order
# dependent, so an identically-sized list can be differently ORDERED and
# silently misalign with its cached embeddings. That bug produced a whole
# wrong conclusion once already.
assert list(z26["ta"]) == [a["text"] for a in ans3], "d3 answerable misaligned"
assert list(z26["tb2"]) == [u["text"] for u in unans["break@2"]], "b2 misaligned"
assert list(z26["tb3"]) == [u["text"] for u in unans["break@3"]], "b3 misaligned"
assert len(Zu2) == len(u2), f"d2 unanswerable drifted {len(Zu2)}/{len(u2)}"
print(f"depth-2: {len(h2)} answerable, {len(u2)} unanswerable")
print(f"depth-3: {len(ans3)} answerable, {len(unans['break@2'])} break@2, "
      f"{len(unans['break@3'])} break@3", flush=True)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

# Training rows: singles + SEEN 2-hop compositions only. No 3-hop anywhere,
# so depth 3 stays the zero-shot test D119 established it can be.
Xs, Ysum, Ypres = [], [], []
for i, q in enumerate(queries):
    if q["kind"] == "single" and q["phrasing_idx"] not in HELD_PH:
        Xs.append(Zq[i])
        Ysum.append(RC[q["relation"]])
        v = np.zeros(len(RELS), np.float32)
        v[ridx[q["relation"]]] = 1.0
        Ypres.append(v)
for i, h in enumerate(hops):
    if h["kind"] not in HOLD2:
        Xs.append(Zh[i])
        Ysum.append(RC[h["chain"][0]] + RC[h["chain"][1]])
        v = np.zeros(len(RELS), np.float32)
        for r in h["chain"]:
            v[ridx[r]] = 1.0
        Ypres.append(v)
X = torch.tensor(np.stack(Xs))
torch.manual_seed(SEED)
sum_head = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, 1024))
opt = torch.optim.AdamW(sum_head.parameters(), lr=1e-3, weight_decay=1e-4)
Ys = torch.tensor(np.stack(Ysum))
for _ in range(40):
    for b in torch.randperm(len(X)).split(512):
        opt.zero_grad()
        ((sum_head(X[b]) - Ys[b]) ** 2).sum(-1).mean().backward()
        opt.step()
sum_head.eval()

pres_head = nn.Sequential(nn.Linear(1024, 256), nn.GELU(),
                          nn.Linear(256, len(RELS)))
optp = torch.optim.AdamW(pres_head.parameters(), lr=1e-3, weight_decay=1e-4)
Yp = torch.tensor(np.stack(Ypres))
bce = nn.BCEWithLogitsLoss()
for _ in range(60):
    for b in torch.randperm(len(X)).split(512):
        optp.zero_grad()
        bce(pres_head(X[b]), Yp[b]).backward()
        optp.step()
pres_head.eval()
print(f"sum + presence heads trained on {len(Xs)} rows "
      f"(singles + seen 2-hop only)", flush=True)


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
    return path, frontier


def score_pop(rows, Z, answerable):
    with torch.no_grad():
        tgt = sum_head(torch.tensor(Z)).numpy()
        pres = torch.sigmoid(pres_head(torch.tensor(Z))).numpy()
    out_rows = []
    for j, a in enumerate(rows):
        path, got = walk(a["subject"], tgt[j])
        ok = (answerable and bool(got)
              and bool(set(got) & set(a["answers"])))
        # the refusal statistic: the HIGHEST presence score among relations
        # the walk never took. Low means every relation the question asked
        # for was actually walked.
        walked = set(path)
        unmet = max([float(pres[j][ridx[r]]) for r in RELS
                     if r not in walked], default=0.0)
        out_rows.append({"empty": not (path and got), "ok": ok,
                         "unmet": unmet})
    return out_rows


print("scoring five populations...", flush=True)
POPS = {
    "d2 answerable": (score_pop(h2, Zh2, True), True),
    "d2 unanswerable": (score_pop(u2, Zu2, False), False),
    "d3 answerable": (score_pop(ans3, Za, True), True),
    "d3 break@2": (score_pop(unans["break@2"], Zb2, False), False),
    "d3 break@3": (score_pop(unans["break@3"], Zb3, False), False),
}


def tally(rows, answerable, thr):
    c = collections.Counter()
    for r in rows:
        if r["empty"] or r["unmet"] > thr:
            c["abstain"] += 1
        elif answerable:
            c["correct" if r["ok"] else "wrong"] += 1
        else:
            c["wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: c[k] / n for k in ("correct", "wrong", "abstain")} | {"n": n}


print(f"\nONE threshold on unmet presence, both depths")
hdr = ["d2 ans corr", "d2 UNANS ref", "d3 ans corr", "d3 brk@2 ref",
       "d3 brk@3 ref"]
print(f"{'thr':>5} " + "".join(f"{h:>14s}" for h in hdr))
sweep = {}
for t in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
    v = {k: tally(rows, ans, t) for k, (rows, ans) in POPS.items()}
    sweep[t] = v
    print(f"{t:5.2f} " + "".join(f"{x:14.3f}" for x in (
        v["d2 answerable"]["correct"], v["d2 unanswerable"]["abstain"],
        v["d3 answerable"]["correct"], v["d3 break@2"]["abstain"],
        v["d3 break@3"]["abstain"])))

# Pre-stated rule: the threshold maximising the WORST of the five figures of
# merit, so no population can be sacrificed to flatter the others.
def worst(t):
    v = sweep[t]
    return min(v["d2 answerable"]["correct"], v["d2 unanswerable"]["abstain"],
               v["d3 answerable"]["correct"], v["d3 break@2"]["abstain"],
               v["d3 break@3"]["abstain"])


THR = max(sweep, key=worst)
V = sweep[THR]
print(f"\nselected thr={THR} (maximises the WORST of the five, so no "
      f"population is sacrificed)  worst={worst(THR):.3f}")
for k, (rows, ans) in POPS.items():
    d = V[k]
    if ans:
        print(f"  {k:18s} correct {d['correct']:.3f}  wrong {d['wrong']:.3f}"
              f"  abstain {d['abstain']:.3f}  (n={d['n']})")
    else:
        print(f"  {k:18s} refused {d['abstain']:.3f}  answered "
              f"{d['wrong']:.3f}  (n={d['n']})")
lo, hi = wilson_ci(int(V["d3 break@3"]["abstain"] * V["d3 break@3"]["n"]),
                   V["d3 break@3"]["n"])
print(f"  break@3 refusal CI95 [{lo:.3f}, {hi:.3f}]")
print(f"\nD119 baseline (global residual, thr 0.40): d3 answerable 0.851, "
      f"break@2 0.907, break@3 0.267")

out = {
    "manifest": run_manifest(seed=SEED, config={"MIN_GAIN": MIN_GAIN,
                                                "MAX_STEPS": MAX_STEPS}),
    "selected_threshold": THR, "worst_of_five": round(worst(THR), 4),
    "sweep": {str(k): v for k, v in sweep.items()},
    "selected": V,
    "break3_refusal_ci95": [round(lo, 4), round(hi, 4)],
    "d119_baseline": {"d3_answerable": 0.851, "break2": 0.907,
                      "break3": 0.267},
    "scope": ("Refusal fires when a relation the PRESENCE head says the "
              "question requires was never walked. Scale-free by "
              "construction: presence is an independent sigmoid per "
              "relation, not a magnitude. No 3-hop data in training, so "
              "depth 3 remains zero-shot. One threshold across both depths "
              "and all five populations."),
}
(ROOT / "results" / "exp27_perstep.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp27_perstep.json")

# ---------------------------------------------------------------------------
# The presence rule LOSES: 0.577 refusal at depth 2 where the residual gets
# 0.970, and 0.313 on break@3. So the per-step idea this experiment was built
# to test is refuted, and the corrected D119 numbers point elsewhere — an
# ABSOLUTE residual threshold with a head that has seen depth 3. This is the
# consolidated head-to-head across all five populations at ONE threshold.
# ---------------------------------------------------------------------------
ALLK = sorted({">".join(a["chain"]) for a in ans3})
HOLD3 = set(list(np.random.default_rng(1).permutation(ALLK))[:max(1, len(ALLK) // 3)])
X3, Y3 = list(Xs), list(Ysum)
for j, a in enumerate(ans3):
    if ">".join(a["chain"]) not in HOLD3:
        X3.append(Za[j])
        Y3.append(sum(RC[r] for r in a["chain"]))
Xt, Yt = torch.tensor(np.stack(X3)), torch.tensor(np.stack(Y3))
torch.manual_seed(SEED)
sum3 = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, 1024))
o3 = torch.optim.AdamW(sum3.parameters(), lr=1e-3, weight_decay=1e-4)
for _ in range(40):
    for b in torch.randperm(len(Xt)).split(512):
        o3.zero_grad()
        ((sum3(Xt[b]) - Yt[b]) ** 2).sum(-1).mean().backward()
        o3.step()
sum3.eval()
print(f"\nsum head retrained with depth-3 rows "
      f"({len(X3) - len(Xs)} added; {len(HOLD3)} 3-compositions held out)")


def abs_tally(hd, rows, Z, thr, answerable, only_kinds=None):
    with torch.no_grad():
        tgt = hd(torch.tensor(Z)).numpy()
    c = collections.Counter()
    for j, a in enumerate(rows):
        if only_kinds is not None and ">".join(a["chain"]) not in only_kinds:
            continue
        path, got = walk(a["subject"], tgt[j])
        resid = tgt[j] - sum((RC[r] for r in path), np.zeros(1024, np.float32))
        if not path or not got or float(np.linalg.norm(resid)) > thr:
            c["abstain"] += 1
        elif answerable:
            c["correct" if set(got) & set(a["answers"]) else "wrong"] += 1
        else:
            c["wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: c[k] / n for k in ("correct", "wrong", "abstain")} | {"n": n}


print("ABSOLUTE residual, depth-3-trained head, one threshold, five populations")
print(f"{'thr':>5} " + "".join(f"{h:>14s}" for h in hdr))
final = {}
for t in (0.4, 0.5, 0.6, 0.7, 0.8, 1.0):
    v = {"d2 answerable": abs_tally(sum3, h2, Zh2, t, True),
         "d2 unanswerable": abs_tally(sum3, u2, Zu2, t, False),
         "d3 answerable": abs_tally(sum3, ans3, Za, t, True, HOLD3),
         "d3 break@2": abs_tally(sum3, unans["break@2"], Zb2, t, False),
         "d3 break@3": abs_tally(sum3, unans["break@3"], Zb3, t, False)}
    final[t] = v
    print(f"{t:5.2f} " + "".join(f"{x:14.3f}" for x in (
        v["d2 answerable"]["correct"], v["d2 unanswerable"]["abstain"],
        v["d3 answerable"]["correct"], v["d3 break@2"]["abstain"],
        v["d3 break@3"]["abstain"])))

BT = max(final, key=lambda t: min(
    final[t]["d2 answerable"]["correct"], final[t]["d2 unanswerable"]["abstain"],
    final[t]["d3 answerable"]["correct"], final[t]["d3 break@2"]["abstain"],
    final[t]["d3 break@3"]["abstain"]))
W = final[BT]
wv = min(W["d2 answerable"]["correct"], W["d2 unanswerable"]["abstain"],
         W["d3 answerable"]["correct"], W["d3 break@2"]["abstain"],
         W["d3 break@3"]["abstain"])
print(f"\nBEST single threshold {BT} (max of the worst-of-five) worst={wv:.3f}")
for k, v in W.items():
    tag = ("correct %.3f wrong %.3f abstain %.3f" %
           (v["correct"], v["wrong"], v["abstain"])) if "answerable" in k and \
        "un" not in k else "refused %.3f answered %.3f" % (v["abstain"],
                                                           v["wrong"])
    print(f"  {k:18s} {tag}  (n={v['n']})")
out["presence_rule_refuted"] = True
out["absolute_residual_depth3_trained"] = {str(k): v for k, v in final.items()}
out["best_single_threshold"] = {"thr": BT, "worst_of_five": round(wv, 4),
                                "table": W}
(ROOT / "results" / "exp27_perstep.json").write_text(json.dumps(out, indent=1))
print("[done] consolidated comparison appended")
