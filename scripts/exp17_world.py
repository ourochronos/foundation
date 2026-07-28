"""Express the REAL corpus as a v0.6-pipeline world (D110).

The planner (D41/D44) and the store have never met. Every real-store
number so far came from a human hand-specifying a relation path;
`chain(X, ['P_CITES','P_INTRODUCES','P_EVALUATES_ON'])` is not a question
anyone asks. This adapter is the wiring: it exports the AI component of
the live `poc` store in the shape `v06_pipeline.build_artifacts` expects,
so the closed-form artifacts (participation types, relation entries,
operators, range-cluster profiles) can be rebuilt over real claims and
the two small heads retrained against real questions.

Scope, deliberately: the arXiv component only — citations, the
title→method bridge, and the three resource relations. That is the
connected subgraph multi-hop was measured on (D107/D109). Wikipedia's
13k claims are a different shape and would confound the first
measurement of whether a synthetic-world planner transfers.

Questions are TEMPLATED with several phrasings per relation and the last
two held out, following the K5 frozen-template discipline (D48): a head
that only ever sees its training phrasings is measuring memorisation.
Templates are the honest ceiling here — this measures whether the
planner picks the right relation and walk, not whether it understands
free-form English, and the D-entry must say so.

Usage: .venv/bin/python scripts/exp17_world.py
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from foundation.kb import KB                                    # noqa: E402

AI_RELS = ("P_CITES", "P_INTRODUCES", "P_EVALUATES_ON",
           "P_BUILDS_ON", "P_COMPARES_TO")

# Several ways a person actually asks for each relation. Index >= 4 is
# held out — never trained on, only evaluated.
PHRASINGS = {
    "P_EVALUATES_ON": [
        "What benchmarks does {s} evaluate on?",
        "Which datasets is {s} tested on?",
        "What does {s} report results on?",
        "Which benchmark did {s} use?",
        "On what data was {s} assessed?",          # held
        "What did they run {s} against?",          # held
    ],
    "P_BUILDS_ON": [
        "What does {s} build on?",
        "Which model is {s} based on?",
        "What does {s} adapt?",
        "What is the backbone of {s}?",
        "What does {s} start from?",               # held
        "Which prior method does {s} extend?",     # held
    ],
    "P_COMPARES_TO": [
        "What does {s} compare against?",
        "Which baselines does {s} use?",
        "What is {s} measured against?",
        "Which systems does {s} beat?",
        "What did they benchmark {s} versus?",     # held
        "Who are {s}'s competitors?",              # held
    ],
    "P_CITES": [
        "What does {s} cite?",
        "Which papers does {s} reference?",
        "What prior work does {s} draw on?",
        "What is in {s}'s bibliography?",
        "Which works are cited by {s}?",           # held
        "What does {s} point to?",                 # held
    ],
    "P_INTRODUCES": [
        "What does {s} introduce?",
        "What method does {s} propose?",
        "What is {s}'s contribution?",
        "What does {s} present?",
        "What did {s} put forward?",               # held
        "What is new in {s}?",                     # held
    ],
}
HELD_FROM = 4


def main() -> None:
    kb = KB(backend="pg", table="poc")
    claims = [c for c in kb.claims
              if c["pid"] in AI_RELS and c["page"].startswith("arxiv:")]
    print(f"{len(claims)} arXiv-component claims over "
          f"{len({c['pid'] for c in claims})} relations")

    facts, seen = [], {}
    for c in claims:
        key = (c["subject"], c["pid"], c["object"])
        if key in seen:
            continue
        seen[key] = len(facts)
        facts.append({
            "subject": c["subject"], "relation": c["pid"],
            "object": c["object"],
            "text": kb.store.texts[c["idx"]],
            # id tokens are what the walker hands off between hops; the
            # store's own tokens are already the right ones
            "entities": sorted(kb.store.ids[c["idx"]]),
            "numbers": [], "year": None,
        })

    queries = []
    for i, f in enumerate(facts):
        for pi, tpl in enumerate(PHRASINGS[f["relation"]]):
            queries.append({"fact_idx": i, "relation": f["relation"],
                            "kind": "single", "phrasing_idx": pi,
                            "text": tpl.format(s=f["subject"])})

    world = {"facts": facts, "queries": queries,
             "held_out_phrasings": list(range(HELD_FROM,
                                              max(len(v) for v
                                                  in PHRASINGS.values()))),
             "hops": [], "holdout_compositions": []}
    out = ROOT / "data" / "real_world_ai.json"
    out.write_text(json.dumps(world))
    rc = collections.Counter(f["relation"] for f in facts)
    print(json.dumps({"facts": len(facts), "queries": len(queries),
                      "relations": dict(rc),
                      "held_out_phrasings": world["held_out_phrasings"],
                      "distinct_subjects": len({f["subject"]
                                                for f in facts})},
                     indent=1))
    print(f"[done] {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
