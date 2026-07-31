"""The reviewers' break cases, as tests (model v1 §1).

Four models reviewed v0 blind and all four broke it the same way. Those exact
cases are reproduced here — first asserting that the v0 behaviour WAS wrong,
then that v1 fixes it. A fix with no test naming the case it fixes is a claim,
not a repair.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Refs are store-scoped throughout: `local:` is a rejected namespace because
# two stores would both mint `local:p1` for different people (model v1 review).
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
    cs = [dob("s.alice:p1", "1907-05-22", "agent:A"),
          dob("s.bob:p9", "1907-05-23", "agent:B")]
    assert conflicts(cs, None, FUNC) == []
    assert len(agreement(cs, None)) == 2, "v0 sees two unrelated propositions"


def test_v1_accepting_sameas_surfaces_the_conflict():
    """Same claims, same store, one accepted identity claim -> detected."""
    cs = [dob("s.alice:p1", "1907-05-22", "agent:A"),
          dob("s.bob:p9", "1907-05-23", "agent:B")]
    cl = Closure()
    assert cl.accept("s.alice:p1", "wikidata:Q152", "agent:A")
    assert cl.accept("s.bob:p9", "wikidata:Q152", "agent:B")
    found = conflicts(cs, cl, FUNC)
    assert len(found) == 1 and found[0].kind == "functional", found


def test_v1_agreement_pools_across_stores():
    """Two stores extract the SAME fact under different local refs.
    v0 counted two propositions of one agent each; v1 counts one of two."""
    cs = [dob("s.alice:p1", "1907-05-22", "agent:A"),
          dob("s.bob:p9", "1907-05-22", "agent:B")]
    assert len(agreement(cs, None)) == 2
    cl = Closure()
    cl.accept("s.alice:p1", "wikidata:Q152", "agent:A")
    cl.accept("s.bob:p9", "wikidata:Q152", "agent:B")
    ag = agreement(cs, cl)
    # `claimant:` prefixed because neither claim names evidence — the weakest
    # honest reading, and distinguishable from a real document source.
    assert len(ag) == 1
    assert next(iter(ag.values())) == {"claimant:agent:A", "claimant:agent:B"}


def test_conflict_disappears_when_identity_is_retracted():
    """Identity is defeasible, so the conflict it implies must be too."""
    cs = [dob("s.alice:p1", "1907-05-22", "agent:A"),
          dob("s.bob:p9", "1907-05-23", "agent:B")]
    cl = Closure()
    cl.accept("s.alice:p1", "wikidata:Q152", "agent:A")
    cl.accept("s.bob:p9", "wikidata:Q152", "agent:B")
    assert len(conflicts(cs, cl, FUNC)) == 1
    assert conflicts(cs, Closure(), FUNC) == []      # closure rebuilt without it


# --------------------------------------- the qualifier loophole (fable's #2) --
def test_v0_qualifier_loophole_is_closed():
    """(X, member_of, Y, -, {}) must conflict with
    (X, member_of, Y, +, {valid_time: 1980}) — v0's exact-match rule missed it,
    so any agent could dodge dispute by adding one qualifier."""
    a = Claim("s.alice:x", "member_of", "entity", "s.alice:y", False,
              claimant="agent:A")
    b = Claim("s.alice:x", "member_of", "entity", "s.alice:y", True,
              (("valid_time", "time", {"t": "1980", "p": "year"}),),
              claimant="agent:B")
    found = conflicts([a, b], None)
    assert len(found) == 1 and found[0].kind == "polarity", found


def test_absent_qualifier_is_unrestricted():
    assert scopes_overlap({}, {"valid_time": {"t": "1980", "p": "year"}})
    assert scopes_overlap({"valid_place": "wikidata:Q30"}, {})


def test_disjoint_time_scopes_do_not_conflict():
    """Two presidents is not a contradiction — the qualifier does the work."""
    a = Claim("s.alice:x", "position_held", "entity", "s.alice:pres", True,
              (("valid_time", "time", {"t": "2009", "p": "year"}),),
              claimant="agent:A")
    b = Claim("s.alice:y", "position_held", "entity", "s.alice:pres", True,
              (("valid_time", "time", {"t": "2021", "p": "year"}),),
              claimant="agent:B")
    assert conflicts([a, b], None, frozenset({"position_held"})) == []


def test_overlapping_time_scopes_do_conflict():
    a = dob("s.alice:x", "1907-05-22", "agent:A",
            qualifiers=(("valid_from", "time", {"t": "1900", "p": "year"}),))
    b = dob("s.alice:x", "1907-05-23", "agent:B",
            qualifiers=(("valid_from", "time", {"t": "1950", "p": "year"}),))
    assert len(conflicts([a, b], None, FUNC)) == 1


def test_different_stated_assumptions_do_not_conflict():
    """Audit law #10 as data: two numbers measured under different conditions
    are both true, and neither retracts the other."""
    a = Claim("s.alice:exp", "gate_cost", "quantity", {"n": "-0.083", "u": None},
              True, (("under_assumption", "text", "residual_r_asked"),),
              claimant="agent:A")
    b = Claim("s.alice:exp", "gate_cost", "quantity", {"n": "-0.243", "u": None},
              True, (("under_assumption", "text", "raw_target_r_asked"),),
              claimant="agent:B")
    assert conflicts([a, b], None, frozenset({"gate_cost"})) == []


# ---------------------------------------------------- deterministic reps ----
def test_representative_is_deterministic_not_insertion_ordered():
    """Two stores merging the same claims in different orders must agree, or
    proposition keys are store-local and silently unshareable."""
    pairs = [("s.alice:z", "wikidata:Q1"), ("s.alice:a", "s.alice:z")]
    a, b = Closure(), Closure()
    for x, y in pairs:
        a.accept(x, y, "agent:A")
    for x, y in reversed(pairs):
        b.accept(x, y, "agent:A")
    assert a.rep("s.alice:a") == b.rep("s.alice:a") == "wikidata:Q1"


def test_authoritative_namespace_wins_representative():
    assert rank("wikidata:Q1") < rank("s.alice:a")
    cl = Closure()
    cl.accept("s.alice:zzz", "wikidata:Q9", "agent:A")
    assert cl.rep("s.alice:zzz") == "wikidata:Q9"


def test_proposition_key_is_stable_under_ref_choice():
    cl = Closure()
    cl.accept("s.alice:p1", "wikidata:Q152", "agent:A")
    cl.accept("s.bob:p9", "wikidata:Q152", "agent:B")
    assert (proposition_key(dob("s.alice:p1", "1907-05-22", "x"), cl)
            == proposition_key(dob("s.bob:p9", "1907-05-22", "y"), cl))


# ------------------------------------------------ fusion-bomb circuit breaks --
def test_blocked_pairs_never_fuse():
    """`conflates` / `different_from` must survive a later sameAs."""
    cl = Closure()
    cl.block("s.alice:x1", "s.alice:x2")
    assert not cl.accept("s.alice:x1", "s.alice:x2", "agent:A")
    assert any("blocked" in r for _, _, r in cl.rejected)


def test_block_propagates_through_the_class():
    cl = Closure()
    cl.accept("s.alice:x1", "s.alice:x1b", "agent:A")
    cl.block("s.alice:x1", "s.alice:x2")
    assert not cl.accept("s.alice:x1b", "s.alice:x2", "agent:A")


def test_max_class_size_breaks_a_fusion_chain():
    cl = Closure(Policy(max_class_size=3))
    assert cl.accept("s.alice:e0", "s.alice:e1", "agent:A")
    assert cl.accept("s.alice:e0", "s.alice:e2", "agent:A")
    assert not cl.accept("s.alice:e0", "s.alice:e3", "agent:A")
    assert any("max_class_size" in r for _, _, r in cl.rejected)


def test_corroboration_required_before_fusion():
    cl = Closure(Policy(require_agents=2))
    assert not cl.accept("s.alice:a", "s.alice:b", "agent:A")
    assert not cl.accept("s.alice:a", "s.alice:b", "agent:A")   # same agent twice
    assert cl.accept("s.alice:a", "s.alice:b", "agent:B")


def test_untrusted_agent_cannot_assert_identity():
    cl = Closure(Policy(trusted_agents={"agent:A"}))
    assert not cl.accept("s.alice:a", "s.alice:b", "agent:X")
    assert cl.accept("s.alice:a", "s.alice:b", "agent:A")


def test_rejections_are_recorded_not_dropped():
    """A silently ignored identity claim is indistinguishable from one never
    made, which is exactly the audit failure this project keeps finding."""
    cl = Closure(Policy(max_class_size=2))
    cl.accept("s.alice:a", "s.alice:b", "agent:A")
    cl.accept("s.alice:a", "s.alice:c", "agent:A")
    assert len(cl.rejected) == 1 and cl.rejected[0][:2] == ("s.alice:a", "s.alice:c")


def test_agreement_does_not_pool_across_different_scopes():
    """The scope-free key is for CONFLICT only. A claim about 1980 and an
    unscoped claim are different propositions and must count separately, or
    the fix for the loophole would quietly break agreement counting."""
    a = Claim("s.alice:x", "member_of", "entity", "s.alice:y", True,
              claimant="agent:A")
    b = Claim("s.alice:x", "member_of", "entity", "s.alice:y", True,
              (("valid_time", "time", {"t": "1980", "p": "year"}),),
              claimant="agent:B")
    assert len(agreement([a, b], None)) == 2


def test_annotation_qualifiers_do_not_affect_the_proposition():
    """Only truth-conditional qualifiers scope a claim; annotation belongs on
    the claim act and must not fragment the proposition."""
    a = Claim("s.alice:x", "p", "text", "v", claimant="agent:A")
    b = Claim("s.alice:x", "p", "text", "v",
              qualifiers=(("extracted_by", "text", "parser_v2"),),
              claimant="agent:B")
    ag = agreement([a, b], None)
    assert len(ag) == 1
    assert next(iter(ag.values())) == {"claimant:agent:A", "claimant:agent:B"}


# ------------------------------------- agreement counts evidence, not claims --
def test_derived_claims_do_not_inflate_agreement():
    """Three agents each deriving one fact from ONE paper is one source, not
    three. Otherwise federation's whole payoff is manufacturable locally."""
    from foundation.model.conflict import Evidence
    base = Claim("s.alice:x", "p", "text", "v", claimant="agent:A", hash="H0",
                 evidence=(Evidence("span", "doi:10.1/abc"),))
    derived = [Claim("s.alice:x", "p", "text", "v", claimant=f"agent:{n}",
                     hash=f"H{i}", evidence=(Evidence("premise", premises=("H0",)),))
               for i, n in enumerate("BCD", start=1)]
    ag = agreement([base] + derived, None)
    assert len(ag) == 1
    assert next(iter(ag.values())) == {"span:doi:10.1/abc"}


