"""D93/docs-14 step 1: held-out split + contamination-free experiment store.

Picks 100 held-out AI papers (seed 14) and stages them as 5 shards of 20.
Rebuilds table `linkexp` from every shard dir MINUS the held-out papers'
own P_ASSERTS rows — if the store already held what we are asking the
extractor to rediscover, Arm B would "link" a paper to itself and the
whole measurement would be circular. Their CITATION claims stay in: a
paper whose title is already the object of someone else's P_CITES is
exactly the incremental-ingest case we want to model.

Usage: .venv/bin/python scripts/exp14_build.py
"""
from __future__ import annotations

import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EXP = ROOT / "data" / "exp14"
EXP.mkdir(exist_ok=True)
SRC_SHARDS = ROOT / "data" / "arxiv_ai" / "shards"
PAPERS = ROOT / "data" / "arxiv_ai" / "papers"

# --- pick the held-out papers: only those the baseline actually extracted
# from, so Arm 0 is a real comparison and not an empty cell -----------------
have_claims: dict[str, int] = {}
for f in sorted(SRC_SHARDS.glob("out_*.jsonl")):
    for line in f.read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get("pid"):
            have_claims[d["page"]] = have_claims.get(d["page"], 0) + 1

papers = {}
for p in sorted(PAPERS.glob("*.json")):
    d = json.loads(p.read_text())
    papers["arxiv:" + d["arxiv_id"]] = d

eligible = sorted(pg for pg in have_claims if pg in papers)
rng = random.Random(14)
held = sorted(rng.sample(eligible, 100))
(EXP / "heldout_pages.json").write_text(json.dumps(held, indent=1))
print(f"{len(eligible)} eligible papers -> {len(held)} held out")

# --- stage the 5 shards of 20 (inputs frozen once a fleet runs) ------------
for arm in ("a", "b"):
    (EXP / f"shards_{arm}").mkdir(exist_ok=True)
for i in range(5):
    chunk = [papers[pg] for pg in held[i * 20:(i + 1) * 20]]
    recs = [{"arxiv_id": c["arxiv_id"], "title": c["title"],
             "abstract": c["abstract"], "authors": c.get("authors", []),
             "published": c.get("published", "")} for c in chunk]
    (EXP / "shards_a" / f"in_{i}.json").write_text(json.dumps(recs, indent=1))
print("staged 5 shards of 20 for arm A (arm B inputs get candidates added)")

# --- filtered shard tree: drop held-out papers' own P_ASSERTS rows ---------
FILT = EXP / "store_shards"
if FILT.exists():
    shutil.rmtree(FILT)
FILT.mkdir()
held_set = set(held)
DIRS = ["data/wiki/shards_final", "data/wiki/shards_1k", "data/arxiv/shards",
        "data/arxiv_ai/shards", "data/arxiv_ai/shards_cites",
        "data/hf/shards"]
dropped = kept = 0
for d in DIRS:
    tag = d.replace("/", "_")
    out_dir = FILT / tag
    out_dir.mkdir()
    for f in sorted((ROOT / d).glob("out_*.jsonl")):
        rows = []
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if (r.get("pid") == "P_ASSERTS"
                    and r.get("page") in held_set):
                dropped += 1
                continue
            rows.append(r)
            kept += 1
        (out_dir / f.name).write_text(
            "".join(json.dumps(r) + "\n" for r in rows))
print(f"filtered shard tree: dropped {dropped} held-out P_ASSERTS rows, "
      f"kept {kept}")
(EXP / "build_manifest.json").write_text(json.dumps(
    {"heldout": len(held), "dropped_rows": dropped, "kept_rows": kept,
     "source_dirs": DIRS, "seed": 14}, indent=1))
