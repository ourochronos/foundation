"""How much of the store would REBEL's negation blindness poison?

exp29's stage-8 finding was qualitative: REBEL emits the exact falsehood a
negated sentence denies. `"Paris is not the capital of Germany"` becomes
`('Germany', 'capital', 'Paris')`. What that costs depends entirely on a number
nobody has: **how often does the input contain negation, and how many extracted
triples come from those sentences?**

If the answer is 1% it is a defect to fix later. If it is 15% it disqualifies
the extractor for argumentative text, because every one of those triples enters
the store attributed to a real source with a real span and then *conflicts with
the truth* — a system built to surface disagreement manufacturing disagreements
that do not exist.

The measurement separates two things that are easy to conflate:

- **exposure** — the share of triples derived from a sentence carrying a
  negation cue. Mechanical, exact, and an upper bound on the damage.
- **inversion** — the share of those triples that actually assert the denied
  content. A negation cue may sit outside the extracted relation's scope, so
  exposure overstates it. This is estimated on a hand-checkable sample rather
  than assumed equal to exposure.

Predictions, registered before running:

- **G1** negation is markedly commoner in argumentative corpora (phil / econ /
  pol) than in reportage (news) — denying a position is what argument *is*.
- **G2** exposure exceeds 5% on the argumentative corpora, i.e. this is not a
  tail case.
- **G3** inversion is well below exposure, because many cues fall outside the
  relation's scope — but is not zero.

Usage: .venv/bin/python scripts/exp78_negation_exposure.py [n_per_corpus]
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 300

# Negation cues. Deliberately conservative: only forms that reverse a
# proposition, never "no doubt"/"not only" style intensifiers, which would
# inflate exposure without any risk of inversion.
CUE = re.compile(
    r"\b(?:is|are|was|were|has|have|had|does|do|did|can|could|will|would|"
    r"should|must|may)\s+not\b"
    r"|\bcannot\b|\bnever\b|\bn't\b"
    r"|\b(?:no|neither|nor)\s+\w+"
    r"|\b(?:denies|denied|deny|rejects|rejected|reject|refutes|refuted|"
    r"disputes|disputed|fails\s+to|failed\s+to|lacks|lacked)\b", re.I)
INTENSIFIER = re.compile(r"\bnot\s+only\b|\bno\s+doubt\b|\bnone\s+the\s+less\b", re.I)


def negated(s: str) -> bool:
    return bool(CUE.search(s)) and not INTENSIFIER.search(s)


def sentences_of(dom):
    out = []
    d = ROOT / "data" / dom / "pages"
    if d.exists():
        for f in sorted(d.glob("*.json")):
            pg = json.loads(f.read_text())
            for s in re.split(r"(?<=[.!?])\s+", pg["text"]):
                s = " ".join(s.split())
                if 40 < len(s) < 320:
                    out.append(s)
    return out


def news_sentences():
    rows = json.loads((ROOT / "data" / "news" / "multi_news_300.json").read_text())
    out = []
    for r in rows:
        for art in r["doc"].split("|||||"):
            for s in re.split(r"(?<=[.!?])\s+", art):
                s = " ".join(s.split())
                if 40 < len(s) < 320:
                    out.append(s)
    return out


CORPORA = {d: sentences_of(d) for d in ("phil", "econ", "pol")}
CORPORA["news"] = news_sentences()

print("=== G1: how often is the input negated? ===")
rates = {}
for name, sents in CORPORA.items():
    n = sum(1 for s in sents if negated(s))
    rates[name] = n / max(len(sents), 1)
    print(f"  {name:>6}: {n:>6}/{len(sents):<6} sentences negated "
          f"({100 * rates[name]:.1f}%)")

tok = AutoTokenizer.from_pretrained("Babelscape/rebel-large")
mdl = AutoModelForSeq2SeqLM.from_pretrained("Babelscape/rebel-large")
dev = "cuda" if torch.cuda.is_available() else "cpu"
mdl.to(dev).eval()


def triples(text, nb=5):
    enc = tok(text, return_tensors="pt", truncation=True, max_length=256).to(dev)
    with torch.no_grad():
        g = mdl.generate(**enc, max_length=200, num_beams=nb,
                         num_return_sequences=nb, length_penalty=1.0)
    out = []
    for d in tok.batch_decode(g, skip_special_tokens=False):
        d = d.replace("<s>", "").replace("</s>", "").replace("<pad>", "")
        s = r = o = ""
        cur = None
        for t in d.split():
            if t == "<triplet>":
                if s and r and o:
                    out.append((s.strip(), r.strip(), o.strip()))
                s, cur = "", "s"
            elif t == "<subj>":
                o, cur = "", "o"
            elif t == "<obj>":
                r, cur = "", "r"
            else:
                if cur == "s":
                    s += " " + t
                elif cur == "o":
                    o += " " + t
                elif cur == "r":
                    r += " " + t
        if s and r and o:
            out.append((s.strip(), r.strip(), o.strip()))
    return set(out)


print("\n=== G2: what share of extracted triples comes from negated text? ===")
expo, samples = {}, []
for name, sents in CORPORA.items():
    sub = sents[:N]
    from_neg = from_pos = 0
    for s in sub:
        ts = triples(s)
        if negated(s):
            from_neg += len(ts)
            if ts and len(samples) < 40:
                samples.append((name, s, sorted(ts)[:2]))
        else:
            from_pos += len(ts)
    tot = from_neg + from_pos
    expo[name] = from_neg / max(tot, 1)
    print(f"  {name:>6}: {from_neg:>5}/{tot:<6} triples from negated sentences "
          f"({100 * expo[name]:.1f}%)")

print("\n=== G3: inversion sample (cue inside the relation's span) ===")
# A conservative automatic proxy for inversion: the negation cue falls BETWEEN
# the subject and object mentions in the sentence, so it plausibly scopes the
# relation that was extracted. Hand-checkable, and printed for that purpose.
inv = 0
shown = 0
for name, s, ts in samples:
    for (a, r, b) in ts:
        ia, ib = s.lower().find(a.lower()[:20]), s.lower().find(b.lower()[:20])
        if ia < 0 or ib < 0:
            continue
        lo, hi = sorted((ia, ib))
        if CUE.search(s[lo:hi]):
            inv += 1
            if shown < 8:
                print(f"  [{name}] {s[:104]}")
                print(f"      -> ({a[:26]}, {r}, {b[:26]})")
                shown += 1
            break

arg_expo = max(expo[c] for c in ("phil", "econ", "pol"))
v = []
v.append(f"G1 {'CONFIRMED' if min(rates[c] for c in ('phil','econ','pol')) > rates['news'] else 'REFUTED'}"
         f": negation rate phil {100*rates['phil']:.1f}% / econ "
         f"{100*rates['econ']:.1f}% / pol {100*rates['pol']:.1f}% vs news "
         f"{100*rates['news']:.1f}%.")
v.append(f"G2 {'CONFIRMED' if arg_expo > 0.05 else 'REFUTED'}: up to "
         f"{100*arg_expo:.1f}% of triples from argumentative corpora derive "
         f"from negated sentences — {'not a tail case' if arg_expo > 0.05 else 'a tail case'}.")
v.append(f"G3 {'CONFIRMED' if 0 < inv < len(samples) else 'REFUTED'}: {inv} of "
         f"{len(samples)} sampled negated-sentence extractions have the cue "
         f"between subject and object, so exposure overstates inversion but "
         f"does not eliminate it.")
print("\n=== VERDICTS ===")
for x in v:
    print("  " + x)

(ROOT / "results" / "exp78_negation.json").write_text(json.dumps({
    "sentence_negation_rate": {k: round(v_, 4) for k, v_ in rates.items()},
    "triple_exposure": {k: round(v_, 4) for k, v_ in expo.items()},
    "inversion_sample_hits": inv, "inversion_sample_size": len(samples),
    "n_per_corpus": N, "verdicts": v,
    "scope": ("Exposure is mechanical and exact: the share of triples whose "
              "source sentence carries a proposition-reversing cue. Inversion "
              "is estimated by a conservative proxy - the cue falling between "
              "the subject and object mentions - and printed for hand "
              "checking, because a cue outside the relation's scope is "
              "harmless. Intensifiers like 'not only' are excluded."),
}, indent=1))
print("\n[done] results/exp78_negation.json")
