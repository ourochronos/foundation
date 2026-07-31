"""Extract attributed claims into a CLOSED vocabulary, so they can disagree.

exp69 measured why three corpora in one store shared zero triples: their
predicate vocabularies did not intersect at all, so corroboration and conflict
were impossible by construction rather than rare. Free-form extraction would
reproduce that failure by hand — every page inventing its own relations — so
the model is given a fixed predicate list and told to refuse rather than
improvise.

That refusal option matters as much as the list. An extractor with no way to
say "none of these fit" will force a bad predicate onto every sentence, and the
resulting store looks well-populated while being quietly wrong.

**What this sets up.** Each claim carries its school or position as an
`under_assumption` qualifier, which is what makes the same proposition
assertable in opposite directions without contradiction:

    (free_will, compatible_with, determinism, +, {under_assumption: compatibilism})
    (free_will, compatible_with, determinism, −, {under_assumption: hard_determinism})

Scoped, those correctly do NOT conflict — both hold within their frame. Strip
the qualifiers and they must conflict. **That difference is the measurement**,
and it is the first time the conflict machinery has had genuine opposition to
work on rather than extraction artifacts.

Usage: .venv/bin/python scripts/exp71_extract_positions.py [n_sentences]
"""
from __future__ import annotations

import collections
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 400
BATCH = 8
OUT = ROOT / "results" / "exp71_claims.jsonl"

# CLOSED predicate vocabulary. Deliberately small and relational: each one takes
# two concepts and can be asserted or denied, which is what lets two positions
# collide on one proposition instead of talking past each other.
PREDICATES = {
    "compatible_with": "A and B can both be true / coexist",
    "reduces_to": "A is nothing over and above B",
    "identical_to": "A just is B",
    "requires": "A cannot hold without B",
    "entails": "if A then B",
    "causes": "A brings about B",
    "explains": "A accounts for B",
    "refutes": "A shows B is false",
    "exists": "A is real (object is the mode/domain, e.g. 'mind-independently')",
    "is_kind_of": "A is a species of B",
}
POS_RX = re.compile(
    r"\b(compatibilis\w*|hard determinis\w*|determinis\w*|physicalis\w*|dualis\w*|"
    r"functionalis\w*|eliminativis\w*|panpsychis\w*|deontolog\w*|consequentialis\w*|"
    r"utilitarian\w*|virtue ethic\w*|moral realis\w*|relativis\w*|error theor\w*|"
    r"emotivis\w*|foundationalis\w*|coherentis\w*|reliabilis\w*|internalis\w*|"
    r"externalis\w*|skeptic\w*|nominalis\w*|platonis\w*|conceptualis\w*|empiricis\w*|"
    r"rationalis\w*|positivis\w*|instrumentalis\w*|constructionis\w*|realis\w*|"
    r"keynesian\w*|austrian\w*|monetaris\w*|marxian|marxis\w*|neoclassical|"
    r"chicago school|post-keynesian|supply-side|mmt|modern monetary|"
    r"behavioral econom\w*|new classical|georgis\w*|heterodox|institutional econom\w*)\b",
    re.I)
ATTR = re.compile(r"\b(argue|argues|argued|contend|contends|hold|holds|claim|claims|"
                  r"believe|believes|maintain|maintains|assert|asserts|according to|"
                  r"reject|rejects|deny|denies|object|objects|criticiz\w*|dispute|"
                  r"disagree|insist|posit|posits|defend|defends)\w*\b", re.I)

def position_vocabulary():
    """The CLOSED set of assumption labels — taken from the corpus's own
    position pages, which is what makes them canonical.

    The first run let the model name positions freely and it produced "kant",
    "david hume", "proponents of llm functional" and "traditional duality".
    That is exp69's disjoint-vocabulary failure one level deeper: if
    `under_assumption` values are free-form, two claims from the same school
    never scope-match, so scoped non-conflict and agreement both break exactly
    as cross-corpus corroboration did. A philosopher is also not a position —
    Kant is a person who held views, and using him as a frame label conflates
    who said it with under what assumptions it holds.
    """
    out = {}
    for dom in ("phil", "econ"):
        for f in sorted((ROOT / "data" / dom / "pages").glob("*.json")):
            page = json.loads(f.read_text())
            if page.get("kind") in ("position", "school"):
                name = re.sub(r"\s*\(.*?\)", "", page["title"]).strip()
                out[name.lower()] = name
    return out


POSITIONS = position_vocabulary()

