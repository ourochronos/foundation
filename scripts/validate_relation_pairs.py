"""Validate generated relation-pair files for meaning-PRESERVING types.

A preserving pair must carry identical facts on both sides. Checks per row:
  numbers   — digit tokens (commas stripped) equal as multisets
  content   — every content word (len>=4, non-stop) on each side has a
              4-char-prefix match on the other (catches added/dropped facts;
              tolerates verb<->noun morphology like shipped/shipment)
  expansion — for contraction_expansion only: y must equal x with
              contractions expanded (modulo whitespace); replaces `content`
Duplicate x values (case-insensitive) are dropped silently.

Flagged rows are removed in place; originals kept as <file>.raw next to it.

Usage: .venv/bin/python scripts/validate_relation_pairs.py prop_cleft.jsonl ...
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REL = ROOT / "data" / "relations"

STOP = {"the", "a", "an", "of", "to", "in", "on", "at", "by", "for", "with",
        "from", "was", "were", "is", "are", "that", "it", "its", "what", "and",
        "or", "as", "after", "before", "when", "their", "his", "her", "she",
        "they", "there", "been", "has", "had", "have", "will", "would", "did",
        "does", "not", "into", "during", "over", "under", "than", "this",
        "occurred", "happened", "took", "place", "came"}

CONTRACTIONS = [
    ("won't", "will not"), ("can't", "cannot"), ("shan't", "shall not"),
    ("n't", " not"), ("'ll", " will"), ("'re", " are"), ("'ve", " have"),
    ("'m", " am"),
]
# ambiguous — branch per occurrence ('s can also be possessive: keep it)
AMBIG = [(r"(?i)'s\b", [" is", " has", None]), (r"(?i)'d\b", [" would", " had"])]


def numbers(t: str) -> list[str]:
    return sorted(n.replace(",", "").rstrip(".:") for n in re.findall(r"\d[\d,.:]*", t))


def content(t: str) -> set[str]:
    toks = re.findall(r"[A-Za-z][\w'-]*", t.lower())
    return {w for w in toks if len(w) >= 4 and w not in STOP and "'" not in w}


def covered(src: set[str], dst_text: str) -> set[str]:
    """Words in src with no 4-char-prefix match in dst — i.e. NOT covered."""
    dtoks = re.findall(r"[A-Za-z][\w'-]*", dst_text.lower())
    missing = set()
    for w in src:
        if not any(d.startswith(w[:4]) for d in dtoks):
            missing.add(w)
    return missing


def expand(t: str) -> set[str]:
    """All candidate expansions, branching each ambiguous 's/'d occurrence."""
    base = t
    for c, e in CONTRACTIONS:
        base = re.sub(re.escape(c), e, base, flags=re.IGNORECASE)

    outs = {base}
    for pat, opts in AMBIG:
        rx = re.compile(pat)
        frontier = outs
        for _ in range(8):                       # bounded occurrences
            nxt = set()
            for s in frontier:
                m = rx.search(s)
                if not m:
                    nxt.add(s)
                    continue
                for o in opts:
                    rep = m.group(0) if o is None else o
                    # freeze this occurrence with \x00 so search moves on
                    nxt.add(s[:m.start()] + rep.replace("'", "\x00") + s[m.end():])
            if nxt == frontier:
                break
            frontier = nxt
        outs = {s.replace("\x00", "'") for s in frontier}
    return {re.sub(r"\s+", " ", o).strip().lower() for o in outs}


def check(row: dict, strict_expansion: bool) -> list[str]:
    x, y = row["x"], row["y"]
    errs = []
    if numbers(x) != numbers(y):
        errs.append(f"numbers {numbers(x)} != {numbers(y)}")
    if strict_expansion:
        yn = re.sub(r"\s+", " ", y).strip().lower()
        if yn not in expand(x) and "'" not in x:
            errs.append("x has no contraction")
        elif yn not in expand(x):
            errs.append("y != expand(x)")
    else:
        miss_y = covered(content(x), y)
        miss_x = covered(content(y), x)
        if miss_y:
            errs.append(f"y missing {sorted(miss_y)}")
        if miss_x:
            errs.append(f"y adds {sorted(miss_x)}")
    return errs


def main() -> None:
    for name in sys.argv[1:]:
        f = REL / name
        rows, seen = [], set()
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                o = json.loads(line)
                if o["x"].lower() not in seen:
                    seen.add(o["x"].lower())
                    rows.append(o)
        strict = rows[0]["relation"] == "contraction_expansion"
        good, bad = [], []
        for r in rows:
            errs = check(r, strict)
            (bad if errs else good).append((r, errs))
        print(f"\n=== {name}: {len(rows)} unique rows, {len(bad)} flagged ===")
        for r, errs in bad:
            print(f"  x: {r['x'][:90]}")
            print(f"  y: {r['y'][:90]}")
            print(f"     {'; '.join(errs)}")
        raw = f.with_suffix(".raw")
        if not raw.exists():
            f.rename(raw)
        f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                             for r, _ in good), encoding="utf-8")
        print(f"[write] {len(good)} rows -> {f.name} (originals in {raw.name})")


if __name__ == "__main__":
    main()
