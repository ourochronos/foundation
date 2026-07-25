"""Positive control for the role-bits extractor (D8 house rule, unit form).

One proposition, written every way English offers, asserting this channel's
CONTRACT rather than "detects all meaning change":

  preserving   every meaning-preserving rewrite must produce identical bits
               (role_sim 1.0) — voice, cleft, nominalization, clause order
  in scope     binding and marked grammatical features must separate —
               role swap, tense, hedge
  out of scope reported for visibility, never asserted:
               * valence (negation, quantifiers) — a linear steering direction
                 the amp channel catches (D15/D16, negation amp_cos ≈ -0.12);
                 the `min` combination means role bits need not see it.
               * an ADDED or DROPPED argument whose filler appears in neither
                 text — indistinguishable, for this extractor, from a role
                 that was merely *renamed*, and the shared-vocabulary gate
                 that resolves it in favour of "renamed" is load-bearing:
                 measured, relaxing it drops formality_shift 0.931 -> 0.580
                 while buying at most 0.04 on any changing type. Same family
                 of accepted limitation as converse predicates (D18).

This is the instrument check — if it fails, the structure channel's role_sim
numbers are not trustworthy, and the transformation-pair tables cannot tell
you which construction broke.

Exits non-zero on any failure. Cheap; run it after touching codec/role_bits.py.

Usage: .venv/bin/python scripts/check_role_bits.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec import role_bits as RB   # noqa: E402

PLAIN = "Vireo Analytics audited 40 accounts in Trenton."

PRESERVING = [
    ("cleft-subject", "It was Vireo Analytics that audited 40 accounts in Trenton."),
    ("cleft-object", "It was 40 accounts that Vireo Analytics audited in Trenton."),
    ("cleft-adjunct", "It was in Trenton that Vireo Analytics audited 40 accounts."),
    ("pseudo-cleft", "What Vireo Analytics audited in Trenton was 40 accounts."),
    ("passive", "40 accounts were audited by Vireo Analytics in Trenton."),
    ("nominal-poss", "Vireo Analytics's audit of 40 accounts occurred in Trenton."),
    ("nominal-there", "There was an audit of 40 accounts by Vireo Analytics in Trenton."),
    ("clause-order", "In Trenton, Vireo Analytics audited 40 accounts."),
]

CHANGING = [
    ("role swap", "40 accounts audited Vireo Analytics in Trenton."),
    ("recipient swap", "Vireo Analytics audited 40 accounts for Trenton."),
    ("tense", "Vireo Analytics will audit 40 accounts in Trenton."),
    ("hedge-modal", "Vireo Analytics may audit 40 accounts in Trenton."),
    ("hedge-raising", "Vireo Analytics appears to audit 40 accounts in Trenton."),
]

OUT_OF_SCOPE = [
    ("negation", "Vireo Analytics did not audit 40 accounts in Trenton."),
    ("quantifier", "Vireo Analytics audited all 40 accounts in Trenton."),
    ("added arg", "Vireo Analytics audited 40 accounts for Trenton Bank."),
]


def main() -> None:
    ref = RB.extract(PLAIN)
    print(f"reference: {PLAIN}\n           {ref}\n")
    failures = []

    print(f"{'construction':>16}  role_sim  expect")
    for label, text in PRESERVING:
        s = RB.role_sim(ref, RB.extract(text), PLAIN, text)
        ok = s >= 0.999
        print(f"{label:>16}  {s:>7.2f}  =1.0 {'ok' if ok else 'FAIL'}")
        if not ok:
            failures.append((label, text, s, RB.extract(text)))
    for label, text in CHANGING:
        s = RB.role_sim(ref, RB.extract(text), PLAIN, text)
        ok = s < 0.999
        print(f"{label:>16}  {s:>7.2f}  <1.0 {'ok' if ok else 'FAIL'}")
        if not ok:
            failures.append((label, text, s, RB.extract(text)))
    for label, text in OUT_OF_SCOPE:
        s = RB.role_sim(ref, RB.extract(text), PLAIN, text)
        print(f"{label:>16}  {s:>7.2f}   n/a (out of scope — not asserted)")

    if failures:
        print(f"\n{len(failures)} FAILURE(S):")
        for label, text, s, bits in failures:
            print(f"  {label}: role_sim={s:.3f}\n    {text}\n    {bits}")
        raise SystemExit(1)
    print(f"\n[ok] {len(PRESERVING)} preserving constructions normalize to "
          f"identical bits; {len(CHANGING)} in-scope changing ones separate; "
          f"{len(OUT_OF_SCOPE)} out-of-scope cases reported only")


if __name__ == "__main__":
    main()
