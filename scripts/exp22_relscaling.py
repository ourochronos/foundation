"""What actually limits novel-relation transfer: basis width, or how many
relations you have trained on? (D115)

D114 said the anchor CONTENT is the mechanism. D115's over-provisioning runs
then failed twice in a row to improve on a tiny corpus-fit basis:

  corpus-fit k-means, 18 in-domain relations, K=8   0.286
  external k-means over 13,713 properties, K=8-512  0.106 - 0.163
  landmark basis, 512 - 13,713 property vectors     0.104 - 0.120

Two explanations were tried and neither survived: coverage (the external
basis has ample span at K=512) and discriminability (landmarks improved
mean off-diagonal cosine to 0.940 and top-1 did not move).

What is invariant across every one of those runs is the thing never varied:
**the head sees exactly 18 distinct relation targets.** A narrow basis may
be winning not because it represents relations better, but because 18
examples constrain a map into 8 dimensions and constrain nothing at all in
13,713. If that is right, the scaling axis is the RELATION VOCABULARY, not
the basis — and over-provisioned anchors cannot help until it grows.

So: hold the basis recipe fixed, hold the held-out relations fixed, and vary
only how many relations are trained on.

Usage: .venv/bin/python scripts/exp22_relscaling.py
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

MIN_N, PER_REL, N_HELD, SEED = 20, 150, 8, 0
K_BASIS = 8

sch = {d["pid"]: d for d in
       json.loads((ROOT / "data" / "schema_v0.json").read_text())}
kb = KB(backend="pg", table="poc")
wiki = [c for c in kb.claims
        if not c["page"].startswith(("arxiv:", "hf:", "user"))]
cnt = collections.Counter(c["pid"] for c in wiki)
RELS = sorted(p for p, n in cnt.items()
              if n >= MIN_N and p in sch
              and len(sch[p].get("aliases", ())) >= 2)
rng = np.random.default_rng(SEED)
perm = list(RELS)
rng.shuffle(perm)
HELD_R = sorted(perm[:N_HELD])
POOL_R = perm[N_HELD:]                       # candidates to train on
print(f"{len(RELS)} relations (n>={MIN_N}); {len(HELD_R)} held out, "
      f"{len(POOL_R)} available to train on")

by_rel = collections.defaultdict(list)
for c in wiki:
    if c["pid"] in RELS:
        by_rel[c["pid"]].append(c)
facts = []
for r in RELS:
    xs = by_rel[r]
    if len(xs) > PER_REL:
        xs = [xs[i] for i in rng.choice(len(xs), PER_REL, replace=False)]
    facts.extend(xs)
FRAMES = ["What is the {a} of {s}?", "For {s}, what is the {a}?"]
queries = []
for f in facts:
    for a in sch[f["pid"]]["aliases"]:
        for fr in FRAMES:
            queries.append({"pid": f["pid"], "subject": f["subject"],
                            "object": f["object"],
                            "text": fr.format(a=a, s=f["subject"])})
print(f"{len(queries)} questions", flush=True)

cache = ROOT / "results" / "exp22_emb.npz"
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    Zq, Zl, lab_order = z["Zq"], z["Zl"], list(z["lab_order"])
else:
    Zq = P.unit(P.embed_texts([q["text"] for q in queries]))
    lab_order = list(RELS)
    Zl = P.unit(P.embed_texts([sch[p]["label"] for p in lab_order]))
    np.savez(cache, Zq=Zq, Zl=Zl, lab_order=np.array(lab_order))
V = {p: Zl[i] for i, p in enumerate(lab_order)}
print(f"embeddings {Zq.shape}", flush=True)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

gold = collections.defaultdict(set)
for c in wiki:
    gold[(c["subject"], c["pid"])].add(c["object"])
he_i = [i for i, q in enumerate(queries) if q["pid"] in HELD_R]
Xhe = torch.tensor(Zq[he_i])
ri = {r: i for i, r in enumerate(RELS)}


def run(train_rels, seed):
    """Basis refit on exactly these train relations — the realistic setting,
    where you only have the vocabulary you actually have."""
    k = min(K_BASIS, len(train_rels))
    PC = P.unit(fit_anchors(np.stack([V[r] for r in train_rels]), k,
                            seed=SEED))
    C = {p: P.unit(V[p] @ PC.T) for p in RELS}
    tr_i = [i for i, q in enumerate(queries) if q["pid"] in set(train_rels)]
    Xtr = torch.tensor(Zq[tr_i])
    torch.manual_seed(seed)
    Y = torch.tensor(np.stack([C[queries[i]["pid"]] for i in tr_i]))
    hd = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, k))
    opt = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(Xtr)).split(512):
            opt.zero_grad()
            pr = hd(Xtr[b])
            pr = pr / (pr.norm(dim=-1, keepdim=True) + 1e-9)
            (1 - (pr * Y[b]).sum(-1)).mean().backward()
            opt.step()
    hd.eval()
    M = np.stack([C[r] for r in RELS])
    with torch.no_grad():
        ph = hd(Xhe).numpy()
    ph = ph / (np.linalg.norm(ph, axis=1, keepdims=True) + 1e-9)
    Sh = ph @ M.T
    h1 = float(np.mean([int(np.argmax(Sh[j]) == ri[queries[i]["pid"]])
                        for j, i in enumerate(he_i)]))
    tal = collections.Counter()
    for j, i in enumerate(he_i):
        q = queries[i]
        got = gold.get((q["subject"], RELS[int(np.argmax(Sh[j]))]), set())
        tal["abstain" if not got else
            ("correct" if q["object"] in got else "wrong")] += 1
    a = tal["correct"] + tal["wrong"]
    return h1, (tal["correct"] / a if a else 0.0)


# Several random subsets per size: with so few relations, WHICH ones you get
# matters as much as how many, and a single draw would be indistinguishable
# from luck.
SIZES = [r for r in (4, 6, 8, 12, 16, 20, 24, len(POOL_R)) if r <= len(POOL_R)]
SIZES = sorted(set(SIZES))
REPS = 5
print(f"\nheld-out top-1 vs NUMBER OF TRAINING RELATIONS "
      f"(basis refit each time, K={K_BASIS}, chance {1/len(RELS):.3f})")
print(f"{'n_train':>8} {'top-1 mean':>11} {'min':>7} {'max':>7} "
      f"{'e2e prec':>10}")
curve = {}
for n in SIZES:
    hs, ps = [], []
    for rep in range(REPS):
        sub = list(np.random.default_rng(100 + rep).permutation(POOL_R)[:n])
        h, pr = run(sub, seed=rep)
        hs.append(h)
        ps.append(pr)
    curve[n] = {"top1_mean": float(np.mean(hs)), "top1_min": float(min(hs)),
                "top1_max": float(max(hs)),
                "e2e_precision_mean": float(np.mean(ps)), "reps": REPS}
    print(f"{n:8d} {np.mean(hs):11.3f} {min(hs):7.3f} {max(hs):7.3f} "
          f"{np.mean(ps):10.3f}", flush=True)

lo_s, hi_s = SIZES[0], SIZES[-1]
print(f"\n{lo_s} -> {hi_s} training relations: top-1 "
      f"{curve[lo_s]['top1_mean']:.3f} -> {curve[hi_s]['top1_mean']:.3f}, "
      f"e2e precision {curve[lo_s]['e2e_precision_mean']:.3f} -> "
      f"{curve[hi_s]['e2e_precision_mean']:.3f}")

out = {
    "manifest": run_manifest(seed=SEED, config={"MIN_N": MIN_N,
                                                "K_BASIS": K_BASIS,
                                                "REPS": REPS,
                                                "held_out": HELD_R}),
    "n_relations": len(RELS), "n_held_out_q": len(he_i),
    "chance_top1": round(1 / len(RELS), 4),
    "curve": curve,
    "scope": ("Only the NUMBER of training relations varies; the basis "
              "recipe (k-means, K=8, refit on the train subset) and the 8 "
              "held-out relations are fixed. 5 random subsets per size, "
              "because which relations you draw matters as much as how "
              "many at this scale. Single-hop."),
}
(ROOT / "results" / "exp22_relscaling.json").write_text(json.dumps(out,
                                                                   indent=1))
print("\n[done] results/exp22_relscaling.json")
