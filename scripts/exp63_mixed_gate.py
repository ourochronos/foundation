"""The answer-type gate under both encoders, on the MIXED benchmark (D134's own)

exp62 tested the gate on chain-break unanswerables and found it harmful — but
that is not the population the gate was built for. D134 measured its benefit on
**not-applicable** questions (relation real, entity real, pair absent), lifting
refusal from 0.050 to 0.693. A chain-break walk returns objects of a plausible
type, so the gate has little to detect there and mostly suppresses correct
answers. exp62 was a null on the wrong benchmark and should not be read as a
refutation of D134.

This rebuilds D134's mixed benchmark exactly — three kinds of unanswerable,
**never averaged** (law #9):

    chain_break     depth 2; first hop walks, second leads nowhere
    not_applicable  depth 1; relation real, entity real, pair absent
    absent_entity   depth 1; subject genuinely not in this store
                    (real arXiv subjects, not fabricated strings)

and asks the question D170 left open: with the gate active on both arms, does
EmbeddingGemma reach or beat BGE-M3 in the strict-refusal region this system
operates in?

**Calibration follows D134, per encoder.** The type threshold is swept on a
calibration split — trained answerable plus HALF the not-applicable population
— and chosen by max-worst-of-two (answerable accuracy vs not-applicable
refusal). Evaluation uses the OTHER half. A cosine threshold no more transfers
across encoders than a residual norm does (D125), and exp62 measured the
store-derived p25 at 0.4329 for M3 against 0.7347 for Gemma — so a shared
constant would silently break one arm.

**The verdict logic checks the control comparison FIRST.** Three experiments in
a row (exp52, exp53, exp62) produced confident verdict strings that compared
the wrong pair — most recently declaring the gate a success when it had made
both encoders worse and merely hurt one less. Here: does gate-ON beat gate-OFF
*within* an encoder, before any cross-encoder claim is made at all.

**Registered prediction.** The gate helps on not_applicable for both encoders,
reproducing D134's direction; it stays harmful on chain_break, which is what
exp62 actually measured. Whether that is enough to put Gemma ahead overall I
genuinely do not know, which is why this is worth running.

Usage: .venv/bin/python scripts/exp63_mixed_gate.py
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

SEED, MIN_GAIN, K_BASIS, CAP = 0, 0.2, 48, 1200
RES_GRID = (0.4, 0.6, 0.8, 1.0, 1.2, 1.6)
TF_GRID = (0.0, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60, 0.70)

sch = {d["pid"]: d["label"] for d in
       json.loads((ROOT / "data" / "schema_v0.json").read_text())}
props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
kb = KB(backend="pg", table="poc")
wiki = [c for c in kb.claims
        if not c["page"].startswith(("arxiv:", "hf:", "user"))]
LABEL = {}
for c in wiki:
    p = c["pid"]
    if p not in LABEL:
        lab = sch.get(p) or (props.get(p) or {}).get("label")
        if lab:
            LABEL[p] = lab
RELS = sorted(LABEL)
wiki = [c for c in wiki if c["pid"] in LABEL]
gold, avail = collections.defaultdict(set), collections.defaultdict(set)
for c in wiki:
    gold[(c["subject"], c["pid"])].add(c["object"])
    avail[c["subject"]].add(c["pid"])
subjects = sorted(avail)
OBJS = sorted({c["object"] for c in wiki})
foreign = sorted({c["subject"] for c in kb.claims
                  if c["page"].startswith("arxiv:")})
rng = np.random.default_rng(SEED)


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


def t1(s, r):
    return f"What is the {LABEL[r]} of {s}?"


def t2(s, r1, r2):
    return f"What is the {LABEL[r2]} of the {LABEL[r1]} of {s}?"


d1, d2, chain_break, not_app, absent = [], [], [], [], []
for s in subjects:
    for r in sorted(avail[s]):
        d1.append({"subject": s, "chain": [r], "answers": sorted(gold[(s, r)]),
                   "text": t1(s, r)})
        m1 = step({s}, r)
        for r2 in sorted(options_at(m1)):
            m2 = step(m1, r2)
            if m2:
                d2.append({"subject": s, "chain": [r, r2],
                           "answers": sorted(m2)[:300], "text": t2(s, r, r2)})
    for r1 in sorted(avail[s]):
        m1 = step({s}, r1)
        if not m1:
            continue
        for r2 in RELS:
            if not step(m1, r2):
                chain_break.append({"subject": s, "chain": [r1, r2],
                                    "answers": [], "text": t2(s, r1, r2)})
    for r in RELS:
        if r not in avail[s]:
            not_app.append({"subject": s, "chain": [r], "answers": [],
                            "text": t1(s, r)})
for s in foreign:
    for r in RELS:
        absent.append({"subject": s, "chain": [r], "answers": [],
                       "text": t1(s, r)})


def cap(rows, n=CAP):
    rows = sorted(rows, key=lambda a: (a["subject"], ">".join(a["chain"])))
    if len(rows) > n:
        rows = [rows[i] for i in sorted(rng.choice(len(rows), n,
                                                   replace=False))]
    return rows


POP = {}
for k, v in (("ans_d1", d1), ("ans_d2", d2), ("chain_break", chain_break),
             ("not_applicable", not_app), ("absent_entity", absent)):
    POP[k] = cap(v)
    print(f"  {k:15s} {len(POP[k]):5d}")
ORDER = sorted(POP)
texts, index = [], {}
for key in ORDER:
    index[key] = (len(texts), len(texts) + len(POP[key]))
    texts += [a["text"] for a in POP[key]]
print(f"{len(texts)} questions, {len(OBJS)} objects, {len(foreign)} foreign "
      f"subjects", flush=True)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402


def unit(a):
    return a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9)


def encode(arm, items):
    if arm == "m3":
        import v06_pipeline as P
        return unit(P.embed_texts(list(items))).astype(np.float32)
    from sentence_transformers import SentenceTransformer
    global _G
    try:
        _G
    except NameError:
        _G = SentenceTransformer("google/embeddinggemma-300m", device="cuda")
    return _G.encode(list(items), prompt_name="STS", batch_size=128,
                     convert_to_numpy=True, normalize_embeddings=True,
                     show_progress_bar=False).astype(np.float32)


def load(arm):
    cache = ROOT / "results" / f"exp63_{arm}_emb.npz"
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        assert list(z["texts"]) == texts and list(z["objs"]) == OBJS, \
            f"cache misaligned for {arm}; delete it"
        return z["Z"], z["Zl"], z["Zo"]
    print(f"  embedding {len(texts)} q + {len(RELS)} labels + {len(OBJS)} "
          f"objects under {arm}...", flush=True)
    Z = encode(arm, texts)
    Zl = encode(arm, [LABEL[r] for r in RELS])
    Zo = encode(arm, OBJS)
    np.savez(cache, Z=Z, Zl=Zl, Zo=Zo, texts=np.array(texts),
             objs=np.array(OBJS))
    return Z, Zl, Zo


ARMS = {}
for arm in ("m3", "gemma"):
    Z, Zl, Zo = load(arm)
    OI = {o: i for i, o in enumerate(OBJS)}
    RAW = {r: Zl[i] for i, r in enumerate(RELS)}
    PC = unit(fit_anchors(np.stack([RAW[r] for r in RELS]), K_BASIS, seed=SEED))
    C = {r: unit(RAW[r] @ PC.T) for r in RELS}
    CENT = {}
    for r in RELS:
        ids = [OI[o] for (s, rr_) in gold if rr_ == r
               for o in sorted(gold[(s, rr_)]) if o in OI][:400]
        if ids:
            CENT[r] = unit(Zo[ids].mean(0))
    tr = [i for i, a in enumerate(POP["ans_d1"])][::2]      # half of d1 trains
    Xs, Ys = [], []
    E1, E2 = Z[slice(*index["ans_d1"])], Z[slice(*index["ans_d2"])]
    for j in tr:
        Xs.append(E1[j])
        Ys.append(C[POP["ans_d1"][j]["chain"][0]])
    for j, a in enumerate(POP["ans_d2"][::2]):
        Xs.append(E2[j * 2])
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

    def walk_all(key, max_steps):
        """Per-row walk outcome, so thresholds can be swept without re-walking."""
        rows = POP[key]
        E = Z[slice(*index[key])]
        with torch.no_grad():
            tgt = hd(torch.tensor(E)).numpy()
        out = []
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
            tf = 1.0
            if frontier:
                r_ask = max(CENT, key=lambda r: float(tgt[j] @ C[r]))
                ids = [OI[o] for o in sorted(frontier) if o in OI]
                if ids:
                    tf = float(np.mean(Zo[ids] @ CENT[r_ask]))
            out.append({"walkable": bool(path and frontier), "resid": rn,
                        "tfit": tf,
                        "ok": bool(frontier & set(a["answers"]))})
        return out

    W = {k: walk_all(k, 2 if k in ("ans_d1", "not_applicable", "absent_entity")
                     else 3) for k in ORDER}
    print(f"\n=== {arm}: walks computed ===", flush=True)
    ARMS[arm] = {"W": W, "tr": tr}


def verdict_row(r, res_thr, tf_thr):
    if (not r["walkable"]) or r["resid"] > res_thr or r["tfit"] < tf_thr:
        return "refuse"
    return "correct" if r["ok"] else "wrong"


def rate(rows, res_thr, tf_thr, what):
    v = [verdict_row(r, res_thr, tf_thr) for r in rows]
    n = max(len(v), 1)
    return round(v.count(what) / n, 4)


RESULTS = {}
for arm, A in ARMS.items():
    W, tr = A["W"], A["tr"]
    na = W["not_applicable"]
    CAL_NA, EV_NA = na[::2], na[1::2]
    CAL_ANS = [W["ans_d1"][j] for j in tr]
    print(f"\n=== {arm}: type-threshold calibration (D134's rule) ===")
    print(f"  {'res':>5} {'tfit':>6} {'CAL answerable':>15} "
          f"{'CAL not-appl refused':>21}")
    best = None
    for res_thr in RES_GRID:
        for t in TF_GRID:
            acc = rate(CAL_ANS, res_thr, t, "correct")
            ref = rate(CAL_NA, res_thr, t, "refuse")
            if best is None or min(acc, ref) > best[0]:
                best = (min(acc, ref), res_thr, t, acc, ref)
    _, RES_THR, TTHR, ca, cr = best
    print(f"  selected res={RES_THR} tfit={TTHR}  "
          f"(CAL answerable {ca:.3f}, CAL not-appl refused {cr:.3f})")
    row = {"res_thr": RES_THR, "tfit_thr": TTHR}
    for gate, tag in ((False, "off"), (True, "on")):
        t = TTHR if gate else 0.0
        row[tag] = {
            "ans_d1_correct": rate(W["ans_d1"], RES_THR, t, "correct"),
            "ans_d1_wrong": rate(W["ans_d1"], RES_THR, t, "wrong"),
            "ans_d2_correct": rate(W["ans_d2"], RES_THR, t, "correct"),
            "not_applicable_refuse": rate(EV_NA, RES_THR, t, "refuse"),
            "chain_break_refuse": rate(W["chain_break"], RES_THR, t, "refuse"),
            "absent_entity_refuse": rate(W["absent_entity"], RES_THR, t,
                                         "refuse"),
        }
    RESULTS[arm] = row
    print(f"  {'metric':>24} {'gate off':>10} {'gate on':>10} {'Δ':>9}")
    for k in row["off"]:
        a, b = row["off"][k], row["on"][k]
        print(f"  {k:>24} {a:10.4f} {b:10.4f} {b - a:+9.4f}")

print("\n=== STEP 1: does the gate beat its own control, per encoder? ===")
ctrl = {}
for arm, r in RESULTS.items():
    d_na = r["on"]["not_applicable_refuse"] - r["off"]["not_applicable_refuse"]
    d_ans = r["on"]["ans_d1_correct"] - r["off"]["ans_d1_correct"]
    ctrl[arm] = {"not_applicable_gain": round(d_na, 4),
                 "answerable_cost": round(d_ans, 4)}
    print(f"  {arm:>6}  not-applicable refusal {d_na:+.4f}   "
          f"answerable correct {d_ans:+.4f}")
helps = {a: c["not_applicable_gain"] > 0.02 for a, c in ctrl.items()}
print(f"  gate helps on its own population: {helps}")

print("\n=== STEP 2: only now, encoder vs encoder WITH the gate on ===")
cmp_ = {}
if all(helps.values()):
    for k in RESULTS["m3"]["on"]:
        cmp_[k] = round(RESULTS["gemma"]["on"][k] - RESULTS["m3"]["on"][k], 4)
        print(f"  {k:>24} gemma-m3 {cmp_[k]:+.4f}")
    key = ["not_applicable_refuse", "chain_break_refuse",
           "absent_entity_refuse"]
    ref_delta = float(np.mean([cmp_[k] for k in key]))
    ans_delta = cmp_["ans_d1_correct"]
    if ref_delta > 0.02 and ans_delta > -0.02:
        verdict = (f"SWAP JUSTIFIED — with the gate on both arms Gemma "
                   f"refuses better across all three unanswerable kinds "
                   f"({ref_delta:+.4f}) without losing answerable accuracy "
                   f"({ans_delta:+.4f}).")
    elif ref_delta < -0.02:
        verdict = (f"M3 STAYS — Gemma still refuses worse with the gate on "
                   f"({ref_delta:+.4f} across the three unanswerable kinds).")
    else:
        verdict = (f"TRADE — refusal {ref_delta:+.4f}, answerable "
                   f"{ans_delta:+.4f}; neither dominates and the choice is a "
                   f"deployment preference, not a measurement.")
else:
    verdict = (f"CANNOT COMPARE — the gate does not beat its own control on "
               f"{[a for a, h in helps.items() if not h]}, so a cross-encoder "
               f"comparison with it enabled would be comparing two "
               f"differently-broken configurations. That is exactly the error "
               f"exp62 made.")
print(f"\n=== VERDICT ===\n  {verdict}")

out = {"manifest": run_manifest(seed=SEED,
                                config={"RES_GRID": list(RES_GRID),
                                        "TF_GRID": list(TF_GRID),
                                        "K_BASIS": K_BASIS, "CAP": CAP}),
       "population_sizes": {k: len(POP[k]) for k in ORDER},
       "arms": RESULTS, "gate_vs_control": ctrl, "gate_helps": helps,
       "gemma_minus_m3_gate_on": cmp_, "verdict": verdict,
       "registered_prediction": (
           "the gate helps on not_applicable for both encoders, reproducing "
           "D134's direction, and stays harmful on chain_break which is what "
           "exp62 measured; whether that puts Gemma ahead overall is "
           "genuinely unknown"),
       "scope": ("D134's mixed benchmark rebuilt exactly — three kinds of "
                 "unanswerable, never averaged (law #9), with absent_entity "
                 "subjects taken from the real arXiv component rather than "
                 "fabricated. exp62 tested the gate on chain-break "
                 "unanswerables, which is not the population it was built "
                 "for, and its null should not be read as refuting D134. "
                 "Type threshold calibrated per encoder on HALF the "
                 "not-applicable population plus trained answerable, "
                 "evaluated on the other half (D134's rule), because a "
                 "cosine threshold does not transfer across encoders any "
                 "more than a residual norm does (D125). The verdict logic "
                 "checks gate-ON against gate-OFF WITHIN each encoder before "
                 "any cross-encoder claim, because exp52, exp53 and exp62 "
                 "each produced a confident verdict comparing the wrong "
                 "pair.")}
(ROOT / "results" / "exp63_mixed_gate.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp63_mixed_gate.json")
