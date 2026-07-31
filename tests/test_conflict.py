"""The reviewers' break cases, as tests (model v1 §1).

Four models reviewed v0 blind and all four broke it the same way. Those exact
cases are reproduced here — first asserting that the v0 behaviour WAS wrong,
then that v1 fixes it. A fix with no test naming the case it fixes is a claim,
not a repair.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from foundation.model.conflict import (                           # noqa: E402
    Claim, agreement, conflicts, proposition_key, scopes_overlap)
from foundation.model.identity import Closure, Policy, rank       # noqa: E402

DOB = "date_of_birth"
FUNC = frozenset({DOB})


def dob(subj, date, who, **kw):
    return Claim(subj, DOB, "time", {"t": date, "p": "day"},
                 claimant=who, **kw)


# ------------------------------------------------- the fatal flaw, v0 vs v1 --
def test_v0_break_case_two_local_refs_no_conflict_without_closure():
    """Reviewers' case: A and B disagree about one person under local: refs.
    With no identity closure this is v0 — two facts, zero conflicts."""
    cs = [dob("local:a1", "1907-05-22", "agent:A"),
          dob("local:b9", "1907-05-23", "agent:B")]
    assert conflicts(cs, None, FUNC) == []
    assert len(agreement(cs, None)) == 2, "v0 sees two unrelated propositions"


def test_v1_accepting_sameas_surfaces_the_conflict():
    """Same claims, same store, one accepted identity claim -> detected."""
    cs = [dob("local:a1", "1907-05-22", "agent:A"),
          dob("local:b9", "1907-05-23", "agent:B")]
    cl = Closure()
    assert cl.accept("local:a1", "wikidata:Q152", "agent:A")
    assert cl.accept("local:b9", "wikidata:Q152", "agent:B")
    found = conflicts(cs, cl, FUNC)
    assert len(found) == 1 and found[0].kind == "functional", found


def test_v1_agreement_pools_across_stores():
    """Two stores extract the SAME fact under different local refs.
    v0 counted two propositions of one agent each; v1 counts one of two."""
    cs = [dob("local:a1", "1907-05-22", "agent:A"),
          dob("local:b9", "1907-05-22", "agent:B")]
    assert len(agreement(cs, None)) == 2
    cl = Closure()
    cl.accept("local:a1", "wikidata:Q152", "agent:A")
    cl.accept("local:b9", "wikidata:Q152", "agent:B")
    ag = agreement(cs, cl)
    assert len(ag) == 1 and next(iter(ag.values())) == {"agent:A", "agent:B"}


def test_conflict_disappears_when_identity_is_retracted():
    """Identity is defeasible, so the conflict it implies must be too."""
    cs = [dob("local:a1", "1907-05-22", "agent:A"),
          dob("local:b9", "1907-05-23", "agent:B")]
    cl = Closure()
    cl.accept("local:a1", "wikidata:Q152", "agent:A")
    cl.accept("local:b9", "wikidata:Q152", "agent:B")
    assert len(conflicts(cs, cl, FUNC)) == 1
    assert conflicts(cs, Closure(), FUNC) == []      # closure rebuilt without it


# --------------------------------------- the qualifier loophole (fable's #2) --
def test_v0_qualifier_loophole_is_closed():
    """(X, member_of, Y, -, {}) must conflict with
    (X, member_of, Y, +, {valid_time: 1980}) — v0's exact-match rule missed it,
    so any agent could dodge dispute by adding one qualifier."""
    a = Claim("local:x", "member_of", "entity", "local:y", False,
              claimant="agent:A")
    b = Claim("local:x", "member_of", "entity", "local:y", True,
              (("valid_time", "time", {"t": "1980", "p": "year"}),),
              claimant="agent:B")
    found = conflicts([a, b], None)
    assert len(found) == 1 and found[0].kind == "polarity", found


def test_absent_qualifier_is_unrestricted():
    assert scopes_overlap({}, {"valid_time": {"t": "1980", "p": "year"}})
    assert scopes_overlap({"valid_place": "wikidata:Q30"}, {})


def test_disjoint_time_scopes_do_not_conflict():
    """Two presidents is not a contradiction — the qualifier does the work."""
    a = Claim("local:x", "position_held", "entity", "local:pres", True,
              (("valid_time", "time", {"t": "2009", "p": "year"}),),
              claimant="agent:A")
    b = Claim("local:y", "position_held", "entity", "local:pres", True,
              (("valid_time", "time", {"t": "2021", "p": "year"}),),
              claimant="agent:B")
    assert conflicts([a, b], None, frozenset({"position_held"})) == []


def test_overlapping_time_scopes_do_conflict():
    a = dob("local:x", "1907-05-22", "agent:A",
            qualifiers=(("valid_from", "time", {"t": "1900", "p": "year"}),))
    b = dob("local:x", "1907-05-23", "agent:B",
            qualifiers=(("valid_from", "time", {"t": "1950", "p": "year"}),))
    assert len(conflicts([a, b], None, FUNC)) == 1


def test_different_stated_assumptions_do_not_conflict():
    """Audit law #10 as data: two numbers measured under different conditions
    are both true, and neither retracts the other."""
    a = Claim("local:exp", "gate_cost", "quantity", {"n": "-0.083", "u": None},
              True, (("under_assumption", "text", "residual_r_asked"),),
              claimant="agent:A")
    b = Claim("local:exp", "gate_cost", "quantity", {"n": "-0.243", "u": None},
              True, (("under_assumption", "text", "raw_target_r_asked"),),
              claimant="agent:B")
    assert conflicts([a, b], None, frozenset({"gate_cost"})) == []


# ---------------------------------------------------- deterministic reps ----
def test_representative_is_deterministic_not_insertion_ordered():
    """Two stores merging the same claims in different orders must agree, or
    proposition keys are store-local and silently unshareable."""
    pairs = [("local:z", "wikidata:Q1"), ("local:a", "local:z")]
    a, b = Closure(), Closure()
    for x, y in pairs:
        a.accept(x, y, "agent:A")
    for x, y in reversed(pairs):
        b.accept(x, y, "agent:A")
    assert a.rep("local:a") == b.rep("local:a") == "wikidata:Q1"


def test_authoritative_namespace_wins_representative():
    assert rank("wikidata:Q1") < rank("local:a")
    cl = Closure()
    cl.accept("local:zzz", "wikidata:Q9", "agent:A")
    assert cl.rep("local:zzz") == "wikidata:Q9"


def test_proposition_key_is_stable_under_ref_choice():
    cl = Closure()
    cl.accept("local:a1", "wikidata:Q152", "agent:A")
    cl.accept("local:b9", "wikidata:Q152", "agent:B")
    assert (proposition_key(dob("local:a1", "1907-05-22", "x"), cl)
            == proposition_key(dob("local:b9", "1907-05-22", "y"), cl))


# ------------------------------------------------ fusion-bomb circuit breaks --
def test_blocked_pairs_never_fuse():
    """`conflates` / `different_from` must survive a later sameAs."""
    cl = Closure()
    cl.block("local:x1", "local:x2")
    assert not cl.accept("local:x1", "local:x2", "agent:A")
    assert any("blocked" in r for _, _, r in cl.rejected)


def test_block_propagates_through_the_class():
    cl = Closure()
    cl.accept("local:x1", "local:x1b", "agent:A")
    cl.block("local:x1", "local:x2")
    assert not cl.accept("local:x1b", "local:x2", "agent:A")


def test_max_class_size_breaks_a_fusion_chain():
    cl = Closure(Policy(max_class_size=3))
    assert cl.accept("local:e0", "local:e1", "agent:A")
    assert cl.accept("local:e0", "local:e2", "agent:A")
    assert not cl.accept("local:e0", "local:e3", "agent:A")
    assert any("max_class_size" in r for _, _, r in cl.rejected)


def test_corroboration_required_before_fusion():
    cl = Closure(Policy(require_agents=2))
    assert not cl.accept("local:a", "local:b", "agent:A")
    assert not cl.accept("local:a", "local:b", "agent:A")   # same agent twice
    assert cl.accept("local:a", "local:b", "agent:B")


def test_untrusted_agent_cannot_assert_identity():
    cl = Closure(Policy(trusted_agents={"agent:A"}))
    assert not cl.accept("local:a", "local:b", "agent:X")
    assert cl.accept("local:a", "local:b", "agent:A")


def test_rejections_are_recorded_not_dropped():
    """A silently ignored identity claim is indistinguishable from one never
    made, which is exactly the audit failure this project keeps finding."""
    cl = Closure(Policy(max_class_size=2))
    cl.accept("local:a", "local:b", "agent:A")
    cl.accept("local:a", "local:c", "agent:A")
    assert len(cl.rejected) == 1 and cl.rejected[0][:2] == ("local:a", "local:c")


def test_agreement_does_not_pool_across_different_scopes():
    """The scope-free key is for CONFLICT only. A claim about 1980 and an
    unscoped claim are different propositions and must count separately, or
    the fix for the loophole would quietly break agreement counting."""
    a = Claim("local:x", "member_of", "entity", "local:y", True,
              claimant="agent:A")
    b = Claim("local:x", "member_of", "entity", "local:y", True,
              (("valid_time", "time", {"t": "1980", "p": "year"}),),
              claimant="agent:B")
    assert len(agreement([a, b], None)) == 2


def test_annotation_qualifiers_do_not_affect_the_proposition():
    """Only truth-conditional qualifiers scope a claim; annotation belongs on
    the claim act and must not fragment the proposition."""
    a = Claim("local:x", "p", "text", "v", claimant="agent:A")
    b = Claim("local:x", "p", "text", "v",
              qualifiers=(("extracted_by", "text", "parser_v2"),),
              claimant="agent:B")
    ag = agreement([a, b], None)
    assert len(ag) == 1 and next(iter(ag.values())) == {"agent:A", "agent:B"}
