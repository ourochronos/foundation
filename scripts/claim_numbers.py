"""Every number in a claim must be derivable from the evidence it cites.

This mechanises the defect four independent raters kept finding by hand. Over
D150–D153 the single most common flag was not a wrong conclusion — it was a
**number in the claim or its scope that the supplied evidence did not
contain**:

  * "fails at 5" relations, where 5 appeared in no artifact anywhere;
  * a gap of "0.230" that the evidence put at 0.2294;
  * "measured on two corpora", with one corpus supplied;
  * a contrasting figure of "0.050" cited from an experiment not in `src`.

Each was caught by a human-scale read of one claim at a time, and each cost a
round of premium adjudication calls to find. They are all the same defect and
it is checkable: take the decimals the claim asserts, take the numbers the
cited files actually contain, and report what cannot be reached from them.

**Derivation, but constrained — and the constraint is the whole design.** An
honest claim routinely states a number the artifact does not literally store:
a gap between two measurements, a rate from a count and a total. The first
version of this file therefore accepted any pairwise difference or quotient
over every number in the cited files — and passed all 14 claims, including one
whose scope cites `0.050` from an experiment it does not cite at all. With a
few hundred evidence numbers there are ~80,000 differences and ~160,000
quotients, so at three decimals *something* always lands within tolerance. A
check that cannot fail is not a check; that is the same mistake as the row
count that passed at 10-vs-10, one file over.

So derivations are restricted to ones that mean something:

  * **verbatim** — the number is in a cited file;
  * **rate** — a quotient of two integers that appear in the same container
    (5821 of 6000 refused → 0.970);
  * **gap** — a difference of two floats in the same container (frozen 0.9033
    vs rebuilt 0.9611 → 0.058).

"Same container" is what does the work: `frozen` and `rebuilt` sit side by
side under one key because the experiment put them there, so their difference
is a quantity the experiment measured. Two numbers from unrelated corners of
a file have no such relationship, and their difference is a coincidence.
Anything reachable only that way is reported as **UNCITED**, because that is
what an adjudicator will call it.

Bare integers are ignored. They are overwhelmingly hidden-unit counts, epoch
counts, "three objectives" and the like, and checking them buys noise. The
exception is any integer a claim leans on as a measurement, which will read as
a decimal in practice ("5821 of 6000" is checked via the 0.970 beside it).

**What this does NOT establish.** A derived match is a search result, and a
search over a few thousand candidates finds coincidences. Row 5's scope cites
`0.050` from an experiment it does not cite at all; the run reports it as
`rate 148/2939` = 0.0504, two unrelated counts inside the file it does cite.
That is why derived is its own category and never counted as clean: the tool
is trusted to say a number is **absent**, and trusted only to *shortlist* the
rest. Tightening the derivation rules further was tried and abandoned —
requiring a denominator to be its container's largest integer breaks the
legitimate 5821/6000, because the containers nest and the root group holds the
whole file. Fifty-four numbers verified outright and eighteen to eyeball is
worth more than a stricter rule that quietly rejects honest arithmetic.

Usage: .venv/bin/python scripts/claim_numbers.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from claimset import load_claims                                  # noqa: E402

DEC = re.compile(r"-?\d+\.\d+")
MAX_PAIRS = 400          # cap the pairwise expansion on huge evidence blocks


def numbers_in(text: str) -> list[str]:
    """The decimals as WRITTEN — trailing zeros carry the precision.

    Parsing first loses it: float("0.050") prints as "0.05", which reads as
    two decimals and sets a tolerance ten times too loose. At that width a
    scan over a few thousand candidate quotients will always find a hit, and
    it did — the uncited 0.050 in row 5's scope came back "supported" by
    129/2704 = 0.0477.
    """
    return list(dict.fromkeys(DEC.findall(text)))


def _walk(o, groups: list[list[float]], here: list[float]) -> None:
    """Collect numbers, grouped by the container they sit in.

    A group is one dict or list: the numbers an experiment wrote side by side.
    Differences are only meaningful within a group, which is what keeps this
    from accepting arithmetic coincidences between unrelated corners of a file.
    """
    if isinstance(o, dict):
        mine: list[float] = []
        for k, v in o.items():
            if isinstance(k, str):
                mine.extend(float(x) for x in DEC.findall(k))
            _walk(v, groups, mine)
        groups.append(mine)
        here.extend(mine)
    elif isinstance(o, list):
        mine = []
        for v in o:
            _walk(v, groups, mine)
        groups.append(mine)
        here.extend(mine)
    elif isinstance(o, bool):
        return
    elif isinstance(o, (int, float)):
        here.append(float(o))
    elif isinstance(o, str):
        here.extend(float(x) for x in DEC.findall(o))


def evidence_numbers(claim: dict) -> tuple[list[float], list[list[float]]]:
    """(every number, numbers grouped by container) over the cited files.

    Deliberately wider than the cited keys: the question here is whether the
    number EXISTS in the experiment that produced it, which is what an
    adjudicator's "this figure is not in the numbers" flag really means.
    """
    flat: list[float] = []
    groups: list[list[float]] = []
    seen = set()
    for path, _keys in [tuple(claim["src"])] + [tuple(x) for x in
                                                claim.get("extra", [])]:
        if path in seen:
            continue
        seen.add(path)
        p = ROOT / path
        if p.exists():
            _walk(json.loads(p.read_text()), groups, flat)
    return flat, groups


def supported(target: float, flat: list[float],
              groups: list[list[float]], tol: float) -> str | None:
    """How `target` is reachable, or None. Verbatim, then rate, then gap."""
    for v in flat:
        if abs(v - target) <= tol:
            return "verbatim"
    for g in groups:
        ints = [v for v in g if v == int(v) and abs(v) >= 1]
        for a in ints[:60]:
            for b in ints[:60]:
                if b and abs(a / b - abs(target)) <= tol:
                    return f"rate {a:g}/{b:g}"
    for g in groups:
        # every value in the container, including integral floats: a rebuilt
        # arm scoring exactly 1.0 is a measurement, and dropping it made the
        # 0.771 retrieval gap look uncited when the experiment measured it
        fl = sorted({round(v, 6) for v in g if abs(v) <= 1.5})[:60]
        for i, a in enumerate(fl):
            for b in fl[i + 1:]:
                if abs(abs(a - b) - abs(target)) <= tol:
                    return f"gap {a:g}-{b:g}"
    return None


def audit(claim: dict) -> list[tuple[str, str | None]]:
    flat, groups = evidence_numbers(claim)
    out = []
    for s in numbers_in(claim["claim"] + " " + claim["scope"]):
        tol = 0.5 * 10 ** -len(s.split(".")[-1])       # precision as written
        out.append((s, supported(float(s), flat, groups, tol)))
    return out


def main() -> int:
    """Three outcomes, not two — derived is not the same as cited.

    Only ABSENT is a hard failure. A number reached by rate or gap is
    reported for review rather than counted as clean: within a small
    container those derivations are usually the real quantity, but they are
    still a search over candidates, and calling a search result "supported"
    is how the first version passed all 14 claims including a wrong one.
    """
    explain = "--explain" in sys.argv
    claims = load_claims()
    absent_claims, n_verb, n_der, n_abs = 0, 0, 0, 0
    print(f"{len(claims)} claims — numbers asserted vs numbers cited")
    print("(verbatim = in a cited file; derived = computed from one, review "
          "it; absent = nowhere)\n")
    for c in claims:
        rows = audit(c)
        verb = [s for s, how in rows if how == "verbatim"]
        der = [(s, how) for s, how in rows if how and how != "verbatim"]
        miss = [s for s, how in rows if how is None]
        n_verb, n_der, n_abs = n_verb + len(verb), n_der + len(der), \
            n_abs + len(miss)
        flag = "ABSENT" if miss else ("review" if der else "ok")
        print(f"{flag:7s} row {c['row']:3s}  {len(verb)} verbatim, "
              f"{len(der)} derived, {len(miss)} absent")
        if der and (explain or miss):
            for s, how in der:
                print(f"          derived  {s:<9s} {how}")
        if miss:
            absent_claims += 1
            print(f"          ABSENT   {', '.join(miss)}")
    print(f"\n{n_verb} verbatim / {n_der} derived / {n_abs} absent")
    print(f"{absent_claims} of {len(claims)} claims assert a number no cited "
          f"file contains")
    return absent_claims


if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)
