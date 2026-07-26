"""K6 L1 — (a) per-case store setting (docs/09 both-settings pass);
(b) propagation-decay diagnosis on pooled post-edit misses: which hop
diverges first, single- vs multi-edit cases, and whether the correct next
fact even existed in the store.

Usage: .venv/bin/python scripts/k6_stage4_l1.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
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
cases = json.loads((ROOT / "data" / "mquake" /
                    "MQuAKE-CF-3k.json").read_text())
case_by_id = {c["case_id"]: c for c in cases}
z = np.load(ROOT / "results" / "mquake_cf3k_emb_v2.npz")
Zf, Zq, Zh = z["Zf"], z["Zq"], z["Zh"]
ez = np.load(ROOT / "results" / "k6_edit_emb.npz")
Zn = ez["Zn"]
RELS = sorted({f["relation"] for f in facts})
R = len(RELS)
ridx = {r: i for i, r in enumerate(RELS)}

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
    tr = [i for i in tr_q if queries[i]["relation"] == r][:300]
    if not tr:
        tr = [i for i, q in enumerate(queries) if q["relation"] == r][:20]
    rel_entry[r] = {
        "proto": P.unit(Zq[tr].mean(0)),
        "t": fit_translation(Zq[tr], np.stack([Zf[queries[i]["fact_idx"]]
                                               for i in tr]))}
det = nn.Sequential(nn.Linear(1024, 256), nn.GELU(), nn.Linear(256, R))
det.load_state_dict(torch.load(ROOT / "checkpoints" / "k6_det.pt",
                               weights_only=True))
ans = nn.Sequential(nn.Linear(1024, 128), nn.GELU(), nn.Linear(128, KC))
ans.load_state_dict(torch.load(ROOT / "checkpoints" / "k6_ans.pt",
                               weights_only=True))

fact_key = {(f["subject"], f["relation"], f["object"]): i
            for i, f in enumerate(facts)}
train_ids = set(w["train_case_ids"])
test_cases = [c for c in cases if c["case_id"] not in train_ids]
edit_emb = {}
k = 0
for c in test_cases:
    for rw in c["requested_rewrite"]:
        key = (rw["subject"], rw["relation_id"], rw["target_true"]["str"])
        if key in fact_key:
            edit_emb[(c["case_id"], key)] = (Zn[k], rw)
            k += 1

hop_rows = {(h["case_id"], h["phrasing"]): (i, h)
            for i, h in enumerate(hops) if not h["train"]}


def run_case(c):
    """Per-case store: case facts + post-edit real facts, edits superseded."""
    st = MemoryStore()
    kmap = {}
    tl = c["orig"]["triples_labeled"]
    tr_ = c["orig"]["triples"]
    rows = []
    for (sl, rl, ol), t in zip(tl, tr_):
        fi = fact_key.get((sl, t[1], ol))
        if fi is None:
            return None
        rows.append((sl, t[1], ol, Zf[fi]))
    ek = {tuple(t) for t in c["orig"]["edit_triples"]}
    ntl, ntr = c["orig"]["new_triples_labeled"], c["orig"]["new_triples"]
    for (sl, rl, ol), t in zip(ntl, ntr):
        if tuple(t) in ek:
            continue
        fi = fact_key.get((sl, t[1], ol))
        if fi is not None:
            rows.append((sl, t[1], ol, Zf[fi]))
    idx_of = {}
    for s_, r_, o_, zf in rows:
        idx_of[(s_, r_, o_)] = st.add(zf, [s_, o_], f"{s_}|{r_}|{o_}")
    obj_of = {v: k_[2] for k_, v in idx_of.items()}
    for rw_key, (zn, rw) in edit_emb.items():
        if rw_key[0] != c["case_id"]:
            continue
        old = idx_of.get(rw_key[1])
        if old is None:
            continue
        ni = st.add(zn, [rw["subject"], rw["target_new"]["str"]], "edit")
        st.supersede(old, ni)
        obj_of[ni] = rw["target_new"]["str"]
    live = [(s_, r_, o_) for (s_, r_, o_), i in idx_of.items()
            if not st.shadowed[i]]
    for rw_key, (zn, rw) in edit_emb.items():
        if rw_key[0] == c["case_id"] and rw_key[1] in idx_of:
            live.append((rw["subject"], rw["relation_id"],
                         rw["target_new"]["str"]))
    ss, os_ = {}, {}
    for s_, r_, o_ in live:
        ss.setdefault(s_, set()).add(r_)
        os_.setdefault(o_, set()).add(r_)
    br = {(a, b) for n in set(ss) | set(os_)
          for a in os_.get(n, ()) for b in ss.get(n, ())}
    wk = ChannelWalker(st, protos={r: rel_entry[r]["proto"] for r in RELS},
                       ops={r: rel_entry[r]["t"] for r in RELS})
    rng_c = {}
    for r in RELS:
        v = np.zeros(KC)
        for s_, r_, o_ in live:
            if r_ == r and o_ in clus_of:
                v[clus_of[o_]] += 1
        rng_c[r] = v / (v.sum() + 1e-12)
    art = dict(RELS=RELS, rel_entry=rel_entry, rng_cprof=rng_c,
               P_name=P_name, name_i=name_i)
    plan = P.make_planner(det, ans, art, max_k=4, cand_k=5,
                          link_ok=lambda a, b: (a, b) in br,
                          entry_ok=lambda s_, r: r in ss.get(s_, ()))
    row = hop_rows.get((c["case_id"], 0))
    if row is None:
        return None
    i, h = row
    golds = {c["new_answer"]} | set(c.get("new_answer_alias", []))
    p = plan(Zh[i], h["subject"])
    got = None
    if p is not None and not wk.abstain_hop1(id_tokens([h["subject"]]),
                                             p[0]):
        got = wk.walk(id_tokens([h["subject"]]), p)
    return (obj_of.get(got) in golds if got is not None else False,
            len(c["single_hops"]))


hitk = Counter()
nk = Counter()
for c in test_cases:
    r = run_case(c)
    if r is None:
        continue
    ok, nh = r
    hitk[nh] += ok
    nk[nh] += 1
res_pc = {}
for nh in sorted(nk):
    res_pc[f"{nh}hop"] = {"p1": hitk[nh] / nk[nh], "n": nk[nh],
                          "p1_ci95": wilson_ci(hitk[nh], nk[nh])}
    print(f"[percase {nh}hop] P@1={hitk[nh]/nk[nh]:.3f} (n={nk[nh]})",
          flush=True)
tot = sum(hitk.values()) / sum(nk.values())
print(f"[percase all] P@1={tot:.3f}", flush=True)

# ---- (b) pooled propagation diagnosis ------------------------------------
diag = Counter()
# rebuild pooled edited store exactly as stage 3
store = MemoryStore()
for f, zf in zip(facts, Zf):
    store.add(zf, f["entities"], f["text"])
new_idx_of = {}
for (cid, key), (zn, rw) in edit_emb.items():
    old = fact_key[key]
    ni = store.add(zn, [rw["subject"], rw["target_new"]["str"]],
                   f"{rw['subject']}|{rw['relation_id']}|"
                   f"{rw['target_new']['str']}")
    store.supersede(old, ni)
    new_idx_of[(cid, key)] = ni
fact_obj = {i: f["object"] for i, f in enumerate(facts)}
for (cid, key), ni in new_idx_of.items():
    fact_obj[ni] = edit_emb[(cid, key)][1]["target_new"]["str"]
subj_slots, obj_slots = {}, {}
for i in range(len(store.texts)):
    if store.shadowed[i]:
        continue
    if i < len(facts):
        s_, r_, o_ = facts[i]["subject"], facts[i]["relation"], \
            facts[i]["object"]
    else:
        e = next(v for k2, v in edit_emb.items()
                 if new_idx_of.get(k2) == i)[1]
        s_, r_, o_ = e["subject"], e["relation_id"], e["target_new"]["str"]
    subj_slots.setdefault(s_, set()).add(r_)
    obj_slots.setdefault(o_, set()).add(r_)
BRIDGE = {(a, b) for n in set(subj_slots) | set(obj_slots)
          for a in obj_slots.get(n, ()) for b in subj_slots.get(n, ())}
walker = ChannelWalker(store, protos={r: rel_entry[r]["proto"]
                                      for r in RELS},
                       ops={r: rel_entry[r]["t"] for r in RELS})
rng_cprof = {}
for r in RELS:
    v = np.zeros(KC)
    for i in range(len(facts)):
        if not store.shadowed[i] and facts[i]["relation"] == r \
                and facts[i]["object"] in clus_of:
            v[clus_of[facts[i]["object"]]] += 1
    rng_cprof[r] = v / (v.sum() + 1e-12)
art = dict(RELS=RELS, rel_entry=rel_entry, rng_cprof=rng_cprof,
           P_name=P_name, name_i=name_i)
plan = P.make_planner(det, ans, art, max_k=4, cand_k=5,
                      link_ok=lambda a, b: (a, b) in BRIDGE,
                      entry_ok=lambda s_, r: r in subj_slots.get(s_, ()))

for c in test_cases:
    row = hop_rows.get((c["case_id"], 0))
    if row is None:
        continue
    i, h = row
    golds = {c["new_answer"]} | set(c.get("new_answer_alias", []))
    p = plan(Zh[i], h["subject"])
    # gold post-edit chain fact indices
    ek = {tuple(t) for t in c["orig"]["edit_triples"]}
    gold_path = []
    okpath = True
    for (sl, rl, ol), t in zip(c["orig"]["new_triples_labeled"],
                               c["orig"]["new_triples"]):
        if tuple(t) in ek:
            ky = next((k2 for k2 in edit_emb
                       if k2[0] == c["case_id"]
                       and k2[1][1] == t[1] and k2[1][0] == sl), None)
            gold_path.append(new_idx_of.get(ky) if ky else None)
        else:
            gold_path.append(fact_key.get((sl, t[1], ol)))
    if any(g is None for g in gold_path):
        okpath = False
    n_edits = len(c["requested_rewrite"])
    tag = "1edit" if n_edits == 1 else "multiedit"
    if p is None:
        diag[(tag, "no-plan")] += 1
        continue
    gold_chain = [t[1] for t in c["orig"]["new_triples"]]
    if p != gold_chain:
        diag[(tag, "wrong-chain")] += 1
        continue
    if not okpath:
        diag[(tag, "gold-fact-missing")] += 1
        continue
    # walk with tracing
    hand = id_tokens([h["subject"]])
    visited = set()
    dv = None
    for k2, rel in enumerate(p):
        r_ = store.query(walker.pt[rel], hand or None, k=1, id_weight=1.0,
                         exclude=visited if k2 else None)
        cur = r_[0][0]
        visited.add(cur)
        if cur != gold_path[k2]:
            dv = k2
            break
        hand = store.content_ids[cur] - hand
    if dv is None:
        ok = fact_obj.get(gold_path[-1]) in golds
        diag[(tag, "ok" if ok else "gold-obj-mismatch")] += 1
    else:
        diag[(tag, f"diverge-hop{dv+1}")] += 1

print("[diagnosis]", dict(sorted(diag.items())), flush=True)
out = ROOT / "results" / "k6_l1.json"
out.write_text(json.dumps(
    {"per_case": res_pc, "per_case_overall": tot,
     "pooled_diagnosis": {f"{a}|{b}": v for (a, b), v in diag.items()},
     "manifest": run_manifest(seed=0)}, indent=2))
print(f"[done] {out.relative_to(ROOT)}")
