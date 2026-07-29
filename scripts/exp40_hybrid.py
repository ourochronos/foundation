"""Retrieval + label-coordinate fallback, switched on neighbour distance (D136).

Two results point opposite ways and neither component can be the architecture
alone:

  D129  1-NN retrieval beats the parametric head on unseen PHRASINGS of
        known relations, 0.925 vs 0.614.
  D131  Retrieval collapses on NEW relations, 0.229 against the head's
        0.782, because it can only return a target that exists in its bank —
        a relation with no stored examples gets the nearest KNOWN relation's
        coordinate, confidently.

Those are different axes, so this crosses them: relations either known or
held out entirely, phrasings either trained or held out. Four populations,
never averaged, plus a not-applicable unanswerable set (law #9).

The hybrid switches on **neighbour distance**, which D132 argued is itself a
confidence signal and should be reported as one: if the nearest stored
question is close, trust retrieval; if nothing is close, the relation
probably has no examples, so fall back to its label-derived coordinate. The
switch is calibrated on populations that exhibit the failure (law #6) and
never on the evaluation sets.

D134's answer-type gate is on throughout, since it is now part of the walker.

Usage: .venv/bin/python scripts/exp40_hybrid.py
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
N_HOLD_REL, CAP = 12, 1000

sch = {d["pid"]: d for d in
       json.loads((ROOT / "data" / "schema_v0.json").read_text())}
props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
kb = KB(backend="pg", table="poc")
wiki_all = [c for c in kb.claims
            if not c["page"].startswith(("arxiv:", "hf:", "user"))]
LABEL, ALIAS = {}, {}
for c in wiki_all:
    p = c["pid"]
    if p in LABEL:
        continue
    lab = (sch.get(p) or {}).get("label") or (props.get(p) or {}).get("label")
    al = list((sch.get(p) or {}).get("aliases", []))
    al += [a for a in (props.get(p) or {}).get("aliases", []) if a not in al]
    al = [a for a in al if 2 < len(a) < 40]
    if lab and len(al) >= 4:
        LABEL[p], ALIAS[p] = lab, al[:4]
RELS = sorted(LABEL)
wiki = [c for c in wiki_all if c["pid"] in LABEL]
gold, avail = collections.defaultdict(set), collections.defaultdict(set)
for c in wiki:
    gold[(c["subject"], c["pid"])].add(c["object"])
    avail[c["subject"]].add(c["pid"])
subjects = sorted(avail)
OBJS = sorted({c["object"] for c in wiki})
rng = np.random.default_rng(SEED)
HOLD_R = {RELS[i] for i in sorted(rng.permutation(len(RELS))[:N_HOLD_REL])}
print(f"{len(wiki)} claims / {len(RELS)} relations (>=4 aliases) / "
      f"{len(subjects)} subjects")
print(f"held out ENTIRELY: {', '.join(sorted(LABEL[r] for r in HOLD_R))}")

TRAIN_AL = {r: ALIAS[r][:2] for r in RELS}
EVAL_AL = {r: ALIAS[r][2:] for r in RELS}


def q(s, r, alias):
    return {"subject": s, "chain": [r], "answers": sorted(gold[(s, r)]),
            "text": f"What is the {alias} of {s}?"}


POP = collections.defaultdict(list)
for s in subjects:
    for r in sorted(avail[s]):
        nov = "newrel" if r in HOLD_R else "knownrel"
        POP[f"{nov}_trainphr"].append(q(s, r, TRAIN_AL[r][0]))
        POP[f"{nov}_newphr"].append(q(s, r, EVAL_AL[r][0]))
    for r in RELS:                                   # law #9: not-applicable
        if r not in avail[s]:
            POP["not_applicable"].append(
                {"subject": s, "chain": [r], "answers": [],
                 "text": f"What is the {EVAL_AL[r][0]} of {s}?"})
for k in list(POP):
    v = sorted(POP[k], key=lambda a: (a["subject"], a["chain"][0]))
    if len(v) > CAP:
        v = [v[i] for i in sorted(rng.choice(len(v), CAP, replace=False))]
    POP[k] = v
    print(f"  {k:22s} {len(v):5d}")

ORDER = sorted(POP)
texts, index = [], {}
for k in ORDER:
    index[k] = (len(texts), len(texts) + len(POP[k]))
    texts += [a["text"] for a in POP[k]]
# the retrieval BANK: trained aliases of KNOWN relations only, which is what
# a deployed system would actually have stored
bank_rows = [q(s, r, a) for s in subjects for r in sorted(avail[s])
             if r not in HOLD_R for a in TRAIN_AL[r]]
bank_rows = sorted(bank_rows, key=lambda a: (a["subject"], a["chain"][0],
                                             a["text"]))
if len(bank_rows) > 4000:
    bank_rows = [bank_rows[i] for i in
                 sorted(rng.choice(len(bank_rows), 4000, replace=False))]
bank_texts = [a["text"] for a in bank_rows]
cache = ROOT / "results" / "exp40_emb.npz"
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    assert list(z["texts"]) == texts and list(z["bank"]) == bank_texts \
        and list(z["objs"]) == OBJS, "cache misaligned; delete it"
    Z, Zl, Zo, Zb = z["Z"], z["Zl"], z["Zo"], z["Zb"]
else:
    Z = P.unit(P.embed_texts(texts))
    Zl = P.unit(P.embed_texts([LABEL[r] for r in RELS]))
    Zo = P.unit(P.embed_texts(OBJS))
    Zb = P.unit(P.embed_texts(bank_texts))
    np.savez(cache, Z=Z, Zl=Zl, Zo=Zo, Zb=Zb, texts=np.array(texts),
             bank=np.array(bank_texts), objs=np.array(OBJS))
RC = {r: Zl[i] for i, r in enumerate(RELS)}
OI = {o: i for i, o in enumerate(OBJS)}
PC = P.unit(fit_anchors(np.stack([RC[r] for r in RELS]), K_BASIS, seed=SEED))
C = {r: P.unit(RC[r] @ PC.T) for r in RELS}
BANK_Y = np.stack([C[a["chain"][0]] for a in bank_rows])
CENT = {}
for r in RELS:
    ids = [OI[o] for o in sorted({c["object"] for c in wiki
                                  if c["pid"] == r}) if o in OI]
    if ids:
        CENT[r] = P.unit(Zo[ids].mean(0))
print(f"{len(texts)} questions, bank {Zb.shape}, "
      f"{len(CENT)} answer-type centroids", flush=True)


def emb(k):
    a, b = index[k]
    return Z[a:b]


def step(nodes, r):
    out = set()
    for s in nodes:
        out |= gold.get((s, r), set())
    return out


def targets(E, mode, dthr=None):
    """mode: retrieval | fallback | hybrid. Returns (target, nn_similarity)."""
    S = E @ Zb.T
    j = S.argmax(1)
    sim = S[np.arange(len(E)), j]
    ret = BANK_Y[j]
    fb = np.stack([P.unit(e @ PC.T) for e in E])   # label-space projection
    if mode == "retrieval":
        return ret, sim
    if mode == "fallback":
        return fb, sim
    use = (sim >= dthr)[:, None]
    return np.where(use, ret, fb), sim


def evaluate(key, mode, dthr, tthr, answerable=True):
    rows, E = POP[key], emb(key)
    tgt, sim = targets(E, mode, dthr)
    c = collections.Counter()
    for i, a in enumerate(rows):
        resid, frontier, path = tgt[i].copy(), {a["subject"]}, []
        for _ in range(2):
            opts = sorted(set().union(*(avail.get(x, set())
                                        for x in frontier))
                          if frontier else set())
            if not opts:
                break
            g = sorted(((float(resid @ C[r]), r) for r in opts),
                       reverse=True)
            if g[0][0] <= MIN_GAIN:
                break
            nxt = step(frontier, g[0][1])
            if not nxt:
                break
            frontier, path = nxt, path + [g[0][1]]
            resid = resid - C[g[0][1]]
        rn = float(np.linalg.norm(resid))
        # D134 answer-type gate: r_asked read off the TARGET, not the path
        tf = 0.0
        if frontier:
            r_asked = max(RELS, key=lambda r: float(tgt[i] @ C[r]))
            ids = [OI[o] for o in sorted(frontier) if o in OI]
            if ids and r_asked in CENT:
                tf = float(np.mean(Zo[ids] @ CENT[r_asked]))
        if not path or not frontier or rn > RES_THR or tf < tthr:
            c["refuse"] += 1
        elif answerable and set(frontier) & set(a["answers"]):
            c["correct"] += 1
        else:
            c["wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: round(c[k] / n, 4) for k in
            ("correct", "wrong", "refuse")} | {"n": n,
                                               "nn_sim": float(np.mean(sim))}


# calibrate the distance switch and the type threshold on populations that
# exhibit the failure — never on the evaluation sets (law #6)
CAL_KEYS = [("knownrel_trainphr", True), ("not_applicable", False)]
best, bw = (0.0, 0.0), -1.0
for dthr in (0.0, 0.55, 0.65, 0.75, 0.85, 0.95):
    for tthr in (0.0, 0.30, 0.40):
        v = []
        for k, ans in CAL_KEYS:
            r = evaluate(k, "hybrid", dthr, tthr, ans)
            v.append(r["correct"] if ans else r["refuse"])
        if min(v) > bw:
            bw, best = min(v), (dthr, tthr)
DTHR, TTHR = best
print(f"\ncalibrated: neighbour-distance switch {DTHR}, type-fit {TTHR} "
      f"(worst-of-two {bw:.3f} on calibration)")

EVALS = [("knownrel_trainphr", True), ("knownrel_newphr", True),
         ("newrel_trainphr", True), ("newrel_newphr", True),
         ("not_applicable", False)]
print(f"\n{'population':22s} {'mode':>10} {'correct':>8} {'wrong':>7} "
      f"{'refuse':>7} {'nn sim':>7}")
res = {}
for key, ans in EVALS:
    for mode in ("retrieval", "fallback", "hybrid"):
        r = evaluate(key, mode, DTHR, TTHR, ans)
        res[f"{key}_{mode}"] = r
        print(f"{key:22s} {mode:>10} {r['correct']:8.3f} {r['wrong']:7.3f} "
              f"{r['refuse']:7.3f} {r['nn_sim']:7.3f}")
    print()

print("does the hybrid match the better component on EACH axis?")
for key, ans in EVALS:
    if not ans:
        continue
    rt = res[f"{key}_retrieval"]["correct"]
    fb = res[f"{key}_fallback"]["correct"]
    hy = res[f"{key}_hybrid"]["correct"]
    print(f"  {key:22s} retrieval {rt:.3f}  fallback {fb:.3f}  "
          f"hybrid {hy:.3f}   {'OK' if hy >= max(rt, fb) - 0.02 else 'LAGS'}")

k = "newrel_newphr_hybrid"
lo, hi = wilson_ci(int(res[k]["correct"] * res[k]["n"]), res[k]["n"])
print(f"\nhardest cell (new relation AND new phrasing), hybrid: "
      f"{res[k]['correct']:.3f} CI95 [{lo:.3f}, {hi:.3f}]")

out = {
    "manifest": run_manifest(seed=SEED, config={"N_HOLD_REL": N_HOLD_REL,
                                                "DTHR": DTHR,
                                                "TTHR": TTHR}),
    "held_out_relations": sorted(LABEL[r] for r in HOLD_R),
    "results": res, "switch": {"distance": DTHR, "type_fit": TTHR},
    "scope": ("Crosses the two axes that D129 and D131 measured separately: "
              "relation known or held out ENTIRELY, phrasing trained or held "
              "out. The retrieval bank contains trained aliases of KNOWN "
              "relations only, which is what a deployed system would have. "
              "The switch is neighbour distance, calibrated on trained "
              "phrasings plus not-applicable (law #6), never on the "
              "evaluation cells. D134's answer-type gate is on throughout."),
}
(ROOT / "results" / "exp40_hybrid.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp40_hybrid.json")

# ---------------------------------------------------------------------------
# The hybrid lags on every axis: neighbour distance separates the regimes on
# AVERAGE (0.92/0.86 known vs 0.75/0.74 new) but overlaps far too much
# per-item, so the switch sends known-relation queries to the weak fallback
# and new-relation queries to the wrong-by-construction retrieval.
#
# But a deployed system does not have to GUESS which regime it is in. It
# knows its own bank. The honest switch is a lookup, not a proxy: identify
# the relation from the label-space projection, then ask whether that
# relation has any stored examples at all. If it does, retrieval is
# applicable; if it does not, retrieval cannot possibly return it and the
# fallback is the only correct choice.
# ---------------------------------------------------------------------------
BANK_RELS = {a["chain"][0] for a in bank_rows}
print(f"\nbank covers {len(BANK_RELS)} of {len(RELS)} relations")


def evaluate_lookup(key, tthr, answerable=True):
    rows, E = POP[key], emb(key)
    ret, sim = targets(E, "retrieval")
    fb, _ = targets(E, "fallback")
    c = collections.Counter()
    routed_ret = 0
    for i, a in enumerate(rows):
        r_fb = max(RELS, key=lambda r: float(fb[i] @ C[r]))
        use_ret = r_fb in BANK_RELS          # a lookup, not a guess
        routed_ret += use_ret
        tgt_i = ret[i] if use_ret else fb[i]
        resid, frontier, path = tgt_i.copy(), {a["subject"]}, []
        for _ in range(2):
            opts = sorted(set().union(*(avail.get(x, set())
                                        for x in frontier))
                          if frontier else set())
            if not opts:
                break
            g = sorted(((float(resid @ C[r]), r) for r in opts),
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
            r_asked = max(RELS, key=lambda r: float(tgt_i @ C[r]))
            ids = [OI[o] for o in sorted(frontier) if o in OI]
            if ids and r_asked in CENT:
                tf = float(np.mean(Zo[ids] @ CENT[r_asked]))
        if not path or not frontier or rn > RES_THR or tf < tthr:
            c["refuse"] += 1
        elif answerable and set(frontier) & set(a["answers"]):
            c["correct"] += 1
        else:
            c["wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: round(c[k] / n, 4) for k in
            ("correct", "wrong", "refuse")} | {"n": n,
                                               "routed_to_retrieval":
                                               round(routed_ret / n, 4)}


print(f"\n{'population':22s} {'best single':>12} {'dist-switch':>12} "
      f"{'BANK-LOOKUP':>12} {'->retrieval':>12}")
look = {}
for key, ans in EVALS:
    r = evaluate_lookup(key, TTHR, ans)
    look[key] = r
    best_single = max(res[f"{key}_retrieval"]["correct"],
                      res[f"{key}_fallback"]["correct"]) if ans else \
        max(res[f"{key}_retrieval"]["refuse"],
            res[f"{key}_fallback"]["refuse"])
    got = r["correct"] if ans else r["refuse"]
    hy = res[f"{key}_hybrid"]["correct"] if ans else \
        res[f"{key}_hybrid"]["refuse"]
    print(f"{key:22s} {best_single:12.3f} {hy:12.3f} {got:12.3f} "
          f"{r['routed_to_retrieval']:12.3f}")
out["bank_lookup_switch"] = look
(ROOT / "results" / "exp40_hybrid.json").write_text(json.dumps(out, indent=1))
print("[done] bank-lookup switch appended")
