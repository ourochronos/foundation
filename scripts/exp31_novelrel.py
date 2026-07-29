"""Can the walker walk a relation it has NEVER trained on? (D125)

This is the product claim, end to end: a new relation type arrives, nothing is
reindexed, no head is retrained — is it immediately queryable?

The pieces have been measured separately and never together. D113/D116 showed
relation *identification* transfers from label embeddings to relations absent
at training time. D123 showed *composition* generalises to unseen relation
pairs. But in every walker experiment so far, every relation in the evaluation
was also in training; only the pairings were novel.

**Design.** 12 of 61 relations are held out ENTIRELY: every chain containing
one is excluded from training, at every depth. A held-out relation still has
coordinates, because coordinates come from its LABEL (D113/D116) rather than
from training, so nothing about it needs to be learned at ingest time.

Three evaluation populations, never merged:

  novel relation      — the chain routes through a relation never trained
  unseen instance     — the relation was trained, but this subject-relation
                        instance was held out. This is the honest reference:
                        a novel relation should be compared against a novel
                        *instance*, not against memorised training rows
  trained             — reported only as a ceiling

Controls are mandatory (D123): shuffled relation coordinates and a random
target must both collapse, or the store is doing the work.

Refusal is measured against unanswerable populations graded by break point
(law #7), split by whether the broken chain involves a novel relation —
because refusing correctly on a relation you have never seen is a strictly
harder ask than refusing on a familiar one.

Usage: .venv/bin/python scripts/exp31_novelrel.py
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

SEED, MIN_GAIN, THR = 0, 0.2, 0.8
N_HOLD_REL, INST_FRAC, CAP_UNANS = 12, 0.20, 2000

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


rng = np.random.default_rng(SEED)
HOLD_R = {RELS[i] for i in sorted(rng.permutation(len(RELS))[:N_HOLD_REL])}
print(f"{len(wiki)} claims, {len(RELS)} relations; "
      f"{len(HOLD_R)} held out ENTIRELY:")
print("  " + ", ".join(sorted(LABEL[r] for r in HOLD_R)))

# ---- enumerate chains, deterministic (law #8) ----
chains = {1: [], 2: [], 3: []}
for s in subjects:
    stack = [({s}, [])]
    while stack:
        nodes, ch = stack.pop()
        if len(ch) >= 3:
            continue
        for r in sorted(options_at(nodes)):
            nx = step(nodes, r)
            if not nx:
                continue
            c2 = ch + [r]
            chains[len(c2)].append({"subject": s, "chain": c2,
                                    "answers": sorted(nx)[:300]})
            stack.append((nx, c2))
for d in chains:
    chains[d].sort(key=lambda a: (a["subject"], ">".join(a["chain"])))


def n_novel(ch):
    return sum(1 for r in ch if r in HOLD_R)


# train = no novel relation anywhere, minus a held-out slice of instances
POPS = collections.defaultdict(list)
rr = np.random.default_rng(SEED + 1)
for d in (1, 2, 3):
    for a in chains[d]:
        nv = n_novel(a["chain"])
        if nv:
            if d <= 2:
                POPS[f"eval_d{d}_novel{nv}"].append(a)
        elif rr.random() < INST_FRAC and d <= 2:
            POPS[f"eval_d{d}_inst"].append(a)
        else:
            POPS[f"train_d{d}"].append(a)
for k in sorted(POPS):
    print(f"  {k:18s} {len(POPS[k]):6d} chains, "
          f"{len({tuple(a['chain']) for a in POPS[k]}):4d} shapes")

# ---- unanswerable, split by whether a novel relation is involved ----
unans = collections.defaultdict(list)
for s in subjects:
    for r1 in sorted(avail[s]):
        m1 = step({s}, r1)
        if not m1:
            continue
        for r2 in RELS:
            if step(m1, r2):
                continue
            key = ("unans_novel" if (r1 in HOLD_R or r2 in HOLD_R)
                   else "unans_trained")
            unans[key].append({"subject": s, "chain": [r1, r2],
                               "answers": []})
for k in sorted(unans):
    unans[k].sort(key=lambda a: (a["subject"], ">".join(a["chain"])))
    if len(unans[k]) > CAP_UNANS:
        unans[k] = [unans[k][i] for i in
                    sorted(rng.choice(len(unans[k]), CAP_UNANS,
                                      replace=False))]
    print(f"  {k:18s} {len(unans[k]):6d}")


def text_of(s, chain):
    np_ = s
    for r in chain[:-1]:
        np_ = f"the {LABEL[r]} of {np_}"
    return f"What is the {LABEL[chain[-1]]} of {np_}?"


BAG = dict(POPS)
BAG.update(unans)
ORDER = sorted(BAG)
texts, index = [], {}
for key in ORDER:
    index[key] = (len(texts), len(texts) + len(BAG[key]))
    texts += [text_of(a["subject"], a["chain"]) for a in BAG[key]]
cache = ROOT / "results" / "exp31_emb.npz"
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    assert list(z["texts"]) == texts, "cache misaligned; delete it"
    Z, Zl = z["Z"], z["Zl"]
else:
    Z = P.unit(P.embed_texts(texts))
    Zl = P.unit(P.embed_texts([LABEL[r] for r in RELS]))
    np.savez(cache, Z=Z, Zl=Zl, texts=np.array(texts))
RC = {r: Zl[i] for i, r in enumerate(RELS)}
print(f"\n{len(texts)} questions embedded; example (novel relation): "
      f"{texts[index['eval_d1_novel1'][0]]!r}", flush=True)


def emb(key):
    a, b = index[key]
    return Z[a:b]


import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

Xs, Ys = [], []
for key in ("train_d1", "train_d2", "train_d3"):
    E = emb(key)
    for j, a in enumerate(BAG[key]):
        Xs.append(E[j])
        Ys.append(sum(RC[r] for r in a["chain"]))
X, Y = torch.tensor(np.stack(Xs)), torch.tensor(np.stack(Ys))
torch.manual_seed(SEED)
head = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, 1024))
opt = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-4)
for _ in range(40):
    for b in torch.randperm(len(X)).split(512):
        opt.zero_grad()
        ((head(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
        opt.step()
head.eval()
print(f"head trained on {len(Xs)} chains — none containing any of the "
      f"{len(HOLD_R)} held-out relations", flush=True)

RC_SHUF = {r: RC[t] for r, t in
           zip(RELS, [RELS[i] for i in
                      np.random.default_rng(7).permutation(len(RELS))])}


def run(key, max_steps, answerable, mode="real"):
    rows, E = BAG[key], emb(key)
    with torch.no_grad():
        tgt = head(torch.tensor(E)).numpy()
    rc = RC_SHUF if mode == "shuffled" else RC
    g = np.random.default_rng(11)
    c = collections.Counter()
    exact = 0
    for j, a in enumerate(rows):
        t = tgt[j]
        if mode == "random":
            v = g.normal(size=1024).astype(np.float32)
            t = v / np.linalg.norm(v) * float(np.linalg.norm(tgt[j]))
        resid, frontier, path = t.copy(), {a["subject"]}, []
        for _ in range(max_steps):
            opts = options_at(frontier)
            best, bg = None, MIN_GAIN
            for r in opts:
                gg = float(resid @ rc[r])
                if gg > bg:
                    best, bg = r, gg
            if best is None:
                break
            nxt = step(frontier, best)
            if not nxt:
                break
            frontier, path = nxt, path + [best]
            resid = resid - rc[best]
        rn = float(np.linalg.norm(t - sum((rc[r] for r in path),
                                          np.zeros(1024, np.float32))))
        if not path or not frontier or rn > THR:
            c["abstain"] += 1
            continue
        if answerable:
            exact += path == a["chain"]
            c["correct" if set(frontier) & set(a["answers"]) else "wrong"] += 1
        else:
            c["wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: round(c[k] / n, 4) for k in ("correct", "wrong", "abstain")} | {
        "exact_chain": round(exact / n, 4), "n": n}


print("\n=== THE PRODUCT CLAIM: relations never trained on ===")
print(f"{'population':20s} {'correct':>8} {'wrong':>7} {'abstain':>8} "
      f"{'exact':>7} {'n':>7}")
res = {}
for key, mx in (("eval_d1_novel1", 2), ("eval_d1_inst", 2),
                ("eval_d2_novel1", 3), ("eval_d2_novel2", 3),
                ("eval_d2_inst", 3)):
    if key not in BAG or not BAG[key]:
        continue
    r = run(key, mx, True)
    res[key] = r
    print(f"{key:20s} {r['correct']:8.3f} {r['wrong']:7.3f} "
          f"{r['abstain']:8.3f} {r['exact_chain']:7.3f} {r['n']:7d}")

print("\nrefusal (unanswerable), split by whether a novel relation is involved")
for key in ("unans_novel", "unans_trained"):
    r = run(key, 3, False)
    res[key] = r
    print(f"{key:20s} refused {r['abstain']:.3f}  answered {r['wrong']:.3f}  "
          f"(n={r['n']})")

print("\ncontrols on the novel-relation populations")
print(f"{'population':20s} {'real':>8} {'shuffled':>10} {'random':>8}")
ctrl = {}
for key, mx in (("eval_d1_novel1", 2), ("eval_d2_novel1", 3)):
    if key not in BAG:
        continue
    sh = run(key, mx, True, "shuffled")["correct"]
    rd = run(key, mx, True, "random")["correct"]
    ctrl[key] = {"real": res[key]["correct"], "shuffled": sh, "random": rd}
    print(f"{key:20s} {res[key]['correct']:8.3f} {sh:10.3f} {rd:8.3f}")

k = "eval_d1_novel1"
lo, hi = wilson_ci(int(res[k]["correct"] * res[k]["n"]), res[k]["n"])
print(f"\nnovel-relation depth-1 correct CI95 [{lo:.3f}, {hi:.3f}]")

out = {
    "manifest": run_manifest(seed=SEED, config={"N_HOLD_REL": N_HOLD_REL,
                                                "INST_FRAC": INST_FRAC,
                                                "THR": THR}),
    "held_out_relations": sorted(LABEL[r] for r in HOLD_R),
    "n_relations": len(RELS), "results": res, "controls": ctrl,
    "novel_d1_ci95": [round(lo, 4), round(hi, 4)],
    "scope": ("12 of 61 relations held out ENTIRELY — every chain containing "
              "one is excluded from training at every depth. Coordinates for "
              "a held-out relation come from its LABEL, so nothing about it "
              "is learned at ingest. The honest reference is 'unseen "
              "instance' (relation trained, this instance held out), not "
              "trained rows. Refusal split by whether the broken chain "
              "involves a novel relation."),
}
(ROOT / "results" / "exp31_novelrel.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp31_novelrel.json")

# ---------------------------------------------------------------------------
# The product claim fails: 0.293 correct / 0.283 wrong on a novel relation
# against 0.967 for a novel INSTANCE of a known one. But the cause is already
# in the decision log. D114 showed that predicting a relation as a point in
# RAW 1024-d memorises perfectly and transfers nothing (0.000 on held-out
# relations), while predicting into a FROZEN ANCHOR BASIS fit on known
# relations transfers (0.264) — "the basis is the mechanism, not the
# bottleneck". The walker's sum head predicts in raw 1024-d. It is in exactly
# the configuration D114 refuted.
#
# So: fit the basis on TRAINED relations only, express every relation as
# coordinates in it (a held-out relation gets coordinates by projection,
# never moving the basis — the append-only property), and have the head
# predict there. Residual arithmetic is unchanged; it just happens in K
# dimensions instead of 1024. K is swept, because D114's knee was fit for 26
# relations and there are 61 here.
# ---------------------------------------------------------------------------
from codec.evals.anchors import fit_anchors                      # noqa: E402

TRAINED_R = [r for r in RELS if r not in HOLD_R]
print(f"\n=== D114's fix applied to the walker: predict into an anchor basis "
      f"fit on the {len(TRAINED_R)} trained relations ===")
print(f"{'K':>4} {'novel d1':>9} {'novel wrong':>12} {'inst d1':>8} "
      f"{'novel d2':>9} {'unans ref':>10}")
basis_res = {}
for K in (8, 16, 24, 32, 48):
    PC = P.unit(fit_anchors(np.stack([RC[r] for r in TRAINED_R]), K,
                            seed=SEED))
    C = {r: P.unit(RC[r] @ PC.T) for r in RELS}
    Xb, Yb = [], []
    for key in ("train_d1", "train_d2", "train_d3"):
        E = emb(key)
        for j, a in enumerate(BAG[key]):
            Xb.append(E[j])
            Yb.append(sum(C[r] for r in a["chain"]))
    Xt, Yt = torch.tensor(np.stack(Xb)), torch.tensor(np.stack(Yb))
    torch.manual_seed(SEED)
    hd = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, K))
    op = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(Xt)).split(512):
            op.zero_grad()
            ((hd(Xt[b]) - Yt[b]) ** 2).sum(-1).mean().backward()
            op.step()
    hd.eval()

    def run_basis(key, max_steps, answerable):
        rows, E = BAG[key], emb(key)
        with torch.no_grad():
            tgt = hd(torch.tensor(E)).numpy()
        c = collections.Counter()
        for j, a in enumerate(rows):
            resid, frontier, path = tgt[j].copy(), {a["subject"]}, []
            for _ in range(max_steps):
                opts = options_at(frontier)
                best, bg = None, MIN_GAIN
                for r in opts:
                    gg = float(resid @ C[r])
                    if gg > bg:
                        best, bg = r, gg
                if best is None:
                    break
                nxt = step(frontier, best)
                if not nxt:
                    break
                frontier, path = nxt, path + [best]
                resid = resid - C[best]
            rn = float(np.linalg.norm(tgt[j] - sum((C[r] for r in path),
                                                   np.zeros(K, np.float32))))
            if not path or not frontier or rn > THR:
                c["abstain"] += 1
            elif answerable:
                c["correct" if set(frontier) & set(a["answers"])
                  else "wrong"] += 1
            else:
                c["wrong"] += 1
        n = max(sum(c.values()), 1)
        return {k: c[k] / n for k in ("correct", "wrong", "abstain")}

    n1 = run_basis("eval_d1_novel1", 2, True)
    i1 = run_basis("eval_d1_inst", 2, True)
    n2 = run_basis("eval_d2_novel1", 3, True)
    ur = run_basis("unans_novel", 3, False)
    basis_res[K] = {"novel_d1": n1, "inst_d1": i1, "novel_d2": n2,
                    "unans_novel_refused": ur["abstain"]}
    print(f"{K:4d} {n1['correct']:9.3f} {n1['wrong']:12.3f} "
          f"{i1['correct']:8.3f} {n2['correct']:9.3f} {ur['abstain']:10.3f}",
          flush=True)

print(f"\nraw 1024-d baseline (above): novel d1 "
      f"{res['eval_d1_novel1']['correct']:.3f} correct / "
      f"{res['eval_d1_novel1']['wrong']:.3f} wrong, inst d1 "
      f"{res['eval_d1_inst']['correct']:.3f}")
out["anchor_basis_fix"] = {str(k): v for k, v in basis_res.items()}
out["raw_baseline"] = {"novel_d1": res["eval_d1_novel1"],
                       "inst_d1": res["eval_d1_inst"]}
(ROOT / "results" / "exp31_novelrel.json").write_text(json.dumps(out, indent=1))
print("[done] anchor-basis sweep appended")

# ---------------------------------------------------------------------------
# The basis fix lifts novel-relation answering 0.293 -> 0.784, but refusal on
# novel relations appears to fall (0.751 -> 0.412). Before attributing that to
# the method: THR=0.8 was calibrated on residual norms in 1024-d. Residuals in
# K-d are not the same scale, so the drop may be an uncalibrated threshold
# rather than real degradation. Sweeping THR in the basis space settles it —
# and per audit law #6 the sweep is read on populations that exhibit the
# failure, with the novel-relation populations reported afterwards.
# ---------------------------------------------------------------------------
K = 48
PC = P.unit(fit_anchors(np.stack([RC[r] for r in TRAINED_R]), K, seed=SEED))
C = {r: P.unit(RC[r] @ PC.T) for r in RELS}
Xb, Yb = [], []
for key in ("train_d1", "train_d2", "train_d3"):
    E = emb(key)
    for j, a in enumerate(BAG[key]):
        Xb.append(E[j])
        Yb.append(sum(C[r] for r in a["chain"]))
Xt, Yt = torch.tensor(np.stack(Xb)), torch.tensor(np.stack(Yb))
torch.manual_seed(SEED)
hd = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, K))
op = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
for _ in range(40):
    for b in torch.randperm(len(Xt)).split(512):
        op.zero_grad()
        ((hd(Xt[b]) - Yt[b]) ** 2).sum(-1).mean().backward()
        op.step()
hd.eval()


def run_k(key, max_steps, answerable, thr):
    rows, E = BAG[key], emb(key)
    with torch.no_grad():
        tgt = hd(torch.tensor(E)).numpy()
    c = collections.Counter()
    for j, a in enumerate(rows):
        resid, frontier, path = tgt[j].copy(), {a["subject"]}, []
        for _ in range(max_steps):
            opts = options_at(frontier)
            best, bg = None, MIN_GAIN
            for r in opts:
                gg = float(resid @ C[r])
                if gg > bg:
                    best, bg = r, gg
            if best is None:
                break
            nxt = step(frontier, best)
            if not nxt:
                break
            frontier, path = nxt, path + [best]
            resid = resid - C[best]
        rn = float(np.linalg.norm(tgt[j] - sum((C[r] for r in path),
                                               np.zeros(K, np.float32))))
        if not path or not frontier or rn > thr:
            c["abstain"] += 1
        elif answerable:
            c["correct" if set(frontier) & set(a["answers"]) else "wrong"] += 1
        else:
            c["wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: c[k] / n for k in ("correct", "wrong", "abstain")}


print(f"\n=== threshold re-calibration in the K={K} basis ===")
print(f"{'THR':>5} | {'train d1':>9} {'train d2':>9} {'unans trained':>14} "
      f"| {'novel d1':>9} {'novel wrong':>12} {'unans novel':>12}")
tsw = {}
for t in (0.2, 0.3, 0.4, 0.5, 0.6, 0.8):
    c1 = run_k("train_d1", 2, True, t)
    c2 = run_k("train_d2", 3, True, t)
    ut = run_k("unans_trained", 3, False, t)
    n1 = run_k("eval_d1_novel1", 2, True, t)
    un = run_k("unans_novel", 3, False, t)
    tsw[t] = {"train_d1": c1["correct"], "train_d2": c2["correct"],
              "unans_trained_refused": ut["abstain"],
              "novel_d1": n1["correct"], "novel_d1_wrong": n1["wrong"],
              "unans_novel_refused": un["abstain"]}
    print(f"{t:5.2f} | {c1['correct']:9.3f} {c2['correct']:9.3f} "
          f"{ut['abstain']:14.3f} | {n1['correct']:9.3f} {n1['wrong']:12.3f} "
          f"{un['abstain']:12.3f}", flush=True)

# calibrate on TRAINED populations only (novel ones never influence it)
BT = max(tsw, key=lambda t: min(tsw[t]["train_d1"], tsw[t]["train_d2"],
                                tsw[t]["unans_trained_refused"]))
V = tsw[BT]
print(f"\nselected THR={BT} on trained populations only "
      f"(worst = {min(V['train_d1'], V['train_d2'], V['unans_trained_refused']):.3f})")
print(f"  NOVEL relations at that threshold: correct {V['novel_d1']:.3f}  "
      f"wrong {V['novel_d1_wrong']:.3f}  unanswerable refused "
      f"{V['unans_novel_refused']:.3f}")
print(f"  raw-1024d baseline:                correct "
      f"{res['eval_d1_novel1']['correct']:.3f}  wrong "
      f"{res['eval_d1_novel1']['wrong']:.3f}  unanswerable refused "
      f"{res['unans_novel']['abstain']:.3f}")
out["basis_threshold_sweep"] = {str(k): v for k, v in tsw.items()}
out["basis_selected_thr"] = BT
(ROOT / "results" / "exp31_novelrel.json").write_text(json.dumps(out, indent=1))
print("[done] threshold re-calibration appended")
