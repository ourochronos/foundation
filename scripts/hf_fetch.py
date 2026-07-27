"""HF parts-inventory fetcher (docs/13 P2, block 4 of the pass plan).

Top models by downloads per pipeline tag relevant to our stack; keeps the
FULL model card markdown (immutable source layer) + API metadata. Stages
claim-extraction shards; the card->claims fleet runs a later pass.

Usage: .venv/bin/python scripts/hf_fetch.py
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "data" / "hf" / "cards"
SHARDS = ROOT / "data" / "hf" / "shards"
CARDS.mkdir(parents=True, exist_ok=True)
SHARDS.mkdir(parents=True, exist_ok=True)
HDR = {"User-Agent": "foundation-research/0.1 (zonk1024@gmail.com)"}
TAGS = ["feature-extraction", "sentence-similarity",
        "token-classification", "text-classification",
        "zero-shot-classification"]

seen = set()
for tag in TAGS:
    # BALANCED ADMISSION (user 2026-07-27): union of top-40 by 30-day
    # downloads AND top-40 by all-time — recency momentum + durable
    # staples; both numbers recorded as dated observations.
    pool = []
    for sort_key in ("downloads", "downloadsAllTime"):
        try:
            r = requests.get("https://huggingface.co/api/models",
                             params={"pipeline_tag": tag,
                                     "sort": sort_key, "direction": "-1",
                                     "limit": "40",
                                     "expand[]": "downloadsAllTime"},
                             headers=HDR, timeout=60)
            if r.status_code == 200:
                pool += r.json()
        except Exception as e:
            print(f"[hf] ! {tag}/{sort_key}: {e}", flush=True)
        time.sleep(0.5)
    for m in pool:
        mid = m.get("modelId") or m.get("id")
        if not mid or mid in seen:
            continue
        seen.add(mid)
        try:
            card = requests.get(
                f"https://huggingface.co/{mid}/raw/main/README.md",
                headers=HDR, timeout=60)
            md = card.text if card.status_code == 200 else ""
        except Exception:
            md = ""
        slug = re.sub(r"[^A-Za-z0-9_.-]+", "__", mid)[:120]
        (CARDS / f"{slug}.json").write_text(json.dumps({
            "id": mid, "pipeline_tag": tag,
            "downloads": m.get("downloads"),
            "downloads_all_time": m.get("downloadsAllTime"),
            "likes": m.get("likes"),
            "license": next((t.split(":", 1)[1] for t in
                             m.get("tags", []) if
                             t.startswith("license:")), None),
            "tags": m.get("tags", [])[:40], "card_md": md[:60000]}))
        time.sleep(0.5)
    print(f"[hf] {tag}: total {len(seen)}", flush=True)

cards = [json.loads(p.read_text()) for p in sorted(CARDS.glob("*.json"))]
per = 20
n = (len(cards) + per - 1) // per
for i in range(n):
    (SHARDS / f"in_{i}.json").write_text(json.dumps(
        [{k: c[k] for k in ("id", "pipeline_tag", "downloads", "license",
                            "card_md")} for c in
         cards[i * per:(i + 1) * per]]))
print(f"[done] {len(cards)} cards -> {n} shards", flush=True)
