"""D97 fix, staged: separate the resource MENTION from its RELATION.

The audit found extraction gets the resource right and the relation
wrong — a backbone typed `P_EVALUATES_ON`, a baseline typed
`P_BUILDS_ON`, a related-work mention extracted at all. That is a
narrow decision being made under an 8k-character window alongside
everything else.

So re-type instead of re-extract: every existing claim already names a
real resource, and the body window already contains the sentence that
says HOW it is used. This pulls that sentence out and stages it for a
pass whose only job is the three-way (plus DROP) decision — channel
separation applied to extraction, and it reuses the whole fleet run.

Because the frozen 50-claim audit sample is unchanged, the re-typed
claims can be graded on the SAME items: a paired comparison, not a new
sample against a new baseline.

Usage: .venv/bin/python scripts/exp15_retype_prep.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SH = ROOT / "data" / "arxiv_ai" / "shards_res"
OUT = ROOT / "data" / "arxiv_ai" / "shards_retype"
OUT.mkdir(exist_ok=True)
PER = 60                      # decisions per shard: short items, so many fit

def _squash(s: str) -> str:
    """Fold the things papers vary and names do not depend on."""
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _locate(obj: str, sources, want: int = 3) -> list[str]:
    """Find where a source names this resource.

    A prefix match over one field was the whole bug (D97/D98): it made me
    mis-grade five claims and then made a typing agent DELETE two valid
    ones. So search every field, match on a punctuation-and-case-folded
    form (`Llama 3` finds `LLaMA-3.1-8B`), and fall back to the longest
    distinctive token before giving up.
    """
    out: list[str] = []
    probes = [obj]
    toks = [t for t in re.split(r"[\s/_-]+", obj) if len(t) > 3]
    if toks:
        probes.append(max(toks, key=len))
    for src, tag in sources:
        if not src:
            continue
        sq = _squash(src)
        # map squashed offsets back to raw offsets
        idx = [i for i, ch in enumerate(src) if re.match(r"[a-z0-9]", ch.lower())]
        for probe in probes:
            ps = _squash(probe)
            if not ps:
                continue
            start = 0
            while len(out) < want:
                j = sq.find(ps, start)
                if j < 0:
                    break
                start = j + 1
                if j >= len(idx):
                    break
                raw = idx[j]
                s0 = max(0, raw - 320)
                out.append(f"[{tag}] ..."
                           + re.sub(r"\s+", " ", src[s0:raw + 340]).strip()
                           + "...")
            if out:
                break
        if len(out) >= want:
            break
    return out


win = {}
for f in sorted(SH.glob("in_*.json")):
    for p in json.loads(f.read_text()):
        win["arxiv:" + p["arxiv_id"]] = p

items, no_ctx = [], 0
for f in sorted(SH.glob("out_*.jsonl")):
    for ln, line in enumerate(f.read_text().splitlines()):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if not (d.get("pid") and d.get("object")):
            continue
        p = win.get(d["page"], {})
        body = p.get("body_window", "") or ""
        abst = p.get("abstract", "") or ""
        obj = d["object"]
        ctxs = _locate(obj, ((body, "body"), (abst, "abstract"),
                             (p.get("title", "") or "", "title")))
        if not ctxs:
            no_ctx += 1
        items.append({"sid": f"{f.name}:{ln}", "page": d["page"],
                      "subject": d["subject"], "object": obj,
                      "current_pid": d["pid"],
                      "statement": d["statement"],
                      "contexts": ctxs or ["*** no mention located ***"]})

for i in range(0, len(items), PER):
    (OUT / f"in_{i // PER}.json").write_text(
        json.dumps(items[i:i + PER], indent=1))
n = (len(items) + PER - 1) // PER
print(f"{len(items)} claims staged into {n} typing shards of {PER} "
      f"({no_ctx} with no locatable mention)")
