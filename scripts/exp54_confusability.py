"""Is it branching, or is it confusability? (D154 claim 6, and D137's owed test)

Two adversarial raters independently named the same falsifier — *"the evidence
covaries branching and confusability, failing to rule out confusability as the
actual cause"* — and the project's own log had already conceded it. D137's
revisit (a), written weeks earlier:

    D124's branching prediction still deserves a proper test, with the node
    set held fixed and confusable options added.

D124 measured refusal falling as the number of relations available at the
break step rises (correlation −0.79, −0.83, −0.91) and read it as ambiguity.
But in a real store the questions with many options are also the questions
whose options are *semantically crowded*, so the two vary together and neither
D124 nor D137 separated them. D137 got a hint for free — adding reverse edges
doubled the option set and cost **nothing**, because reverse coordinates never
compete with a forward question — but that changed the node set, so it
measured a different denominator rather than the effect.

**Design: hold everything fixed and vary only WHICH options are present.**
Every question is a chain-break unanswerable `(s, r1, r2)` where `r2` leads
nowhere from the frontier `m1 = step(s, r1)`. The walker's job is to refuse.
At that break step it sees `avail(m1)` — a set of distractors, none of which
is `r2`. So:

  * **confusable arm** — the k options with the HIGHEST cosine to the asked
    relation's coordinate `C[r2]`;
  * **non-confusable arm** — the k options with the LOWEST cosine;
  * **random arm** — k drawn without regard to cosine, the natural baseline.

**Branching is k, identical across arms.** Only crowding differs. Sweep k and
watch refusal:

  * if refusal falls with k in the confusable arm and stays flat in the
    non-confusable arm, **confusability is the mechanism** and D124's
    correlation is confounded — claim 6 gets restated;
  * if it falls in all three arms, **branching is the variable after all**,
    D137's refinement is wrong, and D124 stands unexplained.

**Step 1 is walked for real; only the break step is controlled.** A first
version granted a perfect first hop — frontier set to `m1`, residual set to
`predicted - C[r1]` — and every arm refused 100% of the time at every k. The
reason is arithmetic: with unit coordinates and `THR=0.8`, answering requires
an available option within cosine 0.68 of the asked relation, and the most
confusable arm averages 0.39. **Granting a clean first hop removes exactly the
accumulated residual error that D124's effect lives in**, so the idealised
break step cannot fail to refuse and the experiment measures nothing. The walk
now starts at the subject with unrestricted options, and the subset is applied
at the second step only. Step 1 is deterministic given the target, so all three
arms enter the break from the same frontier and stay comparable.

A manipulation check is mandatory — the mean cosine actually achieved in each
arm is reported, because an arm that failed to separate would produce a null
that reads exactly like a refuted hypothesis.

Reuses exp31's populations and cache under a content assert; no new embeddings.

Usage: .venv/bin/python scripts/exp54_confusability.py
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

SEED, MIN_GAIN, THR = 0, 0.2, 0.8          # D123's fixed threshold, as exp30
N_HOLD_REL, INST_FRAC, CAP_UNANS = 12, 0.20, 2000
# k tops out at 8 because the corpus does not have more: only 5.2% of break
# frontiers offer 8+ options and 0.2% offer 16+, so a sweep to 16 left THREE
# usable cases. Three doublings is the range this store can actually support.
KS = (1, 2, 3, 4, 6, 8)

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


# --- exp31's populations verbatim, so its embedding cache applies ---
rng = np.random.default_rng(SEED)
HOLD_R = {RELS[i] for i in sorted(rng.permutation(len(RELS))[:N_HOLD_REL])}
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
POPS = collections.defaultdict(list)
rr = np.random.default_rng(SEED + 1)
for d in (1, 2, 3):
    for a in chains[d]:
        nv = sum(1 for r in a["chain"] if r in HOLD_R)
        if nv:
            if d <= 2:
                POPS[f"eval_d{d}_novel{nv}"].append(a)
        elif rr.random() < INST_FRAC and d <= 2:
            POPS[f"eval_d{d}_inst"].append(a)
        else:
            POPS[f"train_d{d}"].append(a)
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
            unans[key].append({"subject": s, "chain": [r1, r2], "answers": []})
for k in sorted(unans):
    unans[k].sort(key=lambda a: (a["subject"], ">".join(a["chain"])))
    if len(unans[k]) > CAP_UNANS:
        unans[k] = [unans[k][i] for i in
                    sorted(rng.choice(len(unans[k]), CAP_UNANS,
                                      replace=False))]


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
z = np.load(ROOT / "results" / "exp31_emb.npz", allow_pickle=True)
assert list(z["texts"]) == texts, "populations differ from exp31; cache invalid"
Z, Zl = z["Z"], z["Zl"]
RC = {r: Zl[i] for i, r in enumerate(RELS)}
print(f"{len(RELS)} relations; exp31's cache reused under a content assert")


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
print(f"head trained on {len(Xs)} rows (raw 1024-d, as D124)", flush=True)

# ---- walk step 1 for real, then hold the break step for the arms ----
CASES, step1_abstained = [], 0
for key in ("unans_trained", "unans_novel"):
    rows, E = BAG[key], emb(key)
    with torch.no_grad():
        tgt = head(torch.tensor(E)).numpy()
    for j, a in enumerate(rows):
        r2 = a["chain"][1]
        resid = tgt[j].copy()
        best, bg = None, MIN_GAIN
        for r in options_at({a["subject"]}):        # step 1: UNRESTRICTED
            g = float(resid @ RC[r])
            if g > bg:
                best, bg = r, g
        if best is None:
            step1_abstained += 1
            continue                 # refused before reaching the break step
        f1 = step({a["subject"]}, best)
        if not f1:
            step1_abstained += 1
            continue
        resid = resid - RC[best]
        opts = sorted(options_at(f1))
        if len(opts) < max(KS):
            continue                 # needs enough options to subset to
        CASES.append({"pop": key, "f1": f1, "r2": r2, "resid": resid,
                      "opts": opts,
                      "cos": {r: float(RC[r] @ RC[r2]) for r in opts}})
print(f"{len(CASES)} break-step cases with >= {max(KS)} options "
      f"({step1_abstained} refused or died at step 1, before the break)")
if len(CASES) < 100:
    raise SystemExit(f"only {len(CASES)} usable cases — too few to read a "
                     f"slope from; lower max(KS) or widen the population")


def refuse_at(case, subset):
    """Does the walker refuse AT the break step, given exactly `subset`?"""
    resid = case["resid"]
    best, bg = None, MIN_GAIN
    for r in subset:
        g = float(resid @ RC[r])
        if g > bg:
            best, bg = r, g
    if best is None:
        return True                       # residual unspent: correct refusal
    nxt = step(case["f1"], best)
    if not nxt:
        return True                       # option led nowhere: refusal
    rn = float(np.linalg.norm(resid - RC[best]))
    return rn > THR                       # still unexplained: refusal


rs = np.random.default_rng(SEED + 7)
ARMS = ("confusable", "non_confusable", "random")
res = {a: {} for a in ARMS}
mean_cos, max_cos = {a: {} for a in ARMS}, {a: {} for a in ARMS}
print(f"\n{'k':>3} " + " ".join(f"{a:>16s}" for a in ARMS)
      + "   | mean cos / MAX cos to the asked relation")
for k in KS:
    row, cosrow, maxrow = {}, {}, {}
    for arm in ARMS:
        ref, cs, mx = 0, [], []
        for c in CASES:
            o = c["opts"]
            if arm == "confusable":
                sub = sorted(o, key=lambda r: -c["cos"][r])[:k]
            elif arm == "non_confusable":
                sub = sorted(o, key=lambda r: c["cos"][r])[:k]
            else:
                sub = [o[i] for i in
                       sorted(rs.choice(len(o), k, replace=False))]
            ref += refuse_at(c, sub)
            cs.append(float(np.mean([c["cos"][r] for r in sub])))
            # the MAX matters because the walker takes ONE option: a bag of
            # harmless distractors plus one plausible relation is, to a greedy
            # argmax, exactly as dangerous as that one relation alone
            mx.append(float(np.max([c["cos"][r] for r in sub])))
        row[arm] = ref / len(CASES)
        cosrow[arm], maxrow[arm] = float(np.mean(cs)), float(np.mean(mx))
        res[arm][str(k)] = round(row[arm], 4)
        mean_cos[arm][str(k)] = round(cosrow[arm], 4)
        max_cos[arm][str(k)] = round(maxrow[arm], 4)
    print(f"{k:3d} " + " ".join(f"{row[a]:16.4f}" for a in ARMS)
          + "   | " + " ".join(f"{cosrow[a]:.2f}/{maxrow[a]:.2f}"
                               for a in ARMS), flush=True)

# ---- does one quantity explain all 18 cells? ----
cells = [(a, k) for a in ARMS for k in KS]
ref_v = np.array([res[a][str(k)] for a, k in cells])
mean_v = np.array([mean_cos[a][str(k)] for a, k in cells])
max_v = np.array([max_cos[a][str(k)] for a, k in cells])
k_v = np.array([float(k) for _, k in cells])
corr = {"max_cos": float(np.corrcoef(ref_v, max_v)[0, 1]),
        "mean_cos": float(np.corrcoef(ref_v, mean_v)[0, 1]),
        "log2_k": float(np.corrcoef(ref_v, np.log2(k_v))[0, 1])}
print(f"\nacross all {len(cells)} (arm, k) cells, refusal correlates with:")
for kk in sorted(corr, key=lambda x: corr[x]):
    print(f"  {kk:9s} r = {corr[kk]:+.4f}")

# ---- manipulation check: did the arms actually differ in crowding? ----
sep = float(np.mean([mean_cos["confusable"][str(k)]
                     - mean_cos["non_confusable"][str(k)] for k in KS]))
print(f"\nmanipulation check — mean cosine separation between the confusable "
      f"and non-confusable arms: {sep:+.4f}")
if sep < 0.05:
    raise SystemExit("arms did not separate on confusability; any null below "
                     "would be a failed manipulation, not a refuted hypothesis")

# ---- slopes: how much does refusal move per doubling of branching? ----
def slope(arm):
    xs = np.log2(np.array(KS, float))
    ys = np.array([res[arm][str(k)] for k in KS], float)
    return float(np.polyfit(xs, ys, 1)[0])


slopes = {a: round(slope(a), 4) for a in ARMS}
print(f"\nrefusal change per DOUBLING of branching:")
for a in ARMS:
    print(f"  {a:16s} {slopes[a]:+.4f}")
drop = {a: round(res[a][str(KS[0])] - res[a][str(KS[-1])], 4) for a in ARMS}
print(f"total refusal lost from k={KS[0]} to k={KS[-1]}: "
      + ", ".join(f"{a} {drop[a]:+.4f}" for a in ARMS))

n = len(CASES)
lo_c, hi_c = wilson_ci(int(res["confusable"][str(KS[-1])] * n), n)
lo_n, hi_n = wilson_ci(int(res["non_confusable"][str(KS[-1])] * n), n)
separated = lo_n > hi_c
# the comparison that separates "count" from "crowding": ONE confusable
# option against MANY non-confusable ones
one_conf = res["confusable"][str(KS[0])]
many_nonconf = res["non_confusable"][str(KS[-1])]
print(f"\none confusable option refuses {one_conf:.4f}; "
      f"{KS[-1]} non-confusable options refuse {many_nonconf:.4f}")

dominant = min(corr, key=lambda x: corr[x])
if one_conf < many_nonconf and dominant == "max_cos":
    verdict = (f"CROWDING, NOT COUNT — a SINGLE confusable option refuses "
               f"{one_conf:.4f} while {KS[-1]} non-confusable options refuse "
               f"{many_nonconf:.4f}, and across all {len(cells)} cells "
               f"refusal tracks the MOST confusable option available "
               f"(r={corr['max_cos']:+.3f}) better than the count "
               f"(r={corr['log2_k']:+.3f}) or the mean "
               f"(r={corr['mean_cos']:+.3f}). Branching lowers refusal "
               f"because more options means a higher maximum, which is why "
               f"D124 saw a correlation and why D137's reverse edges were "
               f"free. Claim 6 should name the maximum, not the count.")
elif drop["confusable"] > 0.05 and drop["non_confusable"] <= 0.05:
    verdict = (f"CONFUSABILITY IS THE MECHANISM — refusal falls "
               f"{drop['confusable']:+.4f} when added options are confusable "
               f"and {drop['non_confusable']:+.4f} when they are not.")
elif drop["confusable"] > 0.05 and drop["non_confusable"] > 0.05:
    verdict = (f"BOTH MATTER — refusal falls in every arm "
               f"({drop['confusable']:+.4f} confusable, "
               f"{drop['non_confusable']:+.4f} non-confusable), so count is "
               f"not merely a proxy; but the arms differ in LEVEL at every k, "
               f"so crowding is not reducible to count either.")
else:
    verdict = (f"NO CLEAN READING — drops {drop['confusable']:+.4f} / "
               f"{drop['non_confusable']:+.4f}, correlations {corr}; needs "
               f"diagnosis before anything is concluded.")
print(f"\n=== VERDICT ===\n  {verdict}")

out = {
    "manifest": run_manifest(seed=SEED, config={"MIN_GAIN": MIN_GAIN,
                                                "THR": THR, "KS": list(KS),
                                                "N_HOLD_REL": N_HOLD_REL}),
    "n_cases": n, "ks": list(KS),
    "refusal_by_arm": res, "mean_cosine_by_arm": mean_cos,
    "max_cosine_by_arm": max_cos,
    "correlations_across_cells": {k: round(v, 4) for k, v in corr.items()},
    "one_confusable_vs_many_non": {"one_confusable": one_conf,
                                   f"{KS[-1]}_non_confusable": many_nonconf},
    "manipulation_separation": round(sep, 4),
    "slope_per_doubling": slopes, "total_drop": drop,
    "ci95_at_max_k": {"confusable": [round(lo_c, 4), round(hi_c, 4)],
                      "non_confusable": [round(lo_n, 4), round(hi_n, 4)]},
    "arms_separated_at_max_k": separated,
    "verdict": verdict,
    "scope": ("Isolates the break step of chain-break unanswerables: the "
              "frontier is set to step(s, r1) and the residual to "
              "predicted - C[r1], so the first hop is granted and only what "
              "happens AT the break is measured. Branching is k and is "
              "IDENTICAL across arms; only which options are present varies, "
              "which is the test D137's revisit (a) named and never ran and "
              "which two adversarial raters independently asked for (D154). "
              "Cases are restricted to break steps with at least max(KS) "
              "options so every k is a subset of the same option set — that "
              "restriction biases toward high-branching questions and is "
              "reported rather than hidden. Raw 1024-d at D123's fixed "
              "THR=0.8, as exp30, so nothing is re-tuned before the "
              "diagnosis is read. A manipulation check aborts the run if the "
              "arms failed to separate on cosine, because a failed "
              "manipulation produces a null indistinguishable from a refuted "
              "hypothesis."),
}
(ROOT / "results" / "exp54_confusability.json").write_text(
    json.dumps(out, indent=1))
print("\n[done] results/exp54_confusability.json")
