"""Can we plan a relation that did not exist at training time? (D113)

D112 concluded that R² enumeration is the honest ceiling, because relation
identity is a COORDINATE in this system, not content: participation vectors
are `2R`, the detection head is `1024 -> R`. A novel relation is a new AXIS,
which retrains every head and redefines every stored participation vector.
That is a reindex, and it is the same mistake anchors were invented to avoid
— anchors work because content is coordinates in a FIXED basis (A2, transfer
gap 0.000).

This tests the fix directly: give a relation a content vector, project it
onto a frozen basis, and predict a POINT in relation space instead of a
class over known relations. A softmax cannot score a relation that did not
exist at training time; a predicted point can.

**The design guards against the obvious cheat.** A relation's content vector
is the embedding of its LABEL only ("spouse"). Every question is generated
from its ALIASES only ("married to", "wife", "husband"). The label never
appears in a question, so matching cannot be lexical — the query has to land
near the right concept without ever having seen its name.

Three scorers, all trained ONLY on train relations:
  S  softmax over train relations   — the status quo. Scores 0 on held-out
                                      relations BY CONSTRUCTION; it cannot
                                      emit a class it has no output unit
                                      for. Stated, not run as a fake number.
  E  predicted point, RAW embedding — ablation. If E works and A does not,
                                      the anchor basis is destroying
                                      information. If E and A tie, the basis
                                      is free compression and the encoder is
                                      doing the semantic work — which is the
                                      honest credit assignment.
  A  predicted point, FROZEN ANCHOR — the proposal. Fixed K_R dimensions,
     coordinates                      independent of R.

Relation content is B1b-safe: a label arrives WITH the relation at mint
time, so no corpus-wide statistic is ever refit into a persistent path.

Usage: .venv/bin/python scripts/exp19_relanchor.py
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

MIN_N, PER_REL, K_R, N_HELD = 50, 150, 8, 8
SEED = 0

sch = {d["pid"]: d for d in
       json.loads((ROOT / "data" / "schema_v0.json").read_text())}
kb = KB(backend="pg", table="poc")
wiki = [c for c in kb.claims
        if not c["page"].startswith(("arxiv:", "hf:", "user"))]
cnt = collections.Counter(c["pid"] for c in wiki)
RELS = sorted(p for p, n in cnt.items()
              if n >= MIN_N and p in sch and len(sch[p].get("aliases", ())) >= 2)
rng = np.random.default_rng(SEED)
perm = list(RELS)
rng.shuffle(perm)
HELD_R, TRAIN_R = sorted(perm[:N_HELD]), sorted(perm[N_HELD:])
print(f"{len(RELS)} relations: {len(TRAIN_R)} train, {len(HELD_R)} HELD OUT")
print("  held out: " + ", ".join(f"{p}({sch[p]['label']})" for p in HELD_R))

# Facts, subsampled per relation so one big relation cannot set the headline.
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
print(f"{len(facts)} facts")

# Questions from ALIASES ONLY. Two neutral frames, so the alias carries all
# of the relation signal and the frame carries none.
FRAMES = ["What is the {a} of {s}?", "For {s}, what is the {a}?"]
queries = []
for f in facts:
    for a in sch[f["pid"]]["aliases"]:
        for fr in FRAMES:
            queries.append({"pid": f["pid"], "subject": f["subject"],
                            "object": f["object"],
                            "text": fr.format(a=a, s=f["subject"])})
print(f"{len(queries)} questions (aliases x {len(FRAMES)} frames)")

cache = ROOT / "results" / "exp19_emb.npz"
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    Zq, Zl, lab_order = z["Zq"], z["Zl"], list(z["lab_order"])
else:
    Zq = P.unit(P.embed_texts([q["text"] for q in queries]))
    lab_order = list(RELS)
    Zl = P.unit(P.embed_texts([sch[p]["label"] for p in lab_order]))
    np.savez(cache, Zq=Zq, Zl=Zl, lab_order=np.array(lab_order))
V = {p: Zl[i] for i, p in enumerate(lab_order)}      # relation content vecs
print(f"embeddings {Zq.shape} queries / {Zl.shape} relation labels",
      flush=True)

# Frozen anchor basis fit on TRAIN relation vectors only. A held-out
# relation receives coordinates by projection — it never moves the basis,
# which is exactly the append-only property (B1/B1b).
PC = P.unit(fit_anchors(np.stack([V[r] for r in TRAIN_R]), K_R, seed=SEED))
C = {p: P.unit(V[p] @ PC.T) for p in RELS}
print(f"anchor basis {PC.shape} fit on train relations only")

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

tr_i = [i for i, q in enumerate(queries) if q["pid"] in TRAIN_R]
he_i = [i for i, q in enumerate(queries) if q["pid"] in HELD_R]
torch.manual_seed(SEED)


def fit_point_head(target, dim):
    """Regress the query embedding onto a relation's content coordinates."""
    X = torch.tensor(Zq[tr_i])
    Y = torch.tensor(np.stack([target[queries[i]["pid"]] for i in tr_i]))
    hd = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, dim))
    opt = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(X)).split(512):
            opt.zero_grad()
            pr = hd(X[b])
            pr = pr / (pr.norm(dim=-1, keepdim=True) + 1e-9)
            (1 - (pr * Y[b]).sum(-1)).mean().backward()
            opt.step()
    hd.eval()
    return hd


