"""The corroboration falsifier: does reportage repeat where discourse did not?

Four corpora produced four zeros and the closure was written on the hypothesis
that repetition is structural in *observational* text and absent from
*discourse*. The status panel called that "an untested hypothesis carried as
consolation," which is fair, and named the cheap falsifier: multi-source news.

Reportage is the opposite genre to everything tried so far. Ten outlets
covering one event **restate the same facts by construction** — that is what
wire copy is — where papers cite rather than repeat and positions disagree
rather than concur. And crucially the entity vocabulary closes for free:
subjects are *named people, organisations and places*, which is exactly where
string matching works, unlike the abstract concepts that produced 510 distinct
terms from 316 claims.

So this is the strongest available test, and it is designed to be able to fail
in the informative direction:

- if corroboration is ~0 **here**, it is dead as a mechanism and `min_sources`
  should be deleted rather than mothballed;
- if it fires, the closure was premature and the corpus choice was the whole
  problem.

**The measurement avoids the extraction confound entirely.** Rather than
running a model over the text and measuring whether *its* triples repeat —
which conflates extractor variance with genuine non-repetition — this counts
**named-entity co-mention agreement**: for each event, how many
(entity, entity) pairs are mentioned together by more than one source article.
That is corroboration at its most generous, so a zero here is decisive in a way
a zero after extraction would not be.

Predictions, registered before running:

- **N1** entity repetition across sources within an event is high (>50% of
  entities appear in ≥2 articles) — the vocabulary closes for free.
- **N2** co-mention corroboration is **> 0**, unlike all four prior corpora.
- **N3** cross-EVENT corroboration is near zero, confirming the signal is
  genuine agreement about one event rather than generic frequent terms.

Usage: .venv/bin/python scripts/exp74_news_corroboration.py [n_events]
"""
from __future__ import annotations

import collections
import itertools
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 137

rows = json.loads((ROOT / "data" / "news" / "multi_news_300.json").read_text())
events = []
for r in rows:
    arts = [a.strip() for a in r["doc"].split("|||||") if len(a.strip()) > 400]
    if len(arts) >= 3:                       # need >=3 independent sources
        events.append(arts)
events = events[:N]
print(f"{len(events)} events with >=3 sources "
      f"({sum(len(e) for e in events)} articles)", flush=True)

# Named entities by orthography: capitalised multiword spans, minus sentence
# openers and stopwords. Crude on purpose — a heavier NER would add a
# dependency whose errors are harder to reason about than this one's, and the
# question is whether repetition exists at all, not its exact rate.
STOP = {"The", "A", "An", "But", "And", "In", "On", "At", "For", "It", "He",
        "She", "They", "We", "This", "That", "There", "His", "Her", "Their",
        "New", "Some", "One", "After", "When", "While", "If", "As", "So",
        "According", "Reuters", "AP", "Associated", "Press", "CNN", "By"}
NE = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,3})\b")


def ents(text: str) -> set[str]:
    out = set()
    for s in re.split(r"(?<=[.!?])\s+", text):
        for m in NE.finditer(s[1:] if s else ""):    # skip sentence-opener cap
            w = m.group(1)
            if w.split()[0] not in STOP and len(w) > 3:
                out.add(w)
    return out


per_event = [[ents(a) for a in arts] for arts in events]

# ---- N1: does the entity vocabulary close within an event? ----------------
shared_frac, all_shared = [], []
for docs in per_event:
    c = collections.Counter(e for d in docs for e in d)
    if not c:
        continue
    sh = {e for e, n in c.items() if n >= 2}
    shared_frac.append(len(sh) / len(c))
    all_shared.append(sh)
print(f"\n=== N1: entity repetition WITHIN an event ===")
print(f"  mean fraction of entities mentioned by >=2 sources: "
      f"{sum(shared_frac) / max(len(shared_frac), 1):.3f}")
print(f"  median shared entities per event: "
      f"{sorted(len(s) for s in all_shared)[len(all_shared) // 2]}")

# ---- N2: co-mention corroboration ----------------------------------------
corr, total = 0, 0
examples = []
for ei, docs in enumerate(per_event):
    pairs = collections.defaultdict(set)
    for di, d in enumerate(docs):
        top = sorted(d)[:60]                 # bound the quadratic
        for a, b in itertools.combinations(top, 2):
            pairs[(a, b)].add(di)
    total += len(pairs)
    hit = {p for p, ds in pairs.items() if len(ds) >= 2}
    corr += len(hit)
    if hit and len(examples) < 5:
        examples.append((ei, sorted(hit)[:3]))
print(f"\n=== N2: co-mention corroboration ===")
print(f"  entity pairs asserted together: {total}")
print(f"  by >=2 INDEPENDENT sources:     {corr}  "
      f"({100 * corr / max(total, 1):.1f}%)")
for ei, ex in examples[:4]:
    print(f"    event {ei}: {ex}")

# ---- N3: is it about the event, or just frequent words? -------------------
cross = collections.defaultdict(set)
for ei, docs in enumerate(per_event):
    for e in set().union(*docs) if docs else set():
        cross[e].add(ei)
promiscuous = {e for e, evs in cross.items() if len(evs) > 1}
within_only = [s - promiscuous for s in all_shared]
print(f"\n=== N3: event-specific vs generic ===")
print(f"  entities appearing in >1 EVENT (generic): {len(promiscuous)}"
      f" of {len(cross)}")
print(f"  median event-specific shared entities: "
      f"{sorted(len(s) for s in within_only)[len(within_only) // 2]}")

mean_share = sum(shared_frac) / max(len(shared_frac), 1)
v = []
v.append(f"N1 {'CONFIRMED' if mean_share > 0.5 else 'REFUTED'}: "
         f"{mean_share:.3f} of entities per event are mentioned by >=2 "
         f"sources — the vocabulary closes {'for free' if mean_share > 0.5 else 'less than hoped'}.")
v.append(f"N2 {'CONFIRMED' if corr > 0 else 'REFUTED'}: {corr} co-mention "
         f"pairs are corroborated by independent sources, versus 0 in all four "
         f"prior corpora." if corr else
         f"N2 REFUTED: 0 corroborated pairs even in reportage — corroboration "
         f"is dead as a mechanism and min_sources should be deleted.")
med_spec = sorted(len(s) for s in within_only)[len(within_only) // 2]
v.append(f"N3 {'CONFIRMED' if med_spec > 0 else 'REFUTED'}: median "
         f"{med_spec} event-SPECIFIC shared entities, so the signal is "
         f"agreement about one event rather than generic frequent terms.")
print("\n=== VERDICTS ===")
for x in v:
    print("  " + x)

(ROOT / "results" / "exp74_news.json").write_text(json.dumps({
    "events": len(events), "articles": sum(len(e) for e in events),
    "mean_shared_entity_fraction": round(mean_share, 4),
    "pairs_total": total, "pairs_corroborated": corr,
    "generic_entities": len(promiscuous), "distinct_entities": len(cross),
    "median_event_specific_shared": med_spec, "verdicts": v,
    "scope": ("Corroboration is measured as named-entity CO-MENTION agreement, "
              "not extracted-triple agreement, deliberately: running a model "
              "here would conflate extractor variance with genuine "
              "non-repetition. This is corroboration at its most generous, so "
              "a zero would be decisive where a zero after extraction would "
              "not. Entities are recognised orthographically rather than by a "
              "trained NER, which under-counts but does not manufacture "
              "agreement."),
}, indent=1))
print("\n[done] results/exp74_news.json")
