"""v0.6 pipeline as reusable pieces (J4/K4/K5 need it parameterized by world).

Faithful port of probe_soft_planner.py's artifact construction +
train_reasoner_v06.py's heads/planner/eval — one implementation, many worlds.
Store-side artifacts (participation types, relation entries, operators,
range-cluster profiles) are all closed-form recomputable; the learned heads
(detection, answer-type) read ONLY the question embedding. `PC` (the
participation-cluster basis) can be passed in frozen — that is J4's dial:
grow everything else, keep the basis the heads were trained against.
"""

from __future__ import annotations

import sys
from itertools import permutations, product
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec import whiten as W                                     # noqa: E402
from codec.evals.anchors import fit_anchors                       # noqa: E402
from codec.memory_store import MemoryStore, fit_translation, id_tokens  # noqa: E402
from codec.walker import ChannelWalker                            # noqa: E402

KC = 8


def unit(X):
    return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)


_ENC = None


def embed_texts(texts, batch=256):
    global _ENC
    if _ENC is None:
        from codec.encode import M3Encoder
        _ENC = (M3Encoder(), W.load(str(ROOT / "results" / "whiten_v0.npz")))
    enc, wh = _ENC
    d, _ = enc.encode(texts, sparse=False)
    return unit(W.apply(d, wh))


def load_or_build_emb(world, cache: Path):
    if cache.exists():
        z = np.load(cache)
        return z["Zf"], z["Zq"], z["Zh"]
    Zf = embed_texts([f["text"] for f in world["facts"]])
    Zq = embed_texts([q["text"] for q in world["queries"]])
    Zh = embed_texts([h["text"] for h in world["hops"]])
    np.savez(cache, Zf=Zf, Zq=Zq, Zh=Zh)
    return Zf, Zq, Zh


def build_artifacts(world, Zf, Zq, PC=None):
    """Store + all closed-form artifacts. PC=None fits a fresh cluster
    basis; passing one keeps it frozen (heads stay aligned)."""
    facts, queries = world["facts"], world["queries"]
    HELD = set(world["held_out_phrasings"])
    RELS = sorted({f["relation"] for f in facts})
    R = len(RELS)
    ridx = {r: i for i, r in enumerate(RELS)}

    names = sorted({f["subject"] for f in facts}
                   | {f["object"] for f in facts})
    name_i = {n: i for i, n in enumerate(names)}
    part = np.zeros((len(names), 2 * R), np.float32)
    for f in facts:
        part[name_i[f["subject"]], ridx[f["relation"]]] += 1
        if f["object"] in name_i:
            part[name_i[f["object"]], R + ridx[f["relation"]]] += 1
    P_name = part / (np.linalg.norm(part, axis=1, keepdims=True) + 1e-12)
    if PC is None:
        PC = unit(fit_anchors(P_name, KC))
    clus_of = {n: int(np.argmax(P_name[i] @ PC.T))
               for n, i in name_i.items()}

    seen_q = [i for i, q in enumerate(queries) if q["kind"] == "single"
              and q["phrasing_idx"] not in HELD]
    rel_entry = {}
    for r in RELS:
        fs = [f for f in facts if f["relation"] == r]
        dom = np.mean([P_name[name_i[f["subject"]]] for f in fs], 0)
        rng_ = np.mean([P_name[name_i[f["object"]]] for f in fs], 0)
        tr = [i for i in seen_q if queries[i]["relation"] == r][:300]
        proto = unit(Zq[tr].mean(0))
        t_r = fit_translation(Zq[tr],
                              np.stack([Zf[queries[i]["fact_idx"]]
                                        for i in tr]))
        rel_entry[r] = {"dom": dom, "rng": rng_, "proto": proto, "t": t_r}

    rng_cprof = {}
    for r in RELS:
        fs = [f for f in facts if f["relation"] == r
              and f["object"] in clus_of]
        v = np.zeros(KC)
        for f in fs:
            v[clus_of[f["object"]]] += 1
        rng_cprof[r] = v / (v.sum() + 1e-12)

    store = MemoryStore()
    for f, zf in zip(facts, Zf):
        store.add(zf, f["entities"] + f["numbers"], f["text"])
    walker = ChannelWalker(store,
                           protos={r: rel_entry[r]["proto"] for r in RELS},
                           ops={r: rel_entry[r]["t"] for r in RELS})
    return dict(RELS=RELS, name_i=name_i, P_name=P_name, PC=PC,
                clus_of=clus_of, rel_entry=rel_entry, rng_cprof=rng_cprof,
                store=store, walker=walker, seen_q=seen_q, HELD=HELD)


def cosd(a, b):
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


def train_heads(world, Zq, Zh, seed=0, epochs=60):
    """Detection (multi-label relations) + answer-type (participation
    cluster) heads. Returns (det_head, ans_head, hop_eval_ids).
    NOTE: labels for ans_head need clus_of — pass artifacts via closure-free
    second call to be explicit."""
    raise NotImplementedError("use train_heads_with(art, ...)")


