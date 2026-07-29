"""The walker on the wiki corpus, with PAIR-CLEAN composition holdouts (D123).

D122 proved that with 5 relations a pair-clean composition holdout does not
exist beyond depth 2: the ~15 realised adjacent pairs recur too densely to
isolate a triple from all of them. Every depth claim since D119 has been
blocked on that. The wiki component has **62 relations, 636 realised 2-hop
shapes and 2,489 3-hop shapes**, which makes the holdout constructible for
the first time.

This is also where the two arcs meet. D113-D116 built relation coordinates
from LABELS so the vocabulary is open; D117-D122 built a walker that takes
order and depth from the store. Until now they have never run together —
the AI corpus's five relation names were hand-written for D117 and carry no
vocabulary at all.

**Holdout design, which is the point of the experiment.** A set of adjacent
relation PAIRS is held out. Training excludes any chain containing a
held-out pair, at every depth. Evaluation uses:

  depth 2, pair-clean   — the chain's single pair is held out
  depth 3, pair-clean   — BOTH adjacent pairs are held out
  depth 3, partial      — exactly one pair is held out (reported separately,
                          never merged, because D122 showed that merging
                          these is what made depth-3 look easy)

Per D122's rule, pair-cleanliness is reported alongside every number.

**Scope, deliberately.** Questions name relations by their LABEL, so
relation *identification* is easy by construction and *composition* is
isolated as the variable under test. That is the opposite of D113's design,
where labels were hidden behind aliases precisely because identification was
the thing being measured. Stating which is under test matters more than
which choice is made. Phrasing robustness is likewise not tested here (D110
covers it); one frame per question.

A side benefit: "What is the inception of the employer of X?" is a question
a person might actually ask, which is a real improvement on D121's
"What do the works cited by the works cited by ... cite?" and partly
dissolves that confound.

Usage: .venv/bin/python scripts/exp29_wikiwalker.py
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

SEED, MIN_GAIN = 0, 0.2
HOLD_FRAC = 0.34
CAP = {"single": 6000, 2: 7000, 3: 8000, "unans": 2000}

# Labels: prefer the curated schema, fall back to the full Wikidata dump so
# every relation in the corpus has content (D116's vocabulary, reused).
sch = {d["pid"]: d["label"] for d in
       json.loads((ROOT / "data" / "schema_v0.json").read_text())}
props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())

kb = KB(backend="pg", table="poc")
wiki = [c for c in kb.claims
        if not c["page"].startswith(("arxiv:", "hf:", "user"))]
LABEL = {}
for c in wiki:
    p = c["pid"]
    if p in LABEL:
        continue
    if p in sch:
        LABEL[p] = sch[p]
    elif p in props:
        LABEL[p] = props[p]["label"]
RELS = sorted(LABEL)
wiki = [c for c in wiki if c["pid"] in LABEL]
print(f"{len(wiki)} wiki claims over {len(RELS)} labelled relations "
      f"({len({c['pid'] for c in wiki}) - len(RELS)} unlabelled dropped)")

gold = collections.defaultdict(set)
avail = collections.defaultdict(set)
for c in wiki:
    gold[(c["subject"], c["pid"])].add(c["object"])
    avail[c["subject"]].add(c["pid"])
subjects = sorted(avail)


def step(nodes, r):
    out = set()
    for s in nodes:
        out |= gold.get((s, r), set())
    return out


# ---- enumerate chains deterministically (audit law #8) ----
chains = {1: [], 2: [], 3: []}
for s in subjects:
    stack = [({s}, [])]
    while stack:
        nodes, ch = stack.pop()
        if len(ch) >= 3:
            continue
        for r in sorted(set().union(*(avail.get(x, set()) for x in nodes))):
            nx = step(nodes, r)
            if not nx:
                continue
            c2 = ch + [r]
            chains[len(c2)].append({"subject": s, "chain": c2,
                                    "answers": sorted(nx)[:300]})
            stack.append((nx, c2))
for d in (1, 2, 3):
    chains[d].sort(key=lambda a: (a["subject"], ">".join(a["chain"])))
    print(f"depth {d}: {len(chains[d])} chains, "
          f"{len({tuple(a['chain']) for a in chains[d]})} shapes")

# ---- hold out PAIRS, not shapes ----
all_pairs = sorted({(a["chain"][0], a["chain"][1]) for a in chains[2]})
rng = np.random.default_rng(SEED)
perm = list(rng.permutation(len(all_pairs)))
HOLD_P = {all_pairs[i] for i in perm[: int(HOLD_FRAC * len(all_pairs))]}
print(f"{len(all_pairs)} realised pairs, {len(HOLD_P)} held out "
      f"({len(HOLD_P)/len(all_pairs):.0%})")


def pairs_of(ch):
    return list(zip(ch, ch[1:]))


def n_held(ch):
    return sum(1 for p in pairs_of(ch) if p in HOLD_P)


POPS = {
    "train_d1": [a for a in chains[1]],
    "train_d2": [a for a in chains[2] if n_held(a["chain"]) == 0],
    "train_d3": [a for a in chains[3] if n_held(a["chain"]) == 0],
    "eval_d2_clean": [a for a in chains[2] if n_held(a["chain"]) == 1],
    "eval_d3_clean": [a for a in chains[3] if n_held(a["chain"]) == 2],
    "eval_d3_partial": [a for a in chains[3] if n_held(a["chain"]) == 1],
}
for k, v in POPS.items():
    if k.startswith("train") and k != "train_d1":
        cap = CAP[int(k[-1])]
    elif k == "train_d1":
        cap = CAP["single"]
    else:
        cap = CAP.get(int(k.split("_d")[1][0]), 8000)
    if len(v) > cap:
        idx = sorted(rng.choice(len(v), cap, replace=False))
        POPS[k] = [v[i] for i in idx]
    print(f"  {k:18s} {len(POPS[k]):6d} chains, "
          f"{len({tuple(a['chain']) for a in POPS[k]}):5d} shapes")

# ---- unanswerable, graded by break point, from TRAINED pairs only so the
# refusal threshold is calibrated where the failure lives (audit law #6) ----
unans = {2: {2: []}, 3: {2: [], 3: []}}
for s in subjects:
    for r1 in sorted(avail[s]):
        m1 = step({s}, r1)
        if not m1:
            continue
        for r2 in RELS:
            m2 = step(m1, r2)
            if not m2:
                unans[2][2].append({"subject": s, "chain": [r1, r2],
                                    "answers": []})
                unans[3][2].append({"subject": s, "chain": [r1, r2, RELS[0]],
                                    "answers": []})
                continue
            for r3 in RELS:
                if not step(m2, r3):
                    unans[3][3].append({"subject": s,
                                        "chain": [r1, r2, r3],
                                        "answers": []})
for d in unans:
    for k in unans[d]:
        rows = unans[d][k]
        rows.sort(key=lambda a: (a["subject"], ">".join(a["chain"])))
        if len(rows) > CAP["unans"]:
            idx = sorted(rng.choice(len(rows), CAP["unans"], replace=False))
            unans[d][k] = [rows[i] for i in idx]
        print(f"  unans d{d} break@{k}: {len(unans[d][k])}")

# ---- questions: labels named verbatim, composition is the variable ----
def text_of(s, chain):
    np_ = s
    for r in chain[:-1]:
        np_ = f"the {LABEL[r]} of {np_}"
    return f"What is the {LABEL[chain[-1]]} of {np_}?"


ORDER = (sorted(POPS) + [f"unans_{d}_{k}" for d in unans for k in unans[d]])
BAG = dict(POPS)
for d in unans:
    for k in unans[d]:
        BAG[f"unans_{d}_{k}"] = unans[d][k]
texts, index = [], {}
for key in ORDER:
    rows = BAG[key]
    index[key] = (len(texts), len(texts) + len(rows))
    texts += [text_of(a["subject"], a["chain"]) for a in rows]
print(f"\n{len(texts)} questions total; example: {texts[index['eval_d3_clean'][0]]!r}")

cache = ROOT / "results" / "exp29_emb.npz"
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    assert list(z["texts"]) == texts, "cache misaligned; delete it"
    Z, Zl = z["Z"], z["Zl"]
else:
    Z = P.unit(P.embed_texts(texts))
    Zl = P.unit(P.embed_texts([LABEL[r] for r in RELS]))
    np.savez(cache, Z=Z, Zl=Zl, texts=np.array(texts))
RC = {r: Zl[i] for i, r in enumerate(RELS)}
print(f"embeddings {Z.shape} questions / {Zl.shape} relation labels",
      flush=True)


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
print(f"sum head trained on {len(Xs)} chains, all containing NO held-out "
      f"pair", flush=True)


def walk(subject, target, max_steps):
    resid, frontier, path = target.copy(), {subject}, []
    for _ in range(max_steps):
        options = set()
        for s in frontier:
            options |= avail.get(s, set())
        best, best_g = None, MIN_GAIN
        for r in options:
            g = float(resid @ RC[r])
            if g > best_g:
                best, best_g = r, g
        if best is None:
            break
        nxt = step(frontier, best)
        if not nxt:
            break
        frontier, path = nxt, path + [best]
        resid = resid - RC[best]
    return path, frontier


def judge(key, thr, answerable, max_steps):
    rows, E = BAG[key], emb(key)
    with torch.no_grad():
        tgt = head(torch.tensor(E)).numpy()
    c = collections.Counter()
    exact = 0
    for j, a in enumerate(rows):
        path, got = walk(a["subject"], tgt[j], max_steps)
        resid = tgt[j] - sum((RC[r] for r in path), np.zeros(1024, np.float32))
        if not path or not got or float(np.linalg.norm(resid)) > thr:
            c["abstain"] += 1
            continue
        if answerable:
            exact += path == a["chain"]
            c["correct" if set(got) & set(a["answers"]) else "wrong"] += 1
        else:
            c["wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: c[k] / n for k in ("correct", "wrong", "abstain")} | {
        "exact_chain": exact / n, "n": n}


# Threshold calibrated ONLY on trained-pair populations plus the unanswerable
# sets (which exhibit the failure, per audit law #6). Held-out pairs never
# influence it.
print("\nthreshold calibration on TRAINED pairs + unanswerable")
print(f"{'thr':>5} {'d2 corr':>8} {'d3 corr':>8} {'brk@2 ref':>10} "
       f"{'brk@3 ref':>10} {'worst':>7}")
best, best_w = None, -1
for t in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0):
    a2 = judge("train_d2", t, True, 3)
    a3 = judge("train_d3", t, True, 4)
    b2 = judge("unans_3_2", t, False, 4)
    b3 = judge("unans_3_3", t, False, 4)
    w = min(a2["correct"], a3["correct"], b2["abstain"], b3["abstain"])
    print(f"{t:5.2f} {a2['correct']:8.3f} {a3['correct']:8.3f} "
          f"{b2['abstain']:10.3f} {b3['abstain']:10.3f} {w:7.3f}")
    if w > best_w:
        best_w, best = w, t
THR = best
print(f"selected thr={THR} (max worst-case on calibration populations)")

print(f"\n=== HELD-OUT PAIRS — the pair-clean composition test ===")
print(f"{'population':18s} {'pairs held':>10} {'correct':>8} {'wrong':>7} "
      f"{'abstain':>8} {'exact':>7} {'n':>7}")
res = {}
for key, mx, ph in (("eval_d2_clean", 3, "1 of 1"),
                    ("eval_d3_clean", 4, "2 of 2"),
                    ("eval_d3_partial", 4, "1 of 2")):
    r = judge(key, THR, True, mx)
    res[key] = {**r, "pairs_held": ph}
    print(f"{key:18s} {ph:>10} {r['correct']:8.3f} {r['wrong']:7.3f} "
          f"{r['abstain']:8.3f} {r['exact_chain']:7.3f} {r['n']:7d}")
print(f"\n{'reference (trained pairs)':18s}")
for key, mx in (("train_d2", 3), ("train_d3", 4)):
    r = judge(key, THR, True, mx)
    res[key] = {**r, "pairs_held": "0"}
    print(f"{key:18s} {'0':>10} {r['correct']:8.3f} {r['wrong']:7.3f} "
          f"{r['abstain']:8.3f} {r['exact_chain']:7.3f} {r['n']:7d}")
print(f"\n{'refusal (unanswerable)':18s}")
for key in ("unans_2_2", "unans_3_2", "unans_3_3"):
    r = judge(key, THR, False, 4)
    res[key] = r
    print(f"{key:18s} {'—':>10} refused {r['abstain']:.3f}  answered "
          f"{r['wrong']:.3f}  (n={r['n']})")

lo, hi = wilson_ci(int(res["eval_d3_clean"]["correct"]
                       * res["eval_d3_clean"]["n"]),
                   res["eval_d3_clean"]["n"])
print(f"\npair-clean depth-3 correct CI95 [{lo:.3f}, {hi:.3f}]")
print(f"D122 reference: the only pair-clean number available on the AI "
      f"corpus was depth 2, 0.359 correct / 0.000 wrong / 0.641 abstain")

out = {
    "manifest": run_manifest(seed=SEED, config={"HOLD_FRAC": HOLD_FRAC,
                                                "MIN_GAIN": MIN_GAIN,
                                                "thr": THR}),
    "n_relations": len(RELS), "n_claims": len(wiki),
    "n_pairs": len(all_pairs), "n_held_pairs": len(HOLD_P),
    "threshold": THR, "results": res,
    "d3_clean_ci95": [round(lo, 4), round(hi, 4)],
    "scope": ("Composition holdout is over adjacent PAIRS, not shapes: "
              "training excludes any chain containing a held-out pair at "
              "every depth, and pair-cleanliness is reported for every "
              "evaluation population (D122's rule). Questions name "
              "relations by LABEL, so relation identification is easy by "
              "construction and composition is the isolated variable — the "
              "opposite of D113, where labels were hidden behind aliases "
              "because identification was what was being measured. One "
              "phrasing per question; phrasing robustness is D110's."),
}
(ROOT / "results" / "exp29_wikiwalker.json").write_text(json.dumps(out,
                                                                   indent=1))
print("\n[done] results/exp29_wikiwalker.json")

# ---------------------------------------------------------------------------
# Negative controls. Held-out-pair performance (0.925) MATCHING trained-pair
# performance (0.913) is a strong claim, and there is a boring explanation
# that must be excluded first: if the store offers only one walkable relation
# per step, the walk is forced and the head contributes nothing. Two controls,
# plus the branching factor that would make the walk trivial.
#
#   RANDOM   — replace the predicted target with a random vector of the same
#              magnitude. Any performance left is what the STORE alone gives.
#   SHUFFLED — permute the relation->coordinate assignment. The head's output
#              is unchanged and still well-formed; only its meaning is broken.
# ---------------------------------------------------------------------------
def branching(key, max_steps):
    rows = BAG[key]
    counts = []
    for a in rows[:2000]:
        frontier = {a["subject"]}
        for r in a["chain"][:max_steps]:
            opts = set()
            for s in frontier:
                opts |= avail.get(s, set())
            counts.append(len(opts))
            nxt = step(frontier, r)
            if not nxt:
                break
            frontier = nxt
    return float(np.mean(counts)), int(np.median(counts))


print("\nbranching factor — how many relations the walk chooses between")
for key, mx in (("eval_d2_clean", 2), ("eval_d3_clean", 3)):
    m, md = branching(key, mx)
    print(f"  {key:18s} mean {m:.1f}  median {md}  "
          f"(1 would make the walk forced)")

RC_SHUF = {r: RC[s] for r, s in
           zip(RELS, [RELS[i] for i in np.random.default_rng(7).permutation(
               len(RELS))])}


def judge_control(key, thr, max_steps, mode):
    rows, E = BAG[key], emb(key)
    with torch.no_grad():
        tgt = head(torch.tensor(E)).numpy()
    rc = RC_SHUF if mode == "shuffled" else RC
    g = np.random.default_rng(11)
    c = collections.Counter()
    for j, a in enumerate(rows):
        t = tgt[j]
        if mode == "random":
            v = g.normal(size=1024).astype(np.float32)
            t = v / np.linalg.norm(v) * float(np.linalg.norm(tgt[j]))
        resid, frontier, path = t.copy(), {a["subject"]}, []
        for _ in range(max_steps):
            options = set()
            for s in frontier:
                options |= avail.get(s, set())
            best, bg = None, MIN_GAIN
            for r in options:
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
        rr = t - sum((rc[r] for r in path), np.zeros(1024, np.float32))
        if not path or not frontier or float(np.linalg.norm(rr)) > thr:
            c["abstain"] += 1
        else:
            c["correct" if set(frontier) & set(a["answers"]) else "wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: c[k] / n for k in ("correct", "wrong", "abstain")}


print("\ncontrols on the pair-clean populations")
print(f"{'population':18s} {'real':>8} {'shuffled RC':>12} {'random tgt':>11}")
ctrl = {}
for key, mx in (("eval_d2_clean", 3), ("eval_d3_clean", 4)):
    real = res[key]["correct"]
    sh = judge_control(key, THR, mx, "shuffled")["correct"]
    rd = judge_control(key, THR, mx, "random")["correct"]
    ctrl[key] = {"real": real, "shuffled_rc": sh, "random_target": rd}
    print(f"{key:18s} {real:8.3f} {sh:12.3f} {rd:11.3f}")
out["controls"] = ctrl
out["branching"] = {k: branching(k, m)[0]
                    for k, m in (("eval_d2_clean", 2), ("eval_d3_clean", 3))}
(ROOT / "results" / "exp29_wikiwalker.json").write_text(json.dumps(out,
                                                                   indent=1))
print("[done] controls appended")
