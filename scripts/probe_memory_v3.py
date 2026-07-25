"""A1 judgment probe — does the memory stack survive de-templating?

Adversary predictions under test (07-phase3-plan.md, threats #1/#2/#9/#10):
  P1 relational addressing falls to 0.75-0.85 once operators must average
     over 8 phrasings and get tested on 4 NEVER-SEEN phrasings
  P2 hop P@1 falls well below 0.9 with template diversity + name collisions
  P3 the revisit composition (loc_big — answer may BE the source city)
     breaks hard `exclude`/`demote` walk semantics
  P4 identity-overlap stops being an oracle under collisions

Also measured: temporal distractors (dated capital pairs), no-answer score
separation (is abstention learnable from top-1 score?).

Operator fitting uses phrasings 0-7 and 30% of entities; ALL evaluation rows
report seen-phrasing vs HELD-OUT-phrasing (8-11) separately.

Usage: .venv/bin/python scripts/probe_memory_v3.py
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


def main() -> None:
    world = json.loads((ROOT / "data" / "closed_world_v3.json").read_text())
    facts, queries, hops = world["facts"], world["queries"], world["hops"]
    HELD = set(world["held_out_phrasings"])

    from codec.encode import M3Encoder
    from codec.role_bits import _nlp
    enc, nlp = M3Encoder(), _nlp()
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))

    def embed(texts):
        d, _ = enc.encode(texts, sparse=False)
        return unit(W.apply(d, whitener))

    cache = ROOT / "results" / "closed_world_v3_emb.npz"
    if cache.exists():
        z = np.load(cache)
        Zf, Zq, Zh = z["Zf"], z["Zq"], z["Zh"]
    else:
        print(f"[encode] {len(facts)}+{len(queries)}+{len(hops)}", flush=True)
        Zf = embed([f["text"] for f in facts])
        Zq = embed([q["text"] for q in queries])
        Zh = embed([h["text"] for h in hops])
        np.savez(cache, Zf=Zf, Zq=Zq, Zh=Zh)

    def qids_of(text):
        doc = nlp(text)
        return id_tokens([t.text.rstrip("'s") if t.text.endswith("'s") else t.text
                          for t in doc if t.pos_ == "PROPN"]
                         + [t.text for t in doc if t.like_num])

    store = MemoryStore()
    for f, zf in zip(facts, Zf):
        store.add(zf, f["entities"] + f["numbers"], f["text"])

    def top1(z, ids=None, w=0.5, demote=None, exclude=None):
        return store.query(z, ids, k=1, id_weight=w if (ids or demote) else 0.0,
                           demote_ids=demote, exclude=exclude)[0]

    ans = [i for i, q in enumerate(queries) if q["kind"] == "single"]
    qid_cache = {i: qids_of(queries[i]["text"]) for i in ans}

    # ---- 1: single-hop retrieval, seen vs held-out phrasings ----
    def p1(idxs, use_ids, t_by_rel=None):
        if not idxs:
            return float("nan")
        hit = 0
        for i in idxs:
            z = Zq[i]
            if t_by_rel is not None:
                z = z + t_by_rel[queries[i]["relation"]]
            r = top1(z, qid_cache[i] if use_ids else None)
            hit += r[0] == queries[i]["fact_idx"]
        return hit / len(idxs)

    seen = [i for i in ans if queries[i]["phrasing_idx"] not in HELD]
    held = [i for i in ans if queries[i]["phrasing_idx"] in HELD]
    print(f"[1 direct] seen-phrasing: gist={p1(seen, False):.3f} "
          f"+id={p1(seen, True):.3f} (n={len(seen)}) | HELD-phrasing: "
          f"gist={p1(held, False):.3f} +id={p1(held, True):.3f} (n={len(held)})")

    # ---- 2: relational addressing, operators fit on seen phrasings only ----
    m = hash_test_mask([queries[i]["text"] for i in seen], frac=0.7)
    fit_idx = [i for i, t in zip(seen, m) if not t]
    test_seen = [i for i, t in zip(seen, m) if t]
    t_by_rel = {}
    for rel in {queries[i]["relation"] for i in ans}:
        tr = [i for i in fit_idx if queries[i]["relation"] == rel]
        t_by_rel[rel] = fit_translation(
            Zq[tr], np.stack([Zf[queries[i]["fact_idx"]] for i in tr]))
    print(f"[2 relational] seen-phrasing test: +t={p1(test_seen, False, t_by_rel):.3f} "
          f"+t+id={p1(test_seen, True, t_by_rel):.3f} (n={len(test_seen)}) | "
          f"HELD-phrasing: +t={p1(held, False, t_by_rel):.3f} "
          f"+t+id={p1(held, True, t_by_rel):.3f}")

    # ---- 3: hops per composition, walk semantics ON vs OFF for revisit ----
    pop_idx = {f["subject"]: i for i, f in enumerate(facts)
               if f["relation"] == "population_of"}
    born_idx = {f["subject"]: i for i, f in enumerate(facts)
                if f["relation"] == "born_in"}
    hop_pairs = {}          # t_hop banks per (rel_from, rel_to), disjoint fit
    test_subj = {h["subject"] for h in hops}
    def bank(rel_from, obj_to_fact):
        P = [(i, obj_to_fact[f["object"]]) for i, f in enumerate(facts)
             if f["relation"] == rel_from and f["subject"] not in test_subj
             and f["object"] in obj_to_fact]
        return fit_translation(np.stack([Zf[i] for i, _ in P[:200]]),
                               np.stack([Zf[j] for _, j in P[:200]]))
    cap_idx = {f["subject"]: i for i, f in enumerate(facts)
               if f["relation"] == "capital_of"
               and (f["year"] is None or f["year"] >= 2000)}
    big_idx = {f["subject"]: i for i, f in enumerate(facts)
               if f["relation"] == "largest_city_of"}
    hop_pairs[("capital_of", "population_of")] = bank("capital_of", pop_idx)
    hop_pairs[("largest_city_of", "population_of")] = bank("largest_city_of", pop_idx)
    hop_pairs[("ceo_of", "born_in")] = bank("ceo_of", born_idx)
    hop_pairs[("located_in", "capital_of")] = bank("located_in", cap_idx)
    hop_pairs[("located_in", "largest_city_of")] = bank("located_in", big_idx)

    results = {}
    for kind in ("cap_pop", "big_pop", "ceo_born", "loc_cap", "loc_big",
                 "loc_cap_pop"):
        cases = [(h, Zh[i]) for i, h in enumerate(hops) if h["kind"] == kind]
        for walk_on in ((True, False) if kind == "loc_big" else (True,)):
            hit = 0
            for h, zq in cases:
                chain = h["chain"]
                z, visited, prev_ids = zq + t_by_rel[chain[0]], set(), qids_of(h["text"])
                cur = top1(z)
                visited.add(cur[0])
                ok = True
                for a, b in zip(chain, chain[1:]):
                    hand = store.ids[cur[0]] - prev_ids
                    t = hop_pairs[(a, b)]
                    if walk_on:
                        cur = top1(store.Z[cur[0]] + t, hand, w=0.5,
                                   demote=prev_ids, exclude=set(visited))
                    else:
                        cur = top1(store.Z[cur[0]] + t, hand, w=0.5)
                    prev_ids = prev_ids | (store.ids[cur[0]] & prev_ids)
                    visited.add(cur[0])
                hit += cur[0] == h["answer_fact"]
            tag = kind + ("" if walk_on else " (walk OFF)")
            results[tag] = hit / len(cases)
            print(f"[hop {tag:>22}] P@1 = {hit / len(cases):.3f} (n={len(cases)})")

    # ---- 4: no-answer separation ----
    na = [i for i, q in enumerate(queries) if q["kind"] == "no_answer"]
    sc_ans = [top1(Zq[i], qid_cache[i])[1] for i in ans[:300]]
    sc_na = [top1(Zq[i], qids_of(queries[i]["text"]))[1] for i in na]
    print(f"[4 no-answer] top-1 score: answerable mean={np.mean(sc_ans):.3f} "
          f"(p10 {np.quantile(sc_ans, 0.1):.3f}) | no-answer "
          f"mean={np.mean(sc_na):.3f} (p90 {np.quantile(sc_na, 0.9):.3f})")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "direct": {"seen_gist": p1(seen, False), "seen_id": p1(seen, True),
                      "held_gist": p1(held, False), "held_id": p1(held, True)},
           "relational": {"seen_t": p1(test_seen, False, t_by_rel),
                          "seen_t_id": p1(test_seen, True, t_by_rel),
                          "held_t": p1(held, False, t_by_rel),
                          "held_t_id": p1(held, True, t_by_rel)},
           "hops": results,
           "no_answer": {"answerable_mean": float(np.mean(sc_ans)),
                         "answerable_p10": float(np.quantile(sc_ans, 0.1)),
                         "na_mean": float(np.mean(sc_na)),
                         "na_p90": float(np.quantile(sc_na, 0.9))}}
    (ROOT / "results" / "memory_v3.json").write_text(json.dumps(out, indent=2))
    print("[done] results/memory_v3.json")


if __name__ == "__main__":
    main()
