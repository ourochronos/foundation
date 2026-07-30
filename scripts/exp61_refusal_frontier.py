"""The encoder comparison, matched on the REFUSAL frontier (D60's open question)

exp60 compared encoders at matched *trained-answerable* coverage and found the
swap buys +0.122 on novel-relation answering — while novel-unanswerable
refusal fell **0.6300 → 0.3315**. Matching coverage on answerable questions
does not pin down behaviour on unanswerable ones, so the arms were still at
different points on the answer/refuse trade and the gain was not established.

This reports the **whole frontier** instead of a point: sweep the residual
threshold across a wide grid and trace, for each arm, the curve of

    novel-relation answering  vs  novel-unanswerable refusal

If one encoder's curve **dominates** — more correct answers at every refusal
level — the swap is justified without reference to any operating point. If the
curves cross, the swap is a trade and the choice depends on what the deployment
values, which is a different kind of answer and needs saying as one.

**No operating point is selected from novel data.** That would be law #6
violated — calibrating on the population you then report. The curve *is* the
result; the interpolated readings at matched refusal are a way of reading the
curve, not a tuned threshold. Nothing here is proposed for deployment.

Both arms use the SAME basis (`kmeans_label` K=48, what the pipeline runs) and
therefore the same residual dimensionality, so the threshold is a commensurate
quantity across them — which it was not in exp60's basis comparison.

**Registered prediction.** The curves cross. Gemma answers more at permissive
thresholds and M3 refuses better at strict ones, because exp60 showed Gemma
sitting further toward coverage at every threshold it picked. If Gemma instead
dominates outright, the swap is a clean win and I was wrong to hedge.

Usage: .venv/bin/python scripts/exp61_refusal_frontier.py
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

from codec.evals.anchors import fit_anchors                      # noqa: E402
from codec.manifest import run_manifest                          # noqa: E402
from foundation.kb import KB                                     # noqa: E402

SEED, MIN_GAIN, K_BASIS = 0, 0.2, 48
N_HOLD_REL, INST_FRAC, CAP_UNANS = 12, 0.20, 2000
GRID = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4, 1.6, 2.0)
MATCH_AT = (0.30, 0.40, 0.50, 0.60, 0.70, 0.80)

sch = {d["pid"]: d["label"] for d in
       json.loads((ROOT / "data" / "schema_v0.json").read_text())}
props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
kb = KB(backend="pg", table="poc")
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
gold, avail = collections.defaultdict(set), collections.defaultdict(set)
for c in wiki:
    gold[(c["subject"], c["pid"])].add(c["object"])
    avail[c["subject"]].add(c["pid"])
subjects = sorted(avail)


def step(nodes, r):
    out = set()
    for s in nodes:
        out |= gold.get((s, r), set())
    return out


def options_at(nodes):
    o = set()
    for s in nodes:
        o |= avail.get(s, set())
    return o


rng = np.random.default_rng(SEED)
HOLD_R = {RELS[i] for i in sorted(rng.permutation(len(RELS))[:N_HOLD_REL])}
TRAINED_R = [r for r in RELS if r not in HOLD_R]
chains = {1: [], 2: [], 3: []}
for s in subjects:
    stack = [({s}, [])]
    while stack:
        nodes, ch = stack.pop()
        if len(ch) >= 3:
            continue
        for r in sorted(options_at(nodes)):
            nx = step(nodes, r)
            if not nx:
                continue
            c2 = ch + [r]
            chains[len(c2)].append({"subject": s, "chain": c2,
                                    "answers": sorted(nx)[:300]})
            stack.append((nx, c2))
for d in chains:
    chains[d].sort(key=lambda a: (a["subject"], ">".join(a["chain"])))
POPS = collections.defaultdict(list)
rr = np.random.default_rng(SEED + 1)
for d in (1, 2, 3):
    for a in chains[d]:
        nv = sum(1 for r in a["chain"] if r in HOLD_R)
        if nv:
            if d <= 2:
                POPS[f"eval_d{d}_novel{nv}"].append(a)
        elif rr.random() < INST_FRAC and d <= 2:
            POPS[f"eval_d{d}_inst"].append(a)
        else:
            POPS[f"train_d{d}"].append(a)
unans = collections.defaultdict(list)
for s in subjects:
    for r1 in sorted(avail[s]):
        m1 = step({s}, r1)
        if not m1:
            continue
        for r2 in RELS:
            if step(m1, r2):
                continue
            key = ("unans_novel" if (r1 in HOLD_R or r2 in HOLD_R)
                   else "unans_trained")
            unans[key].append({"subject": s, "chain": [r1, r2], "answers": []})
for k in sorted(unans):
    unans[k].sort(key=lambda a: (a["subject"], ">".join(a["chain"])))
    if len(unans[k]) > CAP_UNANS:
        unans[k] = [unans[k][i] for i in
                    sorted(rng.choice(len(unans[k]), CAP_UNANS, replace=False))]


def text_of(s, chain):
    np_ = s
    for r in chain[:-1]:
        np_ = f"the {LABEL[r]} of {np_}"
    return f"What is the {LABEL[chain[-1]]} of {np_}?"


BAG = dict(POPS)
BAG.update(unans)
ORDER = sorted(BAG)
texts, index = [], {}
for key in ORDER:
    index[key] = (len(texts), len(texts) + len(BAG[key]))
    texts += [text_of(a["subject"], a["chain"]) for a in BAG[key]]

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402


def unit(a):
    return a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9)


def embeddings(arm):
    if arm == "m3":
        z = np.load(ROOT / "results" / "exp31_emb.npz", allow_pickle=True)
        assert list(z["texts"]) == texts, "population drifted from exp31"
        return z["Z"], z["Zl"]
    z = np.load(ROOT / "results" / "exp60_gemma_emb.npz", allow_pickle=True)
    assert list(z["texts"]) == texts, "exp60 gemma cache misaligned"
    return z["Z"], z["Zl"]


def emb(Z, key):
    a, b = index[key]
    return Z[a:b]


def run(Z, C, hd, dim, key, max_steps, answerable, thr):
    rows, E = BAG[key], emb(Z, key)
    with torch.no_grad():
        tgt = hd(torch.tensor(E)).numpy()
    c = collections.Counter()
    for j, a in enumerate(rows):
        resid, frontier, path = tgt[j].copy(), {a["subject"]}, []
        for _ in range(max_steps):
            best, bg = None, MIN_GAIN
            for r in options_at(frontier):
                g = float(resid @ C[r])
                if g > bg:
                    best, bg = r, g
            if best is None:
                break
            nxt = step(frontier, best)
            if not nxt:
                break
            frontier, path = nxt, path + [best]
            resid = resid - C[best]
        rn = float(np.linalg.norm(tgt[j] - sum((C[r] for r in path),
                                               np.zeros(dim, np.float32))))
        if not path or not frontier or rn > thr:
            c["abstain"] += 1
        elif answerable:
            c["correct" if set(frontier) & set(a["answers"]) else "wrong"] += 1
        else:
            c["wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: round(c[k] / n, 4) for k in ("correct", "wrong", "abstain")}


CURVES = {}
for arm in ("m3", "gemma"):
    Z, Zl = embeddings(arm)
    RAW = {r: Zl[i] for i, r in enumerate(RELS)}
    PC = unit(fit_anchors(np.stack([RAW[r] for r in TRAINED_R]), K_BASIS,
                          seed=SEED))
    C = {r: unit(RAW[r] @ PC.T) for r in RELS}
    Xs, Ys = [], []
    for key in ("train_d1", "train_d2", "train_d3"):
        E = emb(Z, key)
        for j, a in enumerate(BAG[key]):
            Xs.append(E[j])
            Ys.append(sum(C[r] for r in a["chain"]))
    X, Y = torch.tensor(np.stack(Xs)), torch.tensor(np.stack(Ys))
    torch.manual_seed(SEED)
    hd = nn.Sequential(nn.Linear(Z.shape[1], 512), nn.GELU(),
                       nn.Linear(512, K_BASIS))
    op = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(X)).split(512):
            op.zero_grad()
            ((hd(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
            op.step()
    hd.eval()
    print(f"\n=== {arm} (basis kmeans_label K={K_BASIS}, dim {K_BASIS}) ===",
          flush=True)
    print(f"  {'thr':>5} {'novel_correct':>14} {'novel_wrong':>12} "
          f"{'unansNov_refuse':>16} {'train_d1':>9}")
    pts = []
    for t in GRID:
        nv = run(Z, C, hd, K_BASIS, "eval_d1_novel1", 2, True, t)
        un = run(Z, C, hd, K_BASIS, "unans_novel", 3, False, t)
        tr = run(Z, C, hd, K_BASIS, "train_d1", 2, True, t)
        pts.append({"thr": t, "novel_correct": nv["correct"],
                    "novel_wrong": nv["wrong"],
                    "unans_novel_refuse": un["abstain"],
                    "train_d1_correct": tr["correct"]})
        print(f"  {t:5.2f} {nv['correct']:14.4f} {nv['wrong']:12.4f} "
              f"{un['abstain']:16.4f} {tr['correct']:9.4f}", flush=True)
    CURVES[arm] = pts

# ---- read each curve at matched novel-unanswerable refusal ----
def at_refusal(pts, target):
    xs = np.array([p["unans_novel_refuse"] for p in pts])
    ys = np.array([p["novel_correct"] for p in pts])
    o = np.argsort(xs)
    xs, ys = xs[o], ys[o]
    if target < xs[0] or target > xs[-1]:
        return None
    return float(np.interp(target, xs, ys))


print(f"\n=== novel-relation answering at MATCHED novel-unanswerable refusal ===")
print(f"  {'refusal':>8} {'m3':>9} {'gemma':>9} {'gemma-m3':>10}")
matched, dominates, crosses = {}, True, False
for rf in MATCH_AT:
    a, b = at_refusal(CURVES["m3"], rf), at_refusal(CURVES["gemma"], rf)
    if a is None or b is None:
        print(f"  {rf:8.2f} {'-':>9} {'-':>9}   (outside one curve's range)")
        continue
    matched[str(rf)] = {"m3": round(a, 4), "gemma": round(b, 4),
                        "delta": round(b - a, 4)}
    if b < a:
        dominates = False
    if b - a < 0:
        crosses = True
    print(f"  {rf:8.2f} {a:9.4f} {b:9.4f} {b - a:+10.4f}")

deltas = [v["delta"] for v in matched.values()]
md = float(np.mean(deltas)) if deltas else 0.0
if deltas and all(d > 0.02 for d in deltas):
    verdict = (f"GEMMA DOMINATES — it answers more novel-relation questions "
               f"at every matched refusal level tested (mean {md:+.4f}). The "
               f"encoder swap is a clean win, not a trade, and exp60's "
               f"apparent refusal cost was an operating-point artifact.")
elif deltas and all(d < -0.02 for d in deltas):
    verdict = (f"M3 DOMINATES — Gemma answers FEWER at every matched refusal "
               f"level (mean {md:+.4f}). The identification-level advantage "
               f"does not survive the frontier comparison.")
elif deltas:
    verdict = (f"CURVES CROSS — mean {md:+.4f} but the sign is not constant "
               f"across refusal levels, so the swap is a TRADE and which "
               f"encoder is better depends on the operating point a "
               f"deployment wants.")
else:
    verdict = "INCONCLUSIVE — the curves do not overlap on refusal."
print(f"\n=== VERDICT ===\n  {verdict}")

out = {"manifest": run_manifest(seed=SEED, config={"GRID": list(GRID),
                                                   "K_BASIS": K_BASIS,
                                                   "MATCH_AT": list(MATCH_AT)}),
       "n_relations": len(RELS), "n_trained": len(TRAINED_R),
       "curves": CURVES, "matched_at_refusal": matched, "verdict": verdict,
       "registered_prediction": (
           "the curves cross — Gemma answers more at permissive thresholds "
           "and M3 refuses better at strict ones; outright Gemma dominance "
           "would mean the hedge in exp60 was wrong"),
       "scope": ("Reports the whole answer/refuse frontier rather than a "
                 "point, because exp60 matched on trained-answerable "
                 "coverage and that does not pin down behaviour on "
                 "unanswerable questions — the +0.122 answering gain came "
                 "with a -0.299 refusal loss. Both arms use the SAME basis "
                 "(kmeans_label K=48) and therefore the same residual "
                 "dimensionality, so the threshold is commensurate across "
                 "them, which it was not in exp60's basis comparison. NO "
                 "operating point is selected from novel data: the curve is "
                 "the result and the matched readings are a way of reading "
                 "it, not a calibration (law #6). Nothing here is proposed "
                 "for deployment.")}
(ROOT / "results" / "exp61_refusal_frontier.json").write_text(
    json.dumps(out, indent=1))
print("\n[done] results/exp61_refusal_frontier.json")
