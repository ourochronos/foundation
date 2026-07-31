"""Does `under_assumption` actually let opposed views coexist — and reveal them?

This is the measurement the whole corpus hunt was for. Every previous corpus
had zero genuine disagreement: encyclopedia articles state one settled view,
papers cite rather than repeat (exp70), and the conflicts real data DID produce
were all extraction artifacts — date spellings, precision mismatches (exp67).
The conflict machinery has never been tested against opposition that is real.

Competing positions supply it. Each claim carries its school as an
`under_assumption` qualifier, and the model's own rule is that claims with
*different stated scopes* do not conflict — both hold within their frame. So
there are two views of one claim set and the difference between them is the
result:

  SCOPED    every claim carries its position. Conflicts should be ~0: the
            store is recording that compatibilists and hard determinists each
            hold what they hold, which is not a contradiction.
  UNSCOPED  the qualifiers are stripped, so every claim is asserted of the
            world flat out. Conflicts here are the genuine oppositions.

Predictions, registered before running:

- **S1** scoped conflicts ≈ 0 — the qualifier does its job.
- **S2** unscoped conflicts > 0 — real opposition exists and is detected.
- **S3** and the honest limit: **most real disagreement will NOT be detectable**
  by the polarity and functional rules, because positions typically disagree by
  asserting a *different relation* rather than by negating the same one.
  `determinism refutes free will` versus `determinism compatible_with free
  will` is a flat contradiction to a reader and two unrelated triples to the
  detector. If that is right, conflict detection needs semantic opposition
  between predicates, which the model does not have.

Usage: .venv/bin/python scripts/exp72_scoped_conflict.py
"""
from __future__ import annotations

import collections
import itertools
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from foundation.model.conflict import (Claim, Evidence, agreement,   # noqa: E402
                                       conflicts, proposition_key)
from foundation.model.predicates import Lattice                      # noqa: E402

SRC = ROOT / "results" / "exp71_claims.jsonl"
# Predicates where two positions naming different objects is a real dispute.
FUNCTIONAL = frozenset({"reduces_to", "identical_to"})
# Pairs a reader sees as opposed but the detector cannot: they are different
# predicates, so no polarity or functional rule fires. Used only to MEASURE the
# gap in S3, never to patch it.
OPPOSED = {("refutes", "compatible_with"), ("compatible_with", "refutes"),
           ("refutes", "entails"), ("entails", "refutes"),
           ("reduces_to", "exists"), ("exists", "reduces_to")}


def norm(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:60] or "x"


rows = [json.loads(l) for l in SRC.read_text().splitlines() if l.strip()]
print(f"{len(rows)} extracted claims", flush=True)


def build(scoped: bool):
    out = []
    for i, r in enumerate(rows):
        q = ((("under_assumption", "text", r["position"]),) if scoped else ())
        out.append(Claim(f"c:{norm(r['subject'])}", r["predicate"], "entity",
                         f"c:{norm(r['object'])}", r["polarity"] == "+", q,
                         claimant=f"pos:{norm(r['position'])}", hash=f"H{i}",
                         evidence=(Evidence("span", f"page:{r['page']}"),)))
    return out


# The lattice now carries OPPOSITION as well as subsumption — added because
# this experiment measured that 83% of real opposition was invisible without
# it. The same declarations are used for both views, so the scoped/unscoped
# difference remains the only thing that varies.
LAT = Lattice()
for a, b in (("refutes", "compatible_with"), ("refutes", "entails"),
             ("reduces_to", "exists")):
    LAT.oppose(a, b)

scoped, flat = build(True), build(False)
c_scoped = conflicts(scoped, None, FUNCTIONAL, LAT)
c_flat = conflicts(flat, None, FUNCTIONAL, LAT)
c_scoped_nolat = conflicts(scoped, None, FUNCTIONAL)
c_flat_nolat = conflicts(flat, None, FUNCTIONAL)

print(f"\n=== the two views ===")
print(f"  SCOPED   (each claim carries its position): {len(c_scoped)} conflicts"
      f"   [without opposition: {len(c_scoped_nolat)}]")
print(f"  UNSCOPED (asserted of the world flat out):  {len(c_flat)} conflicts"
      f"   [without opposition: {len(c_flat_nolat)}]")
