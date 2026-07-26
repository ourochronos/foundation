"""Entity individuation (symbolic-channel v2) — docs/08, D49.

Identity ≠ surface form. The registry assigns opaque eids at write time via
a CLOSED-FORM resolver (no learning): surface overlap → slot/type gate →
functional-conflict gate → neighborhood score. Numbers stay surface tokens
(values, not individuals). Late equivalence = redirect, never rewrite.

The resolver's signals are all store content: what a candidate eid has done
(participation slots), who it connects to (neighbor eids), and whether
absorbing the incoming fact would violate a functional relation with a
CONFLICTING object — which is evidence of distinctness, not change, unless
the text marks an event (supersession's territory, handled upstream).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from codec.memory_store import id_tokens

_NUMERIC = re.compile(r"^[\d][\d,.\s]*$")


def is_value(s: str) -> bool:
    """Numbers/years are values, not individuals."""
    return bool(_NUMERIC.match(s.strip()))


@dataclass
class Entity:
    eid: str
    forms: set[str] = field(default_factory=set)        # full surface forms
    form_tokens: set[str] = field(default_factory=set)  # token union
    slots: dict = field(default_factory=dict)           # (rel, role) -> count
    functional: dict = field(default_factory=dict)      # (rel,'s') -> other eid
    neighbors: set[str] = field(default_factory=set)    # eids seen in shared facts
    anchor: np.ndarray | None = None                    # running mean fact gist
    n_anchor: int = 0
    redirect: str | None = None


class EntityRegistry:
    def __init__(self, tau_surf: float = 1.0):
        self.entities: dict[str, Entity] = {}
        self.by_form: dict[str, set[str]] = {}          # full form -> eids
        self.tau_surf = tau_surf
        self._n = 0

    # ---- helpers --------------------------------------------------------
    def _get(self, eid: str) -> Entity:
        e = self.entities[eid]
        while e.redirect:
            e = self.entities[e.redirect]
        return e

    def _mint(self, form: str) -> Entity:
        eid = f"e{self._n:05d}"
        self._n += 1
        e = Entity(eid=eid, forms={form}, form_tokens=id_tokens([form]))
        self.entities[eid] = e
        self.by_form.setdefault(form, set()).add(eid)
        return e

    def candidates(self, form: str) -> list[Entity]:
        return [self._get(eid) for eid in self.by_form.get(form, ())]

    # ---- write-time resolution (docs/08 §2) ------------------------------
    def resolve_write(self, form: str, rel: str, role: str,
                      other: str | None, fact_z: np.ndarray | None = None,
                      functional: bool = False) -> str:
        """Resolve a mention in an incoming fact to an eid (minting if
        needed) and record the fact's contribution. `other` is the other
        argument's eid (or None if it's a value). `functional` marks the
        (rel, subject) slot as one-object-per-subject."""
        cands = self.candidates(form)
        survivors, scored = [], []
        for c in cands:
            if functional and role == "s":
                held = c.functional.get((rel, "s"))
                if held is not None and other is not None and held != other:
                    continue                    # conflicting object: distinct
            score = (len(c.neighbors & {other}) if other else 0) \
                + 0.5 * bool(c.slots.get((rel, role)))
            survivors.append(c); scored.append(score)
        if len(survivors) == 1:
            e = survivors[0]        # same name, no contradiction: same thing
        elif survivors and max(scored) > 0:
            e = survivors[int(np.argmax(scored))]
        else:
            e = self._mint(form)    # 0 candidates, or several w/o evidence
        e.forms.add(form)
        e.form_tokens |= id_tokens([form])
        self.by_form.setdefault(form, set()).add(e.eid)
        e.slots[(rel, role)] = e.slots.get((rel, role), 0) + 1
        if functional and role == "s" and other is not None:
            e.functional[(rel, "s")] = other
        if other is not None:
            e.neighbors.add(other)
        if fact_z is not None:
            e.anchor = (fact_z.copy() if e.anchor is None
                        else (e.anchor * e.n_anchor + fact_z)
                        / (e.n_anchor + 1))
            e.n_anchor += 1
        return e.eid

    # ---- query-time resolution (docs/08 §3) ------------------------------
    def resolve_query(self, form: str, rel: str | None = None,
                      role: str = "s") -> list[str]:
        """Candidate eids for a query mention. If `rel` is given, keep only
        eids that have EVER filled that (rel, role) slot — the concrete form
        of the type gate (relation-existence check). Returns [] (unknown),
        [eid] (resolved), or several (genuinely ambiguous — caller must
        flag, not guess)."""
        cands = self.candidates(form)
        if rel is not None:
            hits = [c for c in cands if c.slots.get((rel, role))]
            if hits:
                cands = hits
        return [c.eid for c in cands]

    # ---- merges (docs/08 §5) ---------------------------------------------
    def merge(self, keep: str, absorb: str) -> None:
        a, k = self._get(absorb), self._get(keep)
        if a.eid == k.eid:
            return
        k.forms |= a.forms
        k.form_tokens |= a.form_tokens
        for slot, n in a.slots.items():
            k.slots[slot] = k.slots.get(slot, 0) + n
        k.functional.update({s: o for s, o in a.functional.items()
                             if s not in k.functional})
        k.neighbors |= a.neighbors
        for f in a.forms:
            self.by_form.setdefault(f, set()).add(k.eid)
        a.redirect = k.eid


def functional_relations(facts: list[dict]) -> set[str]:
    """Relations with ~one object per subject, derived by counting."""
    from collections import defaultdict
    objs = defaultdict(set)
    for f in facts:
        objs[(f["relation"], f["subject"])].add(f["object"])
    per_rel = defaultdict(list)
    for (r, _s), o in objs.items():
        per_rel[r].append(len(o))
    return {r for r, ns in per_rel.items()
            if sum(ns) / len(ns) <= 1.05}