def test_two_real_documents_are_two_sources():
    from foundation.model.conflict import Evidence
    cs = [Claim("s.alice:x", "p", "text", "v", claimant="agent:A", hash="H1",
                evidence=(Evidence("span", "doi:10.1/aaa"),)),
          Claim("s.bob:x", "p", "text", "v", claimant="agent:B", hash="H2",
                evidence=(Evidence("span", "doi:10.2/bbb"),))]
    cl = Closure()
    cl.accept("s.alice:x", "wikidata:Q1", "agent:A")
    cl.accept("s.bob:x", "wikidata:Q1", "agent:B")
    assert len(next(iter(agreement(cs, cl).values()))) == 2


def test_same_document_via_two_agents_is_one_source():
    from foundation.model.conflict import Evidence
    cs = [Claim("s.alice:x", "p", "text", "v", claimant=a, hash=h,
                evidence=(Evidence("span", "doi:10.1/same"),))
          for a, h in (("agent:A", "H1"), ("agent:B", "H2"))]
    assert next(iter(agreement(cs, None).values())) == {"span:doi:10.1/same"}


def test_premise_cycle_terminates():
    """A malformed or adversarial premise loop must not hang the fold."""
    from foundation.model.conflict import Evidence
    a = Claim("s.alice:x", "p", "text", "v", claimant="agent:A", hash="HA",
              evidence=(Evidence("premise", premises=("HB",)),))
    b = Claim("s.alice:x", "p", "text", "v", claimant="agent:B", hash="HB",
              evidence=(Evidence("premise", premises=("HA",)),))
    assert agreement([a, b], None) is not None


