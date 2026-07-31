"""Proposition keys, agreement, and contradiction (model v1 §1, §2).

Two failures in v0, both found blind, both fixed here and both tested against
the reviewers' own break cases in `tests/test_conflict.py`.

**1. Identity.** Conflict detection keyed on raw subject strings, so

    Store A:  (local:a1, date_of_birth, 1907-05-22)
    Store B:  (local:b9, date_of_birth, 1907-05-23)   + sameAs

merged to two assertions and *zero* conflicts. Here the **proposition key** is
computed over class representatives, so the conflict appears exactly when the
identity claim is accepted — and disappears again if it is retracted, which is
the honest behaviour for a defeasible claim.

**2. Scope.** v0 required *byte-identical* qualifier sets, so

    (X, member_of, Y, −, {})   vs   (X, member_of, Y, +, {valid_time: 1980})

never conflicted, and any agent could make its claims undisputable by adding
one innocuous qualifier. Conflict now tests whether scopes **overlap**, and an
**absent qualifier means unrestricted** — an unqualified claim overlaps every
scoped one, which is what makes the loophole close.

Agreement is `COUNT(DISTINCT claimant)` over a proposition key, so two stores
that independently extracted one fact pool into one countable agreement rather
than looking like two separate facts.
"""
from __future__ import annotations

import collections
import json
from dataclasses import dataclass, field

from .canonical import (PRECISIONS, CanonError, canon_value, norm_text,
                        norm_time)

# Qualifiers that restrict WHEN/WHERE/UNDER WHAT a proposition holds. These
# enter the proposition key and participate in conflict logic. Everything else
# is annotation and belongs on the claim act, not on the proposition.
TRUTH_CONDITIONAL = {"valid_time", "valid_from", "valid_until",
                     "valid_place", "under_assumption"}
# Unbounded ends as 6-tuples so every comparison stays tuple-vs-tuple. Mixing
# a float infinity with a (y,m,d,h,m,s) tuple raises rather than comparing, and
# an unbounded qualifier is the COMMON case — an absent bound must not be the
# thing that crashes the overlap test.
_NEG_INF = (-10 ** 9,) * 6
_POS_INF = (10 ** 9,) * 6


def _interval(value, precision: str) -> tuple:
    """The half-open interval a time value denotes AT ITS PRECISION.

    A point with a precision is already an interval: 'year 2009' is
    [2009, 2010), not the instant 2009-01-01T00:00:00. Treating it as an
    instant is how a year-precision claim stops overlapping anything.
    """
    s = norm_time(value, precision)
    lo = tuple(int(x) for x in s.replace("T", "-").replace(":", "-").split("-"))
    lo = lo + (0,) * (6 - len(lo))
    i = PRECISIONS.index(precision)
    hi = list(lo)
    hi[i] += 1
    return (lo, tuple(hi))


def _time_bounds(quals: dict) -> tuple:
    """Collapse valid_time / valid_from / valid_until into one interval."""
    if "valid_time" in quals:
        v = quals["valid_time"]
        return _interval(v.get("t", v), v.get("p", "day"))
    lo, hi = _NEG_INF, _POS_INF
    if "valid_from" in quals:
        v = quals["valid_from"]
        lo = _interval(v.get("t", v), v.get("p", "day"))[0]
    if "valid_until" in quals:
        v = quals["valid_until"]
        hi = _interval(v.get("t", v), v.get("p", "day"))[1]
    return (lo, hi)


def scopes_overlap(qa: dict, qb: dict) -> bool:
    """Do two qualifier sets describe conditions that can hold together?

    An ABSENT qualifier is unrestricted and therefore overlaps everything. That
    single rule is what stops an agent evading dispute by adding a qualifier
    nobody else used.
    """
    ta, tb = _time_bounds(qa), _time_bounds(qb)
    if not (ta[0] < tb[1] and tb[0] < ta[1]):
        return False
    for k in ("valid_place", "under_assumption"):
        va, vb = qa.get(k), qb.get(k)
        if va is not None and vb is not None and va != vb:
            return False          # different stated scope; both may hold
    return True


def _tc(qualifiers) -> dict:
    out = {}
    for q in qualifiers or ():
        name = norm_text(q[0])
        if name in TRUTH_CONDITIONAL:
            out[name] = q[2]
    return out


@dataclass(frozen=True)
class Evidence:
    """Why a claimant holds a claim.

    `span` quotes a document, `observation` records a direct channel, and
    `premise` names the claims an inference was drawn from. A derived claim
    has premise evidence and no source of its own, which is what §5 of
    docs/24 turns on.
    """
    kind: str                       # 'span' | 'premise' | 'observation'
    source: str = ""                # document id | channel
    premises: tuple = ()            # claim hashes


