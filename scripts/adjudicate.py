"""Independent adjudication via GitHub Copilot CLI (D86).

Second-rater loop for frozen audits: the ENTIRE audit goes in ONE
`copilot -p` call (1 premium request per audit), BLIND — the adjudicator
never sees our labels. Output: per-index verdicts + reasons, raw
agreement, Cohen's kappa, disagreement table. No verdict changes here —
both raters go in the log; decisions stay with the user.

Usage:
  .venv/bin/python scripts/adjudicate.py arxiv50 [model]
  .venv/bin/python scripts/adjudicate.py g2fp25 [model]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "adjudication"
OUT.mkdir(exist_ok=True)
MODEL = sys.argv[2] if len(sys.argv) > 2 else "gpt-5.6-sol"


def copilot(prompt: str) -> str:
    r = subprocess.run(
        ["copilot", "-p", prompt, "--no-ask-user", "--model", MODEL,
         "--no-auto-update"],
        capture_output=True, text=True, timeout=900, cwd=str(ROOT))
    return r.stdout + "\n" + r.stderr


def parse_verdicts(text: str, allowed: set[str]) -> dict[int, dict]:
    out = {}
    for m in re.finditer(r'\{[^{}]*"idx"[^{}]*\}', text, re.S):
        try:
            d = json.loads(m.group(0))
        except Exception:
            continue
        v = str(d.get("verdict", "")).strip().upper()
        if v in allowed and "idx" in d:
            out[int(d["idx"])] = {"verdict": v,
                                  "reason": str(d.get("reason", ""))[:200]}
    return out


def kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


ARGV_BUDGET = 110_000        # one `copilot -p` prompt; ARG_MAX bites near 1MB


def run(name: str, items: list[dict], prompt: str, allowed: set[str],
        mine: dict[int, str], blocks: list[str] | None = None,
        header: str = ""):
    """One `copilot -p` call when the prompt fits, else batched.

    Sources with large evidence (HF cards run to 60k chars) blow past
    ARG_MAX as one prompt. Shrinking the evidence is the WRONG fix —
    truncation manufactured 6 of 8 disagreements on arxiv50 (D92) — so
    batch instead and keep every item's evidence whole. Indices stay
    global across batches, so the merged verdict map is identical to
    what a single call would have produced.
    """
    if blocks is not None and len(prompt) > ARGV_BUDGET:
        got, batch, size, n_calls = {}, [], 0, 0
        batches = []
        for b in blocks:
            if batch and size + len(b) > ARGV_BUDGET - len(header):
                batches.append(batch)
                batch, size = [], 0
            batch.append(b)
            size += len(b)
        if batch:
            batches.append(batch)
        print(f"[adjudicate] prompt {len(prompt)} chars > budget — "
              f"{len(batches)} batches, evidence kept whole")
        for bt in batches:
            n_calls += 1
            got.update(parse_verdicts(copilot(header + "\n\n".join(bt)),
                                      allowed))
        print(f"[adjudicate] {n_calls} calls, {len(got)} verdicts parsed")
    else:
        got = parse_verdicts(copilot(prompt), allowed)
    missing = [i for i in range(len(items)) if i not in got]
    if missing:
        print(f"[adjudicate] WARNING missing verdicts for idx {missing}")
    both = [i for i in range(len(items)) if i in got and i in mine]
    a = [mine[i] for i in both]
    b = [got[i]["verdict"] for i in both]
    agree = sum(x == y for x, y in zip(a, b)) / max(len(both), 1)
    k = kappa(a, b) if both else 0.0
    disagreements = [
        {"idx": i, "mine": mine[i], "theirs": got[i]["verdict"],
         "their_reason": got[i]["reason"]}
        for i in both if mine[i] != got[i]["verdict"]]
    art = {"audit": name, "model": MODEL, "n": len(items),
           "n_judged": len(both), "raw_agreement": agree,
           "cohens_kappa": k, "disagreements": disagreements,
           "their_verdicts": {str(i): got[i] for i in sorted(got)},
           "my_labels": {str(i): mine[i] for i in sorted(mine)}}
    p = OUT / f"{name}_{MODEL.replace('.', '_').replace('/', '_')}.json"
    p.write_text(json.dumps(art, indent=1))
    print(f"[adjudicate] {name} model={MODEL}: agreement={agree:.3f} "
          f"kappa={k:.3f} disagreements={len(disagreements)}")
    for d in disagreements:
        print(f"  idx {d['idx']}: mine={d['mine']} theirs={d['theirs']} "
              f"— {d['their_reason'][:110]}")
    print(f"[done] {p.relative_to(ROOT)}")



def _body(p: dict) -> str:
    """Full cleaned fulltext for audit evidence, not the extraction window.

    D103: `body_window` is ~8k, sized to fit an extraction prompt; the
    retained source runs to 40k. Auditing on the window capped what both
    raters could know and produced three disagreements that the full text
    settled — one in Sol's favour, one in mine, one still open. Evidence
    for a verdict must not be narrower than evidence for the claim.
    """
    import json as _j
    from pathlib import Path as _P
    try:
        from foundation.fulltext import clean
        f = ROOT / "data/arxiv_ai/papers" / (
            p.get("arxiv_id", "").replace(".", "_").replace("/", "_") + ".json")
        if f.exists():
            full = clean(_j.loads(f.read_text()).get("fulltext") or "",
                         max_chars=10 ** 9)
            if full:
                return full
    except Exception:
        pass
    return p.get("body_window", "")


def _abstract_audit(name: str, slice_dir: str):
    """Shared arXiv claim-audit adjudication: FULL abstracts (D86
    truncation lesson — a clipped abstract manufactures NOT-ASSERTED
    defects), labels frozen before the run, blind to the adjudicator."""
    items = json.loads(
        (ROOT / f"data/{slice_dir}/audit_sample_50.json").read_text())
    abstracts = {}
    for pp in (ROOT / f"data/{slice_dir}/papers").glob("*.json"):
        d = json.loads(pp.read_text())
        abstracts["arxiv:" + d["arxiv_id"]] = d["abstract"]
    labels = json.loads(
        (ROOT / f"data/{slice_dir}/audit_labels_50.json").read_text())
    mine = {i: ("DEFECT" if i in labels["defect_idx"] else "PRECISE")
            for i in range(50)}
    blocks = []
    for i, s in enumerate(items):
        blocks.append(f"### ITEM {i}\nCLAIM: {s['statement']}\n"
                      f"ABSTRACT: {abstracts.get(s['page'], '?')}")
    prompt = (
        "You are an independent audit adjudicator. For each item below, "
        "judge whether the CLAIM is a faithful, self-contained extraction "
        "from the ABSTRACT. Strict rules: the claim must be asserted by "
        "the abstract (not inferred); attribution strength must match "
        "(claiming 'proves' unconditionally where the abstract conditions "
        "or merely studies = defect); dropped qualifiers that change the "
        "claim = defect; glosses not supported by the abstract's words = "
        "defect. Verdict PRECISE or DEFECT.\n"
        "Do not use any tools. Output ONLY a JSON array of 50 objects, "
        'one per item, format {"idx": <n>, "verdict": "PRECISE"|"DEFECT", '
        '"reason": "<short>"} — nothing else.\n\n' + "\n\n".join(blocks))
    run(name, items, prompt, {"PRECISE", "DEFECT"}, mine)


if sys.argv[1] == "arxiv50":
    _abstract_audit("arxiv50", "arxiv")

elif sys.argv[1] == "arxivai50":
    _abstract_audit("arxivai50", "arxiv_ai")

elif sys.argv[1] in ("resv2_50", "resv3_50"):
    _V = "v2" if sys.argv[1] == "resv2_50" else "v3"
    items = json.loads(
        (ROOT / f"data/arxiv_ai/res_{_V}_audit_sample_50.json").read_text())
    win = {}
    for f in sorted((ROOT / "data/arxiv_ai/shards_res").glob("in_*.json")):
        for p in json.loads(f.read_text()):
            win["arxiv:" + p["arxiv_id"]] = p
    labels = json.loads(
        (ROOT / f"data/arxiv_ai/res_{_V}_audit_labels_50.json").read_text())
    mine = {i: ("DEFECT" if i in labels["defect_idx"] else "PRECISE")
            for i in range(50)}
    blocks = []
    for i, s_ in enumerate(items):
        p = win.get(s_["page"], {})
        blocks.append(
            f"### ITEM {i}\nCLAIM: {s_['statement']}\n"
            f"  subject={s_['subject']!r} relation={s_['pid']} "
            f"object={s_['object']!r}\nTITLE: {p.get('title','?')}\n"
            f"ABSTRACT: {p.get('abstract','')}\n"
            f"PAPER BODY:\n{_body(p)}")
    header = (
        "You are an independent audit adjudicator. Each item is a SHARED "
        "RESOURCE claim: the paper's own entity (subject), a relation, and "
        "a resource the paper did not invent (object). Relations: "
        "P_EVALUATES_ON = evaluates/tests/trains on this dataset or "
        "benchmark; P_BUILDS_ON = builds on, fine-tunes, adopts or is "
        "implemented on this base model or prior method; P_COMPARES_TO = "
        "measures itself against this as a baseline (or, when the paper IS "
        "a benchmark, a model it scores).\n"
        "DEFECT if: the ABSTRACT or PAPER BODY does not support it (never "
        "credit your own knowledge of the real system); the RELATION is "
        "wrong for what the text says; the OBJECT is a generic term "
        "(transformer, LSTM, VAE, GAN, SFT, neural network) rather than a "
        "named artifact; or the SUBJECT is a title fragment or stopword. "
        "Otherwise PRECISE.\n"
        "THREE MORE DECLARED CONVENTIONS (D102 — apply, do not re-litigate). "
        "(a) P_EVALUATES_ON covers a corpus the paper TRAINS or fine-tunes "
        "on, not only a held-out test set — training data is not a defect. "
        "(b) When the paper IS a benchmark, models it scores are "
        "P_COMPARES_TO. (c) A subject may be a short DESCRIPTIVE noun "
        "phrase when the paper names no method — a descriptive subject is "
        "not by itself a defect, only a title fragment or stopword is.\n"
        "RESOURCE-NAME GRANULARITY (declared corpus policy, D100 — apply "
        "it, do not re-litigate it): resources are recorded at FAMILY "
        "level. Qwen3 for Qwen3-30B-A3B, AIME for AIME 2024, Claude for "
        "Claude-Sonnet-4.5, CBraMod for CBraMod-small are all CORRECT and "
        "must NOT be marked defective — family-level names are what create "
        "cross-paper linkage, which is the entire purpose of this axis. A "
        "dropped suffix is a DEFECT only when it denotes a genuinely "
        "different artifact (bge-m3-retromae is not BGE-M3; "
        "HarmBench-Response is a distinct subset of HarmBench) or when the "
        "paper's own point is about that specific size or version.\n"
        "Do not use any tools. Output ONLY a JSON array, one object per "
        'ITEM, format {"idx": <n>, "verdict": "PRECISE"|"DEFECT", '
        '"reason": "<short>"} — nothing else. Use each item\'s OWN idx.\n\n')
    run(sys.argv[1], items, header + "\n\n".join(blocks),
        {"PRECISE", "DEFECT"}, mine, blocks=blocks, header=header)

elif sys.argv[1] == "res50":
    items = json.loads(
        (ROOT / "data/arxiv_ai/res_audit_sample_50.json").read_text())
    win = {}
    for f in sorted((ROOT / "data/arxiv_ai/shards_res").glob("in_*.json")):
        for p in json.loads(f.read_text()):
            win["arxiv:" + p["arxiv_id"]] = p
    labels = json.loads(
        (ROOT / "data/arxiv_ai/res_audit_labels_50.json").read_text())
    mine = {i: ("DEFECT" if i in labels["defect_idx"] else "PRECISE")
            for i in range(50)}
    blocks = []
    for i, s in enumerate(items):
        p = win.get(s["page"], {})
        blocks.append(
            f"### ITEM {i}\nCLAIM: {s['statement']}\n"
            f"  subject={s['subject']!r} relation={s['pid']} "
            f"object={s['object']!r}\nTITLE: {p.get('title','?')}\n"
            f"ABSTRACT: {p.get('abstract','')}\n"
            f"PAPER BODY (what the extractor saw):\n{p.get('body_window','')}")
    header = (
        "You are an independent audit adjudicator. Each item is a SHARED "
        "RESOURCE claim extracted from a paper: the paper's own entity "
        "(subject), a relation, and a resource the paper did NOT invent "
        "(object). Relations: P_EVALUATES_ON = evaluates/tests/trains on "
        "this dataset or benchmark; P_BUILDS_ON = builds on, fine-tunes or "
        "extends this base model or prior method; P_COMPARES_TO = compares "
        "against this as a baseline.\n"
        "Verdict DEFECT if: the ABSTRACT or PAPER BODY does not support the "
        "resource (never credit background knowledge of the real model, "
        "even when the claim is true in the world); the RELATION is wrong "
        "(a baseline or an LLM judge recorded as P_BUILDS_ON); the object "
        "is a generic term (transformer, VAE, GAN, neural network) rather "
        "than a named artifact; or the subject is a title fragment or a "
        "stopword. Otherwise PRECISE. Short proper method names are fine.\n"
        "Do not use any tools. Output ONLY a JSON array, one object per "
        'ITEM, format {"idx": <n>, "verdict": "PRECISE"|"DEFECT", '
        '"reason": "<short>"} — nothing else. Use each item\'s OWN idx.\n\n')
    run("res50", items, header + "\n\n".join(blocks),
        {"PRECISE", "DEFECT"}, mine, blocks=blocks, header=header)

elif sys.argv[1] == "hf50":
    items = json.loads((ROOT / "data/hf/audit_sample_50.json").read_text())
    cards = {}
    for pp in (ROOT / "data/hf/cards").glob("*.json"):
        d = json.loads(pp.read_text())
        cards["hf:" + d["id"]] = d
    labels = json.loads((ROOT / "data/hf/audit_labels_50.json").read_text())
    mine = {i: ("DEFECT" if i in labels["defect_idx"] else "PRECISE")
            for i in range(50)}
    blocks = []
    for i, s in enumerate(items):
        c = cards.get(s["page"], {})
        # cards run to 60k chars; the adjudicator gets the metadata fields
        # in full plus a generous card window (truncation manufactured 6
        # of 8 disagreements on arxiv50 — see D92 — so err long)
        md = (c.get("card_md") or "")[:12000]
        blocks.append(
            f"### ITEM {i}\nCLAIM: {s['statement']}\n"
            f"REGISTRY FIELDS: id={c.get('id')!r} license={c.get('license')!r} "
            f"pipeline_tag={c.get('pipeline_tag')!r}\nCARD:\n{md}")
    header = (
        "You are an independent audit adjudicator. Each item is a claim "
        "extracted from a Hugging Face model card. Judge whether the CLAIM "
        "is a faithful, self-contained extraction from the CARD or the "
        "REGISTRY FIELDS. Rules: the claim must be stated by the card or "
        "the registry fields (never inferred from your own knowledge of "
        "the model); a metric claim must carry its benchmark AND metric; "
        "license/pipeline must match the registry fields; the subject must "
        "be the model, not a fragment of a code sample. Cards are "
        "self-reported, so an attributed frame ('the card states/reports/"
        "claims') is correct and NOT a defect. Awkward phrasing is not a "
        "defect. Verdict PRECISE or DEFECT.\n"
        "Do not use any tools. Output ONLY a JSON array, one object per "
        'ITEM below, format {"idx": <n>, "verdict": "PRECISE"|"DEFECT", '
        '"reason": "<short>"} — nothing else. Use each item\'s OWN idx '
        "from its ### ITEM header; they are not necessarily "
        "consecutive from zero.\n\n")
    run("hf50", items, header + "\n\n".join(blocks), {"PRECISE", "DEFECT"},
        mine, blocks=blocks, header=header)

elif sys.argv[1] == "g2fp25":
    items = json.loads(
        (ROOT / "data/wiki/g2_fp_audit_25.json").read_text())
    labels = json.loads(
        (ROOT / "data/wiki/g2_fp_audit_labels.json").read_text())
    mine = {i: ("FALSE" if i in labels["false_idx"] else "TRUE")
            for i in range(25)}
    blocks = []
    for i, s in enumerate(items):
        blocks.append(
            f"### ITEM {i}\nFACT: subject={s['subject']!r} "
            f"property={s['pid']} object={s['object']!r}\n"
            f"STATEMENT: {s.get('statement', '')}")
    prompt = (
        "You are an independent fact adjudicator with strong knowledge of "
        "the history of mathematics and philosophy. Each item is an "
        "extracted biographical fact (Wikidata property semantics: P569 "
        "birth date, P570 death date, P19 birthplace, P20 deathplace, P26 "
        "spouse, P27 citizenship, P69 educated at, P108 employer, P166 "
        "award, P800 known for). Judge from your own world knowledge "
        "whether the FACT is TRUE of the real person (the fact may be "
        "correct even if a typical infobox omits it). Verdict TRUE or "
        "FALSE.\n"
        "Do not use any tools. Output ONLY a JSON array of 25 objects, "
        'format {"idx": <n>, "verdict": "TRUE"|"FALSE", "reason": '
        '"<short>"} — nothing else.\n\n' + "\n\n".join(blocks))
    run("g2fp25", items, prompt, {"TRUE", "FALSE"}, mine)

else:
    raise SystemExit(f"unknown audit {sys.argv[1]!r}")
