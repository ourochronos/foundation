"""Merge the typing and subject decisions into a v2 resource shard set.

Reads the original resource claims and applies, per claim, the relation
decided by the typing pass and, per page, the canonical subject decided
by the naming pass. Writes a NEW shard directory — the original stays
untouched, so every intermediate state remains reproducible and the v1
audit stays meaningful.

Statements are REGENERATED from the canonical triple. That is honest
here and would not be elsewhere: resource statements were always
synthesised by the extractor ("X is evaluated on Y"), never quoted from
the paper, so rewriting one is not touching evidence. A claim whose
subject was the stopword "The" otherwise keeps a sentence reading
"The is evaluated on ALFWorld" after its subject is repaired.

DROP removes a claim. UNCERTAIN keeps it, flagged, and out of the
ingested set — abstention, not deletion (D98).

Usage: .venv/bin/python scripts/exp15_apply.py
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "arxiv_ai" / "shards_res"
TYPE = ROOT / "data" / "arxiv_ai" / "shards_retype"
SUBJ = ROOT / "data" / "arxiv_ai" / "shards_subject"
OUT = ROOT / "data" / "arxiv_ai" / "shards_res_v2"
OUT.mkdir(exist_ok=True)

VERB = {"P_EVALUATES_ON": "is evaluated on",
        "P_BUILDS_ON": "builds on",
        "P_COMPARES_TO": "is compared against"}

typing: dict[str, dict] = {}
for f in sorted(TYPE.glob("out_*.jsonl")):
    for line in f.read_text().splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("sid"):
            typing[d["sid"]] = d

subject: dict[str, dict] = {}
for f in sorted(SUBJ.glob("out_*.jsonl")):
    for line in f.read_text().splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("page") and d.get("subject"):
            subject[d["page"]] = d

stats = collections.Counter()
kept, uncertain = [], []
for f in sorted(SRC.glob("out_*.jsonl")):
    for ln, line in enumerate(f.read_text().splitlines()):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if not (r.get("pid") and r.get("object")):
            continue
        sid = f"{f.name}:{ln}"
        stats["input"] += 1
        t = typing.get(sid)
        if t is None:
            stats["no_typing_decision"] += 1
            continue
        pid = t["pid"]
        if pid == "DROP":
            stats["dropped"] += 1
            continue
        s = subject.get(r["page"])
        subj = s["subject"] if s else r["subject"]
        if s and s.get("changed"):
            stats["subject_repaired"] += 1
        if pid != r["pid"]:
            stats["relation_changed"] += 1
        row = {"page": r["page"], "page_title": r.get("page_title", ""),
               "subject": subj, "pid": pid, "kind": "resource",
               "object": r["object"],
               "statement": f"{subj} {VERB.get(pid, 'relates to')} "
                            f"{r['object']}.",
               "src_sid": sid, "typing_why": str(t.get("why", ""))[:160]}
        if pid == "UNCERTAIN":
            stats["uncertain_held"] += 1
            uncertain.append(row)
        else:
            stats[pid] += 1
            kept.append(row)

if stats["no_typing_decision"]:
    print(f"[apply] REFUSING: {stats['no_typing_decision']} claims have no "
          f"typing decision — the fleet is incomplete. Running now would "
          f"silently drop them from v2. Re-run when all shards have landed.")
    raise SystemExit(1)

for old in OUT.glob("out_*.jsonl"):     # never leave a partial run's files
    old.unlink()
for i in range(0, len(kept), 400):
    (OUT / f"out_{i // 400}.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in kept[i:i + 400]))
(OUT / "held_uncertain.jsonl").write_text(
    "".join(json.dumps(r) + "\n" for r in uncertain))

obj = collections.defaultdict(set)
for r in kept:
    obj[r["object"]].add(r["page"])
stats_out = {
    "counts": dict(stats),
    "kept": len(kept), "held_uncertain": len(uncertain),
    "resources_ge2_papers": sum(1 for v in obj.values() if len(v) >= 2),
    "resources_ge3_papers": sum(1 for v in obj.values() if len(v) >= 3),
    "resources_ge5_papers": sum(1 for v in obj.values() if len(v) >= 5),
    "distinct_subjects": len({r["subject"] for r in kept}),
    "pages": len({r["page"] for r in kept}),
}
(ROOT / "results" / "exp15_apply.json").write_text(
    json.dumps(stats_out, indent=1))
print(json.dumps(stats_out, indent=1))
