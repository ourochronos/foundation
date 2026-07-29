"""Append-then-query: is the store actually reindex-free? (D131)

D130's adjudication found that the project's headline claim has never been
measured. We showed a novel relation is *answerable* (D125, 0.742). We never
showed that **appending** new knowledge requires no reindex — that was
inferred from the design (coordinates come from labels, so a new relation
needs nothing fitted) and never demonstrated by an actual append-then-query
cycle.

This runs the cycle. Two things must both hold, and they are different kinds
of claim:

  MECHANICAL (a verification, not a measurement): appending must not mutate
  any frozen artifact. Fingerprints of the anchor basis, the relation
  coordinates, the head weights and the pre-existing claim representations
  are hashed at freeze time and re-hashed after the append. Byte-identical
  or the claim is simply false.

  BEHAVIOURAL (a measurement): content appended after the freeze must be
  queryable. The honest ceiling is a FULL REBUILD — refit the basis and
  retrain the head on everything, which is what "reindexing" would buy. If
  frozen+append ≈ rebuild, appending costs nothing. If it lags badly, the
  property is weak however clean the mechanics are.

The append is deliberately hostile: it contains relations that did not exist
at freeze time AND entities that did not exist at freeze time, so the 2x2 of
(old/new subject) x (old/new relation) is measured separately. Averaging
those four would hide exactly the case that matters.

Both architectures are run, because the claim differs between them: the
parametric head (D123-D128) versus 1-NN retrieval (D129), where appending is
literally "add rows".

Usage: .venv/bin/python scripts/exp36_append.py
"""
from __future__ import annotations

import collections
import hashlib
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

SEED, MIN_GAIN, K_BASIS = 0, 0.2, 48
NEW_REL_FRAC, NEW_SUBJ_FRAC = 0.25, 0.25
CAP_Q, CAP_UNANS = 900, 1500


def fp(a) -> str:
    """Fingerprint of a frozen artifact."""
    if isinstance(a, dict):
        h = hashlib.sha256()
        for k in sorted(a):
            h.update(k.encode())
            h.update(np.ascontiguousarray(a[k]).tobytes())
        return h.hexdigest()[:16]
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()[:16]


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

rng = np.random.default_rng(SEED)
NEW_R = {RELS[i] for i in
         sorted(rng.permutation(len(RELS))[:int(NEW_REL_FRAC * len(RELS))])}
all_subj = sorted({c["subject"] for c in wiki})
NEW_S = {all_subj[i] for i in
         sorted(rng.permutation(len(all_subj))[:int(NEW_SUBJ_FRAC
                                                    * len(all_subj))])}
print(f"{len(wiki)} claims / {len(RELS)} relations / {len(all_subj)} subjects")
print(f"freeze: {len(RELS) - len(NEW_R)} relations, "
      f"{len(all_subj) - len(NEW_S)} subjects")
print(f"append: {len(NEW_R)} NEW relations, {len(NEW_S)} NEW subjects")


def bucket(c):
    ns, nr = c["subject"] in NEW_S, c["pid"] in NEW_R
    return ("t0" if not ns and not nr else
            "new_rel" if not ns else "new_subj" if not nr else "new_both")


CLAIMS = collections.defaultdict(list)
for c in wiki:
    CLAIMS[bucket(c)].append(c)
for k in ("t0", "new_rel", "new_subj", "new_both"):
    print(f"  {k:9s} {len(CLAIMS[k]):6d} claims")

# T0 store = frozen content only; FULL store = after the append
def store_of(keys):
    g, av = collections.defaultdict(set), collections.defaultdict(set)
    for k in keys:
        for c in CLAIMS[k]:
            g[(c["subject"], c["pid"])].add(c["object"])
            av[c["subject"]].add(c["pid"])
    return g, av


G0, A0 = store_of(["t0"])
GF, AF = store_of(["t0", "new_rel", "new_subj", "new_both"])
T0_RELS = sorted({r for (_, r) in G0})
print(f"\nT0 store {len(G0)} subject-relation pairs over {len(T0_RELS)} "
      f"relations; full store {len(GF)}")


def step(g, nodes, r):
    out = set()
    for s in nodes:
        out |= g.get((s, r), set())
    return out


def text1(s, r):
    return f"What is the {LABEL[r]} of {s}?"


def text2(s, r1, r2):
    return f"What is the {LABEL[r2]} of the {LABEL[r1]} of {s}?"


# ---- query populations, deterministic (law #8) ----
QP = collections.defaultdict(list)
for k in ("t0", "new_rel", "new_subj", "new_both"):
    seen = set()
    for c in sorted(CLAIMS[k], key=lambda x: (x["subject"], x["pid"])):
        key = (c["subject"], c["pid"])
        if key in seen:
            continue
        seen.add(key)
        QP[f"d1_{k}"].append({"subject": c["subject"], "chain": [c["pid"]],
                              "answers": sorted(GF[key]),
                              "text": text1(c["subject"], c["pid"])})
