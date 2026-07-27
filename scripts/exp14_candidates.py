"""D93/docs-14 step 2: per-paper candidate lists + planted decoys (Arm B).

Candidates are computed FROM THE SOURCE (title+abstract) against the
contamination-free `linkexp` store, then written into the shard input.
Two consequences that matter:

  * the fleet stays parallel and stateless — no agent touches a live
    store, so shards remain frozen and re-runnable;
  * extraction stays reproducible from the shard input alone, because
    the exact candidate list the agent saw is journalled beside the
    paper it saw it with.

Every candidate carries its SOURCE PAGE. The retrieval probe (docs/14)
showed dense similarity cannot separate a paper's technical method from
a Wikipedia general concept with similar words, so provenance is shown
rather than filtered — the false-merge rate is something to MEASURE, not
something to assume away.

Planted decoys (2/shard, D8 house rule): a real store entity that is
confusable-but-distinct, injected into a paper where it does not belong.
An instrument that cannot catch a planted merge cannot certify the
natural rate.

Usage: .venv/bin/python scripts/exp14_candidates.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
EXP = ROOT / "data" / "exp14"
TOPK = 12

from foundation.kb import KB                                # noqa: E402
from codec.encode import M3Encoder                          # noqa: E402

kb = KB(backend="pg", table="linkexp")
print(f"linkexp: {kb.status()}", flush=True)

# canonical (shortest) form per eid + the page it was first asserted on
forms: dict[str, str] = {}
for f, eids in kb.reg.by_form.items():
    for e in eids:
        cur = forms.get(e)
        if cur is None or len(f) < len(cur):
            forms[e] = f
page_of: dict[str, str] = {}
for c in kb.claims:
    page_of.setdefault(c["subj_eid"], c["page"])
    if c.get("obj_eid"):
        page_of.setdefault(c["obj_eid"], c["page"])

eids = sorted(forms)
texts = [forms[e] for e in eids]
print(f"indexing {len(eids)} entity forms", flush=True)

enc = M3Encoder()
Z, _ = enc.encode(texts, sparse=False, max_length=64)
Z = np.asarray(Z, np.float32)
Z /= np.linalg.norm(Z, axis=1, keepdims=True) + 1e-9


def source_kind(page: str) -> str:
    if page.startswith("arxiv:"):
        return "arXiv paper"
    if page.startswith("hf:"):
        return "HuggingFace model card"
    return "Wikipedia article"


rng = random.Random(14)
decoy_log = []
for k in range(5):
    src = json.loads((EXP / "shards_a" / f"in_{k}.json").read_text())
    Q, _ = enc.encode([f"{p['title']}. {p['abstract']}" for p in src],
                      sparse=False, max_length=512)
    Q = np.asarray(Q, np.float32)
    Q /= np.linalg.norm(Q, axis=1, keepdims=True) + 1e-9
    sims = Q @ Z.T                                      # [papers, entities]
    # which papers in this shard get a planted decoy
    plant_at = set(rng.sample(range(len(src)), 2))
    out = []
    for i, p in enumerate(src):
        order = np.argsort(-sims[i])[:TOPK]
        cands = [{"eid": eids[j], "name": texts[j],
                  "source": page_of.get(eids[j], "?"),
                  "source_kind": source_kind(page_of.get(eids[j], "?")),
                  "similarity": round(float(sims[i][j]), 3)}
                 for j in order]
        if i in plant_at:
            # a decoy from a DIFFERENT paper, lexically close but not this
            # paper's entity: drawn from the tail of the neighbour list of
            # another shard member so it is plausible, never correct
            other = (i + 7) % len(src)
            tail = np.argsort(-sims[other])[TOPK:TOPK + 40]
            pick = [j for j in tail
                    if page_of.get(eids[j], "?") != "arxiv:" + p["arxiv_id"]]
            if pick:
                j = int(rng.choice(pick))
                d = {"eid": eids[j], "name": texts[j],
                     "source": page_of.get(eids[j], "?"),
                     "source_kind": source_kind(page_of.get(eids[j], "?")),
                     "similarity": round(float(sims[i][j]), 3),
                     "_planted": True}
                cands.insert(rng.randrange(len(cands) + 1), d)
                decoy_log.append({"shard": k, "page": "arxiv:" + p["arxiv_id"],
                                  "eid": d["eid"], "name": d["name"],
                                  "source": d["source"]})
        out.append({**p, "store_candidates":
                    [{kk: vv for kk, vv in c.items() if kk != "_planted"}
                     for c in cands]})
    (EXP / "shards_b").mkdir(exist_ok=True)
    (EXP / "shards_b" / f"in_{k}.json").write_text(json.dumps(out, indent=1))
    print(f"shard {k}: {len(out)} papers, {TOPK} candidates each, "
          f"2 decoys planted", flush=True)

(EXP / "planted_decoys.json").write_text(json.dumps(decoy_log, indent=1))
print(f"[done] {len(decoy_log)} planted decoys logged")
