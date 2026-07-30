"""Can the store LEARN? refused-before -> answered-after (D133).

Two things prompted this, and they turn out to be one experiment.

**"Disbelief" conflates two claims.** D132 named a bucket `disbelief`: a walk
completed but did not satisfy the question. Our store is OPEN-WORLD and
admittedly incomplete, so that state means *no claim was found*, not *the
proposition is false*. Real disbelief needs evidence AGAINST — which the
store does model, as `conflict` and `invalidated_by` — and we have not
earned the closed-world reading the name imports. Renamed `unanswered`
throughout; `conflict` is reserved for contradictory claims.

**The property that actually matters has never been measured.** D131 showed
appending is mechanically free and costs some accuracy on new content. It
never checked the transition that defines a system that learns: **a question
the store could not answer before the update, answered after it.** That is
measured here on the SAME questions, before and after, with the artifacts
frozen (no refit, per D131).

Four transitions, and three of them are failure modes:

  refused -> correct    the property we want: the update was absorbed
  refused -> refused    failed to learn; the knowledge is in the store and
                        still unreachable
  refused -> wrong      absorbed it and got it wrong, the worst outcome
  correct -> wrong      regression: the update damaged prior knowledge

Plus a control the experiment is meaningless without: questions that remain
unanswerable AFTER the update must still be refused. Without it, a system
that simply started answering everything would look like it had learned.

Usage: .venv/bin/python scripts/exp38_update.py
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

SEED, MIN_GAIN, K_BASIS, THR = 0, 0.2, 48, 0.8
UPDATE_FRAC, CAP = 0.30, 1200

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

# Full store, then withhold a random slice of (subject, relation) pairs as
# "the update". Those pairs are the ones whose questions must flip.
full = collections.defaultdict(set)
for c in wiki:
    full[(c["subject"], c["pid"])].add(c["object"])
pairs = sorted(full)
rng = np.random.default_rng(SEED)
upd_idx = set(rng.permutation(len(pairs))[:int(UPDATE_FRAC * len(pairs))]
              .tolist())
UPDATE = {pairs[i] for i in sorted(upd_idx)}
print(f"{len(wiki)} claims / {len(pairs)} subject-relation pairs")
print(f"withheld as the update: {len(UPDATE)} pairs "
      f"({len(UPDATE)/len(pairs):.0%})")


def store(exclude):
    g, av = collections.defaultdict(set), collections.defaultdict(set)
    for k, v in full.items():
        if k in exclude:
            continue
        g[k] = set(v)
        av[k[0]].add(k[1])
    return g, av


G0, A0 = store(UPDATE)          # before the update
G1, A1 = store(set())           # after
T0_RELS = sorted({r for (_, r) in G0})
print(f"before: {len(G0)} pairs / {len(T0_RELS)} relations; "
      f"after: {len(G1)} pairs / {len(RELS)} relations")


def step(g, nodes, r):
    out = set()
    for s in nodes:
        out |= g.get((s, r), set())
    return out


def text1(s, r):
    return f"What is the {LABEL[r]} of {s}?"


# ---- populations, deterministic (law #8) ----
WILL_FLIP = sorted(UPDATE)                       # unanswerable T0, answerable T1
if len(WILL_FLIP) > CAP:
    WILL_FLIP = [WILL_FLIP[i] for i in
                 sorted(rng.choice(len(WILL_FLIP), CAP, replace=False))]
STAYS = sorted(set(full) - UPDATE)               # answerable both times
if len(STAYS) > CAP:
    STAYS = [STAYS[i] for i in sorted(rng.choice(len(STAYS), CAP,
                                                 replace=False))]
# never answerable, before OR after — the control without which "it learned"
# is indistinguishable from "it started answering everything"
never, seen = [], set()
for s in sorted({k[0] for k in pairs}):
    for r in RELS:
        if (s, r) not in full and len(never) < CAP:
            never.append((s, r))
print(f"  will-flip {len(WILL_FLIP)}, stays-answerable {len(STAYS)}, "
      f"never-answerable {len(never)}")

QP = {"flip": [{"subject": s, "chain": [r], "answers": sorted(full[(s, r)]),
                "text": text1(s, r)} for s, r in WILL_FLIP],
      "stays": [{"subject": s, "chain": [r], "answers": sorted(full[(s, r)]),
                 "text": text1(s, r)} for s, r in STAYS],
      "never": [{"subject": s, "chain": [r], "answers": [],
                 "text": text1(s, r)} for s, r in never]}
ORDER = sorted(QP)
texts, index = [], {}
for k in ORDER:
    index[k] = (len(texts), len(texts) + len(QP[k]))
    texts += [q["text"] for q in QP[k]]
cache = ROOT / "results" / "exp38_emb.npz"
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    assert list(z["texts"]) == texts, "cache misaligned; delete it"
    Z, Zl = z["Z"], z["Zl"]
else:
    Z = P.unit(P.embed_texts(texts))
    Zl = P.unit(P.embed_texts([LABEL[r] for r in RELS]))
    np.savez(cache, Z=Z, Zl=Zl, texts=np.array(texts))
RC = {r: Zl[i] for i, r in enumerate(RELS)}
print(f"{len(texts)} questions embedded", flush=True)


def emb(k):
    a, b = index[k]
    return Z[a:b]


import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

# FREEZE on the before-store only. Nothing after this refits.
PC = P.unit(fit_anchors(np.stack([RC[r] for r in T0_RELS]), K_BASIS,
                        seed=SEED))
C = {r: P.unit(RC[r] @ PC.T) for r in RELS}
Xs, Ys = [], []
E = emb("stays")
for j, q in enumerate(QP["stays"]):
    Xs.append(E[j])
    Ys.append(sum(C[r] for r in q["chain"]))
X, Y = torch.tensor(np.stack(Xs)), torch.tensor(np.stack(Ys))
torch.manual_seed(SEED)
head = nn.Sequential(nn.Linear(1024, 512), nn.GELU(),
                     nn.Linear(512, K_BASIS))
opt = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-4)
for _ in range(40):
    for b in torch.randperm(len(X)).split(512):
        opt.zero_grad()
        ((head(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
        opt.step()
head.eval()
print(f"frozen at T0: basis {PC.shape}, head on {len(Xs)} rows", flush=True)


def fp(a) -> str:
    """Fingerprint of a frozen artifact (same recipe as exp36_append)."""
    if isinstance(a, dict):
        h = hashlib.sha256()
        for k in sorted(a):
            h.update(k.encode())
            h.update(np.ascontiguousarray(a[k]).tobytes())
        return h.hexdigest()[:16]
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()[:16]


def artifact_fp() -> dict:
    return {"basis": fp(PC),
            "coords": fp({r: C[r] for r in RELS}),
            "head": fp({n: p.detach().numpy()
                        for n, p in head.named_parameters()})}


# D154 named this as claim 1c's falsifier, and the rater was right: the
# artifacts here are frozen *by construction* — nothing below refits — but the
# only fingerprint evidence lived in exp36's separate append run. "Our code
# does not contain a refit" is an argument about code; this is a measurement,
# and it belongs in the experiment whose claim depends on it.
FROZEN_FP = artifact_fp()
print(f"  fingerprints at T0: {FROZEN_FP}")


def verdict(key, g, av):
    """Returns per-question status using D132's vocabulary, with `disbelief`
    renamed `unanswered` — open-world: no claim found is not falsity."""
    rows, E = QP[key], emb(key)
    with torch.no_grad():
        tgt = head(torch.tensor(E)).numpy()
    out = []
    for j, q in enumerate(rows):
        resid, frontier, path = tgt[j].copy(), {q["subject"]}, []
        margins = []
        for _ in range(len(q["chain"]) + 1):
            opts = sorted(set().union(*(av.get(x, set()) for x in frontier))
                          if frontier else set())
            if not opts:
                break
            gs = sorted(((float(resid @ C[r]), r) for r in opts),
                        reverse=True)
            if gs[0][0] <= MIN_GAIN:
                break
            margins.append(gs[0][0] - (gs[1][0] if len(gs) > 1 else -1.0))
            nxt = step(g, frontier, gs[0][1])
            if not nxt:
                break
            frontier, path = nxt, path + [gs[0][1]]
            resid = resid - C[gs[0][1]]
        rn = float(np.linalg.norm(resid))
        if not path or not frontier:
            st = "vacuous"
        elif rn > THR:
            st = ("ambiguous" if (margins and min(margins) < 0.112)
                  else "unanswered")
        else:
            st = "correct" if set(frontier) & set(q["answers"]) else "wrong"
        out.append(st)
    return out


BEFORE = {k: verdict(k, G0, A0) for k in ORDER}
print("\nappending the update (frozen artifacts reused as-is)...")
AFTER = {k: verdict(k, G1, A1) for k in ORDER}

AFTER_FP = artifact_fp()
MECH_OK = AFTER_FP == FROZEN_FP
print(f"\n=== MECHANICAL CHECK — artifacts unchanged across the update: "
      f"{MECH_OK} ===")
for k in FROZEN_FP:
    print(f"  {k:7s} {FROZEN_FP[k]} -> {AFTER_FP[k]} "
          f"{'OK' if FROZEN_FP[k] == AFTER_FP[k] else 'MUTATED'}")
if not MECH_OK:
    raise SystemExit("frozen artifacts mutated during the update — the "
                     "learning result below would be measuring a refit")


def refused(s):
    return s in ("vacuous", "ambiguous", "unanswered")


print(f"\n=== THE TRANSITION: questions the store could not answer before ===")
tm = collections.Counter()
for b, a in zip(BEFORE["flip"], AFTER["flip"]):
    tm[(("refused" if refused(b) else b), ("refused" if refused(a) else a))] += 1
n = max(sum(tm.values()), 1)
learned = tm[("refused", "correct")] / n
print(f"  refused -> CORRECT   {tm[('refused','correct')]:5d}  {learned:.3f}"
      f"   <- the property: the update was absorbed")
print(f"  refused -> refused   {tm[('refused','refused')]:5d}  "
      f"{tm[('refused','refused')]/n:.3f}   <- failed to learn")
print(f"  refused -> wrong     {tm[('refused','wrong')]:5d}  "
      f"{tm[('refused','wrong')]/n:.3f}   <- absorbed and got it wrong")
other = n - sum(tm[("refused", x)] for x in ("correct", "refused", "wrong"))
print(f"  (answerable before)  {other:5d}   "
      f"<- should be ~0; these were meant to be unanswerable at T0")
lo, hi = wilson_ci(tm[("refused", "correct")], n)
print(f"  learned-rate CI95 [{lo:.3f}, {hi:.3f}]")

print(f"\n=== REGRESSION: questions answerable all along ===")
rm = collections.Counter()
for b, a in zip(BEFORE["stays"], AFTER["stays"]):
    rm[(b if b in ("correct", "wrong") else "refused",
        a if a in ("correct", "wrong") else "refused")] += 1
ns = max(sum(rm.values()), 1)
print(f"  correct -> correct   {rm[('correct','correct')]/ns:.3f}")
print(f"  correct -> wrong     {rm[('correct','wrong')]/ns:.3f}   "
      f"<- damage from the update")
print(f"  correct -> refused   {rm[('correct','refused')]/ns:.3f}")

print(f"\n=== CONTROL: never answerable, before or after ===")
for tag, D in (("before", BEFORE), ("after", AFTER)):
    c = collections.Counter(D["never"])
    m = max(sum(c.values()), 1)
    ans = (c["correct"] + c["wrong"]) / m
    print(f"  {tag:6s} refused {1 - ans:.3f}  answered-anyway {ans:.3f}  "
          f"(vacuous {c['vacuous']/m:.3f} ambiguous {c['ambiguous']/m:.3f} "
          f"unanswered {c['unanswered']/m:.3f})")

print(f"\n=== status mix on the flip set, before vs after ===")
for tag, D in (("before", BEFORE), ("after", AFTER)):
    c = collections.Counter(D["flip"])
    m = max(sum(c.values()), 1)
    print(f"  {tag:6s} " + "  ".join(f"{k} {c[k]/m:.3f}" for k in
                                     ("vacuous", "ambiguous", "unanswered",
                                      "correct", "wrong")))

out = {
    "manifest": run_manifest(seed=SEED, config={"UPDATE_FRAC": UPDATE_FRAC,
                                                "THR": THR,
                                                "K_BASIS": K_BASIS}),
    "n_update_pairs": len(UPDATE),
    "n_flip_questions": len(QP["flip"]),
    "mechanical_check_passed": MECH_OK,
    "fingerprints": {"at_freeze": FROZEN_FP, "after_update": AFTER_FP},
    "transition_flip": {f"{a}->{b}": v for (a, b), v in tm.items()},
    "learned_rate": round(learned, 4),
    "learned_ci95": [round(lo, 4), round(hi, 4)],
    "regression_stays": {f"{a}->{b}": v for (a, b), v in rm.items()},
    "control_never": {t: dict(collections.Counter(D["never"]))
                      for t, D in (("before", BEFORE), ("after", AFTER))},
    "scope": ("The update is a withheld 30% of subject-relation PAIRS "
              "(n_update_pairs); questions over them are unanswerable before "
              "and answerable after, measured on the SAME QUESTIONS "
              "(n_flip_questions) with artifacts frozen at T0. The two counts "
              "differ because they count different things, which an "
              "adjudicator read as 457 unaccounted cases (D156). "
              "`learned_rate` is 432/1200 of everything evaluated; the "
              "separate 0.366 quoted in the claims table is 432/1179 of what "
              "the store could not answer. Frozen means FINGERPRINT-VERIFIED "
              "here and not merely by construction: basis, coordinates and "
              "head are hashed at T0 and re-hashed after the update, and the "
              "run aborts on any difference (D157). `disbelief` is renamed "
              "`unanswered`: an open-world store that finds no claim has not "
              "established falsity. The never-answerable control is what "
              "distinguishes learning from simply starting to answer "
              "everything."),
}
(ROOT / "results" / "exp38_update.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp38_update.json")
