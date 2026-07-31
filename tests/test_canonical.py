"""Adversarial tests for content addressing (model v0 §7).

These are written to BREAK canonicalisation, not to demonstrate it. The failure
mode being guarded against is silent: if two stores disagree on the bytes for
one claim, nothing raises — merge just stops deduplicating that claim, and
contradiction detection stops seeing the two sides as being about the same
thing. So every known way to write the same fact differently gets a test.

The two directions matter equally:
  - MUST COLLIDE: the same claim written differently -> identical hash
  - MUST NOT COLLIDE: different claims -> different hash (a canonicaliser that
    is too aggressive silently merges facts that are not the same, which is
    worse than failing to dedupe)
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from foundation.model.canonical import (                          # noqa: E402
    CanonError, canonical_form, hexid, norm_number, norm_text)

Q = "wikidata:Q42"


def h(*a, **k):
    return hexid(*a, **k)


# ----------------------------------------------------------------- collide --
def test_unicode_nfc_nfd_collide():
    """'Ångström' has two encodings that render identically."""
    nfc, nfd = "Ångström", "Ångström"
    assert nfc != nfd
    assert h(Q, "named", "text", nfc) == h(Q, "named", "text", nfd)


def test_whitespace_variants_collide():
    for v in ("Douglas Adams", "  Douglas Adams  ", "Douglas  Adams",
              "Douglas\tAdams", "Douglas\nAdams"):
        assert h(Q, "named", "text", v) == h(Q, "named", "text", "Douglas Adams")


def test_number_forms_collide():
    base = h(Q, "height", "quantity", {"n": 1, "u": "m"})
    for v in (1, 1.0, "1", "1.0", "1.00", "1e0", "0.1e1", " 1 "):
        assert h(Q, "height", "quantity", {"n": v, "u": "m"}) == base, v


def test_timezone_variants_collide():
    a = {"t": "2009-01-20T17:00:00+00:00", "p": "second"}
    b = {"t": "2009-01-20T12:00:00-05:00", "p": "second"}
    assert h(Q, "at", "time", a) == h(Q, "at", "time", b)
    z = {"t": "2009-01-20T17:00:00Z", "p": "second"}
    assert h(Q, "at", "time", z) == h(Q, "at", "time", a)


def test_qualifier_order_collides():
    """Extraction order must not reach the wire format."""
    q1 = [("valid_time", "time", {"t": "2009", "p": "year"}),
          ("valid_place", "entity", "wikidata:Q30")]
    assert h(Q, "held", "text", "x", True, q1) == \
           h(Q, "held", "text", "x", True, list(reversed(q1)))


def test_namespace_case_collides():
    assert h("WikiData:Q42", "p", "text", "v") == h("wikidata:Q42", "p", "text", "v")


def test_datetime_object_and_string_collide():
    dt = datetime(2009, 1, 20, 17, 0, tzinfo=timezone.utc)
    other = dt.astimezone(timezone(timedelta(hours=9)))
    assert h(Q, "at", "time", {"t": dt, "p": "second"}) == \
           h(Q, "at", "time", {"t": other, "p": "second"})


# ------------------------------------------------------------- NOT collide --
def test_polarity_separates():
    assert h(Q, "member_of", "entity", "wikidata:Q1", True) != \
           h(Q, "member_of", "entity", "wikidata:Q1", False)


def test_time_precision_separates():
    """'true in 2009' is not 'true on 2009-01-01' — the core of law #10."""
    assert h(Q, "at", "time", {"t": "2009-01-01", "p": "year"}) != \
           h(Q, "at", "time", {"t": "2009-01-01", "p": "day"})


def test_sorts_do_not_mix():
    """The string '42' and the quantity 42 are different objects."""
    assert h(Q, "p", "text", "42") != h(Q, "p", "quantity", {"n": 42, "u": None})


def test_unit_separates():
    assert h(Q, "h", "quantity", {"n": 1, "u": "m"}) != \
           h(Q, "h", "quantity", {"n": 1, "u": "km"})
    assert h(Q, "h", "quantity", {"n": 1, "u": None}) != \
           h(Q, "h", "quantity", {"n": 1, "u": "m"})


def test_qualifiers_change_identity():
    """A scope qualifies a claim; it must not be droppable without notice."""
    q = [("valid_time", "time", {"t": "2009", "p": "year"})]
    assert h(Q, "held", "text", "x") != h(Q, "held", "text", "x", True, q)


def test_namespace_is_significant():
    assert h("s.alice:Q42", "p", "text", "v") != h("wikidata:Q42", "p", "text", "v")


