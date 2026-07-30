"""Does the D165 ordering survive when the STORE participates? (the adoption gate)

Everything in D164–D168 is identification level: argmax over relation
coordinates, no store walk, no residual thresholds. That was deliberate —
thresholds do not transfer across representation dimensionality (D125), so an
end-to-end probe would have confounded encoder quality with calibration. But
D158 measured the store's availability filtering at **+0.515** against greedy
walking's +0.009, which means the store supplies most of the answer and an
ordering measured without it may simply not survive.

So this is the gate before any pipeline change. Two factors, crossed:

  * **encoder** — BGE-M3 (current, 1024-d) vs EmbeddingGemma symmetric (768-d)
  * **basis** — `kmeans_label` K=48 (what the pipeline runs today) vs
    `lda_between` K=32 (what D165 recommends)

Everything else is held: same store, same populations, same head
architecture, same seed, same walk, and **one threshold rule applied
identically to all four arms**, swept on TRAINED populations only so the novel
ones never influence calibration (law #6).

Reported per audit law #7 — answerable and unanswerable never averaged, and
novel-relation populations kept separate from trained ones. The product claim
lives in `novel_d1`: a relation the walker has never trained on, reached
through a real store walk.

**What decides adoption.** If `lda_between` K=32 beats `kmeans_label` K=48 on
novel-relation answering *within* each encoder, the basis change is justified
end-to-end. If Gemma beats M3 at matched basis, the encoder change is. If the
identification-level ordering inverts here, D164–D168 stand as statements
about identification and **must not** be read as pipeline recommendations.

**Registered prediction.** Both orderings hold but compress: the store
supplies most of the signal, so basis quality should matter less end-to-end
than it did in isolation. I expect the Gemma advantage to survive clearly and
the basis advantage to shrink toward noise.

Usage: .venv/bin/python scripts/exp60_endtoend_gate.py [m3|gemma|both]
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

from codec.evals.anchors import fit_anchors                      # noqa: E402
from codec.manifest import run_manifest, wilson_ci               # noqa: E402
from foundation.kb import KB                                     # noqa: E402

SEED, MIN_GAIN = 0, 0.2
N_HOLD_REL, INST_FRAC, CAP_UNANS = 12, 0.20, 2000
GRID = (0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2)
WHICH = sys.argv[1] if len(sys.argv) > 1 else "both"

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


# ---- exp31's populations verbatim, so its M3 cache applies ----
rng = np.random.default_rng(SEED)
HOLD_R = {RELS[i] for i in sorted(rng.permutation(len(RELS))[:N_HOLD_REL])}
TRAINED_R = [r for r in RELS if r not in HOLD_R]
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
                    sorted(rng.choice(len(unans[k]), CAP_UNANS, replace=False))]


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
print(f"{len(RELS)} relations ({len(TRAINED_R)} trained), {len(texts)} "
      f"questions across {len(ORDER)} populations", flush=True)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402


def unit(a):
    return a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9)


def embeddings(arm):
    if arm == "m3":
        z = np.load(ROOT / "results" / "exp31_emb.npz", allow_pickle=True)
        assert list(z["texts"]) == texts, "population drifted from exp31"
        return z["Z"], z["Zl"]
    cache = ROOT / "results" / "exp60_gemma_emb.npz"
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        assert list(z["texts"]) == texts, "cache misaligned; delete it"
        return z["Z"], z["Zl"]
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer("google/embeddinggemma-300m", device="cuda")
    print(f"  embedding {len(texts)} questions under Gemma...", flush=True)
    Z = m.encode(texts, prompt_name="STS", batch_size=128,
                 convert_to_numpy=True, normalize_embeddings=True,
                 show_progress_bar=False).astype(np.float32)
    Zl = m.encode([LABEL[r] for r in RELS], prompt_name="STS", batch_size=128,
                  convert_to_numpy=True, normalize_embeddings=True,
                  show_progress_bar=False).astype(np.float32)
    np.savez(cache, Z=Z, Zl=Zl, texts=np.array(texts))
    return Z, Zl


def emb(Z, key):
    a, b = index[key]
    return Z[a:b]


def make_basis(kind, RAW, Z):
    L_tr = np.stack([RAW[r] for r in TRAINED_R])
    if kind == "kmeans_label_K48":
        return unit(fit_anchors(L_tr, 48, seed=SEED))
    if kind == "lda_between_K32":
        groups = []
        for r in TRAINED_R:
            idx = [i for i, a in enumerate(BAG["train_d1"])
                   if a["chain"][0] == r]
            if idx:
                groups.append(emb(Z, "train_d1")[idx])
        mus = [g.mean(0) for g in groups]
        ns = [len(g) for g in groups]
        M = np.stack(mus)
        mu = np.average(M, axis=0, weights=ns)
        D = (M - mu) * np.sqrt(np.array(ns))[:, None]
        return unit(np.linalg.svd(D, full_matrices=False)[2][:32])
    raise ValueError(kind)


def train_head(Z, C, dim):
    Xs, Ys = [], []
    for key in ("train_d1", "train_d2", "train_d3"):
        E = emb(Z, key)
        for j, a in enumerate(BAG[key]):
            Xs.append(E[j])
            Ys.append(sum(C[r] for r in a["chain"]))
    X, Y = torch.tensor(np.stack(Xs)), torch.tensor(np.stack(Ys))
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
    return hd


def run(Z, C, hd, dim, key, max_steps, answerable, thr):
    rows, E = BAG[key], emb(Z, key)
    with torch.no_grad():
        tgt = hd(torch.tensor(E)).numpy()
    c = collections.Counter()
    for j, a in enumerate(rows):
        resid, frontier, path = tgt[j].copy(), {a["subject"]}, []
        for _ in range(max_steps):
            best, bg = None, MIN_GAIN
            for r in options_at(frontier):
                g = float(resid @ C[r])
                if g > bg:
                    best, bg = r, g
            if best is None:
                break
            nxt = step(frontier, best)
            if not nxt:
                break
            frontier, path = nxt, path + [best]
            resid = resid - C[best]
        rn = float(np.linalg.norm(tgt[j] - sum((C[r] for r in path),
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


SPECS = [("train_d1", 2, True), ("train_d2", 3, True),
         ("unans_trained", 3, False), ("eval_d1_inst", 2, True),
         ("eval_d1_novel1", 2, True), ("eval_d2_novel1", 3, True),
         ("unans_novel", 3, False)]
SPECS = [s for s in SPECS if s[0] in BAG and BAG[s[0]]]
ARMS = []
for e in (["m3"] if WHICH in ("m3", "both") else []) + \
        (["gemma"] if WHICH in ("gemma", "both") else []):
    for b in ("kmeans_label_K48", "lda_between_K32"):
        ARMS.append((e, b))

OUT = {}
_cache = {}
for enc, bkind in ARMS:
    if enc not in _cache:
        _cache[enc] = embeddings(enc)
    Z, Zl = _cache[enc]
    RAW = {r: Zl[i] for i, r in enumerate(RELS)}
    PC = make_basis(bkind, RAW, Z)
    dim = PC.shape[0]
    C = {r: unit(RAW[r] @ PC.T) for r in RELS}
    hd = train_head(Z, C, dim)
    name = f"{enc}__{bkind}"
    print(f"\n=== {name} (dim {dim}) ===", flush=True)
    sweep = {}
    for t in GRID:
        s = {k: run(Z, C, hd, dim, k, ms, ans, t)
             for k, ms, ans in SPECS if k in ("train_d1", "train_d2",
                                              "unans_trained")}
        sweep[t] = s
    # one rule, all arms: maximise the worst TRAINED population (law #6)
    best = max(GRID, key=lambda t: min(sweep[t]["train_d1"]["correct"],
                                       sweep[t]["train_d2"]["correct"],
                                       sweep[t]["unans_trained"]["abstain"]))
    res = {k: run(Z, C, hd, dim, k, ms, ans, best) for k, ms, ans in SPECS}
    OUT[name] = {"threshold": best, "dim": dim, "results": res}
    print(f"  THR={best} (worst trained "
          f"{min(sweep[best]['train_d1']['correct'], sweep[best]['train_d2']['correct'], sweep[best]['unans_trained']['abstain']):.3f})")
    for k, ms, ans in SPECS:
        v = res[k]
        m = "correct" if ans else "abstain"
        print(f"    {k:18s} {m:8s} {v[m]:.4f}  wrong {v['wrong']:.4f}  "
              f"n={v['n']}")

print(f"\n{'arm':>34} {'novel_d1':>9} {'novel_d2':>9} {'train_d1':>9} "
      f"{'unans_nov':>10}")
for name, a in OUT.items():
    r = a["results"]
    print(f"{name:>34} {r.get('eval_d1_novel1', {}).get('correct', 0):9.4f} "
          f"{r.get('eval_d2_novel1', {}).get('correct', 0):9.4f} "
          f"{r['train_d1']['correct']:9.4f} "
          f"{r.get('unans_novel', {}).get('abstain', 0):10.4f}")


# ---------------------------------------------------------------------------
# MATCHED COVERAGE. The per-arm rule above ("maximise the worst trained
# population") includes unanswerable REFUSAL in the min, so it rewards
# abstention — and it pushed the 32-d arm to a high-refusal operating point
# where it answers 31% of novel questions at 98% precision while the 48-d arm
# answers 79% at 95%. Those are two points on a frontier, not two qualities.
# Compounding it, a residual norm of 0.6 is not the same quantity in 32
# dimensions as in 48 (D125). Comparing representations at different operating
# points is the defect D159 had to correct, so the comparison is redone at
# matched coverage — matched on a TRAINED population, never on the novel one,
# so calibration still never sees the evaluation set (law #6).
# ---------------------------------------------------------------------------
REF = "m3__kmeans_label_K48"          # what the pipeline runs today
print(f"\n=== matched coverage (train_d1 answered-fraction of {REF}) ===")
matched = {}
if REF in OUT:
    def cov(v):
        return round(v["correct"] + v["wrong"], 4)

    ref_state = _cache[REF.split("__")[0]]
    for name, a in OUT.items():
        enc, bkind = name.split("__")
        Z, Zl = _cache[enc]
        RAW = {r: Zl[i] for i, r in enumerate(RELS)}
        PC = make_basis(bkind, RAW, Z)
        dim = PC.shape[0]
        C = {r: unit(RAW[r] @ PC.T) for r in RELS}
        hd = train_head(Z, C, dim)
        if name == REF:
            target = cov(OUT[REF]["results"]["train_d1"])
        best_t, best_gap = None, 9e9
        for t in GRID:
            c = cov(run(Z, C, hd, dim, "train_d1", 2, True, t))
            if abs(c - target) < best_gap:
                best_t, best_gap = t, abs(c - target)
        res = {k: run(Z, C, hd, dim, k, ms, ans, best_t)
               for k, ms, ans in SPECS}
        matched[name] = {"threshold": best_t,
                         "train_d1_coverage": cov(res["train_d1"]),
                         "results": res}
        r = res
        print(f"  {name:34s} THR={best_t:<4} cov={cov(r['train_d1']):.4f}  "
              f"novel_d1 {r.get('eval_d1_novel1', {}).get('correct', 0):.4f}  "
              f"unans_nov {r.get('unans_novel', {}).get('abstain', 0):.4f}")


def nov(name, table=None):
    t = table if table is not None else OUT
    return t[name]["results"].get("eval_d1_novel1", {}).get("correct", 0.0)


findings = {}
for enc in sorted({a for a, _ in ARMS}):
    a, b = f"{enc}__kmeans_label_K48", f"{enc}__lda_between_K32"
    if a in OUT and b in OUT:
        findings[f"basis_gain_{enc}"] = round(nov(b) - nov(a), 4)
for bk in ("kmeans_label_K48", "lda_between_K32"):
    a, b = f"m3__{bk}", f"gemma__{bk}"
    if a in OUT and b in OUT:
        findings[f"encoder_gain_{bk}"] = round(nov(b) - nov(a), 4)
print("\n=== gains on novel-relation depth-1 (the product claim) ===")
for k, v in findings.items():
    print(f"  {k:32s} {v:+.4f}")

mfind = {}
if matched:
    for enc in sorted({a for a, _ in ARMS}):
        a, b = f"{enc}__kmeans_label_K48", f"{enc}__lda_between_K32"
        if a in matched and b in matched:
            mfind[f"basis_gain_{enc}"] = round(nov(b, matched)
                                               - nov(a, matched), 4)
    for bk in ("kmeans_label_K48", "lda_between_K32"):
        a, b = f"m3__{bk}", f"gemma__{bk}"
        if a in matched and b in matched:
            mfind[f"encoder_gain_{bk}"] = round(nov(b, matched)
                                                - nov(a, matched), 4)
    print("\n=== gains at MATCHED coverage (the comparison that counts) ===")
    for k, v in mfind.items():
        print(f"  {k:32s} {v:+.4f}")

use = mfind if mfind else findings
bg = [v for k, v in use.items() if k.startswith("basis_gain")]
eg = [v for k, v in use.items() if k.startswith("encoder_gain")]
mb = float(np.mean(bg)) if bg else 0.0
me = float(np.mean(eg)) if eg else 0.0
parts = [f"at matched coverage: encoder change "
         f"{'CONFIRMED' if me > 0.02 else 'NOT confirmed'} ({me:+.4f})",
         f"basis change {'CONFIRMED' if mb > 0.02 else 'NOT confirmed'} "
         f"({mb:+.4f})"]
verdict = "; ".join(parts)
print(f"\n=== VERDICT ===\n  {verdict}")

out = {"manifest": run_manifest(seed=SEED, config={"GRID": list(GRID),
                                                   "N_HOLD_REL": N_HOLD_REL,
                                                   "MIN_GAIN": MIN_GAIN}),
       "n_relations": len(RELS), "n_trained": len(TRAINED_R),
       "population_sizes": {k: len(BAG[k]) for k in ORDER},
       "arms": OUT, "gains_novel_d1_own_threshold": findings,
       "matched_coverage": matched, "gains_novel_d1_matched": mfind,
       "verdict": verdict,
       "registered_prediction": (
           "both orderings hold but compress; the Gemma advantage survives "
           "clearly, the basis advantage shrinks toward noise, because D158 "
           "measured the store as supplying +0.515 against the walk's +0.009"),
       "scope": ("The adoption gate. D164-D168 are identification level — no "
                 "store walk, no thresholds — and D158 measured store "
                 "filtering at +0.515, so an ordering measured without the "
                 "store may not survive with it. Encoder x basis crossed on "
                 "exp31's populations, with ONE threshold rule applied "
                 "identically to every arm and swept on TRAINED populations "
                 "only (law #6). Answerable and unanswerable never averaged "
                 "(law #7); novel-relation populations kept separate. If the "
                 "identification-level ordering inverts here, D164-D168 are "
                 "statements about identification and must not be read as "
                 "pipeline recommendations.")}
(ROOT / "results" / "exp60_endtoend_gate.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp60_endtoend_gate.json")
