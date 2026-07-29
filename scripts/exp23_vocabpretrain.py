"""Train the relation head on VOCABULARY, not on the corpus (D116).

D115 found the binding constraint: novel-relation transfer scales with how
many relation TYPES the head has trained on, and this project has been
sitting at n=18 with the curve still rising. Basis width cannot buy what
vocabulary breadth has not supplied.

The head's job is a general map — question text to a point in relation
space. Nothing about it is corpus-specific. And the 13,713 Wikidata
properties ship WITH aliases, which is precisely the material needed to
synthesise `(question text, relation coordinate)` pairs for thousands of
relations that never appear in this corpus.

So the head is trained entirely on vocabulary, with subjects drawn from the
store purely as filler, and **all 26 corpus relations held out** — a
stronger test than D113-D115, where 18 of the 26 were trained. Evaluation is
deliberately identical to those runs (the same 8 held-out relations'
questions, scored against the same 26 candidates) so the numbers are
directly comparable to 0.286 and 0.240.

If the D115 curve keeps climbing, this is the reindex-free story working
end to end: the basis is frozen, the head is trained once on vocabulary, and
a corpus relation the system has never seen is plannable on arrival.

Usage: .venv/bin/python scripts/exp23_vocabpretrain.py
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

MIN_N, PER_REL, N_HELD, SEED = 20, 150, 8, 0
K_BASIS, N_ALIAS, N_MAX = 8, 3, 3000
SIZES = [50, 200, 800, 3000]
FRAMES = ["What is the {a} of {s}?", "For {s}, what is the {a}?"]

sch = {d["pid"]: d for d in
       json.loads((ROOT / "data" / "schema_v0.json").read_text())}
props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
kb = KB(backend="pg", table="poc")
wiki = [c for c in kb.claims
        if not c["page"].startswith(("arxiv:", "hf:", "user"))]
cnt = collections.Counter(c["pid"] for c in wiki)
RELS = sorted(p for p, n in cnt.items()
              if n >= MIN_N and p in sch
              and len(sch[p].get("aliases", ())) >= 2)
rng = np.random.default_rng(SEED)
perm = list(RELS)
rng.shuffle(perm)
HELD_R = sorted(perm[:N_HELD])

# ---- evaluation set: rebuilt EXACTLY as D115, so the numbers compare ----
by_rel = collections.defaultdict(list)
for c in wiki:
    if c["pid"] in RELS:
        by_rel[c["pid"]].append(c)
facts = []
for r in RELS:
    xs = by_rel[r]
    if len(xs) > PER_REL:
        xs = [xs[i] for i in rng.choice(len(xs), PER_REL, replace=False)]
    facts.extend(xs)
queries = []
for f in facts:
    for a in sch[f["pid"]]["aliases"]:
        for fr in FRAMES:
            queries.append({"pid": f["pid"], "subject": f["subject"],
                            "object": f["object"],
                            "text": fr.format(a=a, s=f["subject"])})
z = np.load(ROOT / "results" / "exp22_emb.npz", allow_pickle=True)
Zq, Zl, lab_order = z["Zq"], z["Zl"], list(z["lab_order"])
assert len(Zq) == len(queries), "eval construction drifted from D115"
V = {p: Zl[i] for i, p in enumerate(lab_order)}
he_i = [i for i, q in enumerate(queries) if q["pid"] in HELD_R]
print(f"eval: {len(he_i)} questions over {len(HELD_R)} held-out corpus "
      f"relations, scored against all {len(RELS)}")

# ---- training set: pure vocabulary, no corpus relations at all ----
OURS = set(RELS)
cand = sorted(p for p, d in props.items()
              if p not in OURS and len(d.get("aliases", ())) >= 2
              and len(d["label"]) > 2)
cand = list(np.random.default_rng(SEED).permutation(cand))[:N_MAX]
names = sorted({c["subject"] for c in wiki})
fill = [names[i] for i in
        np.random.default_rng(1).choice(len(names), 400, replace=False)]
train_q = []
for j, p in enumerate(cand):
    for ai, a in enumerate(props[p]["aliases"][:N_ALIAS]):
        for fi, fr in enumerate(FRAMES):
            s = fill[(j * 7 + ai * 3 + fi) % len(fill)]
            train_q.append({"pid": p, "text": fr.format(a=a, s=s)})
print(f"train: {len(train_q)} synthetic questions over {len(cand)} "
      f"vocabulary relations (subjects are filler)", flush=True)

tcache = ROOT / "results" / "exp23_train_emb.npz"
if tcache.exists():
    d = np.load(tcache, allow_pickle=True)
    Zt, Zv, v_order = d["Zt"], d["Zv"], list(d["v_order"])
else:
    Zt = P.unit(P.embed_texts([q["text"] for q in train_q]))
    v_order = list(cand)
    Zv = P.unit(P.embed_texts([props[p]["label"] for p in v_order]))
    np.savez(tcache, Zt=Zt, Zv=Zv, v_order=np.array(v_order))
VV = {p: Zv[i] for i, p in enumerate(v_order)}
print(f"train embeddings {Zt.shape}", flush=True)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

gold = collections.defaultdict(set)
for c in wiki:
    gold[(c["subject"], c["pid"])].add(c["object"])
Xhe = torch.tensor(Zq[he_i])
ri = {r: i for i, r in enumerate(RELS)}


def run(n_props, seed=0):
    sub = set(cand[:n_props])
    rows = [i for i, q in enumerate(train_q) if q["pid"] in sub]
    # Basis fit on the VOCABULARY relations being trained on — in-domain by
    # construction (they are relations), and never our corpus relations.
    PC = P.unit(fit_anchors(np.stack([VV[p] for p in cand[:n_props]]),
                            min(K_BASIS, n_props), seed=SEED))
    k = PC.shape[0]
    Ctr = {p: P.unit(VV[p] @ PC.T) for p in cand[:n_props]}
    Cev = {p: P.unit(V[p] @ PC.T) for p in RELS}
    X = torch.tensor(Zt[rows])
    Y = torch.tensor(np.stack([Ctr[train_q[i]["pid"]] for i in rows]))
    torch.manual_seed(seed)
    hd = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, k))
    opt = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(X)).split(512):
            opt.zero_grad()
            pr = hd(X[b])
            pr = pr / (pr.norm(dim=-1, keepdim=True) + 1e-9)
            (1 - (pr * Y[b]).sum(-1)).mean().backward()
            opt.step()
    hd.eval()
    M = np.stack([Cev[r] for r in RELS])
    with torch.no_grad():
        ph = hd(Xhe).numpy()
    ph = ph / (np.linalg.norm(ph, axis=1, keepdims=True) + 1e-9)
    S = ph @ M.T
    h1 = float(np.mean([int(np.argmax(S[j]) == ri[queries[i]["pid"]])
                        for j, i in enumerate(he_i)]))
    mrr = float(np.mean([1.0 / (1 + int(np.where(np.argsort(-S[j])
                                                 == ri[queries[i]["pid"]]
                                                 )[0][0]))
                         for j, i in enumerate(he_i)]))
    tal = collections.Counter()
    for j, i in enumerate(he_i):
        q = queries[i]
        got = gold.get((q["subject"], RELS[int(np.argmax(S[j]))]), set())
        tal["abstain" if not got else
            ("correct" if q["object"] in got else "wrong")] += 1
    a = tal["correct"] + tal["wrong"]
    return h1, mrr, (tal["correct"] / a if a else 0.0), dict(tal)


print(f"\nheld-out CORPUS relations, head trained ONLY on vocabulary "
      f"(chance {1/len(RELS):.3f})")
print(f"{'n_vocab_rels':>13} {'top-1':>8} {'MRR':>7} {'e2e prec':>10} "
      f"{'correct':>8} {'wrong':>7} {'abstain':>8}")
curve = {}
for n in SIZES:
    h1, mrr, prec, tal = run(n)
    tot = sum(tal.values())
    curve[n] = {"top1": round(h1, 4), "mrr": round(mrr, 4),
                "e2e_precision": round(prec, 4), "tally": tal}
    print(f"{n:13d} {h1:8.3f} {mrr:7.3f} {prec:10.3f} "
          f"{tal.get('correct',0)/tot:8.3f} {tal.get('wrong',0)/tot:7.3f} "
          f"{tal.get('abstain',0)/tot:8.3f}", flush=True)

bn = max(SIZES, key=lambda n: curve[n]["top1"])
lo, hi = wilson_ci(int(curve[bn]["top1"] * len(he_i)), len(he_i))
print(f"\nbest {curve[bn]['top1']:.3f} at {bn} vocabulary relations, "
      f"CI95 [{lo:.3f}, {hi:.3f}]")
print("reference points, same eval set and candidate list:")
print("  D114 corpus-fit basis, 18 corpus relations trained   0.286")
print("  D115 scaling curve, 19 corpus relations trained      0.240")
print("  (both trained on corpus relations; this run trained on NONE)")

out = {
    "manifest": run_manifest(seed=SEED, config={
        "SIZES": SIZES, "K_BASIS": K_BASIS, "N_ALIAS": N_ALIAS,
        "held_out": HELD_R}),
    "n_eval_questions": len(he_i), "chance_top1": round(1 / len(RELS), 4),
    "curve": curve,
    "reference": {"d114_corpus_fit_18_rels": 0.286,
                  "d115_19_rels": 0.240},
    "scope": ("Head trained ONLY on synthetic questions built from Wikidata "
              "property aliases; subjects are filler names. All 26 corpus "
              "relations are held out, a stricter setting than D113-D115 "
              "where 18 were trained. Evaluation set, candidate list and "
              "chance rate are identical to D115 so numbers compare. "
              "Single-hop."),
}
(ROOT / "results" / "exp23_vocabpretrain.json").write_text(
    json.dumps(out, indent=1))
print("\n[done] results/exp23_vocabpretrain.json")

# ---------------------------------------------------------------------------
# 3,000 vocabulary relations lost to 19 corpus ones. But that run confounds
# "more training relations" with "a basis and a training distribution both
# fit to mostly off-domain properties" — Wikidata's tail is database
# identifiers and taxon codes, nothing like our biographical relations.
#
# So select the vocabulary by DOMAIN instead of at random: the N properties
# whose labels are nearest the 18 KNOWN corpus relations. Selection uses only
# known relations; the 8 held-out ones are never involved. If a
# domain-filtered 800 beats a random 800, distribution match — not scale —
# is what governs this mechanism, on the training axis as well as the basis
# axis.
# ---------------------------------------------------------------------------
KNOWN_R = [r for r in RELS if r not in set(HELD_R)]
known_c = P.unit(np.stack([V[r] for r in KNOWN_R]).mean(0))
sim = np.array([float(VV[p] @ known_c) for p in cand])
near = [cand[i] for i in np.argsort(-sim)]
print(f"\ndomain-filtered vocabulary (nearest the {len(KNOWN_R)} KNOWN "
      f"corpus relations; held-out 8 never used to select)")
print("  nearest: " + ", ".join(props[p]["label"] for p in near[:6]))
print("  farthest: " + ", ".join(props[p]["label"] for p in near[-4:]))


def run_ordered(order, n, seed=0):
    global cand
    keep, cand = cand, list(order)
    try:
        return run(n, seed=seed)
    finally:
        cand = keep


print(f"\n{'n_vocab_rels':>13} {'random':>9} {'domain-filtered':>17}")
cmp_ = {}
for n in (50, 200, 800):
    r_rand = curve[n]["top1"]
    h1, mrr, prec, tal = run_ordered(near, n)
    cmp_[n] = {"random_top1": r_rand, "domain_top1": round(h1, 4),
               "domain_e2e_precision": round(prec, 4)}
    print(f"{n:13d} {r_rand:9.3f} {h1:17.3f}", flush=True)

bn2 = max(cmp_, key=lambda n: cmp_[n]["domain_top1"])
lo2, hi2 = wilson_ci(int(cmp_[bn2]["domain_top1"] * len(he_i)), len(he_i))
print(f"\nbest domain-filtered {cmp_[bn2]['domain_top1']:.3f} at n={bn2} "
      f"CI95 [{lo2:.3f}, {hi2:.3f}]  e2e precision "
      f"{cmp_[bn2]['domain_e2e_precision']:.3f}")
out["domain_filtered"] = cmp_
(ROOT / "results" / "exp23_vocabpretrain.json").write_text(
    json.dumps(out, indent=1))
print("[done] domain-filtered results appended")
