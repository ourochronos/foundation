"""D64/F5 — the registered 3-phrasing sensitivity bound: pooled post-edit
eval on all three MQuAKE question phrasings.

Usage: .venv/bin/python scripts/k6_phrasing_sens.py
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
out = {}
for ph in (0, 1, 2):
    hit = n = 0
    for i, h in enumerate(hops):
        if h["train"] or h["phrasing"] != ph:
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
    out[ph] = {"p1": hit / n, "n": n, "ci95": wilson_ci(hit, n)}
    print(f"[phrasing {ph}] post-edit P@1={hit/n:.3f} (n={n})", flush=True)
vals = [out[p]["p1"] for p in out]
print(f"[spread] {min(vals):.3f}-{max(vals):.3f}", flush=True)
(ROOT / "results" / "k6_phrasing_sens.json").write_text(json.dumps(
    {"per_phrasing": {str(k): v for k, v in out.items()},
     "manifest": run_manifest(seed=0)}, indent=2))
print("[done] results/k6_phrasing_sens.json", flush=True)
