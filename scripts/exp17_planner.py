"""Point the D41/D44 planner at the REAL store (D110).

Everything except the two small heads is closed-form from the world, so
this mostly asks whether the *mechanism* survives real data — participation
types over 618 real subjects instead of a generated ontology, relation
prototypes fit from real question embeddings, and a feasibility gate whose
domain/range centroids come from a corpus nobody designed to be clean.

The heads must be retrained: they are `1024 -> R` and R changed from the
synthetic world's 9 relations to this corpus's 5. That is wiring, not a
result, and it is why the interesting number is the HELD-OUT phrasing
accuracy — training phrasings only measure memorisation (D48).

Reported honestly:
  * seen-phrasing relation accuracy (the floor — memorisation is allowed)
  * HELD-OUT phrasing accuracy (the real number)
  * end-to-end answer accuracy through the walker on the live store
  * abstention, because refusing beats guessing (the 0.000-wrong property)

Usage: .venv/bin/python scripts/exp17_planner.py
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

world = json.loads((ROOT / "data" / "real_world_ai.json").read_text())
facts, queries = world["facts"], world["queries"]
HELD = set(world["held_out_phrasings"])
print(f"{len(facts)} facts / {len(queries)} questions", flush=True)

cache = ROOT / "results" / "real_world_ai_emb.npz"
if cache.exists():
    d = np.load(cache)
    Zf, Zq = d["Zf"], d["Zq"]
else:
    Zf = P.unit(P.embed_texts([f["text"] for f in facts]))
    Zq = P.unit(P.embed_texts([q["text"] for q in queries]))
    np.savez(cache, Zf=Zf, Zq=Zq)
print(f"embeddings {Zf.shape} / {Zq.shape}", flush=True)

art = P.build_artifacts(world, Zf, Zq)
RELS = art["RELS"]
print(f"artifacts built over {len(RELS)} relations: {RELS}", flush=True)

# `hops` is empty for this world (no composed questions yet), so Zh is an
# empty hop-embedding matrix of the right width rather than a stub.
Zh = np.zeros((0, Zq.shape[1]), np.float32)
det, ans, _ = P.train_heads_with(art, world, Zq, Zh, seed=0, epochs=60)

import torch                                                  # noqa: E402


def rel_acc(idxs):
    if not idxs:
        return 0.0, 0
    with torch.no_grad():
        pv = torch.sigmoid(det(torch.tensor(Zq[idxs])))
    pred = [RELS[int(i)] for i in pv.argmax(-1)]
    ok = sum(p == queries[i]["relation"] for p, i in zip(pred, idxs))
    return ok / len(idxs), len(idxs)


seen_i = [i for i, q in enumerate(queries) if q["phrasing_idx"] not in HELD]
held_i = [i for i, q in enumerate(queries) if q["phrasing_idx"] in HELD]
rng = np.random.default_rng(0)
seen_s = list(rng.choice(seen_i, min(4000, len(seen_i)), replace=False))
held_s = list(rng.choice(held_i, min(4000, len(held_i)), replace=False))

a_seen, n_seen = rel_acc(seen_s)
a_held, n_held = rel_acc(held_s)
print(f"\nrelation detection")
print(f"  seen phrasings  {a_seen:.3f}  (n={n_seen})   <- memorisation floor")
print(f"  HELD-OUT        {a_held:.3f}  (n={n_held})   <- the real number")

# per-relation held-out breakdown: an average can hide one dead relation
per = collections.defaultdict(lambda: [0, 0])
with torch.no_grad():
    pv = torch.sigmoid(det(torch.tensor(Zq[held_s])))
for j, i in enumerate(held_s):
    r = queries[i]["relation"]
    per[r][1] += 1
    if RELS[int(pv[j].argmax())] == r:
        per[r][0] += 1
print("\nheld-out by relation")
for r in RELS:
    ok, n = per[r]
    if n:
        print(f"  {r:18s} {ok/n:.3f}  (n={n})")

ci_h = wilson_ci(int(a_held * n_held), n_held)
out = {
    "manifest": run_manifest(seed=0, config={"world": "real_world_ai",
                                             "relations": RELS}),
    "facts": len(facts), "questions": len(queries),
    "relation_detection": {
        "seen_phrasings": round(a_seen, 4),
        "held_out": round(a_held, 4),
        "held_out_ci95": [round(x, 4) for x in ci_h],
        "per_relation_held_out": {r: {"acc": round(v[0] / v[1], 4),
                                      "n": v[1]}
                                  for r, v in per.items() if v[1]},
    },
    "scope": ("Templated questions with 2 of 6 phrasings held out. This "
              "measures whether the planner picks the right relation from "
              "a paraphrase it never trained on — NOT free-form language "
              "understanding. Heads retrained because R changed 9 -> 5; "
              "everything else (participation types, relation entries, "
              "operators, feasibility gate) is closed-form from real data."),
}
(ROOT / "results" / "exp17_planner.json").write_text(json.dumps(out, indent=1))
print(f"\n[done] results/exp17_planner.json")

# ---------------------------------------------------------------------------
# End-to-end through the LIVE store.
#
# Relation accuracy is diagnostic; this is the number the project actually
# claims. A mispredicted relation can fail two ways, and they are not
# equally bad: the feasibility gate can refuse (abstain, costs coverage) or
# the walk can succeed against the wrong relation (WRONG, costs the 0.000
# property). Reported separately, always.
# ---------------------------------------------------------------------------
from foundation.kb import KB                                    # noqa: E402

kb = KB(backend="pg", table="poc")
gold = collections.defaultdict(set)
for c in kb.claims:
    if c["pid"] in RELS and c["page"].startswith("arxiv:"):
        gold[(c["subject"], c["pid"])].add(c["object"])

plan = P.make_planner(det, ans, art)


def walk(subject, path):
    """Execute a planned relation path against the live store."""
    cur = {subject}
    for r in path:
        nxt = set()
        for s in cur:
            nxt |= gold.get((s, r), set())
        if not nxt:
            return set()
        cur = nxt
    return cur


def end_to_end(idxs, label):
    tally = collections.Counter()
    by_ph = collections.defaultdict(collections.Counter)
    for i in idxs:
        q = queries[i]
        f = facts[q["fact_idx"]]
        path = plan(Zq[i], f["subject"])
        key = (q["relation"], q["phrasing_idx"])
        if not path:
            tally["abstain"] += 1; by_ph[key]["abstain"] += 1
            continue
        got = walk(f["subject"], path)
        if not got:
            tally["abstain"] += 1; by_ph[key]["abstain"] += 1
        elif f["object"] in got:
            tally["correct"] += 1; by_ph[key]["correct"] += 1
        else:
            tally["wrong"] += 1; by_ph[key]["wrong"] += 1
    n = sum(tally.values())
    print(f"\nend-to-end on the live store — {label} (n={n})")
    for k in ("correct", "wrong", "abstain"):
        print(f"  {k:8s} {tally[k]:5d}  {tally[k]/n:.3f}")
    ansd = tally["correct"] + tally["wrong"]
    prec = tally["correct"] / ansd if ansd else 0.0
    print(f"  precision-when-answered {prec:.3f}  (n={ansd})")
    return tally, prec, by_ph


t_seen, p_seen, _ = end_to_end(seen_s, "seen phrasings")
t_held, p_held, by_ph = end_to_end(held_s, "HELD-OUT phrasings")

print("\nheld-out, per phrasing (does a bad phrasing abstain or lie?)")
for (r, pi), c in sorted(by_ph.items()):
    n = sum(c.values())
    print(f"  {r:18s} {pi}  correct {c['correct']/n:.3f}  "
          f"wrong {c['wrong']/n:.3f}  abstain {c['abstain']/n:.3f}  (n={n})")

out["end_to_end"] = {
    "seen": {**t_seen, "precision_when_answered": round(p_seen, 4)},
    "held_out": {**t_held, "precision_when_answered": round(p_held, 4),
                 "precision_ci95": [round(x, 4) for x in wilson_ci(
                     t_held["correct"], t_held["correct"] + t_held["wrong"])]},
    "per_phrasing_held_out": {f"{r}#{pi}": dict(c)
                              for (r, pi), c in by_ph.items()},
}
(ROOT / "results" / "exp17_planner.json").write_text(json.dumps(out, indent=1))
print(f"\n[done] results/exp17_planner.json")

# ---------------------------------------------------------------------------
# The answer-type gate.
#
# The feasibility gate asks "is this walk POSSIBLE" — and a mispredicted
# relation that happens to be populated for the subject passes it, which is
# exactly how the 0.177 wrong-rate above happens. Detection confidence does
# not separate those cases (the head is confidently wrong). The answer-TYPE
# head does: it already predicts which participation cluster the answer
# should fall in, but v0.6 only ever used it as a SCORER. Used as a
# REFUSER it turns wrong answers into abstentions, which is the trade this
# project exists to make.
#
# Protocol: threshold chosen on DEV subjects under a rule stated before the
# grid was read — the SMALLEST threshold with dev wrong-rate <= 0.02
# (smallest, so it maximises coverage rather than flattering precision).
# Reported on TEST subjects, whose questions were never used to choose it.
# Phrasings 4-5 are held out in both halves.
# ---------------------------------------------------------------------------
rng_cprof = art["rng_cprof"]
with torch.no_grad():
    app = torch.softmax(ans(torch.tensor(Zq[held_s])), -1).numpy()

gated = []
for j, i in enumerate(held_s):
    q, f = queries[i], facts[queries[i]["fact_idx"]]
    path = plan(Zq[i], f["subject"])
    if not path:
        gated.append(("abstain", 0.0, f["subject"]))
        continue
    got = walk(f["subject"], path)
    o = "abstain" if not got else ("correct" if f["object"] in got else "wrong")
    gated.append((o, float(app[j] @ rng_cprof[path[-1]]), f["subject"]))

subs = sorted({r[2] for r in gated})
np.random.default_rng(1).shuffle(subs)
dev = set(subs[: len(subs) // 2])


def tally_at(thr, in_dev):
    c = collections.Counter()
    for o, fit, s in gated:
        if (s in dev) == in_dev:
            c[o if fit >= thr else "abstain"] += 1
    return c


THR = next((round(0.05 * k, 2) for k in range(17)
            if (lambda c: c["wrong"] / sum(c.values()) <= 0.02)(
                tally_at(round(0.05 * k, 2), True))), 0.8)
T = tally_at(THR, False)
n = sum(T.values())
a = T["correct"] + T["wrong"]
print(f"\nanswer-type gate  thr={THR} (chosen on dev subjects)")
print(f"  TEST correct {T['correct']/n:.3f}  wrong {T['wrong']/n:.3f}  "
      f"abstain {T['abstain']/n:.3f}  precision {T['correct']/a:.3f}  (n={n})")

out["answer_type_gate"] = {
    "threshold": THR,
    "selection_rule": ("smallest threshold with DEV-subject wrong-rate "
                       "<= 0.02; stated before the grid was read"),
    "test": {**T, "precision_when_answered": round(T["correct"] / a, 4),
             "precision_ci95": [round(x, 4) for x in wilson_ci(T["correct"],
                                                               a)]},
    "ungated_test_wrong_rate": round(
        tally_at(0.0, False)["wrong"] / sum(tally_at(0.0, False).values()), 4),
}
(ROOT / "results" / "exp17_planner.json").write_text(json.dumps(out, indent=1))
print(f"[done] results/exp17_planner.json")
