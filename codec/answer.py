"""Answer surface (L4) — walked result → one honest sentence.

Statuses map 1:1 to the measured readouts: `answered` (walk hit),
`ambiguous` (multiple eids survived query-time resolution, D52 flag),
`abstain` (plan failure or hop-1 readout, D44), `conflict` (near-tie
between differently-sourced entries, Track I). Template-first; the
decoder_v2t path is optional garnish, never load-bearing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Answer:
    status: str                    # answered | ambiguous | abstain | conflict
    text: str
    fact_text: str | None = None   # provenance: the store entry answered from
    obj: str | None = None
    candidates: list | None = None


def render(question: str, *, obj: str | None = None,
           fact_text: str | None = None, ambiguous_forms: list | None = None,
           conflict_sources: list | None = None) -> Answer:
    if ambiguous_forms:
        opts = "; ".join(ambiguous_forms[:4])
        return Answer("ambiguous", f"That's ambiguous — I know more than "
                                   f"one entity that matches ({opts}). "
                                   f"Which one do you mean?",
                      candidates=ambiguous_forms)
    if conflict_sources:
        srcs = " vs ".join(conflict_sources[:2])
        return Answer("conflict", f"My sources disagree on this ({srcs}). "
                                  f"Tell me which to prefer, or ask "
                                  f"\"according to …\".",
                      candidates=conflict_sources)
    if obj is None:
        return Answer("abstain", "I don't have that in the store — "
                                 "I'd rather say so than guess.")
    return Answer("answered", obj if question.rstrip().endswith("?")
                  else f"{obj}.", fact_text=fact_text, obj=obj)
