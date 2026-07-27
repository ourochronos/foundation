"""Backfill revid + rev_timestamp into cached page JSONs (W2, D87).

Pages fetched before the provenance fix lack revids. This sweeps the
cache in batches of 50 titles per API call (polite), stamping the
CURRENT revision ids — an approximation for pre-fix pages (the text we
hold may be slightly older than the stamped revid; noted in D87), exact
for everything fetched from now on.

Usage: .venv/bin/python scripts/wiki_backfill_revids.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "wiki" / "pages"
API = "https://en.wikipedia.org/w/api.php"
HDR = {"User-Agent": "foundation-research/0.1 (zonk1024@gmail.com)"}

files = {}
for p in OUT.glob("*.json"):
    d = json.loads(p.read_text())
    if not d.get("revid"):
        files[d["title"]] = p

titles = sorted(files)
print(f"[backfill] {len(titles)} pages lack revids", flush=True)
done = 0
for i in range(0, len(titles), 50):
    chunk = titles[i:i + 50]
    r = requests.get(API, params={
        "action": "query", "format": "json", "redirects": 1,
        "prop": "revisions", "rvprop": "ids|timestamp",
        "titles": "|".join(chunk)}, headers=HDR, timeout=60)
    q = r.json().get("query", {})
    # redirect-normalized titles map back to requested ones
    remap = {}
    for kind in ("normalized", "redirects"):
        for m in q.get(kind, []):
            remap[m["to"]] = remap.get(m["from"], m["from"])
    for pg in q.get("pages", {}).values():
        t = pg.get("title", "")
        orig = remap.get(t, t)
        p = files.get(orig) or files.get(t)
        if p is None or "revisions" not in pg:
            continue
        d = json.loads(p.read_text())
        d["revid"] = pg["revisions"][0]["revid"]
        d["rev_timestamp"] = pg["revisions"][0]["timestamp"]
        d["revid_backfilled"] = True
        p.write_text(json.dumps(d))
        done += 1
    print(f"[backfill] {done}", flush=True)
    time.sleep(1.0)
n_have = sum(1 for p in OUT.glob("*.json")
             if json.loads(p.read_text()).get("revid"))
print(f"[done] {n_have}/{len(list(OUT.glob('*.json')))} pages have revids",
      flush=True)
