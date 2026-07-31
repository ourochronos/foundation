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

# Sorts are an OPEN registry with a CLOSED encoding contract: adding one ships
# a canonical byte encoding, it does not change the grammar. `claim_ref` is
# load-bearing three times over — retraction, dimensional confidence, and
# entity splits all need to point at a claim (model v1 §3).
SORTS = ("entity", "text", "quantity", "time", "act_ref", "prop_ref")

# `claim_ref` was one sort in v1 and that was wrong: the two things it pointed
# at resolve DIFFERENTLY, and conflating them meant every consumer had to
# runtime-dispatch while a mis-typed ref silently changed meaning.
#
#   act_ref   resolves to exactly that act. The closure is never applied.
#             Retraction and extraction-fidelity target this — they are about
#             a specific thing somebody did.
#   prop_ref  is STORED as an assertion address and resolves to the whole
#             proposition fibre containing it, under the current closure.
#             Belief and reliability target this — they are about the world.
#
# Both are stored syntactically, so both stay stable and commitment-grade;
# only the resolution rule differs. That is what dissolves the v1 dilemma
# ("stable addresses cannot name mutable proposition keys"): the address is
# stable, and the mutability lives in how it is read.


class _Marker:
    """An existential object. Not a value of any sort, and never confusable
    with one, because it canonicalises under its own head."""
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


# "Alice has no children" is NOT (alice, has_child, bob, -): polarity negates
# one triple and cannot say that no object exists. And a safe decomposition of
# a composite predicate ("grandmother" implies SOME parent) needs the positive
# form. Same missing construct in two polarities, so one pair fixes both.
SOME = _Marker("SOME")
NONE = _Marker("NONE")

# ---------------------------------------------------------------- addresses --
# A content address carries its algorithm. Zero-knowledge aggregation is the
# stated end goal and SHA-256 is expensive inside a circuit, so a move to an
# algebraic hash (Poseidon and relatives) is foreseeable. Without the tag,
# changing hash function means rewriting every content address in every
# federated store — precisely the global rebuild this design exists to forbid.
# One byte now; unfixable later (model v1 §9b).
ALGOS = {"sha256": (b"\x01", hashlib.sha256)}
DEFAULT_ALGO = "sha256"
_BY_TAG = {tag: name for name, (tag, _) in ALGOS.items()}

# Domain separation. Without it an assertion digest and a claim-act digest are
# drawn from one space and could be substituted for each other, and a payload
# hashed under schema v1 could be reinterpreted under v2 with different field
# meanings. Both are standard commitment failures and both are unfixable after
# addresses are in circulation, so the kind and the schema version are hashed
# IN rather than merely stored alongside.
SCHEMA_VERSION = "1"
CONTENT_KINDS = ("assertion", "claim_act", "predicate",
                 "interpretation", "commitment", "event")

# `local` is deliberately NOT a usable namespace. Every store would mint
# `local:owner` for a different person, so a union of two stores silently
# fuses two subjects — or falsely dedupes their claims when the objects happen
# to match. A namespace must be globally unique BEFORE any claim leaves the
# machine, because the ref is baked into an immutable content address and
# cannot be rewritten later without invalidating every address that quotes it.
RESERVED_NAMESPACES = {"local", "self", "me", "store", "tmp", "test"}

# `event:` is exempt from store-scoping because an event id IS a content
# address over its identifying roles, so it is globally unique by construction
# — which is the entire point: two extractors that find the same event must
# mint the same id or federation fails on every n-ary fact.
CONTENT_NAMESPACES = {"event"}
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
    ns, _, rest = r.partition(":")
    ns = ns.lower()
    if ns in RESERVED_NAMESPACES and ns not in CONTENT_NAMESPACES:
        raise CanonError(
            f"namespace {ns!r} is not globally unique: every store mints "
            f"{ns}:owner for a different subject, so a merge would fuse them. "
            f"Mint a store-scoped namespace instead (see mint_namespace).")
    return f"{ns}:{rest}"


def norm_address(a) -> str:
    """A content address as 'algo:hex'. Accepts the tagged bytes form too.

    Rejects a bare digest: an untagged address is the thing that cannot be
    migrated later, so it is refused at the door rather than becoming a
    permanent commitment to one hash function.
    """
    if isinstance(a, (bytes, bytearray)):
        tag, digest = bytes(a[:1]), bytes(a[1:])
        if tag not in _BY_TAG or not digest:
            raise CanonError(f"unknown or empty content address: {a!r}")
        return f"{_BY_TAG[tag]}:{digest.hex()}"
    if not isinstance(a, str):
        raise CanonError(f"claim_ref needs str|bytes, got {type(a).__name__}")
    algo, _, hexd = a.strip().partition(":")
    if algo not in ALGOS or not hexd:
        raise CanonError(f"claim_ref must be 'algo:hex' with algo in "
                         f"{sorted(ALGOS)}, got {a!r}")
    try:
        bytes.fromhex(hexd)
    except ValueError as e:
        raise CanonError(f"claim_ref digest not hex: {a!r}") from e
    return f"{algo}:{hexd.lower()}"


