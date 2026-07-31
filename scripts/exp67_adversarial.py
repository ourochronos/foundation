"""Two walks the last run left untested: the agreement path, and fusion bombs.

exp66 merged two stores that both read the same Wikipedia page, so every
proposition had exactly one independent source and **the agreement path was
never exercised at all**. It also never tested what the panel called the real
federation hazard: one bad `sameAs` fusing two people's classes and flooding
the conflict detector with spurious disputes.

**Walk A — genuine corroboration, from real data rather than synthesis.**
Wikipedia cross-references itself, so the same triple is often extracted from
several pages. Those are genuinely independent documents asserting one fact,
which is exactly what `agreement()` is supposed to count. No injection needed:
the corroboration is already in the corpus if it is there at all.

**Walk B — fusion bombs, and whether the circuit breakers actually bound
them.** Inject bad identity links between unrelated entities and watch the
functional-conflict count. The claim being tested is that `max_class_size` and
`require_agents` convert an unbounded flood into a bounded one.

Predictions, registered before running:

- **A1** some real fraction of triples appear on more than one page — call it
  5–15% — so the agreement path has real signal to count.
- **B1** without breakers, spurious conflicts grow **superlinearly** in the
  number of bad links, because fusing a class of size n makes every pair in it
  a candidate: O(n²) per functional predicate.
- **B2** `max_class_size` bounds the damage to roughly linear.
- **B3** `require_agents=2` blocks a single bad linker **entirely** — zero
  spurious conflicts — because every bad edge comes from one agent.

Usage: .venv/bin/python scripts/exp67_adversarial.py [n_claims]
"""
from __future__ import annotations

import collections
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from foundation.kb import KB                                      # noqa: E402
from foundation.model.canonical import hexid, norm_text            # noqa: E402
from foundation.model.conflict import (Claim, Evidence, agreement,  # noqa: E402
                                       conflicts)
from foundation.model.identity import Closure, Policy              # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
SEED = 0
# Genuinely functional Wikidata properties: one value per subject.
FUNCTIONAL = frozenset({"P569", "P570", "P571", "P19", "P20", "P571"})


_YEAR = re.compile(r"^-?\d{1,4}$")
_YM = re.compile(r"^-?\d{1,4}-\d{2}$")
_YMD = re.compile(r"^-?\d{1,4}-\d{2}-\d{2}$")


_MONTH = ("january february march april may june july august september "
          "october november december").split()
_DMY = re.compile(r"^(\d{1,2})[- ]([a-z]+)[- ](\d{3,4})$")
_MDY = re.compile(r"^([a-z]+)[- ](\d{1,2}),?[- ](\d{3,4})$")


def as_date(o: str):
    """Recognise a date however it is written, BEFORE anything else looks at it.

    Found by real data, and it is the worst kind of bug this model can have.
    The store marks '10 December 1815' as an entity, so sort inference sent it
    down the entity path; '1815-12-10' from another page became a *different*
    entity; and `date_of_birth` being functional then reported the two as a
    contradiction. Baseline run: **104 conflicts, all of them false**, asserting
    that Ada Lovelace's, Turing's and Einstein's birthdays are disputed.

    Note the asymmetry that makes this severe. A date misread as *text* only
    fails to conflict — a silent miss. A date misread as an *entity*
    manufactures a contradiction out of two spellings, and a system whose whole
    purpose is surfacing disagreement cannot afford to invent it.
    """
    s = norm_text(o).lower()
    for rx, order in ((_DMY, (3, 2, 1)), (_MDY, (3, 1, 2))):
        m = rx.match(s)
        if m and m.group(order[1]) in _MONTH:
            y = m.group(order[0]).zfill(4)
            mo = _MONTH.index(m.group(order[1])) + 1
            return {"t": f"{y}-{mo:02d}-{int(m.group(order[2])):02d}", "p": "day"}
    for rx, prec in ((_YMD, "day"), (_YM, "month"), (_YEAR, "year")):
        if rx.match(s):
            return {"t": s, "p": prec}
    return None


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", norm_text(s).lower()).strip("-")[:80] or "x"


kb = KB(backend="pg", table="poc")
rows = sorted((c for c in kb.claims
               if not c["page"].startswith(("arxiv:", "hf:", "user"))),
              key=lambda c: int(c["idx"]))[:N]
print(f"{len(rows)} real claims", flush=True)

# ------------------------------------------------------------------ walk A --
# Distinct triples, and the distinct PAGES each was extracted from.
pages = collections.defaultdict(set)
for r in rows:
    pages[(slug(r["subject"]), r["pid"], slug(r["object"]))].add(r["page"])
multi = {k: v for k, v in pages.items() if len(v) > 1}
print(f"\n=== A: corroboration already in the corpus ===")
print(f"  distinct triples: {len(pages)}   on >1 page: {len(multi)} "
      f"({100 * len(multi) / max(len(pages), 1):.1f}%)")

claims = []
for (s, p, o), pgs in sorted(pages.items()):
    d = as_date(o)
    sort, obj = ("time", d) if d else ("entity", f"s.w:{o}")
    for pg in sorted(pgs):                       # one claim act per source page
        try:
            hh = hexid(f"s.w:{s}", p, sort, obj)
        except Exception:                                        # noqa: BLE001
            continue
        claims.append(Claim(f"s.w:{s}", p, sort, obj, True, (),
                            claimant="s.w:extractor", hash=hh,
                            evidence=(Evidence("span", f"page:{pg}"),)))
ag = agreement(claims, None)
hist = collections.Counter(len(v) for v in ag.values())
corroborated = sum(n for k, n in hist.items() if k > 1)
print(f"  propositions: {len(ag)}   with >1 INDEPENDENT source: {corroborated}")
print(f"  agreement histogram: {dict(sorted(hist.items())[:6])}")

