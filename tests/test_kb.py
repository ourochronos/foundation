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


# --- D101: shared resources are GLOBAL entities ---------------------------
# A benchmark fifty papers use is one thing with no page of its own. The
# batch-locality resolver keeps same-form mentions apart across documents,
# which is right for people in a closed world and wrong here: GSM8K became
# 16 eids and every cross-paper count read 0.

RESOURCES = [
    {"page": "arxiv:1", "page_title": "Paper One", "subject": "Paper One",
     "pid": "P_EVALUATES_ON", "object": "GSM8K", "object_global": True,
     "statement": "Paper One is evaluated on GSM8K."},
    {"page": "arxiv:2", "page_title": "Paper Two", "subject": "Paper Two",
     "pid": "P_EVALUATES_ON", "object": "GSM8K", "object_global": True,
     "statement": "Paper Two is evaluated on GSM8K."},
    {"page": "arxiv:3", "page_title": "Paper Three", "subject": "Paper Three",
     "pid": "P_BUILDS_ON", "object": "GSM8K", "object_global": True,
     "statement": "Paper Three builds on GSM8K."},
]


@pytest.fixture()
def res_kb(tmp_path):
    d = tmp_path / "res"
    d.mkdir()
    (d / "out_0.jsonl").write_text(
        "\n".join(json.dumps(r) for r in RESOURCES) + "\n")
    kb = KB(backend="memory")
    kb.ingest_shards(d, embed=False)
    return kb


def test_global_resource_is_one_entity(res_kb):
    assert len(res_kb.resolve_subject("GSM8K")) == 1


def test_global_resource_counts_every_using_paper(res_kb):
    r = res_kb.cited_by("GSM8K", pid=None)
    assert r["status"] == "answered" and r["n"] == 3
    assert r["sources"] == ["arxiv:1", "arxiv:2", "arxiv:3"]


def test_global_resource_adopts_an_existing_entity(tmp_path):
    """A resource can arrive first as some paper's own subject.

    Ingest is multi-process and the global canonical is not restored on
    replay, so minting unconditionally gives that resource a second eid —
    which is what happened to GRPO (subject of a paper about it, and a
    resource 16 papers build on).
    """
    kb = KB(backend="memory")
    a = tmp_path / "a"
    a.mkdir()
    (a / "out_0.jsonl").write_text(json.dumps(
        {"page": "arxiv:9", "page_title": "About GRPO", "subject": "GRPO",
         "pid": "P_ASSERTS", "object": "a claim about it",
         "statement": "GRPO is analysed."}) + "\n")
    kb.ingest_shards(a, embed=False)
    b = tmp_path / "b"
    b.mkdir()
    (b / "out_0.jsonl").write_text(json.dumps(
        {"page": "arxiv:10", "page_title": "User", "subject": "User",
         "pid": "P_BUILDS_ON", "object": "GRPO", "object_global": True,
         "statement": "User builds on GRPO."}) + "\n")
    kb.ingest_shards(b, embed=False)
    assert len(kb.resolve_subject("GRPO")) == 1


# --- D105: the parts inventory types the tail the corpus vote cannot -----

def test_type_oracle_matches_at_family_level():
    """The corpus writes `Qwen2.5`; the registry writes `Qwen2.5-7B-Instruct`.

    Exact matching found 13 of 719 resource objects; family matching finds
    38, of which 30 are tail cases (<3 papers) that relational
    participation cannot type at all.
    """
    from foundation.typeoracle import family, is_model
    assert family("Qwen2.5-7B-Instruct") == family("Qwen2.5")
    assert family("meta-llama/Llama-3.1-8B") == family("Llama 3.1")
    # a benchmark must NOT fold into a model family
    assert family("GSM8K") != family("Qwen2.5")
    if is_model("Qwen2.5"):                    # skip if cards absent
        assert not is_model("GSM8K")


def test_type_oracle_evidence_is_traceable():
    from foundation.typeoracle import evidence, is_model
    if is_model("Qwen2.5"):
        assert any("Qwen" in e for e in evidence("Qwen2.5"))


def test_declare_adopts_across_ingests_for_every_declaration(tmp_path):
    """All three declarations must adopt before minting, not just one.

    D107: the page_title path still minted unconditionally, so a paper
    title arriving once via the citation axis and once via a bridge got
    two eids — leaving the citation graph and resource graph as
    disconnected components with zero paths between them, silently.
    """
    kb = KB(backend="memory")
    a = tmp_path / "a"
    a.mkdir()
    (a / "out_0.jsonl").write_text(json.dumps(
        {"page": "arxiv:1", "page_title": "Paper One", "subject": "Citer",
         "pid": "P_CITES", "object": "Paper One", "object_page": "arxiv:1",
         "statement": "Citer cites Paper One."}) + "\n")
    kb.ingest_shards(a, embed=False)
    b = tmp_path / "b"
    b.mkdir()
    (b / "out_0.jsonl").write_text(json.dumps(
        {"page": "arxiv:1", "page_title": "Paper One", "subject": "Paper One",
         "pid": "P_INTRODUCES", "object": "MethodX", "object_global": True,
         "statement": "Paper One introduces MethodX."}) + "\n")
    kb.ingest_shards(b, embed=False)
    assert len(kb.resolve_subject("Paper One")) == 1


def test_cross_axis_chain_reaches_the_far_side(tmp_path):
    """The bridge makes citation -> method -> resource a real query."""
    kb = KB(backend="memory")
    d = tmp_path / "x"
    d.mkdir()
    (d / "out_0.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"page": "arxiv:2", "page_title": "Citing", "subject": "Citing",
         "pid": "P_CITES", "object": "Paper One", "object_page": "arxiv:1",
         "statement": "Citing cites Paper One."},
        {"page": "arxiv:1", "page_title": "Paper One", "subject": "Paper One",
         "pid": "P_INTRODUCES", "object": "MethodX", "object_global": True,
         "statement": "Paper One introduces MethodX."},
        {"page": "arxiv:1", "page_title": "Paper One", "subject": "MethodX",
         "pid": "P_EVALUATES_ON", "object": "GSM8K", "object_global": True,
         "statement": "MethodX is evaluated on GSM8K."},
    ]) + "\n")
    kb.ingest_shards(d, embed=False)
    r = kb.chain("Citing", ["P_CITES", "P_INTRODUCES", "P_EVALUATES_ON"])
    assert r["status"] == "answered"
    assert "GSM8K" in {a["object"] for a in r["answers"]}
