"""KB answer-surface semantics on the memory backend (no PG, no GPU)."""
import json

import pytest

from foundation.kb import KB

SHARD = [
    {"page": "Alice Blue", "subject": "Alice Blue", "pid": "P569",
     "object": "1901", "statement": "Alice Blue was born in 1901."},
    {"page": "Alice Blue", "subject": "Alice Blue", "pid": "P69",
     "object": "Utopia College",
     "statement": "Alice Blue studied at Utopia College."},
    {"page": "Utopia College", "subject": "Utopia College", "pid": "P571",
     "object": "1850",
     "statement": "Utopia College was founded in 1850."},
    {"page": "Bob Crimson", "subject": "Bob Crimson", "pid": "P569",
     "object": "1899", "statement": "Bob Crimson was born in 1899."},
    # second source disagrees on Bob's (functional) birth year
    {"page": "History of Crimsons", "subject": "Bob Crimson",
     "pid": "P569", "object": "1897",
     "statement": "Bob Crimson, born 1897, was a Crimson."},
]


@pytest.fixture()
def kb(tmp_path):
    d = tmp_path / "shards"
    d.mkdir()
    (d / "out_0.jsonl").write_text(
        "\n".join(json.dumps(r) for r in SHARD) + "\n")
    kb = KB(backend="memory")
    r = kb.ingest_shards(d, embed=False)
    assert r["ingested"] == len(SHARD)
    return kb


def test_ask_answered_with_citations(kb):
    r = kb.ask("Alice Blue", "P569")
    assert r["status"] == "answered"
    assert r["answers"][0]["object"] == "1901"
    assert r["answers"][0]["citations"] == ["out_0.jsonl:0"]


def test_ask_abstains_on_unknown_and_missing(kb):
    assert kb.ask("Carol Green", "P569")["status"] == "abstain"
    assert kb.ask("Alice Blue", "P20")["status"] == "abstain"


def test_functional_conflict_surfaces(kb):
    r = kb.ask("Bob Crimson", "P569")
    assert r["status"] == "conflict"
    objs = {a["object"] for a in r["answers"]}
    assert objs == {"1899", "1897"}


def test_chain_hand_off(kb):
    r = kb.chain("Alice Blue", ["P69", "P571"])
    assert r["status"] == "answered"
    assert r["answers"][0]["object"] == "1850"


def test_edit_supersedes_and_ripples(kb):
    r = kb.edit("Alice Blue", "P569", "1902", source="test:fix")
    assert r["status"] == "edited" and len(r["superseded"]) == 1
    after = kb.ask("Alice Blue", "P569")
    assert after["status"] == "answered"
    assert after["answers"][0]["object"] == "1902"
    # chain still works after the edit (ripple sanity)
    assert kb.chain("Alice Blue", ["P69", "P571"])["status"] == "answered"


def test_views_by_source(kb):
    v = kb.views("Bob Crimson")
    assert v["status"] == "answered"
    assert set(v["views"]) == {"Bob Crimson", "History of Crimsons"}


def test_brief_grounded(kb):
    b = kb.brief("Alice Blue")
    assert not b["abstain"]
    texts = " ".join(s["text"] for s in b["sentences"])
    assert "1901" in texts
    assert all(s["citations"] for s in b["sentences"])


def test_brief_refuses_unknown(kb):
    assert kb.brief("Carol Green")["abstain"]


# --- D92: a page's canonical form is its TITLE, not its identifier -------
# Wikipedia pages ARE their title, so page==subject canonicalizes them.
# arXiv pages are IDs, which silently defeated that rule: every citing
# paper minted its own eid for the same cited work and evidence counts
# read zero. page_title fixes the citing side, object_page the cited one.

CITES = [
    {"page": "arxiv:2000.001", "page_title": "Paper One",
     "subject": "Paper One", "pid": "P_CITES", "object": "Cited Work",
     "object_page": "arxiv:1999.001",
     "statement": "Paper One cites Cited Work."},
    {"page": "arxiv:2000.002", "page_title": "Paper Two",
     "subject": "Paper Two", "pid": "P_CITES", "object": "Cited Work",
     "object_page": "arxiv:1999.001",
     "statement": "Paper Two cites Cited Work."},
    {"page": "arxiv:2000.003", "page_title": "Paper Three",
     "subject": "Paper Three", "pid": "P_CITES", "object": "Cited Work",
     "object_page": "arxiv:1999.001",
     "statement": "Paper Three cites Cited Work."},
]


@pytest.fixture()
def cite_kb(tmp_path):
    d = tmp_path / "cites"
    d.mkdir()
    (d / "out_0.jsonl").write_text(
        "\n".join(json.dumps(r) for r in CITES) + "\n")
    kb = KB(backend="memory")
    kb.ingest_shards(d, embed=False)
    return kb


def test_cited_work_is_one_entity(cite_kb):
    # the cited work has no rows of its own — it only ever appears as an
    # object — and must still be a single entity
    assert len(cite_kb.resolve_subject("Cited Work")) == 1


def test_cited_by_counts_every_citing_page(cite_kb):
    r = cite_kb.cited_by("Cited Work")
    assert r["status"] == "answered" and r["n"] == 3
    assert r["sources"] == ["arxiv:2000.001", "arxiv:2000.002",
                            "arxiv:2000.003"]


def test_views_abstains_when_nothing_is_said_about_an_entity(cite_kb):
    # known entity, but every claim points AT it — "answered" with an
    # empty body would be the dishonest status
    assert cite_kb.views("Cited Work")["status"] == "abstain"
    assert cite_kb.views("Paper One")["status"] == "answered"
