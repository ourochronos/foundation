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
MODEL = sys.argv[2] if len(sys.argv) > 2 else "gpt-5.4"


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


def run(name: str, items: list[dict], prompt: str, allowed: set[str],
        mine: dict[int, str]):
    raw = copilot(prompt)
    got = parse_verdicts(raw, allowed)
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


if sys.argv[1] == "arxiv50":
    items = json.loads((ROOT / "data/arxiv/audit_sample_50.json").read_text())
    abstracts = {}
    for pp in (ROOT / "data/arxiv/papers").glob("*.json"):
        d = json.loads(pp.read_text())
        abstracts["arxiv:" + d["arxiv_id"]] = d["abstract"]
    labels = json.loads(
        (ROOT / "data/arxiv/audit_labels_50.json").read_text())
    mine = {i: ("DEFECT" if i in labels["defect_idx"] else "PRECISE")
            for i in range(50)}
    blocks = []
    for i, s in enumerate(items):
        blocks.append(f"### ITEM {i}\nCLAIM: {s['statement']}\n"
                      f"ABSTRACT: {abstracts.get(s['page'], '?')[:1400]}")
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
    run("arxiv50", items, prompt, {"PRECISE", "DEFECT"}, mine)

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
