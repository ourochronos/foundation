"""J3 — zero-hand-schema planner: the D38 validation.

Every input the D37 planner hand-coded is now DERIVED from data:
  types      k-means clusters over entity-name embeddings (+ literals);
             an entity's type = soft cluster assignment
  signatures relation domain/range = mean type-assignment of its actual
             subject/object populations (store content)
  detection  RETRIEVAL: question spans (noun chunks + verbs, minus entities)
             scored against relation prototypes = centroids of that
             relation's training-question embeddings
  answer     cluster prototypes from training questions grouped by their
             answer's cluster
  planning   chains scored ADDITIVELY: subject~domain + range~domain links +
             range~answer + detection scores. Exact unification is the
             crisp-signature limit (D37); this is the open-world form.
Same world, same holdouts as D37. Comparison: hand-schema holdouts were
0.553 / 0.353 / 0.042 end-to-end.

Usage: .venv/bin/python scripts/probe_soft_planner.py
"""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from codec import whiten as W
from codec.hop_env import Action, HopEnv
from codec.memory_store import MemoryStore, fit_translation, id_tokens
from codec.structure_channel import hash_test_mask
from codec.role_bits import _nlp

def unit(X): return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)

world = json.loads((ROOT / "data" / "closed_world_v4.json").read_text())
facts, queries, hops = world["facts"], world["queries"], world["hops"]
z = np.load(ROOT / "results" / "closed_world_v4_emb.npz")
Zf, Zq, Zh = z["Zf"], z["Zq"], z["Zh"]
nlp = _nlp()
HELD = set(world["held_out_phrasings"])
RELS = sorted({f["relation"] for f in facts})

from codec.encode import M3Encoder
enc = M3Encoder()
wh = W.load(str(ROOT / "results" / "whiten_v0.npz"))
def embed(ts):
    d, _ = enc.encode(ts, sparse=False)
    return unit(W.apply(d, wh))

# ---- types: RELATIONAL PARTICIPATION (D38's own design — an entity's type
# is what it does in the store; surface-name embeddings cluster by phonology
# and carry no kind signal for invented names, measured 0.862 indistinct) ----
names = sorted({f["subject"] for f in facts} | {f["object"] for f in facts})
cache = ROOT / "results" / "soft_planner_emb.npz"
if cache.exists():
    zz = np.load(cache, allow_pickle=True)
    E, span_texts, S_emb = zz["E"], list(zz["span_texts"]), zz["S_emb"]
else:
    E = embed(names)
    # spans for hop questions + a query sample (detection inputs)
    span_texts, seen_sp = [], set()
    def spans_of(text):
        doc = nlp(text)
        out = []
        ents = {t.text for t in doc if t.pos_ == "PROPN"}
        for ch in doc.noun_chunks:
            t = " ".join(w.text for w in ch if w.text not in ents
                         and w.pos_ != "PROPN" and not w.is_stop)
            if len(t) > 2: out.append(t)
        out += [t.lemma_ for t in doc if t.pos_ == "VERB" and not t.is_stop]
        return out[:5]
    all_q = [h["text"] for h in hops] + [q["text"] for q in queries]
    per_q_spans = [spans_of(t) for t in all_q]
    for sp in per_q_spans:
        for s_ in sp:
            if s_ not in seen_sp:
                seen_sp.add(s_); span_texts.append(s_)
    S_emb = embed(span_texts)
    np.savez(cache, E=E, span_texts=np.array(span_texts, dtype=object),
             S_emb=S_emb)
name_i = {n: i for i, n in enumerate(names)}
name_i_tmp = name_i
span_i = {t: i for i, t in enumerate(span_texts)}

# participation vector: normalized counts over (relation, role) — 2R dims
R = len(RELS)
part = np.zeros((len(names), 2 * R), np.float32)
ridx = {r: i for i, r in enumerate(RELS)}
for f in facts:
    part[name_i_tmp[f["subject"]], ridx[f["relation"]]] += 1
    if f["object"] in name_i_tmp:
        part[name_i_tmp[f["object"]], R + ridx[f["relation"]]] += 1
P_name = part / (np.linalg.norm(part, axis=1, keepdims=True) + 1e-12)
K = 2 * R                                  # profile dimensionality
# answer prototypes now live over participation clusters: k-means on P_name
from codec.evals.anchors import fit_anchors
KC = 8
PC = unit(fit_anchors(P_name, KC))

# ---- relation entries: signatures + operators + prototypes ----
seen_q = [i for i, q in enumerate(queries) if q["kind"] == "single"
          and q["phrasing_idx"] not in HELD]
rel_entry = {}
for r in RELS:
    fs = [f for f in facts if f["relation"] == r]
    dom = np.mean([P_name[name_i[f["subject"]]] for f in fs], 0)
    rng_ = np.mean([P_name[name_i[f["object"]]] for f in fs], 0)
    tr = [i for i in seen_q if queries[i]["relation"] == r][:300]
    proto = unit(Zq[tr].mean(0))
    t_r = fit_translation(Zq[tr], np.stack([Zf[queries[i]["fact_idx"]] for i in tr]))
    rel_entry[r] = {"dom": dom, "rng": rng_, "proto": proto, "t": t_r}

# answer prototypes per participation-cluster
ans_proto = np.zeros((KC, Zq.shape[1]), np.float32)
cnt = np.zeros(KC)
clus_of = {}
for n, i in name_i.items():
    clus_of[n] = int(np.argmax(P_name[i] @ PC.T))