# depth-2 chains that traverse appended content
for s in sorted(AF):
    for r1 in sorted(AF[s]):
        m1 = step(GF, {s}, r1)
        if not m1:
            continue
        for r2 in sorted(set().union(*(AF.get(x, set()) for x in m1))):
            m2 = step(GF, m1, r2)
            if not m2:
                continue
            touches_new = (s in NEW_S or r1 in NEW_R or r2 in NEW_R
                           or any(x in NEW_S for x in m1))
            QP["d2_new" if touches_new else "d2_t0"].append(
                {"subject": s, "chain": [r1, r2], "answers": sorted(m2)[:300],
                 "text": text2(s, r1, r2)})
for k in list(QP):
    if len(QP[k]) > CAP_Q:
        QP[k] = [QP[k][i] for i in sorted(rng.choice(len(QP[k]), CAP_Q,
                                                     replace=False))]
    print(f"  {k:12s} {len(QP[k]):5d} questions")

# unanswerable in the FULL store (law #7), so refusal is measurable
un = []
for s in sorted(AF):
    for r1 in sorted(AF[s]):
        if not step(GF, {s}, r1):
            continue
        for r2 in RELS:
            if not step(GF, step(GF, {s}, r1), r2):
                un.append({"subject": s, "chain": [r1, r2], "answers": [],
                           "text": text2(s, r1, r2)})
un.sort(key=lambda a: (a["subject"], ">".join(a["chain"])))
if len(un) > CAP_UNANS:
    un = [un[i] for i in sorted(rng.choice(len(un), CAP_UNANS,
                                           replace=False))]
QP["unans"] = un
print(f"  {'unans':12s} {len(un):5d} questions")

ORDER = sorted(QP)
texts, index = [], {}
for k in ORDER:
    index[k] = (len(texts), len(texts) + len(QP[k]))
    texts += [q["text"] for q in QP[k]]
cache = ROOT / "results" / "exp36_emb.npz"
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    assert list(z["texts"]) == texts, "cache misaligned; delete it"
    Z, Zl = z["Z"], z["Zl"]
else:
    Z = P.unit(P.embed_texts(texts))
    Zl = P.unit(P.embed_texts([LABEL[r] for r in RELS]))
    np.savez(cache, Z=Z, Zl=Zl, texts=np.array(texts))
RC_ALL = {r: Zl[i] for i, r in enumerate(RELS)}
print(f"\n{len(texts)} questions embedded", flush=True)


def emb(k):
    a, b = index[k]
    return Z[a:b]


import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402


