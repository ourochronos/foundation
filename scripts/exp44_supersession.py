"""Supersession: can the store CHANGE its mind? (D141)

Task 2, and the harder half of the learning claim. D133 tested **addition** —
withheld facts appended, refused→correct at 1.000. It never tested
**supersession**: revising a fact that is already there, where the old answer
must stop winning. That is a different property and exercises different code.

MQuAKE-CF-3k is built for exactly this. Each case carries `requested_rewrite`
(`target_true` → `target_new`) over its original chain, the resulting
`new_answer`, and **human-written questions** — so this measures belief
revision on natural language rather than on templates.

**The edit goes through the real path.** `foundation/kb.py`'s `edit()`
supersedes: it appends a new claim row and shadows every live same-(eid, pid)
row, per D55's address/content separation. A simulated dict overwrite would
test nothing about that. The KB runs on the memory backend, so no embedding
is computed for stored claims — the walker reads the graph from LIVE claims
and brings its own question embeddings.

Everything is frozen before the first edit: basis, coordinates, head. No
refit, per D131.

The transition matrix is the deliverable and three of its four cells are
failures:

    old -> new      the property: the revision was absorbed
    old -> old      STALE: the edit did not take
    old -> other    absorbed something, but the wrong thing
    correct -> refuse   the edit broke retrieval

Single-rewrite and multi-rewrite cases are reported separately: 1,907 of
3,000 carry two or more rewrites and those are a different difficulty.

Usage: .venv/bin/python scripts/exp44_supersession.py
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
print(f"{len(cases)} cases ({N_CASES // 3} per depth)")

# ---- build shards and ingest through the real KB ----
LABEL, rows, seen = {}, [], set()
for c in cases:
    for (s, p, o), (sl, pl, ol) in zip(c["orig"]["triples"],
                                       c["orig"]["triples_labeled"]):
        if p not in props:
            continue
        LABEL[p] = props[p]["label"]
        k = (sl, p, ol)
        if k in seen:
            continue
        seen.add(k)
        rows.append({"page": f"mquake:{sl}", "page_title": sl, "subject": sl,
                     "pid": p, "object": ol,
                     "statement": f"{sl} ({props[p]['label']}): {ol}."})
tmp = Path(tempfile.mkdtemp(prefix="exp44_"))
(tmp / "out_0.jsonl").write_text(
    "".join(json.dumps(r) + "\n" for r in rows))
kb = KB(backend="memory")
info = kb.ingest_shards(tmp, embed=False)
print(f"ingested {len(rows)} claims into a memory KB -> {info}")
RELS = sorted(LABEL)


def graph():
    """Read the graph from LIVE claims only — shadowed rows must vanish."""
    g, av = collections.defaultdict(set), collections.defaultdict(set)
    for c in kb.claims:
        if not kb._live(c):
            continue
        g[(c["subject"], c["pid"])].add(c["object"])
        av[c["subject"]].add(c["pid"])
    return g, av


G0, A0 = graph()
print(f"live graph before edits: {len(G0)} subject-relation pairs")

# ---- questions (human-written), answers before and after ----
Q = []
for c in cases:
    subj = c["orig"]["triples_labeled"][0][0]
    n_rw = len(c["requested_rewrite"])
    Q.append({"node": subj, "depth": len(c["orig"]["triples"]),
              "chain": [t[1] for t in c["orig"]["triples"]],
              "old": [c["answer"]] + list(c.get("answer_alias", [])),
              "new": [c["new_answer"]] + list(c.get("new_answer_alias", [])),
              "n_rw": n_rw, "text": c["questions"][0]})
ENTS = sorted({e for k in G0 for e in ({k[0]} | G0[k])}
              | {x for q in Q for x in q["new"]})
texts = [q["text"] for q in Q]
cache = ROOT / "results" / "exp44_emb.npz"
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
# MQuAKE carries 36 relations, so the basis cannot be wider
K_EFF = min(K_BASIS, len(RELS))
PC = P.unit(fit_anchors(Zl, K_EFF, seed=SEED))
C = {r: P.unit(Zl[i] @ PC.T) for i, r in enumerate(RELS)}
EI = {e: i for i, e in enumerate(ENTS)}
CENT = {}
for r in RELS:
    ids = [EI[o] for k, v in G0.items() if k[1] == r for o in sorted(v)
           if o in EI][:400]
    if ids:
        CENT[r] = P.unit(Ze[ids].mean(0))
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
print(f"head frozen (trained on {len(tr)} even-index questions)", flush=True)


def ask(i, g, av):
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
    if frontier:
        r_asked = max(CENT, key=lambda r: float(TGT[i] @ C[r]))
        ids = [EI[o] for o in sorted(frontier) if o in EI]
        if ids:
            tf = float(np.mean(Ze[ids] @ CENT[r_asked]))
    if not path or not frontier or rn > RES_THR or tf < TTHR:
        return "refuse", frontier
    low = {f.lower() for f in frontier}
    if low & {x.lower() for x in Q[i]["old"]}:
        return "old", frontier
    if low & {x.lower() for x in Q[i]["new"]}:
        return "new", frontier
    return "other", frontier


EV = [i for i in range(len(Q)) if i % 2 == 1]
BEFORE = {i: ask(i, G0, A0)[0] for i in EV}
print(f"\nbefore edits: " + ", ".join(
    f"{k} {v/len(EV):.3f}" for k, v in
    sorted(collections.Counter(BEFORE.values()).items())))

# ---- apply the rewrites through the REAL edit path ----
applied = collections.Counter()
for c in cases:
    for rw in c["requested_rewrite"]:
        subj, p, new = rw["subject"], rw["relation_id"], rw["target_new"]["str"]
        if p not in LABEL:
            applied["skip_unlabelled"] += 1
            continue
        r = kb.edit(subj, p, new, source="mquake:counterfactual")
        applied[r.get("status", "ok")] += 1
print(f"edits applied via kb.edit(): {dict(applied)}")
G1, A1 = graph()
print(f"live graph after edits: {len(G1)} pairs "
      f"({len(G1) - len(G0):+d})")
# sanity: did supersession actually take in the graph?
chk = tot = 0
for c in cases[:200]:
    for rw in c["requested_rewrite"]:
        if rw["relation_id"] not in LABEL:
            continue
        tot += 1
        live = G1.get((rw["subject"], rw["relation_id"]), set())
        chk += (rw["target_new"]["str"] in live
                and rw["target_true"]["str"] not in live)
print(f"supersession sanity: {chk}/{tot} edited pairs now hold ONLY the new "
      f"object")

AFTER = {i: ask(i, G1, A1)[0] for i in EV}
print(f"after edits:  " + ", ".join(
    f"{k} {v/len(EV):.3f}" for k, v in
    sorted(collections.Counter(AFTER.values()).items())))


def matrix(ids, label):
    m = collections.Counter((BEFORE[i], AFTER[i]) for i in ids)
    n = max(len(ids), 1)
    was_old = [i for i in ids if BEFORE[i] == "old"]
    took = sum(1 for i in was_old if AFTER[i] == "new")
    print(f"\n{label} (n={n}; {len(was_old)} answered correctly before)")
    for a in ("old", "new", "other", "refuse"):
        row = [f"{b}:{m[(a, b)]}" for b in ("old", "new", "other", "refuse")
               if m[(a, b)]]
        if row:
            print(f"  from {a:7s} -> " + "  ".join(row))
    if was_old:
        lo, hi = wilson_ci(took, len(was_old))
        print(f"  REVISION RATE (old->new | was old): {took}/{len(was_old)} "
              f"= {took/len(was_old):.3f}  CI95 [{lo:.3f}, {hi:.3f}]")
        stale = sum(1 for i in was_old if AFTER[i] == "old")
        print(f"  stale (old->old): {stale/len(was_old):.3f}   "
              f"broke (old->refuse): "
              f"{sum(1 for i in was_old if AFTER[i]=='refuse')/len(was_old):.3f}")
    return {f"{a}->{b}": v for (a, b), v in m.items()}, (
        took / len(was_old) if was_old else None)


all_m, all_rate = matrix(EV, "ALL cases")
single = [i for i in EV if Q[i]["n_rw"] == 1]
multi = [i for i in EV if Q[i]["n_rw"] > 1]
s_m, s_rate = matrix(single, "SINGLE-rewrite cases")
m_m, m_rate = matrix(multi, "MULTI-rewrite cases")
print(f"\nby depth (revision rate | was old):")
for d in (2, 3, 4):
    ids = [i for i in EV if Q[i]["depth"] == d and BEFORE[i] == "old"]
    if ids:
        print(f"  depth {d}: "
              f"{sum(1 for i in ids if AFTER[i]=='new')/len(ids):.3f} "
              f"(n={len(ids)})")

out = {
    "manifest": run_manifest(seed=SEED, config={"N_CASES": len(cases),
                                                "RES_THR": RES_THR,
                                                "TTHR": TTHR}),
    "edits_applied": dict(applied),
    "supersession_sanity": {"checked": tot, "clean": chk},
    "before": dict(collections.Counter(BEFORE.values())),
    "after": dict(collections.Counter(AFTER.values())),
    "matrix_all": all_m, "revision_rate_all": all_rate,
    "matrix_single": s_m, "revision_rate_single": s_rate,
    "matrix_multi": m_m, "revision_rate_multi": m_rate,
    "scope": ("Supersession, not addition: MQuAKE counterfactual rewrites "
              "applied through foundation/kb.py's real edit() path, which "
              "shadows every live same-(eid,pid) row per D55. The graph is "
              "read from LIVE claims only. Questions are MQuAKE's "
              "human-written phrasings; the head is frozen before the first "
              "edit and never refits. The revision rate is conditional on "
              "the store having answered correctly BEFORE the edit — a "
              "question it could not answer beforehand cannot demonstrate "
              "revision."),
}
(ROOT / "results" / "exp44_supersession.json").write_text(json.dumps(out,
                                                                     indent=1))
print("\n[done] results/exp44_supersession.json")
