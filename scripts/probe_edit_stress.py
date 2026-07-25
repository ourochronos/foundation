"""A6b — supersession at n=200 + old-object queries + chained edits (threat #11).

Measures: (1) post-edit new-object accuracy at n=200; (2) chained edits (50
countries edited twice — the second supersede must target the FIRST edit);
(3) old-object pollution: queries naming the OLD capital — what fraction
resolve to the superseding entry (id-union makes the new entry claim the old
capital's tokens); (4) controls.

Usage: .venv/bin/python scripts/probe_edit_stress.py
"""
from __future__ import annotations
import json, random, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from codec import whiten as W
from codec.memory_store import MemoryStore, id_tokens
from codec.role_bits import _nlp

def unit(X): return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)

world = json.loads((ROOT / "data" / "closed_world_v3.json").read_text())
facts, queries = world["facts"], world["queries"]
z = np.load(ROOT / "results" / "closed_world_v3_emb.npz")
Zf, Zq = z["Zf"], z["Zq"]
nlp = _nlp()
rng = random.Random(5)

cap_facts = {f["subject"]: i for i, f in enumerate(facts)
             if f["relation"] == "capital_of" and (f["year"] is None or f["year"] >= 2000)}
cities = sorted({f["object"] for f in facts if f["relation"] == "capital_of"})
countries = rng.sample(sorted(cap_facts), 250)
edit1, edit2 = countries[:200], countries[:50]        # 50 get a second edit

E_T = ["The capital of {c} was moved to {n}.", "{c} relocated its capital to {n}.",
       "{n} became the new capital of {c}.", "As of this year, {c}'s capital is {n}."]
def mk_edits(cs, tag):
    rows = []
    for c in cs:
        old = facts[cap_facts[c]]["object"]
        n = rng.choice([x for x in cities if x != old])
        rows.append({"country": c, "old": facts[cap_facts[c]]["object"], "new": n,
                     "text": rng.choice(E_T).format(c=c, n=n)})
    return rows
e1 = mk_edits(edit1, 1)
e2 = mk_edits(edit2, 2)

from codec.encode import M3Encoder
enc = M3Encoder()
whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
def embed(ts):
    d, _ = enc.encode(ts, sparse=False); return unit(W.apply(d, whitener))
Ze1, Ze2 = embed([e["text"] for e in e1]), embed([e["text"] for e in e2])
oldq = [f"Name the capital city of {e['old']}." for e in e1[:100]]  # nonsense form? no —
oldq = [f"Which country claims {e['old']} as its capital?" for e in e1[:100]]
Zoq = embed(oldq)

store = MemoryStore()
for f, zf in zip(facts, Zf):
    store.add(zf, f["entities"] + f["numbers"], f["text"])

def apply(edits, Z):
    for e, zv in zip(edits, Z):
        ids = [e["country"], e["new"]]
        top = store.query(zv, id_tokens(ids), k=1, id_weight=0.5)[0]
        ni = store.add(zv, ids, e["text"])
        if top[1] >= 0.88:
            store.supersede(top[0], ni)
apply(e1, Ze1)

# post-edit accuracy (round 1): capital queries for edited countries
def qids_of(text):
    doc = nlp(text)
    return id_tokens([t.text.rstrip("'s") if t.text.endswith("'s") else t.text
                      for t in doc if t.pos_ == "PROPN"])
cq = {i: q for i, q in enumerate(queries)
      if q["kind"] == "single" and q["relation"] == "capital_of"}
by_subj = {facts[q["fact_idx"]]["subject"]: i for i, q in cq.items()}
def post_acc(edits):
    hits = tot = 0
    for e in edits:
        i = by_subj.get(e["country"])
        if i is None: continue
        tot += 1
        r = store.query(Zq[i], qids_of(queries[i]["text"]), k=1, id_weight=0.5)[0]
        hits += e["new"].split()[0] in r[2]
    return hits / max(tot, 1), tot
a1, n1 = post_acc(e1)
print(f"[1] post-edit new-object acc (200 edits): {a1:.3f} (n={n1})")

apply(e2, Ze2)   # chained: second edit on 50 of the same countries
a2, n2 = post_acc(e2)
print(f"[2] chained-edit FINAL-object acc (50 double-edits): {a2:.3f} (n={n2})")

# old-object pollution: query names the OLD capital — top-1 = superseding entry?
pol = 0
for e, zq in zip(e1[:100], Zoq):
    r = store.query(zq, id_tokens([e["old"]]), k=1, id_weight=0.5)[0]
    pol += (e["new"].split()[0] in r[2]) and (e["old"].split()[0] not in
                                              facts[cap_facts[e["country"]]]["text"][:0] or True) and (e["new"] in r[2])
pol_rate = pol / 100
print(f"[3] old-object query pollution: {pol_rate:.2%} resolve to superseding entry")

ctrl = [i for s, i in by_subj.items() if s not in set(edit1)][:100]
ch = np.mean([store.query(Zq[i], qids_of(queries[i]["text"]), k=1,
                          id_weight=0.5)[0][0] == queries[i]["fact_idx"] for i in ctrl])
print(f"[4] untouched controls: {ch:.3f}")
(ROOT / "results" / "edit_stress_a6b.json").write_text(json.dumps(
    {"generated_at": datetime.now(timezone.utc).isoformat(),
     "post_edit_acc": a1, "chained_acc": a2, "old_object_pollution": pol_rate,
     "controls": float(ch), "n": [n1, n2, 100, len(ctrl)]}, indent=2))
print("[done] results/edit_stress_a6b.json")
