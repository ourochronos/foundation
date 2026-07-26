"""K6 stage 3 — the headline: mass counterfactual edits via supersession,
post-edit multi-hop (docs/09 metric 1), edit-propagation gap (metric 3),
wall-clock (metric 5). ALL test-case edits applied at once to the pooled
store — the regime where parameter-editing methods collapse.

Usage: .venv/bin/python scripts/k6_stage3_edits.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from codec.evals.anchors import fit_anchors                       # noqa: E402
from codec.manifest import run_manifest, wilson_ci                # noqa: E402
from codec.memory_store import MemoryStore, fit_translation, id_tokens  # noqa: E402
from codec.walker import ChannelWalker                            # noqa: E402
import v06_pipeline as P                                          # noqa: E402

KC = 8
torch.manual_seed(0)
w = json.loads((ROOT / "data" / "mquake" / "world_cf3k.json").read_text())
facts, queries, hops = w["facts"], w["queries"], w["hops"]
cases = json.loads((ROOT / "data" / "mquake" / "MQuAKE-CF-3k.json").read_text())
case_by_id = {c["case_id"]: c for c in cases}
z = np.load(ROOT / "results" / "mquake_cf3k_emb_v2.npz")
Zf, Zq, Zh = z["Zf"], z["Zq"], z["Zh"]
RELS = sorted({f["relation"] for f in facts})
R = len(RELS)
ridx = {r: i for i, r in enumerate(RELS)}

# ---- pre-edit artifacts, PC pinned to the pre-edit fit (heads alignment) --
names = sorted({f["subject"] for f in facts} | {f["object"] for f in facts})
name_i = {n: i for i, n in enumerate(names)}
part = np.zeros((len(names), 2 * R), np.float32)
for f in facts:
    part[name_i[f["subject"]], ridx[f["relation"]]] += 1
    part[name_i[f["object"]], R + ridx[f["relation"]]] += 1
P_name = part / (np.linalg.norm(part, axis=1, keepdims=True) + 1e-12)
PC = P.unit(fit_anchors(P_name, KC))
clus_of = {n: int(np.argmax(P_name[i] @ PC.T)) for n, i in name_i.items()}

tr_q = [i for i, q in enumerate(queries) if q["train"]]
rel_entry = {}
for r in RELS:
    fs = [f for f in facts if f["relation"] == r]
    tr = [i for i in tr_q if queries[i]["relation"] == r][:300]
    if not tr:
        tr = [i for i, q in enumerate(queries) if q["relation"] == r][:20]
    rel_entry[r] = {
        "proto": P.unit(Zq[tr].mean(0)),
        "t": fit_translation(Zq[tr], np.stack([Zf[queries[i]["fact_idx"]]
                                               for i in tr]))}

store = MemoryStore()
for f, zf in zip(facts, Zf):
    store.add(zf, f["entities"], f["text"])

# ---- apply ALL test-case edits via supersession ---------------------------
fact_key = {(f["subject"], f["relation"], f["object"]): i
            for i, f in enumerate(facts)}
test_cases = [c for c in cases if c["case_id"] not in
              set(w["train_case_ids"])]
edit_rows, new_texts = [], []
for c in test_cases:
    for rw in c["requested_rewrite"]:
        key = (rw["subject"], rw["relation_id"], rw["target_true"]["str"])
        if key not in fact_key:
            continue
        new_texts.append(f"{rw['prompt'].format(rw['subject'])} "
                         f"{rw['target_new']['str']}.")
        edit_rows.append({"old_idx": fact_key[key], "rw": rw,
                          "case_id": c["case_id"],
                          "q": rw["question"],
                          "subject": rw["subject"],
                          "rel": rw["relation_id"],
                          "new_obj": rw["target_new"]["str"]})
ecache = ROOT / "results" / "k6_edit_emb.npz"
if ecache.exists():
    ez = np.load(ecache)
    Zn, Zeq = ez["Zn"], ez["Zeq"]
else:
    Zn = P.embed_texts(new_texts)
    Zeq = P.embed_texts([e["q"] for e in edit_rows])
    np.savez(ecache, Zn=Zn, Zeq=Zeq)

live = list(range(len(facts)))
for e, zn, txt in zip(edit_rows, Zn, new_texts):
    ni = store.add(zn, [e["subject"], e["new_obj"]], txt)
    store.supersede(e["old_idx"], ni)
    e["new_idx"] = ni
    live.append(ni)
live = [i for i in live if not store.shadowed[i]]
print(f"[edits] {len(edit_rows)} counterfactual edits superseded "
      f"({len(test_cases)} test cases)", flush=True)

# live-fact views for gates + object lookup
fact_obj = {}
subj_slots, obj_slots = {}, {}
BRIDGE = set()
live_rows = []
for i in live:
    if i < len(facts):
        s_, r_, o_ = facts[i]["subject"], facts[i]["relation"], \
            facts[i]["object"]
    else:
        e = next(x for x in edit_rows if x.get("new_idx") == i)
        s_, r_, o_ = e["subject"], e["rel"], e["new_obj"]
    fact_obj[i] = o_
    subj_slots.setdefault(s_, set()).add(r_)
    obj_slots.setdefault(o_, set()).add(r_)
    live_rows.append((s_, r_, o_))
for s_, rs in subj_slots.items():
    for a in obj_slots.get(s_, ()):
        for b in rs:
            BRIDGE.add((a, b))

walker = ChannelWalker(store, protos={r: rel_entry[r]["proto"] for r in RELS},
                       ops={r: rel_entry[r]["t"] for r in RELS})
det = nn.Sequential(nn.Linear(1024, 256), nn.GELU(), nn.Linear(256, R))
det.load_state_dict(torch.load(ROOT / "checkpoints" / "k6_det.pt",
                               weights_only=True))
ans = nn.Sequential(nn.Linear(1024, 128), nn.GELU(), nn.Linear(128, KC))
ans.load_state_dict(torch.load(ROOT / "checkpoints" / "k6_ans.pt",
                               weights_only=True))
rng_cprof = {}
for r in RELS:
    v = np.zeros(KC)
    for s_, r_, o_ in live_rows:
        if r_ == r and o_ in clus_of:
            v[clus_of[o_]] += 1
    rng_cprof[r] = v / (v.sum() + 1e-12)
art = dict(RELS=RELS, rel_entry=rel_entry, rng_cprof=rng_cprof,
           P_name=P_name, name_i=name_i)
plan = P.make_planner(det, ans, art, max_k=4, cand_k=5,
                      link_ok=lambda a, b: (a, b) in BRIDGE,
                      entry_ok=lambda s_, r: r in subj_slots.get(s_, ()))

# ---- metric 3a: did each edit land? (single-hop recall at the address) ----
hit1 = 0
for e, zq in zip(edit_rows, Zeq):
    got = walker.walk(id_tokens([e["subject"]]), [e["rel"]])
    hit1 += got is not None and fact_obj.get(got) == e["new_obj"]
m3_single = hit1 / len(edit_rows)
print(f"[edit-landed] single-hop recall at edited address = "
      f"{m3_single:.3f} (n={len(edit_rows)})", flush=True)

# ---- metric 1: post-edit multi-hop --------------------------------------
res, t_all, n_all = {}, 0.0, 0
for nh in ("2hop", "3hop", "4hop"):
    rows = [(h, Zh[i]) for i, h in enumerate(hops)
            if not h["train"] and h["kind"] == nh and h["phrasing"] == 0]
    hit = ab = 0
    for h, zq in rows:
        c = case_by_id[h["case_id"]]
        golds = {c["new_answer"]} | set(c.get("new_answer_alias", []))
        t0 = time.perf_counter()
        p = plan(zq, h["subject"])
        got = None
        if p is not None and not walker.abstain_hop1(
                id_tokens([h["subject"]]), p[0]):
            got = walker.walk(id_tokens([h["subject"]]), p)
        t_all += time.perf_counter() - t0
        n_all += 1
        if got is None:
            ab += 1
        else:
            hit += fact_obj.get(got) in golds
    res[nh] = {"p1": hit / len(rows), "abstain": ab / len(rows),
               "n": len(rows),
               "p1_ci95": wilson_ci(hit, len(rows))}
    print(f"[k6-POST {nh}] P@1={hit/len(rows):.3f} "
          f"abstain={ab/len(rows):.3f} (n={len(rows)})", flush=True)
m1 = sum(res[k]["p1"] * res[k]["n"] for k in res) / sum(res[k]["n"]
                                                        for k in res)
print(f"[k6-POST all] P@1={m1:.3f} | edit-propagation gap = "
      f"{m3_single - m1:.3f} | {1000*t_all/n_all:.0f} ms/question",
      flush=True)

out = ROOT / "results" / "k6_postedit.json"
out.write_text(json.dumps(
    {"post_edit": res, "overall_p1": m1,
     "edit_landed_single": m3_single,
     "propagation_gap": m3_single - m1,
     "ms_per_question": 1000 * t_all / n_all,
     "n_edits": len(edit_rows),
     "setting": "pooled store, ALL test edits applied at once",
     "manifest": run_manifest(seed=0, inputs={
         "world": ROOT / "data" / "mquake" / "world_cf3k.json"})},
    indent=2))
print(f"[done] {out.relative_to(ROOT)}")
