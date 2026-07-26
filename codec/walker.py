"""ChannelWalker — the canonical multi-hop executor (D43/D44).

This is the ONE authoritative implementation of the channel-separated walk;
probes and training scripts must import it rather than re-implementing
(review finding 2026-07-25: the D43 fix lived in a probe while HopEnv.step
kept the defective executor).

The walk obeys the channel-separation law (sixth appearance, D43):

  dense channel   hop k's query is `unit(proto_r + t_r)` — the relation's
                  question-prototype translated by its operator. TYPE-LEVEL
                  content only. The question's own gist never touches
                  execution: a multi-hop question's gist encodes the LAST
                  relation and derails intermediate hops (measured: every
                  traced loc_cap_pop walk grabbed the subject's population
                  fact at hop 1 when queried with question_gist + t).
  id channel      the entity rides symbolically: hand-off mask
                  `ids(cur) − ids(handed in)` — subtract the SUBJECT side
                  of the current fact only, never all-seen ids, so revisit
                  compositions (answer entity already named in the question)
                  keep their hand-off. id_weight 1.0.

Abstention readouts (D44):
  cov      hop-1 id coverage < cov_abstain — the retrieved fact doesn't
           contain the entity the question names (B2's signal).
  classify the retrieved fact's relation, `argmax_r cos(z, proto_r + t_r)`,
           differs from the requested one — under id_weight 1.0 a subject
           lacking the fact yields its OTHER fact with perfect coverage, so
           coverage alone is dead as a signal (measured; recall 1.000 /
           false-abstain 0.010 with the classification readout).

Gold-chain execution on world v4, all 12 compositions: 0.933–1.000
(`results/soft_planner_j3.json`); the D30-era executor scored 0.00–0.76.
"""

from __future__ import annotations

import numpy as np

from codec.memory_store import MemoryStore


def _unit(x: np.ndarray) -> np.ndarray:
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-12)


class ChannelWalker:
    """Executes a planned relation chain against a MemoryStore.

    protos: relation -> mean train-question embedding (whitened, unit)
    ops:    relation -> fitted translation operator (fit_translation)
    """

    def __init__(self, store: MemoryStore, protos: dict[str, np.ndarray],
                 ops: dict[str, np.ndarray], id_weight: float = 1.0,
                 cov_abstain: float = 0.34):
        if set(protos) != set(ops):
            raise ValueError("protos and ops must cover the same relations")
        self.store = store
        self.relations = sorted(protos)
        self.pt = {r: _unit(protos[r] + ops[r]) for r in self.relations}
        self.ptmat = np.stack([self.pt[r] for r in self.relations])
        self.id_weight = id_weight
        self.cov_abstain = cov_abstain

    # ---- readouts -------------------------------------------------------
    def classify(self, fact_idx: int) -> str:
        """Which relation does a stored fact express? argmax over proto+t."""
        return self.relations[int(np.argmax(self.ptmat @ self.store.Z[fact_idx]))]

    def abstain_hop1(self, q_ids: set[str], relation: str) -> bool:
        """True if hop 1 for `relation` should abstain (coverage OR
        relation-classification mismatch)."""
        r = self.store.query(self.pt[relation], q_ids or None, k=1,
                             id_weight=self.id_weight)
        if not r:
            return True
        f = r[0][0]
        cov = len(q_ids & self.store.ids[f]) / max(len(q_ids), 1)
        return cov < self.cov_abstain or self.classify(f) != relation

    # ---- execution ------------------------------------------------------
    def walk(self, q_ids: set[str], chain: list[str]) -> int | None:
        """Execute a relation chain from the entities named in q_ids.
        Returns the final fact index, or None on hop-1 coverage abstention.
        Note: the question gist is deliberately NOT an argument."""
        for rel in chain:
            if rel not in self.pt:
                raise ValueError(f"unknown relation {rel!r}")
        visited: set[int] = set()
        hand = q_ids
        cur = None
        for k, rel in enumerate(chain):
            r = self.store.query(self.pt[rel], hand or None, k=2,
                                 id_weight=self.id_weight,
                                 exclude=visited if k else None)
            if not r:
                return None
            cur = r[0][0]
            visited.add(cur)
            cov = len(hand & self.store.ids[cur]) / max(len(hand), 1)
            if k == 0 and cov < self.cov_abstain:
                return None
            hand = self.store.content_ids[cur] - hand
        return cur
