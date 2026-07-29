"""Answer-type gate + a MIXED unanswerable benchmark (D134).

D133 found the project's worst number and a hole underneath it. Of questions
the store could not answer it properly refused only 0.360, confabulating the
rest; and on the simplest unanswerable question of all — *this relation does
not apply to this entity* — it answers anyway 0.850 of the time. Every
unanswerable population from D118 to D132 was a **chain-break**, so those
refusal numbers describe chain-break refusal specifically (audit law #9).

**The fix is a re-adoption, not an invention.** `avail[subject]` carries
relation identity and nothing else. D110's answer-type gate — the range
profile that knows a relation's answers are dates rather than people — has
been orphaned since the walker replaced the planner.

**The gate, and why it is not circular.** The walk returns objects, and those
objects trivially match the relation the walk *took*. The question is whether
they match the relation the question *asked for*, which is read off the
TARGET rather than the path:

    r_asked = argmax_r  ( (target - sum of coordinates already walked) · RC[r] )

then compare the returned objects against `cent[r_asked]`, the centroid of
that relation's objects in the store. On a not-applicable question the walker
substitutes some other relation, so its answer looks like the relation it
came FROM and not the one asked — measured at 0.965 by probe, which is the
ceiling this gate is chasing.

**The mixed benchmark is the lasting artifact**, and it is what law #9
demands. Three kinds of unanswerable, never averaged:

    chain_break     a multi-hop walk dies partway   (all of D118-D132)
    not_applicable  relation is real, entity is real, the pair is not
    absent_entity   the subject is not in this store at all

Reported with risk-coverage/AURC (D132), not a refusal rate at a threshold.

Usage: .venv/bin/python scripts/exp39_typegate.py
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

SEED, MIN_GAIN, K_BASIS, RES_THR = 0, 0.2, 48, 0.8
CAP = 1200

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
# subjects from the arXiv component: real strings, genuinely absent from the
# wiki store — a true "entity not here", not a fabricated one
foreign = sorted({c["subject"] for c in kb.claims
                  if c["page"].startswith("arxiv:")})
print(f"{len(wiki)} claims / {len(RELS)} relations / {len(subjects)} subjects "
      f"/ {len(OBJS)} objects; {len(foreign)} foreign subjects available")


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


def t1(s, r):
    return f"What is the {LABEL[r]} of {s}?"


def t2(s, r1, r2):
    return f"What is the {LABEL[r2]} of the {LABEL[r1]} of {s}?"


rng = np.random.default_rng(SEED)
POP = {}

# ---- answerable ----
d1 = [{"subject": s, "chain": [r], "answers": sorted(gold[(s, r)]),
       "text": t1(s, r)}
      for s in subjects for r in sorted(avail[s])]
d2 = []
for s in subjects:
    for r1 in sorted(avail[s]):
        m1 = step({s}, r1)
        if not m1:
            continue
        for r2 in sorted(options_at(m1)):
            m2 = step(m1, r2)
            if m2:
                d2.append({"subject": s, "chain": [r1, r2],
                           "answers": sorted(m2)[:300],
                           "text": t2(s, r1, r2)})
# ---- unanswerable, three kinds (law #9) ----
chain_break, not_app, absent = [], [], []
for s in subjects:
    for r1 in sorted(avail[s]):
        m1 = step({s}, r1)
        if not m1:
            continue
        for r2 in RELS:
            if not step(m1, r2):
                chain_break.append({"subject": s, "chain": [r1, r2],
                                    "answers": [], "text": t2(s, r1, r2)})
    for r in RELS:
        if r not in avail[s]:
            not_app.append({"subject": s, "chain": [r], "answers": [],
                            "text": t1(s, r)})
for s in foreign:
    for r in RELS:
        absent.append({"subject": s, "chain": [r], "answers": [],
                       "text": t1(s, r)})


def cap(rows, n=CAP):
    rows = sorted(rows, key=lambda a: (a["subject"], ">".join(a["chain"])))
    if len(rows) > n:
        rows = [rows[i] for i in sorted(rng.choice(len(rows), n,
                                                   replace=False))]
    return rows


for k, v in (("ans_d1", d1), ("ans_d2", d2), ("chain_break", chain_break),
             ("not_applicable", not_app), ("absent_entity", absent)):
    POP[k] = cap(v)
    print(f"  {k:15s} {len(POP[k]):5d}")

ORDER = sorted(POP)
texts, index = [], {}
for k in ORDER:
    index[k] = (len(texts), len(texts) + len(POP[k]))
    texts += [q["text"] for q in POP[k]]
cache = ROOT / "results" / "exp39_emb.npz"
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    assert list(z["texts"]) == texts, "cache misaligned; delete it"
    assert list(z["objs"]) == OBJS, "object list drifted; delete cache"
    Z, Zl, Zo = z["Z"], z["Zl"], z["Zo"]
else:
    Z = P.unit(P.embed_texts(texts))
    Zl = P.unit(P.embed_texts([LABEL[r] for r in RELS]))
    Zo = P.unit(P.embed_texts(OBJS))
    np.savez(cache, Z=Z, Zl=Zl, Zo=Zo, texts=np.array(texts),
             objs=np.array(OBJS))
RC = {r: Zl[i] for i, r in enumerate(RELS)}
OI = {o: i for i, o in enumerate(OBJS)}
print(f"{len(texts)} questions + {len(OBJS)} objects embedded", flush=True)

# ---- the answer-type profile: closed-form from the store, no training ----
CENT = {}
for r in RELS:
    ids = [OI[o] for o in sorted({c["object"] for c in wiki
                                  if c["pid"] == r}) if o in OI]
    if ids:
        CENT[r] = P.unit(Zo[ids].mean(0))
print(f"answer-type centroids for {len(CENT)} relations (closed-form)")


def emb(k):
    a, b = index[k]
    return Z[a:b]


import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

PC = P.unit(fit_anchors(np.stack([RC[r] for r in RELS]), K_BASIS, seed=SEED))
C = {r: P.unit(RC[r] @ PC.T) for r in RELS}
# train on a deterministic half of the answerable questions
tr_ids = {"ans_d1": list(range(0, len(POP["ans_d1"]), 2)),
          "ans_d2": list(range(0, len(POP["ans_d2"]), 2))}
Xs, Ys = [], []
for k, ids in tr_ids.items():
    E = emb(k)
    for j in ids:
        Xs.append(E[j])
        Ys.append(sum(C[r] for r in POP[k][j]["chain"]))
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
print(f"head trained on {len(Xs)} chains (even indices only)", flush=True)


def walk_one(subject, target, max_steps):
    resid, frontier, path = target.copy(), {subject}, []
    for _ in range(max_steps):
        opts = sorted(options_at(frontier))
        if not opts:
            break
        g = sorted(((float(resid @ C[r]), r) for r in opts), reverse=True)
        if g[0][0] <= MIN_GAIN:
            break
        nxt = step(frontier, g[0][1])
        if not nxt:
            break
        frontier, path = nxt, path + [g[0][1]]
        resid = resid - C[g[0][1]]
    return path, frontier, float(np.linalg.norm(resid))


def type_fit(target, path, frontier):
    """How well do the RETURNED objects match the relation the QUESTION
    asked for? r_asked is read off the target, never off the path, or the
    check would be circular."""
    if not frontier:
        return 0.0
    consumed = sum((C[r] for r in path[:-1]),
                   np.zeros(K_BASIS, np.float32)) if len(path) > 1 else \
        np.zeros(K_BASIS, np.float32)
    want = target - consumed
    r_asked = max(RELS, key=lambda r: float(want @ C[r]))
    if r_asked not in CENT:
        return 0.0
    ids = [OI[o] for o in sorted(frontier) if o in OI]
    if not ids:
        return 0.0
    return float(np.mean(Zo[ids] @ CENT[r_asked]))


def score(key, max_steps, answerable, ids=None):
    rows, E = POP[key], emb(key)
    ids = range(len(rows)) if ids is None else ids
    with torch.no_grad():
        tgt = head(torch.tensor(E)).numpy()
    out = []
    for j in ids:
        q = rows[j]
        path, frontier, rn = walk_one(q["subject"], tgt[j], max_steps)
        tf = type_fit(tgt[j], path, frontier)
        ok = bool(answerable and frontier
                  and set(frontier) & set(q["answers"]))
        out.append({"resid": rn, "tfit": tf, "ok": ok,
                    "walkable": bool(path and frontier)})
    return out


EVAL_IDS = {"ans_d1": list(range(1, len(POP["ans_d1"]), 2)),
            "ans_d2": list(range(1, len(POP["ans_d2"]), 2))}
DATA = {
    "ans_d1": score("ans_d1", 2, True, EVAL_IDS["ans_d1"]),
    "ans_d2": score("ans_d2", 3, True, EVAL_IDS["ans_d2"]),
    "chain_break": score("chain_break", 3, False),
    "not_applicable": score("not_applicable", 2, False),
    "absent_entity": score("absent_entity", 2, False),
}
print("scored: " + ", ".join(f"{k}({len(v)})" for k, v in DATA.items()),
      flush=True)

# calibration uses TRAINED-half answerable + a calibration slice of
# not_applicable — a population that exhibits the failure (law #6)
CAL_NA = DATA["not_applicable"][::2]
EV_NA = DATA["not_applicable"][1::2]
CAL = (score("ans_d1", 2, True, tr_ids["ans_d1"]) + CAL_NA)
print(f"calibration {len(CAL)} rows (trained-half answerable + half of "
      f"not_applicable)")

GRID = [0.0, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]


def verdict(r, tthr):
    if not r["walkable"] or r["resid"] > RES_THR or r["tfit"] < tthr:
        return "refuse"
    return "correct" if r["ok"] else "wrong"


print(f"\n{'tfit thr':>9} {'CAL answerable':>15} {'CAL not-appl refused':>21}")
best, bw = 0.0, -1.0
for t in GRID:
    a = [verdict(r, t) for r in CAL[:len(CAL) - len(CAL_NA)]]
    n_ = [verdict(r, t) for r in CAL_NA]
    acc = a.count("correct") / max(len(a), 1)
    ref = n_.count("refuse") / max(len(n_), 1)
    print(f"{t:9.2f} {acc:15.3f} {ref:21.3f}")
    if min(acc, ref) > bw:
        bw, best = min(acc, ref), t
TTHR = best
print(f"selected type-fit threshold {TTHR} (max worst-of-two on calibration)")

print(f"\n=== HELD-OUT: gate OFF (D133 behaviour) vs gate ON ===")
print(f"{'population':16s} | {'OFF: c / w / refuse':>26} | "
      f"{'ON: c / w / refuse':>26}")
res = {}
for key, rows, ans in (("ans_d1", [DATA["ans_d1"]][0], True),
                       ("ans_d2", DATA["ans_d2"], True),
                       ("chain_break", DATA["chain_break"], False),
                       ("not_applicable", EV_NA, False),
                       ("absent_entity", DATA["absent_entity"], False)):
    off = collections.Counter(verdict(r, 0.0) for r in rows)
    on = collections.Counter(verdict(r, TTHR) for r in rows)
    n = max(len(rows), 1)
    res[key] = {"off": {k: round(off[k] / n, 4) for k in
                        ("correct", "wrong", "refuse")},
                "on": {k: round(on[k] / n, 4) for k in
                       ("correct", "wrong", "refuse")}, "n": n}
    f = (f"{off['correct']/n:.3f} / {off['wrong']/n:.3f} / "
         f"{off['refuse']/n:.3f}")
    g = (f"{on['correct']/n:.3f} / {on['wrong']/n:.3f} / "
         f"{on['refuse']/n:.3f}")
    print(f"{key:16s} | {f:>26} | {g:>26}")

na_off = res["not_applicable"]["off"]["refuse"]
na_on = res["not_applicable"]["on"]["refuse"]
lo, hi = wilson_ci(int(na_on * res["not_applicable"]["n"]),
                   res["not_applicable"]["n"])
print(f"\nnot-applicable refusal {na_off:.3f} -> {na_on:.3f}  "
       f"CI95 [{lo:.3f}, {hi:.3f}]   (probe ceiling 0.965)")
cov_off = res["ans_d1"]["off"]["correct"]
cov_on = res["ans_d1"]["on"]["correct"]
print(f"answerable depth-1 coverage {cov_off:.3f} -> {cov_on:.3f}  "
      f"({cov_on - cov_off:+.3f})")


def aurc(rows, conf):
    order = np.argsort(-np.asarray(conf))
    ok = np.asarray([rows[i]["ok"] for i in order], float)
    n = np.arange(1, len(ok) + 1)
    return float(np.mean(np.cumsum(1 - ok) / n))


ALL = (DATA["ans_d1"] + DATA["ans_d2"] + DATA["chain_break"]
       + EV_NA + DATA["absent_entity"])
a_res = aurc(ALL, [-r["resid"] for r in ALL])
a_both = aurc(ALL, [min(-r["resid"] / 2 + r["tfit"], 1.0) for r in ALL])
print(f"\nAURC over the MIXED benchmark (lower = better ranking)")
print(f"  residual only        {a_res:.4f}")
print(f"  residual + type fit  {a_both:.4f}")

out = {
    "manifest": run_manifest(seed=SEED, config={"RES_THR": RES_THR,
                                                "TTHR": TTHR,
                                                "K_BASIS": K_BASIS}),
    "type_fit_threshold": TTHR, "results": res,
    "not_applicable_refusal": {"gate_off": na_off, "gate_on": na_on,
                               "ci95": [round(lo, 4), round(hi, 4)],
                               "probe_ceiling": 0.965},
    "aurc_mixed": {"residual_only": round(a_res, 4),
                   "residual_plus_type": round(a_both, 4)},
    "scope": ("Mixed unanswerable benchmark per audit law #9: chain_break "
              "(all of D118-D132), not_applicable (relation real, entity "
              "real, pair absent) and absent_entity (subject not in this "
              "store; foreign subjects taken from the arXiv component so "
              "they are real strings rather than fabrications). Never "
              "averaged. The type gate reads r_asked off the TARGET, not "
              "the walked path, or it would be circular. Answer-type "
              "centroids are closed-form from the store, untrained."),
}
(ROOT / "results" / "exp39_typegate.json").write_text(json.dumps(out,
                                                                 indent=1))
print("\n[done] results/exp39_typegate.json")
