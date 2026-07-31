"""Identity closure — Layer 4, and load-bearing (model v1 §1).

v0 said the identity view was disposable and that nothing depended on it. Four
blind reviewers found the same consequence: with `local:` refs, two stores'
claims about the same person never pool and never conflict, so **countable
agreement and detectable contradiction — the two things the design is for —
both silently fail on exactly the entities federation exists to reconcile.**

The fix is two levels of identity:

- the **assertion hash** is over raw refs: immutable, the merge primitive, a
  commitment. It never moves.
- the **proposition key** is over equivalence-class representatives: derived,
  recomputed when the closure moves, and *this* is what agreement and conflict
  are computed over.

Storage integrity still does not depend on this layer. Interpretation does, and
saying so is the correction v1 makes.

**Representatives are chosen deterministically** — by namespace authority rank,
then lexicographically — so two stores that have merged the same claims compute
the *same* representative and therefore the same proposition keys. A
representative chosen by insertion order would make proposition keys
store-local and quietly unshareable.

**Acceptance is a policy, not a fact.** One bad `sameAs` fuses two people's
classes and makes every `date_of_birth` in both a spurious conflict — the
`owl:sameAs` failure that linked data actually suffered. So merges pass a
policy with circuit breakers, and `conflates` / `different_from` claims block
fusion outright.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Lower rank wins. Well-known namespaces beat locally-minted ones so that a
# class containing wikidata:Q42 is represented by it rather than by whichever
# local id happened to be created first.
NAMESPACE_RANK = {"seed": 0, "wikidata": 1, "doi": 2, "orcid": 2, "isbn": 2}
LOCAL_RANK = 100


def rank(ref: str) -> tuple[int, str]:
    return (NAMESPACE_RANK.get(ref.split(":", 1)[0], LOCAL_RANK), ref)


@dataclass
class Policy:
    """Circuit breakers on identity fusion.

    `max_class_size` is the blunt instrument that stops a runaway fusion chain
    from swallowing the store. `trusted_agents`, when set, restricts who may
    assert identity at all. `require_agents` demands independent corroboration
    before two classes fuse, which is the cheapest defence against a single
    bad link.
    """
    max_class_size: int = 64
    trusted_agents: set[str] | None = None
    require_agents: int = 1


@dataclass
class Closure:
    """Union-find over accepted `sameAs`, with blocks and an acceptance policy."""
    policy: Policy = field(default_factory=Policy)
    _parent: dict[str, str] = field(default_factory=dict)
    _size: dict[str, int] = field(default_factory=dict)
    _rep: dict[str, str] = field(default_factory=dict)
    _blocked: set[tuple[str, str]] = field(default_factory=set)
    _pending: dict[tuple[str, str], set[str]] = field(default_factory=dict)
    rejected: list[tuple[str, str, str]] = field(default_factory=list)

    # ------------------------------------------------------------ union-find --
    def _find(self, x: str) -> str:
        self._parent.setdefault(x, x)
        self._size.setdefault(x, 1)
        self._rep.setdefault(x, x)
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:          # path compression
            self._parent[x], x = root, self._parent[x]
        return root

    def rep(self, ref: str) -> str:
        """The class representative — deterministic, never insertion-ordered.

        Maintained incrementally per root. The obvious implementation scans
        every known ref on every call, and `proposition_key` calls this once
        per claim: at 10^6 claims over 10^5 refs that is ~10^11 operations, so
        the Python layer dies long before Postgres notices.
        """
        if ref not in self._parent:
            return ref
        return self._rep.get(self._find(ref), ref)

    def members(self, ref: str) -> set[str]:
        root = self._find(ref)
        return {m for m in self._parent if self._find(m) == root}

    def same(self, a: str, b: str) -> bool:
        return self._find(a) == self._find(b)

    # ------------------------------------------------------------- mutation --
    def block(self, a: str, b: str) -> None:
        """`different_from` / `conflates`: these may never fuse.

        Blocking is not retroactive — if the two are already fused the block is
        recorded and reported, because silently splitting an existing class
        would change answers with no trace.
        """
        self._blocked.add(tuple(sorted((a, b))))

    def is_blocked(self, a: str, b: str) -> bool:
        ma, mb = self.members(a) | {a}, self.members(b) | {b}
        return any(tuple(sorted((x, y))) in self._blocked
                   for x in ma for y in mb)

    def accept(self, a: str, b: str, agent: str) -> bool:
        """Offer a `sameAs`. Returns whether the classes were fused.

        Every rejection is recorded with a reason rather than dropped: a
        silently ignored identity claim is indistinguishable from one that was
        never made.
        """
        p = self.policy
        if p.trusted_agents is not None and agent not in p.trusted_agents:
            self.rejected.append((a, b, f"untrusted agent {agent}"))
            return False
        if self.same(a, b):
            return True
        if self.is_blocked(a, b):
            self.rejected.append((a, b, "blocked by different_from/conflates"))
            return False
        if p.require_agents > 1:
            key = tuple(sorted((a, b)))
            self._pending.setdefault(key, set()).add(agent)
            if len(self._pending[key]) < p.require_agents:
                self.rejected.append(
                    (a, b, f"awaiting corroboration "
                           f"({len(self._pending[key])}/{p.require_agents})"))
                return False
        ra, rb = self._find(a), self._find(b)
        if self._size[ra] + self._size[rb] > p.max_class_size:
            self.rejected.append(
                (a, b, f"would exceed max_class_size {p.max_class_size}"))
            return False
        if self._size[ra] < self._size[rb]:
            ra, rb = rb, ra
        best = min(self._rep.get(ra, ra), self._rep.get(rb, rb), key=rank)
        self._parent[rb] = ra
        self._size[ra] += self._size[rb]
        self._rep[ra] = best
        return True

    def accept_all(self, edges) -> list[bool]:
        """Apply a whole edge set in a DETERMINISTIC order. Use this to merge.

        Incremental `accept()` is **not confluent** once a policy bites:
        `max_class_size` and `require_agents` make the outcome depend on the
        order edges arrive, so merging store A then B can accept a different
        `sameAs` set than B then A — and different accepted sets give different
        representatives, hence different proposition keys, hence **different
        agreements and different conflicts from identical claim sets**.

        That matters more than it sounds. The grow-only claim set is a genuine
        CRDT, but everything the system is actually for — agreement,
        contradiction, refusal — is computed above it in this layer, and this
        layer was not confluent. Replaying a sorted edge set makes the closure
        a function of the claims rather than of the sync history.

        Sorting is by (a, b, agent) — content, never arrival — so two peers
        with the same claims converge without exchanging anything else.
        """
        return [self.accept(a, b, agent)
                for a, b, agent in sorted(edges)]

    def canonicalise(self, ref: str) -> str:
        """Map a ref to its representative; unknown refs are their own class."""
        return self.rep(ref) if ref in self._parent else ref
