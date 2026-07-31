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

from .canonical import (NONE, PRECISIONS, SOME, CanonError, canon_value,
                        norm_text, norm_time)

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
    """Keep only truth-conditional qualifiers; DROP everything unregistered.

    Dropping is the safe default and it is load-bearing, not incidental. A
    dropped qualifier imposes no restriction, so an unregistered one always
    overlaps. If unknown qualifiers instead defaulted to *disjoint*, any agent
    could make its claims permanently undisputable by attaching one junk
    qualifier — which is exactly the v0 loophole, re-entering through a side
    door. `test_unregistered_qualifier_cannot_evade_dispute` pins this.
    """
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
                    with_qualifiers=True, with_predicate=True) -> str:
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
    # An existential is not a ref, so it must never reach the closure — SOME
    # and NONE have no identity to resolve.
    if c.object is SOME or c.object is NONE:
        obj = canon_value(c.object_sort, c.object)
    elif c.object_sort == "entity":
        obj = ["entity", canon(c.object)]
    else:
        obj = canon_value(c.object_sort, c.object)
    doc = {"s": canon(c.subject), "o": obj}
    if with_predicate:
        doc["p"] = norm_text(c.predicate)
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


def _compatible_times(a: Claim, b: Claim) -> bool:
    """Do two time objects state the SAME moment at different precisions?

    Found by real data: 24 of 89 baseline conflicts on a real corpus were a
    functional predicate seeing `1953` and `1953-04-11` as contradictory birth
    dates. They are not. The coarser claim is refined by the finer one, and a
    system that reports "Andrew Wiles's birth date is disputed" because one
    source gave only the year has invented a disagreement.

    The rule is the same asymmetry as everywhere else in this model: a coarser
    statement is entailed by a finer one, so **two time values conflict only
    when their intervals are DISJOINT**. Note this does not undo the
    canonicaliser's refusal to zero-fill — refusing to *invent* day precision
    and recognising that a year *contains* a day are different questions, and
    the model needs both answers.
    """
    if a.object_sort != "time" or b.object_sort != "time":
        return False
    try:
        ia = _interval(a.object.get("t"), a.object.get("p", "day"))
        ib = _interval(b.object.get("t"), b.object.get("p", "day"))
    except (CanonError, AttributeError, TypeError):
        return False
    return ia[0] < ib[1] and ib[0] < ia[1]


def _existential(a: Claim, b: Claim):
    """Conflicts involving SOME / NONE.

    These hold for ANY predicate, not only functional ones: "Alice has no
    children" contradicts "Alice's child is Bob" even though `has_child` admits
    many objects. Routing them through the functional rule would have missed
    exactly the claims a personal store needs on day one — no allergies, no
    dietary restrictions.
    """
    if not (a.polarity and b.polarity):
        return None                       # negated existentials: see below
    ma = a.object if a.object in (SOME, NONE) else None
    mb = b.object if b.object in (SOME, NONE) else None
    if ma is None and mb is None:
        return None
    if ma is NONE and mb is None:
        return Conflict("existential", a, b)      # NONE vs a concrete object
    if mb is NONE and ma is None:
        return Conflict("existential", b, a)
    if {ma, mb} == {SOME, NONE}:
        return Conflict("existential", a, b)
    return None                           # SOME vs concrete: entailed, no news


def _subsumption_conflicts(claims, closure, lattice) -> list[Conflict]:
    """`(X, mother_of, Y, +)` versus `(X, parent_of, Y, −)`.

    A flat contradiction that predicate-string grouping cannot see. The rule is
    one-directional, like everything else about the lattice: a POSITIVE claim
    on P contradicts a NEGATIVE claim on Q exactly when P entails Q. The
    converse does not hold — `¬mother_of` is perfectly consistent with
    `parent_of`, because the parent may be the father.
    """
    canon = closure.canonicalise if closure is not None else (lambda r: r)
    out, by_so = [], collections.defaultdict(list)
    for c in claims:
        by_so[(canon(c.subject),
               proposition_key(c, closure, with_polarity=False,
                               with_qualifiers=False, with_predicate=False)
               )].append(c)
    for _, group in sorted(by_so.items()):
        for a in group:
            for b in group:
                if a is b or not a.polarity or b.polarity:
                    continue                      # need a positive and a negative
                pa, pb = norm_text(a.predicate), norm_text(b.predicate)
                if pa == pb or not lattice.entails(pa, pb):
                    continue                      # same-predicate case handled above
                if scopes_overlap(_tc(a.qualifiers), _tc(b.qualifiers)):
                    out.append(Conflict("subsumption", a, b))
    return out


def conflicts(claims, closure=None, functional=frozenset(),
              lattice=None) -> list[Conflict]:
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
                ex = _existential(a, b)
                if ex is not None:
                    out.append(ex)
                elif same_obj and a.polarity != b.polarity:
                    out.append(Conflict("polarity", a, b))
                elif (not same_obj and pred in functional
                      and a.polarity and b.polarity
                      and not _compatible_times(a, b)):
                    out.append(Conflict("functional", a, b))
    if lattice is not None:
        out += _subsumption_conflicts(claims, closure, lattice)
    return out
