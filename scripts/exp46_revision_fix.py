"""Does supplying downstream edges fix revision's break rate? (D146)

Task 2, and a test of a causal claim rather than a hunt for a better number.

D141 measured revision at 0.459 with the dominant failure being
**broke→refuse 0.348**, and offered a mechanism: editing one link mid-chain
leaves the rest of the chain expecting the OLD target's outgoing edges. Change
a person's citizenship to Croatia and the chain still needs Croatia's head of
state; if that edge is absent the walk breaks and refuses.

MQuAKE's `new_single_hops` carries the post-edit chain hop by hop, so those
edges are reconstructible: hop *i*'s relation is unchanged from the original
chain, its object is `new_single_hops[i].answer`, and the next hop's subject
is that answer. Verified on a sample: 276 of 400 mid-chain edits need a
downstream edge and all 276 have one.

**Pre-registered prediction**: supplying them makes the break rate fall
sharply and revision rise, with staleness staying near 0.002. **If the break
rate does not fall, D141's diagnosis was wrong and must be withdrawn** — that
is the plan's stop condition, and this experiment is designed to be able to
deliver that verdict.

Both conditions run here on the **same cases, same frozen head, same
questions**, so the comparison is within-experiment. Comparing against D141's
numbers directly would confound the fix with a different sample.

Usage: .venv/bin/python scripts/exp46_revision_fix.py
"""
from __future__ import annotations

import collections
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import v06_pipeline as P                                        # noqa: E402
from codec.evals.anchors import fit_anchors                      # noqa: E402
from codec.manifest import run_manifest, wilson_ci               # noqa: E402
from foundation.kb import KB                                     # noqa: E402

SEED, MIN_GAIN, K_BASIS, RES_THR, TTHR = 0, 0.2, 48, 0.8, 0.30
N_CASES = 1200

props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
cases_all = json.loads(
    (ROOT / "data" / "mquake" / "MQuAKE-CF-3k.json").read_text())
by_depth = collections.defaultdict(list)
for c in cases_all:
    by_depth[len(c["orig"]["triples"])].append(c)
