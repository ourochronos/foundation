"""Slot-tagged identity channel (D21 residual fix, queue item 1).

The v2 decoder receives identities as a BAG of value tokens and re-attaches
them to roles by guesswork — samples show "5 Tesla / 2.3 cm" regenerated as
"2.3 Gauss / 5 cm". Fix at encode time: fuse each number-like sparse token
with its syntactic head, so the slot carries "5 Tesla", not "5". Non-number
tokens pass through unchanged; schema is identical to sparse_v0.json, so the
decoder architecture doesn't change — only slot content does (one variable).

Writes results/sparse_tagged_v0.json row-aligned with clean_v0.jsonl.

Usage: .venv/bin/python scripts/build_tagged_sparse.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec.role_bits import _nlp   # noqa: E402

OUT = ROOT / "results" / "sparse_tagged_v0.json"
NUMLIKE = re.compile(r"^\d[\d,.:%-]*$")


def main() -> None:
    texts = [json.loads(l)["text"] for l in
             (ROOT / "data" / "clean_v0.jsonl").read_text().splitlines() if l.strip()]
    rows = json.loads((ROOT / "results" / "sparse_v0.json").read_text())
    assert len(texts) == len(rows)
    nlp = _nlp()

    n_tagged = n_num = 0
    out = []
    for text, row in zip(texts, rows):
        doc = None
        toks = []
        for t in row["tokens"]:
            if not NUMLIKE.match(t):
                toks.append(t)
                continue
            n_num += 1
            if doc is None:
                doc = nlp(text)
            tagged = t
            for tok in doc:
                if tok.text == t or tok.text.replace(",", "") == t.replace(",", ""):
                    head = tok.head
                    for _ in range(3):          # ascend through numeric heads
                        if head.like_num or head.pos_ == "NUM":
                            head = head.head
                        else:
                            break
                    if head is not tok and not NUMLIKE.match(head.text):
                        tagged = f"{t} {head.text}"
                        n_tagged += 1
                    break
            toks.append(tagged)
        out.append({"tokens": toks, "weights": row["weights"]})

    OUT.write_text(json.dumps(out))
    print(f"[done] {OUT.name}: {len(out)} rows, "
          f"{n_tagged}/{n_num} number tokens tagged with their head")
    # spot check
    for i in (0, 1000, 9000):
        pairs = [t for t in out[i]["tokens"] if " " in t]
        print(f"  [{i}] {texts[i][:70]}")
        print(f"       tagged: {pairs}")


if __name__ == "__main__":
    main()