def test_no_evidence_falls_back_to_claimant():
    """Weakest honest reading: somebody asserted it and named no source."""
    c = Claim("s.alice:x", "p", "text", "v", claimant="agent:A")
    assert next(iter(agreement([c], None).values())) == {"claimant:agent:A"}


# ------------------------------------------------- existentials (Layer 0) ---
def test_none_contradicts_any_concrete_object():
    """'Alice has no children' vs 'Alice's child is Bob'. Must fire for a
    NON-functional predicate too — has_child admits many objects."""
    from foundation.model.canonical import NONE
    a = Claim("s.alice:me", "has_child", "entity", NONE, claimant="agent:A")
    b = Claim("s.alice:me", "has_child", "entity", "wikidata:Q1",
              claimant="agent:B")
    found = conflicts([a, b], None, frozenset())      # no functional predicates
    assert len(found) == 1 and found[0].kind == "existential", found


def test_none_and_some_contradict():
    from foundation.model.canonical import NONE, SOME
    a = Claim("s.alice:me", "has_allergy", "entity", NONE, claimant="agent:A")
    b = Claim("s.alice:me", "has_allergy", "entity", SOME, claimant="agent:B")
    assert len(conflicts([a, b], None)) == 1


def test_some_is_entailed_by_a_concrete_object_not_conflicting():
    from foundation.model.canonical import SOME
    a = Claim("s.alice:me", "has_child", "entity", SOME, claimant="agent:A")
    b = Claim("s.alice:me", "has_child", "entity", "wikidata:Q1",
              claimant="agent:B")
    assert conflicts([a, b], None) == []


