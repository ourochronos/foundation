"""D68 regression tests — the two audit bugs, exhaustion semantics, parity."""

import numpy as np
import pytest

from codec.memory_store import MemoryStore
from codec.store_pq import PQStore
from codec.walker import ChannelWalker

D, S = 32, 8


def _books(rng):
    """Codebooks that SEPARATE the test vectors: first dsub+1 centroids of
    every subvector are {zeros, e0..e3}, so distinct one-hot inputs get
    distinct codes (random books collide zeros/e0 -> ties masquerading as
    failures; that cost this suite two false alarms)."""
    d = D // S
    B = (rng.normal(size=(S, 16, d)) * 0.01).astype(np.float32)
    for s_ in range(S):
        B[s_, 0] = 0.0
        for j in range(d):
            B[s_, 1 + j] = 0.0
            B[s_, 1 + j, j] = 1.0
    return B


def _basis(i):
    v = np.zeros(D, np.float32)
    v[i] = 1.0
    return v


def _both_stores():
    rng = np.random.default_rng(0)
    return MemoryStore(dim=D), PQStore(_books(rng))


@pytest.mark.parametrize("which", ["mem", "pq"])
def test_all_shadowed_returns_empty(which):
    ms, pq = _both_stores()
    st = ms if which == "mem" else pq
    a = st.add(_basis(0), ["a"], "a")
    b = st.add(_basis(1), ["b"], "b")
    st.shadowed[a] = st.shadowed[b] = True
    assert st.query(_basis(0), k=2) == []


@pytest.mark.parametrize("which", ["mem", "pq"])
def test_all_excluded_returns_empty(which):
    ms, pq = _both_stores()
    st = ms if which == "mem" else pq
    a = st.add(_basis(0), ["a"], "a")
    b = st.add(_basis(1), ["b"], "b")
    assert st.query(_basis(0), k=2, exclude={a, b}) == []


@pytest.mark.parametrize("which", ["mem", "pq"])
def test_shadow_plus_exclude_exhaustion(which):
    ms, pq = _both_stores()
    st = ms if which == "mem" else pq
    a = st.add(_basis(0), ["a"], "a")
    b = st.add(_basis(1), ["b"], "b")
    st.shadowed[a] = True
    assert st.query(_basis(0), k=2, exclude={b}) == []


def test_exhaustion_terminates_walk_mid_chain():
    """Bug 2's chain consequence: candidate exhaustion mid-walk must
    return None, never continue on a garbage entry."""
    st = MemoryStore(dim=D)
    r1, r2 = _basis(0), _basis(1)
    f1 = st.add((r1 + 0.05 * _basis(4)) / np.linalg.norm(r1 + 0.05 * _basis(4)),
                ["x", "y"], "x r1 y")
    # NO r2 facts except f1 itself -> hop 2 excludes visited f1 and exhausts
    w = ChannelWalker(st, protos={"r1": r1, "r2": r2},
                      ops={"r1": np.zeros(D, np.float32),
                           "r2": np.zeros(D, np.float32)})
    assert w.walk({"x"}, ["r1", "r2"]) is None


@pytest.mark.skipif(not __import__("torch").cuda.is_available(),
                    reason="GPU stale-cache path needs CUDA")
def test_pq_gpu_query_supersede_query_reflects_edit():
    """Bug 1: query -> supersede -> query on the GPU path must score the
    POST-edit codes (a count-keyed cache serves pre-edit codes)."""
    rng = np.random.default_rng(0)
    pq = PQStore(_books(rng))
    z_old, z_new, z_far = _basis(0), _basis(9), _basis(5)
    old = pq.add(z_old, ["cap", "x"], "old")
    far = pq.add(z_far, ["other"], "far")
    new = pq.add(z_new, ["cap", "y"], "new")
    assert pq.query(z_old, k=1)[0][0] == old      # builds GPU cache
    pq.supersede(old, new)                        # in-place code mutation
    top = pq.query(z_old, k=1)                    # must see fresh codes
    assert top and top[0][0] == new
    assert pq.query(z_new, k=1)[0][0] != new      # new's own codes replaced


@pytest.mark.parametrize("qi", range(3))
def test_memory_pq_parity_including_exhaustion(qi):
    ms, pq = _both_stores()
    for i in range(3):
        ms.add(_basis(i), [f"e{i}"], f"t{i}")
        pq.add(_basis(i), [f"e{i}"], f"t{i}")
    q = _basis(qi)
    assert ms.query(q, k=1)[0][0] == pq.query(q, k=1)[0][0]
    ex = {0, 1, 2}
    assert ms.query(q, k=1, exclude=ex) == pq.query(q, k=1, exclude=ex) == []
