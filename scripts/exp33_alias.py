"""Does the walker lean on verbatim label matching? (D127)

D123 deliberately named relations by their LABEL in the question text, so
relation *identification* was easy by construction and *composition* was the
isolated variable. That was the right call for what it measured, and it
leaves an obvious hole: relation coordinates are the embedding of the label,
and the question contains that label verbatim, so the head may be doing
string overlap rather than anything semantic. If so, D123's 0.925 is inflated
and the whole wiki arc rests on a lexical shortcut.

This closes the hole with D113's anti-cheat design: **relation coordinates
stay label-derived, but questions are built from ALIASES only**, and the
aliases used at evaluation are held out from training (D110's K5 discipline).
A question says "married to"; the coordinate says "spouse"; the label never
appears in a question the head is scored on.

Comparison is against D123's label-based numbers on the identical pair
holdout, so the drop — if any — is attributable to phrasing alone.

Usage: .venv/bin/python scripts/exp33_alias.py
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
print(f"{len(wiki)} claims over {len(RELS)} relations having a label and "
      f">=3 aliases")
print("  example: " + ", ".join(
    f"{LABEL[r]} <- {ALIAS[r][:3]}" for r in RELS[:2]))

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
    print(f"depth {d}: {len(chains[d])} chains")

all_pairs = sorted({(a["chain"][0], a["chain"][1]) for a in chains[2]})
rng = np.random.default_rng(SEED)
HOLD_P = {all_pairs[i] for i in
          list(rng.permutation(len(all_pairs)))[: int(HOLD_FRAC
                                                      * len(all_pairs))]}
print(f"{len(all_pairs)} pairs, {len(HOLD_P)} held out")

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
for k in sorted(BAG):
    print(f"  {k:16s} {len(BAG[k]):6d}")

# Alias split: first two aliases are TRAINING phrasings, the rest are held
# out for evaluation. The label itself is never used in any question.
TRAIN_AL = {r: ALIAS[r][:2] for r in RELS}
EVAL_AL = {r: ALIAS[r][2:] or ALIAS[r][1:2] for r in RELS}


def word_for(r, key, i):
    pool = TRAIN_AL[r] if key.startswith("train") else EVAL_AL[r]
    return pool[i % len(pool)]


def text_of(a, key, i):
    np_ = a["subject"]
    for r in a["chain"][:-1]:
        np_ = f"the {word_for(r, key, i)} of {np_}"
    return f"What is the {word_for(a['chain'][-1], key, i)} of {np_}?"


# The headline comparison changes TWO things at once (novel pair AND novel
# phrasing), which cannot be attributed. These are the missing cells of the
# 2x2: trained pairs rendered with HELD-OUT aliases isolates phrasing, and
# held-out pairs rendered with TRAINING aliases isolates composition.
BAG["xcell_trainpair_evalalias"] = BAG["train_d2"]
BAG["xcell_evalpair_trainalias"] = BAG["eval_d2_clean"]
RENDER = {"xcell_trainpair_evalalias": "eval",
          "xcell_evalpair_trainalias": "train"}
ORDER = sorted(BAG)
texts, index = [], {}
for key in ORDER:
    index[key] = (len(texts), len(texts) + len(BAG[key]))
    mode = RENDER.get(key, "train" if key.startswith("train") else "eval")
    texts += [text_of(a, "train_" if mode == "train" else "e", i)
              for i, a in enumerate(BAG[key])]
cache = ROOT / "results" / "exp33_emb.npz"
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    assert list(z["texts"]) == texts, "cache misaligned; delete it"
    Z, Zl = z["Z"], z["Zl"]
else:
    Z = P.unit(P.embed_texts(texts))
    Zl = P.unit(P.embed_texts([LABEL[r] for r in RELS]))
    np.savez(cache, Z=Z, Zl=Zl, texts=np.array(texts))
RC = {r: Zl[i] for i, r in enumerate(RELS)}
print(f"\n{len(texts)} questions. Train phrasing: "
      f"{texts[index['train_d2'][0]]!r}")
print(f"HELD-OUT phrasing: {texts[index['eval_d2_clean'][0]]!r}")
print(f"(coordinates come from labels, which never appear above)", flush=True)


def emb(key):
    a, b = index[key]
    return Z[a:b]


import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

Xs, Ys = [], []
for key in ("train_d1", "train_d2"):
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
print(f"head trained on {len(Xs)} chains (training aliases only)", flush=True)


def run(key, max_steps, answerable, thr):
    rows, E = BAG[key], emb(key)
    with torch.no_grad():
        tgt = head(torch.tensor(E)).numpy()
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


best, bw = None, -1
for t in (0.3, 0.4, 0.5, 0.6, 0.8, 1.0):
    v = [run("train_d1", 2, True, t)["correct"],
         run("train_d2", 3, True, t)["correct"],
         run("unans", 3, False, t)["abstain"]]
    if min(v) > bw:
        bw, best = min(v), t
THR = best
print(f"selected THR={THR} on trained/unanswerable populations "
      f"(worst {bw:.3f})")

print("\n=== HELD-OUT PHRASINGS (aliases the head never trained on) ===")
print(f"{'population':18s} {'correct':>8} {'wrong':>7} {'abstain':>8} "
      f"{'n':>7}")
res = {}
for key, mx, ans in (("train_d1", 2, True), ("train_d2", 3, True),
                     ("xcell_trainpair_evalalias", 3, True),
                     ("xcell_evalpair_trainalias", 3, True),
                     ("eval_d2_clean", 3, True), ("unans", 3, False)):
    r = run(key, mx, ans, THR)
    res[key] = r
    print(f"{key:18s} {r['correct']:8.3f} {r['wrong']:7.3f} "
          f"{r['abstain']:8.3f} {r['n']:7d}")

D123 = {"eval_d2_clean": 0.925, "train_d2": 0.913}
print(f"\nD123 with LABELS in the question, same pair holdout:")
print(f"  eval_d2_clean 0.925    train_d2 0.913")
print(f"D127 with HELD-OUT ALIASES:")
print(f"  eval_d2_clean {res['eval_d2_clean']['correct']:.3f}    "
      f"train_d2 {res['train_d2']['correct']:.3f}")
drop = D123["eval_d2_clean"] - res["eval_d2_clean"]["correct"]
print(f"  combined cost on the pair-clean population: {drop:+.3f}")
print("\n2x2 attribution — which change causes the collapse?")
print(f"{'':28s} {'train alias':>12} {'HELD-OUT alias':>15}")
print(f"{'trained pair':28s} {res['train_d2']['correct']:12.3f} "
      f"{res['xcell_trainpair_evalalias']['correct']:15.3f}")
print(f"{'HELD-OUT pair':28s} "
      f"{res['xcell_evalpair_trainalias']['correct']:12.3f} "
      f"{res['eval_d2_clean']['correct']:15.3f}")
d_phr = (res['train_d2']['correct']
         - res['xcell_trainpair_evalalias']['correct'])
d_pair = (res['train_d2']['correct']
          - res['xcell_evalpair_trainalias']['correct'])
print(f"  phrasing alone costs {d_phr:+.3f};  composition alone costs "
      f"{d_pair:+.3f}")
out_extra = {"phrasing_alone": round(d_phr, 4),
             "composition_alone": round(d_pair, 4)}

lo, hi = wilson_ci(int(res["eval_d2_clean"]["correct"]
                       * res["eval_d2_clean"]["n"]),
                   res["eval_d2_clean"]["n"])
out = {
    "manifest": run_manifest(seed=SEED, config={"HOLD_FRAC": HOLD_FRAC,
                                                "THR": THR}),
    "n_relations": len(RELS), "results": res,
    "d123_label_reference": D123,
    "phrasing_cost_combined": round(drop, 4),
    "attribution_2x2": out_extra,
    "eval_d2_clean_ci95": [round(lo, 4), round(hi, 4)],
    "scope": ("Relation coordinates are still the LABEL embedding; every "
              "question is built from ALIASES, and evaluation uses aliases "
              "held out from training (D110's K5 discipline). The label "
              "never appears in a scored question, so a lexical shortcut is "
              "unavailable. Relations needing >=3 aliases, so the relation "
              "set is smaller than D123's 61 and the comparison is "
              "approximate on that axis."),
}
(ROOT / "results" / "exp33_alias.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp33_alias.json")
