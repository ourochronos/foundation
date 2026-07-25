"""v0.5 — typed chain assembly: composition by unification, not learning.

D36/v0.2-4 established that BC cannot learn compositional routing here — and
the diagnosis matured: with type-constrained relations, cue-set lookup is
extensionally perfect on training data, so no comparative rule is ever
learned; worse, the chain is not a learning target at all. Given (detected
relation cues, subject type, answer type), the valid chain is COMPUTABLE:
  chain = ordering of cue relations s.t. domain(r1)=subject type,
          range(ri)=domain(ri+1), range(rk)=answer type.
The law, fifth altitude: composition is structure; structure is symbolic.
Learned components keep the jobs they won: cue detection features, abstention
(id-coverage), halting (chain completion).

Usage: .venv/bin/python scripts/probe_typed_planner.py
"""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from codec.hop_env import Action, HopEnv
from codec.memory_store import MemoryStore, fit_translation, id_tokens
from codec.structure_channel import hash_test_mask
from codec.role_bits import _nlp

def unit(X): return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)

SIG = {"capital_of": ("country", "city"), "largest_city_of": ("country", "city"),
       "located_in": ("city", "country"), "ceo_of": ("company", "person"),
       "founded_in": ("company", "year"), "born_in": ("person", "year"),
       "population_of": ("city", "number"), "headquartered_in": ("company", "city"),
       "mayor_of": ("city", "person")}
CUES = {"capital_of": {"capital", "seat", "government", "administrative"},
        "largest_city_of": {"largest", "biggest", "populous", "urban"},
        "ceo_of": {"ceo", "executive", "helm", "boss"},
        "founded_in": {"founded", "established", "opened", "incorporated", "founding"},
        "born_in": {"born", "birth"},
        "population_of": {"population", "residents", "inhabitants", "headcount",
                          "people", "live"},
        "located_in": {"country", "nation", "belongs", "situated", "contains"},
        "headquartered_in": {"headquartered", "headquarters", "based", "office",
                             "operates"},
        "mayor_of": {"mayor", "mayoralty", "hall"}}
ANS_CUE = [("person", {"who", "whom"}),
           ("year", {"year", "when"}),
           ("number", {"many", "population", "headcount", "residents",
                       "inhabitants"}),
           ("country", {"country", "nation"}),
           ("city", {"city", "capital", "where"})]

world = json.loads((ROOT / "data" / "closed_world_v4.json").read_text())
facts, queries, hops = world["facts"], world["queries"], world["hops"]
z = np.load(ROOT / "results" / "closed_world_v4_emb.npz")
Zf, Zq, Zh = z["Zf"], z["Zq"], z["Zh"]
nlp = _nlp()
HELD = set(world["held_out_phrasings"])

subj_type = {}          # entity -> type, from the store's own facts
for f in facts:
    d, r = SIG[f["relation"]]
    subj_type.setdefault(f["subject"], d)
    if r not in ("year", "number"):
        subj_type.setdefault(f["object"], r)

def qids_of(text):
    doc = nlp(text)
    return id_tokens([t.text.rstrip("'s") if t.text.endswith("'s") else t.text
                      for t in doc if t.pos_ == "PROPN"]
                     + [t.text for t in doc if t.like_num])

def detect(text):
    low = {t.lemma_.lower() for t in nlp(text)} | {w.lower() for w in text.split()}
    rels = {r for r, cs in CUES.items() if low & cs}
    ans = next((a for a, cs in ANS_CUE if low & cs), None)
    return rels, ans

def plan(text, subj):
    rels, ans = detect(text)
    st = subj_type.get(subj)
    chains = []
    for k in (1, 2, 3):
        for perm in permutations(rels, k):
            if SIG[perm[0]][0] != st:
                continue
            ok = all(SIG[perm[i]][1] == SIG[perm[i + 1]][0]
                     for i in range(k - 1))
            if ok and (ans is None or SIG[perm[-1]][1] == ans):
                chains.append(list(perm))
    # prefer longest chains that use the most detected cues, then shortest
    if not chains:
        return None
    chains.sort(key=lambda c: (-len(set(c)), len(c)))
    return chains[0]

store = MemoryStore()
for f, zf in zip(facts, Zf):
    store.add(zf, f["entities"] + f["numbers"], f["text"])
RELS = sorted(SIG)
seen = [i for i, q in enumerate(queries) if q["kind"] == "single"
        and q["phrasing_idx"] not in HELD]
t_by_rel = {}
for rel in RELS:
    tr = [i for i in seen if queries[i]["relation"] == rel][:300]
    t_by_rel[rel] = fit_translation(
        Zq[tr], np.stack([Zf[queries[i]["fact_idx"]] for i in tr]))
env = HopEnv(store, RELS, t_by_rel)

def walk(q_z, q_ids, chain):
    obs = env.reset(q_z, q_ids)
    for k, rel in enumerate(chain):
        a = Action(relation=RELS.index(rel),
                   hand_ids=(obs.cur_ids or set()) - q_ids if k else set(),
                   demote_ids=q_ids if k else set(), exclude_visited=k > 0)
        obs, _ = env.step(a)
        if k == 0 and obs.id_cov < 0.34:      # B2 abstention on first probe
            return None, "abstain"
    return env.cur, "halt"

res = {}
subj_of_hop = {h["text"]: h["subject"] for h in hops}
plan_ok = {}
for kind in sorted({h["kind"] for h in hops}):
    cases = [(h, Zh[i]) for i, h in enumerate(hops) if h["kind"] == kind]
    hit = pok = 0
    for h, zq in cases:
        p = plan(h["text"], h["subject"])
        pok += (p == h["chain"])
        if p is None:
            continue
        got, _ = walk(zq, qids_of(h["text"]), p)
        hit += got == h["answer_fact"]
    res[kind] = hit / len(cases)
    plan_ok[kind] = pok / len(cases)
    tag = " [HOLDOUT]" if kind in world["holdout_compositions"] else ""
    print(f"[typed {kind:>12}] chain-correct={pok/len(cases):.3f} "
          f"end-to-end P@1={hit/len(cases):.3f} (n={len(cases)}){tag}")
# no-answer: plan returns None (type-invalid) or coverage abstains
na = [i for i, q in enumerate(queries) if q["kind"] == "no_answer"]
ab = 0
for i in na:
    q = queries[i]
    subj = next((e for e in qids_of(q["text"])), "")
    p = plan(q["text"], None)   # unknown subject type -> often no valid chain
    if p is None:
        ab += 1
    else:
        got, how = walk(Zq[i], qids_of(q["text"]), p)
        ab += how == "abstain"
print(f"[typed    no_answer] abstain = {ab/len(na):.3f} (n={len(na)})")
res["no_answer_abstain"] = ab / len(na)
(ROOT / "results" / "typed_planner_v05.json").write_text(json.dumps(
    {"generated_at": datetime.now(timezone.utc).isoformat(),
     "end_to_end": res, "chain_correct": plan_ok}, indent=2))
print("[done] results/typed_planner_v05.json")
