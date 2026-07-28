"""Mechanical filters over v2 resource claims (D100 residue).

Two defect families from the D100 audit that need no judgement:

1. **Generic terms** (`transformer`, `LSTM`, `SFT`) — 5 of my 10 defects.
   The extraction and typing prompts both name these as exclusions and
   both let them through, which is the D99 lesson repeating: a prompt
   rule that competes with the source's own phrasing loses, so the rule
   belongs in code. An architecture class is not an artifact.

2. **Self-invented components** — ATTEMPTED AND REJECTED. Sol caught a
   claim that CASC "builds on" a Graph Attention Transformer CASC itself
   introduces, so I tried a proxy: object appears in the paper's own
   title, or in an abstract "we introduce X" clause. It flagged 50 and
   is mostly WRONG — `Qwen2.5-Coder builds on Qwen2.5`, `SWE-Bench Pro
   builds on SWE-bench`, `DeepSeekMath is evaluated on MATH` all trip a
   substring test and are all correct; a derived artifact naturally
   contains its parent's name, and that IS the `P_BUILDS_ON` case. The
   proxy is kept in git history as a negative result and not shipped.
   Detecting "the paper invented this" needs the abstract's own claim
   structure, not string containment.

Usage: .venv/bin/python scripts/exp15_filters.py [--apply]
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "data" / "arxiv_ai" / "shards_res_v2"
SRC = ROOT / "data" / "arxiv_ai" / "shards_res"
APPLY = "--apply" in sys.argv

# Architecture classes, training paradigms and bare task names. Everything
# here is something a field DOES, not something a field SHIPS.
GENERIC = {
    "transformer", "transformers", "lstm", "rnn", "gru", "cnn", "mlp",
    "vae", "gan", "gans", "generative adversarial networks", "sft",
    "rl", "reinforcement learning", "supervised fine-tuning", "attention",
    "self-attention", "neural network", "neural networks", "autoencoder",
    "diffusion", "diffusion model", "diffusion models", "fine-tuning",
    "backpropagation", "gradient descent", "softmax", "dropout",
    "batch normalization", "layer normalization", "embedding",
    "embeddings", "tokenizer", "encoder", "decoder", "graph neural network",
    "graph neural networks", "gnn", "gnns", "convolutional neural network",
    "state space model", "state space models", "ssm", "mixture of experts",
    "moe", "knowledge distillation", "contrastive learning",
}
# Deliberately NOT generic: `U-Net` is a specific citable architecture with
# an author and a paper, unlike `transformer` as a class noun. The audit
# graded "neural surrogate builds on U-Net" PRECISE, and a blocklist that
# contradicts the frozen labels would be tuning the corpus to the gate.

papers = {}
for f in sorted(SRC.glob("in_*.json")):
    for p in json.loads(f.read_text()):
        papers["arxiv:" + p["arxiv_id"]] = p

rows = [json.loads(x) for f in sorted(V2.glob("out_*.jsonl"))
        for x in f.read_text().splitlines() if x.strip()]

INTRO = re.compile(r"\b(we|this paper|this work)\s+(introduce|present|propose"
                   r"|develop|design|build)s?\b[^.]{0,80}", re.I)

kept, dropped_generic, flagged_self = [], [], []
for r in rows:
    obj = r["object"].strip()
    if obj.lower() in GENERIC:
        dropped_generic.append(r)
        continue
    kept.append(r)

summary = {
    "input": len(rows),
    "dropped_generic": len(dropped_generic),
    "generic_objects": dict(collections.Counter(
        r["object"] for r in dropped_generic).most_common()),
    "self_invented_proxy": "REJECTED — see module docstring; string "
                           "containment cannot distinguish a derived "
                           "artifact from a self-invented one",
    "kept": len(kept), "applied": APPLY,
}
(ROOT / "results" / "exp15_filters.json").write_text(json.dumps(summary, indent=1))

if APPLY:
    for old in V2.glob("out_*.jsonl"):
        old.unlink()
    for i in range(0, len(kept), 400):
        (V2 / f"out_{i // 400}.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in kept[i:i + 400]))
    (V2 / "dropped_generic.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in dropped_generic))
print(json.dumps(summary, indent=1)[:2200])