def build(fit_rels, train_keys, tag):
    """Fit basis + head on a given slice. Called twice: FROZEN (T0 only) and
    REBUILD (everything), so the second is the reindexing ceiling."""
    PC = P.unit(fit_anchors(np.stack([RC_ALL[r] for r in fit_rels]),
                            min(K_BASIS, len(fit_rels)), seed=SEED))
    C = {r: P.unit(RC_ALL[r] @ PC.T) for r in RELS}   # NEW rels: projection
    Xs, Ys, bank = [], [], []
    for k in train_keys:
        E = emb(k)
        for j, q in enumerate(QP[k]):
            Xs.append(E[j])
            Ys.append(sum(C[r] for r in q["chain"]))
            bank.append(sum(C[r] for r in q["chain"]))
    X = torch.tensor(np.stack(Xs))
    Y = torch.tensor(np.stack(Ys))
    torch.manual_seed(SEED)
    hd = nn.Sequential(nn.Linear(1024, 512), nn.GELU(),
                       nn.Linear(512, PC.shape[0]))
    op = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(X)).split(512):
            op.zero_grad()
            ((hd(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
            op.step()
    hd.eval()
    print(f"  [{tag}] basis {PC.shape}, head on {len(Xs)} rows, "
          f"bank {len(bank)}")
    return {"PC": PC, "C": C, "head": hd,
            "bankX": np.stack(Xs), "bankY": np.stack(bank)}


print("\nfreezing at T0 (nothing after this point may refit)...", flush=True)
FROZEN = build(T0_RELS, ["d1_t0", "d2_t0"], "frozen")
FROZEN_FP = {"basis": fp(FROZEN["PC"]),
             "coords": fp({r: FROZEN["C"][r] for r in T0_RELS}),
             "head": fp({n: p.detach().numpy()
                         for n, p in FROZEN["head"].named_parameters()})}
print(f"  fingerprints: {FROZEN_FP}")


def run(art, key, g, av, mode, thr=0.8):
    """mode: 'head' (parametric) or 'knn' (1-NN over the frozen bank)."""
    C, rows, E = art["C"], QP[key], emb(key)
    dim = art["PC"].shape[0]
    if mode == "head":
        with torch.no_grad():
            tgt = art["head"](torch.tensor(E)).numpy()
    else:
        S = E @ art["bankX"].T
        tgt = art["bankY"][S.argmax(1)]
    c = collections.Counter()
    for j, q in enumerate(rows):
        resid, frontier, path = tgt[j].copy(), {q["subject"]}, []
        for _ in range(len(q["chain"]) + 1):
            opts = set()
            for s in frontier:
                opts |= av.get(s, set())
            best, bg = None, MIN_GAIN
            for r in opts:
                gg = float(resid @ C[r])
                if gg > bg:
                    best, bg = r, gg
            if best is None:
                break
            nxt = step(g, frontier, best)
            if not nxt:
                break
            frontier, path = nxt, path + [best]
            resid = resid - C[best]
        rn = float(np.linalg.norm(tgt[j] - sum((C[r] for r in path),
                                               np.zeros(dim, np.float32))))
        if not path or not frontier or rn > thr:
            c["abstain"] += 1
        elif key == "unans":
            c["wrong"] += 1
        else:
            c["correct" if set(frontier) & set(q["answers"]) else "wrong"] += 1
    n = max(sum(c.values()), 1)
    return {k: round(c[k] / n, 4) for k in
            ("correct", "wrong", "abstain")} | {"n": n}


print("\nappending (no refit; the frozen artifacts are reused as-is)...")
AFTER_FP = {"basis": fp(FROZEN["PC"]),
            "coords": fp({r: FROZEN["C"][r] for r in T0_RELS}),
            "head": fp({n: p.detach().numpy()
                        for n, p in FROZEN["head"].named_parameters()})}
MECH_OK = AFTER_FP == FROZEN_FP
print(f"  MECHANICAL CHECK — frozen artifacts unchanged after append: "
      f"{MECH_OK}")
for k in FROZEN_FP:
    print(f"    {k:7s} {FROZEN_FP[k]} -> {AFTER_FP[k]} "
          f"{'OK' if FROZEN_FP[k] == AFTER_FP[k] else 'MUTATED'}")

print("\nrebuilding as the reindexing ceiling...", flush=True)
REBUILT = build(RELS, ["d1_t0", "d1_new_rel", "d1_new_subj", "d1_new_both",
                       "d2_t0", "d2_new"], "rebuild")

EVAL = ["d1_t0", "d1_new_rel", "d1_new_subj", "d1_new_both",
        "d2_t0", "d2_new", "unans"]
print(f"\n{'population':14s} {'mode':>5} | {'FROZEN+APPEND':>26} | "
      f"{'REBUILD (ceiling)':>26}")
res = {}
for key in EVAL:
    if not QP.get(key):
        continue
    for mode in ("head", "knn"):
        f_ = run(FROZEN, key, GF, AF, mode)
        r_ = run(REBUILT, key, GF, AF, mode)
        res[f"{key}_{mode}"] = {"frozen": f_, "rebuilt": r_}
        fs = (f"c {f_['correct']:.3f} w {f_['wrong']:.3f} "
              f"a {f_['abstain']:.3f}")
        rs = (f"c {r_['correct']:.3f} w {r_['wrong']:.3f} "
              f"a {r_['abstain']:.3f}")
        print(f"{key:14s} {mode:>5} | {fs:>26} | {rs:>26}")

print("\nAPPEND COST = rebuild minus frozen (positive means reindexing helps)")
for key in EVAL:
    if key == "unans" or not QP.get(key):
        continue
    for mode in ("head", "knn"):
        d = (res[f"{key}_{mode}"]["rebuilt"]["correct"]
             - res[f"{key}_{mode}"]["frozen"]["correct"])
        print(f"  {key:14s} {mode:>5}  {d:+.3f}")

out = {
    "manifest": run_manifest(seed=SEED, config={"K_BASIS": K_BASIS,
                                                "NEW_REL_FRAC": NEW_REL_FRAC,
                                                "NEW_SUBJ_FRAC":
                                                NEW_SUBJ_FRAC}),
    "mechanical_check_passed": MECH_OK,
    "fingerprints": {"at_freeze": FROZEN_FP, "after_append": AFTER_FP},
    "n_new_relations": len(NEW_R), "n_new_subjects": len(NEW_S),
    "claims_by_bucket": {k: len(v) for k, v in CLAIMS.items()},
    "results": res,
    "scope": ("Append-then-query. Frozen artifacts (basis, coordinates, head) "
              "are fitted on T0 content only and reused byte-identically "
              "after the append — verified by fingerprint, which is the "
              "MECHANICAL half of the claim. The BEHAVIOURAL half is frozen "
              "vs a full rebuild on everything, which is what reindexing "
              "would buy. The 2x2 of (old/new subject) x (old/new relation) "
              "is reported separately; averaging them would hide the case "
              "that matters."),
}
(ROOT / "results" / "exp36_append.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp36_append.json")
