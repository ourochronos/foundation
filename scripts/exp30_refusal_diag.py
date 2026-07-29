"""Why is refusal weaker on wiki than on the AI corpus? (D124)

D123 left this as the most serious open item. Refusal on wiki is 0.72–0.98
against the AI corpus's 0.970, and wrong-rates are 0.017–0.073 rather than
~0.000. Refusal is this project's central claim, so "the property is
corpus-dependent" is not an acceptable resting place without a mechanism.

**Pre-registered hypothesis (written before the run): BRANCHING.** The walker
takes the best-matching relation among those AVAILABLE at the current
frontier. With 6.4 options per step on wiki instead of the AI corpus's
handful, a chain that should die has more chances that *some* available
relation spuriously clears MIN_GAIN and absorbs the residual — so the walk
continues and answers instead of refusing. That is a multiple-comparisons
problem, not a threshold problem, and it predicts a specific, falsifiable
shape: **refusal rate should fall monotonically as branching at the break
step rises.**

**Falsifier**: refusal flat in branching. Then the hypothesis is dead and the
alternative — that residual magnitude is simply predicted worse on this
corpus — gets tested instead, via the answerable/unanswerable residual
separation.

**If confirmed**, the principled fix follows from the diagnosis rather than
from tuning: require a larger gain when more options were considered,
`MIN_GAIN + C·log|options|`, calibrated per audit law #6 on populations that
exhibit the failure.

Branching is a property of the STORE, so the AI-corpus comparison needs no
model — only the wiki side requires the trained head.

Usage: .venv/bin/python scripts/exp30_refusal_diag.py
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

SEED, MIN_GAIN, HOLD_FRAC = 0, 0.2, 0.34
CAP = {"single": 6000, 2: 7000, 3: 8000, "unans": 2000}

sch = {d["pid"]: d["label"] for d in
       json.loads((ROOT / "data" / "schema_v0.json").read_text())}
props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
kb = KB(backend="pg", table="poc")

# ---------------------------------------------------------------------------
# A. Both stores. Branching needs no model, so the AI side is store-only.
# ---------------------------------------------------------------------------
AI_RELS = ("P_CITES", "P_INTRODUCES", "P_EVALUATES_ON", "P_BUILDS_ON",
           "P_COMPARES_TO")


def build(claims, rels):
    gold, avail = collections.defaultdict(set), collections.defaultdict(set)
    for c in claims:
        gold[(c["subject"], c["pid"])].add(c["object"])
        avail[c["subject"]].add(c["pid"])
    return gold, avail


ai_claims = [c for c in kb.claims
             if c["pid"] in AI_RELS and c["page"].startswith("arxiv:")]
ai_gold, ai_avail = build(ai_claims, AI_RELS)

wiki_all = [c for c in kb.claims
            if not c["page"].startswith(("arxiv:", "hf:", "user"))]
LABEL = {}
for c in wiki_all:
    p = c["pid"]
    if p not in LABEL:
        lab = sch.get(p) or (props.get(p) or {}).get("label")
        if lab:
            LABEL[p] = lab
RELS = sorted(LABEL)
wiki = [c for c in wiki_all if c["pid"] in LABEL]
gold, avail = build(wiki, RELS)
subjects = sorted(avail)


def step(g, nodes, r):
    out = set()
    for s in nodes:
        out |= g.get((s, r), set())
    return out


def options_at(av, nodes):
    o = set()
    for s in nodes:
        o |= av.get(s, set())
    return o


print(f"AI corpus:   {len(ai_claims)} claims, {len(AI_RELS)} relations, "
      f"{len(ai_avail)} subjects")
print(f"wiki corpus: {len(wiki)} claims, {len(RELS)} relations, "
      f"{len(subjects)} subjects")

# branching over one step from every subject — store-only, no model
for name, av, g in (("AI", ai_avail, ai_gold), ("wiki", avail, gold)):
    b1 = [len(av[s]) for s in sorted(av)]
    b2 = []
    for s in sorted(av):
        for r in sorted(av[s]):
            m = step(g, {s}, r)
            if m:
                b2.append(len(options_at(av, m)))
    print(f"  {name:5s} options at step 1: mean {np.mean(b1):5.2f} "
          f"median {int(np.median(b1))};  at step 2: mean {np.mean(b2):5.2f} "
          f"median {int(np.median(b2))}")

# ---------------------------------------------------------------------------
# B. Wiki populations, rebuilt exactly as D123 and content-verified (law #8).
# ---------------------------------------------------------------------------
chains = {1: [], 2: [], 3: []}
for s in subjects:
    stack = [({s}, [])]
    while stack:
        nodes, ch = stack.pop()
        if len(ch) >= 3:
            continue
        for r in sorted(options_at(avail, nodes)):
            nx = step(gold, nodes, r)
            if not nx:
                continue
            c2 = ch + [r]
            chains[len(c2)].append({"subject": s, "chain": c2,
                                    "answers": sorted(nx)[:300]})
            stack.append((nx, c2))
for d in (1, 2, 3):
    chains[d].sort(key=lambda a: (a["subject"], ">".join(a["chain"])))

all_pairs = sorted({(a["chain"][0], a["chain"][1]) for a in chains[2]})
rng = np.random.default_rng(SEED)
perm = list(rng.permutation(len(all_pairs)))
HOLD_P = {all_pairs[i] for i in perm[: int(HOLD_FRAC * len(all_pairs))]}


def n_held(ch):
    return sum(1 for p in zip(ch, ch[1:]) if p in HOLD_P)


POPS = {
    "train_d1": list(chains[1]),
    "train_d2": [a for a in chains[2] if n_held(a["chain"]) == 0],
    "train_d3": [a for a in chains[3] if n_held(a["chain"]) == 0],
    "eval_d2_clean": [a for a in chains[2] if n_held(a["chain"]) == 1],
    "eval_d3_clean": [a for a in chains[3] if n_held(a["chain"]) == 2],
    "eval_d3_partial": [a for a in chains[3] if n_held(a["chain"]) == 1],
}
for k, v in POPS.items():
    cap = (CAP["single"] if k == "train_d1"
           else CAP[int(k[-1])] if k.startswith("train")
           else CAP.get(int(k.split("_d")[1][0]), 8000))
    if len(v) > cap:
        POPS[k] = [v[i] for i in sorted(rng.choice(len(v), cap,
                                                   replace=False))]

unans = {2: {2: []}, 3: {2: [], 3: []}}
for s in subjects:
    for r1 in sorted(avail[s]):
        m1 = step(gold, {s}, r1)
        if not m1:
            continue
        for r2 in RELS:
            m2 = step(gold, m1, r2)
            if not m2:
                unans[2][2].append({"subject": s, "chain": [r1, r2],
                                    "answers": []})
                unans[3][2].append({"subject": s, "chain": [r1, r2, RELS[0]],
                                    "answers": []})
                continue
            for r3 in RELS:
                if not step(gold, m2, r3):
                    unans[3][3].append({"subject": s, "chain": [r1, r2, r3],
                                        "answers": []})
for d in unans:
    for k in unans[d]:
        rows = unans[d][k]
        rows.sort(key=lambda a: (a["subject"], ">".join(a["chain"])))
        if len(rows) > CAP["unans"]:
            unans[d][k] = [rows[i] for i in
                           sorted(rng.choice(len(rows), CAP["unans"],
                                             replace=False))]


def text_of(s, chain):
    np_ = s
    for r in chain[:-1]:
        np_ = f"the {LABEL[r]} of {np_}"
    return f"What is the {LABEL[chain[-1]]} of {np_}?"


BAG = dict(POPS)
for d in unans:
    for k in unans[d]:
        BAG[f"unans_{d}_{k}"] = unans[d][k]
ORDER = sorted(POPS) + [f"unans_{d}_{k}" for d in unans for k in unans[d]]
texts, index = [], {}
for key in ORDER:
    index[key] = (len(texts), len(texts) + len(BAG[key]))
    texts += [text_of(a["subject"], a["chain"]) for a in BAG[key]]

z = np.load(ROOT / "results" / "exp29_emb.npz", allow_pickle=True)
assert list(z["texts"]) == texts, "populations drifted from D123 — cache stale"
Z, Zl = z["Z"], z["Zl"]
RC = {r: Zl[i] for i, r in enumerate(RELS)}
print(f"\nD123 populations reproduced and content-verified ({len(texts)} "
      f"questions)", flush=True)


def emb(key):
    a, b = index[key]
    return Z[a:b]


import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

Xs, Ys = [], []
for key in ("train_d1", "train_d2", "train_d3"):
    E = emb(key)
    for j, a in enumerate(BAG[key]):
        Xs.append(E[j])
        Ys.append(sum(RC[r] for r in a["chain"]))
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
print(f"head retrained on {len(Xs)} chains (identical to D123)", flush=True)


def walk(subject, target, max_steps, min_gain=MIN_GAIN, adaptive=0.0,
         margin=0.0):
    """Returns (path, frontier, residual, max_options_seen).

    `margin` (D124) stops the walk when the best available relation does not
    beat the runner-up by that much — an AMBIGUITY brake rather than a
    magnitude threshold. The residual then stays unspent and the ordinary
    refusal rule fires."""
    resid, frontier, path, mx = target.copy(), {subject}, [], 0
    for _ in range(max_steps):
        opts = options_at(avail, frontier)
        if not opts:
            break
        mx = max(mx, len(opts))
        thr = min_gain + adaptive * np.log(max(len(opts), 1))
        gains = sorted(((float(resid @ RC[r]), r) for r in opts),
                       reverse=True)
        best, bg = None, thr
        if gains and gains[0][0] > thr:
            second = gains[1][0] if len(gains) > 1 else -1e9
            if gains[0][0] - second >= margin:
                best, bg = gains[0][1], gains[0][0]
        if best is None:
            break
        nxt = step(gold, frontier, best)
        if not nxt:
            break
        frontier, path = nxt, path + [best]
        resid = resid - RC[best]
    return path, frontier, resid, mx


THR = 0.8                       # D123's selected threshold, held fixed here


def rows_for(key, max_steps, adaptive=0.0, min_gain=MIN_GAIN, margin=0.0):
    rowset, E = BAG[key], emb(key)
    with torch.no_grad():
        tgt = head(torch.tensor(E)).numpy()
    out = []
    for j, a in enumerate(rowset):
        path, got, resid, mx = walk(a["subject"], tgt[j], max_steps,
                                    min_gain, adaptive, margin)
        rn = float(np.linalg.norm(resid))
        refused = (not path) or (not got) or rn > THR
        ok = bool(got) and bool(set(got) & set(a["answers"]))
        out.append({"refused": refused, "ok": ok, "resid": rn,
                    "opts": mx, "break_opts": break_options(a)})
    return out


def break_options(a):
    """How many relations were available at the step where this chain dies.
    For answerable chains, at the final step."""
    frontier = {a["subject"]}
    for r in a["chain"]:
        n = len(options_at(avail, frontier))
        nxt = step(gold, frontier, r)
        if not nxt:
            return n
        frontier = nxt
    return len(options_at(avail, frontier))


# ---------------------------------------------------------------------------
# C. THE TEST: refusal rate stratified by branching at the break step.
# ---------------------------------------------------------------------------
print("\n=== THE TEST: refusal vs branching at the break step ===")
BINS = [(1, 2), (3, 4), (5, 6), (7, 9), (10, 14), (15, 99)]
strat = {}
for key, mx in (("unans_2_2", 3), ("unans_3_2", 4), ("unans_3_3", 4)):
    rr = rows_for(key, mx)
    print(f"\n{key}  (n={len(rr)})")
    print(f"{'branching':>12} {'n':>6} {'refused':>9}")
    strat[key] = {}
    for lo, hi in BINS:
        sub = [r for r in rr if lo <= r["break_opts"] <= hi]
        if len(sub) < 20:
            continue
        ref = sum(r["refused"] for r in sub) / len(sub)
        strat[key][f"{lo}-{hi}"] = {"n": len(sub), "refused": round(ref, 4)}
        print(f"{lo:5d}-{hi:<6d} {len(sub):6d} {ref:9.3f}")
    v = [(np.mean([r["break_opts"] for r in rr if lo <= r["break_opts"] <= hi]),
          np.mean([r["refused"] for r in rr if lo <= r["break_opts"] <= hi]))
         for lo, hi in BINS
         if sum(1 for r in rr if lo <= r["break_opts"] <= hi) >= 20]
    if len(v) >= 3:
        c = float(np.corrcoef([x for x, _ in v], [y for _, y in v])[0, 1])
        strat[key]["corr_branching_vs_refusal"] = round(c, 4)
        print(f"  correlation(branching, refusal) = {c:+.3f}"
              f"   {'<- hypothesis PREDICTS strongly negative' if True else ''}")

# ---------------------------------------------------------------------------
# D. Alternative explanation: is the residual separation itself worse?
# ---------------------------------------------------------------------------
print("\nresidual-norm separation (answerable vs unanswerable), wiki")
a2 = rows_for("eval_d2_clean", 3)
u2 = rows_for("unans_2_2", 3)
print(f"  answerable   median {np.median([r['resid'] for r in a2]):.3f}  "
      f"p90 {np.percentile([r['resid'] for r in a2], 90):.3f}")
print(f"  unanswerable median {np.median([r['resid'] for r in u2]):.3f}  "
      f"p10 {np.percentile([r['resid'] for r in u2], 10):.3f}")
overlap = (np.percentile([r["resid"] for r in a2], 90)
           > np.percentile([r["resid"] for r in u2], 10))
print(f"  distributions overlap at the decision region: {overlap}")

out = {
    "manifest": run_manifest(seed=SEED, config={"THR": THR,
                                                "MIN_GAIN": MIN_GAIN}),
    "hypothesis": ("refusal degrades with branching at the break step: more "
                   "available relations means more chances one spuriously "
                   "absorbs the residual (a multiple-comparisons problem)"),
    "branching_stratified_refusal": strat,
    "residual_separation": {
        "answerable_median": float(np.median([r["resid"] for r in a2])),
        "answerable_p90": float(np.percentile([r["resid"] for r in a2], 90)),
        "unanswerable_median": float(np.median([r["resid"] for r in u2])),
        "unanswerable_p10": float(np.percentile([r["resid"] for r in u2], 10)),
    },
    "scope": ("Branching is a store property, measured on both corpora "
              "without a model. The stratified refusal test runs on wiki "
              "only, at D123's fixed threshold 0.8, so nothing is re-tuned "
              "before the diagnosis is read."),
}
(ROOT / "results" / "exp30_refusal_diag.json").write_text(json.dumps(out,
                                                                     indent=1))
print("\n[done] results/exp30_refusal_diag.json")

# ---------------------------------------------------------------------------
# E. The fix implied by the diagnosis.
#
# Confirmed: refusal falls monotonically with branching (corr -0.79 to -0.91),
# while the residual distributions do NOT overlap at the decision region
# (answerable p90 0.579 < unanswerable p10 0.639). So the residual signal is
# clean and the threshold is not the problem — the walk finds a spurious
# continuation and SPENDS the residual before it is ever evaluated. Every
# extra option is another chance to clear MIN_GAIN, which is a
# multiple-comparisons problem and has the standard fix: require a larger
# gain when more comparisons were made.
#
#     gain must exceed  MIN_GAIN + C * log(|options|)
#
# C is calibrated on TRAINED-pair answerable populations plus the
# unanswerable ones — populations that exhibit the failure (audit law #6) —
# and then reported on the pair-clean held-out populations, which never
# influence the choice.
# ---------------------------------------------------------------------------
print("\n=== the fix: gain bar scaled by log(options) ===")
print(f"{'C':>6} | {'train d2':>9} {'train d3':>9} | {'unans 2@2':>10} "
      f"{'unans 3@2':>10} {'unans 3@3':>10} | {'worst':>7}")
cal = {}
for C in (0.0, 0.05, 0.10, 0.15, 0.20, 0.30):
    a2c = rows_for("train_d2", 3, adaptive=C)
    a3c = rows_for("train_d3", 4, adaptive=C)
    u22 = rows_for("unans_2_2", 3, adaptive=C)
    u32 = rows_for("unans_3_2", 4, adaptive=C)
    u33 = rows_for("unans_3_3", 4, adaptive=C)
    acc2 = np.mean([r["ok"] and not r["refused"] for r in a2c])
    acc3 = np.mean([r["ok"] and not r["refused"] for r in a3c])
    r22 = np.mean([r["refused"] for r in u22])
    r32 = np.mean([r["refused"] for r in u32])
    r33 = np.mean([r["refused"] for r in u33])
    w = min(acc2, acc3, r22, r32, r33)
    cal[C] = {"train_d2_correct": float(acc2), "train_d3_correct": float(acc3),
              "unans_2_2": float(r22), "unans_3_2": float(r32),
              "unans_3_3": float(r33), "worst": float(w)}
    print(f"{C:6.2f} | {acc2:9.3f} {acc3:9.3f} | {r22:10.3f} {r32:10.3f} "
          f"{r33:10.3f} | {w:7.3f}")
BEST_C = max(cal, key=lambda c: cal[c]["worst"])
print(f"selected C={BEST_C} (max worst-case on calibration populations)")

print(f"\nheld-out PAIR-CLEAN populations at C=0 vs C={BEST_C} "
      f"(these never influenced the choice)")
print(f"{'population':18s} {'C':>5} {'correct':>8} {'wrong':>7} {'abstain':>8}")
final = {}
for key, mx in (("eval_d2_clean", 3), ("eval_d3_clean", 4)):
    for C in (0.0, BEST_C):
        rr = rows_for(key, mx, adaptive=C)
        n = len(rr)
        corr = sum(1 for r in rr if not r["refused"] and r["ok"]) / n
        wrong = sum(1 for r in rr if not r["refused"] and not r["ok"]) / n
        ab = sum(1 for r in rr if r["refused"]) / n
        final[f"{key}_C{C}"] = {"correct": round(corr, 4),
                                "wrong": round(wrong, 4),
                                "abstain": round(ab, 4), "n": n}
        print(f"{key:18s} {C:5.2f} {corr:8.3f} {wrong:7.3f} {ab:8.3f}")

print("\nrefusal vs branching AFTER the fix (the mechanism should flatten)")
for key, mx in (("unans_2_2", 3), ("unans_3_3", 4)):
    rr = rows_for(key, mx, adaptive=BEST_C)
    pts = []
    for lo, hi in BINS:
        sub = [r for r in rr if lo <= r["break_opts"] <= hi]
        if len(sub) >= 20:
            pts.append((np.mean([r["break_opts"] for r in sub]),
                        np.mean([r["refused"] for r in sub])))
    if len(pts) >= 3:
        c = float(np.corrcoef([x for x, _ in pts], [y for _, y in pts])[0, 1])
        before = strat[key].get("corr_branching_vs_refusal")
        print(f"  {key:12s} corr {before:+.3f} -> {c:+.3f}")
        final[f"{key}_corr_after"] = round(c, 4)

out["adaptive_gain"] = {"calibration": {str(k): v for k, v in cal.items()},
                        "selected_C": BEST_C, "held_out": final}
(ROOT / "results" / "exp30_refusal_diag.json").write_text(json.dumps(out,
                                                                     indent=1))
print("[done] adaptive-gain results appended")

# ---------------------------------------------------------------------------
# F. The fix failed — so the mechanism is not what "multiple comparisons"
# usually means. A Bonferroni-style bar removes FALSE POSITIVES: options that
# clear the threshold by chance. If raising the bar with log|options| barely
# moves the correlation (-0.788 -> -0.754) while costing depth-3 accuracy,
# the competing relations are probably not marginal at all.
#
# Refined hypothesis: this is AMBIGUITY, not noise. With 61 relations and a
# dense store, an unanswerable question often has a genuinely plausible
# alternative continuation available — a different relation that really does
# match the residual well. No threshold can separate "good match to the wrong
# question" from "good match to the right one", because both are good matches.
#
# Test: compare the CHOSEN relation's gain on answerable-correct walks
# against unanswerable-answered walks. Overlap => ambiguity, and threshold
# corrections are hopeless. Then test the signal ambiguity actually implies:
# the MARGIN between the best and second-best available relation.
# ---------------------------------------------------------------------------
def first_step_stats(key, max_steps):
    rowset, E = BAG[key], emb(key)
    with torch.no_grad():
        tgt = head(torch.tensor(E)).numpy()
    out = []
    for j, a in enumerate(rowset):
        opts = sorted(options_at(avail, {a["subject"]}))
        if len(opts) < 2:
            continue
        gains = sorted((float(tgt[j] @ RC[r]) for r in opts), reverse=True)
        path, got, resid, _ = walk(a["subject"], tgt[j], max_steps)
        rn = float(np.linalg.norm(resid))
        answered = bool(path) and bool(got) and rn <= THR
        ok = bool(got) and bool(set(got) & set(a["answers"]))
        out.append({"top": gains[0], "margin": gains[0] - gains[1],
                    "answered": answered, "ok": ok})
    return out


print("\n=== is it noise or ambiguity? gain of the CHOSEN relation ===")
ans_rows = first_step_stats("eval_d2_clean", 3)
un_rows = first_step_stats("unans_2_2", 3)
good = [r for r in ans_rows if r["answered"] and r["ok"]]
bad = [r for r in un_rows if r["answered"]]
for tag, rr in (("answerable, answered correctly", good),
                ("UNanswerable, answered anyway", bad)):
    if rr:
        print(f"  {tag:32s} top-gain median "
              f"{np.median([r['top'] for r in rr]):.3f}  "
              f"p10 {np.percentile([r['top'] for r in rr], 10):.3f}")
print("  -> overlapping medians would mean threshold corrections are hopeless")

print("\nmargin (best minus second-best available relation) as a refusal cue")
for tag, rr in (("answerable, answered correctly", good),
                ("UNanswerable, answered anyway", bad)):
    if rr:
        print(f"  {tag:32s} margin median "
              f"{np.median([r['margin'] for r in rr]):.3f}  "
              f"p10 {np.percentile([r['margin'] for r in rr], 10):.3f}")
sep = None
if good and bad:
    sep = float(np.median([r["margin"] for r in good])
                - np.median([r["margin"] for r in bad]))
    print(f"  median margin separation: {sep:+.3f}  "
          f"({'usable' if abs(sep) > 0.05 else 'NOT usable'})")

out["ambiguity_test"] = {
    "answerable_top_gain_median": float(np.median([r["top"] for r in good]))
    if good else None,
    "unanswerable_top_gain_median": float(np.median([r["top"] for r in bad]))
    if bad else None,
    "answerable_margin_median": float(np.median([r["margin"] for r in good]))
    if good else None,
    "unanswerable_margin_median": float(np.median([r["margin"] for r in bad]))
    if bad else None,
    "margin_separation": sep,
}
(ROOT / "results" / "exp30_refusal_diag.json").write_text(json.dumps(out,
                                                                     indent=1))
print("[done] ambiguity test appended")

# ---------------------------------------------------------------------------
# G. The ambiguity brake: stop when the best relation does not clearly beat
# the runner-up. Calibrated on the same populations as before (law #6),
# reported on the pair-clean held-out sets that never influenced the choice.
# ---------------------------------------------------------------------------
print("\n=== ambiguity brake: require a margin over the runner-up ===")
print(f"{'M':>5} | {'train d2':>9} {'train d3':>9} | {'unans 2@2':>10} "
      f"{'unans 3@2':>10} {'unans 3@3':>10} | {'worst':>7}")
mcal = {}
for M in (0.0, 0.1, 0.2, 0.3, 0.4, 0.6):
    a2 = rows_for("train_d2", 3, margin=M)
    a3 = rows_for("train_d3", 4, margin=M)
    u22 = rows_for("unans_2_2", 3, margin=M)
    u32 = rows_for("unans_3_2", 4, margin=M)
    u33 = rows_for("unans_3_3", 4, margin=M)
    acc2 = float(np.mean([r["ok"] and not r["refused"] for r in a2]))
    acc3 = float(np.mean([r["ok"] and not r["refused"] for r in a3]))
    r22 = float(np.mean([r["refused"] for r in u22]))
    r32 = float(np.mean([r["refused"] for r in u32]))
    r33 = float(np.mean([r["refused"] for r in u33]))
    w = min(acc2, acc3, r22, r32, r33)
    mcal[M] = {"train_d2": acc2, "train_d3": acc3, "unans_2_2": r22,
               "unans_3_2": r32, "unans_3_3": r33, "worst": w}
    print(f"{M:5.2f} | {acc2:9.3f} {acc3:9.3f} | {r22:10.3f} {r32:10.3f} "
          f"{r33:10.3f} | {w:7.3f}")
BEST_M = max(mcal, key=lambda m: mcal[m]["worst"])
print(f"selected M={BEST_M} (max worst-case on calibration populations)")

print(f"\nheld-out PAIR-CLEAN at M=0 vs M={BEST_M}")
print(f"{'population':18s} {'M':>5} {'correct':>8} {'wrong':>7} {'abstain':>8}")
mfinal = {}
for key, mx in (("eval_d2_clean", 3), ("eval_d3_clean", 4)):
    for M in (0.0, BEST_M):
        rr = rows_for(key, mx, margin=M)
        n = len(rr)
        d = {"correct": round(sum(1 for r in rr
                                  if not r["refused"] and r["ok"]) / n, 4),
             "wrong": round(sum(1 for r in rr
                                if not r["refused"] and not r["ok"]) / n, 4),
             "abstain": round(sum(1 for r in rr if r["refused"]) / n, 4)}
        mfinal[f"{key}_M{M}"] = d
        print(f"{key:18s} {M:5.2f} {d['correct']:8.3f} {d['wrong']:7.3f} "
              f"{d['abstain']:8.3f}")

for key, mx in (("unans_2_2", 3), ("unans_3_3", 4)):
    rr = rows_for(key, mx, margin=BEST_M)
    pts = [(np.mean([r["break_opts"] for r in rr
                     if lo <= r["break_opts"] <= hi]),
            np.mean([r["refused"] for r in rr
                     if lo <= r["break_opts"] <= hi]))
           for lo, hi in BINS
           if sum(1 for r in rr if lo <= r["break_opts"] <= hi) >= 20]
    if len(pts) >= 3:
        c = float(np.corrcoef([x for x, _ in pts], [y for _, y in pts])[0, 1])
        print(f"  {key:12s} branching corr "
              f"{strat[key]['corr_branching_vs_refusal']:+.3f} -> {c:+.3f}")
        mfinal[f"{key}_corr_after"] = round(c, 4)

out["ambiguity_brake"] = {"calibration": {str(k): v for k, v in mcal.items()},
                          "selected_M": BEST_M, "held_out": mfinal}
(ROOT / "results" / "exp30_refusal_diag.json").write_text(json.dumps(out,
                                                                     indent=1))
print("[done] ambiguity brake appended")
