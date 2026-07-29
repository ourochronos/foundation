"""Depth 4 on wiki, pair-clean, both representations (D126).

D121 measured a depth curve on the AI corpus and could not interpret it: the
wrong-rate stayed flat while coverage decayed, but questions were built by
nesting noun phrases, so a depth-5 question read "What do the works cited by
the works cited by the methods introduced by ... cite?". That confound could
only hurt, so the coverage decline was ambiguous between "the mechanism
decays" and "the questions became nonsense". D122 then showed the AI corpus
could not support pair-clean holdouts past depth 2 at all.

Wiki fixes both problems at once. Questions read naturally — "What is the
location of the employer of the author of X?" — and with 624 realised pairs a
pair-clean holdout is constructible at every depth.

Two representations are run side by side, because D125 changed the default:
predicting into a frozen anchor basis fit on trained relations beat raw
1024-d by 0.671 vs 0.293 on novel relations. Whether it also helps with DEPTH
is a separate question and has never been asked.

Populations are separated by pair-cleanliness at every depth (D122's rule) —
all pairs held out, partial, or none — and never merged.

Usage: .venv/bin/python scripts/exp32_depth4.py
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
from codec.evals.anchors import fit_anchors                      # noqa: E402
from codec.manifest import run_manifest, wilson_ci               # noqa: E402
from foundation.kb import KB                                     # noqa: E402

SEED, MIN_GAIN, HOLD_FRAC, K_BASIS = 0, 0.2, 0.34, 48
DEPTHS = [2, 3, 4]
CAP = {1: 6000, 2: 7000, 3: 8000, 4: 8000, "unans": 2000}

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


chains = {d: [] for d in [1] + DEPTHS}
for s in subjects:
    stack = [({s}, [])]
    while stack:
        nodes, ch = stack.pop()
        if len(ch) >= max(DEPTHS):
            continue
        for r in sorted(options_at(nodes)):
            nx = step(nodes, r)
            if not nx:
                continue
            c2 = ch + [r]
            if len(c2) in chains:
                chains[len(c2)].append({"subject": s, "chain": c2,
                                        "answers": sorted(nx)[:300]})
            stack.append((nx, c2))
for d in chains:
    chains[d].sort(key=lambda a: (a["subject"], ">".join(a["chain"])))
    print(f"depth {d}: {len(chains[d])} chains, "
          f"{len({tuple(a['chain']) for a in chains[d]})} shapes")

all_pairs = sorted({(a["chain"][0], a["chain"][1]) for a in chains[2]})
rng = np.random.default_rng(SEED)
HOLD_P = {all_pairs[i] for i in
          list(rng.permutation(len(all_pairs)))[: int(HOLD_FRAC
                                                      * len(all_pairs))]}
print(f"{len(all_pairs)} pairs, {len(HOLD_P)} held out")


def n_held(ch):
    return sum(1 for p in zip(ch, ch[1:]) if p in HOLD_P)


BAG = {"train_d1": list(chains[1])}
for d in DEPTHS:
    for a in chains[d]:
        h, tot = n_held(a["chain"]), d - 1
        key = (f"train_d{d}" if h == 0 else
               f"eval_d{d}_clean" if h == tot else f"eval_d{d}_partial")
        BAG.setdefault(key, []).append(a)
for k in sorted(BAG):
    cap = CAP.get(int(k[-1]) if k.startswith("train")
                  else int(k.split("_d")[1][0]), 8000)
    if len(BAG[k]) > cap:
        BAG[k] = [BAG[k][i] for i in sorted(rng.choice(len(BAG[k]), cap,
                                                       replace=False))]
    print(f"  {k:18s} {len(BAG[k]):6d} chains, "
          f"{len({tuple(a['chain']) for a in BAG[k]}):5d} shapes")

unans = collections.defaultdict(list)
for s in subjects:
    for r1 in sorted(avail[s]):
        m1 = step({s}, r1)
        if not m1:
            continue
        for r2 in RELS:
            m2 = step(m1, r2)
            if not m2:
                unans["brk2"].append({"subject": s, "answers": [],
                                      "chain": [r1, r2, RELS[0], RELS[0]]})
                continue
            for r3 in RELS:
                m3 = step(m2, r3)
                if not m3:
                    unans["brk3"].append({"subject": s, "answers": [],
                                          "chain": [r1, r2, r3, RELS[0]]})
                    continue
                for r4 in RELS:
                    if not step(m3, r4):
                        unans["brk4"].append({"subject": s, "answers": [],
                                              "chain": [r1, r2, r3, r4]})
for k in sorted(unans):
    unans[k].sort(key=lambda a: (a["subject"], ">".join(a["chain"])))
    if len(unans[k]) > CAP["unans"]:
        unans[k] = [unans[k][i] for i in
                    sorted(rng.choice(len(unans[k]), CAP["unans"],
                                      replace=False))]
    BAG[k] = unans[k]
    print(f"  {k:18s} {len(unans[k]):6d}")


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
cache = ROOT / "results" / "exp32_emb.npz"
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    assert list(z["texts"]) == texts, "cache misaligned; delete it"
    Z, Zl = z["Z"], z["Zl"]
else:
    Z = P.unit(P.embed_texts(texts))
    Zl = P.unit(P.embed_texts([LABEL[r] for r in RELS]))
    np.savez(cache, Z=Z, Zl=Zl, texts=np.array(texts))
RC = {r: Zl[i] for i, r in enumerate(RELS)}
print(f"\n{len(texts)} questions; depth-4 example: "
      f"{texts[index['eval_d4_clean'][0]] if 'eval_d4_clean' in index else texts[0]!r}",
      flush=True)


def emb(key):
    a, b = index[key]
    return Z[a:b]


import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

TRAIN_KEYS = [k for k in BAG if k.startswith("train")]
PC = P.unit(fit_anchors(np.stack([RC[r] for r in RELS]), K_BASIS, seed=SEED))
COORD = {"raw": RC, "basis": {r: P.unit(RC[r] @ PC.T) for r in RELS}}


def train_head(coord, dim):
    Xs, Ys = [], []
    for key in TRAIN_KEYS:
        E = emb(key)
        for j, a in enumerate(BAG[key]):
            Xs.append(E[j])
            Ys.append(sum(coord[r] for r in a["chain"]))
    X, Y = torch.tensor(np.stack(Xs)), torch.tensor(np.stack(Ys))
    torch.manual_seed(SEED)
    hd = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, dim))
    op = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(X)).split(512):
            op.zero_grad()
            ((hd(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
            op.step()
    hd.eval()
    return hd, len(Xs)


HEADS = {}
for name, dim in (("raw", 1024), ("basis", K_BASIS)):
    HEADS[name], n = train_head(COORD[name], dim)
    print(f"{name} head trained on {n} chains", flush=True)


def run(name, key, max_steps, answerable, thr):
    coord, hd = COORD[name], HEADS[name]
    dim = 1024 if name == "raw" else K_BASIS
    rows, E = BAG[key], emb(key)
    with torch.no_grad():
        tgt = hd(torch.tensor(E)).numpy()
    c = collections.Counter()
    for j, a in enumerate(rows):
        resid, frontier, path = tgt[j].copy(), {a["subject"]}, []
        for _ in range(max_steps):
            best, bg = None, MIN_GAIN
            for r in options_at(frontier):
                g = float(resid @ coord[r])
                if g > bg:
                    best, bg = r, g
            if best is None:
                break
            nxt = step(frontier, best)
            if not nxt:
                break
            frontier, path = nxt, path + [best]
            resid = resid - coord[best]
        rn = float(np.linalg.norm(tgt[j] - sum((coord[r] for r in path),
                                               np.zeros(dim, np.float32))))
        if not path or not frontier or rn > thr:
            c["abstain"] += 1
        elif answerable:
            c["correct" if set(frontier) & set(a["answers"]) else "wrong"] += 1
        else:
            c["wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: c[k] / n for k in ("correct", "wrong", "abstain")} | {"n": n}


# Threshold per representation, calibrated on TRAINED-pair populations plus
# the unanswerable sets (law #6). Pair-clean populations never influence it.
THR = {}
for name in ("raw", "basis"):
    best, bw = None, -1
    for t in (0.3, 0.4, 0.5, 0.6, 0.8, 1.0):
        vals = [run(name, f"train_d{d}", d + 1, True, t)["correct"]
                for d in DEPTHS]
        vals += [run(name, k, 5, False, t)["abstain"]
                 for k in ("brk2", "brk3", "brk4")]
        if min(vals) > bw:
            bw, best = min(vals), t
    THR[name] = best
    print(f"{name}: selected THR={best} (worst-case {bw:.3f} on calibration)")

print("\n=== depth curve, pair-cleanliness separated (D122's rule) ===")
print(f"{'population':20s} {'repr':>6} {'correct':>8} {'wrong':>7} "
      f"{'abstain':>8} {'n':>7}")
res = {}
for d in DEPTHS:
    for suffix in ("clean", "partial"):
        key = f"eval_d{d}_{suffix}"
        if key not in BAG:
            continue
        for name in ("raw", "basis"):
            r = run(name, key, d + 1, True, THR[name])
            res[f"{key}_{name}"] = r
            print(f"{key:20s} {name:>6} {r['correct']:8.3f} {r['wrong']:7.3f} "
                  f"{r['abstain']:8.3f} {r['n']:7d}")
    key = f"train_d{d}"
    for name in ("raw", "basis"):
        r = run(name, key, d + 1, True, THR[name])
        res[f"{key}_{name}"] = r
        print(f"{key:20s} {name:>6} {r['correct']:8.3f} {r['wrong']:7.3f} "
              f"{r['abstain']:8.3f} {r['n']:7d}")

print("\nrefusal by break point")
print(f"{'population':20s} {'repr':>6} {'refused':>8} {'answered':>9}")
for k in ("brk2", "brk3", "brk4"):
    for name in ("raw", "basis"):
        r = run(name, k, 5, False, THR[name])
        res[f"{k}_{name}"] = r
        print(f"{k:20s} {name:>6} {r['abstain']:8.3f} {r['wrong']:9.3f}")

print("\nCOVERAGE DECAY on pair-clean populations (D121's open question)")
for name in ("raw", "basis"):
    row = []
    for d in DEPTHS:
        k = f"eval_d{d}_clean_{name}"
        row.append(f"d{d} {res[k]['correct']:.3f}/{res[k]['wrong']:.3f}"
                   if k in res else f"d{d} —")
    print(f"  {name:6s} " + "   ".join(row) + "   (correct/wrong)")

out = {
    "manifest": run_manifest(seed=SEED, config={"DEPTHS": DEPTHS,
                                                "HOLD_FRAC": HOLD_FRAC,
                                                "K_BASIS": K_BASIS,
                                                "THR": THR}),
    "n_relations": len(RELS), "n_pairs": len(all_pairs),
    "n_held_pairs": len(HOLD_P), "thresholds": THR, "results": res,
    "scope": ("Wiki corpus, natural phrasings, pair-clean holdouts at every "
              "depth (D122's rule: all-pairs-held / partial / trained, never "
              "merged). Two representations side by side because D125 made "
              "the anchor basis the default. Thresholds calibrated per "
              "representation on trained-pair and unanswerable populations "
              "only."),
}
(ROOT / "results" / "exp32_depth4.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp32_depth4.json")
