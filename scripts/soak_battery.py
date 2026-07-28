"""M7 soak battery — frozen KB invariance checks (J4 protocol spirit).

Fixed cases with expected answers recorded at Phase-B-core close (D82);
the soak asserts they stay correct as the corpus/store grows. Includes an
EDIT-PERSISTENCE case: the user:correction supersession must survive
every restart (durability of the supersede semantics, not just rows).

Prints one JSON line (appended to results/soak_log.jsonl by the wrapper).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from foundation.kb import KB  # noqa: E402

kb = KB(backend="pg", table="poc")

CASES = [
    ("wiener_edu", lambda: {"University of Göttingen", "Harvard"} <=
        {a["object"] for a in kb.ask("Norbert Wiener", "P69")["answers"]}),
    ("chain_1734", lambda: any(
        a["object"] == "1734"
        for a in kb.chain("Norbert Wiener", ["P69", "P571"])["answers"])),
    ("turing_born", lambda: any(
        "1912" in a["object"]
        for a in kb.ask("Alan Turing", "P569")["answers"])),
    ("kolmogorov_born_no_format_conflict", lambda:
        kb.ask("Andrey Kolmogorov", "P569")["status"] == "answered"),
    ("unknown_abstains", lambda:
        kb.ask("Nobody Anywhere", "P569")["status"] == "abstain"),
    ("edit_persisted", lambda: any(
        a["object"] == "Columbia, Missouri"
        and "user:correction" in a["sources"]
        for a in kb.ask("Norbert Wiener", "P19")["answers"])),
    ("brief_grounded", lambda: (lambda b: not b["abstain"] and all(
        s["citations"] for s in b["sentences"]))(
        kb.brief("Andrey Kolmogorov"))),
    ("arxiv_views_live", lambda:
        kb.views("independence relations")["status"] == "answered"),
    # D92 sources. The AI slice's own subjects are per-paper method names
    # (1,041 distinct over 1,106 claims), so the cross-paper invariant has
    # to ride the citation axis — cited_by is the only surface in this
    # corpus that joins papers at all.
    ("ai_views_live", lambda:
        kb.views("gte-Qwen2-1.5B-instruct")["status"] == "answered"),
    ("ai_cited_by_live", lambda:
        kb.cited_by("Qwen3 Technical Report")["n"] >= 20),
    ("cited_work_is_one_entity", lambda:
        len(kb.resolve_subject("Proximal Policy Optimization Algorithms")) == 1),
    # D101: a shared resource is ONE entity corpus-wide. Before
    # `object_global` these read 16-18 eids each and every cross-paper
    # count was 0, with nothing failing anywhere to say so.
    ("resource_is_one_entity", lambda: all(
        len(kb.resolve_subject(r)) == 1
        for r in ("GSM8K", "Qwen2.5", "GRPO", "LoRA", "HumanEval"))),
    ("resource_used_by_many_papers", lambda:
        kb.cited_by("GSM8K", pid=None)["n"] >= 10),
]

results, fails = {}, []
for name, fn in CASES:
    try:
        ok = bool(fn())
    except Exception as e:                              # noqa: BLE001
        ok = False
        fails.append(f"{name}: {e}")
    results[name] = ok
    if not ok and name not in [f.split(":")[0] for f in fails]:
        fails.append(name)

pages = len(list((ROOT / "data" / "wiki" / "pages").glob("*.json")))
print(json.dumps({
    "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "battery": results,
    "n_pass": sum(results.values()), "n_total": len(results),
    "failures": fails,
    "store": kb.status(), "pages_on_disk": pages}))