def test_ambiguous_namespaces_rejected():
    """Every store mints local:owner for a different person, so a union would
    fuse two subjects. The ref is frozen into an immutable address, so this
    cannot be disambiguated after the fact — it must be refused up front."""
    from foundation.model.canonical import RESERVED_NAMESPACES, mint_namespace
    for ns in sorted(RESERVED_NAMESPACES):
        with pytest.raises(CanonError, match="globally unique"):
            h(f"{ns}:owner", "p", "text", "v")
    a, b = mint_namespace("alice-laptop"), mint_namespace("bob-phone")
    assert a != b
    assert h(f"{a}:owner", "p", "text", "v") != h(f"{b}:owner", "p", "text", "v")


def test_addresses_are_domain_separated():
    """An assertion digest must never be substitutable for a claim-act digest,
    and a v1 payload must never be reinterpretable under a later schema."""
    from foundation.model.canonical import address, digest_of
    args = ("wikidata:Q42", "p", "text", "v")
    assert address(*args, kind="assertion") != address(*args, kind="claim_act")
    with pytest.raises(CanonError):
        address(*args, kind="not_a_kind")
    body = b"x"
    assert digest_of(body, "assertion") != digest_of(body, "predicate")


def test_qualifier_predicate_separates():
    a = [("valid_time", "entity", "wikidata:Q30")]
    b = [("valid_place", "entity", "wikidata:Q30")]
    assert h(Q, "p", "text", "v", True, a) != h(Q, "p", "text", "v", True, b)


# ------------------------------------------------------------------ reject --
def test_unnamespaced_ref_rejected():
    """The exact thing that collides on federation, refused at the door."""
    with pytest.raises(CanonError):
        h("Q42", "p", "text", "v")
    for bad in (":Q42", "wikidata:", 42, None):
        with pytest.raises(CanonError):
            h(bad, "p", "text", "v")


def test_unknown_sort_rejected():
    with pytest.raises(CanonError):
        h(Q, "p", "boolean", True)


def test_non_finite_quantity_rejected():
    for bad in (float("inf"), float("nan"), "NaN", "Infinity"):
        with pytest.raises(CanonError):
            h(Q, "p", "quantity", {"n": bad, "u": None})


def test_bad_precision_rejected():
    with pytest.raises(CanonError):
        h(Q, "at", "time", {"t": "2009-01-01", "p": "fortnight"})


def test_malformed_qualifier_rejected():
    with pytest.raises(CanonError):
        h(Q, "p", "text", "v", True, [("valid_time", "2009")])


# ------------------------------------------------------------ determinism --
def test_stable_across_processes():
    """Hash must not depend on PYTHONHASHSEED — dict order is not a wire format."""
    import subprocess
    code = (
        "import sys; sys.path.insert(0, %r);"
        "from foundation.model.canonical import hexid;"
        "print(hexid('wikidata:Q42','p','text','v',True,"
        "[('b','text','2'),('a','text','1')]))"
        % str(Path(__file__).resolve().parent.parent))
    outs = {subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, env={"PYTHONHASHSEED": s, "PATH": "/usr/bin"}
                           ).stdout.strip()
            for s in ("0", "1", "12345")}
    assert len(outs) == 1 and next(iter(outs)), outs


def test_canonical_form_is_bytes_and_compact():
    b = canonical_form(Q, "p", "text", "v")
    assert isinstance(b, bytes) and b" " not in b


def test_number_edge_cases():
    assert norm_number("-0") == norm_number(0) == "0"
    assert norm_number("10") == norm_number("1e1") == "10"
    assert norm_number("0.10") == "0.1"
    assert norm_number("1234567890123456789012345") == "1234567890123456789012345"


def test_norm_text_idempotent():
    for s in ("  a  b ", "Ångström", "x"):
        assert norm_text(norm_text(s)) == norm_text(s)


# --------------------------------------------------- partial dates (v0 fix) --
def test_partial_dates_are_first_class():
    """'2009' is how a year-precision fact is written; it must not need a
    January the 1st invented for it."""
    assert h(Q, "at", "time", {"t": "2009", "p": "year"})
    assert h(Q, "at", "time", {"t": "2009-06", "p": "month"})
    assert h(Q, "at", "time", {"t": "2009", "p": "year"}) == \
           h(Q, "at", "time", {"t": "2009-06-15", "p": "year"})


def test_overclaimed_precision_rejected():
    """Refuse to invent a date nobody asserted."""
    for t, p in (("2009", "day"), ("2009", "month"), ("2009-06", "day"),
                 ("2009-06-15", "second")):
        with pytest.raises(CanonError, match="without inventing"):
            h(Q, "at", "time", {"t": t, "p": p})


def test_year_precision_never_collides_with_new_years_day():
    assert h(Q, "at", "time", {"t": "2009", "p": "year"}) != \
           h(Q, "at", "time", {"t": "2009-01-01", "p": "day"})


