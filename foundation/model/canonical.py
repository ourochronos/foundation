"""Canonical form and content addressing for assertions (model v0, §7).

The whole merge story rests on one property:

    two independent stores that extract the same claim must produce
    BYTE-IDENTICAL canonical forms, and therefore the same hash

If that holds, merging stores is a set union of immutable rows — a grow-only
set, the simplest CRDT there is, with no coordination and no merge algorithm to
get wrong. If it fails even occasionally, merge silently stops deduplicating:
the same fact accumulates as distinct assertions, agreement becomes
uncountable, and contradiction detection misses conflicts because the two sides
no longer share a subject key. Nothing raises an error. The store just quietly
gets worse.

So canonicalisation is specified and tested rather than assumed. The known ways
it goes wrong, each handled explicitly below:

- **Unicode**: "Ångström" has two encodings (NFC/NFD) that render identically.
- **Numbers**: 1, 1.0, 1.00, 1e0 are the same quantity; float repr is not
  portable across languages.
- **Time**: the same instant in two timezones; and 2009 (year precision) is not
  2009-01-01 (day precision) — a claim true of a year is not a claim about its
  first day.
- **Key and qualifier order**: dict iteration order is not a wire format.
- **Whitespace**: leading/trailing and interior runs from sloppy extraction.

This module is deliberately dependency-free and small enough to reimplement in
another language from the docstring, which is a requirement rather than a
nicety: a federation partner running different code must agree byte for byte.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

SORTS = ("entity", "text", "quantity", "time")
POLARITY = {True: "+", False: "-"}
# ISO-8601 precision labels, coarsest first. A time value carries its own
# precision because "true in 2009" and "true on 2009-01-01" are different
# claims and must not collide.
PRECISIONS = ("year", "month", "day", "hour", "minute", "second")
_WS = re.compile(r"\s+")


class CanonError(ValueError):
    """Raised when a value cannot be canonicalised. Never silently coerced."""


def norm_text(s: str) -> str:
    """NFC, collapse internal whitespace runs, strip ends.

    NFC rather than NFD because it is the form the web is normalising toward
    and it is shorter; the choice matters less than that it is *stated*.
    """
    if not isinstance(s, str):
        raise CanonError(f"text sort needs str, got {type(s).__name__}")
    return _WS.sub(" ", unicodedata.normalize("NFC", s)).strip()


def norm_number(n) -> str:
    """Shortest exact decimal string: 1, 1.0, 1.00, '1e0' -> '1'.

    Decimal, not float: float('0.1') is not 0.1, and its repr differs across
    languages. Rejects inf/nan rather than encoding them.
    """
    try:
        d = Decimal(str(n))
    except (InvalidOperation, ValueError) as e:
        raise CanonError(f"not a number: {n!r}") from e
    if not d.is_finite():
        raise CanonError(f"non-finite quantity: {n!r}")
    d = d.normalize()
    # normalize() gives 1E+1 for 10; expand to plain notation, no exponent.
    sign, digits, exp = d.as_tuple()
    if exp > 0:
        d = Decimal((sign, digits + (0,) * exp, 0))
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("", "-", "-0", "0", "-0.0") else s


_PARTIAL = ((re.compile(r"^\d{4}$"), "year", "-01-01"),
            (re.compile(r"^\d{4}-\d{2}$"), "month", "-01"))


def _granularity(s: str) -> str:
    """How precise the WRITTEN value actually is, independent of what is claimed."""
    for rx, g, _ in _PARTIAL:
        if rx.match(s):
            return g
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return "day"
    body = s.split("+")[0].split("Z")[0]
    if "T" not in body:
        raise CanonError(f"unrecognised time shape {s!r}")
    clock = body.split("T", 1)[1]
    return {0: "hour", 1: "minute"}.get(clock.count(":"), "second")


def norm_time(t: str | datetime, precision: str) -> str:
    """UTC ISO-8601 truncated to the stated precision, which is carried along.

    Truncation is by precision label, not by zero-filling: a year-precision
    claim canonicalises to '2009' and can never collide with a day-precision
    claim about 2009-01-01.

    **Partial dates are first-class.** '2009' and '2009-01' are how a
    year- or month-precision fact is actually written; requiring '2009-01-01'
    would force every such claim to invent a January the 1st.

    **Claiming more precision than the value carries is an ERROR, not a
    zero-fill.** `('2009', 'day')` is rejected rather than silently becoming
    2009-01-01 — inventing a date nobody asserted is the fabrication this
    whole store exists to prevent, and it is exactly how a year-precision
    fact ends up indistinguishable from a New Year's Day fact.

    Timezone note: a value written with an explicit offset is an instant and
    is converted to UTC, which can shift its date. A naive value is treated as
    already-UTC and never shifts, so plain calendar dates behave as written.
    """
    if precision not in PRECISIONS:
        raise CanonError(f"unknown precision {precision!r}")
    if isinstance(t, str):
        s = t.strip().replace("Z", "+00:00")
        have = _granularity(s)
        if PRECISIONS.index(precision) > PRECISIONS.index(have):
            raise CanonError(
                f"time {t!r} carries {have} precision; cannot claim "
                f"{precision} without inventing a value")
        for rx, _, pad in _PARTIAL:            # pad only to make it parseable;
            if rx.match(s):                    # truncation discards the padding
                s += pad
                break
        try:
            dt = datetime.fromisoformat(s)
        except ValueError as e:
            raise CanonError(f"unparseable time {t!r}") from e
    elif isinstance(t, datetime):
        dt = t
    else:
        raise CanonError(f"time sort needs str|datetime, got {type(t).__name__}")
    dt = (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None
          else dt.astimezone(timezone.utc))
    cut = {"year": "%Y", "month": "%Y-%m", "day": "%Y-%m-%d",
           "hour": "%Y-%m-%dT%H", "minute": "%Y-%m-%dT%H:%M",
           "second": "%Y-%m-%dT%H:%M:%S"}[precision]
    return dt.strftime(cut)


def norm_ref(r: str) -> str:
    """Namespaced entity reference: 'wikidata:Q42', 'local:7f3a'.

    The namespace is mandatory. An unnamespaced id is exactly the thing that
    collides on federation, so it is rejected at the door rather than becoming
    someone else's merge bug.
    """
    if not isinstance(r, str):
        raise CanonError(f"entity ref needs str, got {type(r).__name__}")
    r = unicodedata.normalize("NFC", r).strip()
    if ":" not in r or r.startswith(":") or r.endswith(":"):
        raise CanonError(f"entity ref must be 'namespace:id', got {r!r}")
    ns, _, local = r.partition(":")
    return f"{ns.lower()}:{local}"


def canon_value(sort: str, value) -> list:
    """A sort-tagged canonical value. Always [sort, ...] so sorts never mix."""
    if sort == "entity":
        return ["entity", norm_ref(value)]
    if sort == "text":
        return ["text", norm_text(value)]
    if sort == "quantity":
        if not isinstance(value, dict) or "n" not in value:
            raise CanonError("quantity needs {'n': number, 'u': unit|None}")
        u = value.get("u")
        return ["quantity", norm_number(value["n"]),
                norm_text(u) if u is not None else None]
    if sort == "time":
        if not isinstance(value, dict) or "t" not in value:
            raise CanonError("time needs {'t': ..., 'p': precision}")
        p = value.get("p", "day")
        return ["time", norm_time(value["t"], p), p]
    raise CanonError(f"unknown sort {sort!r}; sorts are closed: {SORTS}")


def canonical_form(subject: str, predicate: str, object_sort: str, obj,
                   polarity: bool = True, qualifiers=()) -> bytes:
    """The bytes that get hashed. Deterministic across processes and machines.

    Qualifiers are sorted by their own canonical encoding, so the order they
    were extracted in cannot change the hash.
    """
    quals = []
    for q in qualifiers or ():
        if len(q) != 3:
            raise CanonError("qualifier is (predicate, sort, value)")
        qp, qs, qv = q
        quals.append([norm_text(qp), canon_value(qs, qv)])
    quals.sort(key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
    doc = {"s": norm_ref(subject),
           "p": norm_text(predicate),
           "o": canon_value(object_sort, obj),
           "n": POLARITY[bool(polarity)],
           "q": quals}
    return json.dumps(doc, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def assertion_hash(*a, **k) -> bytes:
    return hashlib.sha256(canonical_form(*a, **k)).digest()


def hexid(*a, **k) -> str:
    return assertion_hash(*a, **k).hex()
