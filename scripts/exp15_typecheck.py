"""Type resources by relational participation, not by name (D41 → D104).

The model-as-target defect (a claim saying a paper "is evaluated on"
GPT-3, Qwen3, Pillar-0) was first caught with a hardcoded vendor regex.
That has a ceiling by construction: a list of GPT/Llama/Qwen cannot know
`Pillar-0`, `EEG Conformer` or `PI-DON`, and it already missed the whole
Qwen family once on a word-boundary bug.

This project's own law says types come from **relational participation**,
not surface form (D41). Applied here: the corpus votes. Objects papers
BUILD ON are substrates; objects papers EVALUATE ON are data. Measured
purity is high — HumanEval/MBPP/MATH 1.00 evaluated-on, GSM8K 0.94,
Qwen2.5 0.83 and GRPO 0.88 built-on.

**Only the DIRECTIONAL contradiction is a defect.** "Relation disagrees
with the profile" is far too noisy: a paper may legitimately build on
GRPO while another compares against it, and both are correct. But you do
not *evaluate on* a substrate — so `P_EVALUATES_ON` against a
BUILDS_ON-dominant profile is the one contradiction with no innocent
reading, and it is exactly the defect family.

COVERAGE IS THE HEAD ONLY, and this is stated rather than hidden: 37 of
719 objects reach 3 papers. The tail cannot be typed by vote, and the
honest answer there is judgement, not a filter that pretends.

Usage: .venv/bin/python scripts/exp15_typecheck.py [--apply]
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
V2 = ROOT / "data" / "arxiv_ai" / "shards_res_v2"
OUT = ROOT / "data" / "arxiv_ai" / "shards_typecheck"
APPLY = "--apply" in sys.argv
MIN_PAPERS = 3
MIN_PURITY = 0.75

rows = [json.loads(x) for f in sorted(V2.glob("out_*.jsonl"))
        for x in f.read_text().splitlines() if x.strip()]

prof: dict[str, collections.Counter] = collections.defaultdict(
    collections.Counter)
papers: dict[str, set] = collections.defaultdict(set)
for r in rows:
    prof[r["object"]][r["pid"]] += 1
    papers[r["object"]].add(r["page"])

typed = {}
for o, c in prof.items():
    if len(papers[o]) < MIN_PAPERS:
        continue
    tot = sum(c.values())
    dom, n = c.most_common(1)[0]
    if n / tot >= MIN_PURITY:
        typed[o] = (dom, round(n / tot, 3), len(papers[o]))

from foundation.typeoracle import evidence, is_model          # noqa: E402

# TWO mechanisms, because they cover disjoint populations (D105). The vote
# types what the corpus uses often; the parts inventory types what the
# REGISTRY knows, however rare — and rare is exactly where the defect
# survived. Neither reaches names in neither, which is stated, not hidden.
suspect = []
for r in rows:
    if r["pid"] != "P_EVALUATES_ON":
        continue
    if typed.get(r["object"], ("", 0, 0))[0] == "P_BUILDS_ON":
        r["_why"] = f"corpus vote: {typed[r['object']]}"
        suspect.append(r)
    elif is_model(r["object"]):
        r["_why"] = f"HF registry knows it as a model: {evidence(r['object'])[:2]}"
        suspect.append(r)

summary = {
    "objects": len(prof),
    "objects_typed_by_vote": len(typed),
    "coverage_note": (f"only objects with >={MIN_PAPERS} papers and "
                      f">={MIN_PURITY} purity can be typed by vote; the "
                      f"tail of {len(prof) - len(typed)} objects needs "
                      f"judgement, not a filter"),
    "substrates": sorted(o for o, t in typed.items()
                         if t[0] == "P_BUILDS_ON"),
    "datasets": sorted(o for o, t in typed.items()
                       if t[0] == "P_EVALUATES_ON"),
    "directional_contradictions": len(suspect),
    "flagged": [{"page": r["page"], "subject": r["subject"],
                 "object": r["object"], "why": r.get("_why", ""),
                 "src_sid": r.get("src_sid")} for r in suspect],
}
(ROOT / "results" / "exp15_typecheck.json").write_text(
    json.dumps(summary, indent=1))

if APPLY and suspect:
    OUT.mkdir(exist_ok=True)
    (OUT / "in_0.json").write_text(json.dumps(
        [{"sid": r.get("src_sid"), "subject": r["subject"],
          "object": r["object"], "page": r["page"],
          "statement": r["statement"],
          # NOT typed[...] — an oracle-flagged object has no corpus profile
          # by definition (that is why the oracle exists), and indexing it
          # would KeyError on exactly the tail this pass was built for.
          "why": r.get("_why", "")}
         for r in suspect], indent=1))

print(json.dumps({k: v for k, v in summary.items() if k != "flagged"},
                 indent=1)[:1500])
for f in summary["flagged"]:
    print(f"  FLAG {f['subject'][:26]:28s} evaluated-on {f['object'][:18]:20s} "
          f"— {f['why']}")
