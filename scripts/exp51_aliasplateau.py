"""Does the head-vs-retrieval gap plateau above zero? (D154, claim 12)

The falsifier two of three adversarial raters named, in their words: *"the
gap could plateau above zero beyond ten aliases, indicating permanent
information loss; the finite shrinking curve cannot exclude that falsifier"*.
It is the right objection. D139 measured 0.229 at 2 aliases closing to 0.042
at 10 and stopped there — with the curve still moving — and D148/D154 then
read "not a permanent loss of information" off a trend that had never been
run to flat. A residual of 0.042 at the largest supply tested is equally
consistent with "converging to zero" and with "converging to 0.04".

**Two arms, because the obvious experiment has a confound.** Only 11 of our
relations carry 20+ aliases, against 34 at 12+, and requiring 4+ subjects
apiece cuts those to **8 and 24**. Sweeping further therefore means shrinking
the relation vocabulary, and identification gets easier as the vocabulary
shrinks — a gap that closes at 20 aliases on 8 relations would be partly the
vocabulary, not the aliases. So:

  * **A (control)**: relations with 12+ aliases, swept 2 -> 10. Reproduces
    D139's population and its curve.
  * **B (extension)**: relations with 20+ aliases, swept 2 -> 18. The same
    relations at every point, so the curve is internally comparable.

Arms are named for their alias threshold, not their relation count: the
`>= 4 subjects` filter moves the count, and a name that asserts a number the
run does not produce is the defect this project has spent three entries
chasing (D153).

Comparing the two arms **at their shared alias counts** is what says whether
B's smaller vocabulary distorts the shape. If A and B agree where they
overlap, B's tail is trustworthy.

**What decides it.** Fit the gap's tail over B's last three points. If the
gap is still falling and the fitted asymptote is within noise of zero, the
claim survives with its falsifier addressed. If it flattens at a positive
value, **claim 12 is wrong as written** and "data-efficiency, not
information loss" becomes "data-efficiency down to a floor of X" — which is
a better claim than the one we have, and the reason the falsifier was worth
running rather than arguing with.

Head config is exp49's winner (contrastive, 1024 hidden, 40 epochs), fixed
across every point so only alias supply varies.

Usage: .venv/bin/python scripts/exp51_aliasplateau.py
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
from foundation.kb import KB                                     # noqa: E402

SEED, N_SUBJ, N_EVAL_ALIAS = 0, 40, 2
OBJECTIVE, HIDDEN, EPOCHS = "contrastive", 1024, 40      # exp49's winner
ARMS = {"A_control_12plus": {"min_alias": 12, "sweep": [2, 4, 6, 8, 10]},
        "B_extended_20plus": {"min_alias": 20,
                             "sweep": [2, 4, 6, 8, 10, 12, 14, 16, 18]}}

sch = {d["pid"]: d for d in
       json.loads((ROOT / "data" / "schema_v0.json").read_text())}
props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
kb = KB(backend="pg", table="poc")
wiki = [c for c in kb.claims
        if not c["page"].startswith(("arxiv:", "hf:", "user"))]

ALIAS, LABEL = {}, {}
for c in wiki:
    p = c["pid"]
    if p in ALIAS:
        continue
    lab = (sch.get(p) or {}).get("label") or (props.get(p) or {}).get("label")
    al = list((sch.get(p) or {}).get("aliases", []))
    al += [a for a in (props.get(p) or {}).get("aliases", []) if a not in al]
    al = [a for a in al if 2 < len(a) < 40]
    if lab:
        LABEL[p], ALIAS[p] = lab, al

gold = collections.defaultdict(set)
for c in wiki:
    gold[(c["subject"], c["pid"])].add(c["object"])
by_rel = collections.defaultdict(list)
for (s, r) in sorted(gold):
    by_rel[r].append(s)
rng = np.random.default_rng(SEED)


def build(min_alias: int, max_needed: int):
    """Deterministic question set: relations with enough aliases, N subjects.

    Sorted everywhere. D120 turned a published conclusion into a withdrawn
    one because set iteration over strings is per-process hash-randomised and
    the rebuilt list silently misaligned with a cached embedding matrix.
    """
    rng = np.random.default_rng(SEED)     # per-arm, so each arm reproduces
    rels = sorted(r for r in sorted(ALIAS)     # alone rather than only in
                  if len(ALIAS[r]) >= min_alias and len(by_rel[r]) >= 4)
    rows = []                                  # the order the arms happen to
    #                                            run in

    for r in rels:
        subs = sorted(by_rel[r])
        if len(subs) > N_SUBJ:
            idx = sorted(rng.choice(len(subs), N_SUBJ, replace=False))
            subs = [subs[i] for i in idx]
        for ai, a in enumerate(ALIAS[r][:max_needed]):
            for s in subs:
                rows.append({"rel": r, "ai": ai,
                             "text": f"What is the {a} of {s}?"})
    return rels, rows


import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402


def train_head(X, Y_IDX, Mt):
    torch.manual_seed(SEED)
    hd = nn.Sequential(nn.Linear(1024, HIDDEN), nn.GELU(),
                       nn.Linear(HIDDEN, 1024))
    op = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(EPOCHS):
        for b in torch.randperm(len(X)).split(512):
            op.zero_grad()
            pr = hd(X[b])
            q = pr / (pr.norm(dim=-1, keepdim=True) + 1e-9)
            nn.functional.cross_entropy((q @ Mt.T) * 20.0,
                                        Y_IDX[b]).backward()
            op.step()
    hd.eval()
    return hd


results = {}
for arm, cfg in ARMS.items():
    max_needed = max(cfg["sweep"]) + N_EVAL_ALIAS
    rels, rows = build(cfg["min_alias"], max_needed)
    texts = [x["text"] for x in rows]
    print(f"\n=== {arm}: {len(rels)} relations, {len(rows)} questions, "
          f"aliases up to {max_needed} ===", flush=True)
    cache = ROOT / "results" / f"exp51_{arm}_emb.npz"
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        assert list(z["texts"]) == texts and list(z["rels"]) == rels, \
            f"cache misaligned for {arm}; delete it"
        Z, Zl = z["Z"], z["Zl"]
    else:
        Z = P.unit(P.embed_texts(texts))
        Zl = P.unit(P.embed_texts([LABEL[r] for r in rels]))
        np.savez(cache, Z=Z, Zl=Zl, texts=np.array(texts),
                 rels=np.array(rels))
    M = np.stack([Zl[i] for i in range(len(rels))])
    ridx = {r: i for i, r in enumerate(rels)}
    Mt = torch.tensor(M)
    # eval on the LAST two aliases, fixed across the sweep, so every point is
    # scored on identical questions and only training supply varies
    EV = [i for i, x in enumerate(rows) if x["ai"] >= max_needed - N_EVAL_ALIAS]
    curve = {}
    for k in cfg["sweep"]:
        TR = [i for i, x in enumerate(rows) if x["ai"] < k]
        X = torch.tensor(Z[TR])
        Y_IDX = torch.tensor([ridx[rows[i]["rel"]] for i in TR])
        hd = train_head(X, Y_IDX, Mt)
        with torch.no_grad():
            pe = hd(torch.tensor(Z[EV])).numpy()
        pe = pe / (np.linalg.norm(pe, axis=1, keepdims=True) + 1e-9)
        pred = (pe @ M.T).argmax(1)
        head = float(np.mean([rels[int(j)] == rows[i]["rel"]
                              for j, i in zip(pred, EV)]))
        nnp = (Z[EV] @ Z[TR].T).argmax(1)
        knn = float(np.mean([rows[TR[int(j)]]["rel"] == rows[i]["rel"]
                             for j, i in zip(nnp, EV)]))
        curve[str(k)] = {"head": round(head, 4), "knn": round(knn, 4),
                         "gap": round(knn - head, 4), "n_train": len(TR)}
        print(f"  {k:2d} aliases  head {head:.4f}  1-NN {knn:.4f}  "
              f"gap {knn - head:+.4f}", flush=True)
    results[arm] = {"n_relations": len(rels), "n_eval": len(EV),
                    "chance": round(1 / len(rels), 4), "curve": curve}

# ---- do the arms agree where they overlap? --------------------------------
A, B = results["A_control_12plus"], results["B_extended_20plus"]
shared = sorted(set(A["curve"]) & set(B["curve"]), key=int)
print(f"\narm agreement at shared alias counts (gap A vs gap B)")
for k in shared:
    print(f"  {k:>2}  A {A['curve'][k]['gap']:+.4f}   "
          f"B {B['curve'][k]['gap']:+.4f}   "
          f"diff {B['curve'][k]['gap'] - A['curve'][k]['gap']:+.4f}")
overlap_diff = float(np.mean([abs(B["curve"][k]["gap"] - A["curve"][k]["gap"])
                              for k in shared]))

# ---- the tail: still falling, or flat above zero? -------------------------
ks = sorted(B["curve"], key=int)
tail_k = [int(k) for k in ks[-3:]]
tail_g = [B["curve"][k]["gap"] for k in ks[-3:]]
slope, intercept = np.polyfit(tail_k, tail_g, 1)
last = B["curve"][ks[-1]]["gap"]
lo, hi = wilson_ci(int(round((1 - last) * B["n_eval"])), B["n_eval"])
noise = (hi - lo) / 2
print(f"\ntail over aliases {tail_k}: gaps {[round(g, 4) for g in tail_g]}")
print(f"  slope {slope:+.5f} per alias, gap at {ks[-1]} aliases {last:+.4f}")
print(f"  half-width of a 95% interval at this n: {noise:.4f}")

if last <= noise:
    verdict = (f"gap at {ks[-1]} aliases ({last:.4f}) is within noise of "
               f"zero — claim 12 SURVIVES its falsifier")
elif slope < -0.002:
    verdict = (f"gap {last:.4f} is still falling ({slope:+.5f}/alias) and has "
               f"NOT plateaued — the falsifier is not yet ruled out and needs "
               f"aliases past {ks[-1]}")
else:
    verdict = (f"gap PLATEAUS at {last:.4f} (slope {slope:+.5f}/alias) — "
               f"claim 12 is WRONG as written; retrieval's advantage has a "
               f"floor, and 'not a permanent loss' must be withdrawn")
print(f"\n=== VERDICT ===\n  {verdict}")

out = {
    "manifest": run_manifest(seed=SEED,
                             config={"objective": OBJECTIVE, "hidden": HIDDEN,
                                     "epochs": EPOCHS, "N_SUBJ": N_SUBJ,
                                     "arms": ARMS}),
    "results": results, "shared_alias_counts": shared,
    "mean_abs_gap_diff_on_overlap": round(overlap_diff, 4),
    "tail_alias_counts": tail_k,
    "tail_gaps": [round(g, 4) for g in tail_g],
    "tail_slope_per_alias": round(float(slope), 5),
    "gap_at_max_alias": last, "noise_half_width": round(noise, 4),
    "verdict": verdict,
    "scope": ("Addresses the falsifier 2 of 3 adversarial raters named for "
              "claim 12 (D154): the alias curve stopped at 10 and could "
              "plateau above zero. Arm B extends to 18 on the 11 relations "
              "carrying 20+ aliases; arm A reproduces D139's 34-relation "
              "population as a control, because identification gets easier "
              "as the vocabulary shrinks and the extension necessarily "
              "shrinks it. The arms are compared at shared alias counts to "
              "show whether B's smaller vocabulary distorts the shape. "
              "Evaluation is on the last two aliases, FIXED across the "
              "sweep, so only training supply varies. Head is exp49's "
              "winning configuration, frozen."),
}
(ROOT / "results" / "exp51_aliasplateau.json").write_text(
    json.dumps(out, indent=1))
print("\n[done] results/exp51_aliasplateau.json")
