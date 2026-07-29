"""Reverse traversal: can we ask "who cites X?" — and what does it cost? (D137)

Task 4. The walker reads only the subject side, so inverse questions are
unreachable: "who has X as employer" cannot be asked at all, though
`_by_obj` and `cited_by()` have existed in `foundation/kb.py` since the
adjacency work. This adds reverse edges and measures both halves.

**Pre-registered prediction, from D124.** Adding reverse edges roughly
DOUBLES the options available at each step, and D124 measured refusal falling
monotonically with branching (correlation −0.79 to −0.91). So this should buy
inverse questions and cost forward refusal, and the cost should be visible.
If forward performance is unchanged, D124's branching mechanism is weaker
than that entry claimed and it needs revisiting.

A reverse edge needs its own coordinate or the walker cannot tell "employer
of X" from "employed X"; it gets one from the text "reverse {label}",
projected into the same frozen basis — no new mechanism.

Usage: .venv/bin/python scripts/exp41_reverse.py
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

SEED, MIN_GAIN, K_BASIS, RES_THR, TTHR = 0, 0.2, 48, 0.8, 0.4
CAP = 1000

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

fwd_g, fwd_a = collections.defaultdict(set), collections.defaultdict(set)
rev_g, rev_a = collections.defaultdict(set), collections.defaultdict(set)
for c in wiki:
    fwd_g[(c["subject"], c["pid"])].add(c["object"])
    fwd_a[c["subject"]].add(("f", c["pid"]))
    rev_g[(c["object"], c["pid"])].add(c["subject"])
    rev_a[c["object"]].add(("r", c["pid"]))
subjects = sorted(fwd_a)
objects = sorted(rev_a)
OBJS = sorted({c["object"] for c in wiki} | {c["subject"] for c in wiki})
print(f"{len(wiki)} claims / {len(RELS)} relations")
print(f"forward: {len(subjects)} nodes with outgoing edges; "
      f"reverse: {len(objects)} nodes with incoming edges")

# branching, the quantity D124 says governs refusal
bf = float(np.mean([len(fwd_a[s]) for s in subjects]))
bb = float(np.mean([len(fwd_a.get(n, set()) | rev_a.get(n, set()))
                    for n in sorted(set(subjects) | set(objects))]))
print(f"mean options/step: forward-only {bf:.2f} -> bidirectional {bb:.2f} "
      f"({bb/bf:.2f}x)")

rng = np.random.default_rng(SEED)
GOLD = {("f", k[0], k[1]): v for k, v in fwd_g.items()}
GOLD.update({("r", k[0], k[1]): v for k, v in rev_g.items()})


def qf(s, r):
    return {"node": s, "dir": "f", "rel": r, "answers": sorted(fwd_g[(s, r)]),
            "text": f"What is the {LABEL[r]} of {s}?"}


def qr(o, r):
    return {"node": o, "dir": "r", "rel": r, "answers": sorted(rev_g[(o, r)]),
            "text": f"What has {o} as its {LABEL[r]}?"}


POP = collections.defaultdict(list)
for s in subjects:
    for d, r in sorted(fwd_a[s]):
        POP["forward"].append(qf(s, r))
    for r in RELS:
        if ("f", r) not in fwd_a[s]:
            POP["not_applicable"].append(
                {"node": s, "dir": "f", "rel": r, "answers": [],
                 "text": f"What is the {LABEL[r]} of {s}?"})
for o in objects:
    for d, r in sorted(rev_a[o]):
        POP["inverse"].append(qr(o, r))
for k in list(POP):
    v = sorted(POP[k], key=lambda a: (a["node"], a["rel"]))
    if len(v) > CAP:
        v = [v[i] for i in sorted(rng.choice(len(v), CAP, replace=False))]
    POP[k] = v
    print(f"  {k:16s} {len(v):5d}")

ORDER = sorted(POP)
texts, index = [], {}
for k in ORDER:
    index[k] = (len(texts), len(texts) + len(POP[k]))
    texts += [a["text"] for a in POP[k]]
cache = ROOT / "results" / "exp41_emb.npz"
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    assert list(z["texts"]) == texts and list(z["objs"]) == OBJS, \
        "cache misaligned; delete it"
    Z, Zf, Zr, Zo = z["Z"], z["Zf"], z["Zr"], z["Zo"]
else:
    Z = P.unit(P.embed_texts(texts))
    Zf = P.unit(P.embed_texts([LABEL[r] for r in RELS]))
    Zr = P.unit(P.embed_texts([f"reverse {LABEL[r]}" for r in RELS]))
    Zo = P.unit(P.embed_texts(OBJS))
    np.savez(cache, Z=Z, Zf=Zf, Zr=Zr, Zo=Zo, texts=np.array(texts),
             objs=np.array(OBJS))
PC = P.unit(fit_anchors(np.concatenate([Zf, Zr]), K_BASIS, seed=SEED))
C = {("f", r): P.unit(Zf[i] @ PC.T) for i, r in enumerate(RELS)}
C.update({("r", r): P.unit(Zr[i] @ PC.T) for i, r in enumerate(RELS)})
OI = {o: i for i, o in enumerate(OBJS)}
CENT = {}
for d, src in (("f", fwd_g), ("r", rev_g)):
    for r in RELS:
        ids = [OI[o] for k, v in src.items() if k[1] == r for o in sorted(v)
               if o in OI][:400]
        if ids:
            CENT[(d, r)] = P.unit(Zo[ids].mean(0))
print(f"{len(texts)} questions; {len(C)} directed coordinates, "
      f"{len(CENT)} type centroids", flush=True)


def emb(k):
    a, b = index[k]
    return Z[a:b]


import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

tr = {k: list(range(0, len(POP[k]), 2)) for k in ("forward", "inverse")}
Xs, Ys = [], []
for k, ids in tr.items():
    E = emb(k)
    for j in ids:
        Xs.append(E[j])
        Ys.append(C[(POP[k][j]["dir"], POP[k][j]["rel"])])
X, Y = torch.tensor(np.stack(Xs)), torch.tensor(np.stack(Ys))
torch.manual_seed(SEED)
head = nn.Sequential(nn.Linear(1024, 512), nn.GELU(),
                     nn.Linear(512, K_BASIS))
opt = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-4)
for _ in range(40):
    for b in torch.randperm(len(X)).split(512):
        opt.zero_grad()
        ((head(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
        opt.step()
head.eval()
print(f"head trained on {len(Xs)} directed questions", flush=True)


def run(key, bidirectional, answerable=True):
    rows, E = POP[key], emb(key)
    ids = list(range(1, len(rows), 2)) if key in tr else range(len(rows))
    with torch.no_grad():
        tgt = head(torch.tensor(E)).numpy()
    c = collections.Counter()
    for j in ids:
        a = rows[j]
        opts = set(fwd_a.get(a["node"], set()))
        if bidirectional:
            opts |= rev_a.get(a["node"], set())
        best, bg = None, MIN_GAIN
        for e in sorted(opts):
            g = float(tgt[j] @ C[e])
            if g > bg:
                best, bg = e, g
        frontier = GOLD.get((best[0], a["node"], best[1]), set()) if best \
            else set()
        resid = tgt[j] - (C[best] if best else 0.0)
        rn = float(np.linalg.norm(resid))
        tf = 0.0
        if frontier:
            r_asked = max(C, key=lambda e: float(tgt[j] @ C[e]))
            ids_o = [OI[o] for o in sorted(frontier) if o in OI]
            if ids_o and r_asked in CENT:
                tf = float(np.mean(Zo[ids_o] @ CENT[r_asked]))
        if not best or not frontier or rn > RES_THR or tf < TTHR:
            c["refuse"] += 1
        elif answerable and set(frontier) & set(a["answers"]):
            c["correct"] += 1
        else:
            c["wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: round(c[k] / n, 4) for k in
            ("correct", "wrong", "refuse")} | {"n": n}


print(f"\n{'population':16s} {'walker':>16} {'correct':>8} {'wrong':>7} "
      f"{'refuse':>7}")
res = {}
for key, ans in (("forward", True), ("inverse", True),
                 ("not_applicable", False)):
    for bi in (False, True):
        tag = "bidirectional" if bi else "forward-only"
        r = run(key, bi, ans)
        res[f"{key}_{tag}"] = r
        print(f"{key:16s} {tag:>16} {r['correct']:8.3f} {r['wrong']:7.3f} "
              f"{r['refuse']:7.3f}")
    print()

inv = res["inverse_bidirectional"]
lo, hi = wilson_ci(int(inv["correct"] * inv["n"]), inv["n"])
print(f"inverse questions: unreachable before "
      f"({res['inverse_forward-only']['correct']:.3f}) -> "
      f"{inv['correct']:.3f} CI95 [{lo:.3f}, {hi:.3f}]")
d_fwd = (res["forward_bidirectional"]["correct"]
         - res["forward_forward-only"]["correct"])
d_ref = (res["not_applicable_bidirectional"]["refuse"]
         - res["not_applicable_forward-only"]["refuse"])
print(f"cost to forward answering : {d_fwd:+.3f}")
print(f"cost to not-applicable refusal: {d_ref:+.3f}   "
      f"(D124 predicted a cost from {bb/bf:.2f}x branching)")

out = {
    "manifest": run_manifest(seed=SEED, config={"RES_THR": RES_THR,
                                                "TTHR": TTHR}),
    "branching": {"forward_only": round(bf, 3), "bidirectional": round(bb, 3),
                  "ratio": round(bb / bf, 3)},
    "results": res,
    "inverse_ci95": [round(lo, 4), round(hi, 4)],
    "delta_forward": round(d_fwd, 4), "delta_na_refusal": round(d_ref, 4),
    "scope": ("Reverse edges get their own coordinate from the text "
              "'reverse {label}' projected into the same frozen basis — no "
              "new mechanism. Depth 1 only, since the question is whether "
              "the direction is reachable at all. D134's answer-type gate "
              "is on. The prediction under test is D124's: doubling the "
              "options per step should cost forward refusal."),
}
(ROOT / "results" / "exp41_reverse.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp41_reverse.json")