def test_existential_respects_scope():
    """'no children in 1980' does not contradict 'child born 2010'."""
    from foundation.model.canonical import NONE
    a = Claim("s.alice:me", "has_child", "entity", NONE, True,
              (("valid_time", "time", {"t": "1980", "p": "year"}),),
              claimant="agent:A")
    b = Claim("s.alice:me", "has_child", "entity", "wikidata:Q1", True,
              (("valid_time", "time", {"t": "2010", "p": "year"}),),
              claimant="agent:B")
    assert conflicts([a, b], None) == []


def test_existential_across_identity_closure():
    """The two fixes must compose: NONE asserted under one store's ref must
    contradict a concrete object under another's once identity is accepted."""
    from foundation.model.canonical import NONE
    a = Claim("s.alice:p1", "has_child", "entity", NONE, claimant="agent:A")
    b = Claim("s.bob:p9", "has_child", "entity", "wikidata:Q1",
              claimant="agent:B")
    assert conflicts([a, b], None) == []
    cl = Closure()
    cl.accept("s.alice:p1", "wikidata:Q152", "agent:A")
    cl.accept("s.bob:p9", "wikidata:Q152", "agent:B")
    assert len(conflicts([a, b], cl)) == 1


# ------------------------------------------------- subsumption (docs/24) ----
def _lat():
    from foundation.model.predicates import Lattice
    L = Lattice()
    L.subsume("mother_of", "parent_of")
    L.subsume("father_of", "parent_of")
    return L


