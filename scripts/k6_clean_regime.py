"""D64/F9 — manifested regeneration of the clean-regime number and the
sibling-edit contamination count (previously stdout-only / manifest-less).

Usage: .venv/bin/python scripts/k6_clean_regime.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
_src = (ROOT / "scripts" / "k6_stage3_edits.py").read_text()
_head = _src.split("# ---- metric 3a")[0].replace(
    'ROOT = Path(__file__).resolve().parent.parent', f'ROOT = Path("{ROOT}")')
exec(_head)  # noqa: S102
from codec.manifest import run_manifest, wilson_ci  # noqa: E402
from codec.memory_store import id_tokens  # noqa: E402
clean_ids = set()
contam = 0
for c in test_cases:
    ek = {tuple(t) for t in c["orig"]["edit_triples"]}
    bad = False
    for (sl, rl, ol), t in zip(c["orig"]["new_triples_labeled"],
                               c["orig"]["new_triples"]):
        if tuple(t) in ek:
            continue
        fi = fact_key.get((sl, t[1], ol))
        if fi is not None and store.shadowed[fi]:
            bad = True
    contam += bad
    if not bad:
        clean_ids.add(c["case_id"])
res = {}
for nh in ("2hop", "3hop", "4hop"):
    hit = n = 0
    for i, h in enumerate(hops):
        if h["train"] or h["phrasing"] != 0 or h["kind"] != nh \
                or h["case_id"] not in clean_ids:
            continue
        c = case_by_id[h["case_id"]]
        golds = {c["new_answer"]} | set(c.get("new_answer_alias", []))
        p = plan(Zh[i], h["subject"])
        got = None
        if p is not None and not walker.abstain_hop1(
                id_tokens([h["subject"]]), p[0]):
            got = walker.walk(id_tokens([h["subject"]]), p)
        n += 1
        hit += got is not None and fact_obj.get(got) in golds
    res[nh] = {"p1": hit / n, "n": n, "ci95": wilson_ci(hit, n)}
    print(f"[clean {nh}] P@1={hit/n:.3f} (n={n})", flush=True)
tot_h = sum(round(res[k]["p1"] * res[k]["n"]) for k in res)
tot_n = sum(res[k]["n"] for k in res)
print(f"[clean all] P@1={tot_h/tot_n:.3f} | contamination "
      f"{contam}/{len(test_cases)} = {contam/len(test_cases):.3f}",
      flush=True)
(ROOT / "results" / "k6_clean_regime.json").write_text(json.dumps(
    {"clean_regime": res, "overall": tot_h / tot_n,
     "overall_ci95": wilson_ci(tot_h, tot_n),
     "contamination": {"n_contaminated": contam,
                       "n_test": len(test_cases),
                       "rate": contam / len(test_cases)},
     "manifest": run_manifest(seed=0)}, indent=2))
print("[done] results/k6_clean_regime.json", flush=True)