PROMPT = """You extract structured claims from philosophy and economics text.

Use ONLY these predicates:
{preds}

Use ONLY these positions (the school/stance a claim is attributed to):
{positions}

For each numbered sentence output one JSON object on its own line:
{{"n": <number>, "position": "<the school/position the claim is ATTRIBUTED to>",
 "subject": "<concept>", "predicate": "<from the list>", "object": "<concept>",
 "polarity": "+" or "-"}}

Rules:
- position MUST be copied exactly from the list above. A named philosopher or
  economist is NOT a position - if a sentence attributes a view to a person
  rather than to a listed school, skip it.
- Output AT MOST ONE object per sentence. Never repeat a sentence's number.
- polarity "-" if the position DENIES the relation.
- If no predicate in the list fits, or the sentence attributes nothing, output
  {{"n": <number>, "skip": true}}. Do NOT invent a predicate. Skipping is
  correct and expected for many sentences.
- Output ONLY the JSON lines, nothing else.

Sentences:
{body}
"""


def sentences():
    out = []
    for dom in ("phil", "econ"):
        d = ROOT / "data" / dom / "pages"
        for p in sorted(d.glob("*.json")):
            page = json.loads(p.read_text())
            for s in re.split(r"(?<=[.!?])\s+", page["text"]):
                s = " ".join(s.split())
                if 40 < len(s) < 320 and POS_RX.search(s) and ATTR.search(s):
                    out.append({"domain": dom, "page": page["title"], "text": s})
    return out


def gemma(prompt: str) -> str:
    # -n caps generation: at temp 0.1 the model otherwise loops, and the first
    # run emitted 17 near-identical claims for one sentence before stopping.
    # stdout only: this build writes load logs and warnings to stderr, and
    # Gemma 4 wraps replies in <|channel>thought ... <channel|> markers that the
    # JSON scan steps over. Budget covers the thinking tokens too, which the
    # first run did not and which is why most sentences returned nothing.
    r = subprocess.run([str(ROOT / "gemma.sh"), "-n", str(160 * BATCH),
                        "-p", prompt],
                       capture_output=True, text=True, timeout=1800)
    return r.stdout


sents = sentences()
print(f"{len(sents)} candidate sentences, {len(POSITIONS)} closed positions; "
      f"extracting {min(N, len(sents))}", flush=True)
sents = sents[:N]

kept, skipped, bad = [], 0, 0
OUT.write_text("")
for i in range(0, len(sents), BATCH):
    chunk = sents[i:i + BATCH]
    body = "\n".join(f"{j + 1}. {c['text']}" for j, c in enumerate(chunk))
    preds = "\n".join(f"  {k}: {v}" for k, v in PREDICATES.items())
    poss = "\n".join(f"  {v}" for v in sorted(POSITIONS.values()))
    txt = gemma(PROMPT.format(preds=preds, positions=poss, body=body))
    seen_n = set()
    for m in re.finditer(r"\{[^{}]*\"n\"\s*:\s*\d+[^{}]*\}", txt):
        try:
            d = json.loads(m.group(0))
        except Exception:                                        # noqa: BLE001
            bad += 1
            continue
        k = d.get("n", 0) - 1
        if not (0 <= k < len(chunk)):
            bad += 1
            continue
        if k in seen_n:                    # one claim per sentence, first wins
            continue
        if d.get("skip") or d.get("predicate") not in PREDICATES:
            seen_n.add(k)
            skipped += 1
            continue
        pos = str(d.get("position", "")).strip().lower()
        pos = re.sub(r"\s*\(.*?\)", "", pos)
        if pos not in POSITIONS:            # closed vocabulary, no improvising
            seen_n.add(k)
            skipped += 1
            continue
        d["position"] = POSITIONS[pos]
        seen_n.add(k)
        rec = {**chunk[k], **{x: d.get(x) for x in
                              ("position", "subject", "predicate", "object",
                               "polarity")}}
        kept.append(rec)
        with OUT.open("a") as f:
            f.write(json.dumps(rec) + "\n")
    print(f"  {i + len(chunk):>4}/{len(sents)}  kept={len(kept)} "
          f"skipped={skipped} unparsed={bad}", flush=True)

print(f"\nextracted {len(kept)} claims, skipped {skipped}, unparsed {bad}")
byp = collections.Counter(k["predicate"] for k in kept)
bypos = collections.Counter(str(k["position"]).lower()[:28] for k in kept)
print(f"predicates: {dict(byp.most_common())}")
print(f"positions:  {dict(bypos.most_common(12))}")
print(f"\n[done] {OUT}")
