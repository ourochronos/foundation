"""Do positions that share an axis corroborate each other?

Three corpora have now produced zero corroboration between claimants:
encyclopedia articles (exp67, 1.6% and all within-source), papers (exp70, 0 of
1207 — they cite rather than repeat), competing philosophical positions (exp72,
0 of 144 — they disagree rather than concur). `agreement()` has never had
anything to count, which is a problem for a design whose epistemic payoff is
counting independent support.

Politics is the first corpus where concurrence should exist, and the reason is
structural: **a position is a point in a space, not a label.** Social democrats
and democratic socialists differ, but both sit under *left economics*, so
claims they share are genuinely shared — by the axis, if not by the label.

So this measures agreement at two levels:

  POSITION  under_assumption is the position itself. Expect ~0, as everywhere.
  AXIS      each claim's frame is GENERALISED up the lattice to its axes.
            Two positions concurring under one axis now land on one
            proposition, and that is corroboration the label view cannot see.

Generalising up is the safe direction — the same asymmetry the predicate
lattice uses. A claim held under social democracy IS held under left economics;
the converse does not follow, and this never runs that way.

Predictions, registered before running:

- **A1** position-level agreement stays ≈ 0, matching all three prior corpora.
- **A2** axis-level agreement is > 0 — the first corroboration this project has
  measured between distinct claimants.
- **A3** axis generalisation also raises CONFLICT, because two positions under
  one axis asserting opposed relations now collide. Corroboration and
  contradiction should appear together; a change that produced only one of them
  would mean the generalisation is loose rather than informative.

Usage: .venv/bin/python scripts/exp73_axes.py
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from foundation.model.conflict import (Claim, Evidence, conflicts,     # noqa: E402
                                       proposition_key)
from foundation.model.predicates import Lattice, LatticeError          # noqa: E402

FRAMES = json.loads((ROOT / "data" / "frames.json").read_text())
SRC = ROOT / "results" / "exp71_claims.jsonl"
FUNCTIONAL = frozenset({"reduces_to", "identical_to"})


def norm(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:60] or "x"


lat = Lattice()
for a, b in FRAMES["oppose_predicates"]:
    lat.oppose(a, b)
frames = Lattice()
for sub, sup in FRAMES["subsume"]:
    try:
        frames.subsume(norm(sub), norm(sup))
    except LatticeError as e:
        print(f"  frame rejected: {e}")
AXES = {norm(sup) for _, sup in FRAMES["subsume"]}

rows = [json.loads(l) for l in SRC.read_text().splitlines() if l.strip()]
placed = [r for r in rows if frames.ancestors(norm(r["position"])) - {norm(r["position"])}]
print(f"{len(rows)} claims, {len(placed)} from positions placed on an axis "
      f"({len(AXES)} axes)", flush=True)


def build(mode: str):
    """mode: 'position' | 'axis' | 'none'."""
    out = []
    for i, r in enumerate(rows):
        pos = norm(r["position"])
        if mode == "position":
            qs = [(("under_assumption", "text", pos),)]
        elif mode == "axis":
            ax = sorted(frames.ancestors(pos) & AXES)
            qs = [(("under_assumption", "text", a),) for a in ax] or \
                 [(("under_assumption", "text", pos),)]
        else:
            qs = [()]
        for j, q in enumerate(qs):
            out.append(Claim(f"c:{norm(r['subject'])}", r["predicate"], "entity",
                             f"c:{norm(r['object'])}", r["polarity"] == "+", q,
                             claimant=f"pos:{pos}", hash=f"H{i}_{j}",
                             evidence=(Evidence("span", f"page:{r['page']}"),)))
    return out


def measure(mode):
    cs = build(mode)
    props = collections.defaultdict(set)
    for c in cs:
        props[proposition_key(c, None)].add(c.claimant)
    concur = {k: v for k, v in props.items() if len(v) > 1}
    cf = conflicts(cs, None, FUNCTIONAL, lat)
    return {"claims": len(cs), "propositions": len(props),
            "corroborated": len(concur), "conflicts": len(cf),
            "kinds": dict(collections.Counter(c.kind for c in cf))}, concur


print(f"\n{'view':>10} {'claims':>7} {'props':>7} {'CORROBORATED':>13} "
      f"{'conflicts':>10}")
res = {}
for mode in ("position", "axis", "none"):
    m, concur = measure(mode)
    res[mode] = m
    print(f"  {mode:>8} {m['claims']:>7} {m['propositions']:>7} "
          f"{m['corroborated']:>13} {m['conflicts']:>10}   {m['kinds']}")
    if mode == "axis" and concur:
        print("    corroborating pairs:")
        for k, v in list(concur.items())[:5]:
            d = json.loads(k)
            print(f"      {d['s'][2:26]:26} {d['p']:16} {d['o'][1][2:22]:22} "
                  f"<- {sorted(x[4:] for x in v)}")

v = []
v.append(f"A1 {'CONFIRMED' if res['position']['corroborated'] == 0 else 'REFUTED'}"
         f": position-level corroboration = {res['position']['corroborated']}, "
         f"matching all three prior corpora.")
v.append(f"A2 {'CONFIRMED' if res['axis']['corroborated'] > 0 else 'REFUTED'}: "
         f"axis-level corroboration = {res['axis']['corroborated']} — "
         f"{'the first measured between distinct claimants' if res['axis']['corroborated'] else 'still none'}.")
v.append(f"A3 {'CONFIRMED' if res['axis']['conflicts'] > res['position']['conflicts'] else 'REFUTED'}"
         f": axis conflicts {res['position']['conflicts']} -> "
         f"{res['axis']['conflicts']}; corroboration and contradiction should "
         f"rise together or the generalisation is loose rather than informative.")
print("\n=== VERDICTS ===")
for x in v:
    print("  " + x)

(ROOT / "results" / "exp73_axes.json").write_text(json.dumps({
    "n_claims": len(rows), "placed_on_axis": len(placed), "n_axes": len(AXES),
    "views": res, "verdicts": v,
    "scope": ("Frames come from the authored lattice in data/frames.json. The "
              "AXIS view generalises each claim's under_assumption UP to its "
              "axes, which is the safe direction - a claim held under social "
              "democracy is held under left economics, never the converse. A "
              "claim under several axes contributes one claim per axis, so the "
              "axis view has more claims than the position view by "
              "construction and proposition counts are not comparable across "
              "views; corroboration and conflict counts are."),
}, indent=1))
print("\n[done] results/exp73_axes.json")
