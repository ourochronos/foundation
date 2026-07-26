"""v4b probe — Track F (answer-time ALU) + Track I (views on ONE graph).

Track I mechanics under test: a view is ID-CHANNEL CONTENT. Atlas entries
carry "src:meridian" in their id sets; a qualified query adds that token to
its query ids and ordinary overlap rescoring selects the view. Unqualified
queries on conflicted subjects must FLAG (top-2 = same (subject, relation),
different sources), not silently pick.

Track F mechanics: two single-hop walks + symbolic arithmetic on the
retrieved number tokens. Op selection is a 3-cue rule (diff/cmp) — logged
as v1-learnable, everything else is the standard stack (v0.7 det head).

Usage: .venv/bin/python scripts/probe_v4b.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from codec.manifest import run_manifest, wilson_ci                # noqa: E402
from codec.memory_store import MemoryStore, id_tokens             # noqa: E402
from codec.walker import ChannelWalker                            # noqa: E402
import v06_pipeline as P                                          # noqa: E402

w = json.loads((ROOT / "data" / "closed_world_v4.json").read_text())
b = json.loads((ROOT / "data" / "closed_world_v4b.json").read_text())
facts = w["facts"]
Zf, Zq, _ = P.load_or_build_emb(w, ROOT / "results" / "closed_world_v4_emb.npz")
art = P.build_artifacts(w, Zf, Zq)
RELS = art["RELS"]

cache = ROOT / "results" / "v4b_emb.npz"
texts = ([c["text"] for c in b["compute"]]
         + [f["text"] for f in b["conflict_facts"]]
         + [q["text"] for q in b["conflict_queries"]])
if cache.exists():
    z = np.load(cache)
    Zc, Zcf, Zcq = z["Zc"], z["Zcf"], z["Zcq"]
else:
    Zall = P.embed_texts(texts)
    n1, n2 = len(b["compute"]), len(b["conflict_facts"])
    Zc, Zcf, Zcq = Zall[:n1], Zall[n1:n1 + n2], Zall[n1 + n2:]
    np.savez(cache, Zc=Zc, Zcf=Zcf, Zcq=Zcq)

store = MemoryStore()
for f, zf in zip(facts, Zf):
    store.add(zf, f["entities"] + f["numbers"], f["text"])
conf_idx = {}
for cf, zf in zip(b["conflict_facts"], Zcf):
    i = store.add(zf, cf["entities"] + ["src:meridian"], cf["text"])
    conf_idx[cf["subject"]] = i
walker = ChannelWalker(store,
                       protos={r: art["rel_entry"][r]["proto"] for r in RELS},
                       ops={r: art["rel_entry"][r]["t"] for r in RELS})

det = nn.Sequential(nn.Linear(1024, 256), nn.GELU(), nn.Linear(256, len(RELS)))
det.load_state_dict(torch.load(ROOT / "checkpoints" / "reasoner_v07_det.pt",
                               weights_only=True))

res = {}

# ---- Track I: views ------------------------------------------------------
q_hit = u_flag = u_n = c_flag = c_n = q_n = 0
subj_rel = {}
for i, f in enumerate(facts):
    if f["relation"] == "capital_of":
        subj_rel[f["subject"]] = i
for q, zq in zip(b["conflict_queries"], Zcq):
    hand = id_tokens([q["subject"]])
    if q["kind"] == "qualified":
        hand = hand | {"src:meridian"}
        r = store.query(walker.pt["capital_of"], hand, k=1, id_weight=1.0)
        got = r[0][0]
        q_n += 1
        q_hit += b["conflict_facts"][[cf["subject"] for cf in
                                      b["conflict_facts"]].index(
            q["subject"])]["object"] in store.texts[got]
    else:
        r = store.query(walker.pt["capital_of"], hand, k=2, id_weight=1.0)
        top2 = [x[0] for x in r[:2]]
        same_sr = (len(top2) == 2
                   and all(q["subject"] in store.texts[t] for t in top2)
                   and (("src:meridian" in store.ids[top2[0]])
                        != ("src:meridian" in store.ids[top2[1]])))
        if q["kind"] == "unqualified_conflicted":
            u_n += 1; u_flag += same_sr
        else:
            c_n += 1; c_flag += same_sr
res["views"] = {"qualified_p1": q_hit / q_n,
                "conflict_flag": u_flag / u_n,
                "spurious_flag": c_flag / c_n,
                "n": [q_n, u_n, c_n]}
print(f"[I views] qualified P@1={q_hit/q_n:.3f} (n={q_n}) | conflict-flag="
      f"{u_flag/u_n:.3f} (n={u_n}) | spurious={c_flag/c_n:.3f} (n={c_n})",
      flush=True)

# ---- Track F: answer-time ALU --------------------------------------------
names = sorted({f["subject"] for f in facts}, key=len, reverse=True)
ok = n = det_ok = 0
for c, zq in zip(b["compute"], Zc):
    with torch.no_grad():
        pv = torch.sigmoid(det(torch.tensor(zq)[None]))[0].numpy()
    rel = RELS[int(np.argmax(pv))]
    det_ok += rel == c["rel"]
    # two-subject parse: the two known names present in the text
    found = []
    t = c["text"]
    for nm in names:
        if nm in t:
            found.append(nm)
            t = t.replace(nm, " ")
        if len(found) == 2:
            break
    n += 1
    if len(found) != 2:
        continue
    vals = {}
    for nm in found:
        got = walker.walk(id_tokens([nm]), [c["rel"]])
        if got is None:
            break
        m = re.findall(r"[\d,]+", store.texts[got])
        if not m:
            break
        vals[nm] = int(m[-1].replace(",", ""))
    if len(vals) != 2:
        continue
    # op cue (v1-learnable, logged): diff vs cmp
    if c["kind"] == "diff":
        ok += abs(vals[found[0]] - vals[found[1]]) == c["gold"]
    else:
        bigger = max(vals, key=vals.get)
        ok += bigger == c["gold"]
res["compute"] = {"acc": ok / n, "det_rel_acc": det_ok / n, "n": n}
print(f"[F compute] acc={ok/n:.3f} det-rel={det_ok/n:.3f} (n={n})",
      flush=True)

for row in res.values():
    if "n" in row and isinstance(row["n"], int):
        for m in ("acc",):
            if m in row:
                row[m + "_ci95"] = wilson_ci(round(row[m] * row["n"]),
                                             row["n"])
(ROOT / "results" / "v4b_probe.json").write_text(json.dumps(
    {"results": res, "manifest": run_manifest(seed=4141)}, indent=2))
print("[done] results/v4b_probe.json", flush=True)
