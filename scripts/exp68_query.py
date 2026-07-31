"""Walk the query path over the real store — answerable and unanswerable apart.

The store has been merged and its conflicts measured. It has never been ASKED
anything, and the query path carries the claims that make the design worth
having: up-lattice-only expansion, disagreement structured rather than
resolved, and refusal when the edges do not license an answer.

**Answerable and unanswerable are reported separately and never averaged**
(audit law #7), and the unanswerable population **includes the simple case**
(law #9) — a real subject with a predicate it genuinely lacks, which is the
question a store is most likely to answer anyway because everything about it
looks familiar. Three unanswerable populations are used:

  simple      real subject, real predicate, no such edge
  novel_pred  real subject, a predicate absent from the whole store
  novel_subj  a subject the store has never seen

Predictions, registered before running:

- **P1** answerable accuracy is high (>0.95) — this is retrieval over edges
  that exist, not inference.
- **P2** wrongness on unanswerable is **0.000** across all three populations.
  There is no generative step, so the only way to be wrong is to return an
  edge that is not there.
- **P3** up-lattice expansion **raises recall** on a superordinate predicate
  and **never** returns a subordinate answer to a subordinate question.
- **P4** raising `min_sources` to 2 collapses coverage, because exp67 measured
  only 1.6% of triples as multi-source — the refusal machinery works but this
  corpus cannot feed it.

Usage: .venv/bin/python scripts/exp68_query.py [n_claims]
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
from foundation.model.conflict import Claim, Evidence              # noqa: E402
from foundation.model.predicates import Lattice                    # noqa: E402
from foundation.model.query import ask                             # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
SEED = 0
FUNCTIONAL = frozenset({"P569", "P570", "P571", "P19", "P20"})
_YEAR, _YM = re.compile(r"^-?\d{1,4}$"), re.compile(r"^-?\d{1,4}-\d{2}$")
_YMD = re.compile(r"^-?\d{1,4}-\d{2}-\d{2}$")
_MONTH = ("january february march april may june july august september "
          "october november december").split()
_DMY = re.compile(r"^(\d{1,2})[- ]([a-z]+)[- ](\d{3,4})$")
_MDY = re.compile(r"^([a-z]+)[- ](\d{1,2}),?[- ](\d{3,4})$")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", norm_text(s).lower()).strip("-")[:80] or "x"


def as_date(o):
    s = norm_text(o).lower()
    for rx, order in ((_DMY, (3, 2, 1)), (_MDY, (3, 1, 2))):
        m = rx.match(s)
        if m and m.group(order[1]) in _MONTH:
            return {"t": f"{m.group(order[0]).zfill(4)}-"
                         f"{_MONTH.index(m.group(order[1])) + 1:02d}-"
                         f"{int(m.group(order[2])):02d}", "p": "day"}
    for rx, prec in ((_YMD, "day"), (_YM, "month"), (_YEAR, "year")):
        if rx.match(s):
            return {"t": s, "p": prec}
    return None


kb = KB(backend="pg", table="poc")
rows = sorted((c for c in kb.claims
               if not c["page"].startswith(("arxiv:", "hf:", "user"))),
              key=lambda c: int(c["idx"]))[:N]
pages = collections.defaultdict(set)
for r in rows:
    pages[(slug(r["subject"]), r["pid"], slug(r["object"]))].add(r["page"])

claims, truth = [], collections.defaultdict(set)
for (s, p, o), pgs in sorted(pages.items()):
    d = as_date(o)
    sort, obj = ("time", d) if d else ("entity", f"s.w:{o}")
    key = (f"s.w:{s}", p)
    truth[key].add(json.dumps(obj, sort_keys=True))
    for pg in sorted(pgs):
        try:
            hh = hexid(f"s.w:{s}", p, sort, obj)
        except Exception:                                        # noqa: BLE001
            continue
        claims.append(Claim(f"s.w:{s}", p, sort, obj, True, (),
                            claimant="s.w:extractor", hash=hh,
                            evidence=(Evidence("span", f"page:{pg}"),)))
subjects = sorted({c.subject for c in claims})
preds = sorted({c.predicate for c in claims})
print(f"{len(claims)} claims, {len(subjects)} subjects, {len(preds)} predicates",
      flush=True)

rng = random.Random(SEED)


def run(pop, label, min_sources=1, lattice=None):
    right = wrong = refused = 0
    for subj, pred in pop:
        a = ask(claims, subj, pred, None, lattice, FUNCTIONAL, min_sources)
        if not a.answered:
            refused += 1
            continue
        want = truth.get((subj, pred), set())
        got = {json.dumps(x.object, sort_keys=True) for x in a.answers}
        if want and got & want:
            right += 1
        else:
            wrong += 1
    n = max(len(pop), 1)
    print(f"  {label:>28}  n={len(pop):<5} correct={right / n:.3f} "
          f"WRONG={wrong / n:.3f}  refused={refused / n:.3f}")
    return {"n": len(pop), "correct": round(right / n, 4),
            "wrong": round(wrong / n, 4), "refused": round(refused / n, 4)}


# ---------------------------------------------------------- populations ----
answerable = [k for k in sorted(truth) if rng.random() < 0.25][:800]
have = set(truth)
simple = []
while len(simple) < 400:
    s, p = rng.choice(subjects), rng.choice(preds)
    if (s, p) not in have:
        simple.append((s, p))
novel_pred = [(rng.choice(subjects), "P999999") for _ in range(400)]
novel_subj = [(f"s.w:not-a-real-entity-{i}", rng.choice(preds))
              for i in range(400)]

# The HARD unanswerable case: a predicate that subjects like this one usually
# have and this one does not. Random pairs are mostly absurd, so a store gets
# no credit for refusing them; a near-miss is where over-answering happens.
by_pred = collections.defaultdict(set)
for s, p in truth:
    by_pred[p].add(s)
plausible = []
for s in subjects:
    mine_ = {p for (x, p) in truth if x == s}
    for p in sorted(mine_):
        for q in sorted(by_pred):
            if q not in mine_ and len(by_pred[q] & by_pred[p]) > 20:
                plausible.append((s, q))
                break
        break
    if len(plausible) >= 400:
        break

print("\n=== answerable vs unanswerable, never averaged (law #7) ===")
out = {"answerable": run(answerable, "answerable"),
       "unanswerable_simple": run(simple, "unanswerable/simple"),
       "unanswerable_novel_pred": run(novel_pred, "unanswerable/novel predicate"),
       "unanswerable_novel_subj": run(novel_subj, "unanswerable/novel subject"),
       "unanswerable_plausible": run(plausible, "unanswerable/PLAUSIBLE")}

# ------------------------------------------------- up-lattice expansion ----
print("\n=== P3: up-lattice expansion ===")
lat = Lattice()
lat.subsume("P19", "P_birth_or_death_place")     # place of birth ⊑ place
lat.subsume("P20", "P_birth_or_death_place")     # place of death ⊑ place
sup = [(s, "P_birth_or_death_place") for s in subjects
       if (s, "P19") in truth or (s, "P20") in truth][:300]
no_lat = sum(1 for s, p in sup if ask(claims, s, p, None, None).answered)
with_lat = sum(1 for s, p in sup if ask(claims, s, p, None, lat).answered)

# The leak population is CONSTRUCTED, not sampled. Sampling found only one
# subject in the whole corpus with P20 and not P19, so the first version of
# this test had a single chance to fire and its zero measured nothing — the
# third instrument this session that could not move. Synthetic claims are
# legitimate here because the thing under test is a code path, not a corpus
# property.
leak_pop = [s for s in subjects if (s, "P20") in truth and (s, "P19") not in truth]
synth = [Claim(f"s.syn:p{i}", "P20", "entity", f"s.syn:place{i}", True, (),
               claimant="s.syn:x", hash=f"SYN{i}",
               evidence=(Evidence("span", f"doc:{i}"),)) for i in range(200)]
leak_claims = claims + synth
leak_pop += [f"s.syn:p{i}" for i in range(200)]
sub_leak = sum(1 for s in leak_pop
               if any(x.predicate == "P20"
                      for x in ask(leak_claims, s, "P19", None, lat).answers))
print(f"  leak population (has P20, lacks P19): {len(leak_pop)} "
      f"({len(leak_pop) - 200} real + 200 synthetic)")
print(f"  superordinate question answered:  without lattice {no_lat}/{len(sup)}"
      f"   with lattice {with_lat}/{len(sup)}")
print(f"  subordinate question leaking a sibling's answer: {sub_leak} "
      f"(must be 0)")

# ----------------------------------------------------- P4: min_sources -----
print("\n=== P4: refusal threshold vs a single-source corpus ===")
strict = run(answerable, "answerable, min_sources=2", min_sources=2)

v = []
v.append(f"P1 {'CONFIRMED' if out['answerable']['correct'] > 0.95 else 'REFUTED'}"
         f" but NEARLY VACUOUS: answerable correct = "
         f"{out['answerable']['correct']:.3f}. Correctness is set overlap "
         f"against the store's own contents, so this asks whether lookup "
         f"finds what is present. It confirms plumbing, not design.")
worst = max(out[k]['wrong'] for k in out if k.startswith('unanswerable'))
v.append(f"P2 {'CONFIRMED' if worst == 0 else 'REFUTED'}: worst unanswerable "
         f"wrongness = {worst:.3f} across four populations including the "
         f"plausible near-miss. Structurally expected — there is no generative "
         f"step — so this is a regression guard rather than a discovery.")
v.append(f"P3 {'CONFIRMED' if with_lat > no_lat and sub_leak == 0 else 'REFUTED'}"
         f": lattice raises superordinate recall {no_lat} -> {with_lat} with "
         f"{sub_leak} subordinate leaks")
v.append(f"P4 {'CONFIRMED' if strict['refused'] > 0.9 else 'REFUTED'}: at "
         f"min_sources=2 the corpus refuses {strict['refused']:.3f} of "
         f"answerable questions")
print("\n=== VERDICTS ===")
for x in v:
    print("  " + x)

(ROOT / "results" / "exp68_query.json").write_text(json.dumps({
    "n_claims": len(claims), "populations": out,
    "strict_min_sources_2": strict,
    "lattice": {"superordinate_without": no_lat, "superordinate_with": with_lat,
                "subordinate_leaks": sub_leak, "n": len(sup)},
    "verdicts": v,
    "scope": ("Answerable and unanswerable reported separately and never "
              "averaged; the unanswerable set includes the simple case (real "
              "subject, real predicate, absent edge) as well as novel "
              "predicate and novel subject. Correctness is set-overlap against "
              "the store's own contents, so this measures retrieval and "
              "refusal, not extraction quality."),
}, indent=1))
print("\n[done] results/exp68_query.json")
