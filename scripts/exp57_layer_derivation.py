"""Should a relation's basis come from the layer BELOW it? (phase 1 of the layering idea)

D165 found that anchors derived from how relations partition *question* space
(`lda_between`) beat anchors derived from relation *label strings*. That is one
data point for a general principle: **a layer's basis should come from an
adjacent layer, not from its own labels.**

If the principle is real, going one layer further should go further still. A
relation's *domain* and *range profiles* — the mean embedding of the things it
connects — are a cruder but more direct statement of what a relation IS than
either its name or its question distribution. They are also already in the
system: `exp39_typegate`'s `CENT[r]` is exactly a range profile, built for the
answer-type gate and never used to fit a basis.

Five strategies, all fitted on TRAINED relations only:

  * `lda_between`     — D165's champion, question-derived. CONTROL, and it
                        must reproduce 0.4530 at K=32 or this script aborts.
  * `kmeans_range`    — k-means over per-relation range profiles.
  * `kmeans_domrange` — k-means over domain AND range profiles pooled (2 per
                        relation, so 88 vectors: a corpus pool that can exceed
                        the relation count without the external vocabulary).
  * `lda_range`       — top-K eigenvectors of the between-relation scatter of
                        OBJECT embeddings. The L2 analogue of `lda_between`.
  * `lda_domrange`    — same over 88 (relation, role) classes.

The invariant is unchanged: a relation's coordinate is always
`unit(label @ PC.T)`, so only the basis moves and zero-instance arrival
survives. Profiles decide where the axes point; they never become a relation's
coordinate, which is what would break the product claim.

**Registered prediction, before running** (D165's lesson: the summarising
sentence is where this project's errors live, so it gets written down first):
profile-derived bases beat `lda_between` **modestly** — 0.45 to roughly 0.50 —
because a range profile is a blunt summary and the discriminative objective is
already doing most of the work. A large jump would be surprising and should be
replicated on a second holdout draw before being believed. **A loss falsifies
the adjacent-layer principle**, and the layering becomes a description we are
imposing rather than a structure the data has.

Reuses exp56's caches; no new embedding.

Usage: .venv/bin/python scripts/exp57_layer_derivation.py [m3|gemma|both]
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

SEED, MIN_ALIAS, N_SUBJ, N_HOLD_REL = 0, 6, 40, 12
TRAIN_ALIASES, N_EVAL_ALIAS = 2, 2
KS = (4, 8, 16, 32, 43, 64, 87)
WHICH = sys.argv[1] if len(sys.argv) > 1 else "both"

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
print(f"{len(RELS)} relations ({len(TRAINED_R)} trained), {len(TRIP)} triples, "
      f"{len(ENTS)} entities", flush=True)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402


def unit(a):
    return a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9)


def between_scatter_dirs(groups, K):
    """Top-K directions along which group MEANS differ most (S_B eigenvectors)."""
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


def build(strategy, K, ctx):
    L_tr, Zq, dom, rng_, dom_g, rng_g, qg = ctx
    if strategy == "lda_between":
        return between_scatter_dirs(qg, K)
    if strategy == "kmeans_range":
        return unit(fit_anchors(rng_, K, seed=SEED)) if K <= len(rng_) else None
    if strategy == "kmeans_domrange":
        pool = np.concatenate([dom, rng_], 0)
        return unit(fit_anchors(pool, K, seed=SEED)) if K <= len(pool) else None
    if strategy == "lda_range":
        return between_scatter_dirs(rng_g, K)
    if strategy == "lda_domrange":
        return between_scatter_dirs(dom_g + rng_g, K)
    raise ValueError(strategy)


def identify(Z, C_all, dim):
    M = np.stack([C_all[r] for r in RELS])
    tr = [i for i, x in enumerate(rows)
          if x["rel"] in TRAINED_R and x["ai"] < TRAIN_ALIASES]
    ev_t = [i for i, x in enumerate(rows)
            if x["rel"] in TRAINED_R and x["ai"] >= MIN_ALIAS - N_EVAL_ALIAS]
    ev_n = [i for i, x in enumerate(rows) if x["rel"] in HELD_R]
    X = torch.tensor(Z[tr])
    Y = torch.tensor(np.stack([C_all[rows[i]["rel"]] for i in tr]))
    torch.manual_seed(SEED)
    hd = nn.Sequential(nn.Linear(Z.shape[1], 512), nn.GELU(),
                       nn.Linear(512, dim))
    op = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(X)).split(512):
            op.zero_grad()
            ((hd(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
            op.step()
    hd.eval()

    def acc(idxs):
        with torch.no_grad():
            p = unit(hd(torch.tensor(Z[idxs])).numpy())
        pred = (p @ M.T).argmax(1)
        return float(np.mean([RELS[int(j)] == rows[i]["rel"]
                              for j, i in zip(pred, idxs)]))
    return round(acc(ev_t), 4), round(acc(ev_n), 4)


STRATS = ["lda_between", "kmeans_range", "kmeans_domrange",
          "lda_range", "lda_domrange"]
ARMS = (["m3"] if WHICH in ("m3", "both") else []) + \
       (["gemma_symmetric"] if WHICH in ("gemma", "both") else [])
OUT = {}
for arm in ARMS:
    cache = ROOT / "results" / f"exp56_{arm}_emb.npz"
    z = np.load(cache, allow_pickle=True)
    assert list(z["qtext"]) == QTEXT and list(z["ents"]) == ENTS, \
        f"population drifted from exp56 — {arm} cache cannot be reused"
    Zq, Zl, Zent = z["Zq"], z["Zl"], z["Zent"]
    ei = {e: i for i, e in enumerate(ENTS)}
    subs_of = collections.defaultdict(list)
    objs_of = collections.defaultdict(list)
    for s, p, o in TRIP:
        if p in TRAINED_R:
            subs_of[p].append(ei[s])
            objs_of[p].append(ei[o])
    dom_g = [Zent[subs_of[r]] for r in TRAINED_R if subs_of[r]]
    rng_g = [Zent[objs_of[r]] for r in TRAINED_R if objs_of[r]]
    dom = unit(np.stack([g.mean(0) for g in dom_g]))
    rng_ = unit(np.stack([g.mean(0) for g in rng_g]))
    qg = [Zq[[i for i, x in enumerate(rows)
              if x["rel"] == r and x["ai"] < TRAIN_ALIASES]]
          for r in TRAINED_R]
    RAW = {r: Zl[i] for i, r in enumerate(RELS)}
    L_tr = np.stack([RAW[r] for r in TRAINED_R])
    ctx = (L_tr, Zq, dom, rng_, dom_g, rng_g, qg)
    print(f"\n=== ARM: {arm} ===   domain profiles {dom.shape}, "
          f"range profiles {rng_.shape}", flush=True)

    # reproduction gate: the control must match exp56 or nothing below is
    # comparable to it (the D158 lesson — never trust a pasted baseline)
    PC = build("lda_between", 32, ctx)
    _, nov = identify(Zq, {r: unit(RAW[r] @ PC.T) for r in RELS}, 32)
    prev = json.loads((ROOT / "results"
                       / "exp56_anchor_strategy.json").read_text())
    want = prev["arms"][arm]["lda_between_K32"]["novel"]
    print(f"  control check — lda_between K=32: {nov:.4f} vs exp56 "
          f"{want:.4f}")
    assert abs(nov - want) < 1e-3, (
        f"control does not reproduce exp56 ({nov} vs {want}); every "
        f"comparison below would be against a different setup")

    res = {}
    print(f"  {'strategy':>18} {'K':>4} {'trained':>8} {'NOVEL':>8} {'vs ctrl':>8}")
    for st in STRATS:
        for K in KS:
            PC = build(st, K, ctx)
            if PC is None:
                continue
            t, n = identify(Zq, {r: unit(RAW[r] @ PC.T) for r in RELS},
                            PC.shape[0])
            res[f"{st}_K{K}"] = {"strategy": st, "K": K, "trained": t,
                                 "novel": n}
            print(f"  {st:>18} {K:4d} {t:8.4f} {n:8.4f} {n - want:+8.4f}",
                  flush=True)
    OUT[arm] = {"control_novel_K32": want, "cells": res}

print("\n=== best NOVEL per strategy, against the D165 champion ===")
verdicts = {}
for arm, a in OUT.items():
    ctrl = a["control_novel_K32"]
    print(f"\n  {arm}  (control lda_between K=32 = {ctrl:.4f})")
    best_profile = None
    for st in STRATS:
        cells = [v for v in a["cells"].values() if v["strategy"] == st]
        if not cells:
            continue
        b = max(cells, key=lambda v: v["novel"])
        tag = "  <- CONTROL" if st == "lda_between" else ""
        print(f"    {st:>18} K={b['K']:<4d} trained {b['trained']:.4f}  "
              f"NOVEL {b['novel']:.4f}  {b['novel'] - ctrl:+.4f}{tag}")
        if st != "lda_between" and (best_profile is None
                                    or b["novel"] > best_profile["novel"]):
            best_profile = dict(b)
    gain = best_profile["novel"] - ctrl
    verdicts[arm] = {"best_profile": best_profile, "gain_over_control": round(gain, 4)}
    if gain > 0.02:
        v = (f"SUPPORTED — profile-derived beats question-derived by "
             f"{gain:+.4f}; deriving a layer from the one below it is a real "
             f"mechanism, not a description.")
    elif gain > -0.02:
        v = (f"NO DIFFERENCE — {gain:+.4f}. Profiles are neither better nor "
             f"worse than questions, so 'derive from the adjacent layer' is "
             f"underdetermined by this test.")
    else:
        v = (f"FALSIFIED — profile-derived LOSES by {gain:+.4f}. The layering "
             f"is a description we are imposing, not a structure the data "
             f"has, and the adjacent-layer principle should be dropped.")
    verdicts[arm]["verdict"] = v
    print(f"    -> {v}")

out = {"manifest": run_manifest(seed=SEED,
                                config={"KS": list(KS), "STRATS": STRATS,
                                        "N_HOLD_REL": N_HOLD_REL}),
       "n_relations": len(RELS), "n_trained": len(TRAINED_R),
       "chance": round(1 / len(RELS), 4),
       "arms": OUT, "verdicts": verdicts,
       "registered_prediction": (
           "profile-derived bases beat lda_between MODESTLY (0.45 -> ~0.50); "
           "a large jump would be surprising and needs a second holdout draw "
           "before belief; a loss falsifies the adjacent-layer principle"),
       "scope": ("Phase 1 of the layering idea: does a relation's basis do "
                 "better when derived from the layer BELOW (its domain/range "
                 "profiles — what it connects) than from its own labels or "
                 "from its question distribution? Coordinates remain "
                 "unit(label @ PC.T) in every strategy, so only the basis "
                 "moves and zero-instance arrival is untouched. All bases "
                 "fitted on TRAINED relations only. Reuses exp56's caches "
                 "under a content assert, and the lda_between control must "
                 "reproduce exp56's number in-run or the script aborts — no "
                 "pasted baselines (D158). Identification level only, so the "
                 "ordering still needs end-to-end confirmation before any "
                 "pipeline change.")}
(ROOT / "results" / "exp57_layer_derivation.json").write_text(
    json.dumps(out, indent=1))
print("\n[done] results/exp57_layer_derivation.json")
