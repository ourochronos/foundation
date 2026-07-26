"""PQStore invariants: MeMoryStore-compatible semantics on random codebooks
(exactness not required — ORDER preservation on separated vectors is)."""

import numpy as np
import pytest

from codec.store_pq import PQStore

D, S = 32, 8


def _books(rng):
    return rng.normal(size=(S, 16, D // S)).astype(np.float32)


def test_add_query_roundtrip():
    rng = np.random.default_rng(0)
    pq = PQStore(_books(rng))
    z1 = np.eye(D, dtype=np.float32)[0]
    z2 = np.eye(D, dtype=np.float32)[5]
    a = pq.add(z1, ["alpha"], "a")
    b = pq.add(z2, ["beta"], "b")
    assert pq.query(z1, k=1)[0][0] == a
    assert pq.query(z2, k=1)[0][0] == b


def test_id_rescoring_and_exclude():
    rng = np.random.default_rng(0)
    pq = PQStore(_books(rng))
    z = np.ones(D, np.float32) / np.sqrt(D)
    a = pq.add(z, ["alpha"], "a")
    b = pq.add(z, ["beta"], "b")
    assert pq.query(z, {"beta"}, k=1, id_weight=1.0)[0][0] == b
    assert pq.query(z, k=1, exclude={a})[0][0] == b


def test_supersede_semantics_match_memory_store():
    rng = np.random.default_rng(0)
    pq = PQStore(_books(rng))
    z_old = np.eye(D, dtype=np.float32)[1]
    z_new = np.eye(D, dtype=np.float32)[9]
    old = pq.add(z_old, ["cap", "x"], "old")
    new = pq.add(z_new, ["cap", "y"], "new")
    pq.supersede(old, new)
    assert pq.query(z_old, k=1)[0][0] == new     # address inheritance
    assert "x" in pq.ids[new]                    # addressable by old ids
    assert "x" not in pq.content_ids[new]        # never handed off (D55)
    assert pq.shadowed[old]


def test_empty_and_dim_guard():
    rng = np.random.default_rng(0)
    pq = PQStore(_books(rng))
    assert pq.query(np.ones(D, np.float32)) == []
    with pytest.raises(ValueError):
        pq.add(np.ones(D + 1, np.float32), ["x"], "bad")