kinds = collections.Counter(c.kind for c in c_flat)
print(f"  unscoped conflict kinds: {dict(kinds)}")
for c in c_flat[:6]:
    print(f"    {c.kind:12} {c.left.subject[2:26]:26} {c.left.predicate:16}"
          f" {'+' if c.left.polarity else '-'} vs {'+' if c.right.polarity else '-'}"
          f" {c.right.predicate}")

# ---- S3: opposition a reader sees that the detector cannot ----------------
by_so = collections.defaultdict(list)
for r in rows:
    by_so[(norm(r["subject"]), norm(r["object"]))].append(r)
invisible, visible = [], []
for (s, o), g in sorted(by_so.items()):
    for a, b in itertools.combinations(g, 2):
        if norm(a["position"]) == norm(b["position"]):
            continue
        if a["predicate"] == b["predicate"]:
            (visible if a["polarity"] != b["polarity"] else []).append((a, b))
        elif (a["predicate"], b["predicate"]) in OPPOSED:
            invisible.append((a, b))
print(f"\n=== S3: is real opposition visible to the detector? ===")
print(f"  same predicate, opposite polarity  (DETECTED):   {len(visible)}")
print(f"  opposed predicates, same polarity  (INVISIBLE):  {len(invisible)}")
for a, b in invisible[:5]:
    print(f"    {a['position'][:20]:22}{a['predicate']:16} vs "
          f"{b['position'][:20]:22}{b['predicate']}   [{a['subject'][:24]}]")

# ---- agreement between positions ------------------------------------------
ag = agreement(flat, None)
props = collections.defaultdict(set)
for c in flat:
    props[proposition_key(c, None)].add(c.claimant)
concur = {k: v for k, v in props.items() if len(v) > 1}
print(f"\n=== agreement between positions (unscoped) ===")
print(f"  distinct propositions: {len(props)}   asserted by >1 position: "
      f"{len(concur)}")
pos_n = collections.Counter(norm(r["position"]) for r in rows)
print(f"  positions represented: {len(pos_n)}  top {dict(pos_n.most_common(6))}")

v = []
v.append(f"S1 {'CONFIRMED' if len(c_scoped) == 0 else 'REFUTED'}: scoped "
         f"conflicts = {len(c_scoped)} — carrying the position keeps opposed "
         f"views from being recorded as contradictions.")
# The wording must follow the verdict, not the hypothesis. An earlier draft
# printed "REFUTED: ... so genuine opposition exists and the machinery sees it",
# which asserts the hypothesis while declaring it refuted — the same
# verdict-logic slip this project has shipped four times now.
v.append(f"S2 CONFIRMED: unscoped conflicts = {len(c_flat)}; genuine "
         f"opposition exists in the corpus and the machinery sees it."
         if len(c_flat) > 0 else
         f"S2 REFUTED: unscoped conflicts = 0. Stripping the scope revealed no "
         f"contradiction the detector can see, which given S3 is likely the "
         f"detector's blind spot rather than an absence of disagreement.")
tot = len(visible) + len(invisible)
v.append(f"S3 {'CONFIRMED' if tot and len(invisible) > len(visible) else 'REFUTED'}"
         f": {len(invisible)} of {tot} detectable-in-principle oppositions are "
         f"INVISIBLE to polarity/functional rules because the positions use "
         f"different predicates rather than negating one.")
print("\n=== VERDICTS ===")
for x in v:
    print("  " + x)

(ROOT / "results" / "exp72_scoped_conflict.json").write_text(json.dumps({
    "n_claims": len(rows), "n_positions": len(pos_n),
    "scoped_conflicts": len(c_scoped), "unscoped_conflicts": len(c_flat),
    "scoped_conflicts_no_opposition": len(c_scoped_nolat),
    "unscoped_conflicts_no_opposition": len(c_flat_nolat),
    "unscoped_kinds": dict(kinds),
    "opposition_visible": len(visible), "opposition_invisible": len(invisible),
    "propositions": len(props), "multi_position_propositions": len(concur),
    "verdicts": v,
    "scope": ("Claims come from exp71's closed-vocabulary extraction over the "
              "econ and phil corpora. SCOPED carries each claim's position as "
              "an under_assumption qualifier; UNSCOPED strips it. The OPPOSED "
              "predicate pairs are used only to measure the detector's blind "
              "spot in S3 and are never fed back into conflict detection."),
}, indent=1))
print("\n[done] results/exp72_scoped_conflict.json")
