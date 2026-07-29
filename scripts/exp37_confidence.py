"""Graded confidence instead of a binary refuse (D132).

Refusal has been a single threshold on unexplained residual since D118, and
that is too flat in two distinct ways.

**Measurement**: every refusal number in D118-D131 is one point on a curve —
0.970 here, 0.72-0.98 there — chosen by a different rule each time. Those
numbers were never comparable across corpora, depths or architectures. The
threshold-free metric for exactly this is selective prediction: the
RISK-COVERAGE curve and its area (AURC). Lower AURC means the score RANKS
better, independent of where anyone puts the bar. That is the first thing
this measures, and it is retroactively the right way to compare the whole arc.

**Representation**: a binary abstain conflates cases the store can already
tell apart. Covalence's subjective-logic opinion tuple was formally adopted
at D69 as the designed upgrade path and never built — belief / disbelief /
uncertainty with the rule that **"unknown != 50%"**. Applied here that
separates three reasons we currently lump together:

  VACUOUS  - the store offers no path at all. High uncertainty, no evidence
             either way. `foundation/kb.py` already calls this `abstain`.
  CONFLICT - several relations match the residual well and near-equally.
             D124 showed this is the dominant failure and that it is
             AMBIGUITY, not noise (competing gains 1.198 vs 1.390). Belief
             is split, not absent — the opposite of vacuous.
  DISBELIEF- a walk completed but the residual says it did not answer the
             question asked.

D69's warning is respected: adopt the *tuple as an output representation*;
do NOT build a propagation engine. Covalence measured belief oscillation
from stacking five frameworks.

Signals are all already computed by the walker — residual, per-step gain
margin, branching, answer-set size, path length against predicted magnitude.
D124 tested margin and log-options as individual THRESHOLDS and each failed
to shift the frontier; whether a combination RANKS better is a different
question, and AURC is what answers it.

Usage: .venv/bin/python scripts/exp37_confidence.py
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
from codec.manifest import run_manifest                          # noqa: E402
from foundation.kb import KB                                     # noqa: E402

SEED, MIN_GAIN, HOLD_FRAC = 0, 0.2, 0.34
CAP = {"single": 6000, 2: 7000, 3: 8000, "unans": 2000}

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


# ---- populations rebuilt exactly as D123, content-verified (law #8) ----
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
for d in (1, 2, 3):
    chains[d].sort(key=lambda a: (a["subject"], ">".join(a["chain"])))
all_pairs = sorted({(a["chain"][0], a["chain"][1]) for a in chains[2]})
rng = np.random.default_rng(SEED)
HOLD_P = {all_pairs[i] for i in
          list(rng.permutation(len(all_pairs)))[: int(HOLD_FRAC
                                                      * len(all_pairs))]}


def n_held(ch):
    return sum(1 for p in zip(ch, ch[1:]) if p in HOLD_P)


BAG = {"train_d1": list(chains[1]),
       "train_d2": [a for a in chains[2] if n_held(a["chain"]) == 0],
       "train_d3": [a for a in chains[3] if n_held(a["chain"]) == 0],
       "eval_d2_clean": [a for a in chains[2] if n_held(a["chain"]) == 1],
       "eval_d3_clean": [a for a in chains[3] if n_held(a["chain"]) == 2],
       "eval_d3_partial": [a for a in chains[3] if n_held(a["chain"]) == 1]}
for k in list(BAG):
    cap = (CAP["single"] if k == "train_d1"
           else CAP[int(k[-1])] if k.startswith("train")
           else CAP.get(int(k.split("_d")[1][0]), 8000))
    if len(BAG[k]) > cap:
        BAG[k] = [BAG[k][i] for i in sorted(rng.choice(len(BAG[k]), cap,
                                                       replace=False))]
unans = {2: {2: []}, 3: {2: [], 3: []}}
for s in subjects:
    for r1 in sorted(avail[s]):
        m1 = step({s}, r1)
        if not m1:
            continue
        for r2 in RELS:
            m2 = step(m1, r2)
            if not m2:
                unans[2][2].append({"subject": s, "chain": [r1, r2],
                                    "answers": []})
                unans[3][2].append({"subject": s, "chain": [r1, r2, RELS[0]],
                                    "answers": []})
                continue
            for r3 in RELS:
                if not step(m2, r3):
                    unans[3][3].append({"subject": s, "chain": [r1, r2, r3],
                                        "answers": []})
for d in unans:
    for k in unans[d]:
        rows = unans[d][k]
        rows.sort(key=lambda a: (a["subject"], ">".join(a["chain"])))
        if len(rows) > CAP["unans"]:
            rows = [rows[i] for i in sorted(rng.choice(len(rows),
                                                       CAP["unans"],
                                                       replace=False))]
        BAG[f"unans_{d}_{k}"] = rows


def text_of(s, chain):
    np_ = s
    for r in chain[:-1]:
        np_ = f"the {LABEL[r]} of {np_}"
    return f"What is the {LABEL[chain[-1]]} of {np_}?"


ORDER = sorted(BAG)
texts, index = [], {}
for key in ORDER:
    index[key] = (len(texts), len(texts) + len(BAG[key]))
    texts += [text_of(a["subject"], a["chain"]) for a in BAG[key]]
z = np.load(ROOT / "results" / "exp29_emb.npz", allow_pickle=True)
assert list(z["texts"]) == texts, "populations drifted from D123"
Z, Zl = z["Z"], z["Zl"]
RC = {r: Zl[i] for i, r in enumerate(RELS)}
print(f"D123 populations reproduced ({len(texts)} questions)", flush=True)


def emb(k):
    a, b = index[k]
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
print(f"head trained on {len(Xs)} chains", flush=True)


def walk_signals(subject, target, max_steps):
    """Walk once, recording every signal the walker already computes."""
    resid, frontier, path = target.copy(), {subject}, []
    margins, branch = [], []
    for _ in range(max_steps):
        opts = sorted(options_at(frontier))
        if not opts:
            break
        branch.append(len(opts))
        g = sorted(((float(resid @ RC[r]), r) for r in opts), reverse=True)
        if g[0][0] <= MIN_GAIN:
            break
        margins.append(g[0][0] - (g[1][0] if len(g) > 1 else -1.0))
        nxt = step(frontier, g[0][1])
        if not nxt:
            break
        frontier, path = nxt, path + [g[0][1]]
        resid = resid - RC[g[0][1]]
    rn = float(np.linalg.norm(resid))
    return {"path": path, "frontier": frontier, "resid": rn,
            "margin": float(min(margins)) if margins else 0.0,
            "branch": float(np.mean(branch)) if branch else 0.0,
            "nans": float(len(frontier)),
            "steps": float(len(path)),
            "mag": float(np.linalg.norm(target))}


def score_pop(key, max_steps, answerable):
    rows, E = BAG[key], emb(key)
    with torch.no_grad():
        tgt = head(torch.tensor(E)).numpy()
    out = []
    for j, a in enumerate(rows):
        s = walk_signals(a["subject"], tgt[j], max_steps)
        # "correct if answered": answerable AND the walk hit a gold object.
        # For unanswerable items this is False by construction, so ANSWERING
        # one is an error — which is what makes both populations a single
        # selective-prediction problem rather than two disconnected metrics.
        ok = bool(answerable and s["frontier"]
                  and set(s["frontier"]) & set(a["answers"]))
        out.append({**s, "ok": ok, "pop": key,
                    "walkable": bool(s["path"] and s["frontier"])})
    return out


POPS = [("train_d2", 3, True), ("train_d3", 4, True),
        ("eval_d2_clean", 3, True), ("eval_d3_clean", 4, True),
        ("unans_2_2", 3, False), ("unans_3_3", 4, False)]
DATA = {k: score_pop(k, m, a) for k, m, a in POPS}
print("signals computed for " + ", ".join(f"{k}({len(v)})"
                                          for k, v in DATA.items()),
      flush=True)

CAL = DATA["train_d2"] + DATA["train_d3"] + DATA["unans_2_2"]
EVAL = DATA["eval_d2_clean"] + DATA["eval_d3_clean"] + DATA["unans_3_3"]
print(f"calibration set {len(CAL)} (trained pairs + unanswerable, per law "
      f"#6); evaluation set {len(EVAL)} (pair-clean + held-out unanswerable)")


def aurc(rows, conf):
    """Area under the risk-coverage curve. Sort by confidence descending;
    at each coverage, risk = errors among the answered. Threshold-free."""
    order = np.argsort(-np.asarray(conf))
    ok = np.asarray([rows[i]["ok"] for i in order], dtype=float)
    cum_err = np.cumsum(1.0 - ok)
    n = np.arange(1, len(ok) + 1)
    return float(np.mean(cum_err / n)), (n / len(ok)), (cum_err / n)


def feats(r):
    return np.array([-r["resid"], r["margin"], -np.log1p(r["branch"]),
                     -np.log1p(r["nans"]), r["steps"], r["mag"]],
                    dtype=np.float64)


# fit the combined score on the CALIBRATION set only
Xc = np.stack([feats(r) for r in CAL])
yc = np.array([r["ok"] for r in CAL], dtype=np.float64)
mu, sd = Xc.mean(0), Xc.std(0) + 1e-9
Xc = (Xc - mu) / sd
w = np.zeros(Xc.shape[1])
b = 0.0
for _ in range(600):                       # plain logistic regression
    p_ = 1 / (1 + np.exp(-(Xc @ w + b)))
    gw = Xc.T @ (p_ - yc) / len(yc)
    gb = float((p_ - yc).mean())
    w -= 0.5 * gw
    b -= 0.5 * gb

SCORERS = {
    "residual only (D118-D131)": lambda r: -r["resid"],
    "margin only (D124)": lambda r: r["margin"],
    "combined (fitted on calibration)":
        lambda r: float(((feats(r) - mu) / sd) @ w + b),
}
print(f"\n{'scorer':36s} {'AURC':>8} {'risk@50%':>9} {'risk@80%':>9} "
      f"{'cov@risk<=0.05':>15}")
res = {}
for name, f in SCORERS.items():
    conf = [f(r) for r in EVAL]
    a, cov, risk = aurc(EVAL, conf)
    r50 = float(risk[int(0.5 * len(risk)) - 1])
    r80 = float(risk[int(0.8 * len(risk)) - 1])
    okmask = risk <= 0.05
    c05 = float(cov[okmask][-1]) if okmask.any() else 0.0
    res[name] = {"aurc": round(a, 4), "risk_at_50": round(r50, 4),
                 "risk_at_80": round(r80, 4),
                 "coverage_at_risk_05": round(c05, 4)}
    print(f"{name:36s} {a:8.4f} {r50:9.3f} {r80:9.3f} {c05:15.3f}")
print("  (lower AURC = better RANKING, independent of any threshold)")

# ---- SL-style status decomposition of what is currently one bucket ----
CONFLICT_MARGIN = float(np.percentile([r["margin"] for r in CAL
                                       if r["walkable"]], 25))
print(f"\nSL-style decomposition of the single 'abstain' bucket "
      f"(conflict when min-margin < {CONFLICT_MARGIN:.3f}, the calibration "
      f"25th percentile)")
print(f"{'population':18s} {'vacuous':>9} {'conflict':>9} {'disbelief':>10} "
      f"{'answered':>9}")
dec = {}
THR = 0.8
for key, _m, ans in POPS:
    c = collections.Counter()
    for r in DATA[key]:
        if not r["walkable"]:
            c["vacuous"] += 1
        elif r["resid"] > THR:
            c["conflict" if r["margin"] < CONFLICT_MARGIN
              else "disbelief"] += 1
        else:
            c["answered"] += 1
    n = max(sum(c.values()), 1)
    dec[key] = {k: round(c[k] / n, 4) for k in
                ("vacuous", "conflict", "disbelief", "answered")}
    print(f"{key:18s} {c['vacuous']/n:9.3f} {c['conflict']/n:9.3f} "
          f"{c['disbelief']/n:10.3f} {c['answered']/n:9.3f}")

out = {
    "manifest": run_manifest(seed=SEED, config={"MIN_GAIN": MIN_GAIN,
                                                "THR": THR}),
    "n_calibration": len(CAL), "n_eval": len(EVAL),
    "selective_prediction": res,
    "status_decomposition": dec,
    "conflict_margin_cut": round(CONFLICT_MARGIN, 4),
    "scope": ("Selective prediction over answerable and unanswerable "
              "populations TOGETHER: answering an unanswerable item is an "
              "error, which makes refusal and accuracy one metric instead "
              "of two incomparable ones. AURC is threshold-free, so it "
              "compares across corpora and depths in a way every refusal "
              "number in D118-D131 could not. The combined scorer is fitted "
              "on the calibration set only (trained pairs + unanswerable, "
              "per law #6). The SL decomposition is an OUTPUT "
              "representation, not a propagation framework — D69 recorded "
              "that stacking those caused belief oscillation in Covalence."),
}
(ROOT / "results" / "exp37_confidence.json").write_text(json.dumps(out,
                                                                   indent=1))
print("\n[done] results/exp37_confidence.json")