for i in seen_q:
    obj = facts[queries[i]["fact_idx"]]["object"]
    c = clus_of[obj]
    ans_proto[c] += Zq[i]; cnt[c] += 1
for c in range(KC):
    if cnt[c]: ans_proto[c] = unit(ans_proto[c])
# range profile of a relation in cluster space, for the answer term
def rng_cluster_prof(r):
    fs = [f for f in facts if f["relation"] == r and f["object"] in clus_of]
    v = np.zeros(KC)
    for f in fs: v[clus_of[f["object"]]] += 1
    return v / (v.sum() + 1e-12)
rng_cprof = {}

def cosd(a, b):
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))

def plan(text, q_emb, subject):
    doc = nlp(text)
    ents = {t.text for t in doc if t.pos_ == "PROPN"}
    sp = []
    for ch in doc.noun_chunks:
        t = " ".join(w.text for w in ch if w.text not in ents
                     and w.pos_ != "PROPN" and not w.is_stop)
        if len(t) > 2 and t in span_i: sp.append(t)
    sp += [t.lemma_ for t in doc if t.pos_ == "VERB" and not t.is_stop
           and t.lemma_ in span_i]
    det = {}
    for s_ in sp[:5]:
        v = S_emb[span_i[s_]]
        raw = np.array([float(v @ rel_entry[r]["proto"]) for r in RELS])
        post = np.exp((raw - raw.max()) * 24); post /= post.sum()
        for j, r in enumerate(RELS):
            det[r] = max(det.get(r, 0.0), float(post[j]))
    cand = sorted(det, key=det.get, reverse=True)[:4]
    subj_p = P_name[name_i[subject]] if subject in name_i else None
    if subj_p is None: return None
    aprof = np.array([float(q_emb @ ans_proto[c]) if cnt[c] else -1
                      for c in range(KC)])
    best, best_s = None, -1e9
    for k in range(1, 4):
        for perm in permutations(cand, k):
            feas = cosd(subj_p, rel_entry[perm[0]]["dom"])
            for a, b in zip(perm, perm[1:]):
                feas = min(feas, cosd(rel_entry[a]["rng"], rel_entry[b]["dom"]))
            if feas < 0.35:
                continue
            r_last = perm[-1]
            if r_last not in rng_cprof:
                rng_cprof[r_last] = rng_cluster_prof(r_last)
            rp = rng_cprof[r_last]
            ans = float(rp @ aprof / (np.linalg.norm(rp)
                        * np.linalg.norm(aprof) + 1e-12))
            s_ = sum(det[r] for r in perm) + 0.5 * ans - 0.05 * k
            if s_ > best_s:
                best_s, best = s_, list(perm)
    return best

store = MemoryStore()
for f, zf in zip(facts, Zf):
    store.add(zf, f["entities"] + f["numbers"], f["text"])
env = HopEnv(store, RELS, {r: rel_entry[r]["t"] for r in RELS})

def qids_of(text):
    doc = nlp(text)
    return id_tokens([t.text.rstrip("'s") if t.text.endswith("'s") else t.text
                      for t in doc if t.pos_ == "PROPN"]
                     + [t.text for t in doc if t.like_num])

def walk(q_z, q_ids, chain):
    """Channel-separated walk (replaces the D30 oracle walk, gold-chain exec
    0.93-1.00 vs 0.0-0.76): the dense query per hop is the relation PROTOTYPE
    + operator — type-level only, because the question gist encodes the LAST
    hop's relation and derails intermediate hops (measured: all loc_cap_pop
    walks grabbed the subject's population fact at hop 1). The entity rides
    the id channel; the hand-off mask is ids(cur) - ids(handed in) — subtract
    the subject side only, NOT all seen ids, so revisit compositions where
    the answer entity already appears in the question keep their hand-off."""
    env.reset(q_z, q_ids)
    hand = q_ids
    for k, rel in enumerate(chain):
        z = unit(rel_entry[rel]["proto"] + rel_entry[rel]["t"])
        r = store.query(z, hand or None, k=2, id_weight=1.0,
                        exclude=env.visited if k else None)
        env.cur = r[0][0]
        env.visited.add(r[0][0])
        cov = len(hand & store.ids[env.cur]) / max(len(hand), 1)
        if k == 0 and cov < 0.34:
            return None
        hand = store.ids[env.cur] - hand
    return env.cur

res, chain_ok = {}, {}
for kind in sorted({h["kind"] for h in hops}):
    cases = [(h, Zh[i]) for i, h in enumerate(hops) if h["kind"] == kind]
    hit = pok = 0
    for h, zq in cases:
        p = plan(h["text"], zq, h["subject"])
        pok += p == h["chain"]
        if p:
            hit += walk(zq, qids_of(h["text"]), p) == h["answer_fact"]
    res[kind], chain_ok[kind] = hit / len(cases), pok / len(cases)
    tag = " [HOLDOUT]" if kind in world["holdout_compositions"] else ""
    print(f"[soft {kind:>12}] chain={pok/len(cases):.3f} "
          f"P@1={hit/len(cases):.3f} (n={len(cases)}){tag}", flush=True)

(ROOT / "results" / "soft_planner_j3.json").write_text(json.dumps(
    {"generated_at": datetime.now(timezone.utc).isoformat(),
     "end_to_end": res, "chain_correct": chain_ok, "K": K,
     "hand_schema_reference": {"big_pop": 0.553, "cap_mayor": 0.353,
                                "hq_loc_cap": 0.042}}, indent=2))
print("[done] results/soft_planner_j3.json")
