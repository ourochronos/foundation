"""Canonicalise resource OBJECTS and isolate model-as-target claims (D99).

Two residual families, handled by the tool suited to each:

1. **Surface variants** — `ALFWorld`/`AlFWorld`, `Qwen 2.5`/`Qwen2.5`,
   `SWE-Bench`/`SWE-bench`. Case and punctuation only, so this is a
   deterministic fold and needs no judgement. Deliberately CONSERVATIVE:
   it folds case/space/hyphen and nothing else, so `Qwen2.5-7B` and
   `Qwen2.5-14B` stay apart — merging genuinely different model sizes
   would be a false merge, and those are unrecoverable (D49).

2. **Model-as-evaluation-target** — 49 claims typed `P_EVALUATES_ON`
   whose object is a model rather than a dataset. The typing prompt
   already forbids this and lost to the papers' own "we evaluate on
   GPT-3" phrasing, so detection moves out of the prompt and into a
   mechanical check; the surviving decision (adapt? compare? drop?) is
   narrow enough for one agent pass.

Usage: .venv/bin/python scripts/exp15_objects.py
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "data" / "arxiv_ai" / "shards_res_v2"
OUT = ROOT / "data" / "arxiv_ai" / "shards_modelcheck"
OUT.mkdir(exist_ok=True)

MODEL = re.compile(
    r"^(gpt|llama|qwen|gemma|mistral|deberta|roberta|bert|t5|phi|claude|"
    r"gemini|deepseek|vicuna|falcon|olmo|internvl|palm|mixtral|yi|baichuan|"
    r"chatglm|opt|bloom|pythia|starcoder|codellama)\b", re.I)


def fold(s: str) -> str:
    """Case + separator only. Nothing that could merge two real things."""
    return re.sub(r"[\s\-_./]+", "", s.lower())


rows = [json.loads(x) for f in sorted(V2.glob("out_*.jsonl"))
        for x in f.read_text().splitlines() if x.strip()]

# --- 1. deterministic object fold ----------------------------------------
groups: dict[str, collections.Counter] = collections.defaultdict(
    collections.Counter)
for r in rows:
    groups[fold(r["object"])][r["object"]] += 1

canon = {}
folded = 0
for key, forms in groups.items():
    if len(forms) < 2:
        continue
    # dominant = most claims, ties broken by longer form (keeps "SWE-Bench"
    # over a truncation, and keeps capitalisation that carries meaning)
    best = sorted(forms.items(), key=lambda kv: (-kv[1], -len(kv[0])))[0][0]
    for f_ in forms:
        if f_ != best:
            canon[f_] = best
            folded += forms[f_]

for r in rows:
    if r["object"] in canon:
        r["object_before_fold"] = r["object"]
        r["object"] = canon[r["object"]]
        r["statement"] = re.sub(re.escape(r["object_before_fold"]) + r"\.$",
                                r["object"] + ".", r["statement"])

# --- 2. isolate model-as-target claims for one narrow agent pass ---------
suspect = [r for r in rows
           if r["pid"] == "P_EVALUATES_ON" and MODEL.match(r["object"])]
items = [{"sid": r["src_sid"], "subject": r["subject"], "object": r["object"],
          "page": r["page"], "statement": r["statement"],
          "typing_why": r.get("typing_why", "")} for r in suspect]
(OUT / "in_0.json").write_text(json.dumps(items, indent=1))

for i in range(0, len(rows), 400):
    (V2 / f"out_{i // 400}.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows[i:i + 400]))

summary = {"claims": len(rows), "variant_groups_folded": len(
    {canon[k] for k in canon}), "claims_rewritten": folded,
    "folds": sorted({f"{k} -> {v}" for k, v in canon.items()}),
    "model_as_target_isolated": len(items)}
(ROOT / "results" / "exp15_objects.json").write_text(
    json.dumps(summary, indent=1))
print(json.dumps(summary, indent=1)[:1800])
