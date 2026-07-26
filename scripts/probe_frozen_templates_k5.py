"""K5 — frozen-generator eval: templates written AFTER the system froze.

The held-out-phrasings eval (rows 8-11) shared the original template bank's
authorial style. These templates were written 2026-07-25, after D44's heads,
artifacts, and thresholds were all fixed, in deliberately different
registers (telegraphic, bureaucratic, colloquial-indirect, journalistic).
Nothing here appeared in any training or calibration path.

Entity ALIASES are explicitly out of scope: the id channel matches surface
tokens, so aliasing needs alias entries in the store (open item, logged).

Usage: .venv/bin/python scripts/probe_frozen_templates_k5.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from codec.manifest import run_manifest, wilson_ci                # noqa: E402
import v06_pipeline as P                                          # noqa: E402

SINGLE_T = {
    "capital_of": ["Capital city of {s} — which one is it?",
                   "State, for the record, the capital of {s}.",
                   "A quick geography check: {s}'s capital goes by what name?"],
    "largest_city_of": ["Biggest urban center in {s}?",
                        "Of all cities in {s}, which has the most people?",
                        "The single largest city {s} has — name it."],
    "located_in": ["{s}: which country claims it?",
                   "On a map, {s} falls inside which nation's borders?",
                   "File {s} under its country — which is?"],
    "population_of": ["Headcount for {s}?",
                      "Resident count of {s}, please.",
                      "{s} is home to how many people?"],
    "mayor_of": ["City hall of {s} — who sits at the top?",
                 "The person currently mayoring {s} is…?",
                 "Name the official who runs {s}."],
    "ceo_of": ["Top executive at {s}?",
               "The corner office at {s} belongs to whom?",
               "{s}'s chief executive — give the name."],
    "born_in": ["Birth year of {s}?",
                "{s} came into the world in which year?",
                "Records show {s} was born when, exactly?"],
    "founded_in": ["Founding year of {s}?",
                   "{s} first opened its doors in which year?",
                   "Date the establishment of {s} for me — the year."],
    "headquartered_in": ["Home base of {s}?",
                         "{s} runs its operations out of which city?",
                         "The head office of {s} sits where?"],
}

HOP_T = {
    "cap_pop": ["Headcount for the capital of {s}?",
                "The capital of {s} is home to how many people?"],
    "big_pop": ["Resident count of {s}'s biggest urban center, please.",
                "Of all cities in {s}, the largest holds how many people?"],
    "ceo_born": ["Birth year of the top executive at {s}?",
                 "The person holding {s}'s corner office was born when?"],
    "mayor_born": ["Birth year of the official who runs {s}?",
                   "The person at the top of {s}'s city hall — born in "
                   "which year?"],
    "hq_pop": ["Headcount for the city {s} runs its operations out of?",
               "The home base of {s} holds how many residents?"],
    "hq_loc": ["The city {s} operates from falls inside which nation's "
               "borders?",
               "Which country claims the home base of {s}?"],
    "hq_mayor": ["Who sits at the top of city hall where {s} keeps its "
                 "head office?",
                 "The city {s} operates from — name its mayor."],
    "loc_cap": ["Capital of the country that claims {s} — which one?",
                "The nation {s} falls inside has which capital city?"],
    "loc_big": ["Biggest urban center of the country claiming {s}?",
                "The nation {s} falls inside — its largest city is?"],
    "cap_mayor": ["Who runs city hall in {s}'s capital?",
                  "The capital of {s} — name the official at the top of it."],
    "loc_cap_pop": ["Headcount for the capital of the nation claiming {s}?",
                    "The country {s} falls inside has a capital — how many "
                    "people call it home?"],
    "hq_loc_cap": ["Capital of the country claiming {s}'s home base?",
                   "The nation where {s} keeps its head office — its "
                   "capital is?"],
}

w = json.loads((ROOT / "data" / "closed_world_v4.json").read_text())
facts, queries, hops = w["facts"], w["queries"], w["hops"]
Zf, Zq, Zh = P.load_or_build_emb(
    w, ROOT / "results" / "closed_world_v4_emb.npz")
art = P.build_artifacts(w, Zf, Zq)
det, ans, _ = P.train_heads_with(art, w, Zq, Zh)
plan = P.make_planner(det, ans, art)
walker = art["walker"]

rng = random.Random(7)

# fresh single-hop questions
srows = []
for rel, ts in SINGLE_T.items():
    fs = [i for i, f in enumerate(facts) if f["relation"] == rel]
    for j, fi in enumerate(rng.sample(fs, 40)):
        srows.append({"fact_idx": fi, "relation": rel,
                      "text": ts[j % len(ts)].format(s=facts[fi]["subject"])})
# fresh hop questions (reuse gold chains/answers, new surface text)
hrows = []
for kind, ts in HOP_T.items():
    ks = [h for h in hops if h["kind"] == kind]
    for j, h in enumerate(rng.sample(ks, 30)):
        hrows.append({**h, "text": ts[j % len(ts)].format(s=h["subject"])})

cache = ROOT / "results" / "frozen_templates_k5_emb.npz"
import numpy as np
if cache.exists():
    z = np.load(cache)
    Zs, Zhn = z["Zs"], z["Zhn"]
else:
    Zs = P.embed_texts([r["text"] for r in srows])
    Zhn = P.embed_texts([r["text"] for r in hrows])
    np.savez(cache, Zs=Zs, Zhn=Zhn)

res = {}
hit = 0
for r, zq in zip(srows, Zs):
    p = plan(zq, facts[r["fact_idx"]]["subject"])
    if p and not walker.abstain_hop1(P.qids_of(r["text"]), p[0]):
        hit += walker.walk(P.qids_of(r["text"]), p) == r["fact_idx"]
res["single"] = {"p1": hit / len(srows), "n": len(srows)}
print(f"[k5      single] P@1={hit/len(srows):.3f} (n={len(srows)}) "
      f"[held-out-phrasings baseline 0.993]", flush=True)

HOLD = set(w["holdout_compositions"])
for kind in sorted(HOP_T):
    rows = [(r, Zhn[i]) for i, r in enumerate(hrows) if r["kind"] == kind]
    pok = hit = 0
    for r, zq in rows:
        p = plan(zq, r["subject"])
        pok += p == r["chain"]
        if p and not walker.abstain_hop1(P.qids_of(r["text"]), p[0]):
            hit += walker.walk(P.qids_of(r["text"]), p) == r["answer_fact"]
    res[kind] = {"chain": pok / len(rows), "p1": hit / len(rows),
                 "n": len(rows)}
    flag = " [HOLDOUT]" if kind in HOLD else ""
    print(f"[k5 {kind:>12}] chain={pok/len(rows):.3f} "
          f"P@1={hit/len(rows):.3f} (n={len(rows)}){flag}", flush=True)

for row in res.values():
    for m in ("chain", "p1"):
        if m in row:
            row[m + "_ci95"] = wilson_ci(round(row[m] * row["n"]), row["n"])

out = ROOT / "results" / "frozen_templates_k5.json"
out.write_text(json.dumps(
    {"results": res,
     "manifest": run_manifest(seed=7, inputs={
         "world": ROOT / "data" / "closed_world_v4.json"},
         config={"templates_written": "2026-07-25 post-freeze",
                 "aliases": "out of scope — id channel needs alias entries"})},
    indent=2))
print(f"[done] {out.relative_to(ROOT)}")
