"""Apply pooled-checker vetoes to extraction shards (D83 write-back).

Reads every veto_*.jsonl in the shard dir and nulls the pid of matching
rows in out_*.jsonl IN PLACE, adding "vetoed": true — the row stays as a
record and KB.ingest_shards skips it. Match key = verbatim
(page, subject, object). Rule-6 (duplicate) vetoes keep the FIRST live
copy and null the rest; every other rule nulls all matches.

Usage: .venv/bin/python scripts/apply_vetoes.py data/arxiv_ai/shards
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

shard_dir = Path(sys.argv[1])
vetoes: dict[tuple[str, str, str], dict] = {}
for vf in sorted(shard_dir.glob("veto_*.jsonl")):
    for line in vf.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        vetoes[(d["page"], d["subject"], d["object"])] = d

matched: set[tuple[str, str, str]] = set()
n_nulled = n_live = 0
for f in sorted(shard_dir.glob("out_*.jsonl")):
    rows = [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
    kept_one: set[tuple[str, str, str]] = set()
    changed = False
    for r in rows:
        if not r.get("pid"):
            continue
        key = (r.get("page", ""), r.get("subject", ""), r.get("object", ""))
        v = vetoes.get(key)
        if v is None:
            n_live += 1
            continue
        matched.add(key)
        if v["rule"] == 6 and key not in kept_one:
            kept_one.add(key)          # duplicate veto: first copy lives
            n_live += 1
            continue
        r["pid"] = None
        r["vetoed"] = True
        r["veto_rule"] = v["rule"]
        changed = True
        n_nulled += 1
    if changed:
        f.write_text("".join(json.dumps(r) + "\n" for r in rows))

unmatched = [k for k in vetoes if k not in matched]
print(f"[veto] {len(vetoes)} veto rows -> {n_nulled} rows nulled, "
      f"{n_live} live")
for k in unmatched:
    print(f"[veto] UNMATCHED (check keys): {k}")