# ------------------------------------------------------------------ walk B --
print(f"\n=== B: fusion bombs vs circuit breakers ===")
ents = sorted({c.subject for c in claims}
              | {c.object for c in claims if c.object_sort == "entity"})
rng = random.Random(SEED)
base = conflicts(claims, None, FUNCTIONAL)
print(f"  baseline conflicts (no bad links): {len(base)}")

def confusable_pairs(ents, n, rng):
    """A REALISTIC bad linker: fuses entities with similar names.

    The first version of this injected uniformly random `sameAs` and found
    almost nothing — 400 bad links produced 5 extra conflicts. That is not
    evidence the hazard is imaginary; it is evidence the adversary was wrong.
    Random links over thousands of entities almost never join two that share a
    functional predicate, so there is nothing to contradict.

    The threat is a linker that fuses *plausible* entities, which is what an
    over-eager name matcher actually does — and those are precisely the ones
    that both have a birth date. Grouping by a shared name token reproduces it.
    """
    buckets = collections.defaultdict(list)
    for e in ents:
        for tok in e.split(":", 1)[1].split("-"):
            if len(tok) > 3:
                buckets[tok].append(e)
    cands = [b for b in buckets.values() if len(b) > 1]
    out = []
    while cands and len(out) < n:
        b = rng.choice(cands)
        a, c = rng.choice(b), rng.choice(b)
        if a != c:
            out.append((a, c, "agent:bad_linker"))
    return out


REGIMES = (("no breakers", Policy(max_class_size=10 ** 9, require_agents=1)),
           ("max_class_size=64", Policy(max_class_size=64, require_agents=1)),
           ("require_agents=2", Policy(max_class_size=10 ** 9, require_agents=2)))
results = {}
print(f"  {'regime':>20} {'bad links':>10} {'class max':>10} "
      f"{'conflicts':>10} {'rejected':>9}")
for name, pol in REGIMES:
    row = []
    for n_bad in (0, 25, 100, 400):
        cl = Closure(pol)
        cl.accept_all(confusable_pairs(ents, n_bad, random.Random(SEED)))
        biggest = max((len(cl.members(e)) for e in ents), default=1)
        found = conflicts(claims, cl, FUNCTIONAL)
        row.append({"bad_links": n_bad, "max_class": biggest,
                    "conflicts": len(found), "rejected": len(cl.rejected)})
        print(f"  {name:>20} {n_bad:>10} {biggest:>10} {len(found):>10} "
              f"{len(cl.rejected):>9}", flush=True)
    results[name] = row

# ------------------------------------------------------------------ verdict --
nb = {r["bad_links"]: r["conflicts"] for r in results["no breakers"]}
cap = {r["bad_links"]: r["conflicts"] for r in results["max_class_size=64"]}
req = {r["bad_links"]: r["conflicts"] for r in results["require_agents=2"]}
b0 = len(base)
verdicts = []
lo, hi = nb[100] - b0, nb[400] - b0
MIN_SIGNAL = 20          # below this the ratio is noise, not a growth rate
if lo < MIN_SIGNAL:
    verdicts.append(
        f"B1 NO SIGNAL: only {lo} spurious conflicts at 100 bad links and "
        f"{hi} at 400 — too few to call a growth rate. A ratio computed here "
        f"would be a divide-by-guard artifact, not a measurement, and that "
        f"exact mistake has been made in this project three times.")
else:
    growth = hi / lo
    verdicts.append(
        f"B1 {'CONFIRMED' if growth > 4.5 else 'REFUTED'}: without breakers, "
        f"4x the bad links gives {growth:.1f}x the spurious conflicts "
        f"({lo} -> {hi}); superlinear needs >4.")
if hi < MIN_SIGNAL:
    verdicts.append(
        f"B2 UNTESTABLE: the unbroken regime only reached {hi} spurious "
        f"conflicts, so there is nothing for a breaker to cut.")
else:
    verdicts.append(
        f"B2 {'CONFIRMED' if cap[400] - b0 < hi / 2 else 'REFUTED'}: "
        f"max_class_size cuts spurious conflicts at 400 bad links from "
        f"{hi} to {cap[400] - b0}.")
verdicts.append(
    f"B3 {'CONFIRMED' if req[400] == b0 else 'REFUTED'}: require_agents=2 "
    f"leaves {req[400] - b0} spurious conflicts from a single bad linker "
    f"(predicted 0).")
verdicts.append(
    f"A1 {'CONFIRMED' if 5 <= 100 * len(multi) / max(len(pages), 1) <= 15 else 'REFUTED'}"
    f": {100 * len(multi) / max(len(pages), 1):.1f}% of triples appear on more "
    f"than one page (predicted 5-15%).")
print("\n=== VERDICTS ===")
for v in verdicts:
    print("  " + v)

(ROOT / "results" / "exp67_adversarial.json").write_text(json.dumps({
    "n_rows": len(rows), "distinct_triples": len(pages),
    "multi_page_triples": len(multi),
    "propositions": len(ag), "corroborated": corroborated,
    "agreement_hist": dict(sorted(hist.items())),
    "baseline_conflicts": b0, "regimes": results, "verdicts": verdicts,
    "scope": ("Walk A uses corroboration already present in the corpus - the "
              "same triple extracted from different Wikipedia pages is "
              "genuinely independent evidence - rather than synthesising it. "
              "Walk B injects random sameAs between unrelated entities and "
              "measures spurious functional conflicts against three policy "
              "regimes. Predictions were registered in the docstring before "
              "the run."),
}, indent=1))
print("\n[done] results/exp67_adversarial.json")
