"""Does a basis work in proportion to how well its partition matches the task?

The superposition account: an embedding space holds many overlapping
categorizations at once, because aligning to any one of them would cap what it
can express. On that view a basis is useful **to the extent it extracts the
partition the task actually needs** — not because it came from an adjacent
ontological layer (exp57: refuted), not because it is orthogonal (exp56: r≈0),
and not because it avoids redundancy with the encoder (exp58: r≈0).

Everything measured so far is monotone in task-partition alignment:

    which relation is asked (the task partition)   0.453
    label similarity (an indirect proxy for it)    0.425
    what kind of thing it connects (another one)   0.309
    no partition at all (random orthonormal)       0.287
    a transformation rather than a partition       0.236

That is suggestive and it is not a test, because every one of those also
changes the *method*. This changes **only the partition**.

**Design.** Hold the method fixed — between-class scatter, same K, same head,
same everything — and corrupt the class assignment by a fraction `p`. At p=0
the classes are the true relations; at p=1 each question is assigned a random
relation. Class count and approximate class sizes are preserved throughout, so
rank and granularity do not move; only alignment does. This is a permutation
control with a dose-response curve rather than a single shuffled point.

**Only the BASIS sees the corrupted partition.** Coordinates are still
`unit(label @ PC.T)` from true labels, the head still trains on true targets,
and evaluation is still true-relation identification. The corruption isolates
one thing: whether the directions the basis spans are the ones that separate
the classes the task cares about.

**Registered prediction.** Monotone decline from ≈0.45 at p=0 toward the
random-orthonormal band (≈0.17–0.29 at K=32) by p=1, with most of the loss in
the first half of the corruption range. A FLAT curve falsifies the account —
it would mean the basis works for a reason unrelated to which partition it
separates, and the ordering in the table above is coincidence.

Usage: .venv/bin/python scripts/exp59_partition_alignment.py [m3|gemma|both]
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

from codec.manifest import run_manifest                          # noqa: E402
from foundation.kb import KB                                     # noqa: E402

SEED, MIN_ALIAS, N_SUBJ, N_HOLD_REL = 0, 6, 40, 12
TRAIN_ALIASES, N_EVAL_ALIAS = 2, 2
K_MAIN = 32
PS = (0.0, 0.125, 0.25, 0.5, 0.75, 1.0)
N_SEEDS = 3
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

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402


def unit(a):
    return a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9)


def between_dirs(Z, assign, K):
    """Top-K directions separating the means of the given class assignment."""
    g = collections.defaultdict(list)
    for i, c in enumerate(assign):
        g[c].append(i)
    mus, ns = [], []
    for c in sorted(g):
        mus.append(Z[g[c]].mean(0))
        ns.append(len(g[c]))
    if len(mus) < 2 or K > len(mus) - 1:
        return None
    M = np.stack(mus)
    mu = np.average(M, axis=0, weights=ns)
    D = (M - mu) * np.sqrt(np.array(ns))[:, None]
    return unit(np.linalg.svd(D, full_matrices=False)[2][:K])


def identify(Z, C_all, dim):
    M = np.stack([C_all[r] for r in RELS])
    tr = [i for i, x in enumerate(rows)
          if x["rel"] in TRAINED_R and x["ai"] < TRAIN_ALIASES]
    ev_t = [i for i, x in enumerate(rows)
            if x["rel"] in TRAINED_R and x["ai"] >= MIN_ALIAS - N_EVAL_ALIAS]
    ev_n = [i for i, x in enumerate(rows) if x["rel"] in HELD_R]
    X = torch.tensor(Z[tr])
    # targets are the TRUE relation's coordinate — the corruption never
    # touches the task, only the directions the basis spans
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
            pr = unit(hd(torch.tensor(Z[idxs])).numpy())
        pred = (pr @ M.T).argmax(1)
        return float(np.mean([RELS[int(j)] == rows[i]["rel"]
                              for j, i in zip(pred, idxs)]))
    return round(acc(ev_t), 4), round(acc(ev_n), 4)


ARMS = (["m3"] if WHICH in ("m3", "both") else []) + \
       (["gemma_symmetric"] if WHICH in ("gemma", "both") else [])
OUT = {}
for arm in ARMS:
    z = np.load(ROOT / "results" / f"exp56_{arm}_emb.npz", allow_pickle=True)
    assert list(z["qtext"]) == QTEXT and list(z["ents"]) == ENTS, \
        f"population drift vs exp56 for {arm}"
    Zq, Zl = z["Zq"], z["Zl"]
    RAW = {r: Zl[i] for i, r in enumerate(RELS)}
    tr_idx = [i for i, x in enumerate(rows)
              if x["rel"] in TRAINED_R and x["ai"] < TRAIN_ALIASES]
    true_assign = [rows[i]["rel"] for i in tr_idx]
    Ztr = Zq[tr_idx]
    print(f"\n=== ARM: {arm} === {len(tr_idx)} training questions over "
          f"{len(TRAINED_R)} classes, K={K_MAIN}", flush=True)

    # control: p=0 must reproduce exp56's lda_between at this K
    prev = json.loads((ROOT / "results"
                       / "exp56_anchor_strategy.json").read_text())
    want = prev["arms"][arm][f"lda_between_K{K_MAIN}"]["novel"]
    PC = between_dirs(Ztr, true_assign, K_MAIN)
    _, n0 = identify(Zq, {r: unit(RAW[r] @ PC.T) for r in RELS}, K_MAIN)
    print(f"  control — p=0.0 reproduces exp56: {n0:.4f} vs {want:.4f}")
    assert abs(n0 - want) < 1e-3, (
        f"p=0 does not reproduce exp56 ({n0} vs {want}); the curve below "
        f"would not be anchored to anything")

    curve = {}
    print(f"  {'corrupt p':>10} {'NOVEL mean':>11} {'sd':>7} {'trained':>8}")
    for p in PS:
        novs, trs = [], []
        seeds = [SEED] if p == 0.0 else list(range(N_SEEDS))
        for s in seeds:
            if p == 0.0:
                assign = true_assign
            else:
                g = np.random.default_rng(1000 + s)
                assign = [(RELS[int(g.integers(len(RELS)))]
                           if g.random() < p else a) for a in true_assign]
            PC = between_dirs(Ztr, assign, K_MAIN)
            if PC is None:
                continue
            t, n = identify(Zq, {r: unit(RAW[r] @ PC.T) for r in RELS},
                            PC.shape[0])
            novs.append(n)
            trs.append(t)
        curve[str(p)] = {"novel_mean": round(float(np.mean(novs)), 4),
                         "novel_sd": round(float(np.std(novs)), 4),
                         "trained_mean": round(float(np.mean(trs)), 4),
                         "n_seeds": len(novs)}
        c = curve[str(p)]
        print(f"  {p:10.3f} {c['novel_mean']:11.4f} {c['novel_sd']:7.4f} "
              f"{c['trained_mean']:8.4f}", flush=True)
    OUT[arm] = curve

print("\n=== does alignment predict transfer? ===")
verdicts = {}
for arm, curve in OUT.items():
    xs = np.array([float(p) for p in curve])
    ys = np.array([curve[p]["novel_mean"] for p in curve])
    r = float(np.corrcoef(xs, ys)[0, 1])
    drop = float(ys[0] - ys[-1])
    floor_sd = curve[str(PS[-1])]["novel_sd"]
    verdicts[arm] = {"corr_p_vs_novel": round(r, 4),
                     "drop_p0_to_p1": round(drop, 4),
                     "floor_sd": floor_sd}
    print(f"  {arm:>18} r={r:+.4f}  drop {ys[0]:.4f} -> {ys[-1]:.4f} "
          f"({drop:+.4f}), floor sd {floor_sd:.4f}")
mr = float(np.mean([v["corr_p_vs_novel"] for v in verdicts.values()]))
md = float(np.mean([v["drop_p0_to_p1"] for v in verdicts.values()]))
if mr < -0.7 and md > 0.10:
    verdict = (f"SUPPORTED — corrupting the partition while holding the "
               f"method fixed costs {md:.4f} of novel transfer (r={mr:+.3f}). "
               f"A basis works in proportion to how well its partition "
               f"matches the task, which is what the superposition account "
               f"predicts and what the ontological accounts did not.")
elif md < 0.05:
    verdict = (f"FALSIFIED — the curve is FLAT ({md:+.4f}). Which partition "
               f"the basis separates does not matter, so the ordering across "
               f"strategies has some other cause and the alignment account "
               f"should be dropped.")
else:
    verdict = (f"PARTIAL — drop {md:+.4f}, r={mr:+.3f}. Alignment matters but "
               f"does not account for the full spread across strategies.")
print(f"\n=== VERDICT ===\n  {verdict}")

out = {"manifest": run_manifest(seed=SEED, config={"K": K_MAIN, "PS": list(PS),
                                                   "N_SEEDS": N_SEEDS}),
       "n_relations": len(RELS), "n_trained": len(TRAINED_R),
       "chance": round(1 / len(RELS), 4),
       "random_orthonormal_reference_K32": {"m3": 0.0064,
                                            "gemma_symmetric": 0.1731},
       "curves": OUT, "verdicts": verdicts, "verdict": verdict,
       "registered_prediction": (
           "monotone decline from ~0.45 at p=0 toward the random-orthonormal "
           "band (~0.17-0.29) by p=1, most of the loss in the first half; a "
           "FLAT curve falsifies the alignment account"),
       "scope": ("Changes ONLY the partition the basis is derived from. "
                 "Method, K, head, targets and evaluation are identical "
                 "across every point: the corrupted assignment is used to "
                 "compute between-class scatter directions and nothing else, "
                 "while coordinates stay unit(label @ PC.T) from true labels "
                 "and the head trains on true targets. Class count and "
                 "approximate class sizes are preserved so rank and "
                 "granularity do not move. p=0 must reproduce exp56's "
                 "lda_between in-run or the script aborts (D158: no pasted "
                 "baselines). Identification level only.")}
(ROOT / "results" / "exp59_partition_alignment.json").write_text(
    json.dumps(out, indent=1))
print("\n[done] results/exp59_partition_alignment.json")
