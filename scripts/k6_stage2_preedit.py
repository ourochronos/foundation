"""K6 stage 2 — heads on TRAIN cases; pre-edit multi-hop eval on TEST cases
(pooled store, the honest setting). Metric 2 of docs/09. Hit = walked
fact's object matches answer or any alias.

Usage: .venv/bin/python scripts/k6_stage2_preedit.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from codec.evals.anchors import fit_anchors                       # noqa: E402
from codec.manifest import run_manifest, wilson_ci                # noqa: E402
from codec.memory_store import MemoryStore, fit_translation, id_tokens  # noqa: E402
from codec.walker import ChannelWalker                            # noqa: E402
import v06_pipeline as P                                          # noqa: E402

KC = 8
torch.manual_seed(0)
w = json.loads((ROOT / "data" / "mquake" / "world_cf3k.json").read_text())
facts, queries, hops = w["facts"], w["queries"], w["hops"]
z = np.load(ROOT / "results" / "mquake_cf3k_emb.npz")
Zf, Zq, Zh = z["Zf"], z["Zq"], z["Zh"]
RELS = sorted({f["relation"] for f in facts})
R = len(RELS)
ridx = {r: i for i, r in enumerate(RELS)}

names = sorted({f["subject"] for f in facts} | {f["object"] for f in facts})
name_i = {n: i for i, n in enumerate(names)}
part = np.zeros((len(names), 2 * R), np.float32)
for f in facts:
    part[name_i[f["subject"]], ridx[f["relation"]]] += 1
    part[name_i[f["object"]], R + ridx[f["relation"]]] += 1
P_name = part / (np.linalg.norm(part, axis=1, keepdims=True) + 1e-12)
PC = P.unit(fit_anchors(P_name, KC))
clus_of = {n: int(np.argmax(P_name[i] @ PC.T)) for n, i in name_i.items()}

tr_q = [i for i, q in enumerate(queries) if q["train"]]
rel_entry, rng_cprof = {}, {}
for r in RELS:
    fs = [f for f in facts if f["relation"] == r]
    tr = [i for i in tr_q if queries[i]["relation"] == r][:300]
    if not tr:
        tr = [i for i, q in enumerate(queries)
              if q["relation"] == r][:20]      # rare-rel fallback, logged
    rel_entry[r] = {
        "dom": np.mean([P_name[name_i[f["subject"]]] for f in fs], 0),
        "rng": np.mean([P_name[name_i[f["object"]]] for f in fs], 0),
        "proto": P.unit(Zq[tr].mean(0)),
        "t": fit_translation(Zq[tr], np.stack([Zf[queries[i]["fact_idx"]]
                                               for i in tr]))}
    v = np.zeros(KC)
    for f in fs:
        v[clus_of[f["object"]]] += 1
    rng_cprof[r] = v / (v.sum() + 1e-12)

store = MemoryStore()
for f, zf in zip(facts, Zf):
    store.add(zf, f["entities"], f["text"])
walker = ChannelWalker(store, protos={r: rel_entry[r]["proto"] for r in RELS},
                       ops={r: rel_entry[r]["t"] for r in RELS})

# heads on train split
Xs, Ys, Xa, Ya = [], [], [], []
for i in tr_q:
    y = np.zeros(R, np.float32); y[ridx[queries[i]["relation"]]] = 1
    Xs.append(Zq[i]); Ys.append(y)
    obj = facts[queries[i]["fact_idx"]]["object"]
    Xa.append(Zq[i]); Ya.append(clus_of[obj])
for i, h in enumerate(hops):
    if h["train"]:
        y = np.zeros(R, np.float32)
        for r in h["chain"]:
            y[ridx[r]] = 1
        Xs.append(Zh[i]); Ys.append(y)
        Xa.append(Zh[i]); Ya.append(clus_of[facts[h["answer_fact"]]["object"]])
X, Y = torch.tensor(np.stack(Xs)), torch.tensor(np.stack(Ys))
Xa_t, Ya_t = torch.tensor(np.stack(Xa)), torch.tensor(Ya)
det = nn.Sequential(nn.Linear(1024, 256), nn.GELU(), nn.Linear(256, R))
opt = torch.optim.AdamW(det.parameters(), lr=1e-3, weight_decay=1e-4)
lf = nn.BCEWithLogitsLoss()
for ep in range(40):
    for b in torch.randperm(len(X)).split(512):
        opt.zero_grad(); lf(det(X[b]), Y[b]).backward(); opt.step()
ans = nn.Sequential(nn.Linear(1024, 128), nn.GELU(), nn.Linear(128, KC))
opta = torch.optim.AdamW(ans.parameters(), lr=1e-3)
ce = nn.CrossEntropyLoss()
for ep in range(30):
    for b in torch.randperm(len(Xa_t)).split(512):
        opta.zero_grad(); ce(ans(Xa_t[b]), Ya_t[b]).backward(); opta.step()
torch.save(det.state_dict(), ROOT / "checkpoints" / "k6_det.pt")
torch.save(ans.state_dict(), ROOT / "checkpoints" / "k6_ans.pt")
print(f"[heads] det n={len(X)} ans n={len(Xa_t)} over {R} relations",
      flush=True)

art = dict(RELS=RELS, rel_entry=rel_entry, rng_cprof=rng_cprof,
           P_name=P_name, name_i=name_i)
plan = P.make_planner(det, ans, art)

res = {}
for nh in ("2hop", "3hop", "4hop"):
    rows = [(h, Zh[i]) for i, h in enumerate(hops)
            if not h["train"] and h["kind"] == nh and h["phrasing"] == 0]
    hit = pok = ab = 0
    for h, zq in rows:
        p = plan(zq, h["subject"])
        pok += p == h["chain"]
        if p is None or walker.abstain_hop1(
                id_tokens([h["subject"]]), p[0]):
            ab += 1
            continue
        got = walker.walk(id_tokens([h["subject"]]), p)
        if got is not None:
            aliases = {h["answer"]} \
                | set(sum([c.get("answer_alias", [])
                           for c in [h]], []))
            hit += facts[got]["object"] in aliases or \
                facts[got]["object"] == h["answer"]
    res[nh] = {"p1": hit / len(rows), "chain": pok / len(rows),
               "abstain": ab / len(rows), "n": len(rows)}
    print(f"[k6-pre {nh}] P@1={hit/len(rows):.3f} chain={pok/len(rows):.3f} "
          f"abstain={ab/len(rows):.3f} (n={len(rows)})", flush=True)

for row in res.values():
    row["p1_ci95"] = wilson_ci(round(row["p1"] * row["n"]), row["n"])
out = ROOT / "results" / "k6_preedit.json"
out.write_text(json.dumps(
    {"results": res, "setting": "pooled store, pre-edit, phrasing 0",
     "manifest": run_manifest(seed=0, inputs={
         "world": ROOT / "data" / "mquake" / "world_cf3k.json"})}, indent=2))
print(f"[done] {out.relative_to(ROOT)}")
