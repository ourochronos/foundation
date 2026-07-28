"""Type a resource name using the HuggingFace parts inventory (D105).

Relational participation (D104) types resources the corpus uses often —
37 of 719 objects reach the 3-paper threshold. Everything below it is
untypeable by vote, and that tail is where the model-as-target defect
survives: `Pillar-0`, `EEG Conformer`, `TinyLlama-1.1B` are each used by
one or two papers, so no majority exists to consult.

The parts inventory answers the tail directly: a name in the HF registry
IS a model, regardless of how few papers cite it. This is the dogfood
premise doing real work — the components corpus typing the literature
corpus.

Matching is at FAMILY level, the same granularity the resource axis
declares (D100): the corpus writes `Qwen2.5` where HF writes
`Qwen2.5-7B-Instruct`. Exact matching found 13 objects; family matching
finds 38, of which 30 are tail cases the vote cannot reach.

The inventory must be sampled for this job. Ours originally covered only
retrieval/classification pipeline tags and matched 3 of 719 objects,
because the literature cites generative LLMs (D104). Widening the tags
to generation and multimodal is what made the oracle viable.
"""
from __future__ import annotations

import collections
import functools
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "data" / "hf" / "cards"

# size, revision and variant suffixes — everything the granularity policy
# folds away. Applied repeatedly: `Qwen2.5-7B-Instruct` -> `Qwen2.5`.
_SUFFIX = re.compile(
    r"[-_ ]?(\d+\.?\d*[bm]|instruct|chat|base|it|preview|schnell|dev|"
    r"v\d+(\.\d+)?|mini|small|medium|large|xl|xxl|tiny|nano|flash|turbo|"
    r"thinking|a\d+b)$", re.I)


def _fold(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def family(name: str) -> str:
    """Fold a model name to its family key."""
    n = name.split("/")[-1]
    for _ in range(4):
        m = _SUFFIX.search(n)
        if not m:
            break
        n = n[:m.start()]
    return _fold(n)


@functools.lru_cache(maxsize=1)
def _index() -> dict[str, set]:
    idx: dict[str, set] = collections.defaultdict(set)
    for p in CARDS.glob("*.json"):
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        f = family(d.get("id", ""))
        if len(f) >= 3:            # 1-2 char families collide on everything
            idx[f].add(d["id"])
    return dict(idx)


def is_model(name: str) -> bool:
    """True when the HF registry knows this name as a model."""
    return family(name) in _index()


def evidence(name: str) -> list[str]:
    """The registry ids backing an `is_model` verdict, for provenance."""
    return sorted(_index().get(family(name), ()))
