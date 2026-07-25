"""Identity comparison channel (D3/D20: substitutions belong to identities).

The structure channel deliberately cannot see single-token literal edits
("Tuesday" -> "Saturday" scores 0.92 through it) — by D3 those are identity
edits and this channel owns them. Codec-level comparison is then

    sim(x, y) = min( struct_sim(x, y), identity_sim(x, y) )

The design constraint (D20): naive string equality false-flags meaning-
preserving reformatting ("around 3" -> "approximately 03:00"). Resolution —
**substitution is a BIDIRECTIONAL mismatch**: flag a category only when both
sides hold values the other lacks. A date substitution leaves 22 unmatched in
x AND 23 unmatched in y -> flagged; a reformatting leaves surplus fragments on
one side only ("03:00" contributes an extra 0) -> not flagged. One-sided
information gain/loss is elaboration or ellipsis, which the other channels
(and the fidelity axis) own.

Numbers: maximal digit-groups, comma/leading-zero normalized, compared as
value multisets. Entities: PROPN token lemma-cased sets from the parse.
"""

from __future__ import annotations

import re
from collections import Counter

_NUM = re.compile(r"\d+(?:\.\d+)?")


def _num_values(text: str) -> Counter:
    """Multiset of numeric values: split on non-digit/non-dot boundaries, so
    "4,200" -> {4, 200}? No — commas stripped FIRST so it parses as 4200;
    times like 03:00 split into {3, 0}."""
    t = text.replace(",", "")
    vals = Counter()
    for m in _NUM.finditer(t):
        try:
            v = float(m.group())
        except ValueError:
            continue
        vals[v] += 1
    return vals


def _entities(doc) -> Counter:
    return Counter(t.text.lower() for t in doc if t.pos_ == "PROPN")


def _category_sim(cx: Counter, cy: Counter) -> float:
    """1.0 unless the mismatch is bidirectional; then the matched fraction."""
    inter = cx & cy
    only_x, only_y = cx - inter, cy - inter
    if not only_x or not only_y:      # one-sided surplus = reformat/ellipsis
        return 1.0
    total = max(sum(cx.values()), sum(cy.values()))
    return sum(inter.values()) / max(total, 1)


def identity_sim(x_text: str, y_text: str, nlp=None) -> float:
    """min over categories (numbers, entities); 1.0 = identities agree."""
    if nlp is None:
        from codec.role_bits import _nlp
        nlp = _nlp()
    n_sim = _category_sim(_num_values(x_text), _num_values(y_text))
    e_sim = _category_sim(_entities(nlp(x_text)), _entities(nlp(y_text)))
    return min(n_sim, e_sim)