rng = np.random.default_rng(SEED)
cases = []
for d in (2, 3, 4):
    pool = by_depth[d]
    take = min(N_CASES // 3, len(pool))
    cases += [pool[i] for i in sorted(rng.choice(len(pool), take,
                                                 replace=False))]
LABEL, base_rows, seen = {}, [], set()
for c in cases:
    for (s, p, o), (sl, pl, ol) in zip(c["orig"]["triples"],
                                       c["orig"]["triples_labeled"]):
        if p not in props:
            continue
        LABEL[p] = props[p]["label"]
        if (sl, p, ol) in seen:
            continue
        seen.add((sl, p, ol))
        base_rows.append({"page": f"mquake:{sl}", "page_title": sl,
                          "subject": sl, "pid": p, "object": ol,
                          "statement": f"{sl} ({props[p]['label']}): {ol}."})
RELS = sorted(LABEL)
print(f"{len(cases)} cases, {len(base_rows)} base claims, {len(RELS)} relations")


def new_chain_edges(c):
    """Reconstruct the POST-edit chain: relations are unchanged, objects come
    from new_single_hops, and each hop's subject is the previous answer."""
    out, subj = [], c["orig"]["triples_labeled"][0][0]
    hops = c.get("new_single_hops") or []
    for i, (s, p, o) in enumerate(c["orig"]["triples"]):
        if p not in LABEL or i >= len(hops):
            return out
        ans = hops[i].get("answer")
        if not ans:
            return out
        out.append((subj, p, ans))
        subj = ans
    return out


Q = [{"node": c["orig"]["triples_labeled"][0][0],
      "depth": len(c["orig"]["triples"]),
      "chain": [t[1] for t in c["orig"]["triples"]],
      "old": [c["answer"]] + list(c.get("answer_alias", [])),
      "new": [c["new_answer"]] + list(c.get("new_answer_alias", [])),
      "n_rw": len(c["requested_rewrite"]), "text": c["questions"][0]}
     for c in cases]
ENTS = sorted({r["subject"] for r in base_rows}
              | {r["object"] for r in base_rows}
              | {e for c in cases for (_, _, e) in new_chain_edges(c)}
              | {x for q in Q for x in q["new"]})
texts = [q["text"] for q in Q]
cache = ROOT / "results" / "exp46_emb.npz"
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    assert list(z["texts"]) == texts and list(z["ents"]) == ENTS, \
        "cache misaligned; delete it"
    Z, Zl, Ze = z["Z"], z["Zl"], z["Ze"]
else:
    Z = P.unit(P.embed_texts(texts))
    Zl = P.unit(P.embed_texts([LABEL[r] for r in RELS]))
    Ze = P.unit(P.embed_texts(ENTS))
    np.savez(cache, Z=Z, Zl=Zl, Ze=Ze, texts=np.array(texts),
             ents=np.array(ENTS))
K_EFF = min(K_BASIS, len(RELS))
PC = P.unit(fit_anchors(Zl, K_EFF, seed=SEED))
C = {r: P.unit(Zl[i] @ PC.T) for i, r in enumerate(RELS)}
EI = {e: i for i, e in enumerate(ENTS)}
print(f"{len(Q)} questions, {len(ENTS)} entities embedded", flush=True)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

tr = list(range(0, len(Q), 2))
X = torch.tensor(Z[tr])
Y = torch.tensor(np.stack([sum(C[r] for r in Q[i]["chain"]) for i in tr]))
torch.manual_seed(SEED)
head = nn.Sequential(nn.Linear(1024, 512), nn.GELU(),
                     nn.Linear(512, K_EFF))
opt = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-4)
for _ in range(60):
    for b in torch.randperm(len(X)).split(512):
        opt.zero_grad()
        ((head(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
        opt.step()
head.eval()
with torch.no_grad():
    TGT = head(torch.tensor(Z)).numpy()
EV = [i for i in range(len(Q)) if i % 2 == 1]
print(f"head frozen (trained on {len(tr)}); evaluating on {len(EV)}",
      flush=True)


def fresh_kb():
    tmp = Path(tempfile.mkdtemp(prefix="exp46_"))
    (tmp / "out_0.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in base_rows))
    kb = KB(backend="memory")
    kb.ingest_shards(tmp, embed=False)
    return kb


def graph(kb):
    g, av = collections.defaultdict(set), collections.defaultdict(set)
    for c in kb.claims:
        if kb._live(c):
            g[(c["subject"], c["pid"])].add(c["object"])
            av[c["subject"]].add(c["pid"])
    return g, av


def CENT_from(g):
    out = {}
    for r in RELS:
        ids = [EI[o] for k, v in g.items() if k[1] == r for o in sorted(v)
               if o in EI][:400]
        if ids:
            out[r] = P.unit(Ze[ids].mean(0))
    return out


def ask(i, g, av, CENT):
    q = Q[i]
    resid, frontier, path = TGT[i].copy(), {q["node"]}, []
    for _ in range(q["depth"] + 1):
        opts = sorted(set().union(*(av.get(n, set()) for n in frontier))
                      if frontier else set())
        if not opts:
            break
        gs = sorted(((float(resid @ C[r]), r) for r in opts), reverse=True)
        if gs[0][0] <= MIN_GAIN:
            break
        nxt = set()
        for n in frontier:
            nxt |= g.get((n, gs[0][1]), set())
        if not nxt:
            break
        frontier, path = nxt, path + [gs[0][1]]
        resid = resid - C[gs[0][1]]
    rn = float(np.linalg.norm(resid))
    tf = 0.0
    if frontier and CENT:
        r_asked = max(CENT, key=lambda r: float(TGT[i] @ C[r]))
        ids = [EI[o] for o in sorted(frontier) if o in EI]
        if ids:
            tf = float(np.mean(Ze[ids] @ CENT[r_asked]))
    if not path or not frontier or rn > RES_THR or tf < TTHR:
        return "refuse"
    low = {f.lower() for f in frontier}
    if low & {x.lower() for x in q["old"]}:
        return "old"
    if low & {x.lower() for x in q["new"]}:
        return "new"
    return "other"


kb0 = fresh_kb()
G0, A0 = graph(kb0)
CENT0 = CENT_from(G0)
BEFORE = {i: ask(i, G0, A0, CENT0) for i in EV}
print(f"before: " + ", ".join(f"{k} {v/len(EV):.3f}" for k, v in
                              sorted(collections.Counter(BEFORE.values()
                                                         ).items())))


def apply_edits(kb, with_downstream):
    stats = collections.Counter()
    extra = []
    for c in cases:
        for rw in c["requested_rewrite"]:
            if rw["relation_id"] in LABEL:
                stats[kb.edit(rw["subject"], rw["relation_id"],
                              rw["target_new"]["str"],
                              source="mquake:cf").get("status", "ok")] += 1
        if not with_downstream:
            continue
        for (s_, p_, o_) in new_chain_edges(c)[1:]:      # skip the rewrite
            r = kb.edit(s_, p_, o_, source="mquake:downstream")
            if r.get("status") in ("abstain", "ambiguous"):
                extra.append({"page": f"mquake:{s_}", "page_title": s_,
                              "subject": s_, "pid": p_, "object": o_,
                              "statement":
                                  f"{s_} ({LABEL[p_]}): {o_}."})
            else:
                stats["downstream_edited"] += 1
    if extra:
        tmp = Path(tempfile.mkdtemp(prefix="exp46_ds_"))
        uniq, s2 = set(), []
        for r in extra:
            k = (r["subject"], r["pid"], r["object"])
            if k not in uniq:
                uniq.add(k)
                s2.append(r)
        (tmp / "out_0.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in s2))
        kb.ingest_shards(tmp, embed=False)
        stats["downstream_ingested"] = len(s2)
    return stats


RES = {}
for cond in ("rewrite only (D141)", "rewrite + downstream edges"):
    kb = fresh_kb()
    st = apply_edits(kb, with_downstream=cond.startswith("rewrite +"))
    g, av = graph(kb)
    CENT = CENT_from(g)
    after = {i: ask(i, g, av, CENT) for i in EV}
    was_old = [i for i in EV if BEFORE[i] == "old"]
    m = collections.Counter((BEFORE[i], after[i]) for i in EV)
    took = sum(1 for i in was_old if after[i] == "new")
    stale = sum(1 for i in was_old if after[i] == "old")
    broke = sum(1 for i in was_old if after[i] == "refuse")
    oth = sum(1 for i in was_old if after[i] == "other")
    n = max(len(was_old), 1)
    RES[cond] = {"edits": dict(st), "n_was_old": len(was_old),
                 "revision": took / n, "stale": stale / n,
                 "broke": broke / n, "other": oth / n,
                 "graph_pairs": len(g),
                 "matrix": {f"{a}->{b}": v for (a, b), v in m.items()}}
    lo, hi = wilson_ci(took, n)
    print(f"\n{cond}")
    print(f"  edits: {dict(st)}")
    print(f"  live graph {len(g)} pairs")
    print(f"  revision {took/n:.3f} CI95 [{lo:.3f}, {hi:.3f}]   "
          f"stale {stale/n:.3f}   broke {broke/n:.3f}   other {oth/n:.3f}"
          f"   (n={n})")
    for d in (2, 3, 4):
        ids = [i for i in was_old if Q[i]["depth"] == d]
        if ids:
            print(f"    depth {d}: revision "
                  f"{sum(1 for i in ids if after[i]=='new')/len(ids):.3f} "
                  f"broke {sum(1 for i in ids if after[i]=='refuse')/len(ids):.3f}"
                  f" (n={len(ids)})")

a, b = RES["rewrite only (D141)"], RES["rewrite + downstream edges"]
print(f"\n=== PRE-REGISTERED PREDICTION ===")
print(f"  break rate {a['broke']:.3f} -> {b['broke']:.3f}  "
      f"({b['broke']-a['broke']:+.3f})")
print(f"  revision   {a['revision']:.3f} -> {b['revision']:.3f}  "
      f"({b['revision']-a['revision']:+.3f})")
print(f"  staleness  {a['stale']:.3f} -> {b['stale']:.3f}")
verdict = ("CONFIRMED — D141's diagnosis holds"
           if b["broke"] < a["broke"] - 0.05
           else "NOT CONFIRMED — D141's diagnosis must be withdrawn")
print(f"  {verdict}")

out = {
    "manifest": run_manifest(seed=SEED, config={"N_CASES": len(cases),
                                                "RES_THR": RES_THR,
                                                "TTHR": TTHR}),
    "conditions": RES, "verdict": verdict,
    "scope": ("Both conditions share the same cases, the same frozen head "
              "and the same questions, so the comparison is "
              "within-experiment; D141's numbers came from a different "
              "sample and are not the baseline here. Downstream edges are "
              "reconstructed from new_single_hops — relations unchanged, "
              "objects from each hop's answer, each hop's subject the "
              "previous answer — and applied via kb.edit() where the "
              "subject is known, or ingested where it is not."),
}
(ROOT / "results" / "exp46_revision_fix.json").write_text(
    json.dumps(out, indent=1))
print("\n[done] results/exp46_revision_fix.json")
