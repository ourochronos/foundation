"""Aggregate the two adjudication passes into a quorum table (D152).

Reads every stored verdict artifact, **checks each one still refers to the
claims it was written about**, and only then aggregates. That check is the
point: verdicts key on index, and when the claim list changed length every
stored verdict silently re-pointed to a different claim while remaining
perfectly parseable. Twice now a published conclusion has come from an
artifact that had quietly stopped meaning what it said (D150, D152), so
alignment is verified in code before any number is computed.

Aggregation follows what the earlier rounds established about the raters:

  * **Per-rater majority of 3 before quorum.** D150 measured a single rater
    flagging between 1 and 6 of the same 11 claims across identical runs. One
    adversarial run is a sample, not a verdict, so each rater votes with its
    own majority and a 1-1-1 disagreement is reported as SPLIT rather than
    silently resolved — rater instability is a result here, not noise to
    average away.
  * **The author's own family is excluded from quorum.** Claude judging
    claims written by Claude is not an independent rater; it is reported
    alongside, which is how the family effect stays visible.
  * **Both prompts, never merged.** Verification asks "is this supported?"
    and rewards hedging; attack asks "could this be wrong at all?" and
    punishes it. A claim that passes verification and fails attack is not
    contradictory — it is a claim that is true and empty, which is exactly
    what the pair of prompts exists to separate.

Usage: .venv/bin/python scripts/adjud_quorum.py
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from claimset import check_alignment, load_claims                 # noqa: E402

ADJ = ROOT / "data" / "adjudication"
RATERS = ["gpt-5.6-sol", "gemini-3.1-pro-preview", "grok-4.5", "claude-fable-5"]
AUTHOR_FAMILY = {"claude-fable-5"}          # excluded from quorum, reported
RUNS = ["1", "2", "3"]
FLAG = {"REFUTABLE", "UNFALSIFIABLE"}       # anything that is not SURVIVES
CLAIMS = load_claims()
N = len(CLAIMS)


def _fn(model: str) -> str:
    return model.replace(".", "_").replace("/", "_")


def load(name: str) -> tuple[dict | None, list[str]]:
    p = ADJ / f"{name}.json"
    if not p.exists():
        return None, [f"{p.name}: missing"]
    art = json.loads(p.read_text())
    bad = check_alignment(art, CLAIMS)
    return art, [f"{p.name}: {b}" for b in bad]


def verdicts(art: dict) -> dict[int, str]:
    return {int(k): v["verdict"] for k, v in art["their_verdicts"].items()}


def reasons(art: dict) -> dict[int, str]:
    return {int(k): v.get("reason", "") for k, v in art["their_verdicts"].items()}


# ---- load everything, refusing anything whose indices moved ---------------
problems, attack, verify = [], {}, {}
for m in RATERS:
    for r in RUNS:
        art, bad = load(f"attack_r{r}_{_fn(m)}")
        problems += bad
        if art and not bad:
            attack[(m, r)] = art
    art, bad = load(f"claims_{_fn(m)}")
    problems += bad
    if art and not bad:
        verify[m] = art

print(f"{N} claims in the current block ({ADJ.parent.parent.name}/docs/18)")
print(f"usable: {len(attack)}/{len(RATERS) * len(RUNS)} attack runs, "
      f"{len(verify)}/{len(RATERS)} verification runs")
if problems:
    print("\nEXCLUDED — these artifacts no longer refer to the current claims:")
    for p in problems[:12]:
        print(f"  {p}")
    if len(problems) > 12:
        print(f"  ... and {len(problems) - 12} more")
if not attack:
    raise SystemExit("\nno usable attack runs; re-run scripts/adjudicate.py")

# ---- per-rater majority over its 3 runs -----------------------------------
# A rater votes only with a FULL set of runs. The first version of this took
# whatever runs existed and used `count > 1` as the majority rule, so with one
# run per rater every claim came back SPLIT, SPLIT is not a flag, and zero
# flags printed as SURVIVES — a clean bill of health computed from a third of
# the data. Absent evidence must never read as passing evidence.
maj, stability, partial = {}, {}, {}
for m in RATERS:
    runs = [attack[(m, r)] for r in RUNS if (m, r) in attack]
    if not runs:
        continue
    vs = [verdicts(a) for a in runs]
    per_claim, agree = {}, collections.Counter()
    for i in range(N):
        got = [v.get(i, "ABSENT") for v in vs]
        c = collections.Counter(got).most_common()
        per_claim[i] = c[0][0] if c[0][1] * 2 > len(got) else "SPLIT"
        agree["unanimous" if c[0][1] == len(got) else
              ("majority" if c[0][1] * 2 > len(got) else "split")] += 1
    if len(runs) < len(RUNS):
        partial[m] = len(runs)          # reported, but does not vote
    else:
        maj[m] = per_claim
    flags = [sum(1 for i in range(N) if v.get(i) in FLAG) for v in vs]
    stability[m] = {"n_runs": len(runs), "flags_per_run": flags,
                    "range": max(flags) - min(flags), "votes": m in maj,
                    **agree}

print(f"\n{'rater':26s} {'runs':>4} {'flags/run':>14} {'range':>5} "
      f"{'unanim':>7} {'2-1':>5} {'split':>6}")
for m in RATERS:
    s = stability.get(m)
    if not s:
        continue
    tag = "  (author family)" if m in AUTHOR_FAMILY else ""
    if not s["votes"]:
        tag += f"  INCOMPLETE {s['n_runs']}/{len(RUNS)} runs — does not vote"
    print(f"{m:26s} {s['n_runs']:4d} {str(s['flags_per_run']):>14} "
          f"{s['range']:5d} {s.get('unanimous', 0):7d} "
          f"{s.get('majority', 0):5d} {s.get('split', 0):6d}{tag}")

# ---- quorum over independent raters ---------------------------------------
QRATERS = [m for m in RATERS if m in maj and m not in AUTHOR_FAMILY]
COMPLETE = len(QRATERS) >= 2
if not COMPLETE:
    print(f"\n*** INCOMPLETE: {len(QRATERS)} independent rater(s) with a full "
          f"{len(RUNS)}-run set; a quorum needs at least 2. The table below "
          f"is a partial view and is NOT written to results/. ***")
print(f"\nquorum over {len(QRATERS)} independent raters "
      f"(excluded: {', '.join(sorted(AUTHOR_FAMILY & set(maj))) or 'none'})")
print(f"\n{'#':>2} {'flags':>5} {'quorum':>13} {'author':>13}  claim")
table = []
for i in range(N):
    per = {m: maj[m][i] for m in QRATERS}
    nflag = sum(1 for v in per.values() if v in FLAG)
    nsplit = sum(1 for v in per.values() if v == "SPLIT")
    # a claim on which raters could not reproduce their own verdicts is not
    # a claim that survived; it is one with no verdict
    q = ("NO VERDICT" if not QRATERS or nsplit * 2 >= len(QRATERS) else
         "FLAGGED" if nflag * 2 > len(QRATERS) else
         "SPLIT" if nflag * 2 == len(QRATERS) else "SURVIVES")
    auth = {m: maj[m][i] for m in maj if m in AUTHOR_FAMILY}
    av = next(iter(auth.values()), "-")
    table.append({"idx": i, "claim": CLAIMS[i]["claim"],
                  "per_rater": per, "n_flagging": nflag, "quorum": q,
                  "author_family": av})
    print(f"{i:2d} {nflag:2d}/{len(QRATERS):<2d} {q:>13} {av:>13}  "
          f"{CLAIMS[i]['claim'][:64]}")

# ---- verification pass, reported separately, never merged -----------------
vsupp = {}
if verify:
    print(f"\nverification pass (\"is this supported?\"), 1 run per rater")
    for m, art in verify.items():
        v = verdicts(art)
        bad = [i for i in range(N) if v.get(i) not in ("SUPPORTED", None)]
        vsupp[m] = {"n": len(v), "not_supported": bad}
        print(f"  {m:26s} {len(v) - len(bad)}/{len(v)} SUPPORTED"
              + (f"   flagged: {bad}" if bad else ""))
    allbad = collections.Counter(i for d in vsupp.values()
                                 for i in d["not_supported"])
    vq = sorted(i for i, c in allbad.items() if c * 2 > len(vsupp))
    print(f"  quorum not-supported: {vq if vq else 'none'}")

# ---- the falsifiers, for claims the quorum flagged ------------------------
flagged = [t for t in table if t["quorum"] == "FLAGGED"]
print(f"\n{len(flagged)} of {N} claims flagged by quorum under attack"
      if COMPLETE else
      f"\nno quorum: {N} claims have NO VERDICT until the batch finishes")
named = {}
for t in flagged:
    rs = []
    for m in QRATERS:
        for r in RUNS:
            a = attack.get((m, r))
            if a and verdicts(a).get(t["idx"]) in FLAG:
                rs.append({"rater": m, "run": r,
                           "verdict": verdicts(a)[t["idx"]],
                           "falsifier": reasons(a)[t["idx"]]})
    named[t["idx"]] = rs
    print(f"\n[{t['idx']}] {t['claim'][:100]}")
    print(f"    quorum {t['n_flagging']}/{len(QRATERS)}  "
          f"per-rater {t['per_rater']}")
    for x in rs[:3]:
        print(f"    - {x['rater']} r{x['run']} {x['verdict']}: "
              f"{x['falsifier'][:150]}")

out = {
    "n_claims": N,
    "claims": [c["claim"] for c in CLAIMS],
    "excluded_artifacts": problems,
    "raters": RATERS, "quorum_raters": QRATERS,
    "author_family_excluded": sorted(AUTHOR_FAMILY),
    "stability": stability,
    "attack_table": table,
    "verification": vsupp,
    "flagged": [t["idx"] for t in flagged],
    "falsifiers": named,
    "scope": ("Per-rater majority of 3 adversarial runs, then quorum over "
              "raters outside the author's model family. SPLIT means a rater "
              "returned three different verdicts on identical input and is "
              "reported, not resolved. The verification pass is listed "
              "separately and never merged with attack: the two prompts "
              "reward opposite behaviours, so a claim passing one and failing "
              "the other is a finding about the claim, not rater noise. "
              "Every artifact was checked against the current claim text "
              "before use; misaligned ones are listed in "
              "`excluded_artifacts` and contribute nothing."),
}
if COMPLETE:
    (ROOT / "results" / "adjud_quorum.json").write_text(
        json.dumps(out, indent=1))
    print("\n[done] results/adjud_quorum.json")
else:
    print("\n[not written] incomplete run — finish the batch, then re-run")
