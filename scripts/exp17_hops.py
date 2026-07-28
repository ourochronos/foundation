"""Multi-hop over the REAL store — the capability D110 left untested.

D110 measured single-hop planning on real claims and found the mechanism
transfers. `world["hops"]` was empty there, so composing two relations over
real data was never asked. This adds it.

The held-out axis is deliberately DIFFERENT from D110's. There, phrasings
were held out and compositions did not exist. Here, whole COMPOSITIONS are
held out: `P_INTRODUCES -> P_EVALUATES_ON` and `P_CITES -> P_INTRODUCES`
never appear in training, though both of their constituent relations are
trained heavily as singles. That asks the question worth asking — can the
planner chain two relations it has never seen chained? — rather than
whether it memorised a chain.

`P_CITES -> P_CITES` is subsampled. Unsubsampled it is 5,721 of the 7,345
real 2-hop instances and would let one composition set the headline.

Grading is the same honest triple as D110: correct / wrong / abstain, with
the answer-type gate promoted to refuser. A wrong multi-hop answer is worse
than a wrong single-hop one — it is a real fact about the wrong entity, two
steps from anything the question mentioned.

Usage: .venv/bin/python scripts/exp17_hops.py
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
from codec.manifest import run_manifest, wilson_ci               # noqa: E402

# How to name the objects of a relation, and how to ask a relation about a
# noun phrase. A hop's text is q[r2] wrapped around np[r1].
NP = {
    "P_CITES": ["the works {s} cites", "the papers referenced by {s}"],
    "P_INTRODUCES": ["the method introduced by {s}",
                     "what {s} proposes"],
    "P_BUILDS_ON": ["what {s} builds on", "the model {s} is based on"],
    "P_COMPARES_TO": ["the baselines {s} compares against",
                      "the systems {s} is measured against"],
    "P_EVALUATES_ON": ["the benchmarks {s} evaluates on",
                       "the datasets {s} is tested on"],
}
Q = {
    "P_CITES": ["What do {np} cite?", "What prior work do {np} draw on?"],
    "P_INTRODUCES": ["What do {np} introduce?",
                     "What method do {np} propose?"],
    "P_BUILDS_ON": ["What do {np} build on?", "What are {np} based on?"],
    "P_COMPARES_TO": ["What do {np} compare against?",
                      "Which baselines do {np} use?"],
    "P_EVALUATES_ON": ["What do {np} evaluate on?",
                       "Which datasets are {np} tested on?"],
}
# Never trained on. Both constituents are trained heavily as singles.
HOLDOUT = ["P_INTRODUCES>P_EVALUATES_ON", "P_CITES>P_INTRODUCES"]
MIN_N, CITES_CAP = 36, 800

world = json.loads((ROOT / "data" / "real_world_ai.json").read_text())
facts = world["facts"]
by_subj = collections.defaultdict(list)
for i, f in enumerate(facts):
    by_subj[f["subject"]].append(i)

inst = collections.defaultdict(list)
for f in facts:
    for j in by_subj.get(f["object"], ()):
        g = facts[j]
        if g["object"] == f["subject"]:           # a -> b -> a says nothing
            continue
        inst[f"{f['relation']}>{g['relation']}"].append((f["subject"], j))

rng = np.random.default_rng(0)
hops = []
for kind, items in sorted(inst.items()):
    if len(items) < MIN_N:
        continue
    if kind == "P_CITES>P_CITES" and len(items) > CITES_CAP:
        items = [items[k] for k in rng.choice(len(items), CITES_CAP,
                                              replace=False)]
    r1, r2 = kind.split(">")
    for subj, jf in items:
        for a in range(len(NP[r1])):
            for b in range(len(Q[r2])):
                hops.append({
                    "kind": kind, "chain": [r1, r2], "answer_fact": jf,
                    "subject": subj, "phrasing_idx": a * len(Q[r2]) + b,
                    "text": Q[r2][b].format(np=NP[r1][a].format(s=subj)),
                })
world["hops"] = hops
world["holdout_compositions"] = HOLDOUT
kept = sorted(collections.Counter(h["kind"] for h in hops).items())
print(f"{len(hops)} hop questions over {len(kept)} compositions")
for k, n in kept:
    print(f"  {'HELD ' if k in HOLDOUT else '     '}{k:38s} {n:6d}")
dropped = {k: len(v) for k, v in inst.items() if len(v) < MIN_N}
print(f"dropped (n < {MIN_N}): {dropped}")

out_world = ROOT / "data" / "real_world_ai_hops.json"
out_world.write_text(json.dumps(world))

d = np.load(ROOT / "results" / "real_world_ai_emb.npz")
Zf, Zq = d["Zf"], d["Zq"]
hcache = ROOT / "results" / "real_world_ai_hop_emb.npz"
if hcache.exists():
    Zh = np.load(hcache)["Zh"]
else:
    Zh = P.unit(P.embed_texts([h["text"] for h in hops]))
    np.savez(hcache, Zh=Zh)
print(f"hop embeddings {Zh.shape}", flush=True)

art = P.build_artifacts(world, Zf, Zq)
RELS = art["RELS"]
det, ans, hop_eval_ids = P.train_heads_with(art, world, Zq, Zh, seed=0,
                                            epochs=60)
import torch                                                     # noqa: E402

from foundation.kb import KB                                     # noqa: E402

kb = KB(backend="pg", table="poc")
gold = collections.defaultdict(set)
for c in kb.claims:
    if c["pid"] in RELS and c["page"].startswith("arxiv:"):
        gold[(c["subject"], c["pid"])].add(c["object"])
REPEATED = [0]


def walk(subject, path):
    cur = {subject}
    for r in path:
        nxt = set()
        for x in cur:
            nxt |= gold.get((x, r), set())
        if not nxt:
            return set()
        cur = nxt
    return cur


# ---------------------------------------------------------------------------
# Arity head (D111): predict the path LENGTH, so a repeated relation becomes
# expressible. Trained on exactly the same split as the other two heads —
# singles (seen phrasings) as length 1, hops as length 2, with held-out
# COMPOSITIONS and the reserved hop instances excluded, so nothing the
# evaluation touches is in its training set.
# ---------------------------------------------------------------------------
from torch import nn                                             # noqa: E402

torch.manual_seed(0)
HELD_PH = set(world["held_out_phrasings"])
Xk, Yk = [], []
for i, q in enumerate(world["queries"]):
    if q["kind"] == "single" and q["phrasing_idx"] not in HELD_PH:
        Xk.append(Zq[i]); Yk.append(0)
for i, h in enumerate(hops):
    if h["kind"] not in HOLDOUT and i not in hop_eval_ids:
        Xk.append(Zh[i]); Yk.append(1)
Xk_t = torch.tensor(np.stack(Xk)); Yk_t = torch.tensor(Yk)
arity = nn.Sequential(nn.Linear(1024, 128), nn.GELU(), nn.Linear(128, 2))
optk = torch.optim.AdamW(arity.parameters(), lr=1e-3)
cek = nn.CrossEntropyLoss()
for _ in range(40):
    for b in torch.randperm(len(Xk_t)).split(512):
        optk.zero_grad(); cek(arity(Xk_t[b]), Yk_t[b]).backward(); optk.step()
with torch.no_grad():
    ah = int((arity(torch.tensor(Zh[[i for i, h in enumerate(hops)
                                    if h["kind"] in HOLDOUT]])).argmax(-1)
              == 1).float().mean() * 1000) / 1000
print(f"arity head: {len(Xk)} training rows; held-out-composition hops "
      f"called 2-hop {ah:.3f} of the time")

# ---------------------------------------------------------------------------
# Empirical linkability gate (D111).
#
# The default gate scores a link as cosd(range[a], domain[b]) over 2R-dim
# participation centroids. On a real corpus that is dominated by entities
# with object-side participation ONLY — out-of-corpus cited works exist as
# stubs because the corpus stops there — so cosd(rng[P_CITES],
# dom[P_CITES]) = 0.092 and every chain through a citation is refused. The
# gate is measuring where the corpus ENDS, not whether two relations
# compose. In a synthetic world every entity is in-corpus and the two
# coincide, which is why this never surfaced before.
#
# The replacement asks the question the gate is for, directly and in closed
# form: of the things that appear as objects of `a`, what fraction appear
# as subjects of `b`? That is exactly "can I actually walk a then b", and
# it needs no centroid. Same for the entry gate on the subject itself.
# ---------------------------------------------------------------------------
obj_of = collections.defaultdict(set)
subj_of = collections.defaultdict(set)
for f in facts:
    obj_of[f["relation"]].add(f["object"])
    subj_of[f["relation"]].add(f["subject"])
LINK = {(a, b): (len(obj_of[a] & subj_of[b]) / max(len(obj_of[a]), 1))
        for a in RELS for b in RELS}
LINK_THR = 0.05
print("\nempirical linkability |obj(a) & subj(b)| / |obj(a)|  "
      f"(gate at {LINK_THR})")
print(f"{'':16s}" + "".join(f"{b[2:10]:>10s}" for b in RELS))
for a in RELS:
    print(f"{a[2:14]:16s}" + "".join(f"{LINK[(a, b)]:10.3f}" for b in RELS))

plan = P.make_planner(det, ans, art, arity_head=arity,
                      cand_from_arity=True,
                      path_ok=lambda s, pm: bool(walk(s, list(pm))))
rng_cprof = art["rng_cprof"]


def walk(subject, path):
    cur = {subject}
    for r in path:
        nxt = set()
        for s in cur:
            nxt |= gold.get((s, r), set())
        if not nxt:
            return set()
        cur = nxt
    return cur


# Two evaluation populations, never mixed:
#   HELD-OUT COMPOSITION — the chain shape was never trained (the real test)
#   seen composition, held-out instance — the 20% split train_heads_with
#                                         reserves (a memorisation check)
held_comp = [i for i, h in enumerate(hops) if h["kind"] in HOLDOUT]
seen_comp = sorted(hop_eval_ids)
print(f"\neval: {len(held_comp)} held-out-composition, "
      f"{len(seen_comp)} seen-composition held-out instances", flush=True)


def run(idxs, label):
    with torch.no_grad():
        app = torch.softmax(ans(torch.tensor(Zh[idxs])), -1).numpy()
        pvv = torch.sigmoid(det(torch.tensor(Zh[idxs]))).numpy()
    rows, chain_ok = [], 0
    for j, i in enumerate(idxs):
        h = hops[i]
        path = plan(Zh[i], h["subject"])
        if path and len(set(path)) != len(path):
            REPEATED[0] += 1
        if path == h["chain"]:
            chain_ok += 1
        if not path:
            rows.append(("abstain", 0.0, h["kind"]))
            continue
        got = walk(h["subject"], path)
        o = ("abstain" if not got else
             ("correct" if facts[h["answer_fact"]]["object"] in got
              else "wrong"))
        rows.append((o, float(app[j] @ rng_cprof[path[-1]]), h["kind"]))
    n = len(rows)
    ung = collections.Counter(r[0] for r in rows)
    print(f"\n{label} (n={n})")
    print(f"  exact chain recovered  {chain_ok/n:.3f}")
    print(f"  ungated   correct {ung['correct']/n:.3f}  "
          f"wrong {ung['wrong']/n:.3f}  abstain {ung['abstain']/n:.3f}")
    # A -> A chains are 79% of the real 2-hop shapes and the planner cannot
    # emit them at all (permutations over DISTINCT candidates, and a
    # multi-label relation vector has no way to say "twice"). Mixing them in
    # would hide a structural limit inside an average, so they are split out.
    for tag, keep in (("same-relation A->A",
                       lambda k: k.split(">")[0] == k.split(">")[1]),
                      ("distinct-relation A->B",
                       lambda k: k.split(">")[0] != k.split(">")[1])):
        sub = [r for r in rows if keep(r[2])]
        if not sub:
            continue
        c = collections.Counter(r[0] for r in sub)
        m = len(sub)
        print(f"    {tag:22s} correct {c['correct']/m:.3f}  "
              f"wrong {c['wrong']/m:.3f}  abstain {c['abstain']/m:.3f}"
              f"  (n={m})")
    return rows, chain_ok / n


rows_h, chain_h = run(held_comp, "HELD-OUT COMPOSITIONS")
rows_s, chain_s = run(seen_comp, "seen compositions, held-out instances")
print(f"\nplanned paths that repeat a relation, over both populations: "
      f"{REPEATED[0]}  (0 before the arity head + entity-level gate)")

# Answer-type gate, threshold selected exactly as in D110 but on the SEEN
# compositions — the held-out compositions must not touch the choice.
THRS = [round(0.05 * k, 2) for k in range(17)]


def tally(rows, thr):
    c = collections.Counter()
    for o, fit, _ in rows:
        c[o if fit >= thr else "abstain"] += 1
    return c


# The threshold rule is calibrated on SEEN compositions — and with the
# entity-level gate that population has wrong=0.001, so the rule fires at
# 0.0 and the gate provides no protection at all on held-out compositions.
# That is a methodological trap worth stating plainly: A REFUSAL THRESHOLD
# CANNOT BE CALIBRATED ON A POPULATION THAT DOES NOT EXHIBIT THE FAILURE.
# In D110 the calibration split did make errors, so it worked there. Here
# the achievable curve is printed instead, to separate "the signal is
# absent" from "the calibration source is wrong" — they need different fixes.
fit_c = [f for o, f, _ in rows_h if o == "correct"]
fit_w = [f for o, f, _ in rows_h if o == "wrong"]
if fit_c and fit_w:
    print(f"\nanswer-type fit on HELD-OUT compositions: correct med "
          f"{np.median(fit_c):.3f}  wrong med {np.median(fit_w):.3f}")
    print("  achievable curve (oracle threshold — NOT a claimed result)")
    for t in (0.0, 0.2, 0.4, 0.6, 0.8):
        c = tally(rows_h, t); m = sum(c.values())
        a_ = c["correct"] + c["wrong"]
        print(f"    thr {t:.1f}  correct {c['correct']/m:.3f}  "
              f"wrong {c['wrong']/m:.3f}  precision "
              f"{(c['correct']/a_ if a_ else 0):.3f}")

THR = next((t for t in THRS
            if (lambda c: c["wrong"] / max(sum(c.values()), 1) <= 0.02)(
                tally(rows_s, t))), THRS[-1])
G = tally(rows_h, THR)
n = sum(G.values())
a = G["correct"] + G["wrong"]
print(f"\nanswer-type gate  thr={THR} (chosen on SEEN compositions)")
print(f"  HELD-OUT COMPOSITIONS  correct {G['correct']/n:.3f}  "
      f"wrong {G['wrong']/n:.3f}  abstain {G['abstain']/n:.3f}  "
      f"precision {(G['correct']/a if a else 0):.3f}  (n={n})")

per = collections.defaultdict(collections.Counter)
for o, fit, k in rows_h:
    per[k][o if fit >= THR else "abstain"] += 1
print("\nper held-out composition (gated)")
for k, c in sorted(per.items()):
    m = sum(c.values())
    print(f"  {k:38s} correct {c['correct']/m:.3f}  wrong {c['wrong']/m:.3f}"
          f"  abstain {c['abstain']/m:.3f}  (n={m})")

res = {
    "manifest": run_manifest(seed=0, config={"holdout_compositions": HOLDOUT,
                                             "min_n": MIN_N,
                                             "cites_cap": CITES_CAP}),
    "hops": len(hops),
    "compositions": dict(kept),
    "held_out_compositions": {
        "n": len(held_comp), "exact_chain_recovered": round(chain_h, 4),
        "ungated": dict(collections.Counter(r[0] for r in rows_h)),
        "gated": {**G, "threshold": THR,
                  "precision_when_answered": round(G["correct"] / a, 4)
                  if a else 0.0,
                  "precision_ci95": [round(x, 4)
                                     for x in wilson_ci(G["correct"], a)]
                  if a else None},
        "per_composition_gated": {k: dict(c) for k, c in per.items()},
    },
    "seen_compositions": {
        "n": len(seen_comp), "exact_chain_recovered": round(chain_s, 4),
        "ungated": dict(collections.Counter(r[0] for r in rows_s)),
    },
    "scope": ("2-hop only. Compositions held out entirely, so this measures "
              "chaining relations never seen chained — not phrasing "
              "robustness, which D110 covers. Hop questions are templated "
              "(2 noun phrases x 2 question forms per composition)."),
}
(ROOT / "results" / "exp17_hops.json").write_text(json.dumps(res, indent=1))
print("\n[done] results/exp17_hops.json")