def train_heads_with(art, world, Zq, Zh, seed=0, epochs=60):
    import torch
    from torch import nn
    torch.manual_seed(seed)
    facts, queries, hops = world["facts"], world["queries"], world["hops"]
    RELS, HELD = art["RELS"], art["HELD"]
    HOLD = set(world["holdout_compositions"])
    R = len(RELS)

    Xs, Ys = [], []
    for i, q in enumerate(queries):
        if q["kind"] == "single" and q["phrasing_idx"] not in HELD:
            y = np.zeros(R, np.float32)
            y[RELS.index(q["relation"])] = 1.0
            Xs.append(Zq[i]); Ys.append(y)
    hop_rows = []
    for i, h in enumerate(hops):
        if h["kind"] not in HOLD:
            y = np.zeros(R, np.float32)
            for r in h["chain"]:
                y[RELS.index(r)] = 1.0
            hop_rows.append((i, y))
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(hop_rows))
    cut = int(0.8 * len(hop_rows))
    for j in perm[:cut]:
        i, y = hop_rows[j]
        Xs.append(Zh[i]); Ys.append(y)
    hop_eval_ids = {hop_rows[j][0] for j in perm[cut:]}
    X = torch.tensor(np.stack(Xs)); Y = torch.tensor(np.stack(Ys))

    det_head = nn.Sequential(nn.Linear(1024, 256), nn.GELU(),
                             nn.Linear(256, R))
    opt = torch.optim.AdamW(det_head.parameters(), lr=1e-3, weight_decay=1e-4)
    lossf = nn.BCEWithLogitsLoss()
    for ep in range(epochs):
        for b in torch.randperm(len(X)).split(512):
            opt.zero_grad()
            lossf(det_head(X[b]), Y[b]).backward()
            opt.step()

    clus_of = art["clus_of"]
    Xa, Ya = [], []
    for i, q in enumerate(queries):
        if q["kind"] == "single" and q["phrasing_idx"] not in HELD:
            obj = facts[q["fact_idx"]]["object"]
            if obj in clus_of:
                Xa.append(Zq[i]); Ya.append(clus_of[obj])
    for j in perm[:cut]:
        i, _ = hop_rows[j]
        obj = facts[hops[i]["answer_fact"]]["object"]
        if obj in clus_of:
            Xa.append(Zh[i]); Ya.append(clus_of[obj])
    Xa_t = torch.tensor(np.stack(Xa)); Ya_t = torch.tensor(Ya)
    ans_head = nn.Sequential(nn.Linear(1024, 128), nn.GELU(),
                             nn.Linear(128, KC))
    opta = torch.optim.AdamW(ans_head.parameters(), lr=1e-3)
    ce = torch.nn.CrossEntropyLoss()
    for ep in range(40):
        for b in torch.randperm(len(Xa_t)).split(512):
            opta.zero_grad()
            ce(ans_head(Xa_t[b]), Ya_t[b]).backward()
            opta.step()
    return det_head, ans_head, hop_eval_ids


def make_planner(det_head, ans_head, art, det_floor=0.2, req_thr=0.5,
                 feas_thr=0.35, max_k=3, cand_k=4, link_ok=None,
                 entry_ok=None, arity_head=None, path_ok=None,
                 cand_from_arity=False):
    """v0.6 final planner: PoE (detection log-odds + answer-cluster
    log-mass), participation feasibility gate, required+restricted
    detected relations (D44).

    `arity_head` (D111) predicts the path LENGTH. Without it the candidate
    paths are `permutations` over distinct relations, which cannot express
    a repeated relation at all — and on the real store `A -> A` is 79% of
    the 2-hop shapes, so that gap produced wrong answers at 0.925 rather
    than abstentions. With it, the predicted length is fixed first and
    repeats become expressible. Default None preserves the exact prior
    behaviour, so the synthetic-world results are untouched.
    """
    import torch
    RELS, rel_entry = art["RELS"], art["rel_entry"]
    P_name, name_i, rng_cprof = art["P_name"], art["name_i"], art["rng_cprof"]

    def plan(q_emb, subject):
        with torch.no_grad():
            pv = torch.sigmoid(det_head(torch.tensor(q_emb)[None]))[0].numpy()
            ap = torch.softmax(ans_head(torch.tensor(q_emb)[None]),
                               -1)[0].numpy()
            if arity_head is None:
                ks = range(1, max_k + 1)
            else:
                k_hat = int(torch.argmax(
                    arity_head(torch.tensor(q_emb)[None])[0])) + 1
                ks = [k_hat]
        det = {r: float(pv[j]) for j, r in enumerate(RELS)}
        order = sorted(det, key=det.get, reverse=True)
        if cand_from_arity and arity_head is not None:
            # k relations for a k-hop path; every one of them must be used,
            # so the second relation cannot be dropped for being under a
            # threshold it was never calibrated to clear.
            cand = order[:max(ks)]
            req = set()
        else:
            cand = [r for r in order[:cand_k] if det[r] >= det_floor]
            req = {r for r in RELS if det[r] > req_thr}
        if subject not in name_i:
            return None
        subj_p = P_name[name_i[subject]]
        best, best_s = None, -1e9
        def paths(k):
            # product() takes `repeat` as a keyword; permutations() takes
            # the length positionally. Repeats are only allowed when the
            # arity head has fixed the length.
            return (product(cand, repeat=k) if arity_head is not None
                    else permutations(cand, k))
        for k in ks:
            for pm in paths(k):
                if path_ok is not None:
                    if not req <= set(pm) or not path_ok(subject, pm):
                        continue
                elif link_ok is not None:
                    if (entry_ok is not None
                            and not entry_ok(subject, pm[0])) or \
                            any(not link_ok(a, b)
                                for a, b in zip(pm, pm[1:])) or \
                            not req <= set(pm):
                        continue
                else:
                    feas = cosd(subj_p, rel_entry[pm[0]]["dom"])
                    for a, b in zip(pm, pm[1:]):
                        feas = min(feas, cosd(rel_entry[a]["rng"],
                                              rel_entry[b]["dom"]))
                    if feas < feas_thr or not req <= set(pm):
                        continue
                ev = sum(np.log(max(det[r], 1e-4)
                                / (1 - min(det[r], 1 - 1e-4))) for r in pm)
                ans = float(ap @ rng_cprof[pm[-1]])
                s_ = ev + np.log(max(ans, 1e-4))
                if s_ > best_s:
                    best_s, best = s_, list(pm)
        return best
    return plan