def test_naive_calendar_date_does_not_shift():
    assert h(Q, "at", "time", {"t": "2009-12-31", "p": "day"}) == \
           h(Q, "at", "time", {"t": "2009-12-31T00:00:00", "p": "day"})


# ------------------------------------------- hash agility + claim_ref (v1) --
def test_address_is_algorithm_tagged():
    """Untagged addresses cannot be migrated; ZK aggregation will want an
    algebraic hash later (model v1 §9b)."""
    from foundation.model.canonical import ALGOS, address, norm_address
    a = address(Q, "p", "text", "v")
    assert a[:1] == ALGOS["sha256"][0] and len(a) == 33
    assert norm_address(a) == h(Q, "p", "text", "v")
    assert h(Q, "p", "text", "v").startswith("sha256:")


def test_unknown_algorithm_rejected():
    from foundation.model.canonical import address
    with pytest.raises(CanonError):
        address(Q, "p", "text", "v", algo="md5")


def test_bare_digest_rejected_as_claim_ref():
    """A bare digest is a permanent commitment to one hash function."""
    bare = h(Q, "p", "text", "v").split(":", 1)[1]
    with pytest.raises(CanonError):
        h(Q, "retracts", "act_ref", bare)
    for bad in ("sha256:", "poseidon:ab", "sha256:zz", b"\xff\xab"):
        with pytest.raises(CanonError):
            h(Q, "retracts", "act_ref", bad)


def test_claim_ref_round_trips_and_accepts_bytes():
    from foundation.model.canonical import address
    target = address(Q, "date_of_birth", "text", "1907-05-22")
    assert h(Q, "retracts", "act_ref", target) == \
           h(Q, "retracts", "act_ref", norm_addr_str(target))


def norm_addr_str(b):
    from foundation.model.canonical import norm_address
    return norm_address(b)


def test_claim_ref_case_insensitive_hex():
    a = h(Q, "p", "text", "v")
    algo, hexd = a.split(":", 1)
    assert h(Q, "cites", "prop_ref", f"{algo}:{hexd.upper()}") == \
           h(Q, "cites", "prop_ref", a)


def test_claim_ref_is_not_text():
    """A pointer to a claim is not a string that looks like one."""
    a = h(Q, "p", "text", "v")
    assert h(Q, "cites", "prop_ref", a) != h(Q, "cites", "text", a)


def test_confidence_dimensions_target_different_things():
    """Dimensional confidence: the dimension is the predicate, the context is
    the qualifier, and — the v1 correction — the TARGET differs by dimension.

    Extraction fidelity is about a specific thing somebody did, so it takes an
    act_ref and the closure is never applied to it. Belief is about the world,
    so it takes a prop_ref and follows the proposition wherever identity
    resolution later carries it.
    """
    fact = h(Q, "place_of_birth", "entity", "wikidata:Q350")
    fidelity = h("s.alice:extractor_v3", "extraction_fidelity", "quantity",
                 {"n": "0.92", "u": None}, True, [("about", "act_ref", fact)])
    belief = h("s.alice:me", "believed", "quantity", {"n": "0.92", "u": None},
               True, [("about", "prop_ref", fact)])
    assert fidelity != belief          # same number, different dimension
    scoped = h("s.alice:me", "believed", "quantity", {"n": "0.92", "u": None},
               True, [("about", "prop_ref", fact),
                      ("in_domain", "text", "biography")])
    assert scoped != belief            # context changes the claim


# ------------------------------------------------ Layer 0 closure (v2) ------
def test_existentials_are_not_values():
    """'no children' must be expressible, and must never collide with a real
    object of the same sort."""
    from foundation.model.canonical import NONE, SOME
    none_child = h(Q, "has_child", "entity", NONE)
    some_child = h(Q, "has_child", "entity", SOME)
    a_child = h(Q, "has_child", "entity", "wikidata:Q1")
    assert len({none_child, some_child, a_child}) == 3


def test_existential_keeps_its_sort():
    """'no children' and 'no birth date' are different claims."""
    from foundation.model.canonical import NONE
    assert h(Q, "p", "entity", NONE) != h(Q, "p", "time", NONE)


def test_existential_polarity_still_distinguishes():
    from foundation.model.canonical import NONE
    assert h(Q, "p", "entity", NONE, True) != h(Q, "p", "entity", NONE, False)


def test_act_ref_and_prop_ref_are_distinct_sorts():
    """v1 conflated these; they resolve differently, so a mis-typed ref would
    silently change meaning instead of failing."""
    a = h(Q, "p", "text", "v")
    assert h(Q, "retracts", "act_ref", a) != h(Q, "believes", "prop_ref", a)


