"""Is identity information *linearly present* in the dense latent? (no decoder)

The decoder reconstructs TRAIN propositions ~perfectly but generalizes only to
gist. That is ambiguous: the latent may carry identities (readout overfits), or
the decoder may be using z as an index key into memorized sentences.

This probe removes the generative model entirely. Ridge regression from the
whitened dense latent to *presence of each lexical token*, fit on train and
scored on held-out propositions. If numeric/identity tokens are predictable
above the frequency baseline, the information is in the dense channel and the
bottleneck is the readout. If they are at baseline while content words are
predictable, the dense channel really is a topic code and the sparse identity
channel (D3) is doing necessary work.

Usage: .venv/bin/python scripts/probe_identity_info.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec import data as D_, whiten as W        # noqa: E402

MIN_COUNT = 5
TOPK = 20


def is_numeric(tok: str) -> bool:
    return bool(re.search(r"\d", tok))


def main() -> None:
    clean = [D_.Proposition(**json.loads(l)) for l in
             (ROOT / "data" / "clean_v0.jsonl").read_text().splitlines() if l.strip()]
    dense = np.load(ROOT / "results" / "dense_v0.npy")
    sparse_rows = json.loads((ROOT / "results" / "sparse_v0.json").read_text())
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
    Z = W.apply(dense, whitener)

    # vocabulary of lexical tokens
    counts: dict[str, int] = {}
    for r in sparse_rows:
        for t in set(r["tokens"]):
            counts[t] = counts.get(t, 0) + 1
    vocab = sorted([t for t, c in counts.items() if c >= MIN_COUNT])
    vidx = {t: i for i, t in enumerate(vocab)}
    numeric_cols = np.array([is_numeric(t) for t in vocab])
    print(f"[vocab] {len(vocab)} tokens (>= {MIN_COUNT} occurrences); "
          f"{int(numeric_cols.sum())} numeric, {int((~numeric_cols).sum())} non-numeric")

    Y = np.zeros((len(clean), len(vocab)), dtype=np.float32)
    for i, r in enumerate(sparse_rows):
        for t in set(r["tokens"]):
            j = vidx.get(t)
            if j is not None:
                Y[i, j] = 1.0

    _, eval_p = D_.split(clean, eval_frac=0.1)
    eval_keys = {p.text for p in eval_p}
    is_eval = np.array([p.text in eval_keys for p in clean])
    Xtr, Ytr = Z[~is_eval], Y[~is_eval]
    Xte, Yte = Z[is_eval], Y[is_eval]
    print(f"[split] train={len(Xtr)} eval={len(Xte)}")

    # ridge, closed form
    lam = 1.0
    d = Xtr.shape[1]
    A = Xtr.T @ Xtr + lam * np.eye(d, dtype=np.float32)
    Wt = np.linalg.solve(A, Xtr.T @ Ytr)             # [d, V]
    P = Xte @ Wt                                      # [n_eval, V]

    prior = Ytr.mean(axis=0)                          # frequency baseline

    def recall_at_k(scores: np.ndarray, truth: np.ndarray, cols: np.ndarray,
                    k: int = TOPK) -> float:
        """Mean recall of true tokens (restricted to `cols`) in the model's top-k."""
        s = np.where(cols[None, :], scores, -np.inf)
        top = np.argpartition(-s, min(k, s.shape[1]) - 1, axis=1)[:, :k]
        hits, tot = 0, 0
        for i in range(truth.shape[0]):
            true_set = set(np.where(truth[i] * cols)[0])
            if not true_set:
                continue
            hits += len(true_set & set(top[i].tolist()))
            tot += len(true_set)
        return hits / max(tot, 1)

    results = {}
    for name, cols in [("numeric", numeric_cols), ("non_numeric", ~numeric_cols),
                       ("all", np.ones_like(numeric_cols))]:
        probe = recall_at_k(P, Yte, cols)
        base = recall_at_k(np.tile(prior, (len(Xte), 1)), Yte, cols)
        lift = probe / max(base, 1e-9)
        results[name] = {"probe_recall": probe, "frequency_baseline": base,
                         "lift": lift, "n_tokens": int(cols.sum())}
        print(f"[{name:>12}] recall@{TOPK} probe={probe:.3f} "
              f"baseline={base:.3f}  lift={lift:.2f}x")

    verdict = (
        "DENSE CARRIES IDENTITIES — numeric tokens recoverable well above the "
        "frequency baseline; the bottleneck is the decoder readout, not the latent"
        if results["numeric"]["lift"] > 2.0 else
        "DENSE IS A TOPIC CODE — numeric tokens near the frequency baseline while "
        "content words are predictable; the sparse identity channel is necessary"
    )
    print(f"\n[verdict] {verdict}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "min_count": MIN_COUNT, "topk": TOPK, "vocab_size": len(vocab),
           "results": results, "verdict": verdict}
    (ROOT / "results" / "identity_info_probe.json").write_text(json.dumps(out, indent=2))
    print("[done] results/identity_info_probe.json")


if __name__ == "__main__":
    main()
