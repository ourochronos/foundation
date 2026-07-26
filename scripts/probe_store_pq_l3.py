"""L3 acceptance — PQStore vs MemoryStore on the K6 pooled post-edit
battery (must reproduce within CI), plus latency/memory at 100k and 1M
entries (budget: ≤50 ms/query at 1M).

Usage: .venv/bin/python scripts/probe_store_pq_l3.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from codec.manifest import run_manifest, wilson_ci                # noqa: E402
from codec.memory_store import MemoryStore, fit_translation, id_tokens  # noqa: E402
from codec.store_pq import PQStore                                # noqa: E402
from codec.walker import ChannelWalker                            # noqa: E402
from codec import whiten as W                                     # noqa: E402
import v06_pipeline as P                                          # noqa: E402

# ---- codebooks from the corpus (J2b recipe) -------------------------------
bk_cache = ROOT / "results" / "pq_codebooks_s128.npz"
if bk_cache.exists():
    books = np.load(bk_cache)["books"]
else:
    wh = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    X = P.unit(W.apply(np.load(ROOT / "results" / "dense_v0.npy"), wh))
    books = PQStore.fit_codebooks(X, S=128, K=256)
    np.savez(bk_cache, books=books)
print("[books] ready", flush=True)

# ---- K6 pooled post-edit battery through PQStore --------------------------
_src = (ROOT / "scripts" / "k6_stage4_l1.py").read_text()
_head = _src.split("hitk = Counter()")[0].replace(
    'ROOT = Path(__file__).resolve().parent.parent', f'ROOT = Path("{ROOT}")')
exec(_head)  # noqa: S102 — facts, Zf, edit_emb, rel_entry, det, ans, ...
from collections import Counter                                   # noqa: E402

base = json.loads((ROOT / "results" / "k6_postedit.json").read_text())

pq = PQStore(books)
pq.add_batch(Zf, [set(f["entities"]) for f in facts],
             [f["text"] for f in facts])
# rebuild ids as token sets (add_batch got raw entity lists as sets of strings)
pq.ids = [id_tokens(f["entities"]) for f in facts]
pq.content_ids = [set(x) for x in pq.ids]
fact_obj = {i: f["object"] for i, f in enumerate(facts)}
for (cid, key), (zn, rw) in edit_emb.items():
    ni = pq.add(zn, [rw["subject"], rw["target_new"]["str"]],
                f"{rw['subject']}|{rw['relation_id']}|"
                f"{rw['target_new']['str']}")
    pq.supersede(fact_key[key], ni)
    fact_obj[ni] = rw["target_new"]["str"]
subj_slots, obj_slots = {}, {}
for i in range(len(pq.texts)):
    if pq.shadowed[i]:
        continue
    if i < len(facts):
        s_, r_, o_ = facts[i]["subject"], facts[i]["relation"], \
            facts[i]["object"]
    else:
        s_, r_, o_ = pq.texts[i].split("|")
    subj_slots.setdefault(s_, set()).add(r_)
    obj_slots.setdefault(o_, set()).add(r_)
BRIDGE = {(a, b) for n in set(subj_slots) | set(obj_slots)
          for a in obj_slots.get(n, ()) for b in subj_slots.get(n, ())}
walker = ChannelWalker(pq, protos={r: rel_entry[r]["proto"] for r in RELS},
                       ops={r: rel_entry[r]["t"] for r in RELS})
rng_cprof = {}
for r in RELS:
    v = np.zeros(KC)
    for i in range(len(facts)):
        if not pq.shadowed[i] and facts[i]["relation"] == r \
                and facts[i]["object"] in clus_of:
            v[clus_of[facts[i]["object"]]] += 1
    rng_cprof[r] = v / (v.sum() + 1e-12)
art = dict(RELS=RELS, rel_entry=rel_entry, rng_cprof=rng_cprof,
           P_name=P_name, name_i=name_i)
plan = P.make_planner(det, ans, art, max_k=4, cand_k=5,
                      link_ok=lambda a, b: (a, b) in BRIDGE,
                      entry_ok=lambda s_, r: r in subj_slots.get(s_, ()))

res, t_all, n_all = {}, 0.0, 0
for nh in ("2hop", "3hop", "4hop"):
    rows = [(h, Zh[i]) for i, h in enumerate(hops)
            if not h["train"] and h["kind"] == nh and h["phrasing"] == 0]
    hit = 0
    for h, zq in rows:
        c = case_by_id[h["case_id"]]
        golds = {c["new_answer"]} | set(c.get("new_answer_alias", []))
        t0 = time.perf_counter()
        p = plan(zq, h["subject"])
        got = None
        if p is not None and not walker.abstain_hop1(
                id_tokens([h["subject"]]), p[0]):
            got = walker.walk(id_tokens([h["subject"]]), p)
        t_all += time.perf_counter() - t0
        n_all += 1
        hit += got is not None and fact_obj.get(got) in golds
    fp = base["post_edit"][nh]["p1"]
    res[nh] = {"p1": hit / len(rows), "n": len(rows), "fp32_ref": fp,
               "p1_ci95": wilson_ci(hit, len(rows))}
    print(f"[pq {nh}] P@1={hit/len(rows):.3f} (fp32: {fp:.3f})", flush=True)
print(f"[pq] {1000*t_all/n_all:.0f} ms/question (fp32 ref "
      f"{base['ms_per_question']:.0f})", flush=True)

# ---- scale bench: 100k and 1M synthetic entries ---------------------------
bench = {}
rng = np.random.default_rng(0)
for N in (100_000, 1_000_000):
    big = PQStore(books)
    chunk = 50_000
    made = 0
    while made < N:
        n = min(chunk, N - made)
        Zr = rng.normal(size=(n, 1024)).astype(np.float32)
        Zr /= np.linalg.norm(Zr, axis=1, keepdims=True)
        big.add_batch(Zr, [set() for _ in range(n)], [""] * n)
        made += n
    qs = rng.normal(size=(50, 1024)).astype(np.float32)
    t0 = time.perf_counter()
    for q in qs:
        big.query(q, None, k=5, id_weight=0.0)
    dt = (time.perf_counter() - t0) / len(qs) * 1000
    mem = big.codes.nbytes / 1e6
    bench[N] = {"ms_per_query": dt, "codes_mb": mem}
    print(f"[bench N={N:,}] {dt:.1f} ms/query, codes {mem:.0f} MB "
          f"(fp32 would be {N*4096/1e6:.0f} MB)", flush=True)
    del big

out = ROOT / "results" / "store_pq_l3.json"
out.write_text(json.dumps(
    {"k6_battery": res, "ms_per_question": 1000 * t_all / n_all,
     "scale_bench": {str(k): v for k, v in bench.items()},
     "manifest": run_manifest(seed=0)}, indent=2))
print(f"[done] {out.relative_to(ROOT)}")
