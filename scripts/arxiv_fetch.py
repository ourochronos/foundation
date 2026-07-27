"""ArXiv slice fetcher (Phase B, docs/10): math.LO abstracts-first.

Pulls ~N recent math.LO abstracts via the arXiv export API (Atom; polite
3s between calls), writes data/arxiv/papers/*.json and stages extraction
shards data/arxiv/shards/in_*.json for the Haiku claim-extraction fleet.

Claims model (D69 statement-first, adapted to papers): each claim is a
self-contained ATTRIBUTED statement ("<paper> asserts/proves/defines …")
with provenance = arxiv id; acceptance for the slice is extraction
precision >= 0.6 on a 50-claim frozen audit (10-poc-plan), not the full
gate battery.

Usage: ARXIV_N=120 .venv/bin/python scripts/arxiv_fetch.py
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
import os as _os
SLICE = _os.environ.get("ARXIV_SLICE", "")
OUT = ROOT / "data" / ("arxiv" + SLICE) / "papers"
SHARDS = ROOT / "data" / ("arxiv" + SLICE) / "shards"
OUT.mkdir(parents=True, exist_ok=True)
SHARDS.mkdir(parents=True, exist_ok=True)
API = "http://export.arxiv.org/api/query"
HDR = {"User-Agent": "foundation-research/0.1 (zonk1024@gmail.com)"}
N = int(os.environ.get("ARXIV_N", "120"))

got = 0
for start in range(0, N, 100):
    r = requests.get(API, params={
        "search_query": os.environ.get("ARXIV_QUERY", "cat:math.LO"), "start": start,
        "max_results": min(100, N - start),
        "sortBy": "submittedDate", "sortOrder": "descending"},
        headers=HDR, timeout=60)
    entries = re.findall(r"<entry>(.*?)</entry>", r.text, re.S)
    for e in entries:
        def tag(t, e=e):
            m = re.search(rf"<{t}[^>]*>(.*?)</{t}>", e, re.S)
            return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
        aid = tag("id").rsplit("/", 1)[-1]
        if not aid:
            continue
        (OUT / f"{aid.replace('.', '_').replace('/', '_')}.json").write_text(
            json.dumps({"arxiv_id": aid, "title": tag("title"),
                        "abstract": tag("summary"),
                        "authors": re.findall(r"<name>(.*?)</name>", e),
                        "published": tag("published")}))
        got += 1
    print(f"[arxiv] {got} papers", flush=True)
    if start + 100 < N:
        time.sleep(3)

papers = [json.loads(p.read_text()) for p in sorted(OUT.glob("*.json"))]
S = max(1, (len(papers) + 19) // 20)          # ~20 abstracts per shard
for i in range(S):
    (SHARDS / f"in_{i}.json").write_text(json.dumps(
        papers[i * 20:(i + 1) * 20], indent=1))
print(f"[done] {len(papers)} papers -> {S} shards of ~20", flush=True)

# ---- source retention: full-text backfill (ARXIV_FULLTEXT=1) ---------------
# data/*/papers* is the IMMUTABLE SOURCE LAYER (docs/13): keep the raw HTML
# (gzipped) + a plain-text extract so extraction is always re-derivable.
if os.environ.get("ARXIV_FULLTEXT") == "1":
    import gzip
    H = OUT.parent / "papers_html"
    H.mkdir(exist_ok=True)
    todo = []
    for p in sorted(OUT.glob("*.json")):
        d = json.loads(p.read_text())
        if not d.get("fulltext"):
            todo.append((p, d))
    print(f"[fulltext] {len(todo)} papers to backfill", flush=True)
    n_ok = 0
    for p, d in todo:
        aid = d["arxiv_id"]
        try:
            r = requests.get(f"https://arxiv.org/html/{aid}",
                             headers=HDR, timeout=60)
            if r.status_code != 200:
                r = requests.get(f"https://arxiv.org/abs/{aid}",
                                 headers=HDR, timeout=60)
            html = r.text
            (H / f"{aid.replace('/', '_')}.html.gz").write_bytes(
                gzip.compress(html.encode()))
            txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html,
                         flags=re.S | re.I)
            txt = re.sub(r"<[^>]+>", " ", txt)
            txt = re.sub(r"\s+", " ", txt).strip()
            d["fulltext"] = txt[:40000]
            d["fulltext_source"] = str(r.url)
            p.write_text(json.dumps(d))
            n_ok += 1
        except Exception as e:
            print(f"[fulltext] ! {aid}: {e}", flush=True)
        time.sleep(1.0)
        if n_ok % 50 == 0 and n_ok:
            print(f"[fulltext] {n_ok}", flush=True)
    print(f"[fulltext] done: {n_ok}/{len(todo)}", flush=True)
