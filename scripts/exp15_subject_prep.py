"""Stage a subject-canonicalisation pass over the resource claims (D98).

After relation typing, the residual defects are dominated by SUBJECTS:
the stopword `"The"`, title fragments like `"Fast ANNS"` and
`"Pixels for Programs?"`. D94 already solved this — name the paper's
entity once, in the shortest form that stands alone, and attach every
claim to it — but that rule was written for the abstract pass and never
applied to the resource shards.

So canonicalise in place rather than re-extract, for the same reason the
relation fix did: the claims are fine, one field is wrong. One decision
per PAGE (not per claim), which is also what makes it cheap — 374
decisions instead of 1,062.

Usage: .venv/bin/python scripts/exp15_subject_prep.py
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SH = ROOT / "data" / "arxiv_ai" / "shards_res"
OUT = ROOT / "data" / "arxiv_ai" / "shards_subject"
OUT.mkdir(exist_ok=True)
PER = 50

win = {}
for f in sorted(SH.glob("in_*.json")):
    for p in json.loads(f.read_text()):
        win["arxiv:" + p["arxiv_id"]] = p

subjects: dict[str, collections.Counter] = collections.defaultdict(
    collections.Counter)
for f in sorted(SH.glob("out_*.jsonl")):
    for line in f.read_text().splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("pid") and d.get("subject"):
            subjects[d["page"]][d["subject"]] += 1

items = []
for page, ctr in sorted(subjects.items()):
    p = win.get(page, {})
    items.append({"page": page, "title": p.get("title", ""),
                  "abstract": (p.get("abstract", "") or "")[:1100],
                  "current_subjects": [s for s, _ in ctr.most_common()],
                  "n_claims": sum(ctr.values())})

for i in range(0, len(items), PER):
    (OUT / f"in_{i // PER}.json").write_text(
        json.dumps(items[i:i + PER], indent=1))
n = (len(items) + PER - 1) // PER
multi = sum(1 for x in items if len(x["current_subjects"]) > 1)
print(f"{len(items)} pages -> {n} shards of {PER}; "
      f"{multi} pages currently carry more than one subject")
