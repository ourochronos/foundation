"""MemoryStore invariants: guards, supersession address inheritance,
walk semantics knobs (demote/exclude), identity rescoring."""

import numpy as np
import pytest

from codec.memory_store import MemoryStore, fit_translation, id_tokens

D = 8


def _unit(v):
    return v / (np.linalg.norm(v) + 1e-12)


def test_empty_store_query_returns_empty():
    s = MemoryStore(dim=D)
    assert s.query(np.ones(D, np.float32)) == []


def test_dim_mismatch_raises():
    s = MemoryStore(dim=D)
    with pytest.raises(ValueError):
        s.add(np.ones(D + 1, np.float32), ["x"], "bad")


def test_id_tokens_normalization():
    assert id_tokens(["Barden Group", "4,200"]) == {"barden", "group", "4200"}


def test_identity_rescoring_breaks_gist_tie():
    s = MemoryStore(dim=D)
    z = _unit(np.ones(D, np.float32))
    a = s.add(z, ["alpha"], "fact alpha")
    b = s.add(z, ["beta"], "fact beta")
    top = s.query(z, {"beta"}, k=1, id_weight=0.5)
    assert top[0][0] == b


def test_supersede_inherits_address():
    """The new entry must answer at the OLD entry's key (D33)."""
    s = MemoryStore(dim=D)
    z_old = _unit(np.arange(D).astype(np.float32))
    z_new = _unit(np.ones(D, np.float32) * -1)
    old = s.add(z_old, ["cap", "x"], "capital of X is A")
    new = s.add(z_new, ["cap", "y"], "capital was moved to B")
    s.supersede(old, new)
    top = s.query(z_old, k=1, id_weight=0.0)
    assert top[0][0] == new                       # answers at the old key
    assert s.shadowed[old] and not s.shadowed[new]
    assert {"x", "y"} <= s.ids[new]               # id union


def test_exclude_and_demote():
    s = MemoryStore(dim=D)
    z = _unit(np.ones(D, np.float32))
    a = s.add(z, ["alpha"], "a")
    b = s.add(z, ["beta"], "b")
    top = s.query(z, k=1, exclude={a})
    assert top[0][0] == b
    top = s.query(z, {"x"}, k=1, id_weight=0.5, demote_ids={"alpha"})
    assert top[0][0] == b


def test_fit_translation_recovers_offset():
    rng = np.random.default_rng(0)
    Q = rng.normal(size=(50, D)).astype(np.float32)
    t = np.full(D, 0.3, np.float32)
    T = fit_translation(Q, Q + t)
    assert np.allclose(T, t, atol=1e-5)
