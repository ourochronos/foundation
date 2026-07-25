"""HopEnv — the reasoner's environment over the memory store (C1, plan §C).

Design fixed by measurement (docs/05-reasoner.md v2):
- Actions are DISCRETE hop calls, not latent transforms (D26/D27/D30):
    relation choice   index into the fitted operator inventory
    hand-off mask     WHICH of the current entry's id tokens to promote —
                      selective, because the naive ids(entry)−ids(source)
                      mask is the first-order failure under collisions (D30)
    walk knobs        demote/exclude are SOFT action components, not
                      invariants (D30 retracted them: they hurt on revisit)
    HALT / ABSTAIN    terminal actions; abstention signal exists (id-coverage
                      AUC 0.952, B2) — the env exposes it as an observation
- Observations are cheap store-response readouts (B2): top-k scores, margin,
  id-coverage, plus the current entry's channels. No latent prediction error
  anywhere (D24: flat by construction).

The ORACLE POLICY (the D30 hand-coded walk) lives here too — it is the
imitation floor (per-composition: cap_pop 0.808 ... 3-hop 0.000) and the
trace generator for behavior cloning (C2).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from codec.memory_store import MemoryStore

HALT = -1
ABSTAIN = -2


@dataclass
class Obs:
    """What the policy sees at each step."""
    step: int
    q_z: np.ndarray                 # question gist (fixed for the episode)
    q_ids: set                      # question identity tokens
    cur_z: np.ndarray | None        # current entry gist (None at step 0)
    cur_ids: set | None             # current entry id tokens
    cur_text: str | None
    top_score: float = 0.0          # B2 readouts from the LAST retrieval
    margin: float = 0.0
    id_cov: float = 0.0


@dataclass
class Action:
    relation: int                   # index into env.relations, or HALT/ABSTAIN
    hand_ids: set = field(default_factory=set)   # promote (selective mask)
    demote_ids: set = field(default_factory=set)  # soft demotion set
    exclude_visited: bool = True


class HopEnv:
    def __init__(self, store: MemoryStore, relations: list[str],
                 t_by_rel: dict[str, np.ndarray], id_weight: float = 0.5,
                 max_steps: int = 4):
        self.store = store
        self.relations = relations
        self.t = t_by_rel
        self.id_weight = id_weight
        self.max_steps = max_steps

    def reset(self, q_z: np.ndarray, q_ids: set) -> Obs:
        self.visited: set[int] = set()
        self.cur: int | None = None
        self.n = 0
        self.obs = Obs(step=0, q_z=q_z, q_ids=q_ids,
                       cur_z=None, cur_ids=None, cur_text=None)
        return self.obs

    def step(self, a: Action) -> tuple[Obs, bool]:
        """Returns (obs, done). Terminal actions set obs.cur_* as the answer
        (HALT) or None (ABSTAIN)."""
        if a.relation in (HALT, ABSTAIN):
            if a.relation == ABSTAIN:
                self.cur = None
            return self.obs, True
        self.n += 1
        rel = self.relations[a.relation]
        base = self.obs.q_z if self.cur is None else self.store.Z[self.cur]
        z = base + self.t[rel]
        r = self.store.query(
            z, a.hand_ids or None, k=2,
            id_weight=self.id_weight if (a.hand_ids or a.demote_ids) else 0.0,
            demote_ids=a.demote_ids or None,
            exclude=self.visited if (a.exclude_visited and self.visited) else None)
        top1, top2 = r[0], (r[1] if len(r) > 1 else (None, -np.inf, ""))
        self.cur = top1[0]
        self.visited.add(top1[0])
        cov = (len(a.hand_ids & self.store.ids[top1[0]]) / max(len(a.hand_ids), 1)
               if a.hand_ids else
               len(self.obs.q_ids & self.store.ids[top1[0]])
               / max(len(self.obs.q_ids), 1))
        self.obs = Obs(step=self.n, q_z=self.obs.q_z, q_ids=self.obs.q_ids,
                       cur_z=self.store.Z[top1[0]],
                       cur_ids=self.store.ids[top1[0]],
                       cur_text=self.store.texts[top1[0]],
                       top_score=top1[1], margin=top1[1] - top2[1],
                       id_cov=cov)
        return self.obs, self.n >= self.max_steps


def oracle_policy(env: HopEnv, obs: Obs, chain: list[str],
                  abstain_cov: float = 0.34) -> Action:
    """The D30 hand-coded walk as a policy: follows a GIVEN relation chain
    (the trained policy must learn to infer it), naive hand-off mask,
    hard walk semantics. Abstains when first-hop id-coverage is poor (B2's
    signal). This is the imitation floor, weak by measurement — per-
    composition floors in D30."""
    if obs.step >= len(chain):
        if obs.step > 0 and obs.id_cov < abstain_cov and obs.step == 1:
            return Action(relation=ABSTAIN)
        return Action(relation=HALT)
    rel_idx = env.relations.index(chain[obs.step])
    if obs.step == 0:
        return Action(relation=rel_idx, hand_ids=set(), demote_ids=set(),
                      exclude_visited=False)
    hand = (obs.cur_ids or set()) - obs.q_ids
    return Action(relation=rel_idx, hand_ids=hand, demote_ids=obs.q_ids,
                  exclude_visited=True)