def test_predicate_definition_version_is_in_the_address():
    """v1 keyed predicate identity on (uri, definition_hash) and stored only
    the uri, so two definitions were indistinguishable."""
    d1 = h(Q, "x", "text", "v")
    d2 = h(Q, "y", "text", "v")
    assert h(Q, ("status", d1), "text", "v") != h(Q, ("status", d2), "text", "v")
    assert h(Q, ("status", d1), "text", "v") != h(Q, "status", "text", "v")


def test_bad_predicate_forms_rejected():
    for bad in (42, None, ("a", "b", "c"), ("a", "not-an-address")):
        with pytest.raises(CanonError):
            h(Q, bad, "text", "v")


# ------------------------------------------------- n-ary events -------------
def test_same_event_two_extractors_one_address():
    """The federation-critical property: differing role COVERAGE must not
    change the event's identity, only what is known about it."""
    from foundation.model.canonical import event_address
    key = ("seller", "item", "time")
    a = event_address("sale", {"seller": ("entity", "wikidata:Q1"),
                               "item": ("entity", "wikidata:Q2"),
                               "time": ("time", {"t": "2020", "p": "year"})}, key)
    b = event_address("sale", {"seller": ("entity", "wikidata:Q1"),
                               "item": ("entity", "wikidata:Q2"),
                               "time": ("time", {"t": "2020", "p": "year"}),
                               "price": ("quantity", {"n": 10, "u": "USD"})}, key)
    assert a == b


def test_event_address_is_a_usable_entity_ref():
    from foundation.model.canonical import event_address, norm_ref
    e = event_address("sale", {"seller": ("entity", "wikidata:Q1")}, ("seller",))
    assert norm_ref(e) == e and e.startswith("event:")
    assert h(e, "price", "quantity", {"n": 10, "u": "USD"})


def test_event_differing_key_roles_differs():
    from foundation.model.canonical import event_address
    k = ("seller",)
    assert (event_address("sale", {"seller": ("entity", "wikidata:Q1")}, k)
            != event_address("sale", {"seller": ("entity", "wikidata:Q9")}, k))
    assert (event_address("sale", {"seller": ("entity", "wikidata:Q1")}, k)
            != event_address("gift", {"seller": ("entity", "wikidata:Q1")}, k))


def test_event_missing_key_role_refused():
    """Guessing an identity would fabricate it rather than admit ignorance."""
    from foundation.model.canonical import event_address
    with pytest.raises(CanonError, match="missing identifying"):
        event_address("sale", {"item": ("entity", "wikidata:Q2")},
                      ("seller", "item"))
    with pytest.raises(CanonError, match="no identifying roles"):
        event_address("sale", {"item": ("entity", "wikidata:Q2")}, ())


# ------------------------------------------- salted commitments / deletion --
def test_commitment_is_hiding_not_just_binding():
    """Same content, different salts -> unlinkable published commitments."""
    from foundation.model.canonical import address, commit
    a = address(Q, "has_condition", "entity", "wikidata:Q12206")
    c1, c2 = commit(a, b"0" * 16), commit(a, b"1" * 16)
    assert c1 != c2 and c1 != a


def test_commitment_is_deterministic_for_one_salt():
    from foundation.model.canonical import address, commit
    a = address(Q, "p", "text", "v")
    assert commit(a, b"s" * 16) == commit(a, b"s" * 16)


def test_short_salt_refused():
    from foundation.model.canonical import address, commit
    with pytest.raises(CanonError, match="dictionary-attackable"):
        commit(address(Q, "p", "text", "v"), b"short")


# ------------------------------- found by real data, not by review (exp66) --
def test_short_years_are_real_and_must_canonicalise():
    """Extracted history says '476', '800', '1066'. Four review rounds missed
    this; 4,000 real claims found it in one run."""
    for y in ("476", "800", "1066", "1"):
        assert h(Q, "inception", "time", {"t": y, "p": "year"})


def test_zero_padding_does_not_fork_a_year():
    """'476' and '0476' are the same year and must not become two facts."""
    assert (h(Q, "inception", "time", {"t": "476", "p": "year"})
            == h(Q, "inception", "time", {"t": "0476", "p": "year"}))
    assert (h(Q, "inception", "time", {"t": "476-03", "p": "month"})
            == h(Q, "inception", "time", {"t": "0476-03", "p": "month"}))


def test_bce_refused_rather_than_mangled():
    """Python's calendar starts at year 1. Refusing names the limitation;
    silently coercing would fabricate a date."""
    for bad in ("-0500", "0000"):
        with pytest.raises(CanonError, match="not representable"):
            h(Q, "inception", "time", {"t": bad, "p": "year"})