head_E = fit_point_head(V, 1024)
head_A = fit_point_head(C, K_R)


def rank_eval(hd, target, idxs, label):
    """Top-1 and MRR over ALL relations — held-out ones must compete with
    the trained ones, not just with each other."""
    with torch.no_grad():
        pr = hd(torch.tensor(Zq[idxs])).numpy()
    pr = pr / (np.linalg.norm(pr, axis=1, keepdims=True) + 1e-9)
    M = np.stack([target[r] for r in RELS])
    S = pr @ M.T
    ri = {r: i for i, r in enumerate(RELS)}
    top1 = mrr = 0
    for j, i in enumerate(idxs):
        g = ri[queries[i]["pid"]]
        order = np.argsort(-S[j])
        rank = int(np.where(order == g)[0][0]) + 1
        top1 += rank == 1
        mrr += 1.0 / rank
    return top1 / len(idxs), mrr / len(idxs)


print(f"\nrelation identification, scored against ALL {len(RELS)} relations")
print(f"{'scorer':38s} {'HELD-OUT rel':>13} {'MRR':>7} {'train rel':>11}")
print(f"{'S softmax over train relations':38s} {0.0:13.3f} {0.0:7.3f} "
      f"{'(n/a)':>11}   <- 0 by construction")
res = {}
for name, hd, tgt in (("E predicted point, raw embedding", head_E, V),
                      ("A predicted point, anchor coords", head_A, C)):
    h1, hm = rank_eval(hd, tgt, he_i, name)
    t1, _ = rank_eval(hd, tgt, tr_i, name)
    res[name] = {"held_out_top1": round(h1, 4), "held_out_mrr": round(hm, 4),
                 "train_top1": round(t1, 4), "held_out_n": len(he_i)}
    print(f"{name:38s} {h1:13.3f} {hm:7.3f} {t1:11.3f}")
chance = 1.0 / len(RELS)
print(f"chance top-1 = {chance:.3f}  (n={len(he_i)} held-out-relation "
      f"questions over {len(HELD_R)} unseen relations)")

# End-to-end: plan the relation, then walk the live store. Same honest
# triple. A relation that was never trained still has to produce the right
# object or refuse.
gold = collections.defaultdict(set)
for c in wiki:
    gold[(c["subject"], c["pid"])].add(c["object"])


def end_to_end(hd, target, idxs):
    with torch.no_grad():
        pr = hd(torch.tensor(Zq[idxs])).numpy()
    pr = pr / (np.linalg.norm(pr, axis=1, keepdims=True) + 1e-9)
    M = np.stack([target[r] for r in RELS])
    S = pr @ M.T
    t = collections.Counter()
    for j, i in enumerate(idxs):
        q = queries[i]
        r = RELS[int(np.argmax(S[j]))]
        got = gold.get((q["subject"], r), set())
        t["abstain" if not got else
          ("correct" if q["object"] in got else "wrong")] += 1
    return t


