"""J5 — cross-lingual retrieval: is the gist channel an interlingua? (D40)

200 single-hop v4 queries translated to FR (even idx) / DE (odd idx) by a
Haiku agent, invented entity names kept verbatim. English facts stay in the
store untouched. Measured per language, against the SAME queries in English:

  gist-only   P@1 — dense channel across the language boundary
  +identity   P@1 — hybrid (identity terms extracted by matching the store's
                    known entity vocabulary in the query text — the symbolic
                    channel is lexical, so verbatim names should survive)
  id-coverage      — fraction of queries where the gold subject's tokens were
                    recoverable from the translated text

D40 prediction: gist transfers with modest loss (BGE-M3 is multilingual by
training); the identity channel transfers ~perfectly because names are
surface-copied — i.e. the interlingua is the dense channel, the symbolic
channel is language-parochial but name-preserving.

Usage: .venv/bin/python scripts/probe_crosslingual.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec import whiten as W                                    # noqa: E402
from codec.memory_store import MemoryStore, id_tokens             # noqa: E402


def unit(X):
    return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)


def main() -> None:
    world = json.loads((ROOT / "data" / "closed_world_v4.json").read_text())
    facts, queries = world["facts"], world["queries"]
    xl = json.loads((ROOT / "data" / "crosslingual_queries_v0.json").read_text())

    z = np.load(ROOT / "results" / "closed_world_v4_emb.npz")
    Zf, Zq = z["Zf"], z["Zq"]

    singles = [i for i, q in enumerate(queries) if q["kind"] == "single"][:200]
    assert len(singles) == len(xl)

    from codec.encode import M3Encoder
    enc = M3Encoder()
    wh = W.load(str(ROOT / "results" / "whiten_v0.npz"))

    cache = ROOT / "results" / "crosslingual_emb.npz"
    if cache.exists():
        Zx = np.load(cache)["Zx"]
    else:
        d, _ = enc.encode([x["text"] for x in xl], sparse=False)
        Zx = unit(W.apply(d, wh))
        np.savez(cache, Zx=Zx)

    store = MemoryStore()
    for f, zf in zip(facts, Zf):
        store.add(zf, f["entities"] + f["numbers"], f["text"])

    # identity extraction: match known entity vocabulary verbatim in the text
    vocab = sorted({e for f in facts for e in f["entities"]}, key=len,
                   reverse=True)

    def ids_of(text):
        found, t = [], text
        for name in vocab:
            if name in t:
                found.append(name)
                t = t.replace(name, " ")
        return id_tokens(found)

    def p1(rows, Z, texts):
        hit = idhit = cov = 0
        for j, qi in rows:
            q = queries[qi]
            gold = q["fact_idx"]
            ids = ids_of(texts[j])
            subj = id_tokens([facts[gold]["subject"]])
            cov += bool(subj and subj <= ids)
            hit += store.query(Z[j], None, k=1, id_weight=0.0)[0][0] == gold
            idhit += store.query(Z[j], ids, k=1,
                                 id_weight=0.5 if ids else 0.0)[0][0] == gold
        n = len(rows)
        return hit / n, idhit / n, cov / n

    en_rows = [(j, qi) for j, qi in enumerate(singles)]
    en_texts = [queries[qi]["text"] for qi in singles]
    g, h, c = p1(en_rows, Zq[singles], en_texts)
    print(f"[xl    en] gist P@1={g:.3f}  +ids P@1={h:.3f}  id-cov={c:.3f} "
          f"(n={len(en_rows)})", flush=True)

    out = {"en": {"gist": g, "hybrid": h, "cov": c}}
    for lang in ("fr", "de"):
        rows = [(j, qi) for j, (x, qi) in enumerate(zip(xl, singles))
                if x["lang"] == lang]
        g, h, c = p1(rows, Zx, [x["text"] for x in xl])
        print(f"[xl    {lang}] gist P@1={g:.3f}  +ids P@1={h:.3f}  "
              f"id-cov={c:.3f} (n={len(rows)})", flush=True)
        out[lang] = {"gist": g, "hybrid": h, "cov": c}

    (ROOT / "results" / "crosslingual_j5.json").write_text(json.dumps(out,
                                                                      indent=2))
    print("[done] results/crosslingual_j5.json")


if __name__ == "__main__":
    main()
