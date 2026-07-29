"""Over-provisioned relation basis from the full Wikidata property set (D115).

D114 hit a hard cap: a relation-anchor basis fit by k-means cannot be wider
than the number of relations you already know (18, so K=32 was unrunnable).
That is D6's problem on a new axis, and D6's answer applies — over-provision
ONCE from a large vocabulary, freeze, and let every relation thereafter be a
projection into it. 13,713 labelled Wikidata properties, fetched once to
`data/wikidata_properties.json`.

This is the strongest form of the reindex-free claim available to us: the
basis is fit from an EXTERNAL vocabulary that never saw this corpus, so
every one of our relations — trained and held-out alike — enters only as
coordinates. Nothing about minting a new relation moves the basis.

Two pool variants, because they answer different questions:

  full      — all 13,713 properties, our 26 included. The realistic
              deployment case: a global basis contains everything the
              vocabulary knows, and novelty is relative to the HEAD, which
              still only ever trains on 18 relations.
  excluded  — our 26 relations removed from the pool. The strict case: a
              relation whose label was absent even when the basis was
              built. If this holds up, coordinates for a genuinely
              unforeseen relation are real.

The basis pool is unsupervised throughout — it never sees a query, a label
split, or which relations are held out.

Usage: .venv/bin/python scripts/exp21_overprovision.py
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

MIN_N, PER_REL, N_HELD, SEED = 50, 150, 8, 0
KS = [8, 16, 32, 64, 128, 256, 512]

sch = {d["pid"]: d for d in
       json.loads((ROOT / "data" / "schema_v0.json").read_text())}
props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
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
HELD_R, TRAIN_R = sorted(perm[:N_HELD]), sorted(perm[N_HELD:])

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

z = np.load(ROOT / "results" / "exp19_emb.npz", allow_pickle=True)
Zq, Zl, lab_order = z["Zq"], z["Zl"], list(z["lab_order"])
assert len(Zq) == len(queries), "query construction drifted from D113"
V = {p: Zl[i] for i, p in enumerate(lab_order)}
print(f"{len(RELS)} corpus relations ({len(HELD_R)} held out), "
      f"{len(queries)} questions, {len(props)} Wikidata properties")

pcache = ROOT / "results" / "exp21_prop_emb.npz"
if pcache.exists():
    d = np.load(pcache, allow_pickle=True)
    Zp, p_order = d["Zp"], list(d["p_order"])
else:
    p_order = sorted(props)
    Zp = P.unit(P.embed_texts([props[p]["label"] for p in p_order]))
    np.savez(pcache, Zp=Zp, p_order=np.array(p_order))
print(f"property-label embeddings {Zp.shape}", flush=True)

OURS = set(RELS)
POOLS = {
    "full 13.7k": Zp,
    "excluded (ours removed)": Zp[[i for i, p in enumerate(p_order)
                                   if p not in OURS]],
}
print("pool sizes: " + ", ".join(f"{k} {v.shape[0]}" for k, v in POOLS.items()))

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

tr_i = [i for i, q in enumerate(queries) if q["pid"] in TRAIN_R]
he_i = [i for i, q in enumerate(queries) if q["pid"] in HELD_R]
gold = collections.defaultdict(set)
for c in wiki:
    gold[(c["subject"], c["pid"])].add(c["object"])
Xtr, Xhe = torch.tensor(Zq[tr_i]), torch.tensor(Zq[he_i])
ri = {r: i for i, r in enumerate(RELS)}


def evaluate(PC):
    C = {p: P.unit(V[p] @ PC.T) for p in RELS}
    k = PC.shape[0]
    torch.manual_seed(SEED)
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
        ph, pt = hd(Xhe).numpy(), hd(Xtr).numpy()
    ph = ph / (np.linalg.norm(ph, axis=1, keepdims=True) + 1e-9)
    pt = pt / (np.linalg.norm(pt, axis=1, keepdims=True) + 1e-9)
    Sh, St = ph @ M.T, pt @ M.T
    h1 = float(np.mean([int(np.argmax(Sh[j]) == ri[queries[i]["pid"]])
                        for j, i in enumerate(he_i)]))
    t1 = float(np.mean([int(np.argmax(St[j]) == ri[queries[i]["pid"]])
                        for j, i in enumerate(tr_i)]))
    tal = collections.Counter()
    for j, i in enumerate(he_i):
        q = queries[i]
        got = gold.get((q["subject"], RELS[int(np.argmax(Sh[j]))]), set())
        tal["abstain" if not got else
            ("correct" if q["object"] in got else "wrong")] += 1
    a = tal["correct"] + tal["wrong"]
    return h1, t1, (tal["correct"] / a if a else 0.0), dict(tal)


print(f"\nHELD-OUT-RELATION top-1  (chance {1/len(RELS):.3f}, n={len(he_i)})")
print(f"{'K':>6}" + "".join(f"{k:>26s}" for k in POOLS))
grid = {}
for k in KS:
    row = {}
    for name, pool in POOLS.items():
        row[name] = evaluate(P.unit(fit_anchors(pool, k, seed=SEED)))
    grid[k] = row
    print(f"{k:6d}" + "".join(f"{row[n][0]:26.3f}" for n in POOLS), flush=True)

print(f"\ntrain-relation top-1 (control)")
print(f"{'K':>6}" + "".join(f"{k:>26s}" for k in POOLS))
for k in KS:
    print(f"{k:6d}" + "".join(f"{grid[k][n][1]:26.3f}" for n in POOLS))

print(f"\nend-to-end precision-when-answered, HELD-OUT relations, live store")
print(f"{'K':>6}" + "".join(f"{k:>26s}" for k in POOLS))
for k in KS:
    print(f"{k:6d}" + "".join(f"{grid[k][n][2]:26.3f}" for n in POOLS))

D114_BEST, D114_K = 0.286, 16          # corpus-fit relation basis, capped
best = {n: max(KS, key=lambda k: grid[k][n][0]) for n in POOLS}
print(f"\nD114 corpus-fit relation basis (capped at 18): {D114_BEST:.3f} "
      f"at K={D114_K}")
for n in POOLS:
    k = best[n]
    lo, hi = wilson_ci(int(grid[k][n][0] * len(he_i)), len(he_i))
    print(f"  {n:26s} best {grid[k][n][0]:.3f} at K={k}  CI95 "
          f"[{lo:.3f}, {hi:.3f}]  e2e precision {grid[k][n][2]:.3f}")

out = {
    "manifest": run_manifest(seed=SEED, config={"KS": KS,
                                                "held_out": HELD_R,
                                                "n_properties": len(props)}),
    "chance_top1": round(1 / len(RELS), 4), "n_held_out_q": len(he_i),
    "d114_corpus_fit_best": {"top1": D114_BEST, "K": D114_K, "cap": 18},
    "grid": {str(k): {n: {"held_out_top1": round(v[0], 4),
                          "train_top1": round(v[1], 4),
                          "end_to_end_precision": round(v[2], 4),
                          "end_to_end": v[3]}
                      for n, v in row.items()} for k, row in grid.items()},
    "best_K": best,
    "scope": ("Relation basis fit from an EXTERNAL vocabulary (13,713 "
              "Wikidata property labels) that never saw this corpus, its "
              "queries, or the train/held-out split. Every corpus relation "
              "enters as a projection. 'excluded' additionally removes our "
              "26 relations from the basis pool. Single-hop; same 8 "
              "held-out relations and unstratified split as D113/D114."),
}
(ROOT / "results" / "exp21_overprovision.json").write_text(
    json.dumps(out, indent=1))
print("\n[done] results/exp21_overprovision.json")

# ---------------------------------------------------------------------------
# Why did over-provisioning LOSE? Two candidate mechanisms, distinguishable:
#   (1) coverage — a basis fit on 13.7k mostly-irrelevant properties spends
#       its centroids elsewhere, so our relations project onto little of it;
#   (2) discriminability — the span is fine, but our 26 relations land close
#       together in it, so top-1 among them collapses.
# These need different fixes (more anchors vs a distribution-matched pool),
# so guessing between them is not acceptable.
# ---------------------------------------------------------------------------
def diagnose(PC, label):
    C = {p: V[p] @ PC.T for p in RELS}
    keep = float(np.mean([np.linalg.norm(C[p]) for p in RELS]))   # ||.||<=1
    U = np.stack([P.unit(C[p]) for p in RELS])
    S = U @ U.T
    off = S[~np.eye(len(RELS), dtype=bool)]
    held = [ri[r] for r in HELD_R]
    tr = [ri[r] for r in TRAIN_R]
    nearest = float(np.mean([S[h][tr].max() for h in held]))
    print(f"  {label:34s} K={PC.shape[0]:4d}  variance kept {keep:.3f}  "
          f"mean off-diag cos {off.mean():.3f}  "
          f"held-out's nearest TRAIN relation cos {nearest:.3f}")
    return {"variance_kept": round(keep, 4),
            "mean_offdiag_cos": round(float(off.mean()), 4),
            "held_nearest_train_cos": round(nearest, 4)}


print("\nbasis diagnostics — coverage vs discriminability")
from codec.evals.anchors import fit_anchors as _fa               # noqa: E402
diag = {}
diag["corpus-fit relations (D114)"] = diagnose(
    P.unit(_fa(np.stack([V[r] for r in TRAIN_R]), 8, seed=SEED)),
    "corpus-fit relations (D114)")
for k in (8, 32, 512):
    diag[f"external full K={k}"] = diagnose(
        P.unit(_fa(POOLS["full 13.7k"], k, seed=SEED)), "external full")
out["basis_diagnostics"] = diag
(ROOT / "results" / "exp21_overprovision.json").write_text(
    json.dumps(out, indent=1))
print("[done] diagnostics appended")

# ---------------------------------------------------------------------------
# The diagnosis says k-means is the problem, not the vocabulary: centroids
# are allocated by POOL DENSITY, and our 26 relations sit in a small region
# that a 13.7k-property pool has no reason to resolve finely. So drop the
# clustering. Use the property vectors THEMSELVES as landmarks — every known
# relation is an anchor, a relation's coordinates are its similarity profile
# over the whole vocabulary, and resolution exists wherever the vocabulary
# does. This is over-provisioning in its most literal form, and it is what
# D6 arguably always meant.
# ---------------------------------------------------------------------------
print("\nlandmark bases (property vectors as anchors, no k-means)")
print(f"{'landmarks':>28} {'held-out top1':>14} {'train':>8} {'offdiag cos':>12}"
      f" {'e2e prec':>9}")
land = {}
for n_land in (512, 2048, 8192, len(p_order)):
    idx = (np.arange(len(p_order)) if n_land >= len(p_order)
           else np.random.default_rng(SEED).choice(len(p_order), n_land,
                                                   replace=False))
    PCl = Zp[idx]                       # unit rows already; NOT orthonormal
    h1, t1, prec, _tal = evaluate(PCl)
    U = np.stack([P.unit(V[p] @ PCl.T) for p in RELS])
    S = U @ U.T
    off = float(S[~np.eye(len(RELS), dtype=bool)].mean())
    land[str(n_land)] = {"held_out_top1": round(h1, 4),
                         "train_top1": round(t1, 4),
                         "mean_offdiag_cos": round(off, 4),
                         "end_to_end_precision": round(prec, 4)}
    print(f"{n_land:28d} {h1:14.3f} {t1:8.3f} {off:12.3f} {prec:9.3f}",
          flush=True)

bl = max(land, key=lambda k: land[k]["held_out_top1"])
lo_l, hi_l = wilson_ci(int(land[bl]["held_out_top1"] * len(he_i)), len(he_i))
print(f"\nbest landmark basis: {bl} landmarks, top-1 "
      f"{land[bl]['held_out_top1']:.3f} CI95 [{lo_l:.3f}, {hi_l:.3f}]  "
      f"vs corpus-fit k-means {D114_BEST:.3f} (capped at 18)")
out["landmark_bases"] = land
(ROOT / "results" / "exp21_overprovision.json").write_text(
    json.dumps(out, indent=1))
print("[done] landmark results appended")
