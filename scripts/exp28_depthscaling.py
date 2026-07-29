"""Does the tail fall off as depth grows — with and without exposure? (D121)

D120 established that ANSWERING extrapolates to unseen depth for free while
REFUSAL needs examples at that depth, and left "unbounded depth" restated as
"unbounded given examples at each depth". That was measured at depths 2 and
3 only, so the shape of the curve is unknown: refusal might hold flat given
exposure, or degrade steadily until exposure stops rescuing it.

Depths 2-5, two conditions per depth, so exposure is a controlled variable:

  EXPOSED    — head trained on depths 1..n, with compositions at depth n
               held out, so it has seen the DEPTH but not the CHAIN SHAPE
  ZERO-SHOT  — head trained on depths 1..n-1 only, never any depth-n example

The D120 refusal rule is applied UNCHANGED (absolute residual, threshold
0.5) rather than re-tuned per depth, because a rule that needs re-tuning at
every depth is not a rule. Per-depth best thresholds are reported alongside
to show what re-tuning would have bought.

Unanswerable populations are graded by where the chain dies (D119's
discipline, which is what exposed the depth-3 collapse) — break@k for every
k from 2 to n.

**Stated limitation**: question text is built by nesting noun phrases, so a
depth-5 question reads "What do the works cited by the works cited by the
methods introduced by the works X cites cite?". That is unnatural in a way a
real query never would be, and any degradation with depth is therefore
confounded with the templates getting worse. The confound is one-directional
(it can only hurt), so a flat curve would be a strong result and a declining
one is ambiguous.

Usage: .venv/bin/python scripts/exp28_depthscaling.py
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

SEED, MIN_GAIN, D120_THR = 0, 0.2, 0.5
DEPTHS = [2, 3, 4, 5]
CAP_UNANS = 1000

NP1 = {"P_CITES": "the works {s} cites",
       "P_INTRODUCES": "the method introduced by {s}",
       "P_BUILDS_ON": "what {s} builds on",
       "P_COMPARES_TO": "the baselines {s} compares against",
       "P_EVALUATES_ON": "the benchmarks {s} evaluates on"}
NPn = {"P_CITES": "the works cited by {np}",
       "P_INTRODUCES": "the methods introduced by {np}",
       "P_BUILDS_ON": "what {np} build on",
       "P_COMPARES_TO": "the baselines {np} compare against",
       "P_EVALUATES_ON": "the benchmarks {np} evaluate on"}
QF = {"P_CITES": "What do {np} cite?",
      "P_INTRODUCES": "What do {np} introduce?",
      "P_BUILDS_ON": "What do {np} build on?",
      "P_COMPARES_TO": "What do {np} compare against?",
      "P_EVALUATES_ON": "What do {np} evaluate on?"}

world = json.loads((ROOT / "data" / "real_world_ai_hops.json").read_text())
facts, queries, hops = world["facts"], world["queries"], world["hops"]
HELD_PH = set(world["held_out_phrasings"])
RELS = sorted({f["relation"] for f in facts})
Zq = np.load(ROOT / "results" / "real_world_ai_emb.npz")["Zq"]
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
subjects = sorted(avail)


def step(nodes, r):
    out = set()
    for s in nodes:
        out |= gold.get((s, r), set())
    return out


def text_of(s, chain):
    np_ = NP1[chain[0]].format(s=s)
    for r in chain[1:-1]:
        np_ = NPn[r].format(np=np_)
    return QF[chain[-1]].format(np=np_)


# ---- enumerate answerable chains at every depth (deterministic: D120/law 8)
ans = {d: [] for d in DEPTHS}
for s in subjects:
    stack = [({s}, [])]
    while stack:
        nodes, chain = stack.pop()
        if len(chain) >= max(DEPTHS):
            continue
        opts = sorted(set().union(*(avail.get(x, set()) for x in nodes)))
        for r in opts:
            nx = step(nodes, r)
            if not nx:
                continue
            ch = chain + [r]
            if len(ch) in ans:
                ans[len(ch)].append({"subject": s, "chain": ch,
                                     "answers": sorted(nx)[:300],
                                     "text": text_of(s, ch)})
            stack.append((nx, ch))
for d in DEPTHS:
    ans[d].sort(key=lambda a: (a["subject"], ">".join(a["chain"])))
    print(f"depth {d}: {len(ans[d])} answerable chains")

# ---- unanswerable, graded by where the chain dies ----
rng = np.random.default_rng(SEED)
unans = {d: {k: [] for k in range(2, d + 1)} for d in DEPTHS}
for s in subjects:
    stack = [({s}, [])]
    while stack:
        nodes, chain = stack.pop()
        if len(chain) >= max(DEPTHS):
            continue
        for r in RELS:
            nx = step(nodes, r)
            ch = chain + [r]
            if nx:
                stack.append((nx, ch))
                continue
            # chain dies at hop len(ch); pad to each depth d >= len(ch)
            k = len(ch)
            if k < 2:
                continue
            for d in DEPTHS:
                if d < k:
                    continue
                pad = ch + [RELS[0]] * (d - k)
                unans[d][k].append({"subject": s, "chain": pad,
                                    "answers": [],
                                    "text": text_of(s, pad)})
for d in DEPTHS:
    for k in list(unans[d]):
        rows = unans[d][k]
        rows.sort(key=lambda a: (a["subject"], ">".join(a["chain"])))
        if len(rows) > CAP_UNANS:
            idx = sorted(rng.choice(len(rows), CAP_UNANS, replace=False))
            unans[d][k] = [rows[i] for i in idx]
    print(f"depth {d} unanswerable: " +
          ", ".join(f"break@{k} {len(v)}" for k, v in unans[d].items()))

# ---- embeddings, content-verified (audit law #8) ----
cache = ROOT / "results" / "exp28_emb.npz"
texts, index = [], {}
for d in DEPTHS:
    index[("ans", d)] = (len(texts), len(texts) + len(ans[d]))
    texts += [a["text"] for a in ans[d]]
    for k, rows in unans[d].items():
        index[("un", d, k)] = (len(texts), len(texts) + len(rows))
        texts += [r["text"] for r in rows]
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    assert list(z["texts"]) == texts, "cache misaligned; delete it"
    Z = z["Z"]
else:
    Z = P.unit(P.embed_texts(texts))
    np.savez(cache, Z=Z, texts=np.array(texts))
print(f"{Z.shape[0]} question embeddings", flush=True)


def slice_of(key):
    a, b = index[key]
    return Z[a:b]


import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

# held-out chain SHAPES per depth, so exposure means "saw the depth", never
# "saw this chain"
HOLDK = {}
for d in DEPTHS:
    ks = sorted({">".join(a["chain"]) for a in ans[d]})
    perm = list(np.random.default_rng(1).permutation(ks))
    HOLDK[d] = set(perm[: max(1, len(ks) // 3)])
    print(f"depth {d}: {len(ks)} chain shapes, {len(HOLDK[d])} held out")

BASE_X, BASE_Y = [], []
for i, q in enumerate(queries):
    if q["kind"] == "single" and q["phrasing_idx"] not in HELD_PH:
        BASE_X.append(Zq[i])
        BASE_Y.append(RC[q["relation"]])


def train(max_depth):
    """Train on singles plus every depth up to max_depth, held-out shapes
    excluded at each depth."""
    Xs, Ys = list(BASE_X), list(BASE_Y)
    for d in DEPTHS:
        if d > max_depth:
            break
        Za_ = slice_of(("ans", d))
        for j, a in enumerate(ans[d]):
            if ">".join(a["chain"]) in HOLDK[d]:
                continue
            Xs.append(Za_[j])
            Ys.append(sum(RC[r] for r in a["chain"]))
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
    return hd


def walk(subject, target, max_steps):
    resid, frontier, path = target.copy(), {subject}, []
    for _ in range(max_steps):
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
    return path, frontier, resid


def judge(hd, rows, Zr, thr, answerable, max_steps, only_held=None):
    with torch.no_grad():
        tgt = hd(torch.tensor(Zr)).numpy()
    c = collections.Counter()
    for j, a in enumerate(rows):
        if only_held is not None and ">".join(a["chain"]) not in only_held:
            continue
        path, got, _ = walk(a["subject"], tgt[j], max_steps)
        resid = tgt[j] - sum((RC[r] for r in path), np.zeros(1024, np.float32))
        if not path or not got or float(np.linalg.norm(resid)) > thr:
            c["abstain"] += 1
        elif answerable:
            c["correct" if set(got) & set(a["answers"]) else "wrong"] += 1
        else:
            c["wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: c[k] / n for k in ("correct", "wrong", "abstain")} | {"n": n}


heads = {d: train(d) for d in DEPTHS}
print("\n=== D120 rule applied UNCHANGED (absolute residual, thr 0.5) ===")
print(f"{'depth':>5} {'cond':>10} {'correct':>8} {'wrong':>7} {'abst':>7}  "
      f"refusal by break point")
table = {}
for d in DEPTHS:
    for cond, hd in (("EXPOSED", heads[d]),
                     ("zero-shot", heads[d - 1] if d - 1 in heads else None)):
        if hd is None:
            continue
        A = judge(hd, ans[d], slice_of(("ans", d)), D120_THR, True,
                  d + 1, HOLDK[d])
        refs = {k: judge(hd, unans[d][k], slice_of(("un", d, k)), D120_THR,
                         False, d + 1)["abstain"] for k in unans[d]}
        table[(d, cond)] = {"answerable": A, "refusal": refs}
        print(f"{d:5d} {cond:>10} {A['correct']:8.3f} {A['wrong']:7.3f} "
              f"{A['abstain']:7.3f}  " +
              "  ".join(f"@{k} {v:.3f}" for k, v in sorted(refs.items())))

print("\nworst-case per depth (min over answerable-correct and all refusals)")
print(f"{'depth':>5} {'EXPOSED':>9} {'zero-shot':>10}")
for d in DEPTHS:
    row = []
    for cond in ("EXPOSED", "zero-shot"):
        t = table.get((d, cond))
        row.append("%9.3f" % min([t["answerable"]["correct"]]
                                 + list(t["refusal"].values())) if t
                   else "        —")
    print(f"{d:5d} " + " ".join(row))

out = {
    "manifest": run_manifest(seed=SEED, config={"DEPTHS": DEPTHS,
                                                "thr": D120_THR,
                                                "CAP_UNANS": CAP_UNANS}),
    "n_answerable": {str(d): len(ans[d]) for d in DEPTHS},
    "held_out_shapes": {str(d): sorted(HOLDK[d]) for d in DEPTHS},
    "table": {f"d{d}_{c}": v for (d, c), v in table.items()},
    "scope": ("One refusal rule (D120's absolute residual at 0.5) applied "
              "unchanged at every depth. EXPOSED means the head saw depth n "
              "but not this chain SHAPE; zero-shot means it never saw depth "
              "n at all. Question text nests noun phrases, so deep "
              "questions are unnatural — a confound that can only hurt, so "
              "a flat curve is strong evidence and a declining one is "
              "ambiguous."),
}
(ROOT / "results" / "exp28_depthscaling.json").write_text(json.dumps(out,
                                                                     indent=1))
print("\n[done] results/exp28_depthscaling.json")

# ---------------------------------------------------------------------------
# Depth-2 correctness (0.359) is worse than depth-3 (0.740) and unexplained.
# Leading hypothesis: OVERSHOOT. MAX_STEPS is d+1, and MIN_GAIN is only 0.2,
# so an imperfectly-predicted target can still show >0.2 gain on some
# available relation after the true chain is walked. A spurious extra step
# leaves residual = pred - (n+1 unit vectors), whose norm blows past the
# 0.5 refusal threshold — turning a CORRECT answer into an abstention.
# That predicts: at depth 2, walks are systematically too LONG, and the
# abstentions concentrate on over-length walks.
# ---------------------------------------------------------------------------
print("\npath-length distribution vs true depth (EXPOSED heads)")
print(f"{'depth':>5} {'mean |path|':>11} {'short':>7} {'exact':>7} "
      f"{'long':>7} | {'abstain if exact':>16} {'abstain if long':>16}")
diag = {}
for d in DEPTHS:
    hd = heads[d]
    rows = [a for a in ans[d] if ">".join(a["chain"]) in HOLDK[d]]
    Zr = slice_of(("ans", d))
    Zr = np.stack([Zr[j] for j, a in enumerate(ans[d])
                   if ">".join(a["chain"]) in HOLDK[d]])
    with torch.no_grad():
        tgt = hd(torch.tensor(Zr)).numpy()
    lens, bucket = [], collections.Counter()
    ab = {"exact": [0, 0], "long": [0, 0], "short": [0, 0]}
    for j, a in enumerate(rows):
        path, got, _ = walk(a["subject"], tgt[j], d + 1)
        lens.append(len(path))
        b = ("exact" if len(path) == d else
             ("long" if len(path) > d else "short"))
        bucket[b] += 1
        resid = tgt[j] - sum((RC[r] for r in path), np.zeros(1024, np.float32))
        refused = (not path or not got
                   or float(np.linalg.norm(resid)) > D120_THR)
        ab[b][0] += int(refused)
        ab[b][1] += 1
    n = len(rows)
    diag[d] = {"mean_path": float(np.mean(lens)),
               "short": bucket["short"] / n, "exact": bucket["exact"] / n,
               "long": bucket["long"] / n,
               "abstain_given_exact": ab["exact"][0] / max(ab["exact"][1], 1),
               "abstain_given_long": ab["long"][0] / max(ab["long"][1], 1)}
    print(f"{d:5d} {np.mean(lens):11.2f} {bucket['short']/n:7.3f} "
          f"{bucket['exact']/n:7.3f} {bucket['long']/n:7.3f} | "
          f"{diag[d]['abstain_given_exact']:16.3f} "
          f"{diag[d]['abstain_given_long']:16.3f}")

print("\nMIN_GAIN sweep at depth 2 (does a stricter stop rule fix it?)")
print(f"{'min_gain':>9} {'correct':>8} {'wrong':>7} {'abstain':>8} "
      f"{'mean |path|':>11}")
gain_sweep = {}
for mg in (0.2, 0.3, 0.4, 0.5, 0.6):
    globals()["MIN_GAIN"] = mg
    A = judge(heads[2], ans[2], slice_of(("ans", 2)), D120_THR, True, 3,
              HOLDK[2])
    rows = [a for a in ans[2] if ">".join(a["chain"]) in HOLDK[2]]
    Zr = np.stack([slice_of(("ans", 2))[j] for j, a in enumerate(ans[2])
                   if ">".join(a["chain"]) in HOLDK[2]])
    with torch.no_grad():
        tgt = heads[2](torch.tensor(Zr)).numpy()
    ml = float(np.mean([len(walk(a["subject"], tgt[j], 3)[0])
                        for j, a in enumerate(rows)]))
    gain_sweep[mg] = {**A, "mean_path": ml}
    print(f"{mg:9.2f} {A['correct']:8.3f} {A['wrong']:7.3f} "
          f"{A['abstain']:8.3f} {ml:11.2f}")
globals()["MIN_GAIN"] = 0.2
out["depth2_diagnosis"] = {"path_lengths": diag, "min_gain_sweep":
                           {str(k): v for k, v in gain_sweep.items()}}
(ROOT / "results" / "exp28_depthscaling.json").write_text(json.dumps(out,
                                                                     indent=1))
print("[done] diagnosis appended")

# ---------------------------------------------------------------------------
# Overshoot refuted: walks are never too long (0.000 at every depth) and 99.4%
# are exact-length at depth 2, yet 0.638 of those exact walks are refused. So
# the TARGET is poorly predicted even when the walk is right.
#
# That suggests a contamination asymmetry rather than a depth effect. Holding
# out a SHAPE at depth 2 removes that relation pair from training entirely.
# Holding out a triple at depth 3 does not: its adjacent pairs can still
# appear inside retained chains, and a head trained up to depth 3 also sees
# depth-2 pairs embedded in depth-3 chains. If so, "held-out composition" is
# a much weaker holdout at depth >= 3 than at depth 2 — which would make the
# depth-3 numbers in D120/D121 optimistic, not the depth-2 number anomalous.
# ---------------------------------------------------------------------------
def training_pairs(max_depth):
    """Every adjacent relation pair the head actually saw at this exposure."""
    pairs = set()
    for d in DEPTHS:
        if d > max_depth:
            break
        for a in ans[d]:
            if ">".join(a["chain"]) in HOLDK[d]:
                continue
            for x, y in zip(a["chain"], a["chain"][1:]):
                pairs.add((x, y))
    return pairs


print("\nis 'held-out composition' really held out? (adjacent-pair leakage)")
print(f"{'depth':>5} {'held shapes':>12} {'all pairs seen':>15} "
       f"{'no pair seen':>13}")
leak = {}
for d in DEPTHS:
    tp = training_pairs(d)
    full = part = none = 0
    for shape in sorted(HOLDK[d]):
        ch = shape.split(">")
        ps = list(zip(ch, ch[1:]))
        seen = sum(1 for p in ps if p in tp)
        if seen == len(ps):
            full += 1
        elif seen == 0:
            none += 1
        else:
            part += 1
    n = len(HOLDK[d])
    leak[d] = {"n_held": n, "all_pairs_seen": full / n, "none_seen": none / n,
               "partial": part / n}
    print(f"{d:5d} {n:12d} {full/n:15.3f} {none/n:13.3f}")

print("\nre-evaluating with a STRICTER holdout: shapes whose adjacent pairs")
print("were also never trained (the depth-2 holdout condition, at all depths)")
print(f"{'depth':>5} {'n shapes':>9} {'correct':>8} {'wrong':>7} "
      f"{'abstain':>8}")
strict = {}
for d in DEPTHS:
    tp = training_pairs(d)
    keep = {s for s in HOLDK[d]
            if all(p not in tp for p in zip(s.split(">"), s.split(">")[1:]))}
    if not keep:
        print(f"{d:5d} {0:9d}        —       —        —   "
              f"(no shape is pair-clean at this depth)")
        strict[d] = None
        continue
    A = judge(heads[d], ans[d], slice_of(("ans", d)), D120_THR, True,
              d + 1, keep)
    strict[d] = {**A, "n_shapes": len(keep)}
    print(f"{d:5d} {len(keep):9d} {A['correct']:8.3f} {A['wrong']:7.3f} "
          f"{A['abstain']:8.3f}")
out["pair_leakage"] = leak
out["strict_holdout"] = {str(k): v for k, v in strict.items()}
(ROOT / "results" / "exp28_depthscaling.json").write_text(json.dumps(out,
                                                                     indent=1))
print("[done] leakage analysis appended")
