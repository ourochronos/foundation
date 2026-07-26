"""K6 stage 1 — MQuAKE-CF-3k -> world format + embeddings (docs/09).

Case-level 80/20 split (seed 0): heads/operators see TRAIN cases only.
Facts deduped by labeled triple; pre-edit world here; edits at run stage.

Usage: .venv/bin/python scripts/k6_build_world.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

cases = json.loads((ROOT / "data" / "mquake" / "MQuAKE-CF-3k.json").read_text())
rng = np.random.default_rng(0)
order = rng.permutation(len(cases))
train_ids = {cases[i]["case_id"] for i in order[: int(0.8 * len(cases))]}

fact_i, facts = {}, []
def add_fact(s, r, o, text):
    key = (s, r, o)
    if key not in fact_i:
        fact_i[key] = len(facts)
        facts.append({"subject": s, "relation": r, "object": o,
                      "text": text, "entities": [s, o], "numbers": []})
    return fact_i[key]

queries, hops = [], []
for c in cases:
    tl, tr = c["orig"]["triples_labeled"], c["orig"]["triples"]
    if len(tl) != len(c["single_hops"]):
        continue
    # post-edit chains traverse REAL facts that only appear in
    # new_single_hops (facts of the unedited world beyond the edit point);
    # they belong in the base store. Counterfactual edit_triples do NOT —
    # they enter only via supersession at the edits stage.
    edit_keys = {tuple(t) for t in c["orig"]["edit_triples"]}
    ntl, ntr = c["orig"]["new_triples_labeled"], c["orig"]["new_triples"]
    if len(ntl) == len(c["new_single_hops"]):
        for (sl, rl, ol), t, h in zip(ntl, ntr, c["new_single_hops"]):
            if tuple(t) not in edit_keys:
                add_fact(sl, t[1], ol,
                         f"{h['cloze'].strip()} {h['answer'].strip()}.")
    chain, last = [], None
    ok = True
    for (sl, rl, ol), (s, r, o), h in zip(tl, tr, c["single_hops"]):
        text = f"{h['cloze'].strip()} {h['answer'].strip()}."
        fi = add_fact(sl, r, ol, text)
        chain.append(r)
        last = fi
        queries.append({"fact_idx": fi, "relation": r, "kind": "single",
                        "case_id": c["case_id"],
                        "train": c["case_id"] in train_ids,
                        "text": h["question"]})
    if not ok:
        continue
    for qi, qt in enumerate(c["questions"]):
        hops.append({"kind": f"{len(chain)}hop", "case_id": c["case_id"],
                     "train": c["case_id"] in train_ids,
                     "subject": tl[0][0], "chain": chain,
                     "answer_fact": last, "answer": c["answer"],
                     "phrasing": qi, "text": qt})

world = {"facts": facts, "queries": queries, "hops": hops,
         "train_case_ids": sorted(train_ids)}
(ROOT / "data" / "mquake" / "world_cf3k.json").write_text(json.dumps(world))
rels = sorted({f["relation"] for f in facts})
print(f"[k6-world] {len(facts)} unique facts, {len(queries)} single-q, "
      f"{len(hops)} hop-q, {len(rels)} relations", flush=True)

import v06_pipeline as P
cache = ROOT / "results" / "mquake_cf3k_emb_v2.npz"
if not cache.exists():
    Zf = P.embed_texts([f["text"] for f in facts])
    Zq = P.embed_texts([q["text"] for q in queries])
    Zh = P.embed_texts([h["text"] for h in hops])
    np.savez(cache, Zf=Zf, Zq=Zq, Zh=Zh)
print("[done] data/mquake/world_cf3k.json + results/mquake_cf3k_emb.npz",
      flush=True)
