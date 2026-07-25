"""Encoder bake-off (D12 rank 1): does any off-the-shelf encoder order
propositional transformations correctly?

Candidates:
  bge-m3        retrieval-contrastive (incumbent, control for its own class)
  bge-base-en   retrieval-contrastive (second control — is it the objective
                class or the specific model?)
  nli-mpnet     NLI softmax-trained (entailment/contradiction objective)
  all-mpnet     broad 1B-pair contrastive (paraphrase-heavy)
  sup-simcse    supervised SimCSE — NLI with contradictions as HARD NEGATIVES
                (the objective most directly aligned with our need)

Scores per encoder (own whitened space each):
  ORDERING  auc(invert vs preserve) = P(random inverting pair sits FARTHER
            than random preserving pair). 1.0 = perfect ordering, 0.5 = blind,
            <0.5 = inverted. Plus the two flagship cases.
  IDENTITY  linear-probe recall@20 for verbatim number strings (ground truth
            from validated labels), held-out propositions.
  GEOMETRY  kNN@10 same-domain purity on the corpus (proxy for retrieval use).

Usage: .venv/bin/python scripts/encoder_bakeoff.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec import data as D_, whiten as W    # noqa: E402
from codec.evals import rotations as ROT     # noqa: E402

PRESERVE = ["active_passive", "synonym_swap", "clause_reorder",
            "formality_shift", "paraphrase"]
INVERT = ["negation", "argument_swap", "comparative_flip", "quantifier_change",
          "superlative_flip", "success_failure", "increase_decrease",
          "approval_rejection", "presence_absence", "causal_reverse"]
MODIFY = ["quantity_double", "date_shift", "location_swap", "tense_shift", "hedge"]

N_CORPUS = 4000


def load_all_pairs():
    by_rel = {}
    for f in sorted((ROOT / "data" / "relations").glob("prop_*.jsonl")):
        rows, seen = [], set()
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            o = json.loads(line)
            if o["x"].lower() in seen:
                continue
            seen.add(o["x"].lower())
            rows.append(o)
        if rows:
            by_rel[rows[0]["relation"]] = rows
    return by_rel


class Encoders:
    """Each returns raw (unnormalized) sentence embeddings [n, d]."""

    @staticmethod
    def bge_m3(texts):
        from codec.encode import M3Encoder
        enc = M3Encoder()
        d, _ = enc.encode(texts, sparse=False)
        del enc
        torch.cuda.empty_cache()
        return d

    @staticmethod
    def _st(name, texts):
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer(name, device="cuda" if torch.cuda.is_available() else "cpu")
        v = m.encode(texts, batch_size=128, convert_to_numpy=True,
                     show_progress_bar=False, normalize_embeddings=False)
        del m
        torch.cuda.empty_cache()
        return np.asarray(v, dtype=np.float32)

    @staticmethod
    def bge_base(texts):
        return Encoders._st("BAAI/bge-base-en-v1.5", texts)

    @staticmethod
    def nli_mpnet(texts):
        return Encoders._st("sentence-transformers/nli-mpnet-base-v2", texts)

    @staticmethod
    def all_mpnet(texts):
        return Encoders._st("sentence-transformers/all-mpnet-base-v2", texts)

    @staticmethod
    def sup_simcse(texts):
        from transformers import AutoModel, AutoTokenizer
        name = "princeton-nlp/sup-simcse-roberta-base"
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        tok = AutoTokenizer.from_pretrained(name)
        mod = AutoModel.from_pretrained(name, dtype=torch.float16).to(dev).eval()
        outs = []
        with torch.no_grad():
            for i in range(0, len(texts), 128):
                b = tok(texts[i:i + 128], padding=True, truncation=True,
                        max_length=128, return_tensors="pt").to(dev)
                h = mod(**b).last_hidden_state[:, 0]   # cls_before_pooler
                outs.append(h.float().cpu().numpy())
        del mod
        torch.cuda.empty_cache()
        return np.concatenate(outs).astype(np.float32)


def auc(lo: np.ndarray, hi: np.ndarray) -> float:
    """P(random lo-sample < random hi-sample), ties=0.5 (Mann-Whitney)."""
    order = np.concatenate([lo, hi]).argsort(kind="mergesort")
    ranks = np.empty(len(order)); ranks[order] = np.arange(1, len(order) + 1)
    r_lo = ranks[: len(lo)].sum()
    u = r_lo - len(lo) * (len(lo) + 1) / 2
    return float(1 - u / (len(lo) * len(hi)))


def identity_probe(Z, props, is_eval, min_count=5, topk=20):
    counts = {}
    for p in props:
        for nstr in set(p.numbers):
            counts[nstr] = counts.get(nstr, 0) + 1
    vocab = sorted([t for t, c in counts.items() if c >= min_count])
    if len(vocab) < 20:
        return {"recall": float("nan"), "baseline": float("nan"), "vocab": len(vocab)}
    vidx = {t: i for i, t in enumerate(vocab)}
    Y = np.zeros((len(props), len(vocab)), dtype=np.float32)
    for i, p in enumerate(props):
        for nstr in set(p.numbers):
            j = vidx.get(nstr)
            if j is not None:
                Y[i, j] = 1.0
    Xtr, Ytr, Xte, Yte = Z[~is_eval], Y[~is_eval], Z[is_eval], Y[is_eval]
    lam = 1.0
    A = Xtr.T @ Xtr + lam * np.eye(Z.shape[1], dtype=np.float32)
    Wt = np.linalg.solve(A, Xtr.T @ Ytr)
    P = Xte @ Wt
    prior = np.tile(Ytr.mean(axis=0), (len(Xte), 1))

    def recall(scores):
        top = np.argpartition(-scores, topk - 1, axis=1)[:, :topk]
        hit = tot = 0
        for i in range(len(Yte)):
            true = set(np.where(Yte[i])[0])
            if true:
                hit += len(true & set(top[i].tolist())); tot += len(true)
        return hit / max(tot, 1)

    return {"recall": recall(P), "baseline": recall(prior), "vocab": len(vocab)}


def main() -> None:
    by_rel = load_all_pairs()
    pair_texts, spans, o = [], {}, 0
    for rel, rows in sorted(by_rel.items()):
        spans[rel] = (o, o + len(rows)); o += len(rows)
        pair_texts += [r["x"] for r in rows]
    n_x = o
    for rel, rows in sorted(by_rel.items()):
        pair_texts += [r["y"] for r in rows]

    clean = [D_.Proposition(**json.loads(l)) for l in
             (ROOT / "data" / "clean_v0.jsonl").read_text().splitlines() if l.strip()]
    rng = np.random.default_rng(0)
    sub = rng.permutation(len(clean))[:N_CORPUS]
    props = [clean[i] for i in sub]
    corpus_texts = [p.text for p in props]
    domains = np.array([p.domain for p in props])
    _, eval_p = D_.split(props, eval_frac=0.15)
    ek = {p.text for p in eval_p}
    is_eval = np.array([p.text in ek for p in props])

    results = {}
    for name in ["bge_m3", "bge_base", "nli_mpnet", "all_mpnet", "sup_simcse"]:
        try:
            print(f"\n=== {name} ===", flush=True)
            embed = getattr(Encoders, name)
            E_all = embed(corpus_texts + pair_texts)
            Ec, Ep = E_all[:len(corpus_texts)], E_all[len(corpus_texts):]
            wh = W.fit(Ec[~is_eval])
            Zc = W.apply(Ec, wh)
            Zp = W.apply(Ep, wh)
            Zx, Zy = Zp[:n_x], Zp[n_x:]

            mags = {rel: float(np.einsum("ij,ij->i", Zx[lo:hi], Zy[lo:hi]).mean())
                    for rel, (lo, hi) in spans.items()}
            inv = np.concatenate([np.einsum("ij,ij->i", Zx[lo:hi], Zy[lo:hi])
                                  for rel, (lo, hi) in spans.items() if rel in INVERT])
            pre = np.concatenate([np.einsum("ij,ij->i", Zx[lo:hi], Zy[lo:hi])
                                  for rel, (lo, hi) in spans.items() if rel in PRESERVE])
            ordering = auc(inv, pre)
            ident = identity_probe(Zc, props, is_eval)

            sims = Zc @ Zc.T
            np.fill_diagonal(sims, -np.inf)
            nn = np.argpartition(-sims, 10, axis=1)[:, :10]
            purity = float(np.mean([np.mean(domains[nn[i]] == domains[i])
                                    for i in range(len(domains))]))

            flag_swap = mags.get("argument_swap", float("nan"))
            flag_para = mags.get("paraphrase", float("nan"))
            flag_form = mags.get("formality_shift", float("nan"))
            results[name] = {
                "ordering_auc": ordering, "magnitudes": mags,
                "identity": ident, "domain_purity@10": purity,
                "flagship": {"argument_swap": flag_swap, "paraphrase": flag_para,
                              "formality_shift": flag_form,
                              "swap_below_paraphrase": bool(flag_swap < flag_para)},
            }
            print(f"[{name}] ordering AUC={ordering:.3f} | "
                  f"swap={flag_swap:.3f} para={flag_para:.3f} form={flag_form:.3f} "
                  f"(swap<para: {flag_swap < flag_para}) | "
                  f"num-recall@20={ident['recall']:.3f} (base {ident['baseline']:.3f}) | "
                  f"purity@10={purity:.3f}")
        except Exception as e:                          # noqa: BLE001
            results[name] = {"error": repr(e)}
            print(f"[{name}] FAILED: {e!r}")

    print("\n=== SCOREBOARD (ordering AUC | swap<para | num-recall lift | purity) ===")
    for name, r in results.items():
        if "error" in r:
            print(f"{name:>12}: failed")
            continue
        lift = r["identity"]["recall"] / max(r["identity"]["baseline"], 1e-9)
        print(f"{name:>12}: {r['ordering_auc']:.3f} | "
              f"{str(r['flagship']['swap_below_paraphrase']):>5} | "
              f"{lift:.2f}x | {r['domain_purity@10']:.3f}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "n_corpus": N_CORPUS, "preserve": PRESERVE, "invert": INVERT,
           "modify": MODIFY, "results": results}
    (ROOT / "results" / "encoder_bakeoff.json").write_text(json.dumps(out, indent=2))
    print("[done] results/encoder_bakeoff.json")


if __name__ == "__main__":
    main()