@dataclass(frozen=True)
class Claim:
    """One assertion plus who claimed it. `hash` is over RAW refs (immutable)."""
    subject: str
    predicate: str
    object_sort: str
    object: object
    polarity: bool = True
    qualifiers: tuple = ()
    claimant: str = "local:me"
    hash: str = ""
    evidence: tuple = ()


def proposition_key(c: Claim, closure=None, *, with_polarity=True,
                    with_qualifiers=True) -> str:
    """Identity of the PROPOSITION, modulo the accepted identity closure.

    Derived, not stored: it moves when the closure moves, which is exactly why
    it belongs in Layer 4 and the assertion hash does not.

    `with_qualifiers=False` gives the SCOPE-FREE key — same subject, predicate
    and object, ignoring when/where it is claimed to hold. Conflict detection
    needs this and agreement must not use it: scope overlap is tested
    separately by `scopes_overlap`, so folding qualifiers into the equality
    test as well would re-open the exact loophole v1 exists to close (a claim
    scoped to 1980 would stop "being about" the same thing as an unscoped one
    and could never contradict it). Agreement keeps the full key, because a
    claim about 1980 and an unscoped claim are genuinely different
    propositions and must not pool into one count.
    """
    canon = closure.canonicalise if closure is not None else (lambda r: r)
    obj = (["entity", canon(c.object)] if c.object_sort == "entity"
           else canon_value(c.object_sort, c.object))
    doc = {"s": canon(c.subject), "p": norm_text(c.predicate), "o": obj}
    if with_qualifiers:
        doc["q"] = sorted(
            [norm_text(k), canon_value("entity", v) if isinstance(v, str)
             and ":" in v and k == "valid_place" else str(v)]
            for k, v in _tc(c.qualifiers).items())
    if with_polarity:
        doc["n"] = "+" if c.polarity else "-"
    return json.dumps(doc, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def independent_sources(c: Claim, by_hash: dict, _seen=None) -> set[str]:
    """The distinct EVIDENCE sources behind a claim, folding premises.

    A derived claim contributes the sources of its premises, transitively —
    never itself. Without this, agreement is manufacturable at zero cost: one
    store deriving the same conclusion three ways, or three agents each
    deriving it once, reports an agreement of 3 from a single underlying
    document. Agreement is the entire epistemic payoff of federation, so a
    local process that inflates it for free is not a small bug.

    A claim with no evidence at all falls back to its claimant, which is the
    weakest honest reading: somebody asserted it and named no source.
    """
    _seen = _seen if _seen is not None else set()
    if c.hash and c.hash in _seen:
        return set()                       # premise cycle; contributes nothing
    if c.hash:
        _seen.add(c.hash)
    if not c.evidence:
        return {f"claimant:{c.claimant}"}
    out = set()
    for e in c.evidence:
        if e.kind in ("span", "observation"):
            out.add(f"{e.kind}:{e.source}")
        elif e.kind == "premise":
            for h in e.premises:
                p = by_hash.get(h)
                if p is not None:
                    out |= independent_sources(p, by_hash, _seen)
    return out


def agreement(claims, closure=None) -> dict[str, set[str]]:
    """proposition key -> distinct INDEPENDENT SOURCES.

    Counts evidence, not claims. Two agents who both derived a fact from the
    same paper are one source, which is what "independent" was always supposed
    to mean.
    """
    claims = list(claims)
    by_hash = {c.hash: c for c in claims if c.hash}
    out = collections.defaultdict(set)
    for c in claims:
        out[proposition_key(c, closure)] |= independent_sources(c, by_hash)
    return dict(out)


@dataclass
class Conflict:
    kind: str                       # 'polarity' | 'functional'
    left: Claim
    right: Claim

    def __repr__(self):             # readable in test failures
        return (f"<{self.kind}: {self.left.subject} {self.left.predicate} "
                f"{self.left.object!r} vs {self.right.object!r}>")


def conflicts(claims, closure=None, functional=frozenset()) -> list[Conflict]:
    """Detected, never resolved. Both sides survive; the query reports both.

    `functional` names predicates admitting at most one object per subject —
    the only piece of predicate algebra v1 keeps, because it is how genuine
    disagreement is detected without anyone writing an explicit negation.
    """
    canon = closure.canonicalise if closure is not None else (lambda r: r)
    out, by_sp = [], collections.defaultdict(list)
    for c in claims:
        by_sp[(canon(c.subject), norm_text(c.predicate))].append(c)
    for (_, pred), group in sorted(by_sp.items()):
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if not scopes_overlap(_tc(a.qualifiers), _tc(b.qualifiers)):
                    continue
                same_obj = (
                    proposition_key(a, closure, with_polarity=False,
                                    with_qualifiers=False)
                    == proposition_key(b, closure, with_polarity=False,
                                       with_qualifiers=False))
                if same_obj and a.polarity != b.polarity:
                    out.append(Conflict("polarity", a, b))
                elif (not same_obj and pred in functional
                      and a.polarity and b.polarity):
                    out.append(Conflict("functional", a, b))
    return out
