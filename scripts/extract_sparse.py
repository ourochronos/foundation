"""Extract the sparse identity channel, row-aligned with clean_v0.jsonl.

BGE-M3's lexical weights are {token_id: weight} over the XLM-R vocab. We store
the top-k tokens as *strings* + weights so the decoder can map them into its own
vocabulary — the identity channel carries surface forms, deliberately kept
symbolic and outside the continuous algebra (D3).

Usage: .venv/bin/python scripts/extract_sparse.py [--topk 24]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topk", type=int, default=24)
    args = ap.parse_args()

    texts = [json.loads(l)["text"] for l in
             (ROOT / "data" / "clean_v0.jsonl").read_text().splitlines() if l.strip()]
    print(f"[data] {len(texts)} propositions")

    from codec.encode import M3Encoder
    enc = M3Encoder()
    _, lex = enc.encode(texts, sparse=True)

    tk = enc.model.tokenizer
    rows = []
    for d in lex:
        items = sorted(d.items(), key=lambda kv: -float(kv[1]))[:args.topk]
        toks, ws = [], []
        for tid, w in items:
            s = tk.decode([int(tid)]).strip()
            if s:
                toks.append(s)
                ws.append(round(float(w), 4))
        rows.append({"tokens": toks, "weights": ws})

    out = ROOT / "results" / "sparse_v0.json"
    out.write_text(json.dumps(rows))
    n = sum(len(r["tokens"]) for r in rows) / max(len(rows), 1)
    print(f"[sparse] mean {n:.1f} tokens/proposition -> {out}")
    print(f"[sample] {texts[0]}\n          {rows[0]['tokens'][:12]}")


if __name__ == "__main__":
    main()
