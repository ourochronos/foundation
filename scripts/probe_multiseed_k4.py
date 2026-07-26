"""K4 — multi-seed spread: the full v0.6 pipeline (own store artifacts, own
heads) retrained per world seed. Reports per-seed headline metrics + spread
so no claim rests on the seed-41 point estimate.

Usage: .venv/bin/python scripts/probe_multiseed_k4.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from codec.manifest import run_manifest, wilson_ci                # noqa: E402
import v06_pipeline as P                                          # noqa: E402

SEEDS = [43, 44]
HEADLINES = ["big_pop", "cap_mayor", "hq_loc_cap", "single", "no_answer"]

per_seed = {}
base = json.loads((ROOT / "results" / "reasoner_v06.json").read_text())
per_seed[41] = {k: base["results"][k] for k in base["results"]}

for s in SEEDS:
    w = json.loads((ROOT / "data" / f"closed_world_v4_s{s}.json").read_text())
    Zf, Zq, Zh = P.load_or_build_emb(
        w, ROOT / "results" / f"closed_world_v4_s{s}_emb.npz")
    art = P.build_artifacts(w, Zf, Zq)
    det, ans, hop_eval = P.train_heads_with(art, w, Zq, Zh)
    plan = P.make_planner(det, ans, art)
    print(f"[seed {s}]", flush=True)
    per_seed[s] = P.evaluate(w, Zq, Zh, art, plan, hop_eval_ids=hop_eval,
                             tag=f"s{s} ")

spread = {}
for k in HEADLINES:
    for m in ("chain", "p1", "abstain"):
        vals = [per_seed[s][k][m] for s in per_seed
                if k in per_seed[s] and m in per_seed[s][k]]
        if len(vals) >= 2:
            spread[f"{k}.{m}"] = {"mean": sum(vals) / len(vals),
                                  "min": min(vals), "max": max(vals),
                                  "values": vals}
print("[spread]", json.dumps(
    {k: [round(v, 3) for v in d["values"]] for k, d in spread.items()},
    separators=(",", ":")), flush=True)

for s, res in per_seed.items():
    for row in res.values():
        if "n" in row:
            for m in ("chain", "p1", "abstain"):
                if m in row and m + "_ci95" not in row:
                    row[m + "_ci95"] = wilson_ci(round(row[m] * row["n"]),
                                                 row["n"])

out = ROOT / "results" / "multiseed_k4.json"
out.write_text(json.dumps(
    {"per_seed": {str(k): v for k, v in per_seed.items()}, "spread": spread,
     "manifest": run_manifest(seed=0, inputs={
         f"world{s}": ROOT / "data" / (f"closed_world_v4_s{s}.json"
                                       if s != 41 else "closed_world_v4.json")
         for s in [41, *SEEDS]})},
    indent=2))
print(f"[done] {out.relative_to(ROOT)}")