def test_subsumption_conflict_is_detected():
    """(X, mother_of, Y, +) vs (X, parent_of, Y, -) is a flat contradiction
    that predicate-string grouping cannot see."""
    a = Claim("s.alice:x", "mother_of", "entity", "s.alice:y", True,
              claimant="agent:A")
    b = Claim("s.alice:x", "parent_of", "entity", "s.alice:y", False,
              claimant="agent:B")
    assert conflicts([a, b], None) == []                     # blind without it
    found = conflicts([a, b], None, lattice=_lat())
    assert len(found) == 1 and found[0].kind == "subsumption", found


def test_subsumption_conflict_is_one_directional():
    """not-mother is consistent with parent — the parent may be the father."""
    a = Claim("s.alice:x", "parent_of", "entity", "s.alice:y", True,
              claimant="agent:A")
    b = Claim("s.alice:x", "mother_of", "entity", "s.alice:y", False,
              claimant="agent:B")
    assert conflicts([a, b], None, lattice=_lat()) == []


def test_subsumption_respects_object_and_scope():
    a = Claim("s.alice:x", "mother_of", "entity", "s.alice:y", True,
              claimant="agent:A")
    other = Claim("s.alice:x", "parent_of", "entity", "s.alice:z", False,
                  claimant="agent:B")
    assert conflicts([a, other], None, lattice=_lat()) == []
    scoped = Claim("s.alice:x", "parent_of", "entity", "s.alice:y", False,
                   (("valid_time", "time", {"t": "1800", "p": "year"}),),
                   claimant="agent:B")
    a2 = Claim("s.alice:x", "mother_of", "entity", "s.alice:y", True,
               (("valid_time", "time", {"t": "2000", "p": "year"}),),
               claimant="agent:A")
    assert conflicts([a2, scoped], None, lattice=_lat()) == []


def test_unregistered_qualifier_cannot_evade_dispute():
    """The safe default, pinned: an unknown qualifier imposes no restriction.
    If it defaulted to disjoint, one junk qualifier would make any claim
    permanently undisputable — v0's loophole through a side door."""
    a = Claim("s.alice:x", "p", "entity", "s.alice:y", True,
              (("wibble", "text", "nonsense"),), claimant="agent:A")
    b = Claim("s.alice:x", "p", "entity", "s.alice:y", False, claimant="agent:B")
    found = conflicts([a, b], None)
    assert len(found) == 1 and found[0].kind == "polarity", found


# --------------------------------------------- confluence (v2 panel, fable) --
def test_incremental_accept_is_not_confluent():
    """Documents the hazard rather than hiding it: once a policy bites, edge
    ARRIVAL ORDER changes the closure — and therefore agreements and conflicts
    computed from identical claim sets."""
    edges = [("s.a:1", "s.a:2"), ("s.a:2", "s.a:3"), ("s.a:3", "s.a:4")]
    p = Policy(max_class_size=3)
    fwd, rev = Closure(p), Closure(p)
    for x, y in edges:
        fwd.accept(x, y, "agent:A")
    for x, y in reversed(edges):
        rev.accept(x, y, "agent:A")
    assert fwd.members("s.a:1") != rev.members("s.a:1")


def test_accept_all_is_confluent_under_a_biting_policy():
    """The merge path: same edge SET, any arrival order, identical closure."""
    edges = [("s.a:1", "s.a:2", "agent:A"), ("s.a:2", "s.a:3", "agent:A"),
             ("s.a:3", "s.a:4", "agent:A")]
    p = Policy(max_class_size=3)
    a, b = Closure(p), Closure(p)
    a.accept_all(edges)
    b.accept_all(list(reversed(edges)))
    assert a.members("s.a:1") == b.members("s.a:1")
    assert a.rep("s.a:1") == b.rep("s.a:1")


def test_representative_cache_matches_the_scanning_definition():
    """rep() is now incremental; it must still be the rank-minimum member."""
    cl = Closure()
    cl.accept_all([("s.zed:9", "s.alpha:1", "agent:A"),
                   ("s.alpha:1", "wikidata:Q7", "agent:A")])
    members = cl.members("s.zed:9")
    assert cl.rep("s.zed:9") == min(members, key=rank) == "wikidata:Q7"


