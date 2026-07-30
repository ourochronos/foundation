"""Entity generalisation: does it work on subjects it never trained on? (D149)

Task 3, and the one axis this project has never tested. We have held out
relations (D125), relation pairs (D123), phrasings (D127/D138), instances
(D131) and depths (D119/D121) — never **entities**. It sits in "what we
cannot claim" in both `docs/18` and the draft, and it is the first question a
reader will ask.

**Design.** 25% of subjects are held out **from training questions only**.
Their claims stay in the store, so they remain walkable — only questions
*about* them are absent from the head's training. That is the right test: the
store is not being asked to contain something new, the reasoner is being
asked to answer about an entity it was never trained on.

**Expected positive**, since the head predicts a sum of *relation*
coordinates and never sees an entity identity as a target. That is exactly
why it is worth running: an expected-positive that fails is the most
informative result available, and if it passes it closes a stated limitation
for the cost of one experiment.

Reported per law #9 with the mixed unanswerable populations, and with 1-NN
alongside the head per D129's addendum — retrieval's bank contains only
seen-subject questions, so held-out subjects have no same-subject neighbour
and it must generalise on phrasing alone.

Usage: .venv/bin/python scripts/exp50_entity.py
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

SEED, MIN_GAIN, K_BASIS, RES_THR, TTHR = 0, 0.2, 48, 0.8, 0.40
HOLD_FRAC, CAP = 0.25, 800

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
OBJS = sorted({c["object"] for c in wiki})
rng = np.random.default_rng(SEED)
HELD_S = {subjects[i] for i in
          sorted(rng.permutation(len(subjects))[:int(HOLD_FRAC
                                                     * len(subjects))])}
print(f"{len(wiki)} claims / {len(RELS)} relations / {len(subjects)} subjects")
print(f"held out from TRAINING QUESTIONS: {len(HELD_S)} subjects "
      f"(their claims remain in the store)")
print(f"relations still covered by seen subjects: "
      f"{len({c['pid'] for c in wiki if c['subject'] not in HELD_S})}"
      f"/{len(RELS)}")


def step(nodes, r):
    out = set()
    for s in nodes:
        out |= gold.get((s, r), set())
    return out


def opts_at(nodes):
    o = set()
    for s in nodes:
        o |= avail.get(s, set())
    return o


def t1(s, r):
    return f"What is the {LABEL[r]} of {s}?"


def t2(s, r1, r2):
    return f"What is the {LABEL[r2]} of the {LABEL[r1]} of {s}?"


POP = collections.defaultdict(list)
for s in subjects:
    tag = "held" if s in HELD_S else "seen"
    for r in sorted(avail[s]):
        POP[f"d1_{tag}"].append({"subject": s, "chain": [r],
                                 "answers": sorted(gold[(s, r)]),
                                 "text": t1(s, r)})
        m1 = step({s}, r)
        for r2 in sorted(opts_at(m1)):
            if step(m1, r2):
                POP[f"d2_{tag}"].append(
                    {"subject": s, "chain": [r, r2],
                     "answers": sorted(step(m1, r2))[:300],
                     "text": t2(s, r, r2)})
        # law #9: relation real, entity real, pair absent
    for r in RELS:
        if r not in avail[s]:
            POP[f"na_{tag}"].append({"subject": s, "chain": [r],
                                     "answers": [], "text": t1(s, r)})
for k in list(POP):
    v = sorted(POP[k], key=lambda a: (a["subject"], ">".join(a["chain"])))
    if len(v) > CAP:
        v = [v[i] for i in sorted(rng.choice(len(v), CAP, replace=False))]
    POP[k] = v
    print(f"  {k:10s} {len(v):5d}")

ORDER = sorted(POP)
texts, index = [], {}
for k in ORDER:
    index[k] = (len(texts), len(texts) + len(POP[k]))
    texts += [a["text"] for a in POP[k]]
cache = ROOT / "results" / "exp50_emb.npz"
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    assert list(z["texts"]) == texts and list(z["objs"]) == OBJS, \
        "cache misaligned; delete it"
    Z, Zl, Zo = z["Z"], z["Zl"], z["Zo"]
else:
    Z = P.unit(P.embed_texts(texts))
    Zl = P.unit(P.embed_texts([LABEL[r] for r in RELS]))
    Zo = P.unit(P.embed_texts(OBJS))
    np.savez(cache, Z=Z, Zl=Zl, Zo=Zo, texts=np.array(texts),
             objs=np.array(OBJS))
RC = {r: Zl[i] for i, r in enumerate(RELS)}
OI = {o: i for i, o in enumerate(OBJS)}
PC = P.unit(fit_anchors(Zl, min(K_BASIS, len(RELS)), seed=SEED))
K_EFF = PC.shape[0]
C = {r: P.unit(RC[r] @ PC.T) for r in RELS}
CENT = {}
for r in RELS:
    ids = [OI[o] for k, v in gold.items() if k[1] == r for o in sorted(v)
           if o in OI][:400]
    if ids:
        CENT[r] = P.unit(Zo[ids].mean(0))
print(f"{len(texts)} questions embedded", flush=True)


def emb(k):
    a, b = index[k]
    return Z[a:b]


import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

# train ONLY on seen-subject questions; held-out subjects contribute nothing
Xs, Ys, bankX, bankY = [], [], [], []
for k in ("d1_seen", "d2_seen"):
    E = emb(k)
    for j, a in enumerate(POP[k]):
        Xs.append(E[j])
        Ys.append(sum(C[r] for r in a["chain"]))
        bankX.append(E[j])
        bankY.append(sum(C[r] for r in a["chain"]))
X, Y = torch.tensor(np.stack(Xs)), torch.tensor(np.stack(Ys))
BX, BY = np.stack(bankX), np.stack(bankY)
torch.manual_seed(SEED)
head = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, K_EFF))
opt = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-4)
for _ in range(40):
    for b in torch.randperm(len(X)).split(512):
        opt.zero_grad()
        ((head(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
        opt.step()
head.eval()
print(f"head + retrieval bank built from {len(Xs)} SEEN-subject questions "
      f"only", flush=True)


def run(key, mode, answerable, max_steps):
    rows, E = POP[key], emb(key)
    if mode == "head":
        with torch.no_grad():
            tgt = head(torch.tensor(E)).numpy()
    else:
        tgt = BY[(E @ BX.T).argmax(1)]
    c = collections.Counter()
    for j, a in enumerate(rows):
        resid, frontier, path = tgt[j].copy(), {a["subject"]}, []
        for _ in range(max_steps):
            o = sorted(opts_at(frontier)) if frontier else []
            if not o:
                break
            g = sorted(((float(resid @ C[r]), r) for r in o), reverse=True)
            if g[0][0] <= MIN_GAIN:
                break
            nxt = step(frontier, g[0][1])
            if not nxt:
                break
            frontier, path = nxt, path + [g[0][1]]
            resid = resid - C[g[0][1]]
        rn = float(np.linalg.norm(resid))
        tf = 0.0
        if frontier:
            r_asked = max(CENT, key=lambda r: float(tgt[j] @ C[r]))
            ids = [OI[o_] for o_ in sorted(frontier) if o_ in OI]
            if ids:
                tf = float(np.mean(Zo[ids] @ CENT[r_asked]))
        if not path or not frontier or rn > RES_THR or tf < TTHR:
            c["refuse"] += 1
        elif answerable and set(frontier) & set(a["answers"]):
            c["correct"] += 1
        else:
            c["wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: round(c[k] / n, 4) for k in
            ("correct", "wrong", "refuse")} | {"n": n}


print(f"\n{'population':12s} {'mode':>10} {'correct':>8} {'wrong':>7} "
      f"{'refuse':>7} {'n':>6}")
res = {}
for base, ans, ms in (("d1", True, 2), ("d2", True, 3), ("na", False, 2)):
    for tag in ("seen", "held"):
        for mode in ("head", "knn"):
            k = f"{base}_{tag}"
            r = run(k, mode, ans, ms)
            res[f"{k}_{mode}"] = r
            print(f"{k:12s} {mode:>10} {r['correct']:8.3f} {r['wrong']:7.3f} "
                  f"{r['refuse']:7.3f} {r['n']:6d}")
    print()

print("SEEN vs HELD-OUT subjects (the entity-generalisation gap)")
gaps = {}
for base, key in (("d1", "correct"), ("d2", "correct"), ("na", "refuse")):
    for mode in ("head", "knn"):
        s_ = res[f"{base}_seen_{mode}"][key]
        h_ = res[f"{base}_held_{mode}"][key]
        gaps[f"{base}_{mode}"] = round(h_ - s_, 4)
        print(f"  {base}_{mode:5s} {key:8s} seen {s_:.3f} -> held {h_:.3f}"
              f"   {h_-s_:+.3f}")

k = "d1_held_head"
lo, hi = wilson_ci(int(res[k]["correct"] * res[k]["n"]), res[k]["n"])
worst = max(abs(v) for v in gaps.values())
print(f"\nheld-out-subject depth-1 (head): {res[k]['correct']:.3f} "
      f"CI95 [{lo:.3f}, {hi:.3f}]")
print(f"largest gap across all six comparisons: {worst:.3f}")
verdict = ("ENTITY GENERALISATION HOLDS — no gap exceeds 0.05"
           if worst <= 0.05 else
           f"a gap of {worst:.3f} appears; entities are NOT free")
print(f"  {verdict}")

out = {
    "manifest": run_manifest(seed=SEED, config={"HOLD_FRAC": HOLD_FRAC,
                                                "RES_THR": RES_THR,
                                                "TTHR": TTHR}),
    "n_held_subjects": len(HELD_S), "results": res, "gaps": gaps,
    "largest_gap": worst, "verdict": verdict,
    "scope": ("Subjects are held out of TRAINING QUESTIONS only; their "
              "claims remain in the store and stay walkable, so this "
              "measures whether the reasoner generalises to an entity it "
              "never trained on — not whether the store can hold new ones "
              "(D131 covers that). The retrieval bank likewise contains "
              "only seen-subject questions, so held-out subjects have no "
              "same-subject neighbour. Unanswerable population is "
              "not-applicable per law #9, split the same way."),
}
(ROOT / "results" / "exp50_entity.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp50_entity.json")
