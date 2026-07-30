"""Does a basis help BECAUSE it differs from what the encoder already encodes?

exp57 tested "derive the basis from the layer below" and it lost on both
encoders. The proposed reinterpretation: that test assumed category-faithfulness
and output quality correlate DIRECTLY, and the inverse is more likely — a basis
that mirrors structure the encoder already has is **redundant**, so capturing
the categories faithfully could make output worse rather than better.

That reinterpretation turns a falsification into a confirmation, which is
precisely the move that has to carry its own falsifier. So it gets one.

**The measurement.** For a basis `PC`, orthonormalise its span and ask what
fraction of the encoder's own representation lies inside it:

    capture(X) = mean over rows of  ||x @ Q||^2 / ||x||^2 ,  Q = orth(PC^T)

Two of them, because the basis sits between two different things:

  * `capture_q` — question space, what the head maps FROM;
  * `capture_l` — label space, what gets projected INTO coordinates.

High capture means the basis span is where the encoder already puts its mass:
redundant. Low capture means the basis lives somewhere the encoder does not.

**Three outcomes, stated before running:**

  * capture correlates **negatively** with novel transfer → redundancy hurts,
    the sign convention in exp57 was wrong, and a basis earns its keep by
    differing from the encoder rather than by agreeing with it;
  * **no correlation** → "symmetry hurts" is not the mechanism, and exp57's
    negative result stands as a negative result;
  * capture correlates **positively** → the opposite of the proposal: bases
    work by concentrating on what the encoder already represents well.

**Registered expectation.** I expect a POSITIVE correlation with `capture_l`
and a weak-to-absent one with `capture_q` — because a basis has to preserve
the label geometry it projects, and the winning strategy (`lda_between`) is
derived from question space and so should be well aligned with it, not
orthogonal to it. If the correlation is negative I am wrong and the
redundancy account is right.

Every basis from exp56 and exp57 is rebuilt here and measured, so the
correlation runs over the whole space we have explored rather than over the
handful that happened to win.

Usage: .venv/bin/python scripts/exp58_redundancy.py
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

from codec.evals.anchors import fit_anchors                      # noqa: E402
from codec.manifest import run_manifest                          # noqa: E402
from foundation.kb import KB                                     # noqa: E402

SEED, MIN_ALIAS, N_SUBJ, N_HOLD_REL, K_ENTITY = 0, 6, 40, 12, 32
TRAIN_ALIASES = 2

sch = {d["pid"]: d for d in
       json.loads((ROOT / "data" / "schema_v0.json").read_text())}
props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
kb = KB(backend="pg", table="poc")
wiki = [c for c in kb.claims
        if not c["page"].startswith(("arxiv:", "hf:", "user"))]
LABEL, ALIAS = {}, {}
for c in wiki:
    p = c["pid"]
    if p in LABEL:
        continue
    lab = (sch.get(p) or {}).get("label") or (props.get(p) or {}).get("label")
    al = list((sch.get(p) or {}).get("aliases", []))
    al += [a for a in (props.get(p) or {}).get("aliases", []) if a not in al]
    al = [a for a in al if 2 < len(a) < 40]
    if lab and len(al) >= MIN_ALIAS:
        LABEL[p], ALIAS[p] = lab, al[:MIN_ALIAS]
RELS = sorted(LABEL)
TRIP = sorted({(c["subject"], c["pid"], c["object"]) for c in wiki
               if c["pid"] in LABEL})
by_rel = collections.defaultdict(list)
for s, p, o in TRIP:
    by_rel[p].append(s)
rng = np.random.default_rng(SEED)
SUBJ = {}
for r in RELS:
    s = sorted(set(by_rel[r]))
    SUBJ[r] = ([s[i] for i in sorted(rng.choice(len(s), N_SUBJ, replace=False))]
               if len(s) > N_SUBJ else s)
HELD_R = {RELS[i] for i in sorted(rng.permutation(len(RELS))[:N_HOLD_REL])}
TRAINED_R = [r for r in RELS if r not in HELD_R]
rows = [{"rel": r, "ai": ai, "alias": a, "subj": s}
        for r in RELS for ai, a in enumerate(ALIAS[r]) for s in SUBJ[r]]
QTEXT = [f"What is the {x['alias']} of {x['subj']}?" for x in rows]
ENTS = sorted({t[0] for t in TRIP} | {t[2] for t in TRIP})
EXT = sorted({v["label"] for v in props.values() if v.get("label")})


def unit(a):
    return a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9)


def capture(X, PC):
    """Fraction of each row's squared norm lying in span(PC), averaged."""
    Q = np.linalg.qr(PC.T)[0]                     # [d, r] orthonormal span
    num = (X @ Q) ** 2
    return float(np.mean(num.sum(1) / ((X ** 2).sum(1) + 1e-12)))