# ------------------------------- time precision (found by exp67, real data) --
def test_coarser_and_finer_dates_do_not_conflict():
    """`1953` and `1953-04-11` are the same birth date stated at different
    precisions. Reporting them as disputed invents a disagreement — 24 of 89
    baseline conflicts on the real corpus were exactly this."""
    a = Claim("s.w:wiles", "P569", "time", {"t": "1953", "p": "year"},
              claimant="agent:A")
    b = Claim("s.w:wiles", "P569", "time", {"t": "1953-04-11", "p": "day"},
              claimant="agent:B")
    assert conflicts([a, b], None, frozenset({"P569"})) == []


def test_genuinely_different_dates_still_conflict():
    """The fix must not silence real disagreement."""
    for x, y in ((("1953-04-11", "day"), ("1953-04-12", "day")),
                 (("1953", "year"), ("1954", "year")),
                 (("1765-08-30", "day"), ("476", "year"))):
        a = Claim("s.w:x", "P569", "time", {"t": x[0], "p": x[1]},
                  claimant="agent:A")
        b = Claim("s.w:x", "P569", "time", {"t": y[0], "p": y[1]},
                  claimant="agent:B")
        assert len(conflicts([a, b], None, frozenset({"P569"}))) == 1, (x, y)


def test_precision_tolerance_does_not_apply_across_sorts():
    """A date read as an entity is not a time value and must not be quietly
    reconciled with one — that would hide the ingestion bug rather than it."""
    a = Claim("s.w:x", "P569", "time", {"t": "1953", "p": "year"},
              claimant="agent:A")
    b = Claim("s.w:x", "P569", "entity", "s.w:1953-ce", claimant="agent:B")
    assert len(conflicts([a, b], None, frozenset({"P569"}))) == 1


# ---------------------------------------- the query path (exp68) ------------
def test_query_never_leaks_a_sibling_predicate():
    """Ask for place-of-birth when only place-of-DEATH is known. The lattice
    must not answer. The corpus had exactly one subject in this shape, so the
    experiment's zero measured almost nothing — this pins the code path."""
    from foundation.model.predicates import Lattice
    from foundation.model.query import ask
    lat = Lattice()
    lat.subsume("P19", "place")
    lat.subsume("P20", "place")
    cs = [Claim("s.a:x", "P20", "entity", "s.a:paris", claimant="agent:A")]
    assert ask(cs, "s.a:x", "P19", None, lat).answered is False
    assert ask(cs, "s.a:x", "place", None, lat).answered is True


def test_query_refuses_rather_than_guessing():
    from foundation.model.query import ask
    cs = [Claim("s.a:x", "P569", "text", "1900", claimant="agent:A")]
    for subj, pred in (("s.a:x", "P570"), ("s.a:nobody", "P569")):
        a = ask(cs, subj, pred, None)
        assert not a.answered and "no edge" in a.refusal


def test_query_returns_both_sides_of_a_disagreement():
    """The store structures disagreement; it must never pick."""
    from foundation.model.conflict import Evidence
    from foundation.model.query import ask
    cs = [Claim("s.a:x", "P569", "time", {"t": "1907-05-22", "p": "day"},
                claimant="agent:A", hash="H1",
                evidence=(Evidence("span", "doc:A"),)),
          Claim("s.a:x", "P569", "time", {"t": "1907-05-23", "p": "day"},
                claimant="agent:B", hash="H2",
                evidence=(Evidence("span", "doc:B"),))]
    a = ask(cs, "s.a:x", "P569", None, functional=frozenset({"P569"}))
    assert len(a.answers) == 2 and len(a.conflicts) == 1


