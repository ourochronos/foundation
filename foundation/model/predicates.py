"""The predicate lattice: subsumption and composition (docs/24).

Two relations between predicates, each sound in exactly one direction:

    subsumption   mother_of ⊑ parent_of              every mother is a parent
    composition   mother_of ∘ parent_of ⟹ grandmother_of

**Generalising and composing add no information. Specialising and decomposing
invent it.** From `mother_of(A,B)` it follows that `parent_of(A,B)`; from
`parent_of(A,B)` nothing follows about gender. From a mother-then-parent path a
grandmother follows; from `grandmother_of(A,C)` all that follows is that *some*
intermediate parent exists, and naming them would fabricate a person.

So every operation here moves **up** and none moves down. A query for
`parent_of` must also return `mother_of` claims; a query for `mother_of` must
never return `parent_of` claims.

**Nothing is materialised.** The v1 review argued for deleting predicate
algebra outright, and its argument was concrete: one wrong flag composed with
one wrong `sameAs` manufactures unbounded derived garbage that then floods the
conflict detector. That argument is entirely about *materialisation* and is
correct about it. Rewriting queries instead keeps the blast radius of a wrong
declaration at one query rather than the store — derived facts are never
stored, never merge, never propagate, and never need retracting.

Subsumption is used in one non-query place: conflict detection, which was
otherwise blind to `(X, mother_of, Y, +)` versus `(X, parent_of, Y, −)` — a
flat contradiction it could not see because it grouped on the literal
predicate string.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field


class LatticeError(ValueError):
    """A declaration that would make the lattice unsound."""


@dataclass
class Lattice:
    """Declared subsumption and composition over predicate uris.

    Declarations are ordinary claims elsewhere in the model; this is the
    derived index over the accepted ones, so it lives in Layer 4 and is
    rebuilt rather than migrated.
    """
    _up: dict[str, set[str]] = field(default_factory=lambda:
                                     collections.defaultdict(set))
    _paths: dict[tuple, set[str]] = field(default_factory=lambda:
                                          collections.defaultdict(set))
    _opp: dict[str, set[str]] = field(default_factory=lambda:
                                      collections.defaultdict(set))

    # ---------------------------------------------------------- subsumption --
    def subsume(self, sub: str, sup: str) -> None:
        """Declare `sub ⊑ sup`. Rejects cycles at registration.

        A cycle would make two distinct predicates mutually entailing, which
        silently collapses them — and it would make `ancestors` non-terminating
        for anyone who reimplemented it without the visited set.
        """
        if sub == sup:
            raise LatticeError(f"{sub!r} cannot subsume itself")
        if sub in self.ancestors(sup):
            raise LatticeError(
                f"{sub!r} ⊑ {sup!r} closes a cycle: {sup!r} already reaches "
                f"{sub!r}, which would make them mutually entailing")
        self._up[sub].add(sup)

    def ancestors(self, p: str) -> set[str]:
        """`p` and every predicate it entails. Safe direction, always."""
        seen, stack = {p}, [p]
        while stack:
            for nxt in self._up.get(stack.pop(), ()):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    def entails(self, sub: str, sup: str) -> bool:
        """Does a claim on `sub` entail the same claim on `sup`?"""
        return sup in self.ancestors(sub)

    def specialisations(self, p: str) -> set[str]:
        """Everything at or below `p` — what a query for `p` must ALSO match.

        This is the query-expansion direction and it is the mirror of
        `ancestors`: asking for `parent_of` must return `mother_of` claims,
        because a mother is a parent. It is emphatically NOT a licence to
        return `parent_of` claims when asked for `mother_of`.
        """
        return {q for q in set(self._up) | {p}
                if p in self.ancestors(q)} | {p}

    # ----------------------------------------------------------- opposition --
    def oppose(self, a: str, b: str) -> None:
        """Declare that `a(x,y)` entails NOT `b(x,y)` — and symmetrically.

        Subsumption alone made conflict detection blind to how disagreement
        actually looks. exp72 measured it on real philosophical positions: 15 of
        18 genuine oppositions were invisible, because

            Hard determinism:  determinism refutes         free will
            Compatibilism:     determinism compatible_with free will

        is a flat contradiction to a reader and two unrelated triples to a
        detector that only knows polarity and functional cardinality. Real
        intellectual disagreement is mostly not negation of one relation; it is
        assertion of an incompatible one.

        Opposition is **symmetric**, unlike subsumption — if `refutes` excludes
        `compatible_with` then the reverse holds too — so it is stored both
        ways and needs no direction rule.
        """
        if a == b:
            raise LatticeError(f"{a!r} cannot oppose itself")
        if self.entails(a, b) or self.entails(b, a):
            raise LatticeError(
                f"{a!r} and {b!r} cannot be both subsuming and opposed: one "
                f"entails the other, so asserting both would make every claim "
                f"on the narrower predicate self-contradictory")
        self._opp[a].add(b)
        self._opp[b].add(a)

    def opposes(self, a: str, b: str) -> bool:
        """Does a claim on `a` exclude the same claim on `b`?

        Opposition is inherited DOWNWARD: if `refutes` opposes
        `compatible_with`, then anything below `refutes` opposes anything below
        `compatible_with`, because each entails its ancestor.
        """
        return bool(self.ancestors(a) & set().union(
            *(self._opp.get(x, set()) for x in self.ancestors(b))) ) \
            if self.ancestors(b) else False

    # ---------------------------------------------------------- composition --
    def compose(self, path, composite: str) -> None:
        """Declare `path ⟹ composite`, e.g. [mother_of, parent_of] ⟹ grandmother_of."""
        path = tuple(path)
        if len(path) < 2:
            raise LatticeError("a composition needs at least two steps")
        if composite in path:
            raise LatticeError(
                f"{composite!r} appears in its own defining path, which would "
                f"let it derive itself without bound")
        self._paths[path].add(composite)

    def composites_for(self, path) -> set[str]:
        return set(self._paths.get(tuple(path), ()))

    def paths_for(self, composite: str) -> list[tuple]:
        """How a composite may be DERIVED — never how it may be decomposed.

        A stored `grandmother_of` claim is not rewritten into its path: the
        source did not say which parent, and inventing one is the fabrication
        this whole model refuses. Decomposition yields only an existential
        (`SOME`), which is why that marker exists.
        """
        return sorted(p for p, cs in self._paths.items() if composite in cs)
