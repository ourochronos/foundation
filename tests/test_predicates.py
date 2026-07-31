"""The predicate lattice — up-only, and never materialised (docs/24)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from foundation.model.predicates import Lattice, LatticeError    # noqa: E402


def kin():
    L = Lattice()
    L.subsume("mother_of", "parent_of")
    L.subsume("father_of", "parent_of")
    L.subsume("parent_of", "relative_of")
    return L


def test_entailment_is_transitive_and_one_directional():
    L = kin()
    assert L.entails("mother_of", "relative_of")
    assert not L.entails("relative_of", "mother_of")
    assert not L.entails("mother_of", "father_of")


def test_query_expansion_goes_down_answers_go_up():
    """Asking for parent_of must ALSO match mother_of; asking for mother_of
    must never match parent_of — that would invent a gender."""
    L = kin()
    assert {"mother_of", "father_of", "parent_of"} <= L.specialisations("parent_of")
    assert L.specialisations("mother_of") == {"mother_of"}


def test_subsumption_cycles_rejected_at_registration():
    L = kin()
    with pytest.raises(LatticeError, match="cycle"):
        L.subsume("relative_of", "mother_of")
    with pytest.raises(LatticeError):
        L.subsume("mother_of", "mother_of")


def test_composition_declares_derivation_not_decomposition():
    L = Lattice()
    L.compose(["mother_of", "parent_of"], "grandmother_of")
    assert L.composites_for(["mother_of", "parent_of"]) == {"grandmother_of"}
    assert L.paths_for("grandmother_of") == [("mother_of", "parent_of")]
    assert L.composites_for(["parent_of", "mother_of"]) == set()   # order matters


def test_self_referential_composition_rejected():
    """A composite in its own defining path could derive itself without bound."""
    L = Lattice()
    with pytest.raises(LatticeError, match="own defining path"):
        L.compose(["grandmother_of", "parent_of"], "grandmother_of")
    with pytest.raises(LatticeError, match="at least two"):
        L.compose(["mother_of"], "x")


# ------------------------------------------- opposition (found by exp72) ----
def opp():
    L = Lattice()
    L.oppose("refutes", "compatible_with")
    return L


def test_opposition_is_symmetric():
    L = opp()
    assert L.opposes("refutes", "compatible_with")
    assert L.opposes("compatible_with", "refutes")
    assert not L.opposes("refutes", "requires")


def test_opposition_inherits_downward():
    """If refutes excludes compatible_with, anything BELOW refutes excludes
    anything below compatible_with — each entails its ancestor."""
    L = opp()
    L.subsume("strictly_refutes", "refutes")
    L.subsume("weakly_compatible_with", "compatible_with")
    assert L.opposes("strictly_refutes", "weakly_compatible_with")


def test_cannot_be_both_subsuming_and_opposed():
    """Would make every claim on the narrower predicate self-contradictory."""
    L = Lattice()
    L.subsume("mother_of", "parent_of")
    with pytest.raises(LatticeError, match="both subsuming and opposed"):
        L.oppose("mother_of", "parent_of")
    with pytest.raises(LatticeError):
        L.oppose("refutes", "refutes")
