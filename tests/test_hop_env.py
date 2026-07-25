"""HopEnv guard rails (legacy env, kept for D30-D37 reproduction)."""

import numpy as np
import pytest

from codec.hop_env import Action, HopEnv
from codec.memory_store import MemoryStore

D = 8


def _env():
    s = MemoryStore(dim=D)
    z = np.ones(D, np.float32) / np.sqrt(D)
    s.add(z, ["a"], "fact")
    return HopEnv(s, ["r1"], {"r1": np.zeros(D, np.float32)})


def test_bad_relation_index_raises():
    env = _env()
    env.reset(np.ones(D, np.float32), {"a"})
    with pytest.raises(ValueError):
        env.step(Action(relation=5))


def test_step_before_reset_raises():
    env = _env()
    with pytest.raises((RuntimeError, AttributeError)):
        env.step(Action(relation=0))
