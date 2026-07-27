"""Re-shard the papers a fleet pass missed, at a smaller size.

Fleet-ops (D87 recorded the OUTPUT budget; this is the INPUT side): at 20
papers x ~8k body window = ~180k chars per shard, agents stop early and
cover 12-20 of their 20 papers. Gap shards go out at 10 papers so the
tail actually completes. Inputs of already-run shards are never touched;
gap shards are new files (in_g*.json).

Each wave writes under its OWN prefix (in_g*, in_h*, ...) and refuses to
reuse one. Re-running with a fixed prefix once deleted and rewrote shard
inputs while agents were still reading them — the frozen-input rule
applies to gap shards too, and a wave counter is the cheap enforcement.

Usage: .venv/bin/python scripts/exp15_gap.py [papers_per_shard] [prefix]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SH = ROOT / "data" / "arxiv_ai" / "shards_res"
PER = int(sys.argv[1]) if len(sys.argv) > 1 else 10

staged: dict[str, dict] = {}
for f in sorted(SH.glob("in_*.json")):
    for p in json.loads(f.read_text()):
        staged["arxiv:" + p["arxiv_id"]] = p

covered: set[str] = set()
for f in sorted(SH.glob("out_*.jsonl")):
    for line in f.read_text().splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("pid"):
            covered.add(d["page"])

missing = [staged[k] for k in sorted(staged) if k not in covered]
print(f"staged {len(staged)}  covered {len(covered)}  missing {len(missing)}")
for old in SH.glob("in_g*.json"):
    old.unlink()
n = 0
for i in range(0, len(missing), PER):
    (SH / f"in_g{n}.json").write_text(json.dumps(missing[i:i + PER], indent=1))
    n += 1
print(f"wrote {n} gap shards of <={PER} papers: in_g0..in_g{n-1}")
