"""Does D116's alias-diverse vocabulary pretraining fix D127's brittleness? (D128)

D127 found the dominant failure mode: an unseen ALIAS for a KNOWN relation
collapses the walker from 0.868 to 0.149, while composition costs only 0.026.
Every experiment from D117 onward measured composition and depth while this
sat untested.

The fix has existed since D116 and was never connected. D116 trained a
relation head on 800 domain-selected Wikidata properties with three aliases
each and reached 0.636 end-to-end precision on relations never seen at all.
That is exactly alias-diversity pretraining — it teaches the general map
"some phrasing of a relation" -> "that relation's coordinate", over thousands
of phrasings, instead of the handful the corpus happens to supply.

**Design**: identical to D127 — coordinates from labels, questions from
aliases, evaluation aliases held out — with one change. The head additionally
trains on synthetic depth-1 questions built from **vocabulary** relations
(never the corpus's own), with filler subjects, selected by domain per D116
(nearest the corpus relations). Nothing about the corpus evaluation changes,
so the difference is attributable to the pretraining alone.

The load-bearing cell is `xcell_trainpair_evalalias`: trained pairs rendered
in held-out aliases, which isolates phrasing from composition.

Usage: .venv/bin/python scripts/exp34_aliaspretrain.py
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

SEED, MIN_GAIN, HOLD_FRAC = 0, 0.2, 0.34
CAP = {1: 6000, 2: 7000, "unans": 2000}
N_VOCAB, N_VOCAB_ALIAS = 800, 4

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
    if lab and len(al) >= 3:
        LABEL[p], ALIAS[p] = lab, al
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


chains = {1: [], 2: []}
for s in subjects:
    for r1 in sorted(avail[s]):
        m1 = step({s}, r1)
        if not m1:
            continue
        chains[1].append({"subject": s, "chain": [r1],
                          "answers": sorted(m1)[:300]})
        for r2 in sorted(options_at(m1)):
            m2 = step(m1, r2)
            if m2:
                chains[2].append({"subject": s, "chain": [r1, r2],
                                  "answers": sorted(m2)[:300]})
for d in chains:
    chains[d].sort(key=lambda a: (a["subject"], ">".join(a["chain"])))

all_pairs = sorted({(a["chain"][0], a["chain"][1]) for a in chains[2]})
rng = np.random.default_rng(SEED)
HOLD_P = {all_pairs[i] for i in
          list(rng.permutation(len(all_pairs)))[: int(HOLD_FRAC
                                                      * len(all_pairs))]}
BAG = {"train_d1": chains[1]}
for a in chains[2]:
    key = ("train_d2" if (a["chain"][0], a["chain"][1]) not in HOLD_P
           else "eval_d2_clean")
    BAG.setdefault(key, []).append(a)
for k in list(BAG):
    cap = CAP[int(k[-1])] if k.startswith("train") else CAP[2]
    if len(BAG[k]) > cap:
        BAG[k] = [BAG[k][i] for i in sorted(rng.choice(len(BAG[k]), cap,
                                                       replace=False))]
unans = []
for s in subjects:
    for r1 in sorted(avail[s]):
        m1 = step({s}, r1)
        if not m1:
            continue
        for r2 in RELS:
            if not step(m1, r2):
                unans.append({"subject": s, "chain": [r1, r2], "answers": []})
unans.sort(key=lambda a: (a["subject"], ">".join(a["chain"])))
if len(unans) > CAP["unans"]:
    unans = [unans[i] for i in sorted(rng.choice(len(unans), CAP["unans"],
                                                 replace=False))]
BAG["unans"] = unans

TRAIN_AL = {r: ALIAS[r][:2] for r in RELS}
EVAL_AL = {r: ALIAS[r][2:] or ALIAS[r][1:2] for r in RELS}


def word_for(r, mode, i):
    pool = TRAIN_AL[r] if mode == "train" else EVAL_AL[r]
    return pool[i % len(pool)]


def text_of(a, mode, i):
    np_ = a["subject"]
    for r in a["chain"][:-1]:
        np_ = f"the {word_for(r, mode, i)} of {np_}"
    return f"What is the {word_for(a['chain'][-1], mode, i)} of {np_}?"


BAG["xcell_trainpair_evalalias"] = BAG["train_d2"]
BAG["xcell_evalpair_trainalias"] = BAG["eval_d2_clean"]
RENDER = {"xcell_trainpair_evalalias": "eval",
          "xcell_evalpair_trainalias": "train"}
ORDER = sorted(BAG)
texts, index = [], {}
for key in ORDER:
    index[key] = (len(texts), len(texts) + len(BAG[key]))
    mode = RENDER.get(key, "train" if key.startswith("train") else "eval")
    texts += [text_of(a, mode, i) for i, a in enumerate(BAG[key])]
z = np.load(ROOT / "results" / "exp33_emb.npz", allow_pickle=True)
assert list(z["texts"]) == texts, "populations drifted from D127"
Z, Zl = z["Z"], z["Zl"]
RC = {r: Zl[i] for i, r in enumerate(RELS)}
print(f"D127 populations reproduced ({len(texts)} questions, "
      f"{len(RELS)} relations)", flush=True)


def emb(key):
    a, b = index[key]
    return Z[a:b]


# ---- vocabulary pretraining set: D116's recipe, corpus relations excluded --
OURS = set(RELS)
known_c = P.unit(np.stack([RC[r] for r in RELS]).mean(0))
cand = [p for p, d in props.items()
        if p not in OURS and len(d.get("aliases", ())) >= N_VOCAB_ALIAS
        and len(d["label"]) > 2]
vc = ROOT / "results" / "exp34_vocab_emb.npz"
if vc.exists():
    d = np.load(vc, allow_pickle=True)
    Zv_lab, v_order = d["Zv_lab"], list(d["v_order"])
else:
    v_order = sorted(cand)
    Zv_lab = P.unit(P.embed_texts([props[p]["label"] for p in v_order]))
    np.savez(vc, Zv_lab=Zv_lab, v_order=np.array(v_order))
VL = {p: Zv_lab[i] for i, p in enumerate(v_order)}
sim = np.array([float(VL[p] @ known_c) for p in v_order])
near = [v_order[i] for i in np.argsort(-sim)][:N_VOCAB]
print(f"{len(cand)} candidate vocabulary relations; {N_VOCAB} selected by "
      f"domain (D116). nearest: "
      f"{', '.join(props[p]['label'] for p in near[:5])}")

fill = [subjects[i] for i in
        np.random.default_rng(1).choice(len(subjects), 400, replace=False)]
vq = []
for j, p in enumerate(near):
    for ai, a in enumerate(props[p]["aliases"][:N_VOCAB_ALIAS]):
        vq.append({"pid": p, "text": f"What is the {a} of "
                                     f"{fill[(j * 7 + ai * 3) % len(fill)]}?"})
vqc = ROOT / "results" / "exp34_vq_emb.npz"
if vqc.exists():
    d = np.load(vqc, allow_pickle=True)
    assert list(d["texts"]) == [q["text"] for q in vq], "vocab set drifted"
    Zvq = d["Zvq"]
else:
    Zvq = P.unit(P.embed_texts([q["text"] for q in vq]))
    np.savez(vqc, Zvq=Zvq, texts=np.array([q["text"] for q in vq]))
print(f"{len(vq)} synthetic vocabulary questions "
      f"({N_VOCAB_ALIAS} aliases x {N_VOCAB} relations)", flush=True)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402


def train_head(with_vocab):
    Xs, Ys = [], []
    for key in ("train_d1", "train_d2"):
        E = emb(key)
        for j, a in enumerate(BAG[key]):
            Xs.append(E[j])
            Ys.append(sum(RC[r] for r in a["chain"]))
    if with_vocab:
        for j, q in enumerate(vq):
            Xs.append(Zvq[j])
            Ys.append(VL[q["pid"]])
    X, Y = torch.tensor(np.stack(Xs)), torch.tensor(np.stack(Ys))
    torch.manual_seed(SEED)
    hd = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, 1024))
    op = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(X)).split(512):
            op.zero_grad()
            ((hd(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
            op.step()
    hd.eval()
    return hd, len(Xs)


def run(hd, key, max_steps, answerable, thr):
    rows, E = BAG[key], emb(key)
    with torch.no_grad():
        tgt = hd(torch.tensor(E)).numpy()
    c = collections.Counter()
    for j, a in enumerate(rows):
        resid, frontier, path = tgt[j].copy(), {a["subject"]}, []
        for _ in range(max_steps):
            best, bg = None, MIN_GAIN
            for r in options_at(frontier):
                g = float(resid @ RC[r])
                if g > bg:
                    best, bg = r, g
            if best is None:
                break
            nxt = step(frontier, best)
            if not nxt:
                break
            frontier, path = nxt, path + [best]
            resid = resid - RC[best]
        rn = float(np.linalg.norm(tgt[j] - sum((RC[r] for r in path),
                                               np.zeros(1024, np.float32))))
        if not path or not frontier or rn > thr:
            c["abstain"] += 1
        elif answerable:
            c["correct" if set(frontier) & set(a["answers"]) else "wrong"] += 1
        else:
            c["wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: round(c[k] / n, 4) for k in
            ("correct", "wrong", "abstain")} | {"n": n}


res = {}
for tag, wv in (("no pretraining (D127)", False),
                ("+ vocabulary pretraining", True)):
    hd, n = train_head(wv)
    best, bw = None, -1
    for t in (0.3, 0.4, 0.5, 0.6, 0.8, 1.0):
        v = [run(hd, "train_d1", 2, True, t)["correct"],
             run(hd, "train_d2", 3, True, t)["correct"],
             run(hd, "unans", 3, False, t)["abstain"]]
        if min(v) > bw:
            bw, best = min(v), t
    r = {k: run(hd, k, 3 if "d2" in k or "xcell" in k else 2,
                k != "unans", best)
         for k in ("train_d2", "xcell_trainpair_evalalias",
                   "xcell_evalpair_trainalias", "eval_d2_clean", "unans")}
    res[tag] = {"thr": best, "n_train": n, **r}
    print(f"\n=== {tag}  (thr {best}, {n} training rows) ===")
    for k, v in r.items():
        print(f"  {k:28s} correct {v['correct']:.3f}  wrong {v['wrong']:.3f}"
              f"  abstain {v['abstain']:.3f}")

a = res["no pretraining (D127)"]
b = res["+ vocabulary pretraining"]
print("\n=== the load-bearing cell: trained pairs, HELD-OUT aliases ===")
print(f"  without vocabulary pretraining: "
      f"{a['xcell_trainpair_evalalias']['correct']:.3f}")
print(f"  with    vocabulary pretraining: "
      f"{b['xcell_trainpair_evalalias']['correct']:.3f}")
delta = (b["xcell_trainpair_evalalias"]["correct"]
         - a["xcell_trainpair_evalalias"]["correct"])
print(f"  delta {delta:+.3f}   (D127 measured the phrasing cost at -0.719)")
print(f"  known-phrasing control (train_d2): "
      f"{a['train_d2']['correct']:.3f} -> {b['train_d2']['correct']:.3f}")

out = {
    "manifest": run_manifest(seed=SEED, config={"N_VOCAB": N_VOCAB,
                                                "N_VOCAB_ALIAS":
                                                N_VOCAB_ALIAS}),
    "n_relations": len(RELS), "results": res,
    "phrasing_delta": round(delta, 4),
    "scope": ("Identical to D127 except the head additionally trains on "
              "synthetic depth-1 questions from 800 domain-selected "
              "Wikidata VOCABULARY relations (never the corpus's own) with "
              "filler subjects — D116's recipe. Nothing about the corpus "
              "evaluation changes, so the difference is attributable to the "
              "pretraining. The load-bearing cell is trained pairs rendered "
              "in held-out aliases, which isolates phrasing."),
}
(ROOT / "results" / "exp34_aliaspretrain.json").write_text(json.dumps(out,
                                                                      indent=1))
print("\n[done] results/exp34_aliaspretrain.json")

# ---------------------------------------------------------------------------
# Vocabulary pretraining alone does nothing (0.149 -> 0.146). But D116, where
# it worked, predicted into an ANCHOR BASIS — and D114/D125 both showed that
# raw 1024-d is precisely the configuration that memorises and does not
# generalise. So pretraining may have been the right ingredient in the wrong
# representation. This completes the 2x2: {raw, basis} x {no pretrain,
# pretrain}, scored on the phrasing cell.
#
# The basis is fit on vocabulary + corpus LABELS (unsupervised, no questions,
# no held-out information), so it is available at ingest time exactly as D125
# required.
# ---------------------------------------------------------------------------
from codec.evals.anchors import fit_anchors                      # noqa: E402

K = 48
pool = np.concatenate([np.stack([VL[p] for p in near]),
                       np.stack([RC[r] for r in RELS])])
PC = P.unit(fit_anchors(pool, K, seed=SEED))
C_corp = {r: P.unit(RC[r] @ PC.T) for r in RELS}
C_vocab = {p: P.unit(VL[p] @ PC.T) for p in near}
print(f"\nbasis fit on {len(pool)} relation labels "
      f"({len(near)} vocabulary + {len(RELS)} corpus), K={K}")


def train_basis(with_vocab):
    Xs, Ys = [], []
    for key in ("train_d1", "train_d2"):
        E = emb(key)
        for j, a in enumerate(BAG[key]):
            Xs.append(E[j])
            Ys.append(sum(C_corp[r] for r in a["chain"]))
    if with_vocab:
        for j, q in enumerate(vq):
            Xs.append(Zvq[j])
            Ys.append(C_vocab[q["pid"]])
    X, Y = torch.tensor(np.stack(Xs)), torch.tensor(np.stack(Ys))
    torch.manual_seed(SEED)
    hd = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, K))
    op = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(X)).split(512):
            op.zero_grad()
            ((hd(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
            op.step()
    hd.eval()
    return hd


def run_basis(hd, key, max_steps, answerable, thr):
    rows, E = BAG[key], emb(key)
    with torch.no_grad():
        tgt = hd(torch.tensor(E)).numpy()
    c = collections.Counter()
    for j, a in enumerate(rows):
        resid, frontier, path = tgt[j].copy(), {a["subject"]}, []
        for _ in range(max_steps):
            best, bg = None, MIN_GAIN
            for r in options_at(frontier):
                g = float(resid @ C_corp[r])
                if g > bg:
                    best, bg = r, g
            if best is None:
                break
            nxt = step(frontier, best)
            if not nxt:
                break
            frontier, path = nxt, path + [best]
            resid = resid - C_corp[best]
        rn = float(np.linalg.norm(tgt[j] - sum((C_corp[r] for r in path),
                                               np.zeros(K, np.float32))))
        if not path or not frontier or rn > thr:
            c["abstain"] += 1
        elif answerable:
            c["correct" if set(frontier) & set(a["answers"]) else "wrong"] += 1
        else:
            c["wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: round(c[k] / n, 4) for k in
            ("correct", "wrong", "abstain")} | {"n": n}


print("\n=== 2x2: representation x vocabulary pretraining ===")
print(f"{'condition':32s} {'known phr':>10} {'HELD-OUT phr':>13} "
      f"{'wrong':>7} {'unans ref':>10}")
grid = {}
for wv in (False, True):
    hd = train_basis(wv)
    best, bw = None, -1
    for t in (0.2, 0.3, 0.4, 0.5, 0.6, 0.8):
        v = [run_basis(hd, "train_d1", 2, True, t)["correct"],
             run_basis(hd, "train_d2", 3, True, t)["correct"],
             run_basis(hd, "unans", 3, False, t)["abstain"]]
        if min(v) > bw:
            bw, best = min(v), t
    kn = run_basis(hd, "train_d2", 3, True, best)
    ho = run_basis(hd, "xcell_trainpair_evalalias", 3, True, best)
    un = run_basis(hd, "unans", 3, False, best)
    tag = f"basis K={K}{' + vocab' if wv else ''}"
    grid[tag] = {"thr": best, "known": kn, "heldout_phrasing": ho,
                 "unans_refused": un["abstain"]}
    print(f"{tag:32s} {kn['correct']:10.3f} {ho['correct']:13.3f} "
          f"{ho['wrong']:7.3f} {un['abstain']:10.3f}", flush=True)
for tag, r in (("raw (D127)", a), ("raw + vocab", b)):
    print(f"{tag:32s} {r['train_d2']['correct']:10.3f} "
          f"{r['xcell_trainpair_evalalias']['correct']:13.3f} "
          f"{r['xcell_trainpair_evalalias']['wrong']:7.3f} "
          f"{r['unans']['abstain']:10.3f}")

out["basis_2x2"] = grid
(ROOT / "results" / "exp34_aliaspretrain.json").write_text(json.dumps(out,
                                                                      indent=1))
print("[done] 2x2 appended")
