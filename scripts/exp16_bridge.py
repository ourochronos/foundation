"""Weld the citation axis to the resource axis (D107).

Measured: 3,840 citation claims, 941 resource claims, and **zero** 2-hop
paths between them. 191 papers carry both and every one uses a different
subject for each — the citation axis keys on the paper TITLE
("RadioTrace: Transmitter-Aware Diffusion for Radio Map Estimation…"),
the resource axis on the METHOD name ("RadioTrace"), because each rule
was right for its own job and nobody said they name the same paper.

So the graph is two disconnected components per paper, and every
cross-axis question — "what does the paper X cites evaluate on?" —
returns nothing. Not a retrieval failure: there is no edge to retrieve.

The bridge is one derivable claim per paper: TITLE --P_INTRODUCES-->
METHOD. Forward-directed because `chain` walks forward, which makes
`chain(X, [P_CITES, P_INTRODUCES, P_EVALUATES_ON])` a real query. No
fleet and no judgement — both endpoints already exist and are already
canonical (`page_title` from D92, the D94 method name from the resource
pass); this only states the identity nobody had declared.

Usage: .venv/bin/python scripts/exp16_bridge.py
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "data" / "arxiv_ai" / "shards_res_v2"
OUT = ROOT / "data" / "arxiv_ai" / "shards_bridge"
OUT.mkdir(exist_ok=True)

rows = [json.loads(x) for f in sorted(RES.glob("out_*.jsonl"))
        for x in f.read_text().splitlines() if x.strip()]

# one bridge per (paper, method); a paper with two contributions gets two
pairs: dict[tuple, str] = {}
for r in rows:
    title = (r.get("page_title") or "").strip()
    method = (r.get("subject") or "").strip()
    if not title or not method or title == method:
        continue
    pairs[(r["page"], title, method)] = r["page"]

bridge = []
for (page, title, method) in sorted(pairs):
    bridge.append({
        "page": page, "page_title": title,
        "subject": title,                 # the citation axis's key
        "pid": "P_INTRODUCES",
        "object": method,                 # the resource axis's key
        "kind": "bridge",
        "statement": f"{title} introduces {method}.",
        # the title is canonical for its own page (D92); the method is a
        # corpus-wide name (D101) so both endpoints resolve to one entity
        "object_global": True,
    })

(OUT / "out_0.jsonl").write_text(
    "".join(json.dumps(r) + "\n" for r in bridge))
by_page = collections.Counter(r["page"] for r in bridge)
print(json.dumps({
    "bridge_claims": len(bridge),
    "papers_bridged": len(by_page),
    "papers_with_multiple_methods": sum(1 for v in by_page.values() if v > 1),
    "sample": [b["statement"][:90] for b in bridge[:5]],
}, indent=1))
