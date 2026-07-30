"""The claim block, loaded from `docs/18-writeup-outline.md` (D151/D152).

One artifact holds the claims: the fenced JSON block in `docs/18`. The prose
table in that file is a rendering of it, `adjudicate.py` judges it, and
`adjud_quorum.py` aggregates verdicts about it. Nothing here stores a claim;
this module only reads them and checks that a stored verdict still refers to
the claim it was written about.

Why that check exists: verdict artifacts key on **index**. When the claim list
shortened from 11 to 10, every stored verdict silently re-pointed — the JSON
still parsed, the indices still resolved, and the reasons still read as
plausible prose about *something*. D152 caught it only because a falsifier
about derived thresholds surfaced under a claim about composition. So
`check_alignment` turns that lesson into a precondition instead of a habit.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "18-writeup-outline.md"
STAMP_LEN = 120                 # adjudicate.py truncates `judged_claims` here


def digest(text: str) -> str:
    """Exact fingerprint of a claim, for comparisons the 120-char stamp cannot make.

    The readable stamp is a prefix, and a prefix cannot see an edit past its
    end. That bit: a cross-round diff keyed on the stamp reported two raters
    withdrawing a flag from an "unchanged" claim whose text had in fact been
    edited at character 190. The stamp stays because a human reading an
    artifact needs to see which claim it judged; this sits beside it so a
    machine comparing two rounds is never fooled by a shared prefix.
    """
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def load_claims() -> list[dict]:
    md = DOC.read_text()
    m = re.search(r"## Machine-readable claims.*?```json\n(.*?)\n```", md, re.S)
    if not m:
        raise SystemExit(f"{DOC.name}: no machine-readable claims block found")
    out = json.loads(m.group(1))
    for c in out:
        c["src"] = tuple(c["src"])
        if "extra" in c:
            c["extra"] = [tuple(x) for x in c["extra"]]
    return out


def stamp(claims: list[dict], i: int) -> str:
    """What `adjudicate.py` records in `judged_claims` for index `i`."""
    it = claims[i] if i < len(claims) else {}
    return str(it.get("claim", it.get("statement", "")))[:STAMP_LEN]


def check_alignment(art: dict, claims: list[dict]) -> list[str]:
    """Reasons this artifact's indices cannot be trusted; empty means usable.

    An artifact with no `judged_claims` predates D152 and is unusable for
    anything index-keyed no matter what it says — its aggregate counts may
    still be fine, but that is the caller's call to make explicitly.
    """
    jc = art.get("judged_claims")
    if not jc:
        return ["no judged_claims (pre-D152): index mapping unrecoverable"]
    bad = []
    if len(jc) != len(claims):
        bad.append(f"judged {len(jc)} claims, current block has {len(claims)}")
    for k, v in sorted(jc.items(), key=lambda kv: int(kv[0])):
        i = int(k)
        if i >= len(claims):
            bad.append(f"idx {i}: beyond the current block")
        elif v != stamp(claims, i):
            bad.append(f"idx {i}: judged {v[:56]!r}, now {stamp(claims, i)[:56]!r}")
    return bad
