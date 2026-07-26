"""External associative store over triple-latent entries (Phase 2, docs/04).

Entry = (gist z, identity token set, text, shadow flag). Addressing per D3's
channel ownership:
  gist        kNN cosine in the whitened space — the retrieval geometry the
              backbone was chosen for (D2) and the amp channel deliberately
              never touches (D20)
  identities  exact-overlap rescoring — near-duplicate facts ("The capital of
              X is ...") differ ONLY in identities, so this is where
              discrimination among distractors has to come from
  relational  query = z_question + t_relation, a TRANSLATION (D15); operators
              are fit from example (question, fact) pairs, closed-form

Supersession: a write may `shadow` earlier entries — the knowledge-edit
mechanism. Shadowed entries stay (provenance, inspectability) but are skipped
at query time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

_WORD = re.compile(r"[A-Za-z][\w'-]*|\d[\d,.:]*")


def id_tokens(strings: list[str]) -> set[str]:
    """Identity strings -> normalized token set ('Barden Group' -> {barden,
    group}; '4,200' -> {4200})."""
    out = set()
    for s in strings:
        for w in _WORD.findall(s):
            out.add(w.replace(",", "").lower())
    return out


@dataclass
class MemoryStore:
    dim: int = 1024
    Z: np.ndarray = None                    # [N, dim] unit gists
    ids: list[set] = field(default_factory=list)         # ADDRESS ids
    content_ids: list[set] = field(default_factory=list)  # the entry's OWN
    # entities — what a walk may hand off. Diverges from `ids` only after
    # supersession: the old object must stay ADDRESSABLE ("who replaced
    # X?") but must NOT ride the hand-off into the next hop (measured on
    # MQuAKE: blanket union made post-edit walks carry old+new objects,
    # compounding to 0.39/0.11/0.04 over 2/3/4 hops — D55).
    texts: list[str] = field(default_factory=list)
    shadowed: list[bool] = field(default_factory=list)

    def add(self, z: np.ndarray, identities: list[str], text: str) -> int:
        z = np.asarray(z, dtype=np.float32)
        if z.shape != (self.dim,):
            raise ValueError(f"expected gist of shape ({self.dim},), "
                             f"got {z.shape}")
        z = (z / (np.linalg.norm(z) + 1e-12))[None]
        self.Z = z if self.Z is None else np.concatenate([self.Z, z])
        toks = id_tokens(identities)
        self.ids.append(toks)
        self.content_ids.append(set(toks))
        self.texts.append(text)
        self.shadowed.append(False)
        return len(self.texts) - 1

    def shadow(self, idx: int) -> None:
        self.shadowed[idx] = True

    def supersede(self, old_idx: int, new_idx: int) -> None:
        """Shadow the old entry and give the new one its ADDRESS.

        Keys and values must separate at supersession: an update usually
        arrives event-phrased ("the capital was MOVED to Y") while queries
        keep arriving at the state-phrased address the old entry occupied
        ("which city serves as ..."). The old entry has already proven it
        sits where those queries land — the new entry inherits that key and
        contributes its own text/identities as the value. (Measured: without
        this, 7/20 post-edit queries drifted to the subject's OTHER fact.)
        """
        self.Z[new_idx] = self.Z[old_idx]
        self.ids[new_idx] = self.ids[new_idx] | self.ids[old_idx]
        # content_ids deliberately NOT unioned — hand-off carries only the
        # new entry's own entities
        self.shadowed[old_idx] = True

    def query(self, z_q: np.ndarray, query_ids: set[str] | None = None,
              k: int = 5, id_weight: float = 0.5,
              demote_ids: set[str] | None = None,
              exclude: set[int] | None = None):
        """Top-k live entries by cos(gist) + id_weight * identity-overlap.

        Overlap = |query_ids ∩ entry_ids| / |query_ids| (how much of what the
        query names does the entry cover). id_weight=0 -> pure gist kNN.
        demote_ids: identities to score AGAINST (a hop moves attention off
        the previous subject, not just onto the new one). exclude: visited
        entries — a graph walk must not return to its source node.
        """
        if self.Z is None:
            return []
        z_q = z_q / (np.linalg.norm(z_q) + 1e-12)
        score = self.Z @ z_q.astype(np.float32)
        if query_ids and id_weight:
            ov = np.array([len(query_ids & e) / max(len(query_ids), 1)
                           for e in self.ids], dtype=np.float32)
            score = score + id_weight * ov
        if demote_ids and id_weight:
            dv = np.array([len(demote_ids & e) / max(len(demote_ids), 1)
                           for e in self.ids], dtype=np.float32)
            score = score - id_weight * dv
        score = np.where(np.array(self.shadowed), -np.inf, score)
        if exclude:
            score[list(exclude)] = -np.inf
        top = np.argsort(-score)[:k]
        return [(int(i), float(score[i]), self.texts[i]) for i in top]


def fit_translation(Z_q: np.ndarray, Z_target: np.ndarray) -> np.ndarray:
    """Closed-form relation operator (D15): the mean displacement from
    question latents to their fact latents, on TRAIN pairs only."""
    d = Z_target - Z_q
    return d.mean(axis=0)
