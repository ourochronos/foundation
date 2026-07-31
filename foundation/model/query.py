"""Asking the store a question (docs/24 §6), and refusing to answer it.

Storage, merge and conflict have now been walked over real data. This is the
surface that has never been touched, and it carries the claims that make the
whole design worth anything:

- expansion moves **up the lattice only** — asking for `parent_of` must also
  match `mother_of` claims, and asking for `mother_of` must never match
  `parent_of` claims, because that invents a gender no source gave;
- the store **structures** disagreement and never resolves it, returning every
  surviving candidate with its sources, scopes and conflicts;
- it **refuses** rather than guessing when its edges do not license an answer.

The last one is the point of the project and the easiest to get quietly wrong:
a store that answers anyway, from thin or absent evidence, is exactly the thing
this is meant not to be. So `Adjudication.refusal` is set by the *store*, and a
renderer that ignores it is lying rather than merely being unhelpful.

Nothing here picks a winner. `answers` may legitimately come back with two
mutually contradictory entries and a conflict explaining why both survive.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field

from .conflict import (Claim, conflicts, independent_sources, norm_text,
                       proposition_key, scopes_overlap, _tc)


@dataclass
class Answer:
    """One surviving candidate. Never 'the' answer."""
    object_sort: str
    object: object
    predicate: str                       # the predicate ACTUALLY claimed
    sources: set = field(default_factory=set)
    claims: list = field(default_factory=list)
    scopes: list = field(default_factory=list)

    @property
    def support(self) -> int:
        return len(self.sources)


@dataclass
class Adjudication:
    """What the store returns: candidates, disagreement, and a refusal flag."""
    subject: str
    predicate: str
    answers: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    refusal: str | None = None
    expanded_from: set = field(default_factory=set)

    @property
    def answered(self) -> bool:
        return self.refusal is None and bool(self.answers)


def ask(claims, subject: str, predicate: str, closure=None, lattice=None,
        functional=frozenset(), min_sources: int = 1,
        scope=None) -> Adjudication:
    """Query one (subject, predicate) against a claim set.

    `min_sources` is the refusal threshold: a candidate backed by fewer
    independent sources than this does not license an answer. It is a policy
    input rather than a constant because what counts as enough support is the
    caller's judgement, not the store's — but the store enforces whatever it is
    told and reports the refusal, instead of silently returning weak answers
    and letting a renderer decide.
    """
    canon = closure.canonicalise if closure is not None else (lambda r: r)
    subj, pred = canon(subject), norm_text(predicate)

    # Up-lattice expansion: a claim on a MORE SPECIFIC predicate entails the
    # question. The reverse direction is never consulted — that is the whole
    # asymmetry, and reading it backwards invents information.
    wanted = (lattice.specialisations(pred) if lattice is not None else {pred})
    by_hash = {c.hash: c for c in claims if c.hash}

    hits = [c for c in claims
            if canon(c.subject) == subj and norm_text(c.predicate) in wanted
            and c.polarity
            and (scope is None
                 or scopes_overlap(_tc(c.qualifiers), scope, lattice))]

    adj = Adjudication(subj, pred, expanded_from=wanted - {pred})
    if not hits:
        adj.refusal = ("no edge: the store holds no claim on this subject for "
                       "this predicate or anything below it")
        return adj

    groups = collections.defaultdict(list)
    for c in hits:
        groups[proposition_key(c, closure, with_polarity=False)].append(c)
    for _, g in sorted(groups.items()):
        src = set()
        for c in g:
            src |= independent_sources(c, by_hash)
        adj.answers.append(Answer(g[0].object_sort, g[0].object,
                                  norm_text(g[0].predicate), src, list(g),
                                  [dict(_tc(c.qualifiers)) for c in g]))
    adj.answers.sort(key=lambda a: (-a.support, str(a.object)))

    # Conflicts are REPORTED, never used to drop a candidate.
    adj.conflicts = conflicts(hits, closure, functional, lattice)

    if all(a.support < min_sources for a in adj.answers):
        adj.refusal = (f"insufficient support: best candidate has "
                       f"{max(a.support for a in adj.answers)} independent "
                       f"source(s), policy requires {min_sources}")
    return adj