def between_dirs(groups, K):
    mus, ns = [], []
    for g in groups:
        if len(g):
            mus.append(g.mean(0))
            ns.append(len(g))
    if len(mus) < 2 or K > len(mus) - 1:
        return None
    M = np.stack(mus)
    mu = np.average(M, axis=0, weights=ns)
    D = (M - mu) * np.sqrt(np.array(ns))[:, None]
    return unit(np.linalg.svd(D, full_matrices=False)[2][:K])


ARMS = ["m3", "gemma_symmetric"]
OUT, ALLPTS = {}, []
for arm in ARMS:
    z56 = np.load(ROOT / "results" / f"exp56_{arm}_emb.npz", allow_pickle=True)
    assert list(z56["qtext"]) == QTEXT and list(z56["ents"]) == ENTS, \
        f"population drift vs exp56 for {arm}"
    Zq, Zl, Zent = z56["Zq"], z56["Zl"], z56["Zent"]
    z55 = np.load(ROOT / "results" / f"exp55_{arm}_emb.npz", allow_pickle=True)
    Ze = z55["Ze"] if list(z55["ext"]) == EXT else None
    d = Zq.shape[1]
    RAW = {r: Zl[i] for i, r in enumerate(RELS)}
    L_tr = np.stack([RAW[r] for r in TRAINED_R])
    ei = {e: i for i, e in enumerate(ENTS)}
    subs, objs = collections.defaultdict(list), collections.defaultdict(list)
    for s, p, o in TRIP:
        if p in TRAINED_R:
            subs[p].append(ei[s])
            objs[p].append(ei[o])
    dom_g = [Zent[subs[r]] for r in TRAINED_R if subs[r]]
    rng_g = [Zent[objs[r]] for r in TRAINED_R if objs[r]]
    dom = unit(np.stack([g.mean(0) for g in dom_g]))
    rng_p = unit(np.stack([g.mean(0) for g in rng_g]))
    OFF = unit(np.stack([Zent[ei[o]] - Zent[ei[s]] for s, p, o in TRIP
                         if p in TRAINED_R]))
    qg = [Zq[[i for i, x in enumerate(rows)
              if x["rel"] == r and x["ai"] < TRAIN_ALIASES]]
          for r in TRAINED_R]

    def basis(st, K):
        if st == "kmeans_label":
            return unit(fit_anchors(L_tr, K, seed=SEED)) if K <= len(L_tr) else None
        if st == "pca_label":
            if K > len(L_tr) - 1:
                return None
            return unit(np.linalg.svd(L_tr - L_tr.mean(0),
                                      full_matrices=False)[2][:K])
        if st == "lda_between":
            return between_dirs(qg, K)
        if st == "lda_range":
            return between_dirs(rng_g, K)
        if st == "lda_domrange":
            return between_dirs(dom_g + rng_g, K)
        if st == "kmeans_range":
            return unit(fit_anchors(rng_p, K, seed=SEED)) if K <= len(rng_p) else None
        if st == "kmeans_domrange":
            pool = np.concatenate([dom, rng_p], 0)
            return unit(fit_anchors(pool, K, seed=SEED)) if K <= len(pool) else None
        if st == "kmeans_offset":
            return unit(fit_anchors(OFF, K, seed=SEED))
        if st == "external13k":
            return unit(fit_anchors(Ze, K, seed=SEED)) if Ze is not None else None
        if st == "entity_complement":
            if K > len(L_tr):
                return None
            E = fit_anchors(Zent, K_ENTITY, seed=SEED)
            Q = np.linalg.qr(E.T)[0]
            Lp = L_tr - (L_tr @ Q) @ Q.T
            keep = np.linalg.norm(Lp, axis=1) > 1e-6
            return unit(fit_anchors(unit(Lp[keep]), K, seed=SEED)) \
                if keep.sum() >= K else None
        if st == "random_orthonormal":
            g = np.random.default_rng(SEED).standard_normal((d, K))
            return unit(np.linalg.qr(g)[0].T.astype(np.float32)) if K <= d else None
        return None

    # NOVEL scores already measured, keyed the same way
    prev = {}
    for f, key in ((f"exp56_anchor_strategy.json", "cells"),
                   (f"exp57_layer_derivation.json", "cells")):
        p = ROOT / "results" / f
        if not p.exists():
            continue
        j = json.loads(p.read_text())
        a = j["arms"].get(arm, {})
        cells = a.get(key, a) if isinstance(a, dict) else {}
        for k, v in cells.items():
            if isinstance(v, dict) and "novel" in v:
                prev[(v["strategy"], v["K"])] = v["novel"]
    print(f"\n=== {arm}: {len(prev)} measured (strategy, K) cells ===", flush=True)
    print(f"  {'strategy':>20} {'K':>4} {'NOVEL':>7} {'cap_q':>7} {'cap_l':>7}")
    pts = []
    for (st, K), nov in sorted(prev.items()):
        PC = basis(st, K)
        if PC is None:
            continue
        cq, cl = capture(Zq, PC), capture(np.stack(list(RAW.values())), PC)
        pts.append({"strategy": st, "K": K, "novel": nov,
                    "capture_q": round(cq, 4), "capture_l": round(cl, 4)})
        print(f"  {st:>20} {K:4d} {nov:7.4f} {cq:7.4f} {cl:7.4f}")
    OUT[arm] = pts
    ALLPTS += [dict(p, arm=arm) for p in pts]

