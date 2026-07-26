"""L1(a) — per-case CLEAN pass: real gates, and a 2x2 over the two
store-derived artifacts that might starve on 5-fact stores:
  rng_cprof: case-local vs blended with the global train-store profile
  BRIDGE:    case-local vs union with the global train-store bridge set
Whichever variant closes the pooled/per-case gap names the starving
artifact. Also emits a pooled-style failure anatomy for the best variant.

Usage: .venv/bin/python scripts/k6_percase_clean.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

_src = (ROOT / "scripts" / "k6_stage4_l1.py").read_text()
_head = _src.split("hitk = Counter()")[0].replace(
    'ROOT = Path(__file__).resolve().parent.parent', f'ROOT = Path("{ROOT}")')
exec(_head)  # noqa: S102
from codec.manifest import run_manifest, wilson_ci                # noqa: E402
from codec.walker import ChannelWalker as CW                      # noqa: E402

# global artifacts from TRAIN-case facts ONLY (D64/F4: the first run used
# ALL pooled facts including test cases' — code contradicted the entry's
# anti-leakage claim)
train_fact_idx = set()
for c in cases:
    if c["case_id"] not in set(w["train_case_ids"]):
        continue
    for (sl, rl, ol), t in zip(c["orig"]["triples_labeled"],
                               c["orig"]["triples"]):
        fi = fact_key.get((sl, t[1], ol))
        if fi is not None:
            train_fact_idx.add(fi)
train_facts = [facts[i] for i in sorted(train_fact_idx)]
g_subj, g_obj = {}, {}
for f in train_facts:
    g_subj.setdefault(f["subject"], set()).add(f["relation"])
    g_obj.setdefault(f["object"], set()).add(f["relation"])
G_BRIDGE = {(a, b) for n in set(g_subj) | set(g_obj)
            for a in g_obj.get(n, ()) for b in g_subj.get(n, ())}
G_RNG = {}
for r in RELS:
    v = np.zeros(KC)
    for f in train_facts:
        if f["relation"] == r and f["object"] in clus_of:
            v[clus_of[f["object"]]] += 1
    G_RNG[r] = v / (v.sum() + 1e-12)


def run_case(c, use_grng, use_gbridge, trace=False):
    st = MemoryStore()
    tl, tr_ = c["orig"]["triples_labeled"], c["orig"]["triples"]
    rows = []
    for (sl, rl, ol), t in zip(tl, tr_):
        fi = fact_key.get((sl, t[1], ol))
        if fi is None:
            return None
        rows.append((sl, t[1], ol, Zf[fi]))
    ek = {tuple(t) for t in c["orig"]["edit_triples"]}
    for (sl, rl, ol), t in zip(c["orig"]["new_triples_labeled"],
                               c["orig"]["new_triples"]):
        if tuple(t) not in ek:
            fi = fact_key.get((sl, t[1], ol))
            if fi is not None:
                rows.append((sl, t[1], ol, Zf[fi]))
    # every edit's target_true base fact must be IN the per-case store —
    # multi-edit chains edit facts that sit on neither the original nor the
    # post-edit visible path (case 4: India|capital|New Delhi). Without
    # this, 324/600 walks failed with empty hop-2 coverage (D57).
    for rw_key, (zn, rw) in edit_emb.items():
        if rw_key[0] == c["case_id"] and rw_key[1] in fact_key:
            sl, rel_, ol = rw_key[1]
            if (sl, rel_, ol) not in {(a, b, d) for a, b, d, _ in rows}:
                rows.append((sl, rel_, ol, Zf[fact_key[rw_key[1]]]))
    idx_of, live = {}, []
    for s_, r_, o_, zf in rows:
        idx_of[(s_, r_, o_)] = st.add(zf, [s_, o_], f"{s_}|{r_}|{o_}")
    obj_of = {v: k_[2] for k_, v in idx_of.items()}
    gold_path_keys = []
    for (sl, rl, ol), t in zip(c["orig"]["new_triples_labeled"],
                               c["orig"]["new_triples"]):
        gold_path_keys.append((sl, t[1], ol, tuple(t) in ek))
    for rw_key, (zn, rw) in edit_emb.items():
        if rw_key[0] != c["case_id"] or rw_key[1] not in idx_of:
            continue
        ni = st.add(zn, [rw["subject"], rw["target_new"]["str"]], "edit")
        st.supersede(idx_of[rw_key[1]], ni)
        obj_of[ni] = rw["target_new"]["str"]
        idx_of[(rw["subject"], rw["relation_id"],
                rw["target_new"]["str"])] = ni
    live = [(k_[0], k_[1], k_[2]) for k_, i in idx_of.items()
            if not st.shadowed[i]]
    ss, os_ = {}, {}
    for s_, r_, o_ in live:
        ss.setdefault(s_, set()).add(r_)
        os_.setdefault(o_, set()).add(r_)
    br = {(a, b) for n in set(ss) | set(os_)
          for a in os_.get(n, ()) for b in ss.get(n, ())}
    if use_gbridge:
        br = br | G_BRIDGE
    rng_c = {}
    for r in RELS:
        v = np.zeros(KC)
        for s_, r_, o_ in live:
            if r_ == r and o_ in clus_of:
                v[clus_of[o_]] += 1
        loc = v / (v.sum() + 1e-12)
        rng_c[r] = 0.5 * loc + 0.5 * G_RNG[r] if use_grng else loc
    wk = CW(st, protos={r: rel_entry[r]["proto"] for r in RELS},
            ops={r: rel_entry[r]["t"] for r in RELS})
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
    gold_chain = [t[1] for t in c["orig"]["new_triples"]]
    if p is None:
        return (False, len(tl), "no-plan")
    if not trace:
        got = None
        if not wk.abstain_hop1(id_tokens([h["subject"]]), p[0]):
            got = wk.walk(id_tokens([h["subject"]]), p)
        ok = obj_of.get(got) in golds if got is not None else False
        return (ok, len(tl), "ok" if ok else
                ("wrong-chain" if p != gold_chain else "exec"))
    return None


variants = [("local", False, False), ("+grng", True, False),
            ("+gbridge", False, True), ("+both", True, True)]
out = {}
for name, ug, ub in variants:
    hitk, nk, cat = Counter(), Counter(), Counter()
    for c in test_cases:
        r = run_case(c, ug, ub)
        if r is None:
            continue
        ok, nh, why = r
        hitk[nh] += ok; nk[nh] += 1; cat[why] += 1
    tot = sum(hitk.values()) / sum(nk.values())
    out[name] = {"overall": tot,
                 "by_hop": {str(k): hitk[k] / nk[k] for k in sorted(nk)},
                 "anatomy": dict(cat)}
    print(f"[percase {name:>8}] all={tot:.3f} "
          f"by-hop={[round(hitk[k]/nk[k],3) for k in sorted(nk)]} "
          f"anatomy={dict(cat)}", flush=True)

(ROOT / "results" / "k6_percase_clean.json").write_text(json.dumps(
    {"variants": out, "manifest": run_manifest(seed=0)}, indent=2))
print("[done] results/k6_percase_clean.json", flush=True)

from codec import store_audit as _au
_au.dump("percase")
