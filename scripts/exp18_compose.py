"""Does an explicit composition operator fix ORDERING? (D112)

D111 left zero-shot composition at 0.534 correct / 0.433 wrong. The
diagnosis narrowed twice:

  * recall is fine — both relations sit in the detector's top-2 on 81.7% of
    held-out-composition questions;
  * thresholding, not ranking, was dropping the second relation (fixed by
    taking candidates as the top-k, k from the arity head);
  * what remains is ORDER. A multi-label relation vector is a SET. A chain
    is a SEQUENCE. The detection head cannot express "r1 then r2" as
    distinct from "r2 then r1" even in principle — the same class of gap as
    D111's "cannot say twice".

So this measures ordering in isolation: GIVEN the correct unordered pair,
how often is the order right? Three scorers, all evaluated only on
compositions never seen composed:

  A  current planner            — entity-level walkability + answer-type fit
  B  additive prototype         — unit(proto_r1 + proto_r2), CLOSED FORM,
                                  order-insensitive by construction, so it
                                  is the null: any lift over chance here
                                  would mean the walkability filter is
                                  doing the work, not the prototype
  C  asymmetric prototype       — unit(a*proto_r1 + b*proto_r2), with the
                                  TWO scalars fit on SEEN compositions only.
                                  Two parameters against 8 training
                                  compositions is the most this data can
                                  honestly support; a 2048->1024 linear map
                                  would be fitting noise.

Usage: .venv/bin/python scripts/exp18_compose.py
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

world = json.loads((ROOT / "data" / "real_world_ai_hops.json").read_text())
hops, facts = world["hops"], world["facts"]
HOLD = set(world["holdout_compositions"])
d = np.load(ROOT / "results" / "real_world_ai_emb.npz")
Zf, Zq = d["Zf"], d["Zq"]
Zh = np.load(ROOT / "results" / "real_world_ai_hop_emb.npz")["Zh"]

art = P.build_artifacts(world, Zf, Zq)
RELS, rel_entry = art["RELS"], art["rel_entry"]
proto = {r: rel_entry[r]["proto"] for r in RELS}

# Observed centroid of each composition's question embeddings. Seen ones are
# the fitting target; held-out ones are never touched by the fit.
cent, kinds = {}, collections.defaultdict(list)
for i, h in enumerate(hops):
    kinds[h["kind"]].append(i)
for k, idxs in kinds.items():
    cent[k] = P.unit(Zh[idxs].mean(0))
seen_k = sorted(k for k in kinds if k not in HOLD)
held_k = sorted(k for k in kinds if k in HOLD)
print(f"{len(seen_k)} seen compositions (fit), {len(held_k)} held out: "
      f"{held_k}")


def comp(a, b, r1, r2):
    return P.unit(a * proto[r1] + b * proto[r2])


# Fit (a, b) on SEEN compositions by maximising mean cosine to the observed
# centroid. Two parameters, coarse grid — no optimiser theatre.
grid = np.linspace(-1.0, 2.0, 61)
best, best_s = (1.0, 1.0), -9e9
for a in grid:
    for b in grid:
        if abs(a) < 1e-9 and abs(b) < 1e-9:
            continue
        sc = np.mean([float(comp(a, b, *k.split(">")) @ cent[k])
                      for k in seen_k])
        if sc > best_s:
            best_s, best = sc, (float(a), float(b))
A_, B_ = best
print(f"fitted asymmetric prototype: a={A_:.2f} b={B_:.2f} "
      f"(mean cos on seen compositions {best_s:.3f})")
print("  held-out cos: " + "  ".join(
    f"{k} {float(comp(A_, B_, *k.split('>')) @ cent[k]):.3f}" for k in held_k))

# ---------------------------------------------------------------------------
# Ordering in isolation: the pair is GIVEN correct, only the order is scored.
# ---------------------------------------------------------------------------
held_i = [i for i, h in enumerate(hops) if h["kind"] in HOLD]
seen_i = [i for i, h in enumerate(hops) if h["kind"] not in HOLD]


def order_acc(idxs, score):
    """score(q_emb, r1, r2) -> higher means 'r1 then r2'. Ties count as
    failures, since a tie is not an answer."""
    ok = tie = 0
    for i in idxs:
        r1, r2 = hops[i]["chain"]
        if r1 == r2:
            continue                      # no ordering question to ask
        f, b = score(Zh[i], r1, r2), score(Zh[i], r2, r1)
        ok += f > b
        tie += f == b
    n = sum(1 for i in idxs if hops[i]["chain"][0] != hops[i]["chain"][1])
    return ok / n, tie / n, n


scorers = {
    "B additive (order-blind null)":
        lambda z, r1, r2: float(z @ comp(1.0, 1.0, r1, r2)),
    "C asymmetric (a,b fit on seen)":
        lambda z, r1, r2: float(z @ comp(A_, B_, r1, r2)),
}
print("\nORDERING ACCURACY — pair given correct, only order scored")
print(f"{'scorer':34s} {'held-out':>10} {'ties':>7} {'seen':>10}")
res_ord = {}
for name, sc in scorers.items():
    ah, th, nh = order_acc(held_i, sc)
    as_, ts, ns = order_acc(seen_i, sc)
    res_ord[name] = {"held_out": round(ah, 4), "held_out_ties": round(th, 4),
                     "held_out_n": nh, "seen": round(as_, 4)}
    print(f"{name:34s} {ah:10.3f} {th:7.3f} {as_:10.3f}")
print(f"chance = 0.500 (n={res_ord[list(scorers)[0]]['held_out_n']} held-out "
      f"ordered questions)")

lo, hi = wilson_ci(int(res_ord["C asymmetric (a,b fit on seen)"]["held_out"]
                       * res_ord["C asymmetric (a,b fit on seen)"]
                       ["held_out_n"]),
                   res_ord["C asymmetric (a,b fit on seen)"]["held_out_n"])
print(f"C held-out 95% CI [{lo:.3f}, {hi:.3f}] — overlapping 0.5 means the "
      f"operator carries no order information")

# ---------------------------------------------------------------------------
# D  Position-specific heads.
#
# C failed BELOW chance, which is more informative than failing at chance:
# two scalars on a bag cannot encode sequence, so the fit absorbed
# relation-specific salience (P_CITES has a weaker prototype than
# P_INTRODUCES) and called it position — then anti-transferred when the
# salience ordering flipped. If order is recoverable from the embedding at
# all, it needs to be carried STRUCTURALLY. Two heads, one per slot, is the
# smallest way to ask that: `first` predicts r1, `last` predicts r2.
#
# Trained on seen compositions and on singles (where first == last == the
# single relation). Held-out compositions are excluded from training, so
# any lift is genuine zero-shot order.
# ---------------------------------------------------------------------------
import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

torch.manual_seed(0)
HELD_PH = set(world["held_out_phrasings"])
ridx = {r: i for i, r in enumerate(RELS)}
Xp, Yf_, Yl_ = [], [], []
for i, q in enumerate(world["queries"]):
    if q["kind"] == "single" and q["phrasing_idx"] not in HELD_PH:
        Xp.append(Zq[i]); Yf_.append(ridx[q["relation"]])
        Yl_.append(ridx[q["relation"]])
for i, h in enumerate(hops):
    if h["kind"] not in HOLD:
        r1, r2 = h["chain"]
        Xp.append(Zh[i]); Yf_.append(ridx[r1]); Yl_.append(ridx[r2])
Xp_t = torch.tensor(np.stack(Xp))
heads = {}
for slot, lab in (("first", Yf_), ("last", Yl_)):
    hd = nn.Sequential(nn.Linear(1024, 256), nn.GELU(),
                       nn.Linear(256, len(RELS)))
    opt = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    ce = nn.CrossEntropyLoss()
    Y = torch.tensor(lab)
    for _ in range(40):
        for b in torch.randperm(len(Xp_t)).split(512):
            opt.zero_grad(); ce(hd(Xp_t[b]), Y[b]).backward(); opt.step()
    heads[slot] = hd
    hd.eval()

with torch.no_grad():
    LF = torch.log_softmax(heads["first"](torch.tensor(Zh)), -1).numpy()
    LL = torch.log_softmax(heads["last"](torch.tensor(Zh)), -1).numpy()
_pos = {}


def pos_score(z, r1, r2, _cache={}):
    raise NotImplementedError  # scored by index below, not by embedding


def order_acc_pos(idxs):
    ok = 0
    n = 0
    for i in idxs:
        r1, r2 = hops[i]["chain"]
        if r1 == r2:
            continue
        n += 1
        f = LF[i][ridx[r1]] + LL[i][ridx[r2]]
        b = LF[i][ridx[r2]] + LL[i][ridx[r1]]
        ok += f > b
    return ok / n, n


ah, nh = order_acc_pos(held_i)
as_, _ = order_acc_pos(seen_i)
lo_d, hi_d = wilson_ci(int(ah * nh), nh)
print(f"{'D position-specific heads':34s} {ah:10.3f} {0.0:7.3f} {as_:10.3f}")
print(f"D held-out 95% CI [{lo_d:.3f}, {hi_d:.3f}]")
res_ord["D position-specific heads"] = {
    "held_out": round(ah, 4), "held_out_ties": 0.0, "held_out_n": nh,
    "seen": round(as_, 4), "ci95": [round(lo_d, 4), round(hi_d, 4)]}

out = {
    "manifest": run_manifest(seed=0, config={"grid": [-1.0, 2.0, 61],
                                             "held_out": held_k}),
    "fitted": {"a": A_, "b": B_, "mean_cos_seen": round(best_s, 4),
               "held_out_cos": {k: round(float(comp(A_, B_, *k.split(">"))
                                               @ cent[k]), 4)
                                for k in held_k}},
    "ordering": res_ord,
    "ordering_ci95_C": [round(lo, 4), round(hi, 4)],
    "scope": ("Ordering measured with the relation PAIR given correct, so "
              "this isolates order from recall. Same-relation chains are "
              "excluded — they pose no ordering question. Compositions in "
              "HOLD were never used to fit (a, b)."),
}
(ROOT / "results" / "exp18_compose.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp18_compose.json")
