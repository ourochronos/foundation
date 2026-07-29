"""The walker on MQuAKE: human-written multi-hop questions (D138).

Task 5, and the largest standing caveat in the project. Every question from
D110 to D137 was templated by me, which D121 and D126 both flagged as a
one-directional confound and D127 showed matters more than composition does.

MQuAKE-CF-3k supplies what our templates cannot:

  * 3,000 cases at chain lengths 2, 3 and 4 — 1,000 each, a natural depth
    axis rather than one I constructed;
  * **three human-written phrasings per case**, so paraphrase robustness is
    measured against real English instead of my alias substitutions;
  * Wikidata PIDs, so the label-derived coordinate machinery (D113/D116)
    applies unchanged — 36 relations, all labelled;
  * ground-truth chains, so the store is built from the benchmark's own
    triples and nothing has to be aligned against our wiki slice.

Phrasing 0 trains, phrasings 1 and 2 are held out. That is the honest version
of the D127 phrasing test: same question, different human wording.

D134's answer-type gate and D137's bidirectional traversal are both on, since
both are now part of the walker. A not-applicable unanswerable set is
included per law #9 — without it refusal is unmeasurable.

Usage: .venv/bin/python scripts/exp42_natural.py
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

SEED, MIN_GAIN, K_BASIS, RES_THR, TTHR = 0, 0.2, 48, 0.8, 0.35
CAP_NA = 1500

props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
cases = json.loads((ROOT / "data" / "mquake" / "MQuAKE-CF-3k.json").read_text())

gold, avail, rgold, ravail = (collections.defaultdict(set),
                              collections.defaultdict(set),
                              collections.defaultdict(set),
                              collections.defaultdict(set))
RELS, LABEL = set(), {}
for c in cases:
    for (s, p, o), (sl, pl, ol) in zip(c["orig"]["triples"],
                                       c["orig"]["triples_labeled"]):
        if p not in props:
            continue
        RELS.add(p)
        LABEL[p] = props[p]["label"]
        gold[(sl, p)].add(ol)
        avail[sl].add(("f", p))
        rgold[(ol, p)].add(sl)
        ravail[ol].add(("r", p))
RELS = sorted(RELS)
print(f"{len(cases)} MQuAKE cases -> store with {len(gold)} forward pairs, "
      f"{len(RELS)} relations, {len(avail)} subjects")

# questions: chain length from the case, answer from the case
Q = collections.defaultdict(list)
for c in cases:
    d = len(c["orig"]["triples"])
    if d not in (2, 3, 4):
        continue
    subj = c["orig"]["triples_labeled"][0][0]
    ans = [c["answer"]] + list(c.get("answer_alias", []))
    for pi, qt in enumerate(c["questions"][:3]):
        key = f"d{d}_p{'0' if pi == 0 else 'held'}"
        Q[key].append({"node": subj, "answers": ans, "text": qt,
                       "depth": d, "chain": [t[1] for t in
                                             c["orig"]["triples"]]})
# law #9: not-applicable — a real relation that this subject does not have
rng = np.random.default_rng(SEED)
subs = sorted(avail)
na = []
for s in subs:
    have = {r for d_, r in avail[s]}
    for r in RELS:
        if r not in have:
            na.append({"node": s, "answers": [],
                       "text": f"What is the {LABEL[r]} of {s}?",
                       "depth": 1, "chain": [r]})
na.sort(key=lambda a: (a["node"], a["chain"][0]))
Q["not_applicable"] = [na[i] for i in
                       sorted(rng.choice(len(na), min(CAP_NA, len(na)),
                                         replace=False))]
for k in sorted(Q):
    print(f"  {k:16s} {len(Q[k]):5d}")

ENTS = sorted({e for k in gold for e in ({k[0]} | gold[k])})
ORDER = sorted(Q)
texts, index = [], {}
for k in ORDER:
    index[k] = (len(texts), len(texts) + len(Q[k]))
    texts += [a["text"] for a in Q[k]]
cache = ROOT / "results" / "exp42_emb.npz"
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    assert list(z["texts"]) == texts and list(z["ents"]) == ENTS, \
        "cache misaligned; delete it"
    Z, Zf, Zr, Ze = z["Z"], z["Zf"], z["Zr"], z["Ze"]
else:
    Z = P.unit(P.embed_texts(texts))
    Zf = P.unit(P.embed_texts([LABEL[r] for r in RELS]))
    Zr = P.unit(P.embed_texts([f"reverse {LABEL[r]}" for r in RELS]))
    Ze = P.unit(P.embed_texts(ENTS))
    np.savez(cache, Z=Z, Zf=Zf, Zr=Zr, Ze=Ze, texts=np.array(texts),
             ents=np.array(ENTS))
PC = P.unit(fit_anchors(np.concatenate([Zf, Zr]), K_BASIS, seed=SEED))
C = {("f", r): P.unit(Zf[i] @ PC.T) for i, r in enumerate(RELS)}
C.update({("r", r): P.unit(Zr[i] @ PC.T) for i, r in enumerate(RELS)})
EI = {e: i for i, e in enumerate(ENTS)}
CENT = {}
for r in RELS:
    ids = [EI[o] for k, v in gold.items() if k[1] == r for o in sorted(v)
           if o in EI][:400]
    if ids:
        CENT[("f", r)] = P.unit(Ze[ids].mean(0))
print(f"{len(texts)} questions, {len(ENTS)} entities, {len(CENT)} centroids",
      flush=True)


def emb(k):
    a, b = index[k]
    return Z[a:b]


import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

Xs, Ys = [], []
for d in (2, 3, 4):
    k = f"d{d}_p0"
    E = emb(k)
    for j, a in enumerate(Q[k]):
        Xs.append(E[j])
        Ys.append(sum(C[("f", r)] for r in a["chain"]))
X, Y = torch.tensor(np.stack(Xs)), torch.tensor(np.stack(Ys))
torch.manual_seed(SEED)
head = nn.Sequential(nn.Linear(1024, 512), nn.GELU(),
                     nn.Linear(512, K_BASIS))
opt = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-4)
for _ in range(60):
    for b in torch.randperm(len(X)).split(512):
        opt.zero_grad()
        ((head(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
        opt.step()
head.eval()
print(f"head trained on {len(Xs)} phrasing-0 questions only", flush=True)


def step(node_set, e):
    d, r = e
    src = gold if d == "f" else rgold
    out = set()
    for n in node_set:
        out |= src.get((n, r), set())
    return out


def run(key, answerable=True, max_steps=None):
    rows, E = Q[key], emb(key)
    with torch.no_grad():
        tgt = head(torch.tensor(E)).numpy()
    c = collections.Counter()
    for j, a in enumerate(rows):
        ms = max_steps or a["depth"] + 1
        resid, frontier, path = tgt[j].copy(), {a["node"]}, []
        for _ in range(ms):
            opts = set()
            for n in frontier:
                opts |= avail.get(n, set()) | ravail.get(n, set())
            if not opts:
                break
            g = sorted(((float(resid @ C[e]), e) for e in sorted(opts)),
                       reverse=True)
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
            r_asked = max(CENT, key=lambda e: float(tgt[j] @ C[e]))
            ids = [EI[o] for o in sorted(frontier) if o in EI]
            if ids:
                tf = float(np.mean(Ze[ids] @ CENT[r_asked]))
        low = {x.lower() for x in a["answers"]}
        if not path or not frontier or rn > RES_THR or tf < TTHR:
            c["refuse"] += 1
        elif answerable and {f.lower() for f in frontier} & low:
            c["correct"] += 1
        else:
            c["wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: round(c[k] / n, 4) for k in
            ("correct", "wrong", "refuse")} | {"n": n}


print(f"\n=== HUMAN-WRITTEN QUESTIONS ===")
print(f"{'population':18s} {'correct':>8} {'wrong':>7} {'refuse':>7} "
      f"{'n':>6}")
res = {}
for d in (2, 3, 4):
    for tag in ("p0", "pheld"):
        k = f"d{d}_{tag}"
        r = run(k)
        res[k] = r
        lbl = f"depth {d} " + ("trained phrasing" if tag == "p0"
                               else "HELD-OUT phrasing")
        print(f"{lbl:18s} {r['correct']:8.3f} {r['wrong']:7.3f} "
              f"{r['refuse']:7.3f} {r['n']:6d}")
r = run("not_applicable", False, 2)
res["not_applicable"] = r
print(f"{'not_applicable':18s} {'—':>8} {r['wrong']:7.3f} {r['refuse']:7.3f} "
      f"{r['n']:6d}")

print("\nphrasing cost on HUMAN paraphrases (trained -> held-out)")
for d in (2, 3, 4):
    a, b = res[f"d{d}_p0"]["correct"], res[f"d{d}_pheld"]["correct"]
    print(f"  depth {d}: {a:.3f} -> {b:.3f}  ({b - a:+.3f})")
print("  D127 measured -0.719 for ALIAS substitution on templated questions")

k = "d2_pheld"
lo, hi = wilson_ci(int(res[k]["correct"] * res[k]["n"]), res[k]["n"])
print(f"\ndepth-2 held-out human phrasing: {res[k]['correct']:.3f} "
      f"CI95 [{lo:.3f}, {hi:.3f}]")

out = {
    "manifest": run_manifest(seed=SEED, config={"RES_THR": RES_THR,
                                                "TTHR": TTHR,
                                                "K_BASIS": K_BASIS}),
    "n_cases": len(cases), "n_relations": len(RELS),
    "n_forward_pairs": len(gold), "results": res,
    "scope": ("Store built from MQuAKE-CF-3k's own ground-truth triples; "
              "questions are the benchmark's three HUMAN-WRITTEN phrasings "
              "per case, with phrasing 0 trained and 1-2 held out. Depth is "
              "the benchmark's own chain length (2/3/4, 1000 cases each), "
              "not a construction of ours. Relation coordinates are "
              "label-derived (D113/D116); D134's answer-type gate and "
              "D137's bidirectional traversal are on. A not-applicable set "
              "is included per law #9. Answers are matched against MQuAKE's "
              "answer aliases, case-folded."),
}
(ROOT / "results" / "exp42_natural.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp42_natural.json")
