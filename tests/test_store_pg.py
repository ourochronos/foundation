"""PgStore semantics parity (M4). Skips when Postgres is unavailable."""

import numpy as np
import pytest

try:
    from codec.store_pg import PgStore
    _pg = PgStore(table="test_entries", dim=8, fresh=True)
    _PG_OK = True
except Exception:
    _PG_OK = False

pytestmark = pytest.mark.skipif(not _PG_OK, reason="no local Postgres")

D = 8


def _st():
    return PgStore(table="test_entries", dim=D, fresh=True)


def _basis(i):
    v = np.zeros(D, np.float32)
    v[i] = 1.0
    return v


def test_add_query_hybrid_scoring():
    st = _st()
    z = np.ones(D, np.float32) / np.sqrt(D)
    a = st.add(z, ["alpha"], "a")
    b = st.add(z, ["beta"], "b")
    assert st.query(z, {"beta"}, k=1, id_weight=1.0)[0][0] == b
    assert st.query(z, k=1, exclude={a})[0][0] == b


def test_supersede_semantics():
    st = _st()
    old = st.add(_basis(1), ["cap", "x"], "old")
    new = st.add(_basis(5), ["cap", "y"], "new")
    st.supersede(old, new)
    assert st.query(_basis(1), k=1)[0][0] == new     # address inheritance
    assert "x" in st.ids[new]                        # addressable
    assert "x" not in st.content_ids[new]            # never handed off
    # durability: a fresh attach sees the same state
    st2 = PgStore(table="test_entries", dim=D)
    assert st2.shadowed[old] and "x" in st2.ids[new]
    assert "x" not in st2.content_ids[new]


def test_exhaustion_returns_empty():
    st = _st()
    a = st.add(_basis(0), ["a"], "a")
    b = st.add(_basis(1), ["b"], "b")
    st.shadow(a)
    assert st.query(_basis(0), k=2, exclude={b}) == []


def test_parity_with_memory_store():
    from codec.memory_store import MemoryStore
    ms = MemoryStore(dim=D)
    pg = _st()
    for i in range(4):
        ms.add(_basis(i), [f"e{i}"], f"t{i}")
        pg.add(_basis(i), [f"e{i}"], f"t{i}")
    for qi in range(4):
        q = (_basis(qi) + 0.1 * _basis((qi + 1) % 4))
        assert ms.query(q, {f"e{qi}"}, k=2, id_weight=0.7)[0][0] == \
            pg.query(q, {f"e{qi}"}, k=2, id_weight=0.7)[0][0]
    ms.supersede(0, 1)
    pg.supersede(0, 1)
    assert ms.query(_basis(0), k=1)[0][0] == pg.query(_basis(0), k=1)[0][0]
