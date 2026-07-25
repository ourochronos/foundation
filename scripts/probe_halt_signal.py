"""B2 — Halting/abstention signal audit on the de-templated world.

D30 killed top-1 absolute score as an abstention signal. This audits every
cheap store-response readout for TWO separations the reasoner needs:
  HALT      answer-reached vs mid-walk vs over-stepped (one forced extra hop)
  ABSTAIN   answerable vs no-answer queries
Signals: top1-top2 margin, top1 absolute, id-coverage (fraction of query ids
present in the retrieved entry), hand-off size, step score delta. Reported as
single-threshold AUC per signal (rank-based), plus distribution summaries.

Literature stance (07-plan B2): halting should be a cheap READOUT; this
decides which readout, or whether v0 falls back to supervised-halt only.

Usage: .venv/bin/python scripts/probe_halt_signal.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec.memory_store import MemoryStore, fit_translation, id_tokens  # noqa: E402
from codec.structure_channel import hash_test_mask                      # noqa: E402


def unit(X):
    return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)


def auc(neg, pos):
    lo, hi = np.asarray(neg, float), np.asarray(pos, float)
    order = np.concatenate([lo, hi]).argsort(kind="mergesort")
    ranks = np.empty(len(order)); ranks[order] = np.arange(1, len(order) + 1)
    u = ranks[:len(lo)].sum() - len(lo) * (len(lo) + 1) / 2
    return float(1 - u / (len(lo) * len(hi)))


def main() -> None:
    world = json.loads((ROOT / "data" / "closed_world_v3.json").read_text())
    facts, queries, hops = world["facts"], world["queries"], world["hops"]
    z = np.load(ROOT / "results" / "closed_world_v3_emb.npz")
    Zf, Zq, Zh = z["Zf"], z["Zq"], z["Zh"]

    from codec.role_bits import _nlp
    nlp = _nlp()

    def qids_of(text):
        doc = nlp(text)
        return id_tokens([t.text.rstrip("'s") if t.text.endswith("'s") else t.text
                          for t in doc if t.pos_ == "PROPN"]
                         + [t.text for t in doc if t.like_num])

    store = MemoryStore()
    for f, zf in zip(facts, Zf):
        store.add(zf, f["entities"] + f["numbers"], f["text"])

    def q2(zv, ids, demote=None, exclude=None):
        r = store.query(zv, ids, k=2, id_weight=0.5 if (ids or demote) else 0.0,
                        demote_ids=demote, exclude=exclude)
        top1, top2 = r[0], r[1]
        cov = (len(ids & store.ids[top1[0]]) / max(len(ids), 1)) if ids else 0.0
        return top1, {"margin": top1[1] - top2[1], "top1": top1[1],
                      "id_cov": cov}

    # ---- ABSTAIN: answerable vs no-answer (single-hop) ----
    ans = [i for i, q in enumerate(queries) if q["kind"] == "single"][:600]
    na = [i for i, q in enumerate(queries) if q["kind"] == "no_answer"]
    sig_ans, sig_na = [], []
    for pool, out in ((ans, sig_ans), (na, sig_na)):
        for i in pool:
            _, s = q2(Zq[i], qids_of(queries[i]["text"]))
            out.append(s)
    print("[ABSTAIN] answerable vs no-answer, AUC per signal:")
    ab = {}
    for k in ("margin", "top1", "id_cov"):
        a = auc([s[k] for s in sig_na], [s[k] for s in sig_ans])
        ab[k] = a
        print(f"    {k:>8}: {a:.3f}")

    # ---- HALT: oracle walks on cap_pop (the composition that works) ----
    # fit t_cap / t_hop as in the v3 probe, on non-test subjects
    seen = [i for i, q in enumerate(queries) if q["kind"] == "single"
            and q["phrasing_idx"] not in set(world["held_out_phrasings"])]
    t_by_rel = {}
    for rel in ("capital_of", "population_of"):
        tr = [i for i in seen if queries[i]["relation"] == rel][:300]
        t_by_rel[rel] = fit_translation(
            Zq[tr], np.stack([Zf[queries[i]["fact_idx"]] for i in tr]))
    pop_idx = {f["subject"]: i for i, f in enumerate(facts)
               if f["relation"] == "population_of"}
    test_subj = {h["subject"] for h in hops}
    P = [(i, pop_idx[f["object"]]) for i, f in enumerate(facts)
         if f["relation"] == "capital_of" and f["subject"] not in test_subj
         and f["object"] in pop_idx][:200]
    t_hop = fit_translation(np.stack([Zf[i] for i, _ in P]),
                            np.stack([Zf[j] for _, j in P]))

    mid, done, over = [], [], []
    cases = [(h, Zh[i]) for i, h in enumerate(hops) if h["kind"] == "cap_pop"]
    for h, zq in cases:
        ids0 = qids_of(h["text"])
        r1, s1 = q2(zq + t_by_rel["capital_of"], None)
        hand = store.ids[r1[0]] - ids0
        r2, s2 = q2(store.Z[r1[0]] + t_hop, hand, demote=ids0,
                    exclude={r1[0]})
        if r2[0] != h["answer_fact"]:
            continue                          # audit successful walks only
        mid.append(s1)
        done.append(s2)
        hand2 = store.ids[r2[0]] - hand
        _, s3 = q2(store.Z[r2[0]] + t_hop, hand2, demote=hand,
                   exclude={r1[0], r2[0]})           # forced extra hop
        over.append(s3)

    print(f"[HALT] on {len(done)} successful cap_pop walks — "
          "done-vs-mid | done-vs-overstep AUC:")
    hl = {}
    for k in ("margin", "top1", "id_cov"):
        a1 = auc([s[k] for s in mid], [s[k] for s in done])
        a2 = auc([s[k] for s in over], [s[k] for s in done])
        hl[k] = {"done_vs_mid": a1, "done_vs_overstep": a2}
        print(f"    {k:>8}: {a1:.3f} | {a2:.3f}")

    best_ab = max(ab, key=ab.get)
    verdict = (f"abstain: best signal {best_ab} AUC={ab[best_ab]:.3f}; "
               + ("usable" if ab[best_ab] > 0.8 else "NO single cheap signal — "
                  "abstention must be learned (value head) or use answer-type "
                  "checks"))
    print(f"[verdict] {verdict}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "abstain_auc": ab, "halt_auc": hl,
           "n_walks": len(done), "verdict": verdict}
    (ROOT / "results" / "halt_signal_b2.json").write_text(json.dumps(out, indent=2))
    print("[done] results/halt_signal_b2.json")


if __name__ == "__main__":
    main()
