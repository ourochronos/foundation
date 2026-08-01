"""Do TRIPLES corroborate where entities do? REBEL over multi-source news.

exp74 showed the entity substrate for corroboration exists in reportage (8,802
co-mention pairs, versus zero in four discourse corpora) but explicitly did not
show that extracted *triples* corroborate. This closes that gap, and it does so
with a purpose-built extractor rather than a generative model — a class of tool
this project never looked for until prompted.

**Why REBEL changes the argument.** exp73 concluded that closing the entity and
predicate vocabularies was "an ontology-building project" and the line was shut
on that basis. That was wrong, or at least premature: REBEL emits
`(subject, relation, object)` directly and its relation vocabulary **is
Wikidata properties** — `presenter`, `country`, `participant` — so the
predicate vocabulary closes for free, with no authoring at all. That is one of
the three vocabularies exp73 said had to close simultaneously, obtained off the
shelf.

**And its failure mode is the right one.** On "Compatibilists hold that free
will is compatible with determinism" REBEL returns *nothing* — it is trained on
factual relations between named entities, not abstract conceptual ones, and it
declines rather than inventing. So its competence domain is precisely the genre
where exp74 located corroboration. That alignment is evidence for the genre
hypothesis, not a limitation to work around.

Predictions, registered before running:

- **R1** triple-level corroboration is **> 0** — the thing four discourse
  corpora never produced.
- **R2** it is well below the co-mention upper bound of exp74 (5.0%), because
  agreeing on a *relation* is strictly harder than co-mentioning two entities.
- **R3** surface-form variation is the remaining barrier: merging obvious
  entity aliases (`Bourdain` → `Anthony Bourdain`) measurably raises
  corroboration, which would locate the last of the three vocabularies rather
  than leaving it as an unbounded ontology problem.

Usage: .venv/bin/python scripts/exp75_rebel_news.py [n_events]
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

ROOT = Path(__file__).resolve().parent.parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
MAX_CHARS = 1400

tok = AutoTokenizer.from_pretrained("Babelscape/rebel-large")
mdl = AutoModelForSeq2SeqLM.from_pretrained("Babelscape/rebel-large")
dev = "cuda" if torch.cuda.is_available() else "cpu"
mdl.to(dev).eval()
print(f"REBEL on {dev}", flush=True)


def triples(text, nb=3):
    enc = tok(text, return_tensors="pt", truncation=True, max_length=512).to(dev)
    with torch.no_grad():
        g = mdl.generate(**enc, max_length=256, num_beams=nb,
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


rows = json.loads((ROOT / "data" / "news" / "multi_news_300.json").read_text())
events = []
for r in rows:
    arts = [a.strip() for a in r["doc"].split("|||||") if len(a.strip()) > 400]
    if len(arts) >= 3:
        events.append(arts)
events = events[:N]
print(f"{len(events)} events, {sum(len(e) for e in events)} articles", flush=True)


def norm(s):
    return re.sub(r"[^a-z0-9 ]+", "", s.lower()).strip()


def alias_map(names):
    """Merge an obvious alias into its longer form: `Bourdain` -> `Anthony
    Bourdain` when the short name is a whole-word suffix of exactly one longer
    name. Deliberately conservative — one ambiguous match and it declines,
    because the failure this project keeps hitting is over-merging
    (`full-employment`~`unemployment`), not under-merging."""
    longer = sorted({n for n in names if " " in n}, key=len, reverse=True)
    out = {}
    for n in names:
        if " " in n:
            continue
        hits = [L for L in longer if re.search(rf"\b{re.escape(n)}$", L)]
        if len(hits) == 1:
            out[n] = hits[0]
    return out


raw_c = raw_t = al_c = al_t = 0
examples = []
for ei, arts in enumerate(events):
    per_doc = []
    for a in arts:
        ts = set()
        for chunk in [a[i:i + MAX_CHARS] for i in range(0, min(len(a), MAX_CHARS * 3), MAX_CHARS)]:
            if len(chunk) > 200:
                ts |= triples(chunk)
        per_doc.append({(norm(s), norm(r), norm(o)) for s, r, o in ts})
    seen = collections.defaultdict(set)
    for di, ts in enumerate(per_doc):
        for t in ts:
            seen[t].add(di)
    raw_t += len(seen)
    hit = {t for t, ds in seen.items() if len(ds) >= 2}
    raw_c += len(hit)

    names = {x for ts in per_doc for t in ts for x in (t[0], t[2])}
    am = alias_map(names)
    seen2 = collections.defaultdict(set)
    for di, ts in enumerate(per_doc):
        for s, r, o in ts:
            seen2[(am.get(s, s), r, am.get(o, o))].add(di)
    al_t += len(seen2)
    h2 = {t for t, ds in seen2.items() if len(ds) >= 2}
    al_c += len(h2)
    if h2 and len(examples) < 6:
        examples.append((ei, sorted(h2)[:2]))
    if (ei + 1) % 10 == 0:
        print(f"  {ei + 1}/{len(events)}  raw {raw_c}/{raw_t}  "
              f"aliased {al_c}/{al_t}", flush=True)

print(f"\n=== triple-level corroboration ===")
print(f"  raw surface forms : {raw_c}/{raw_t} "
      f"({100 * raw_c / max(raw_t, 1):.2f}%)")
print(f"  after alias merge : {al_c}/{al_t} "
      f"({100 * al_c / max(al_t, 1):.2f}%)")
for ei, ex in examples:
    print(f"    event {ei}: {ex}")

v = []
v.append(f"R1 {'CONFIRMED' if raw_c > 0 else 'REFUTED'}: {raw_c} triples "
         f"asserted by >=2 independent sources, versus 0 in four discourse "
         f"corpora.")
v.append(f"R2 {'CONFIRMED' if 100 * raw_c / max(raw_t, 1) < 5.0 else 'REFUTED'}"
         f": triple corroboration {100 * raw_c / max(raw_t, 1):.2f}% sits "
         f"{'below' if 100 * raw_c / max(raw_t, 1) < 5.0 else 'above'} exp74's "
         f"5.0% co-mention upper bound, as agreeing on a relation is harder "
         f"than co-mentioning two entities.")
v.append(f"R3 {'CONFIRMED' if al_c > raw_c else 'REFUTED'}: conservative alias "
         f"merging moves corroboration {raw_c} -> {al_c}, so surface variation "
         f"{'is' if al_c > raw_c else 'is not'} a locatable remaining barrier.")
print("\n=== VERDICTS ===")
for x in v:
    print("  " + x)

(ROOT / "results" / "exp75_rebel_news.json").write_text(json.dumps({
    "events": len(events), "articles": sum(len(e) for e in events),
    "raw_corroborated": raw_c, "raw_triples": raw_t,
    "aliased_corroborated": al_c, "aliased_triples": al_t,
    "verdicts": v,
    "scope": ("REBEL emits Wikidata-property relations, so the predicate "
              "vocabulary is closed by the extractor rather than authored. "
              "Entities remain surface forms; the alias pass merges a short "
              "name into a longer one only when the match is unique, since "
              "over-merging is this project's demonstrated failure mode. Only "
              "the first ~4k characters of each article are read."),
}, indent=1))
print("\n[done] results/exp75_rebel_news.json")