def norm_predicate(p) -> list:
    """A predicate reference as [uri, definition_address | null].

    v1 keyed predicate identity on (uri, definition_hash) and then stored only
    the uri in assertions, so two definitions under one uri were
    indistinguishable despite the document claiming merge-safety. Passing a
    bare string is still allowed and canonicalises with an explicit null: it
    records that the claim named no definition version, rather than pretending
    it named one.
    """
    if isinstance(p, str):
        return [norm_text(p), None]
    if isinstance(p, (tuple, list)) and len(p) == 2:
        return [norm_text(p[0]), norm_address(p[1])]
    raise CanonError(f"predicate must be uri or (uri, definition_address), "
                     f"got {p!r}")


def canon_value(sort: str, value) -> list:
    """A sort-tagged canonical value. Always [sort, ...] so sorts never mix."""
    if value is SOME or value is NONE:
        # Distinct head, so an existential can never collide with a real value
        # of the same sort. The sort is retained: "no children" and "no
        # birth date" are different claims.
        return [value.name.lower(), sort]
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
    if sort in ("act_ref", "prop_ref"):
        return [sort, norm_address(value)]
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
           "p": norm_predicate(predicate),
           "o": canon_value(object_sort, obj),
           "n": POLARITY[bool(polarity)],
           "q": quals}
    return json.dumps(doc, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def digest_of(payload: bytes, kind: str, algo: str = DEFAULT_ALGO) -> bytes:
    """Domain-separated tagged digest over an arbitrary canonical payload."""
    if algo not in ALGOS:
        raise CanonError(f"unknown hash algorithm {algo!r}")
    if kind not in CONTENT_KINDS:
        raise CanonError(f"unknown content kind {kind!r}; kinds are "
                         f"{CONTENT_KINDS}")
    tag, fn = ALGOS[algo]
    pre = f"{kind}\x00{SCHEMA_VERSION}\x00".encode()
    return tag + fn(pre + payload).digest()


def mint_namespace(store_id: str) -> str:
    """A globally unique namespace for one store's locally-minted refs.

    Callers pass a store identifier that is unique by construction — a UUID, a
    public key fingerprint, a domain. This exists so that `local:` never has to
    work: a ref is frozen into content addresses the moment it is used, so
    disambiguating it after the fact is not available.
    """
    s = norm_text(store_id).lower().replace(" ", "-")
    if not s or ":" in s or s in RESERVED_NAMESPACES:
        raise CanonError(f"bad store id {store_id!r}")
    return f"s.{s}"


def event_address(event_type: str, roles: dict, identifying,
                  algo: str = DEFAULT_ALGO) -> str:
    """A globally stable id for an n-ary fact, derived from its KEY roles.

    "Alice sold the house to Bob for $10 in 2020" can be reified as
    `(alice, sold, house, {to, price})` or `(alice, sold_to, bob, {item,
    price})`. Different addresses, no dedup, agreement never sees agreement —
    federation fails on every n-ary fact. So an event gets an entity of its
    own, and its identity is a content address over its role bindings.

    **Identity comes from a declared subset of roles, not all of them.** Two
    extractors rarely recover the same role set: one gets seller/item/buyer,
    another also gets the price. Hashing everything would make those different
    events. Hashing the roles the event *type* declares as identifying makes
    them the same event with different amounts known about it — and the extra
    roles become ordinary claims about that entity.

    `roles` maps role name -> (sort, value). `identifying` names the key roles;
    every one of them must be present, because an event missing part of its
    key cannot be given a stable identity and guessing one would fabricate
    identity rather than admit ignorance.
    """
    ident = tuple(identifying)
    if not ident:
        raise CanonError(f"event type {event_type!r} declares no identifying "
                         f"roles, so no two extractions could ever agree")
    missing = [r for r in ident if r not in roles]
    if missing:
        raise CanonError(f"event of type {event_type!r} is missing "
                         f"identifying role(s) {missing}; it cannot be given a "
                         f"stable identity")
    body = {"t": norm_text(event_type),
            "r": sorted([norm_text(r), canon_value(*roles[r])] for r in ident)}
    payload = json.dumps(body, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    tag, fn = ALGOS[algo]
    return f"event:{algo}.{fn(payload).hexdigest()}"


def commit(content_addr: bytes, salt: bytes, algo: str = DEFAULT_ALGO) -> bytes:
    """A SALTED public commitment over a private content address.

    A content address is binding but not hiding, and the claims in a personal
    store come from tiny spaces — enumerate the diagnosis codes, hash each
    against the shared seed vocabulary, match the published log. Shared
    vocabulary makes proposition keys work and makes that attack easy, so the
    two are at war unless what gets published is salted.

    It is also the **deletion mechanism**, which append-only otherwise makes
    impossible. Destroying the payload and its salt leaves a commitment nobody
    can ever open or dictionary-attack, while the address itself remains so
    references do not dangle and the record still shows that something was
    asserted and later erased. A person's agent needs this for facts about
    third parties, coerced entries, and legal erasure.
    """
    if len(salt) < 16:
        raise CanonError("salt must be at least 16 bytes or the commitment is "
                         "dictionary-attackable, which is the whole point")
    return digest_of(bytes(salt) + bytes(content_addr), "commitment", algo)


def address(*a, algo: str = DEFAULT_ALGO, kind: str = "assertion", **k) -> bytes:
    """Domain-separated content address: algo byte followed by the digest."""
    return digest_of(canonical_form(*a, **k), kind, algo)


def hexid(*a, **k) -> str:
    """Text form, 'algo:hex' — the form that goes in a claim_ref."""
    return norm_address(address(*a, **k))
