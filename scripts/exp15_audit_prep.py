"""Draw the frozen 50-claim resource audit and build its grading file.

NEW instrument (docs/15): these claims come from body text, so each one
is graded against the paper's own `body_window` — the text the extractor
actually saw — not the abstract. The D92 abstract instrument is left
untouched so the older audits stay comparable.

The grading file shows, per claim, the window regions mentioning the
resource, so a grader can check "is this resource really named here, and
is the relation right?" without re-reading 8k of body per item.

Usage: .venv/bin/python scripts/exp15_audit_prep.py
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SH = ROOT / "data" / "arxiv_ai" / "shards_res"
SCRATCH = Path("/tmp/claude-1000/-home-zonk1024-projects-foundation/"
               "d8283ce1-0c3c-47aa-89e5-27777f401372/scratchpad")

windows = {}
for f in sorted(SH.glob("in_*.json")):
    for p in json.loads(f.read_text()):
        windows["arxiv:" + p["arxiv_id"]] = p

rows = []
for f in sorted(SH.glob("out_*.jsonl")):
    for ln, line in enumerate(f.read_text().splitlines()):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("pid") and d.get("object") and d.get("subject"):
            d["sid"] = f"{f.name}:{ln}"
            rows.append(d)
print(f"{len(rows)} live resource claims")

rng = random.Random(17)
sample = rng.sample(rows, min(50, len(rows)))
keep = ("kind", "object", "page", "pid", "statement", "subject", "sid")
out = [{k: r.get(k) for k in keep} for r in sample]
(SH.parent / "res_audit_sample_50.json").write_text(json.dumps(out, indent=1))

blocks = []
for i, r in enumerate(out):
    p = windows.get(r["page"], {})
    win = p.get("body_window", "") or ""
    obj = r["object"]
    # show every region of the window that names the resource
    hits = []
    lo = win.lower()
    for m in re.finditer(re.escape(obj.lower()[:24]), lo):
        s = max(0, m.start() - 200)
        hits.append("..." + re.sub(r"\s+", " ", win[s:m.start() + 220]) + "...")
        if len(hits) >= 3:
            break
    if not hits:
        hits = ["*** RESOURCE NAME NOT FOUND VERBATIM IN WINDOW ***",
                "abstract: " + (p.get("abstract", "")[:600] or "?")]
    blocks.append(
        f"=== ITEM {i} [{r['page']}]\nCLAIM: {r['statement']}\n"
        f"  subject={r['subject']!r}  pid={r['pid']}  object={obj!r}\n"
        f"TITLE: {p.get('title','?')}\nWINDOW EVIDENCE:\n  "
        + "\n  ".join(hits))
(SCRATCH / "res_audit.txt").write_text("\n\n".join(blocks))
print(f"grading file: {SCRATCH / 'res_audit.txt'}")
