"""P_CITES claims from RETAINED source HTML (docs/13 citation axis).

No fetching: the bibliography is already in data/*/papers_html/*.html.gz,
which exists precisely so extraction can be re-derived (source-retention
policy). No LLM either — citation edges are a mechanical pattern, so this
is a deterministic extractor with a measurable error mode, not a fleet.

Claim shape (docs/13): page = the CITING paper (it is the source that
asserts the citation), subject = citing paper's short title, object =
the cited work's title when it is in-corpus, else "arXiv:<id>". Using
the in-corpus TITLE is what gives the AI slice cross-paper entity
structure: every paper citing the same work resolves to one eid, so
`cited_by` counts become an evidence signal.

Usage: .venv/bin/python scripts/cite_extract.py data/arxiv_ai
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLICE = Path(sys.argv[1] if len(sys.argv) > 1 else "data/arxiv_ai")
HTML = ROOT / SLICE / "papers_html"
PAPERS = ROOT / SLICE / "papers"
OUT = ROOT / SLICE / "shards_cites"
OUT.mkdir(exist_ok=True)

# arXiv ids as they appear in bibliographies: "arXiv:2501.12948",
# "arXiv preprint arXiv:1706.03762v5", bare abs/ URLs.
ID_RE = re.compile(r"(?:arxiv[:\s]*(?:preprint\s+arxiv:)?|abs/)"
                   r"(\d{4}\.\d{4,5})(v\d+)?", re.I)


def base(aid: str) -> str:
    return aid.split("v")[0]


in_corpus: dict[str, dict] = {}
for p in sorted(PAPERS.glob("*.json")):
    d = json.loads(p.read_text())
    in_corpus[base(d["arxiv_id"])] = d

rows, n_html, edges, self_cites = [], 0, 0, 0
for h in sorted(HTML.glob("*.html.gz")):
    aid = h.name[: -len(".html.gz")]
    citing = in_corpus.get(base(aid))
    if citing is None:
        continue
    n_html += 1
    html = gzip.decompress(h.read_bytes()).decode("utf8", "replace")
    # bibliography only: everything after the last references heading —
    # body-text arXiv mentions are not citations of record
    m = None
    for m in re.finditer(r"(?i)>\s*(references|bibliography)\s*<", html):
        pass
    tail = html[m.start():] if m else html
    seen: set[str] = set()
    for mm in ID_RE.finditer(tail):
        cid = base(mm.group(1))
        if cid in seen:
            continue
        seen.add(cid)
        if cid == base(aid):
            self_cites += 1
            continue
        edges += 1
        cited = in_corpus.get(cid)
        obj = cited["title"] if cited else f"arXiv:{cid}"
        rows.append({
            "page": f"arxiv:{citing['arxiv_id']}",
            "page_title": citing["title"],
            "subject": citing["title"],
            "pid": "P_CITES",
            "kind": "citation",
            "object": obj[:200],
            "statement": (f"{citing['title']} (arXiv:{citing['arxiv_id']}) "
                          f"cites {obj} (arXiv:{cid})."),
            "in_corpus": cited is not None})

S = max(1, (len(rows) + 999) // 1000)
for i in range(S):
    (OUT / f"out_{i}.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows[i * 1000:(i + 1) * 1000]))

n_ic = sum(1 for r in rows if r["in_corpus"])
cited_by: dict[str, set] = {}
for r in rows:
    if r["in_corpus"]:
        cited_by.setdefault(r["object"], set()).add(r["page"])
top = sorted(((len(v), k) for k, v in cited_by.items()), reverse=True)[:10]
summary = {"papers_read": n_html, "edges": edges, "self_cites_dropped":
           self_cites, "claims": len(rows), "in_corpus_edges": n_ic,
           "distinct_in_corpus_cited": len(cited_by),
           "top_cited_in_corpus": [{"title": k, "citing_papers": n}
                                   for n, k in top], "shards": S}
(ROOT / SLICE / "cite_summary.json").write_text(json.dumps(summary, indent=1))
print(json.dumps(summary, indent=1)[:1400])