def test_min_sources_refusal_counts_independent_evidence():
    """Two agents citing one document must not satisfy a two-source policy."""
    from foundation.model.conflict import Evidence
    from foundation.model.query import ask
    same = [Claim("s.a:x", "P569", "text", "1900", claimant=f"agent:{n}",
                  hash=f"H{i}", evidence=(Evidence("span", "doc:one"),))
            for i, n in enumerate("AB")]
    assert not ask(same, "s.a:x", "P569", None, min_sources=2).answered
    two = [Claim("s.a:x", "P569", "text", "1900", claimant=f"agent:{n}",
                 hash=f"H{i}", evidence=(Evidence("span", f"doc:{n}"),))
           for i, n in enumerate("AB")]
    assert ask(two, "s.a:x", "P569", None, min_sources=2).answered


def test_opposed_predicates_conflict_though_both_positive():
    """exp72's finding: 83% of real philosophical opposition looks like this,
    and polarity/functional rules see nothing."""
    from foundation.model.predicates import Lattice
    L = Lattice()
    L.oppose("refutes", "compatible_with")
    a = Claim("c:determinism", "refutes", "entity", "c:free-will", True,
              claimant="pos:hard-determinism")
    b = Claim("c:determinism", "compatible_with", "entity", "c:free-will", True,
              claimant="pos:compatibilism")
    assert conflicts([a, b], None) == []                 # blind without it
    found = conflicts([a, b], None, lattice=L)
    assert len(found) == 1 and found[0].kind == "opposition", found


def test_opposition_respects_scope():
    """Held under different stated assumptions, opposed claims coexist —
    which is the whole reason under_assumption exists."""
    from foundation.model.predicates import Lattice
    L = Lattice()
    L.oppose("refutes", "compatible_with")
    a = Claim("c:determinism", "refutes", "entity", "c:free-will", True,
              (("under_assumption", "text", "Hard determinism"),),
              claimant="pos:hard-determinism")
    b = Claim("c:determinism", "compatible_with", "entity", "c:free-will", True,
              (("under_assumption", "text", "Compatibilism"),),
              claimant="pos:compatibilism")
    assert conflicts([a, b], None, lattice=L) == []


# ------------------------------ nested assumption frames (political corpus) --
def _frames():
    """Political positions are points in a space, not labels: two can share an
    economic axis while opposing on a social one."""
    from foundation.model.predicates import Lattice
    L = Lattice()
    L.subsume("social democracy", "left economics")
    L.subsume("democratic socialism", "left economics")
    L.subsume("neoliberalism", "right economics")
    L.oppose("increases", "decreases")
    return L


def _claim(pred, frame, pol=True):
    return Claim("c:minimum-wage", pred, "entity", "c:unemployment", pol,
                 (("under_assumption", "text", frame),),
                 claimant=f"pos:{frame}")


def test_sibling_frames_still_coexist():
    """Two positions under the same broader frame are still distinct frames —
    the coexistence under_assumption provides must survive the change."""
    a, b = _claim("increases", "social democracy"), _claim("decreases", "democratic socialism")
    assert conflicts([a, b], None, lattice=_frames()) == []


def test_narrower_frame_conflicts_with_the_broader_one_it_entails():
    """A claim held under Left economics applies to anyone accepting social
    democracy, so the two CAN contradict — equality alone could never see it."""
    a, b = _claim("increases", "left economics"), _claim("decreases", "social democracy")
    L = _frames()
    assert conflicts([a, b], None) == []                    # atomic: invisible
    found = conflicts([a, b], None, lattice=L)
    assert len(found) == 1 and found[0].kind == "opposition", found


def test_unrelated_frames_do_not_conflict():
    a = _claim("increases", "left economics")
    b = _claim("decreases", "right economics")
    assert conflicts([a, b], None, lattice=_frames()) == []


def test_unscoped_claim_still_conflicts_with_any_frame():
    """An unqualified claim is unrestricted and must remain disputable."""
    a = Claim("c:minimum-wage", "increases", "entity", "c:unemployment", True,
              claimant="pos:none")
    b = _claim("decreases", "social democracy")
    assert len(conflicts([a, b], None, lattice=_frames())) == 1
