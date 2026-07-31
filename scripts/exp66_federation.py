"""Walk the field: real claims through the v2 model, split, merged, measured.

Four panel rounds found real flaws by reading. This finds the other kind — the
ones nobody thinks to imagine — by running the model over 12,942 real
extracted claims and merging two synthetic stores built from them.

Note what would have caught the `prop_ref` bug in thirty seconds: looking at an
actual agreement histogram and seeing unrelated propositions in one bucket.
Four expert reviewers were needed to find by reading what one bad number shows.

**The harness is built to be walked repeatedly.** Every claim that fails to
convert is appended to `results/landmines.jsonl` with its reason and its
original row, so the corpus of known-messy cases grows monotonically and
becomes a regression suite. Stepping on a mine is the point; stepping on the
same one twice is the failure.

**Ground truth is available and that is the whole design.** Both synthetic
stores are built from ONE corpus, so any two claims descending from the same
original row are known to be about the same fact. Anything the model then
reports as a conflict between them is a **false positive**, measured rather
than argued. That number is the one to watch: a conflict detector that fires on
agreement is worse than one that stays silent.

Usage:
  .venv/bin/python scripts/exp66_federation.py [n_claims] [--precision-drift F]
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from foundation.kb import KB                                      # noqa: E402
from foundation.model.canonical import (CanonError, hexid,         # noqa: E402
                                        mint_namespace, norm_text)
from foundation.model.conflict import (Claim, Evidence, agreement,  # noqa: E402
                                       conflicts, proposition_key)
from foundation.model.identity import Closure, Policy              # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 4000
DRIFT = (float(sys.argv[sys.argv.index("--precision-drift") + 1])
         if "--precision-drift" in sys.argv else 0.0)
NS_A, NS_B = mint_namespace("store-a"), mint_namespace("store-b")
SEED_NS = "seed"

LAND = ROOT / "results" / "landmines.jsonl"
mines: list[dict] = []


def mine(kind: str, why: str, row: dict) -> None:
    mines.append({"kind": kind, "why": why[:200], "row": row})


# ---------------------------------------------------------------- sorts ----
_YEAR = re.compile(r"^-?\d{3,4}$")
_YM = re.compile(r"^-?\d{3,4}-\d{2}$")
_YMD = re.compile(r"^-?\d{3,4}-\d{2}-\d{2}$")
_NUM = re.compile(r"^-?\d[\d,]*\.?\d*$")


def infer_sort(row: dict):
    """Guess a sort from a bare string object. Deliberately fallible.

    The store holds `object` as text with no type, so this is the first place
    real data meets a typed model — and every wrong guess here is a landmine
    worth recording rather than a bug worth hiding. A date read as text will
    never conflict with the same date read as time, which is silent.
    """
    o = norm_text(row["object"])
    if row.get("obj_eid") not in (None, "None", ""):
        return "entity", o
    for rx, prec in ((_YMD, "day"), (_YM, "month"), (_YEAR, "year")):
        if rx.match(o):
            return "time", {"t": o, "p": prec}
    if _NUM.match(o) and len(o) > 4:
        return "quantity", {"n": o.replace(",", ""), "u": None}
    return "text", o


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm_text(s).lower()).strip("-")[:80] or "x"


def drift_precision(val, sort):
    """REFINE a year to a full date — fable's event-key dilemma, live.

    The first version of this coarsened instead, and measured nothing: every
    time literal in this corpus is already year-precision, so coarsening a year
    to a year is a no-op and the knob could not move. The realistic divergence
    runs the other way — one extractor recovers "1940-06-15" where another got
    only "1940" — and that is what splits one fact into two propositions.

    Whether that matters is empirical, which is the point of measuring it
    rather than arguing about it.
    """
    if sort != "time" or not isinstance(val, dict) or val.get("p") != "year":
        return val
    return {"t": f"{norm_text(val['t']).zfill(4)}-06-15", "p": "day"}


def build(rows, ns, drift=0.0):
    """One synthetic store: local refs, one claim act per row."""
    out, rng = [], 0
    for r in rows:
        try:
            sort, obj = infer_sort(r)
        except Exception as e:                                   # noqa: BLE001
            mine("sort_inference", repr(e), r)
            continue
        rng = (rng * 1103515245 + 12345) & 0x7FFFFFFF            # deterministic
        if drift and (rng / 0x7FFFFFFF) < drift:
            obj = drift_precision(obj, sort)
        subj = f"{ns}:{slug(r['subject'])}"
        if sort == "entity":
            obj = f"{ns}:{slug(obj)}"
        try:
            h = hexid(subj, r["pid"], sort, obj)
        except CanonError as e:
            mine("canonicalise", str(e), r)
            continue
        out.append(Claim(subj, r["pid"], sort, obj, True, (),
                         claimant=f"{ns}:extractor", hash=h,
                         evidence=(Evidence("span", f"page:{r['page']}"),)))
    return out


print(f"loading store …", flush=True)
kb = KB(backend="pg", table="poc")
wiki = sorted((c for c in kb.claims
               if not c["page"].startswith(("arxiv:", "hf:", "user"))),
              key=lambda c: int(c["idx"]))[:N]
print(f"{len(wiki)} real claims, drift={DRIFT}", flush=True)

# Both stores see the SAME rows, so every pair is known-agreeing ground truth.
A, B = build(wiki, NS_A), build(wiki, NS_B, drift=DRIFT)
converted = len(A)
print(f"converted {converted}/{len(wiki)} per store "
      f"({100 * converted / max(len(wiki), 1):.1f}%), {len(mines)} landmines",
      flush=True)

# --------------------------------------------------------------- merge -----
# Identity links: only entities whose slug both stores minted, via a shared
# seed namespace. This is the realistic case — partial linkage, not total.
ents = {c.subject for c in A} | {c.object for c in A if c.object_sort == "entity"}
edges = []
for e in sorted(ents):
    s = e.split(":", 1)[1]
    edges.append((e, f"{SEED_NS}:{s}", "agent:linker"))
    edges.append((f"{NS_B}:{s}", f"{SEED_NS}:{s}", "agent:linker"))
cl = Closure(Policy(max_class_size=64))
cl.accept_all(edges)
print(f"closure: {len(edges)} sameAs offered, "
      f"{len(cl.rejected)} rejected", flush=True)

merged = A + B
ag = agreement(merged, cl)
sizes = collections.Counter(len(v) for v in ag.values())

# Two different questions, and conflating them is what the first run of this
# harness got wrong. DEDUP asks whether both stores' claims land on one
# proposition. AGREEMENT asks how many independent EVIDENCE sources back it.
# Here both stores extracted the same Wikipedia page, so agreement of 1 is the
# correct answer and a naive "pooled" count reads it as total failure.
stores = collections.defaultdict(set)
for c in merged:
    stores[proposition_key(c, cl)].add(c.subject.split(":", 1)[0])
cross = sum(1 for v in stores.values() if len(v) > 1)
pooled = sum(n for k, n in sizes.items() if k > 1)

# ---- the measurement that matters: conflicts between known-agreeing claims --
by_key = collections.defaultdict(list)
for c in merged:
    by_key[proposition_key(c, cl)].append(c)
found = conflicts(merged, cl, frozenset())
false_pos = [c for c in found
             if c.left.subject.split(":", 1)[1] == c.right.subject.split(":", 1)[1]
             and c.left.predicate == c.right.predicate]

n_time = sum(1 for c in A if c.object_sort == "time")
print(f"\nclaims in:    {len(merged)}   ->  propositions: {len(ag)}")
print(f"time claims:  {n_time} per store (all year-precision in this corpus)")
print(f"DEDUP:        {100 * cross / max(len(ag), 1):.1f}% of propositions "
      f"carry BOTH stores ({cross}/{len(ag)})")
print(f"AGREEMENT:    {pooled} propositions have >1 independent source "
      f"(both stores read the same page, so 1 is correct here)")
print(f"conflicts:    {len(found)}   FALSE POSITIVES: {len(false_pos)}")
if false_pos:
    print("  example false positive:", false_pos[0])
for k, n in sorted(collections.Counter(m["kind"] for m in mines).items()):
    print(f"  landmine {k:>18}: {n}")

LAND.parent.mkdir(exist_ok=True)
with LAND.open("a") as f:
    for m in mines[:2000]:
        f.write(json.dumps(m) + "\n")

out = {"n_rows": len(wiki), "converted_per_store": converted,
       "precision_drift": DRIFT,
       "landmines": dict(collections.Counter(m["kind"] for m in mines)),
       "claims_in": len(A) + len(B), "propositions": len(ag),
       "cross_store_propositions": cross,
       "dedup_pct": round(100 * cross / max(len(ag), 1), 2),
       "multi_source_propositions": pooled,
       "agreement_hist": dict(sorted(sizes.items())),
       "conflicts": len(found),
       "false_positive_conflicts": len(false_pos),
       "sort_mix": dict(collections.Counter(c.object_sort for c in A)),
       "scope": ("Both synthetic stores are built from ONE corpus, so any two "
                 "claims descending from the same row are known to agree; a "
                 "reported conflict between them is a measured false positive, "
                 "not an argued one. Landmines append to results/landmines.jsonl "
                 "so the messy-case corpus grows monotonically.")}
(ROOT / "results" / "exp66_federation.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp66_federation.json  +  results/landmines.jsonl")
