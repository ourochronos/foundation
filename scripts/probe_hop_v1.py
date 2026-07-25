"""Can anything LATENT close the 2-hop gap? (D26 revisit, reasoner arc expt 1)

D26: constant-translation hops die (0.062 even with perfect intermediate
grounding) because hop displacements are entity-conditional. Three challengers
against that floor, all text-free between hops:

  B   constant t_hop (positive control — must reproduce ~0.06)
  B'  ridge LINEAR hop W·z(fact1): input-dependent by construction — if
      entity content is linearly routable to the answer address, W finds it
  D   triple-coherent hop: gist moves by the MEAN hop operator, and the
      IDENTITY SET hands off symbolically (fact1.ids minus the query's own
      ids) into retrieval rescoring. No codec pass, no text — pure store
      arithmetic on both channels. The hop D21's conflict result demands.

Plus the D24 bridge (revised D25 prediction): paraphrase retrieval under
query-latent noise — identity rescoring should activate when the gist
degrades, which scale alone did not produce.

Usage: .venv/bin/python scripts/probe_hop_v1.py
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


def unit(X):
    return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)


def query_ids(text: str, nlp) -> set:
    doc = nlp(text)
    names = [t.text.rstrip("'s") if t.text.endswith("'s") else t.text
             for t in doc if t.pos_ == "PROPN"]
    nums = [t.text for t in doc if t.like_num]
    return id_tokens(names + nums)


def noise(Z, sigma, rng):
    u = rng.standard_normal(Z.shape)
    u = u / np.linalg.norm(u, axis=-1, keepdims=True)
    return unit(Z + sigma * u)


def main() -> None:
    world = json.loads((ROOT / "data" / "closed_world_v1.json").read_text())
    facts, queries, hops = world["facts"], world["queries"], world["hops"]

    from codec.encode import M3Encoder
    from codec.role_bits import _nlp
    enc, nlp = M3Encoder(), _nlp()
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))

    def embed(texts):
        d, _ = enc.encode(texts, sparse=False)
        return unit(W.apply(d, whitener))

    cache = ROOT / "results" / "closed_world_v1_emb.npz"
    if cache.exists():
        z = np.load(cache)
        Zf, Zq, Zh = z["Zf"], z["Zq"], z["Zh"]
        print(f"[cache] embeddings reused ({len(Zf)}/{len(Zq)}/{len(Zh)})")
    else:
        Zf = embed([f["text"] for f in facts])
        Zq = embed([q["text"] for q in queries])
        Zh = embed([h["text"] for h in hops])
        np.savez(cache, Zf=Zf, Zq=Zq, Zh=Zh)
    qids = [query_ids(q["text"], nlp) for q in queries]
    hids = [query_ids(h["text"], nlp) for h in hops]

    store = MemoryStore()
    for f, z in zip(facts, Zf):
        store.add(z, f["entities"] + f["numbers"], f["text"])

    def top1(z, ids=None, w=0.5, demote=None, exclude=None):
        return store.query(z, ids, k=1, id_weight=w if (ids or demote) else 0.0,
                           demote_ids=demote, exclude=exclude)[0]

    # t_cap from relational queries (as in D25/D26)
    rel_q = [i for i, q in enumerate(queries) if q["kind"] == "relational"
             and q["relation"] == "capital_of"]
    m = hash_test_mask([queries[i]["text"] for i in rel_q], frac=0.7)
    tr = [i for i, t in zip(rel_q, m) if not t]
    t_cap = fit_translation(Zq[tr],
                            np.stack([Zf[queries[i]["fact_idx"]] for i in tr]))

    # hop-pair bank on countries with NO hop test case — all 600 this time
    test_countries = {h["country"] for h in hops}
    pop_idx = {f["subject"]: i for i, f in enumerate(facts)
               if f["relation"] == "population_of"}
    pairs = [(i, pop_idx[f["object"]]) for i, f in enumerate(facts)
             if f["relation"] == "capital_of"
             and f["subject"] not in test_countries]
    Z1 = np.stack([Zf[i] for i, _ in pairs])
    Z2 = np.stack([Zf[j] for _, j in pairs])
    t_hop = fit_translation(Z1, Z2)
    print(f"[fit] t_cap on {len(tr)} query pairs; hop bank {len(pairs)} pairs")

    # ridge maps at several strengths (closed form, fit once each)
    ridges = {}
    d = Z1.shape[1]
    G = Z1.T @ Z1
    for alpha in (0.1, 1.0, 10.0):
        ridges[alpha] = np.linalg.solve(G + alpha * np.eye(d), Z1.T @ Z2).T

    hit = {"B": 0, "D@0.5": 0, "D@1.0": 0}
    hit.update({f"B'a={a}": 0 for a in ridges})
    hop1_ok = 0
    for h, zq, hq in zip(hops, Zh, hids):
        r1 = top1(zq + t_cap)
        hop1_ok += r1[0] == h["hop1_fact"]
        z1 = store.Z[r1[0]]
        hit["B"] += top1(z1 + t_hop)[0] == h["hop2_fact"]
        for a, Wr in ridges.items():
            hit[f"B'a={a}"] += top1(unit(Wr @ z1))[0] == h["hop2_fact"]
        hand = store.ids[r1[0]] - hq          # fact1 identities minus query's
        for w in (0.5, 1.0):
            # promote the handed-off entity, demote the previous subject,
            # never revisit the source node
            hit[f"D@{w}"] += top1(z1 + t_hop, hand, w=w, demote=hq,
                                  exclude={r1[0]})[0] == h["hop2_fact"]

    n = len(hops)
    print(f"[hop1] {hop1_ok / n:.3f}")
    for k in ("B", "B'a=0.1", "B'a=1.0", "B'a=10.0", "D@0.5", "D@1.0"):
        print(f"[{k:>8}] 2-hop P@1 = {hit[k] / n:.3f}")

    # ---- D24 bridge: paraphrase retrieval under query noise ----
    rng = np.random.default_rng(0)
    para = [i for i, q in enumerate(queries) if q["kind"] == "paraphrase"]
    noise_rows = []
    for sg in (0.0, 0.5, 1.0, 1.5):
        Zn = noise(Zq, sg, rng) if sg else Zq
        g = np.mean([top1(Zn[i])[0] == queries[i]["fact_idx"] for i in para])
        gi = np.mean([top1(Zn[i], qids[i])[0] == queries[i]["fact_idx"]
                      for i in para])
        lat = 1.0 / np.sqrt(1.0 + sg * sg)
        noise_rows.append({"sigma": sg, "latent_cos": lat,
                           "gist": float(g), "with_identity": float(gi)})
        print(f"[noise σ={sg} lat_cos={lat:.2f}] gist={g:.3f} +identity={gi:.3f} "
              f"(Δ={gi - g:+.3f})")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "hop1": hop1_ok / n,
           "two_hop": {k: v / n for k, v in hit.items()},
           "n_hops": n, "n_hop_pairs": len(pairs),
           "noisy_paraphrase": noise_rows}
    (ROOT / "results" / "hop_v1.json").write_text(json.dumps(out, indent=2))
    print("[done] results/hop_v1.json")


if __name__ == "__main__":
    main()
