"""Phase-2 memory gate, part 1: retrieval precision on closed-world facts.

Three questions, per docs/04-memory.md and the roadmap gate:
  1 PARAPHRASE ADDRESSING — query wordings share no template with stored
    facts; P@1 among 360 near-duplicate facts. Ablation: gist-only vs
    gist + identity rescoring (the D3 claim that identity discrimination is
    the store's precision mechanism).
  2 RELATIONAL ADDRESSING — one algebra, three uses (T2): fit a TRANSLATION
    t_rel from (question-latent -> fact-latent) on 30% of each relation's
    queries; test P@1 on the held-out 70% with query' = z_q + t_rel.
    Compared against the same queries without the operator.
  3 KNOWLEDGE EDIT — write superseding facts with a shadow policy (new entry
    shadows its own top-scoring live match); the 20 edited capitals must
    resolve to the NEW object afterward, and the other 40 stay intact.

Usage: .venv/bin/python scripts/probe_memory_v0.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec import whiten as W                                  # noqa: E402
from codec.memory_store import MemoryStore, fit_translation, id_tokens  # noqa: E402
from codec.structure_channel import hash_test_mask             # noqa: E402

ID_WEIGHT = 0.5
SHADOW_MIN = 0.88          # combined score a new entry must reach to shadow
                           # (measured: correct supersession targets score
                           #  0.91-1.06; the 1.10 first guess never fired)


def unit(X):
    return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)


def query_ids(text: str, nlp) -> set:
    doc = nlp(text)
    names = [t.text.rstrip("'s") if t.text.endswith("'s") else t.text
             for t in doc if t.pos_ == "PROPN"]
    nums = [t.text for t in doc if t.like_num]
    return id_tokens(names + nums)


def main() -> None:
    world = json.loads((ROOT / "data" / "closed_world.json").read_text())
    facts, queries, edits = world["facts"], world["queries"], world["edits"]

    from codec.encode import M3Encoder
    from codec.role_bits import _nlp
    enc, nlp = M3Encoder(), _nlp()
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))

    def embed(texts):
        d, _ = enc.encode(texts, sparse=False)
        return unit(W.apply(d, whitener))

    Zf = embed([f["text"] for f in facts])
    Zq = embed([q["text"] for q in queries])
    Ze = embed([e["text"] for e in edits])
    qids = [query_ids(q["text"], nlp) for q in queries]

    store = MemoryStore()
    for f, z in zip(facts, Zf):
        store.add(z, f["entities"] + f["numbers"], f["text"])

    # ---- 1: paraphrase addressing ----
    para = [i for i, q in enumerate(queries) if q["kind"] == "paraphrase"]
    def p_at_1(idxs, Z, use_ids, t_by_rel=None):
        hits = 0
        for i in idxs:
            z = Z[i]
            if t_by_rel is not None:
                z = z + t_by_rel[queries[i]["relation"]]
            r = store.query(z, qids[i] if use_ids else None,
                            k=1, id_weight=ID_WEIGHT if use_ids else 0.0)
            hits += int(r[0][0] == queries[i]["fact_idx"])
        return hits / len(idxs)

    p_gist = p_at_1(para, Zq, False)
    p_full = p_at_1(para, Zq, True)
    print(f"[1 paraphrase] P@1 gist-only={p_gist:.3f}  +identity={p_full:.3f} "
          f"(n={len(para)}, {len(facts)} candidates)")

    # ---- 2: relational addressing (train/test split per relation) ----
    rel_q = [i for i, q in enumerate(queries) if q["kind"] == "relational"]
    m = hash_test_mask([queries[i]["text"] for i in rel_q], frac=0.7)
    train = [i for i, t in zip(rel_q, m) if not t]
    test = [i for i, t in zip(rel_q, m) if t]
    t_by_rel = {}
    for rel in {q["relation"] for q in queries}:
        tr = [i for i in train if queries[i]["relation"] == rel]
        t_by_rel[rel] = fit_translation(
            Zq[tr], np.stack([Zf[queries[i]["fact_idx"]] for i in tr]))
    r_raw = p_at_1(test, Zq, False)
    r_tr = p_at_1(test, Zq, False, t_by_rel)
    r_tr_id = p_at_1(test, Zq, True, t_by_rel)
    print(f"[2 relational] P@1 raw={r_raw:.3f}  +translation={r_tr:.3f}  "
          f"+translation+identity={r_tr_id:.3f} (n={len(test)}, "
          f"t fit on {len(train)})")

    # ---- 3: knowledge edit ----
    # pre-edit: the paraphrase query for each edited fact resolves to the old
    edit_fis = [e["fact_idx"] for e in edits]
    eq = [i for i in para if queries[i]["fact_idx"] in edit_fis]
    control = [i for i in para if queries[i]["fact_idx"] not in edit_fis][:60]
    pre = p_at_1(eq, Zq, True)
    for e, z in zip(edits, Ze):
        ids = e["entities"] + e["numbers"]
        top = store.query(z, id_tokens(ids), k=1, id_weight=ID_WEIGHT)
        new_idx = store.add(z, ids, e["text"])
        if top and top[0][1] >= SHADOW_MIN:
            store.supersede(top[0][0], new_idx)
    post_hits = 0
    by_fi = {e["fact_idx"]: (i, e) for i, e in enumerate(edits)}
    for i in eq:
        r = store.query(Zq[i], qids[i], k=1, id_weight=ID_WEIGHT)
        _, e = by_fi[queries[i]["fact_idx"]]
        post_hits += int(e["new_object"].split()[0] in r[0][2])
    post = post_hits / len(eq)
    ctrl = p_at_1(control, Zq, True)
    print(f"[3 edit] pre-edit P@1 (old fact)={pre:.3f} | post-edit resolves to "
          f"NEW object={post:.3f} (n={len(eq)}) | untouched controls={ctrl:.3f}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "n_facts": len(facts),
           "paraphrase": {"gist_only": p_gist, "with_identity": p_full,
                          "n": len(para)},
           "relational": {"raw": r_raw, "with_translation": r_tr,
                          "with_translation_and_identity": r_tr_id,
                          "n_test": len(test), "n_train": len(train)},
           "edit": {"pre": pre, "post_new_object": post,
                    "controls_after_edits": ctrl, "n": len(eq)},
           "id_weight": ID_WEIGHT, "shadow_min": SHADOW_MIN}
    (ROOT / "results" / "memory_v0.json").write_text(json.dumps(out, indent=2))
    print("[done] results/memory_v0.json")


if __name__ == "__main__":
    main()
