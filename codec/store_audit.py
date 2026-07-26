"""Phase-A audit instrumentation (observation ONLY; D67).

Enabled by FOUNDATION_STORE_AUDIT=1. Counts, never alters:
  bug1: PQStore._scores() served from a GPU cache built BEFORE the most
        recent supersede() (the stale-cache pattern).
  bug2: query() selections where fewer than k candidates have finite
        scores after shadow/exclude masking; zero-finite separately.
"""
from __future__ import annotations
import os

ENABLED = os.environ.get("FOUNDATION_STORE_AUDIT") == "1"
counters = {"queries": 0, "deficit_lt_k": 0, "zero_finite": 0,
            "pq_scores_calls": 0, "pq_cache_uses": 0,
            "pq_stale_cache_uses": 0, "supersedes": 0}


def report() -> dict:
    return dict(counters)


def dump(tag: str = "") -> None:
    if ENABLED:
        print(f"[store-audit{(' ' + tag) if tag else ''}] {report()}",
              flush=True)
