"""E1 — store-key quantization (07-plan Track E; D28 pre-justifies).

Variants: fp32 reference, int8 per-dim, binary (sign), anchor-code (key
replaced by nearest of N k-means anchors). Metric: v3 single-hop relational
addressing (+t, +t+id — the shipping config) plus bytes/key.

Usage: .venv/bin/python scripts/probe_store_quant.py
"""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from codec.memory_store import MemoryStore, fit_translation, id_tokens
from codec.structure_channel import hash_test_mask
from codec.evals.anchors import fit_anchors
from codec.role_bits import _nlp

def unit(X): return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)

world = json.loads((ROOT / "data" / "closed_world_v3.json").read_text())
facts, queries = world["facts"], world["queries"]
z = np.load(ROOT / "results" / "closed_world_v3_emb.npz")
Zf, Zq = z["Zf"], z["Zq"]
nlp = _nlp()
HELD = set(world["held_out_phrasings"])
ans = [i for i, q in enumerate(queries) if q["kind"] == "single"]
seen = [i for i in ans if queries[i]["phrasing_idx"] not in HELD]
m = hash_test_mask([queries[i]["text"] for i in seen], frac=0.7)
fit_idx = [i for i, t in zip(seen, m) if not t]
test = [i for i, t in zip(seen, m) if t][:1200]
t_by_rel = {}
for rel in {queries[i]["relation"] for i in ans}:
    tr = [i for i in fit_idx if queries[i]["relation"] == rel]
    t_by_rel[rel] = fit_translation(Zq[tr], np.stack([Zf[queries[i]["fact_idx"]] for i in tr]))
qids = {i: id_tokens([t.text.rstrip("'s") if t.text.endswith("'s") else t.text
                      for t in nlp(queries[i]["text"]) if t.pos_ == "PROPN"]
                     + [t.text for t in nlp(queries[i]["text"]) if t.like_num]) for i in test}

def variants():
    yield "fp32", Zf.copy(), 4096
    s = np.abs(Zf).max(0, keepdims=True) / 127.0
    yield "int8", unit((np.round(Zf / s).astype(np.int8)).astype(np.float32) * s), 1024
    yield "binary", unit(np.sign(Zf).astype(np.float32)), 128
    for N in (512, 4096):
        A = unit(fit_anchors(Zf, N))
        code = np.argmax(Zf @ A.T, axis=1)
        yield f"anchor{N}", A[code], 2

rows = []
for name, Zk, bytes_ in variants():
    store = MemoryStore()
    for f, zk in zip(facts, Zk):
        store.add(zk, f["entities"] + f["numbers"], f["text"])
    h_t = h_ti = 0
    for i in test:
        zt = Zq[i] + t_by_rel[queries[i]["relation"]]
        h_t += store.query(zt, None, k=1, id_weight=0)[0][0] == queries[i]["fact_idx"]
        h_ti += store.query(zt, qids[i], k=1, id_weight=0.5)[0][0] == queries[i]["fact_idx"]
    rows.append({"variant": name, "bytes_per_key": bytes_,
                 "p1_t": h_t / len(test), "p1_t_id": h_ti / len(test)})
    print(f"[{name:>9}] {bytes_:>5}B/key  +t={h_t/len(test):.3f}  +t+id={h_ti/len(test):.3f}")
(ROOT / "results" / "store_quant_e1.json").write_text(json.dumps(
    {"generated_at": datetime.now(timezone.utc).isoformat(), "n_test": len(test),
     "rows": rows}, indent=2))
print("[done] results/store_quant_e1.json")
