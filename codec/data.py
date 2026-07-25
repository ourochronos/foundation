"""Proposition dataset loading, validation, dedup, and splitting.

Input: JSONL files with fields text / entities / numbers / domain, produced by
generator subagents (docs/02-codec.md). Labels are generator-self-reported, so
`validate` re-checks every entity/number against the text verbatim and drops
labels that don't appear; propositions themselves are kept.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Proposition:
    text: str
    entities: list[str] = field(default_factory=list)
    numbers: list[str] = field(default_factory=list)
    domain: str = "unknown"

    def to_json(self) -> str:
        return json.dumps(
            {"text": self.text, "entities": self.entities,
             "numbers": self.numbers, "domain": self.domain},
            ensure_ascii=False,
        )


def _norm_key(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def load_dir(path: str | Path) -> tuple[list[Proposition], dict]:
    """Load, validate, and dedupe all *.jsonl under `path`. Returns (props, stats)."""
    props: list[Proposition] = []
    stats = {"files": 0, "lines": 0, "parse_errors": 0, "dropped_labels": 0,
             "dupes": 0, "by_domain": {}}
    seen: set[str] = set()

    for f in sorted(Path(path).glob("*.jsonl")):
        stats["files"] += 1
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            stats["lines"] += 1
            try:
                obj = json.loads(line)
                text = str(obj["text"]).strip()
            except (json.JSONDecodeError, KeyError, TypeError):
                stats["parse_errors"] += 1
                continue
            if not text:
                stats["parse_errors"] += 1
                continue

            key = _norm_key(text)
            if key in seen:
                stats["dupes"] += 1
                continue
            seen.add(key)

            # keep only labels that appear verbatim in the text
            ents, nums = [], []
            for e in obj.get("entities") or []:
                if isinstance(e, str) and e in text:
                    ents.append(e)
                else:
                    stats["dropped_labels"] += 1
            for n in obj.get("numbers") or []:
                if isinstance(n, str) and n in text:
                    nums.append(n)
                else:
                    stats["dropped_labels"] += 1

            domain = str(obj.get("domain", "unknown"))
            props.append(Proposition(text, ents, nums, domain))
            stats["by_domain"][domain] = stats["by_domain"].get(domain, 0) + 1

    stats["kept"] = len(props)
    return props, stats


def split(props: list[Proposition], eval_frac: float = 0.1) -> tuple[list[Proposition], list[Proposition]]:
    """Deterministic hash split — stable across runs and file order."""
    train, evals = [], []
    threshold = int(eval_frac * 2**32)
    for p in props:
        h = int.from_bytes(hashlib.sha256(p.text.encode()).digest()[:4], "big")
        (evals if h < threshold else train).append(p)
    return train, evals


def save_jsonl(props: list[Proposition], path: str | Path) -> None:
    Path(path).write_text("\n".join(p.to_json() for p in props) + "\n", encoding="utf-8")
