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
