"""M4 acceptance — PgStore vs recorded batteries (D67 gate).

(a) K6 pooled post-edit battery THROUGH PgStore (1,043 supersessions,
    hybrid scoring, walks) vs k6_postedit.json.
(b) Exact walk parity: 300 sampled gold-chain walks, PgStore output must
    EQUAL MemoryStore output index-for-index.
(c) Scale: 100k exact + HNSW, 1M HNSW; registered budget <=50 ms/query @1M.

Usage: .venv/bin/python scripts/probe_store_pg_m4.py
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
_src = (ROOT / "scripts" / "k6_stage3_edits.py").read_text()
_head = _src.split("# ---- metric 3a")[0].replace(
    'ROOT = Path(__file__).resolve().parent.parent', f'ROOT = Path("{ROOT}")')
exec(_head)  # noqa: S102 — store (MemoryStore, edited), walker, plan, ...
from codec.manifest import run_manifest, wilson_ci   # noqa: E402
from codec.memory_store import id_tokens             # noqa: E402
from codec.store_pg import PgStore                   # noqa: E402
from codec.walker import ChannelWalker               # noqa: E402

print("[pg] porting edited pooled store into Postgres...", flush=True)
pg = PgStore.from_store(store, table="k6_battery")
wk_pg = ChannelWalker(pg, protos={r: rel_entry[r]["proto"] for r in RELS},
                      ops={r: rel_entry[r]["t"] for r in RELS})

base = json.loads((ROOT / "results" / "k6_postedit.json").read_text())
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
        if p is not None and not wk_pg.abstain_hop1(
                id_tokens([h["subject"]]), p[0]):
            got = wk_pg.walk(id_tokens([h["subject"]]), p)
        t_all += time.perf_counter() - t0
        n_all += 1
        hit += got is not None and fact_obj.get(got) in golds
    fp = base["post_edit"][nh]["p1"]
    res[nh] = {"p1": hit / len(rows), "n": len(rows), "fp32_ref": fp,
               "p1_ci95": wilson_ci(hit, len(rows))}
    print(f"[pg {nh}] P@1={hit/len(rows):.3f} (ref {fp:.3f})", flush=True)
print(f"[pg] {1000*t_all/n_all:.0f} ms/question (MemoryStore ref "
      f"{base['ms_per_question']:.0f})", flush=True)

# (b) exact parity on sampled walks
rng = np.random.default_rng(0)
sample = rng.choice(len(hops), 300, replace=False)
mism = tried = 0
for i in sample:
    h = hops[i]
    p = plan(Zh[i], h["subject"])
    if p is None:
        continue
    tried += 1
    a = walker.walk(id_tokens([h["subject"]]), p)
    b = wk_pg.walk(id_tokens([h["subject"]]), p)
    mism += a != b
print(f"[parity] {tried} walks, mismatches={mism}", flush=True)

# (c) scale
bench = {}
for N, use_hnsw in ((100_000, False), (100_000, True), (1_000_000, True)):
    tbl = f"bench_{N}"
    big = PgStore(table=tbl, fresh=(not use_hnsw or N == 1_000_000))
    if len(big.texts) < N:
        made = len(big.texts)
        while made < N:
            n = min(50_000, N - made)
            Zr = rng.normal(size=(n, 1024)).astype(np.float32)
            big.add_batch(Zr, [set() for _ in range(n)], [""] * n)
            made += n
            if made % 200_000 == 0:
                print(f"  [load {tbl}] {made:,}", flush=True)
    if use_hnsw:
        t0 = time.perf_counter()
        big.build_hnsw()
        print(f"  [hnsw {tbl}] built in {time.perf_counter()-t0:.0f}s",
              flush=True)
    qs = rng.normal(size=(30, 1024)).astype(np.float32)
    t0 = time.perf_counter()
    for q in qs:
        big.query(q, None, k=5, id_weight=0.0)
    dt = (time.perf_counter() - t0) / len(qs) * 1000
    key = f"{N}{'_hnsw' if use_hnsw else ''}"
    bench[key] = dt
    print(f"[bench {key}] {dt:.1f} ms/query", flush=True)

(ROOT / "results" / "store_pg_m4.json").write_text(json.dumps(
    {"k6_battery": res, "ms_per_question": 1000 * t_all / n_all,
     "walk_parity": {"n": tried, "mismatches": mism},
     "bench_ms": bench,
     "manifest": run_manifest(seed=0)}, indent=2))
print("[done] results/store_pg_m4.json", flush=True)
