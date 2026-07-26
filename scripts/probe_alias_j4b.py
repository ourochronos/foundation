"""D49 acceptance test 2 — aliases via registry forms (docs/08 §5).

200 v4 single queries rephrased onto DERIVED alias surface forms
("North Halmelton" -> "N. Halmelton"; "Kelmorrinia" -> "Kelmorr") that the
surface-token id channel could NOT match, registered as additional forms on
the eid. Target: >= 0.90 x canonical-form P@1.

Usage: .venv/bin/python scripts/probe_alias_j4b.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from codec.individuation import EntityRegistry, functional_relations, is_value  # noqa: E402
from codec.manifest import run_manifest, wilson_ci                # noqa: E402
from codec.memory_store import MemoryStore, id_tokens             # noqa: E402
from codec.walker import ChannelWalker                            # noqa: E402
import v06_pipeline as P                                          # noqa: E402

w = json.loads((ROOT / "data" / "closed_world_v4.json").read_text())
Zf, Zq, _ = P.load_or_build_emb(w, ROOT / "results" / "closed_world_v4_emb.npz")
FUNC = functional_relations(w["facts"])
reg = EntityRegistry()
store = MemoryStore()
for fi, f in enumerate(w["facts"]):
    rel, subj, obj = f["relation"], f["subject"], f["object"]
    if is_value(obj):
        se = reg.resolve_write(subj, rel, "s", "v:" + obj.replace(",", ""),
                               functional=rel in FUNC, batch="w41")
        ids = {se} | id_tokens([obj])
    else:
        se = reg.resolve_write(subj, rel, "s", None, batch="w41")
        oe = reg.resolve_write(obj, rel, "o", se, batch="w41")
        reg._get(se).neighbors.add(oe)
        ids = {se, oe}
    idx = store.add(Zf[fi], [], f["text"])
    store.ids[idx] = ids

art = P.build_artifacts(w, Zf, Zq)
walker = ChannelWalker(store,
                       protos={r: art["rel_entry"][r]["proto"] for r in art["RELS"]},
                       ops={r: art["rel_entry"][r]["t"] for r in art["RELS"]})


def alias_of(name: str) -> str:
    parts = name.split()
    if len(parts) > 1:
        return parts[0][0] + ". " + " ".join(parts[1:])
    return name[: max(5, len(name) - 4)]


rng = random.Random(3)
singles = [q for q in w["queries"] if q["kind"] == "single"]
rows = rng.sample(singles, 200)
can_hit = ali_hit = registered = 0
for q in rows:
    f = w["facts"][q["fact_idx"]]
    subj, rel = f["subject"], f["relation"]
    eids = reg.resolve_query(subj, rel)
    if len(eids) != 1:
        continue
    eid = eids[0]
    al = alias_of(subj)
    e = reg._get(eid)
    e.forms.add(al)
    reg.by_form.setdefault(al, set()).add(eid)
    registered += 1
    # canonical + alias query both resolve -> walk
    for text_subj, bucket in ((subj, "can"), (al, "ali")):
        cand = reg.resolve_query(text_subj, rel)
        ok = False
        if len(cand) == 1:
            got = walker.walk({cand[0]}, [rel])
            ok = got == q["fact_idx"]
        if bucket == "can":
            can_hit += ok
        else:
            ali_hit += ok
print(f"[alias] canonical P@1={can_hit/registered:.3f} "
      f"alias P@1={ali_hit/registered:.3f} "
      f"ratio={ali_hit/max(can_hit,1):.3f} (n={registered}) [target >=0.90]",
      flush=True)
out = ROOT / "results" / "alias_j4b.json"
out.write_text(json.dumps(
    {"canonical_p1": can_hit / registered, "alias_p1": ali_hit / registered,
     "ratio": ali_hit / max(can_hit, 1), "n": registered,
     "alias_ci95": wilson_ci(ali_hit, registered),
     "manifest": run_manifest(seed=3)}, indent=2))
print(f"[done] {out.relative_to(ROOT)}")
