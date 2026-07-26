"""Regression tests for the canonical executor (codec/walker.py, D43/D44).

The synthetic world here is built to reproduce the two measured failure
modes the D30-era executor had:
  1. multi-hop questions whose gist matches the LAST relation (the walker
     must not care — it never sees the question gist);
  2. revisit compositions where the answer entity is already named in the
     question (the naive all-seen-ids hand-off mask goes empty).
"""

import numpy as np
import pytest

from codec.memory_store import MemoryStore
from codec.walker import ChannelWalker

D = 16


def _unit(v):
    return v / (np.linalg.norm(v) + 1e-12)


def _basis(i):
    v = np.zeros(D, np.float32)
    v[i] = 1.0
    return v


@pytest.fixture()
def world():
    """Two relations r1 (X in Y) and r2 (cap of Y is C) over two chains,
    one of which is a revisit: the subject city IS its country's capital."""
    store = MemoryStore(dim=D)
    # facts cluster by relation in the dense space; ids disambiguate
    r1_dir, r2_dir = _basis(0), _basis(1)
    f = {}
    f["a_in_y"] = store.add(_unit(r1_dir + 0.05 * _basis(4)), ["cityA", "landY"],
                            "cityA is in landY")
    f["cap_y"] = store.add(_unit(r2_dir + 0.05 * _basis(5)), ["landY", "cityC"],
                           "capital of landY is cityC")
    # revisit chain: cityB in landZ, capital of landZ is cityB itself
    f["b_in_z"] = store.add(_unit(r1_dir + 0.05 * _basis(6)), ["cityB", "landZ"],
                            "cityB is in landZ")
    f["cap_z"] = store.add(_unit(r2_dir + 0.05 * _basis(7)), ["landZ", "cityB"],
                           "capital of landZ is cityB")
    protos = {"r1": r1_dir, "r2": r2_dir}
    ops = {"r1": np.zeros(D, np.float32), "r2": np.zeros(D, np.float32)}
    return store, ChannelWalker(store, protos, ops), f


def test_two_hop(world):
    store, w, f = world
    assert w.walk({"citya"}, ["r1", "r2"]) == f["cap_y"]


def test_revisit_hand_off_survives(world):
    """ids(cur) - ids(handed in) must keep the object even when it already
    appeared in the question (the D43 loc_cap_pop failure)."""
    store, w, f = world
    assert w.walk({"cityb"}, ["r1", "r2"]) == f["cap_z"]


def test_walk_ignores_question_gist(world):
    """The walk takes no gist argument at all — API-level enforcement of
    the D43 finding."""
    store, w, f = world
    import inspect
    assert "q_z" not in inspect.signature(w.walk).parameters


def test_abstain_on_unknown_entity(world):
    store, w, f = world
    assert w.walk({"nosuchcity"}, ["r1"]) is None


def test_abstain_readout_relation_mismatch(world):
    """A subject that lacks the requested relation yields its OTHER fact
    with perfect coverage — classification must catch it (D44)."""
    store, w, f = world
    # landY has a capital fact but no located_in fact
    assert w.abstain_hop1({"landy"}, "r2") is False       # answerable
    # cityC exists only as an object; asking r1 of it must abstain
    assert w.abstain_hop1({"cityc"}, "r1") is True


def test_unknown_relation_raises(world):
    store, w, f = world
    with pytest.raises(ValueError):
        w.walk({"citya"}, ["nope"])


def test_classify(world):
    store, w, f = world
    assert w.classify(f["a_in_y"]) == "r1"
    assert w.classify(f["cap_y"]) == "r2"


def test_hand_off_excludes_superseded_address_ids(world):
    """After supersession the old object stays ADDRESSABLE but must not
    ride the hand-off (the D55 MQuAKE propagation bug)."""
    store, w, f = world
    z = store.Z[f["cap_y"]].copy()
    ni = store.add(_unit(_basis(1) + 0.05 * _basis(9)),
                   ["landY", "cityNEW"], "capital of landY is cityNEW")
    store.supersede(f["cap_y"], ni)
    assert "cityc" in store.ids[ni]            # addressable by old object
    assert "cityc" not in store.content_ids[ni]  # but never handed off
