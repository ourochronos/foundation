"""D95/docs-15: score the resource axis against its frozen criteria.

Mechanical instruments only. The frozen 50-claim precision audit is a
separate human-graded artifact (data/arxiv_ai/res_audit_labels_50.json),
per docs/15 — and it is a NEW instrument, not an amendment of the
abstract-graded D92 one, because these claims come from body text.

Fragmentation is the criterion this axis lives or dies on: resources
have no page, so they can only become one entity by being NAMED the same
way by every paper. `_variants` groups surface forms by an aggressive
normalisation (case, punctuation, size/version suffixes, the words
benchmark/dataset/model) and reports how much of each resource's mass
sits on its dominant form.

Usage: .venv/bin/python scripts/exp15_score.py
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SH = ROOT / "data" / "arxiv_ai" / "shards_res"

from codec.manifest import run_manifest                          # noqa: E402

RES_PIDS = {"P_EVALUATES_ON", "P_BUILDS_ON", "P_COMPARES_TO"}


def norm(s: str) -> str:
    """Aggressive canonical key — what the names WOULD collapse to if a
    normaliser ran. Divergence from the extractor's own naming is the
    fragmentation being measured."""
    t = s.lower().strip()
    t = re.sub(r"\b(the|benchmark|benchmarks|dataset|datasets|model|models|"
               r"corpus|suite)\b", " ", t)
    t = re.sub(r"[-_\s./]+", "", t)
    t = re.sub(r"\(.*?\)", "", t)
    # trailing size/version suffixes: -7b, -v2, 1.5b, -instruct, -base
    t = re.sub(r"(instruct|chat|base|it)$", "", t)
    t = re.sub(r"\d+\.?\d*[bm]$", "", t)
    return t


rows = []
for f in sorted(SH.glob("out_*.jsonl")):
    for ln, line in enumerate(f.read_text().splitlines()):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("pid") in RES_PIDS and d.get("object") and d.get("subject"):
            d["sid"] = f"{f.name}:{ln}"
            rows.append(d)

pages = {r["page"] for r in rows}
by_obj = collections.defaultdict(set)
for r in rows:
    by_obj[r["object"]].add(r["page"])

shared = {k: v for k, v in by_obj.items() if len(v) >= 3}
groups = collections.defaultdict(lambda: collections.defaultdict(set))
for obj, pgs in by_obj.items():
    groups[norm(obj)][obj] |= pgs

# fragmentation over the 20 groups covering the most papers
ranked = sorted(groups.items(),
                key=lambda kv: -len(set().union(*kv[1].values())))[:20]
frag = []
for key, forms in ranked:
    tot = sum(len(v) for v in forms.values())
    dom = max(len(v) for v in forms.values())
    frag.append({"canonical_key": key, "surface_forms": len(forms),
                 "papers_total_mentions": tot,
                 "dominant_form": max(forms, key=lambda f: len(forms[f])),
                 "dominant_share": round(dom / tot, 3),
                 "forms": sorted(forms, key=lambda f: -len(forms[f]))[:6]})
mean_dom = round(sum(f["dominant_share"] for f in frag) / max(len(frag), 1), 3)

out = {
    "manifest": run_manifest(config={"protocol": "docs/15 (D95)",
                                     "shards": str(SH)}),
    "claims": len(rows), "papers_with_resources": len(pages),
    "distinct_resource_objects": len(by_obj),
    "resources_in_ge2_papers": sum(1 for v in by_obj.values() if len(v) >= 2),
    "resources_in_ge3_papers": len(shared),
    "resources_in_ge5_papers": sum(1 for v in by_obj.values() if len(v) >= 5),
    "resources_in_ge10_papers": sum(1 for v in by_obj.values() if len(v) >= 10),
    "pid_mix": dict(collections.Counter(r["pid"] for r in rows)),
    "top_shared": [{"object": k, "papers": len(v)}
                   for k, v in sorted(by_obj.items(),
                                      key=lambda kv: -len(kv[1]))[:25]],
    "fragmentation_top20": frag,
    "mean_dominant_share_top20": mean_dom,
    "criteria": {
        "population_ge100_resources_in_ge3_papers": {
            "pass": len(shared) >= 100, "value": len(shared)},
        "fragmentation_mean_dominant_share_ge_0.90": {
            "pass": mean_dom >= 0.90, "value": mean_dom},
    },
    "criteria_pending_audit": [
        "resource-claim precision >= 0.80 (frozen 50, graded vs body window)"],
}
(ROOT / "results" / "exp15_resource_axis.json").write_text(
    json.dumps(out, indent=1))
p = {k: v for k, v in out.items() if k not in ("manifest", "fragmentation_top20")}
print(json.dumps(p, indent=1)[:3000])
print("\n--- fragmentation (worst 8 of top 20) ---")
for f in sorted(frag, key=lambda x: x["dominant_share"])[:8]:
    print(f"  {f['dominant_share']:.2f}  {f['dominant_form'][:26]:28s} "
          f"{f['surface_forms']} forms: {f['forms'][:4]}")