_NLP = None


def qids_of(text):
    global _NLP
    if _NLP is None:
        from codec.role_bits import _nlp
        _NLP = _nlp()
    doc = _NLP(text)
    return id_tokens([t.text.rstrip("'s") if t.text.endswith("'s")
                      else t.text for t in doc if t.pos_ == "PROPN"]
                     + [t.text for t in doc if t.like_num])


def evaluate(world, Zq, Zh, art, plan, hop_eval_ids=None, fact_offset=0,
             singles_n=400, na_n=200, tag=""):
    """Eval battery. fact_offset shifts this world's fact indices into a
    union store (J4)."""
    facts, queries, hops = world["facts"], world["queries"], world["hops"]
    HOLD = set(world["holdout_compositions"])
    HELD = set(world["held_out_phrasings"])
    walker, name_i = art["walker"], art["name_i"]
    res = {}
    for kind in sorted({h["kind"] for h in hops}):
        if hop_eval_ids is None or kind in HOLD:
            cases = [(h, Zh[i]) for i, h in enumerate(hops)
                     if h["kind"] == kind]
        else:
            cases = [(h, Zh[i]) for i, h in enumerate(hops)
                     if h["kind"] == kind and i in hop_eval_ids]
        if not cases:
            continue
        hit = pok = 0
        for h, zq in cases:
            p = plan(zq, h["subject"])
            pok += p == h["chain"]
            if p and not walker.abstain_hop1(qids_of(h["text"]), p[0]):
                hit += (walker.walk(qids_of(h["text"]), p)
                        == h["answer_fact"] + fact_offset)
        res[kind] = {"chain": pok / len(cases), "p1": hit / len(cases),
                     "n": len(cases)}
        flag = " [HOLDOUT]" if kind in HOLD else ""
        print(f"[{tag}{kind:>12}] chain={pok/len(cases):.3f} "
              f"P@1={hit/len(cases):.3f} (n={len(cases)}){flag}", flush=True)

    singles = [i for i, q in enumerate(queries) if q["kind"] == "single"
               and q["phrasing_idx"] in HELD][:singles_n]
    hit = 0
    for i in singles:
        q = queries[i]
        p = plan(Zq[i], facts[q["fact_idx"]]["subject"])
        if p and not walker.abstain_hop1(qids_of(q["text"]), p[0]):
            hit += (walker.walk(qids_of(q["text"]), p)
                    == q["fact_idx"] + fact_offset)
    res["single"] = {"p1": hit / len(singles), "n": len(singles)}
    print(f"[{tag}      single] P@1={hit/len(singles):.3f} "
          f"(n={len(singles)})", flush=True)

    na = [i for i, q in enumerate(queries) if q["kind"] == "no_answer"][:na_n]
    abst = 0
    for i in na:
        q = queries[i]
        subj = next((n for n in name_i if n in q["text"]), "")
        p = plan(Zq[i], subj)
        abst += (p is None) or walker.abstain_hop1(qids_of(q["text"]), p[0])
    res["no_answer"] = {"abstain": abst / len(na), "n": len(na)}
    print(f"[{tag}   no_answer] abstain={abst/len(na):.3f} (n={len(na)})",
          flush=True)
    return res