print("\n=== does redundancy with the encoder predict transfer? ===")
corrs = {}
for arm, pts in OUT.items():
    n = np.array([p["novel"] for p in pts])
    cq = np.array([p["capture_q"] for p in pts])
    cl = np.array([p["capture_l"] for p in pts])
    corrs[arm] = {"capture_q_vs_novel": round(float(np.corrcoef(cq, n)[0, 1]), 4),
                  "capture_l_vs_novel": round(float(np.corrcoef(cl, n)[0, 1]), 4),
                  "n_cells": len(pts)}
    print(f"  {arm:>18}  cap_q r={corrs[arm]['capture_q_vs_novel']:+.4f}   "
          f"cap_l r={corrs[arm]['capture_l_vs_novel']:+.4f}   "
          f"({len(pts)} cells)")

rq = np.mean([c["capture_q_vs_novel"] for c in corrs.values()])
rl = np.mean([c["capture_l_vs_novel"] for c in corrs.values()])
if rq < -0.3 or rl < -0.3:
    verdict = (f"REDUNDANCY HURTS — capture correlates NEGATIVELY with "
               f"transfer (q {rq:+.3f}, l {rl:+.3f}). A basis earns its keep "
               f"by differing from what the encoder already encodes, and "
               f"exp57's sign convention was wrong.")
elif rq > 0.3 or rl > 0.3:
    verdict = (f"REDUNDANCY HELPS — capture correlates POSITIVELY (q "
               f"{rq:+.3f}, l {rl:+.3f}). Bases work by concentrating on what "
               f"the encoder already represents well, which is the opposite "
               f"of the symmetry proposal.")
else:
    verdict = (f"NOT THE MECHANISM — capture barely predicts transfer (q "
               f"{rq:+.3f}, l {rl:+.3f}). Redundancy with the encoder does "
               f"not explain which bases work, so exp57's negative result "
               f"stands as a negative result rather than an inverted one.")
print(f"\n=== VERDICT ===\n  {verdict}")

out = {"manifest": run_manifest(seed=SEED, config={"K_ENTITY": K_ENTITY}),
       "cells": OUT, "correlations": corrs, "verdict": verdict,
       "registered_expectation": (
           "POSITIVE with capture_l, weak-to-absent with capture_q; a "
           "negative correlation means the redundancy account is right and "
           "I am wrong"),
       "scope": ("Rebuilds every basis measured in exp56 and exp57 and asks "
                 "what fraction of the encoder's own question and label "
                 "representation lies inside each basis span, then "
                 "correlates that against already-measured novel transfer. "
                 "This exists to give the 'symmetry hurts' reinterpretation "
                 "of exp57 a falsifier of its own, since reinterpreting a "
                 "negative result as a confirmation is otherwise "
                 "unfalsifiable. Correlation runs over the whole explored "
                 "space, not the winners.")}
(ROOT / "results" / "exp58_redundancy.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp58_redundancy.json")
