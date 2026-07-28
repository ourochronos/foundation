"""Stigmergic curation: traversal deposits traces, traces rank the work.

Every curation gap this corpus has had was found by a query returning
nothing and a human noticing — `cited_by` ambiguous over 16 eids, the
citation and resource axes with zero paths between them. The signal was
always there; nobody collected it.

Both polarities matter and the system already emits both:
  * a hop that ABSTAINS says an edge or a document is missing → link/fetch
  * a hop that returns AMBIGUOUS says one name covers two things → split

Four constraints, each from a measured result, shape what this may do:

1. **Append-only, never rewriting stored representations.** Global
   statistics in persistent paths is precisely what B1/B1b refuted, and
   not re-projecting anything old is the whole reindex-free property.
   Traces are their own log; the store never learns from them directly.
2. **Propose, never dispose.** A false merge is unrecoverable and a false
   split is repairable (D49/D52), so reinforcement may nominate a link
   and may never make one.
3. **Steering is separate from evidence.** `cited_by` counts are what a
   user sees; if traffic fed them, popular paths would manufacture their
   own corroboration. Traces live in a different file and never touch a
   count.
4. **Never in the answer path.** Traces may reorder what is CONSIDERED;
   they may not affect what is ASSERTED. The measured 0.000-wrong-answer
   property dies the moment a well-trodden path answers because it is
   well-trodden.
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "results" / "query_traces.jsonl"


class TraceLog:
    """Collects per-hop outcomes from answer surfaces."""

    def __init__(self, path: Path | None = None):
        self.path = path or LOG
        self.rows: list[dict] = []

    def record(self, query: str, pids: list[str], result: dict) -> None:
        for t in result.get("trace", []):
            self.rows.append({"query": query, "path": "/".join(pids),
                              "hop": t["hop"], "pid": t["pid"],
                              "subject": t["subject"],
                              "status": t["status"]})

    def flush(self) -> int:
        with self.path.open("a") as f:
            for r in self.rows:
                f.write(json.dumps(r) + "\n")
        n, self.rows = len(self.rows), []
        return n


def report(rows: list[dict], top: int = 12) -> dict:
    """Rank curation debt by how often traversal actually hit it.

    Demand-weighted by construction: an entity nobody traverses never
    appears, which is the point — curate what is used, not what exists.
    """
    missing = collections.Counter()      # abstain → link or fetch
    ambiguous = collections.Counter()    # ambiguous → split
    edge = collections.Counter()         # which transition fails
    for r in rows:
        if r["status"] == "abstain":
            missing[(r["pid"], r["subject"])] += 1
            edge[(r["hop"], r["pid"], "abstain")] += 1
        elif r["status"] == "ambiguous":
            ambiguous[r["subject"]] += 1
            edge[(r["hop"], r["pid"], "ambiguous")] += 1
    return {
        "hops_traced": len(rows),
        "blocked_transitions": [
            {"hop": h, "pid": p, "status": s, "n": n}
            for (h, p, s), n in edge.most_common()],
        "fetch_or_link_candidates": [
            {"pid": p, "subject": s, "blocked_queries": n}
            for (p, s), n in missing.most_common(top)],
        "split_candidates": [
            {"subject": s, "blocked_queries": n}
            for s, n in ambiguous.most_common(top)],
        "note": ("Candidates are PROPOSALS. Acting on one goes through the "
                 "same acceptance discipline as any other curation — the "
                 "trace ranks the work, it does not do the work."),
    }
