"""Memory at scale (9.9k facts) + 2-hop composition — the reasoner on-ramp.

Part 1 — the D25 gates at 27x the entry count. Prediction under test (D25
finding 2): identity rescoring was a no-op at 360 entries and should ACTIVATE
here, where the gist has 27x the near-duplicates to confuse.

Part 2 — 2-hop chains ("population of the capital of X"), three ways:
  A composed operators, no grounding:  z_q + t_cap + t_hop -> retrieve once
  B latent chain with retrieval snap:  z_q + t_cap -> retrieve fact1 ->
       z(fact1) + t_hop -> retrieve answer   (no text in the loop)
  C codec loop: hop1 as in B, then READ the capital out of fact1's text,
       compose a fresh hop-2 query, encode, + t_pop -> retrieve
A-vs-B isolates what intermediate retrieval (snapping to a real entry)
corrects; B-vs-C is pure-latent vs symbolic hand-off — the Coconut question
at this program's scale. All operators are closed-form translations fit on
held-out-disjoint countries. The hand-coded chain is the BASELINE a trained
reasoner must beat.

Usage: .venv/bin/python scripts/probe_memory_v1.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec import whiten as W                                    # noqa: E402
from codec.memory_store import MemoryStore, fit_translation, id_tokens  # noqa: E402
from codec.structure_channel import hash_test_mask               # noqa: E402

ID_WEIGHT = 0.5
SHADOW_MIN = 0.88


def unit(X):
    return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)


def query_ids(text: str, nlp) -> set:
    doc = nlp(text)
    names = [t.text.rstrip("'s") if t.text.endswith("'s") else t.text
             for t in doc if t.pos_ == "PROPN"]
    nums = [t.text for t in doc if t.like_num]
    return id_tokens(names + nums)


def main() -> None:
    world = json.loads((ROOT / "data" / "closed_world_v1.json").read_text())
    facts, queries = world["facts"], world["queries"]
    edits, hops = world["edits"], world["hops"]

    from codec.encode import M3Encoder
    from codec.role_bits import _nlp
    enc, nlp = M3Encoder(), _nlp()
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))

    def embed(texts):
        d, _ = enc.encode(texts, sparse=False)
        return unit(W.apply(d, whitener))

    print(f"[encode] {len(facts)} facts + {len(queries)} queries "
          f"+ {len(edits)} edits + {len(hops)} hops", flush=True)
    Zf = embed([f["text"] for f in facts])
    Zq = embed([q["text"] for q in queries])
    Ze = embed([e["text"] for e in edits])
    Zh = embed([h["text"] for h in hops])
    qids = [query_ids(q["text"], nlp) for q in queries]

    store = MemoryStore()
    for f, z in zip(facts, Zf):
        store.add(z, f["entities"] + f["numbers"], f["text"])

    def top1(z, ids=None):
        return store.query(z, ids, k=1,
                           id_weight=ID_WEIGHT if ids else 0.0)[0]

    # ---------- part 1: the D25 gates at scale ----------
    para = [i for i, q in enumerate(queries) if q["kind"] == "paraphrase"]
    rel_q = [i for i, q in enumerate(queries) if q["kind"] == "relational"]

    def p_at_1(idxs, use_ids, t_by_rel=None):
        hits = 0
        for i in idxs:
            z = Zq[i]
            if t_by_rel is not None:
                z = z + t_by_rel[queries[i]["relation"]]
            r = top1(z, qids[i] if use_ids else None)
            hits += int(r[0] == queries[i]["fact_idx"])
        return hits / len(idxs)

    p_g, p_id = p_at_1(para, False), p_at_1(para, True)
    print(f"[1 paraphrase @9.9k] P@1 gist={p_g:.3f}  +identity={p_id:.3f} "
          f"(was 0.794/0.797 @360)")

    m = hash_test_mask([queries[i]["text"] for i in rel_q], frac=0.7)
    train = [i for i, t in zip(rel_q, m) if not t]
    test = [i for i, t in zip(rel_q, m) if t]
    t_by_rel = {}
    for rel in {q["relation"] for q in queries}:
        tr = [i for i in train if queries[i]["relation"] == rel]
        t_by_rel[rel] = fit_translation(
            Zq[tr], np.stack([Zf[queries[i]["fact_idx"]] for i in tr]))
    r_raw, r_tr = p_at_1(test, False), p_at_1(test, False, t_by_rel)
    r_tr_id = p_at_1(test, True, t_by_rel)
    print(f"[2 relational @9.9k] raw={r_raw:.3f}  +t={r_tr:.3f}  "
          f"+t+id={r_tr_id:.3f} (was 0.905/0.988/0.992 @360)")

    edit_fis = set(e["fact_idx"] for e in edits)
    eq = [i for i in para if queries[i]["fact_idx"] in edit_fis]
    pre = p_at_1(eq, True) if eq else float("nan")
    for e, z in zip(edits, Ze):
        ids = e["entities"] + e["numbers"]
        t = top1(z, id_tokens(ids))
        ni = store.add(z, ids, e["text"])
        if t[1] >= SHADOW_MIN:
            store.supersede(t[0], ni)
    by_fi = {e["fact_idx"]: e for e in edits}
    post = (np.mean([by_fi[queries[i]["fact_idx"]]["new_object"].split()[0]
                     in top1(Zq[i], qids[i])[2] for i in eq])
            if eq else float("nan"))
    print(f"[3 edit @9.9k] pre={pre:.3f} post-new={post:.3f} (n={len(eq)})")
    # hop tests use a FRESH facts-only store: the edit entries above both
    # index outside Zf and change capitals (corrupting hop ground truth)
    store = MemoryStore()
    for f, z in zip(facts, Zf):
        store.add(z, f["entities"] + f["numbers"], f["text"])

    # ---------- part 2: 2-hop composition ----------
    # t_cap: reuse the relational operator. t_hop: capital-fact -> population-
    # fact-of-that-capital, fit on countries with no hop test case.
    test_countries = {h["country"] for h in hops}
    fact_by_idx = facts
    pairs = []
    for i, f in enumerate(facts):
        if f["relation"] == "capital_of" and f["subject"] not in test_countries:
            cap = f["object"]
            j = next((k for k, g in enumerate(facts)
                      if g["relation"] == "population_of" and g["subject"] == cap),
                     None)
            if j is not None:
                pairs.append((i, j))
    pairs = pairs[:150]
    t_hop = fit_translation(np.stack([Zf[i] for i, _ in pairs]),
                            np.stack([Zf[j] for _, j in pairs]))
    t_cap, t_pop = t_by_rel["capital_of"], t_by_rel["population_of"]
    print(f"[hop setup] t_hop fit on {len(pairs)} disjoint countries")

    hitA = hitB = hitC = hop1_ok = 0
    hop2_texts, hop2_meta = [], []
    for h, zq in zip(hops, Zh):
        # A: composed operators, single retrieval
        rA = top1(zq + t_cap + t_hop)
        hitA += int(rA[0] == h["hop2_fact"])
        # B: retrieve intermediate, then latent hop
        r1 = top1(zq + t_cap)
        ok1 = r1[0] == h["hop1_fact"]
        hop1_ok += int(ok1)
        rB = top1(store.Z[r1[0]] + t_hop)
        hitB += int(rB[0] == h["hop2_fact"])
        # C: codec loop — read the capital out of fact1's TEXT
        cap_name = store.texts[r1[0]].rstrip(".").split(" is ")[-1]
        hop2_texts.append(f"Name the population of {cap_name}.")
        hop2_meta.append(h)
    Z2 = embed(hop2_texts)
    for h, z2, txt in zip(hop2_meta, Z2, hop2_texts):
        rC = top1(z2 + t_pop, query_ids(txt, nlp))
        hitC += int(rC[0] == h["hop2_fact"])

    n = len(hops)
    print(f"[hop1] intermediate retrieval P@1 = {hop1_ok / n:.3f}")
    print(f"[2-hop A composed-ops (no grounding)] P@1 = {hitA / n:.3f}")
    print(f"[2-hop B latent chain + retrieval snap] P@1 = {hitB / n:.3f}")
    print(f"[2-hop C codec loop (symbolic hand-off)] P@1 = {hitC / n:.3f}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "n_facts": len(facts),
           "paraphrase": {"gist_only": p_g, "with_identity": p_id},
           "relational": {"raw": r_raw, "with_translation": r_tr,
                          "with_translation_and_identity": r_tr_id},
           "edit": {"pre": float(pre), "post_new_object": float(post),
                    "n": len(eq)},
           "hops": {"n": n, "hop1_p1": hop1_ok / n,
                    "A_composed_ops": hitA / n,
                    "B_latent_chain_snap": hitB / n,
                    "C_codec_loop": hitC / n}}
    (ROOT / "results" / "memory_v1.json").write_text(json.dumps(out, indent=2))
    print("[done] results/memory_v1.json")


if __name__ == "__main__":
    main()
