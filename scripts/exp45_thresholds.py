"""Derive the type-gate threshold from the store instead of tuning it (D142).

Task 3. Three findings of the same shape now exist: D124 (refusal bounded by
density), D126 (depth curve differs by corpus), D138 (type gate 0.693 on wiki,
0.314 on MQuAKE). Three occurrences is a mechanism, not a caveat — a threshold
tuned on one store does not transfer to another.

**The derivation.** The type gate asks whether returned objects look like the
asked relation's range. Its natural scale is therefore *how tight ranges are
in this store*, which is a pure store statistic needing no questions, no
labels and no head:

    for each relation r, and each object o of r:
        fit(o, r) = cos(embed(o), centroid of r's objects)
    TTHR = the q-th percentile of fit over all (o, r) in the store

A store of dates and identifiers has tight ranges and a high percentile; a
store of free-text "notable work" values has loose ones and a low percentile.
The threshold should follow the store, and this makes it do so.

**The test is transfer, not fit.** Derive on wiki, apply UNCHANGED to MQuAKE;
derive on MQuAKE, apply UNCHANGED to wiki. Success is a derived threshold
landing near the tuned one on a corpus it was never tuned on, and producing a
comparable operating point. Failure is equally publishable and would mean
per-store calibration is unavoidable — a real deployment constraint, and one
worth stating plainly rather than hiding behind a tuned constant.

Per the plan's stop condition: if transfer fails, report it and stop. Do not
iterate into a per-corpus fit dressed up as a derivation.

Usage: .venv/bin/python scripts/exp45_thresholds.py
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
from codec.manifest import run_manifest                          # noqa: E402
from foundation.kb import KB                                     # noqa: E402

SEED, MIN_GAIN, RES_THR, PCTL = 0, 0.2, 0.8, 25
CAP = 900

sch = {d["pid"]: d["label"] for d in
       json.loads((ROOT / "data" / "schema_v0.json").read_text())}
props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())


def wiki_store():
    kb = KB(backend="pg", table="poc")
    rows = [c for c in kb.claims
            if not c["page"].startswith(("arxiv:", "hf:", "user"))]
    lab = {}
    for c in rows:
        p = c["pid"]
        if p not in lab:
            l_ = sch.get(p) or (props.get(p) or {}).get("label")
            if l_:
                lab[p] = l_
    rows = [c for c in rows if c["pid"] in lab]
    g = collections.defaultdict(set)
    for c in rows:
        g[(c["subject"], c["pid"])].add(c["object"])
    return "wiki", g, lab


def mquake_store():
    cases = json.loads(
        (ROOT / "data" / "mquake" / "MQuAKE-CF-3k.json").read_text())
    g, lab = collections.defaultdict(set), {}
    for c in cases:
        for (s, p, o), (sl, pl, ol) in zip(c["orig"]["triples"],
                                           c["orig"]["triples_labeled"]):
            if p in props:
                lab[p] = props[p]["label"]
                g[(sl, p)].add(ol)
    return "mquake", g, lab


STORES = {}
for name, g, lab in (wiki_store(), mquake_store()):
    av = collections.defaultdict(set)
    for (s, p) in g:
        av[s].add(p)
    STORES[name] = {"gold": g, "avail": av, "label": lab,
                    "rels": sorted(lab)}
    print(f"{name}: {len(g)} pairs, {len(lab)} relations, {len(av)} subjects")

rng = np.random.default_rng(SEED)
for name, S in STORES.items():
    g, lab, rels = S["gold"], S["label"], S["rels"]
    objs = sorted({o for v in g.values() for o in v})
    subs = sorted(S["avail"])
    cache = ROOT / "results" / f"exp45_{name}_emb.npz"
    ansq = [{"node": s, "rel": r, "answers": sorted(g[(s, r)]),
             "text": f"What is the {lab[r]} of {s}?"}
            for s in subs for r in sorted(S["avail"][s])]
    naq = [{"node": s, "rel": r, "answers": [],
            "text": f"What is the {lab[r]} of {s}?"}
           for s in subs for r in rels if r not in S["avail"][s]]
    for pool in (ansq, naq):
        pool.sort(key=lambda a: (a["node"], a["rel"]))
    ansq = [ansq[i] for i in sorted(rng.choice(len(ansq),
                                               min(CAP, len(ansq)),
                                               replace=False))]
    naq = [naq[i] for i in sorted(rng.choice(len(naq), min(CAP, len(naq)),
                                             replace=False))]
    texts = [a["text"] for a in ansq] + [a["text"] for a in naq]
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        assert list(z["texts"]) == texts and list(z["objs"]) == objs, \
            f"{name} cache misaligned; delete it"
        Z, Zl, Zo = z["Z"], z["Zl"], z["Zo"]
    else:
        Z = P.unit(P.embed_texts(texts))
        Zl = P.unit(P.embed_texts([lab[r] for r in rels]))
        Zo = P.unit(P.embed_texts(objs))
        np.savez(cache, Z=Z, Zl=Zl, Zo=Zo, texts=np.array(texts),
                 objs=np.array(objs))
    OI = {o: i for i, o in enumerate(objs)}
    K = min(48, len(rels))
    PC = P.unit(fit_anchors(Zl, K, seed=SEED))
    C = {r: P.unit(Zl[i] @ PC.T) for i, r in enumerate(rels)}
    CENT, FITS = {}, []
    for r in rels:
        ids = [OI[o] for k, v in g.items() if k[1] == r for o in sorted(v)
               if o in OI]
        if not ids:
            continue
        CENT[r] = P.unit(Zo[ids].mean(0))
        FITS += list(Zo[ids] @ CENT[r])            # store statistic only
    S.update({"Z": Z, "Zo": Zo, "OI": OI, "C": C, "K": K, "CENT": CENT,
              "ansq": ansq, "naq": naq,
              "derived": float(np.percentile(FITS, PCTL)),
              "fit_mean": float(np.mean(FITS))})
    print(f"  {name}: within-relation type fit mean {S['fit_mean']:.3f}, "
          f"p{PCTL} = {S['derived']:.3f}  <- DERIVED threshold")

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

for name, S in STORES.items():
    ansq, K, C = S["ansq"], S["K"], S["C"]
    tr = list(range(0, len(ansq), 2))
    X = torch.tensor(S["Z"][tr])
    Y = torch.tensor(np.stack([C[ansq[i]["rel"]] for i in tr]))
    torch.manual_seed(SEED)
    hd = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, K))
    op = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(X)).split(512):
            op.zero_grad()
            ((hd(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
            op.step()
    hd.eval()
    S["head"] = hd
    with torch.no_grad():
        S["TGT"] = hd(torch.tensor(S["Z"])).numpy()
    print(f"{name}: head trained on {len(tr)} questions", flush=True)


def judge(name, which, tthr):
    S = STORES[name]
    rows = S[which]
    off = 0 if which == "ansq" else len(S["ansq"])
    g, av, C, CENT, OI, Zo = (S["gold"], S["avail"], S["C"], S["CENT"],
                              S["OI"], S["Zo"])
    c = collections.Counter()
    for j, a in enumerate(rows):
        i = off + j
        resid, frontier, path = S["TGT"][i].copy(), {a["node"]}, []
        for _ in range(2):
            opts = sorted(set().union(*(av.get(n, set()) for n in frontier))
                          if frontier else set())
            if not opts:
                break
            gs = sorted(((float(resid @ C[r]), r) for r in opts),
                        reverse=True)
            if gs[0][0] <= MIN_GAIN:
                break
            nxt = set()
            for n in frontier:
                nxt |= g.get((n, gs[0][1]), set())
            if not nxt:
                break
            frontier, path = nxt, path + [gs[0][1]]
            resid = resid - C[gs[0][1]]
        rn = float(np.linalg.norm(resid))
        tf = 0.0
        if frontier:
            r_asked = max(CENT, key=lambda r: float(S["TGT"][i] @ C[r]))
            ids = [OI[o] for o in sorted(frontier) if o in OI]
            if ids:
                tf = float(np.mean(Zo[ids] @ CENT[r_asked]))
        if not path or not frontier or rn > RES_THR or tf < tthr:
            c["refuse"] += 1
        elif which == "ansq" and set(frontier) & set(a["answers"]):
            c["correct"] += 1
        else:
            c["wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: round(c[k] / n, 4) for k in ("correct", "wrong", "refuse")}


TUNED = {"wiki": 0.40, "mquake": 0.30}     # D134 / D138, tuned per corpus
print(f"\n=== TRANSFER TEST: does a DERIVED threshold work on a store it "
      f"was not derived from? ===")
print(f"{'store':8s} {'threshold source':22s} {'value':>7} "
      f"{'answerable correct':>19} {'not-appl refused':>18}")
res = {}
for name in STORES:
    other = "mquake" if name == "wiki" else "wiki"
    for src, t in (("tuned (D134/D138)", TUNED[name]),
                   ("derived, same store", STORES[name]["derived"]),
                   (f"derived on {other}", STORES[other]["derived"])):
        a = judge(name, "ansq", t)
        na = judge(name, "naq", t)
        res[f"{name}|{src}"] = {"thr": round(t, 4),
                                "answerable": a, "not_applicable": na}
        print(f"{name:8s} {src:22s} {t:7.3f} {a['correct']:19.3f} "
              f"{na['refuse']:18.3f}")
    print()

print("verdict per store (derived-on-other vs tuned):")
ok = True
for name in STORES:
    other = "mquake" if name == "wiki" else "wiki"
    tun = res[f"{name}|tuned (D134/D138)"]
    xfer = res[f"{name}|derived on {other}"]
    d_na = xfer["not_applicable"]["refuse"] - tun["not_applicable"]["refuse"]
    d_a = xfer["answerable"]["correct"] - tun["answerable"]["correct"]
    good = abs(d_na) <= 0.10 and abs(d_a) <= 0.10
    ok &= good
    print(f"  {name:8s} threshold {tun['thr']:.2f} -> {xfer['thr']:.3f}   "
          f"refusal {d_na:+.3f}  coverage {d_a:+.3f}   "
          f"{'TRANSFERS' if good else 'DOES NOT TRANSFER'}")
print(f"\nOVERALL: derivation {'TRANSFERS' if ok else 'DOES NOT TRANSFER'} "
      f"across these two stores")

out = {
    "manifest": run_manifest(seed=SEED, config={"PCTL": PCTL,
                                                "RES_THR": RES_THR}),
    "derived": {n: round(S["derived"], 4) for n, S in STORES.items()},
    "within_relation_fit_mean": {n: round(S["fit_mean"], 4)
                                 for n, S in STORES.items()},
    "tuned": TUNED, "results": res, "transfers": bool(ok),
    "scope": ("The type-gate threshold is derived as the p25 of "
              "within-relation type fit — a pure store statistic using no "
              "questions, labels or head. Transfer is the test: each store "
              "is evaluated at its tuned threshold, at its own derived "
              "threshold, and at the threshold derived from the OTHER "
              "store. Only the third is evidence. The residual threshold is "
              "held fixed at 0.8 throughout, since coordinates are unit "
              "vectors and it already transferred."),
}
(ROOT / "results" / "exp45_thresholds.json").write_text(json.dumps(out,
                                                                   indent=1))
print("\n[done] results/exp45_thresholds.json")
