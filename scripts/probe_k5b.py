"""K5b — fresh-author frozen gate (D64/F2): templates by a different
author (Haiku), cue-word-banned, sampled independently (seed 13). No
component has ever seen these strings. Evaluates the CURRENT v0.7 heads.

Usage: .venv/bin/python scripts/probe_k5b.py
"""
from __future__ import annotations
import json, random, sys
from pathlib import Path
import numpy as np, torch
from torch import nn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from codec.manifest import run_manifest, wilson_ci  # noqa: E402
import v06_pipeline as P  # noqa: E402

T = json.loads((ROOT / "data" / "k5b_templates.json").read_text())
w = json.loads((ROOT / "data" / "closed_world_v4.json").read_text())
facts, hops = w["facts"], w["hops"]
Zf, Zq, _ = P.load_or_build_emb(w, ROOT / "results" / "closed_world_v4_emb.npz")
art = P.build_artifacts(w, Zf, Zq)
RELS = art["RELS"]
rng = random.Random(13)
srows, hrows = [], []
for rel, ts in T["single"].items():
    fs = [i for i, f in enumerate(facts) if f["relation"] == rel]
    for j, fi in enumerate(rng.sample(fs, 40)):
        srows.append({"fact_idx": fi, "text":
                      ts[j % len(ts)].format(s=facts[fi]["subject"])})
for kind, ts in T["hops"].items():
    ks = [h for h in hops if h["kind"] == kind]
    for j, h in enumerate(rng.sample(ks, 30)):
        hrows.append({**h, "text": ts[j % len(ts)].format(s=h["subject"])})
cache = ROOT / "results" / "k5b_emb.npz"
if cache.exists():
    z = np.load(cache); Zs, Zh = z["Zs"], z["Zh"]
else:
    Zs = P.embed_texts([r["text"] for r in srows])
    Zh = P.embed_texts([r["text"] for r in hrows])
    np.savez(cache, Zs=Zs, Zh=Zh)
det = nn.Sequential(nn.Linear(1024, 256), nn.GELU(), nn.Linear(256, len(RELS)))
det.load_state_dict(torch.load(ROOT / "checkpoints" / "reasoner_v07_det.pt",
                               weights_only=True))
ans = nn.Sequential(nn.Linear(1024, 128), nn.GELU(), nn.Linear(128, P.KC))
ans.load_state_dict(torch.load(ROOT / "checkpoints" / "reasoner_v06_ans.pt",
                               weights_only=True))
plan = P.make_planner(det, ans, art)
walker = art["walker"]
res = {}
hit = 0
for r, zq in zip(srows, Zs):
    pp = plan(zq, facts[r["fact_idx"]]["subject"])
    if pp and not walker.abstain_hop1(P.qids_of(r["text"]), pp[0]):
        hit += walker.walk(P.qids_of(r["text"]), pp) == r["fact_idx"]
res["single"] = {"p1": hit / len(srows), "n": len(srows)}
print(f"[k5b   single] P@1={hit/len(srows):.3f} (n={len(srows)})", flush=True)
HOLD = set(w["holdout_compositions"])
for kind in sorted(T["hops"]):
    rows = [(r, Zh[i]) for i, r in enumerate(hrows) if r["kind"] == kind]
    pok = hit = 0
    for r, zq in rows:
        pp = plan(zq, r["subject"])
        pok += pp == r["chain"]
        if pp and not walker.abstain_hop1(P.qids_of(r["text"]), pp[0]):
            hit += walker.walk(P.qids_of(r["text"]), pp) == r["answer_fact"]
    res[kind] = {"chain": pok / len(rows), "p1": hit / len(rows),
                 "n": len(rows)}
    fl = " [HOLDOUT]" if kind in HOLD else ""
    print(f"[k5b {kind:>12}] chain={pok/len(rows):.3f} "
          f"P@1={hit/len(rows):.3f} (n={len(rows)}){fl}", flush=True)
for row in res.values():
    for m in ("chain", "p1"):
        if m in row:
            row[m + "_ci95"] = wilson_ci(round(row[m] * row["n"]), row["n"])
(ROOT / "results" / "k5b_probe.json").write_text(json.dumps(
    {"results": res, "manifest": run_manifest(seed=13, inputs={
        "templates": ROOT / "data" / "k5b_templates.json"})}, indent=2))
print("[done] results/k5b_probe.json", flush=True)
