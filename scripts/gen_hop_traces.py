"""C2 — oracle traces over world v3 for behavior cloning.

Runs the oracle policy through HopEnv on every hop case + a sample of
single-hop and no-answer queries, logging (state features, action) per step.
Successful trajectories only for the BC set (CoRAG-style rejection), with
failures counted per composition — the trained policy's headroom.

Writes data/hop_traces_v0.jsonl + summary.
Usage: .venv/bin/python scripts/gen_hop_traces.py
"""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from codec.hop_env import ABSTAIN, HALT, Action, HopEnv, oracle_policy
from codec.memory_store import MemoryStore, fit_translation, id_tokens
from codec.structure_channel import hash_test_mask
from codec.role_bits import _nlp

def unit(X): return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)

world = json.loads((ROOT / "data" / "closed_world_v3.json").read_text())
facts, queries, hops = world["facts"], world["queries"], world["hops"]
z = np.load(ROOT / "results" / "closed_world_v3_emb.npz")
Zf, Zq, Zh = z["Zf"], z["Zq"], z["Zh"]
nlp = _nlp()
HELD = set(world["held_out_phrasings"])

def qids_of(text):
    doc = nlp(text)
    return id_tokens([t.text.rstrip("'s") if t.text.endswith("'s") else t.text
                      for t in doc if t.pos_ == "PROPN"]
                     + [t.text for t in doc if t.like_num])

store = MemoryStore()
for f, zf in zip(facts, Zf):
    store.add(zf, f["entities"] + f["numbers"], f["text"])

RELS = sorted({f["relation"] for f in facts})
seen = [i for i, q in enumerate(queries) if q["kind"] == "single"
        and q["phrasing_idx"] not in HELD]
t_by_rel = {}
for rel in RELS:
    tr = [i for i in seen if queries[i]["relation"] == rel][:300]
    t_by_rel[rel] = fit_translation(
        Zq[tr], np.stack([Zf[queries[i]["fact_idx"]] for i in tr]))
env = HopEnv(store, RELS, t_by_rel)

def run(q_z, q_ids, chain, answer_fact):
    obs = env.reset(q_z, q_ids)
    steps = []
    done = False
    while not done:
        a = oracle_policy(env, obs, chain)
        steps.append({
            "step": obs.step,
            "id_cov": obs.id_cov, "margin": obs.margin, "top": obs.top_score,
            "action_rel": (a.relation if a.relation >= 0
                           else ("HALT" if a.relation == HALT else "ABSTAIN")),
            "hand_ids": sorted(a.hand_ids), "demote": sorted(a.demote_ids),
            "exclude": a.exclude_visited})
        obs, done = env.step(a)
        if a.relation in (HALT, ABSTAIN):
            break
    ok = (env.cur == answer_fact) if answer_fact >= 0 else (env.cur is None)
    return steps, ok

traces, stats = [], {}
# hop cases (chain given — the policy must LEARN to infer it from q text)
for i, h in enumerate(hops):
    steps, ok = run(Zh[i], qids_of(h["text"]), h["chain"], h["answer_fact"])
    stats.setdefault(h["kind"], [0, 0])
    stats[h["kind"]][1] += 1
    stats[h["kind"]][0] += ok
    if ok:
        traces.append({"text": h["text"], "kind": h["kind"],
                       "chain": h["chain"], "steps": steps})
# single-hop (chain = [relation])
singles = [i for i, q in enumerate(queries) if q["kind"] == "single"][:1500]
for i in singles:
    q = queries[i]
    steps, ok = run(Zq[i], qids_of(q["text"]), [q["relation"]], q["fact_idx"])
    stats.setdefault("single", [0, 0])
    stats["single"][1] += 1
    stats["single"][0] += ok
    if ok:
        traces.append({"text": q["text"], "kind": "single",
                       "chain": [q["relation"]], "steps": steps})
# no-answer (oracle should abstain via coverage; chain = best-guess relation)
for i, q in enumerate(queries):
    if q["kind"] != "no_answer":
        continue
    steps, ok = run(Zq[i], qids_of(q["text"]), [q["relation"]], -1)
    stats.setdefault("no_answer", [0, 0])
    stats["no_answer"][1] += 1
    stats["no_answer"][0] += ok
    if ok:
        traces.append({"text": q["text"], "kind": "no_answer",
                       "chain": [q["relation"]], "steps": steps})

out = ROOT / "data" / "hop_traces_v0.jsonl"
out.write_text("".join(json.dumps(t) + "\n" for t in traces))
print(f"[traces] {len(traces)} successful trajectories -> {out.name}")
for k, (ok, n) in sorted(stats.items()):
    print(f"  {k:>12}: oracle {ok}/{n} = {ok/n:.3f}")
(ROOT / "results" / "hop_traces_summary.json").write_text(json.dumps(
    {"generated_at": datetime.now(timezone.utc).isoformat(),
     "n_traces": len(traces),
     "oracle": {k: {"ok": v[0], "n": v[1]} for k, v in stats.items()}}, indent=2))
