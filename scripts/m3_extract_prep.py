"""M3 — shard fetched pages for statement-first extraction agents.

Per D69 (Covalence L1) + D72 (instance context): agents extract
SELF-CONTAINED statements and assign schema pids AT EXTRACTION TIME with
the full sentence in view. Lead + early sections only (pilot scope);
infobox/wikitext stays out of the agent's view — it is the GROUND TRUTH.

Usage: .venv/bin/python scripts/m3_extract_prep.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "data" / "wiki" / "pages"
SHARDS = ROOT / "data" / "wiki" / "shards"
SHARDS.mkdir(parents=True, exist_ok=True)

rows = []
for p in sorted(PAGES.glob("*.json")):
    d = json.loads(p.read_text())
    text = d["text"][:4000]                     # lead + early sections
    rows.append({"title": d["title"], "text": text})
S = 8
per = (len(rows) + S - 1) // S
for i in range(S):
    (SHARDS / f"in_{i}.json").write_text(json.dumps(rows[i*per:(i+1)*per]))
print(f"[prep] {len(rows)} pages -> {S} shards of ~{per}")
