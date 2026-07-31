"""Can the answer-type gate recover Gemma's refusal? (the deciding experiment)

D170 left the encoder choice on a knife edge. The two curves cross at ≈0.52
novel-unanswerable refusal: Gemma answers more below it, M3 refuses better
above it. Saturated, M3 reaches 0.785 correct / 0.205 wrong against Gemma's
0.866 / 0.094 — a higher ceiling at half the error rate, but refusal that
falls away faster. **Gemma is better at answering and worse at knowing when
not to**, and this system is built around refusing rather than guessing, so on
current evidence M3 wins where it matters.

But every run in D164–D170 used only the **residual threshold**. The
answer-type gate (D134) is a *different mechanism* and was absent from all of
them: it compares the returned objects against the range centroid of the
relation the **target** asked for — read off the target rather than the walked
path, which is what keeps it non-circular — and it lifted M3's not-applicable
refusal from **0.050 to 0.693** without touching the residual.

So the question the arc now turns on: does it do the same for Gemma? If it
lifts Gemma's frontier above M3's in the strict region, the swap is justified
at the operating point this project cares about. If not, the arc ends with an
encoder better at what this project values less.

**Calibration is closed-form and per-encoder.** A cosine threshold no more
transfers across encoders than a residual norm does (D125), so the type
threshold is the **p25 of within-relation type fit over TRAINED relations**
(D142's store-derived rule — no labelled data, and the novel populations never
influence it, law #6). Range centroids are computed from the store for every
relation including held-out ones: a held-out relation is absent from *training*
but its claims are in the store, so its centroid is available without
retraining — which is the reindex-free property doing real work.

Four curves: {M3, Gemma} × {gate off, gate on}, each swept across the residual
threshold and traced as novel answering vs novel-unanswerable refusal.

**Registered prediction.** The gate lifts both encoders and helps Gemma more,
because Gemma's failure is specifically discriminating answerable from
unanswerable and the gate attacks exactly that. I do NOT expect it to close the
gap entirely in the strict region — D170's crossover is wide there (−0.11 at
0.80 refusal) and a single mechanism rarely moves a frontier that far.

Usage: .venv/bin/python scripts/exp62_typegate_encoder.py
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
from codec.manifest import run_manifest                          # noqa: E402
from foundation.kb import KB                                     # noqa: E402

SEED, MIN_GAIN, K_BASIS = 0, 0.2, 48
N_HOLD_REL, INST_FRAC, CAP_UNANS = 12, 0.20, 2000
GRID = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.4, 1.6, 2.0)
MATCH_AT = (0.30, 0.40, 0.50, 0.60, 0.70, 0.80)

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
OBJS = sorted({o for (s, r) in gold for o in gold[(s, r)]})
print(f"{len(RELS)} relations ({len(TRAINED_R)} trained), {len(texts)} "
      f"questions, {len(OBJS)} distinct objects for range centroids",
      flush=True)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402


def unit(a):
    return a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9)


def load(arm):
    """Question + label embeddings, plus OBJECT embeddings for the gate."""
    ocache = ROOT / "results" / f"exp62_{arm}_obj.npz"
    if arm == "m3":
        z = np.load(ROOT / "results" / "exp31_emb.npz", allow_pickle=True)
        assert list(z["texts"]) == texts, "population drifted from exp31"
        Z, Zl = z["Z"], z["Zl"]
    else:
        z = np.load(ROOT / "results" / "exp60_gemma_emb.npz", allow_pickle=True)
        assert list(z["texts"]) == texts, "exp60 gemma cache misaligned"
        Z, Zl = z["Z"], z["Zl"]
    if ocache.exists():
        zo = np.load(ocache, allow_pickle=True)
        assert list(zo["objs"]) == OBJS, f"object cache misaligned for {arm}"
        return Z, Zl, zo["Zo"]
    print(f"  embedding {len(OBJS)} objects under {arm}...", flush=True)
    if arm == "m3":
        import v06_pipeline as P
        Zo = unit(P.embed_texts(OBJS)).astype(np.float32)
    else:
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer("google/embeddinggemma-300m", device="cuda")
        Zo = m.encode(OBJS, prompt_name="STS", batch_size=128,
                      convert_to_numpy=True, normalize_embeddings=True,
                      show_progress_bar=False).astype(np.float32)
    np.savez(ocache, Zo=Zo, objs=np.array(OBJS))
    return Z, Zl, Zo


def emb(Z, key):
    a, b = index[key]
    return Z[a:b]


CURVES, META = {}, {}
for arm in ("m3", "gemma"):
    Z, Zl, Zo = load(arm)
    OI = {o: i for i, o in enumerate(OBJS)}
    RAW = {r: Zl[i] for i, r in enumerate(RELS)}
    PC = unit(fit_anchors(np.stack([RAW[r] for r in TRAINED_R]), K_BASIS,
                          seed=SEED))
    C = {r: unit(RAW[r] @ PC.T) for r in RELS}
    # range centroids: closed-form from the store, for EVERY relation
    # including held-out ones — their claims are in the store even though
    # they never entered training
    CENT, fits = {}, []
    for r in RELS:
        ids = [OI[o] for (s, rr_) in gold if rr_ == r
               for o in sorted(gold[(s, rr_)]) if o in OI][:400]
        if ids:
            CENT[r] = unit(Zo[ids].mean(0))
    for r in TRAINED_R:                       # calibrate on TRAINED only
        ids = [OI[o] for (s, rr_) in gold if rr_ == r
               for o in sorted(gold[(s, rr_)]) if o in OI][:400]
        if ids and r in CENT:
            fits += list(Zo[ids] @ CENT[r])
    TTHR = float(np.percentile(fits, 25))
    print(f"\n=== {arm} === type threshold p25 = {TTHR:.4f} "
          f"(from {len(fits)} within-relation fits, trained only)", flush=True)

    Xs, Ys = [], []
    for key in ("train_d1", "train_d2", "train_d3"):
        E = emb(Z, key)
        for j, a in enumerate(BAG[key]):
            Xs.append(E[j])
            Ys.append(sum(C[r] for r in a["chain"]))
    X, Y = torch.tensor(np.stack(Xs)), torch.tensor(np.stack(Ys))
    torch.manual_seed(SEED)
    hd = nn.Sequential(nn.Linear(Z.shape[1], 512), nn.GELU(),
                       nn.Linear(512, K_BASIS))
    op = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(X)).split(512):
            op.zero_grad()
            ((hd(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
            op.step()
    hd.eval()
    META[arm] = {"type_threshold_p25": round(TTHR, 4), "n_fits": len(fits)}

    def run(key, max_steps, answerable, thr, gate):
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
                                                   np.zeros(K_BASIS,
                                                            np.float32))))
            refuse = (not path) or (not frontier) or rn > thr
            if not refuse and gate and frontier:
                # D134's canonical form: subtract hops ALREADY walked so
                # `want` is the FINAL relation's coordinate. The first
                # version used the raw target, which at depth 2 is argmax
                # over C[r1]+C[r2] and recovers neither hop (D173).
                consumed = (sum((C[r] for r in path[:-1]),
                                np.zeros(K_BASIS, np.float32))
                            if len(path) > 1
                            else np.zeros(K_BASIS, np.float32))
                r_ask = max(CENT,
                            key=lambda r: float((tgt[j] - consumed) @ C[r]))
                ids = [OI[o] for o in sorted(frontier) if o in OI]
                if ids:
                    tf = float(np.mean(Zo[ids] @ CENT[r_ask]))
                    if tf < TTHR:
                        refuse = True
            if refuse:
                c["abstain"] += 1
            elif answerable:
                c["correct" if set(frontier) & set(a["answers"]) else "wrong"] += 1
            else:
                c["wrong"] += 1
        n = max(sum(c.values()), 1)
        return {k: round(c[k] / n, 4) for k in
                ("correct", "wrong", "abstain")}

    for gate in (False, True):
        tag = f"{arm}_gate{'ON' if gate else 'OFF'}"
        pts = []
        print(f"  {tag}: {'thr':>5} {'novel_corr':>11} {'novel_wrong':>12} "
              f"{'unansNov_ref':>13} {'train_d1':>9}")
        for t in GRID:
            nv = run("eval_d1_novel1", 2, True, t, gate)
            un = run("unans_novel", 3, False, t, gate)
            tr = run("train_d1", 2, True, t, gate)
            pts.append({"thr": t, "novel_correct": nv["correct"],
                        "novel_wrong": nv["wrong"],
                        "unans_novel_refuse": un["abstain"],
                        "train_d1_correct": tr["correct"]})
            print(f"  {'':>{len(tag)}}  {t:5.2f} {nv['correct']:11.4f} "
                  f"{nv['wrong']:12.4f} {un['abstain']:13.4f} "
                  f"{tr['correct']:9.4f}", flush=True)
        CURVES[tag] = pts


def at_refusal(pts, target):
    xs = np.array([p["unans_novel_refuse"] for p in pts])
    ys = np.array([p["novel_correct"] for p in pts])
    o = np.argsort(xs)
    xs, ys = xs[o], ys[o]
    if target < xs[0] or target > xs[-1]:
        return None
    return float(np.interp(target, xs, ys))


print(f"\n=== novel answering at matched novel-unanswerable refusal ===")
names = ["m3_gateOFF", "m3_gateON", "gemma_gateOFF", "gemma_gateON"]
print(f"  {'refusal':>8} " + " ".join(f"{n:>14}" for n in names))
table = {}
for rf in MATCH_AT:
    vals = {n: at_refusal(CURVES[n], rf) for n in names}
    table[str(rf)] = {n: (round(v, 4) if v is not None else None)
                      for n, v in vals.items()}
    print(f"  {rf:8.2f} " + " ".join(
        (f"{vals[n]:14.4f}" if vals[n] is not None else f"{'-':>14}")
        for n in names))

gains = {}
for arm in ("m3", "gemma"):
    ds = [table[str(r)][f"{arm}_gateON"] - table[str(r)][f"{arm}_gateOFF"]
          for r in MATCH_AT
          if table[str(r)][f"{arm}_gateON"] is not None
          and table[str(r)][f"{arm}_gateOFF"] is not None]
    gains[f"gate_gain_{arm}"] = round(float(np.mean(ds)), 4) if ds else None
strict = [r for r in MATCH_AT if r >= 0.60]
head2head = {}
for r in strict:
    a, b = table[str(r)]["m3_gateON"], table[str(r)]["gemma_gateON"]
    if a is not None and b is not None:
        head2head[str(r)] = round(b - a, 4)
print(f"\n  gate gain (mean over refusal levels): {gains}")
print(f"  gemma-vs-m3 WITH gate, strict region (refusal >= 0.60): {head2head}")

hv = [v for v in head2head.values()]
mh = float(np.mean(hv)) if hv else 0.0
if mh > 0.02:
    verdict = (f"GATE RECOVERS IT — with the answer-type gate on both arms, "
               f"Gemma now leads M3 by {mh:+.4f} in the strict region where "
               f"this system operates. The encoder swap is justified.")
elif mh > -0.02:
    verdict = (f"PARITY — with the gate on both arms the encoders are within "
               f"noise in the strict region ({mh:+.4f}). The swap is neither "
               f"justified nor refuted on refusal grounds, and should be "
               f"decided on the other axes (error rate, ceiling, tokenizer).")
else:
    verdict = (f"GATE DOES NOT RECOVER IT — Gemma still trails by {mh:+.4f} "
               f"in the strict region with the gate on both arms. The "
               f"identification advantage does not reach the operating point "
               f"this project cares about, and M3 should stay.")
print(f"\n=== VERDICT ===\n  {verdict}")

out = {"manifest": run_manifest(seed=SEED, config={"GRID": list(GRID),
                                                   "K_BASIS": K_BASIS,
                                                   "MATCH_AT": list(MATCH_AT)}),
       "meta": META, "curves": CURVES, "matched_at_refusal": table,
       "gate_gain": gains, "gemma_minus_m3_with_gate_strict": head2head,
       "verdict": verdict,
       "registered_prediction": (
           "the gate lifts both encoders and helps Gemma more, since Gemma's "
           "failure is specifically answerable-vs-unanswerable and the gate "
           "attacks exactly that; but it does NOT close the strict-region gap "
           "entirely, which was -0.11 at 0.80 refusal in D170"),
       "scope": ("The deciding experiment for the encoder swap. Every run in "
                 "D164-D170 used only the residual threshold; the answer-type "
                 "gate (D134) is a separate mechanism and was absent from all "
                 "of them. Range centroids are closed-form from the store for "
                 "EVERY relation including held-out ones — a held-out "
                 "relation is absent from training but its claims are in the "
                 "store, so its centroid needs no retraining. The type "
                 "threshold is the p25 of within-relation type fit over "
                 "TRAINED relations only (D142's store-derived rule), "
                 "recomputed per encoder because a cosine threshold no more "
                 "transfers across encoders than a residual norm does (D125). "
                 "Both arms use the same basis (kmeans_label K=48) since "
                 "lda_between was refuted end-to-end at D169. Frontier "
                 "reported as a curve; no operating point is selected from "
                 "novel data.")}
(ROOT / "results" / "exp62_typegate_encoder.json").write_text(
    json.dumps(out, indent=1))
print("\n[done] results/exp62_typegate_encoder.json")