print("\nend-to-end on the live store, HELD-OUT relations only")
for name, hd, tgt in (("E predicted point, raw embedding", head_E, V),
                      ("A predicted point, anchor coords", head_A, C)):
    t = end_to_end(hd, tgt, he_i)
    n = sum(t.values())
    a = t["correct"] + t["wrong"]
    print(f"  {name:34s} correct {t['correct']/n:.3f}  wrong {t['wrong']/n:.3f}"
          f"  abstain {t['abstain']/n:.3f}  precision "
          f"{(t['correct']/a if a else 0):.3f}")
    res[name]["end_to_end"] = dict(t)
    res[name]["end_to_end_precision"] = round(t["correct"] / a, 4) if a else 0.0

# Where do the errors go? The random relation split happened to put SIX of
# the eight held-out relations in one semantic family (place of birth,
# place of death, residence, work location, located-in, headquarters). If
# the errors land mostly on other HELD-OUT relations, the anchor space is
# placing a novel relation in the right neighbourhood and failing to
# separate within it — a very different (and more encouraging) failure than
# scattering it across the trained vocabulary. Stated because the split was
# not stratified, which is a limitation of this run, not a design choice.
Mh = np.stack([C[r] for r in RELS])
with torch.no_grad():
    prh = head_A(torch.tensor(Zq[he_i])).numpy()
prh = prh / (np.linalg.norm(prh, axis=1, keepdims=True) + 1e-9)
Sh = prh @ Mh.T
heldset = set(HELD_R)
top3 = 0
conf = collections.Counter()
for j, i in enumerate(he_i):
    g = queries[i]["pid"]
    order = [RELS[k] for k in np.argsort(-Sh[j])]
    top3 += g in order[:3]
    if order[0] != g:
        conf[(g, order[0])] += 1
into_held = sum(n for (g, pd), n in conf.items() if pd in heldset)
frac_held = into_held / max(sum(conf.values()), 1)
print(f"\nheld-out top-3 {top3/len(he_i):.3f} (chance {3/len(RELS):.3f})")
print(f"errors landing on ANOTHER HELD-OUT relation: {frac_held:.3f}  "
      f"(uniform-chance {(len(HELD_R)-1)/(len(RELS)-1):.3f})")
print("top confusions (true -> predicted)")
for (g, pd), n in conf.most_common(6):
    print(f"  {sch[g]['label'][:34]:36s} -> {sch[pd]['label'][:30]:32s} "
          f"{n:5d} {'[held]' if pd in heldset else ''}")

lo, hi = wilson_ci(int(res["A predicted point, anchor coords"]
                       ["held_out_top1"] * len(he_i)), len(he_i))
out = {
    "manifest": run_manifest(seed=SEED, config={
        "min_n": MIN_N, "per_rel": PER_REL, "K_R": K_R,
        "held_out_relations": HELD_R, "train_relations": TRAIN_R}),
    "n_relations": len(RELS), "n_facts": len(facts),
    "n_questions": len(queries), "chance_top1": round(chance, 4),
    "results": res,
    "held_out_top3": round(top3 / len(he_i), 4),
    "errors_into_held_out_family": round(frac_held, 4),
    "uniform_chance_into_held": round((len(HELD_R) - 1) / (len(RELS) - 1), 4),
    "anchor_top1_ci95": [round(lo, 4), round(hi, 4)],
    "scope": ("Relation content vectors are the embedding of the LABEL; "
              "questions are generated from ALIASES only, so the label "
              "never appears in a question and matching cannot be lexical. "
              "The anchor basis is fit on train relations only; held-out "
              "relations receive coordinates by projection and never move "
              "the basis. Single-hop only."),
}
(ROOT / "results" / "exp19_relanchor.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp19_relanchor.json")
