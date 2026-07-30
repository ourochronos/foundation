"""Does compression really trade generalisation against precision? (D154, claim 7)

The falsifier all three adversarial raters named, unanimously: *"a
representation could improve generalisation without sacrificing precision on a
controlled common corpus; the cross-experiment pattern does not rule that
out."*

The claim — *compression buys generalisation and costs precision* — was fitted
across D125 (novel relations), D126 (depth) and D128 (phrasings). Its scope
said those were three different corpora. **They are not.** `exp31`, `exp32` and
`exp34` all read `KB(backend="pg", table="poc")` at 61/61/60 relations. The
real confound is smaller and more embarrassing: **each derived its own
threshold**. Inside `exp31` alone, the raw arm runs at the inherited THR=0.8
while the basis arm sweeps and selects 0.6 — so the headline 0.293 → 0.742
compares two representations at two different operating points, and part of
the "gain" could be threshold placement (D156).

**This run changes exactly one thing: both representations are tuned by the
same rule.** Same store, same populations, same chains, same head
architecture, same seed, same sweep grid, same selection rule — read on
TRAINED populations only, so the novel ones never influence either threshold
(law #6). Everything else is `exp31`'s design, and its embedding cache is
reused under a content assert, so the populations are provably identical.

Three ways this can come out, and all three are useful:

  * **basis wins generalisation AND loses precision** — the claim survives its
    first controlled test and stops being a post-hoc pattern;
  * **basis wins both** — the trade-off was threshold placement, and D125/D126/
    D128 need rewriting around one mechanism;
  * **basis loses both** — same conclusion, opposite sign.

Reported at each representation's own selected threshold **and at matched
coverage**, because a comparison at two operating points is what caused the
problem in the first place. Matched coverage is the honest way to ask "at the
same willingness to answer, which is more often right?"

Usage: .venv/bin/python scripts/exp53_compression_controlled.py
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
from codec.evals.anchors import fit_anchors                      # noqa: E402
from codec.manifest import run_manifest, wilson_ci               # noqa: E402
from foundation.kb import KB                                     # noqa: E402

SEED, MIN_GAIN = 0, 0.2
N_HOLD_REL, INST_FRAC, CAP_UNANS = 12, 0.20, 2000
K_BASIS = 48
# one grid, both arms. Residual norms live on different scales in 1024-d and
# in K-d, so a shared grid must span both; the selection rule picks per-arm.
GRID = (0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2)

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


# --- population construction, verbatim from exp31 so its cache applies ---
rng = np.random.default_rng(SEED)
HOLD_R = {RELS[i] for i in sorted(rng.permutation(len(RELS))[:N_HOLD_REL])}
print(f"{len(wiki)} claims, {len(RELS)} relations; "
      f"{len(HOLD_R)} held out ENTIRELY")

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
cache = ROOT / "results" / "exp31_emb.npz"
z = np.load(cache, allow_pickle=True)
assert list(z["texts"]) == texts, (
    "populations differ from exp31 — this experiment must run on exp31's "
    "exact questions or it is not a controlled comparison of that result")
Z, Zl = z["Z"], z["Zl"]
RC = {r: Zl[i] for i, r in enumerate(RELS)}
print(f"{len(texts)} questions, exp31's cache reused under a content assert")
for k in ORDER:
    print(f"  {k:18s} {len(BAG[k]):6d}")


def emb(key):
    a, b = index[key]
    return Z[a:b]


import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

TRAINED_R = [r for r in RELS if r not in HOLD_R]


def build_arm(name, coords, dim):
    """Train a head to predict sums of `coords`. Identical everywhere else."""
    Xs, Ys = [], []
    for key in ("train_d1", "train_d2", "train_d3"):
        E = emb(key)
        for j, a in enumerate(BAG[key]):
            Xs.append(E[j])
            Ys.append(sum(coords[r] for r in a["chain"]))
    X, Y = torch.tensor(np.stack(Xs)), torch.tensor(np.stack(Ys))
    torch.manual_seed(SEED)
    hd = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, dim))
    op = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(X)).split(512):
            op.zero_grad()
            ((hd(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
            op.step()
    hd.eval()
    print(f"  {name}: head trained on {len(Xs)} rows -> {dim}-d", flush=True)
    return hd


PC = P.unit(fit_anchors(np.stack([RC[r] for r in TRAINED_R]), K_BASIS,
                        seed=SEED))
ARMS = {
    "raw_1024d": {"coords": RC, "dim": 1024},
    f"basis_K{K_BASIS}": {"coords": {r: P.unit(RC[r] @ PC.T) for r in RELS},
                          "dim": K_BASIS},
}
print("\nbuilding both arms with identical training data and seed:")
for name, arm in ARMS.items():
    arm["head"] = build_arm(name, arm["coords"], arm["dim"])


def run(arm, key, max_steps, answerable, thr):
    coords, hd, dim = arm["coords"], arm["head"], arm["dim"]
    rows, E = BAG[key], emb(key)
    with torch.no_grad():
        tgt = hd(torch.tensor(E)).numpy()
    c = collections.Counter()
    for j, a in enumerate(rows):
        resid, frontier, path = tgt[j].copy(), {a["subject"]}, []
        for _ in range(max_steps):
            best, bg = None, MIN_GAIN
            for r in options_at(frontier):
                g = float(resid @ coords[r])
                if g > bg:
                    best, bg = r, g
            if best is None:
                break
            nxt = step(frontier, best)
            if not nxt:
                break
            frontier, path = nxt, path + [best]
            resid = resid - coords[best]
        rn = float(np.linalg.norm(tgt[j] - sum((coords[r] for r in path),
                                               np.zeros(dim, np.float32))))
        if not path or not frontier or rn > thr:
            c["abstain"] += 1
        elif answerable:
            c["correct" if set(frontier) & set(a["answers"]) else "wrong"] += 1
        else:
            c["wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: round(c[k] / n, 4) for k in
            ("correct", "wrong", "abstain")} | {"n": n}


# populations, and which side of the claim each one speaks to
SPECS = [("train_d1", 2, True, "trained"), ("train_d2", 3, True, "trained"),
         ("train_d3", 4, True, "trained"),
         ("unans_trained", 3, False, "trained"),
         ("eval_d1_inst", 2, True, "precision"),
         ("eval_d2_inst", 3, True, "precision"),
         ("eval_d1_novel1", 2, True, "generalisation"),
         ("eval_d2_novel1", 3, True, "generalisation"),
         ("unans_novel", 3, False, "generalisation")]
SPECS = [s for s in SPECS if s[0] in BAG and BAG[s[0]]]

print(f"\n=== threshold sweep, TRAINED populations only, one rule per arm ===")
sweeps, chosen = {}, {}
for name, arm in ARMS.items():
    sw = {}
    for t in GRID:
        sw[t] = {k: run(arm, k, ms, ans, t) for k, ms, ans, ax in SPECS
                 if ax == "trained"}
    # one rule, both arms: maximise the worst trained population, so an arm
    # cannot buy coverage on answerable questions by abandoning refusal
    def worst(t):
        s = sw[t]
        return min(s["train_d1"]["correct"], s["train_d2"]["correct"],
                   s["unans_trained"]["abstain"])
    best = max(GRID, key=worst)
    chosen[name] = best
    sweeps[name] = {str(t): {k: v for k, v in sw[t].items()} for t in GRID}
    print(f"  {name:14s} selected THR={best} "
          f"(worst trained population = {worst(best):.3f})")
    for t in GRID:
        print(f"      {t:4.1f}  d1 {sw[t]['train_d1']['correct']:.3f}  "
              f"d2 {sw[t]['train_d2']['correct']:.3f}  "
              f"unans-refused {sw[t]['unans_trained']['abstain']:.3f}")

print(f"\n=== both arms at their OWN selected threshold ===")
own = {}
for name, arm in ARMS.items():
    own[name] = {k: run(arm, k, ms, ans, chosen[name])
                 for k, ms, ans, _ in SPECS}
hdr = f"{'population':18s} {'axis':15s}"
for name in ARMS:
    hdr += f" {name:>16s}"
print(hdr)
for k, ms, ans, axis in SPECS:
    line = f"{k:18s} {axis:15s}"
    for name in ARMS:
        v = own[name][k]
        line += f" {(v['abstain'] if not ans else v['correct']):16.4f}"
    print(line + ("   (refusal)" if not ans else ""))

# ---- the comparison that decides it, at MATCHED coverage ----
# Coverage is measured on the trained answerable populations, which neither
# arm's threshold was allowed to see novel data to set.
def coverage(arm, thr):
    tot = ans = 0
    for k in ("train_d1", "train_d2"):
        v = run(arm, k, 2 if k.endswith("d1") else 3, True, thr)
        tot += v["n"]
        ans += round((v["correct"] + v["wrong"]) * v["n"])
    return ans / max(tot, 1)


base = ARMS["raw_1024d"]
BASE_COV = coverage(base, chosen["raw_1024d"])
other = f"basis_K{K_BASIS}"
matched = min(GRID, key=lambda t: abs(coverage(ARMS[other], t) - BASE_COV))
print(f"\n=== matched coverage: raw at THR={chosen['raw_1024d']} covers "
      f"{BASE_COV:.4f}; {other} matched at THR={matched} "
      f"({coverage(ARMS[other], matched):.4f}) ===")
match_res = {k: run(ARMS[other], k, ms, ans, matched)
             for k, ms, ans, _ in SPECS}
print(f"{'population':18s} {'axis':15s} {'raw':>10s} {'basis@match':>13s} "
      f"{'delta':>9s}")
deltas = {}
for k, ms, ans, axis in SPECS:
    a = own["raw_1024d"][k]
    b = match_res[k]
    va = a["abstain"] if not ans else a["correct"]
    vb = b["abstain"] if not ans else b["correct"]
    deltas[k] = round(vb - va, 4)
    print(f"{k:18s} {axis:15s} {va:10.4f} {vb:13.4f} {vb - va:+9.4f}")

# FOUR quantities, never averaged across an answerable/unanswerable boundary.
# The first version of this summary took one mean over the "generalisation"
# populations — two answerable and one unanswerable — which is audit law #7
# violated inside the statistic written to test a claim about precision. It
# also hid the finding: on novel relations the wrong-rate barely moves, and
# the basis converts raw's ABSTENTIONS into correct answers.
def mean_over(keys, field, src):
    vals = [src[k][field] - own["raw_1024d"][k][field] for k in keys]
    return round(float(np.mean(vals)), 4) if vals else 0.0


NOVEL_ANS = [k for k, _, ans, ax in SPECS if ax == "generalisation" and ans]
NOVEL_UNANS = [k for k, _, ans, ax in SPECS
               if ax == "generalisation" and not ans]
KNOWN_ANS = [k for k, _, ans, ax in SPECS
             if ax in ("precision", "trained") and ans]
KNOWN_UNANS = [k for k, _, ans, ax in SPECS if ax == "trained" and not ans]

M = match_res
G_ans = mean_over(NOVEL_ANS, "correct", M)          # generalisation, answerable
G_wrong = mean_over(NOVEL_ANS, "wrong", M)          # its precision cost, same pop
R_novel = mean_over(NOVEL_UNANS, "abstain", M)      # refusal on novel unanswerable
P_known = mean_over(KNOWN_ANS, "correct", M)        # known-relation answering
P_wrong = mean_over(KNOWN_ANS, "wrong", M)          # known-relation wrongness
R_known = mean_over(KNOWN_UNANS, "abstain", M)      # refusal on known unanswerable

print(f"\n=== four quantities at matched coverage, never averaged across "
      f"the answerable/unanswerable boundary (law #7) ===")
print(f"  novel-relation ANSWERING   correct {G_ans:+.4f}   "
      f"wrong {G_wrong:+.4f}")
print(f"  novel-relation REFUSAL     abstain {R_novel:+.4f}")
print(f"  known-relation ANSWERING   correct {P_known:+.4f}   "
      f"wrong {P_wrong:+.4f}")
print(f"  known-relation REFUSAL     abstain {R_known:+.4f}")

# "Costs precision" has to mean the cost is COMMENSURATE with the gain, not
# merely non-zero. An absolute 0.02 bar called this trade-off "as stated" on a
# wrongness rise of 0.072 against a correctness rise of 0.741 — a tenth — while
# refusal fell by 0.706. A ratio test asks the question the claim actually
# makes.
gains = G_ans > 0.02
ratio = (G_wrong / G_ans) if G_ans > 0 else 0.0
pays_in_wrongness_where_it_gains = ratio >= 0.25
pays_elsewhere = (R_novel < -0.02 or P_known < -0.02 or R_known < -0.02)
print(f"  wrongness cost is {ratio:.1%} of the generalisation gain on the "
      f"same population")
if gains and pays_in_wrongness_where_it_gains:
    verdict = (f"TRADE-OFF CONFIRMED AS STATED — the basis gains "
               f"{G_ans:+.4f} on novel-relation answering and pays "
               f"{G_wrong:+.4f} in wrongness ON THE SAME POPULATION.")
elif gains and pays_elsewhere:
    verdict = (f"TRADE-OFF CONFIRMED BUT MISLOCATED — the basis gains "
               f"{G_ans:+.4f} on novel-relation answering at a wrongness "
               f"cost of {G_wrong:+.4f} there, only {ratio:.0%} of the gain. "
               f"The price is paid elsewhere: novel-relation refusal "
               f"{R_novel:+.4f}, known-relation answering {P_known:+.4f}, "
               f"known-relation refusal {R_known:+.4f}. Compression does not "
               f"blunt the answers it enables; it blunts REFUSAL and "
               f"degrades what was already working.")
elif gains:
    verdict = (f"REFUTED — the basis gains {G_ans:+.4f} on novel-relation "
               f"answering with no measurable cost anywhere "
               f"(wrong {G_wrong:+.4f}, novel refusal {R_novel:+.4f}, known "
               f"answering {P_known:+.4f}). The trade-off was threshold "
               f"placement, not compression.")
else:
    verdict = (f"NO GENERALISATION GAIN — {G_ans:+.4f} on novel-relation "
               f"answering once both arms are tuned by the same rule; the "
               f"axis does not survive a controlled comparison.")
print(f"\n=== VERDICT ===\n  {verdict}")

out = {
    "manifest": run_manifest(seed=SEED,
                             config={"K_BASIS": K_BASIS, "GRID": list(GRID),
                                     "N_HOLD_REL": N_HOLD_REL,
                                     "MIN_GAIN": MIN_GAIN}),
    "n_relations": len(RELS), "n_held_relations": len(HOLD_R),
    "population_sizes": {k: len(BAG[k]) for k in ORDER},
    "selected_thresholds": chosen,
    "sweeps_trained_only": sweeps,
    "at_own_threshold": own,
    "matched_coverage": {"raw_coverage": round(BASE_COV, 4),
                         "basis_threshold": matched,
                         "basis_coverage": round(
                             coverage(ARMS[other], matched), 4),
                         "results": match_res},
    "deltas_at_matched_coverage": deltas,
    "summary_at_matched_coverage": {
        "novel_answering_correct": G_ans, "novel_answering_wrong": G_wrong,
        "novel_refusal_abstain": R_novel,
        "known_answering_correct": P_known, "known_answering_wrong": P_wrong,
        "known_refusal_abstain": R_known,
        "populations": {"novel_answerable": NOVEL_ANS,
                        "novel_unanswerable": NOVEL_UNANS,
                        "known_answerable": KNOWN_ANS,
                        "known_unanswerable": KNOWN_UNANS}},
    "verdict": verdict,
    "scope": ("Changes exactly ONE thing against exp31: both representations "
              "are tuned by the same rule on the same TRAINED-only "
              "populations (law #6), where exp31 ran its raw arm at an "
              "inherited THR=0.8 and swept only the basis arm to 0.6. Same "
              "store, chains, populations, head architecture, seed and grid; "
              "exp31's embedding cache is reused under a content assert, so "
              "the questions are provably identical. Claim 7's scope "
              "previously said these were three different corpora — exp31, "
              "exp32 and exp34 all read the same table, so the confound was "
              "always tuning rather than corpus (D156). Reported at each "
              "arm's own threshold AND at matched coverage, because "
              "comparing two representations at two operating points is the "
              "defect this experiment exists to remove. The phrasing axis of "
              "the original claim is NOT covered here: it needs exp34's "
              "alias populations, which are a different question set."),
}
(ROOT / "results" / "exp53_compression_controlled.json").write_text(
    json.dumps(out, indent=1))
print("\n[done] results/exp53_compression_controlled.json")
