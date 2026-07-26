"""K6 prep (D50, docs/09) — MQuAKE-CF-3k loader + verbalization + store
builders. PREP ONLY: no evaluation, no heads, no test-answer contact beyond
schema/verbalization (dataset-provided cloze templates — zero authorial
freedom, stronger than the protocol's committed-templates promise).

Emits data/mquake/prep_summary.json with file hashes so the run-time
manifest can prove the data didn't move between prep and runs.

Usage: .venv/bin/python scripts/k6_mquake_prep.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec.manifest import file_hash, run_manifest                # noqa: E402


def load_cases(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def verbalize_hop(hop: dict, new: bool = False) -> str:
    """Declarative fact text from the dataset's own cloze + answer."""
    return f"{hop['cloze'].strip()} {hop['answer'].strip()}."


def case_facts(case: dict) -> dict:
    """Store-ready view of one case: original facts, post-edit facts
    (supersession pairs), multi-hop questions, gold answers."""
    orig = [verbalize_hop(h) for h in case["single_hops"]]
    new = [verbalize_hop(h) for h in case["new_single_hops"]]
    edits = []
    for rw in case["requested_rewrite"]:
        old_txt = f"{rw['prompt'].format(rw['subject'])} {rw['target_true']['str']}."
        new_txt = f"{rw['prompt'].format(rw['subject'])} {rw['target_new']['str']}."
        edits.append({"old": old_txt, "new": new_txt,
                      "subject": rw["subject"],
                      "relation": rw["relation_id"]})
    return {"case_id": case["case_id"],
            "facts": orig, "post_edit_facts": new, "edits": edits,
            "questions": case["questions"],
            "answer": case["answer"],
            "answer_alias": case.get("answer_alias", []),
            "new_answer": case["new_answer"],
            "new_answer_alias": case.get("new_answer_alias", []),
            "n_hops": len(case["single_hops"])}


def main() -> None:
    dd = ROOT / "data" / "mquake"
    cf = load_cases(dd / "MQuAKE-CF-3k.json")
    prepped = [case_facts(c) for c in cf]
    rels = sorted({rw["relation_id"] for c in cf
                   for rw in c["requested_rewrite"]})
    hops = {}
    for p in prepped:
        hops[p["n_hops"]] = hops.get(p["n_hops"], 0) + 1
    # alias pressure: how many answers come with aliases (individuation load)
    aliased = sum(1 for p in prepped
                  if p["answer_alias"] or p["new_answer_alias"])
    summary = {
        "n_cases": len(prepped), "relations": rels,
        "hop_distribution": hops, "cases_with_aliases": aliased,
        "verbalization": "dataset cloze + answer (zero authorial templates)",
        "file_hashes": {f.name: file_hash(f)
                        for f in sorted(dd.glob("MQuAKE-*.json"))},
        "manifest": run_manifest(),
    }
    (dd / "prep_summary.json").write_text(json.dumps(summary, indent=2))
    (dd / "cases_prepped.json").write_text(json.dumps(prepped))
    print(f"[k6-prep] {len(prepped)} cases | hops {hops} | "
          f"{len(rels)} relations | {aliased} alias-bearing", flush=True)
    print(f"[k6-prep] sample fact: {prepped[0]['facts'][0]!r}", flush=True)
    print(f"[k6-prep] sample edit: {prepped[0]['edits'][0]['old']!r} -> "
          f"{prepped[0]['edits'][0]['new']!r}", flush=True)
    print("[done] data/mquake/prep_summary.json", flush=True)


if __name__ == "__main__":
    main()
