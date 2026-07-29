"""Refusal for the residual walker — measured against UNANSWERABLE questions (D118).

D117 bought 0.912 on held-out compositions and gave up the property this
project is actually built around: abstention went to 0.000. The walker
always answers. When the residual cannot be spent it returns whatever
partial frontier it reached, which is a wrong-answer generator by
construction — a 1-hop result handed back for a 2-hop question.

The refusal signal is free and already computed: the UNEXPLAINED RESIDUAL.
The head predicts a sum of relation coordinates whose magnitude encodes how
many relations the question involves; if the walk cannot spend it against
anything reachable from that subject, the question was not answerable from
here and the honest output is an abstention, not a partial walk.

**The measurement problem, which matters more than the mechanism.** Every
hop question in D111-D117 is answerable by construction — they were
enumerated FROM the store. A refuser evaluated only on answerable questions
cannot be distinguished from a refuser that never fires, and audit law #6
says a threshold calibrated where the failure is absent buys nothing. So
this builds an unanswerable population deliberately, and the hard kind:
subjects where the FIRST relation is walkable but the second yields nothing
downstream. Those are exactly the cases where D117 returns a confident
partial answer. Subjects with no outgoing edge at all are excluded — the
walker already abstains on those trivially, and counting them would inflate
the refusal rate for free.

Reported as two populations, never averaged into one number:
  answerable    — correct / wrong / abstain (abstention costs coverage)
  unanswerable  — refused / answered anyway (answering costs correctness)

Usage: .venv/bin/python scripts/exp25_refusal.py
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

SEED, MAX_STEPS, MIN_GAIN = 0, 4, 0.2
LABELS = {"P_CITES": "cites", "P_INTRODUCES": "introduces",
          "P_EVALUATES_ON": "evaluates on", "P_BUILDS_ON": "builds on",
          "P_COMPARES_TO": "compares to"}
NP = {"P_CITES": ["the works {s} cites", "the papers referenced by {s}"],
      "P_INTRODUCES": ["the method introduced by {s}", "what {s} proposes"],
      "P_BUILDS_ON": ["what {s} builds on", "the model {s} is based on"],
      "P_COMPARES_TO": ["the baselines {s} compares against",
                        "the systems {s} is measured against"],
      "P_EVALUATES_ON": ["the benchmarks {s} evaluates on",
                         "the datasets {s} is tested on"]}
Q = {"P_CITES": ["What do {np} cite?", "What prior work do {np} draw on?"],
     "P_INTRODUCES": ["What do {np} introduce?", "What method do {np} propose?"],
     "P_BUILDS_ON": ["What do {np} build on?", "What are {np} based on?"],
     "P_COMPARES_TO": ["What do {np} compare against?",
                       "Which baselines do {np} use?"],
     "P_EVALUATES_ON": ["What do {np} evaluate on?",
                        "Which datasets are {np} tested on?"]}

world = json.loads((ROOT / "data" / "real_world_ai_hops.json").read_text())
facts, queries, hops = world["facts"], world["queries"], world["hops"]
HOLD = set(world["holdout_compositions"])
HELD_PH = set(world["held_out_phrasings"])
RELS = sorted({f["relation"] for f in facts})
Zq = np.load(ROOT / "results" / "real_world_ai_emb.npz")["Zq"]
Zh = np.load(ROOT / "results" / "real_world_ai_hop_emb.npz")["Zh"]
Zlab = np.load(ROOT / "results" / "exp24_label_emb.npz")["Zlab"]
RC = {r: Zlab[i] for i, r in enumerate(RELS)}

kb = KB(backend="pg", table="poc")
gold = collections.defaultdict(set)
for c in kb.claims:
    if c["pid"] in RELS and c["page"].startswith("arxiv:"):
        gold[(c["subject"], c["pid"])].add(c["object"])
avail = collections.defaultdict(set)
for (s, r) in gold:
    avail[s].add(r)


def chain_yield(subject, chain):
    cur = {subject}
    for r in chain:
        nxt = set()
        for s in cur:
            nxt |= gold.get((s, r), set())
        if not nxt:
            return set()
        cur = nxt
    return cur


# ---- unanswerable population: r1 walkable, r2 empty downstream ----
kinds = sorted({h["kind"] for h in hops})
unans = []
for kind in kinds:
    r1, r2 = kind.split(">")
    cands = [s for s in avail if r1 in avail[s]]
    for s in cands:
        if chain_yield(s, [r1, r2]):
            continue                          # answerable, not wanted here
        if not gold.get((s, r1)):
            continue                          # trivial: nothing to walk
        for a in range(len(NP[r1])):
            for b in range(len(Q[r2])):
                unans.append({"kind": kind, "chain": [r1, r2], "subject": s,
                              "text": Q[r2][b].format(
                                  np=NP[r1][a].format(s=s))})
rng = np.random.default_rng(SEED)
if len(unans) > 6000:
    unans = [unans[i] for i in rng.choice(len(unans), 6000, replace=False)]
print(f"{len(unans)} UNANSWERABLE questions built (first relation walkable, "
      f"chain yields nothing)", flush=True)

ucache = ROOT / "results" / "exp25_unans_emb.npz"
if ucache.exists():
    Zu = np.load(ucache)["Zu"]
    assert len(Zu) == len(unans), "unanswerable set drifted; delete cache"
else:
    Zu = P.unit(P.embed_texts([u["text"] for u in unans]))
    np.savez(ucache, Zu=Zu)
print(f"unanswerable embeddings {Zu.shape}", flush=True)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

Xs, Ys = [], []
for i, q in enumerate(queries):
    if q["kind"] == "single" and q["phrasing_idx"] not in HELD_PH:
        Xs.append(Zq[i])
        Ys.append(RC[q["relation"]])
for i, h in enumerate(hops):
    if h["kind"] not in HOLD:
        Xs.append(Zh[i])
        Ys.append(RC[h["chain"][0]] + RC[h["chain"][1]])
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
print(f"sum-head trained on {len(Xs)} rows", flush=True)


def walk(subject, target):
    """Returns (path, frontier, unexplained). `unexplained` is the norm of
    the residual the walk could not spend, normalised by the predicted
    magnitude — 0 means the store fully accounted for the question."""
    resid, frontier, path = target.copy(), {subject}, []
    for _ in range(MAX_STEPS):
        options = set()
        for s in frontier:
            options |= avail.get(s, set())
        best, best_g = None, MIN_GAIN
        for r in options:
            g = float(resid @ RC[r])
            if g > best_g:
                best, best_g = r, g
        if best is None:
            break
        nxt = set()
        for s in frontier:
            nxt |= gold.get((s, best), set())
        if not nxt:
            break
        frontier, path = nxt, path + [best]
        resid = resid - RC[best]
    denom = float(np.linalg.norm(target)) + 1e-9
    return path, frontier, float(np.linalg.norm(resid)) / denom


def score(idxs_or_rows, Z, is_hop):
    with torch.no_grad():
        pr = head(torch.tensor(Z)).numpy()
    rows = []
    for j, item in enumerate(idxs_or_rows):
        h = hops[item] if is_hop else item
        path, got, unexp = walk(h["subject"], pr[j])
        if is_hop:
            ok = bool(got) and facts[h["answer_fact"]]["object"] in got
        else:
            ok = False
        rows.append({"unexp": unexp, "empty": not (path and got), "ok": ok})
    return rows


held_i = [i for i, h in enumerate(hops) if h["kind"] in HOLD]
seen_i = [i for i, h in enumerate(hops) if h["kind"] not in HOLD]
seen_s = list(rng.choice(seen_i, min(3000, len(seen_i)), replace=False))
print("scoring populations...", flush=True)
R_seen = score(seen_s, Zh[seen_s], True)
R_held = score(held_i, Zh[held_i], True)
R_un = score(unans, Zu, False)


def tally(rows, thr, answerable):
    c = collections.Counter()
    for r in rows:
        if r["empty"] or r["unexp"] > thr:
            c["abstain"] += 1
        elif answerable:
            c["correct" if r["ok"] else "wrong"] += 1
        else:
            c["wrong"] += 1                  # answered an unanswerable one
    return c


print(f"\nunexplained-residual threshold sweep")
print(f"{'thr':>6} | {'seen corr':>9} {'seen wrong':>10} | "
      f"{'held corr':>9} {'held wrong':>10} {'held abst':>9} | "
      f"{'UNANS refused':>13}")
sweep = {}
THRS = [1.01, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]
for t in THRS:
    cs, ch, cu = (tally(R_seen, t, True), tally(R_held, t, True),
                  tally(R_un, t, False))
    ns, nh, nu = sum(cs.values()), sum(ch.values()), sum(cu.values())
    sweep[t] = {"seen": dict(cs), "held": dict(ch), "unans": dict(cu)}
    print(f"{t:6.2f} | {cs['correct']/ns:9.3f} {cs['wrong']/ns:10.3f} | "
          f"{ch['correct']/nh:9.3f} {ch['wrong']/nh:10.3f} "
          f"{ch['abstain']/nh:9.3f} | {cu['abstain']/nu:13.3f}")

# Calibrate on a population that EXHIBITS the failure (audit law #6): the
# seen compositions plus the unanswerable ones, which is where wrong answers
# actually live. Rule fixed before reading the sweep: the largest threshold
# (most coverage) whose UNANSWERABLE refusal rate is at least 0.90.
THR = next((t for t in THRS
            if (lambda c: c["abstain"] / sum(c.values()) >= 0.90)(
                tally(R_un, t, False))), THRS[-1])
ch, cu, cs = (tally(R_held, THR, True), tally(R_un, THR, False),
              tally(R_seen, THR, True))
nh, nu = sum(ch.values()), sum(cu.values())
a = ch["correct"] + ch["wrong"]
print(f"\nselected threshold {THR} (largest with unanswerable refusal >= 0.90)")
print(f"  ANSWERABLE   (held-out comps)  correct {ch['correct']/nh:.3f}  "
      f"wrong {ch['wrong']/nh:.3f}  abstain {ch['abstain']/nh:.3f}  "
      f"precision {(ch['correct']/a if a else 0):.3f}")
print(f"  UNANSWERABLE                   refused {cu['abstain']/nu:.3f}  "
      f"answered anyway {cu['wrong']/nu:.3f}")
lo, hi = wilson_ci(cu["abstain"], nu)
print(f"  refusal CI95 [{lo:.3f}, {hi:.3f}]")
print(f"\nD117 (no refusal): held-out correct 0.912 wrong 0.088 abstain 0.000;"
      f" unanswerable refused 0.000 by construction")

out = {
    "manifest": run_manifest(seed=SEED, config={"MIN_GAIN": MIN_GAIN,
                                                "MAX_STEPS": MAX_STEPS}),
    "n_unanswerable": len(unans), "selected_threshold": THR,
    "sweep": {str(k): v for k, v in sweep.items()},
    "selected": {"answerable_held_out": dict(ch), "unanswerable": dict(cu),
                 "seen": dict(cs)},
    "unanswerable_refusal_ci95": [round(lo, 4), round(hi, 4)],
    "scope": ("Unanswerable questions are constructed so the FIRST relation "
              "is walkable and the chain still yields nothing — the case "
              "where D117 returns a confident partial answer. Subjects with "
              "no outgoing edges are excluded, since the walker abstains on "
              "those trivially and they would inflate the refusal rate. "
              "Answerable and unanswerable are reported separately and never "
              "averaged."),
}
(ROOT / "results" / "exp25_refusal.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp25_refusal.json")
