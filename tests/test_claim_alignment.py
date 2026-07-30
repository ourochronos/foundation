"""Stored verdicts must still refer to the claims they judged (D151, D152).

Twice a published conclusion came from an artifact that had quietly stopped
meaning what it said. D150: the claims lived in two places — `docs/18` and
`adjudicate.py` — and drifted, so an adjudication was reported for text that
was never adjudicated. D152: the claims moved to one place, but verdicts key
on **index**, and when the list shortened from 11 to 10 every stored verdict
re-pointed to a different claim. Both failures were silent. The JSON parsed,
the indices resolved, and the reasons read as plausible prose about
*something* — the only symptom was a falsifier about derived thresholds
surfacing under a claim about composition.

Neither is the kind of thing a person catches by looking. So the invariant is
checked here instead: every artifact in `data/adjudication/` that judges the
claim block must carry `judged_claims`, and every stamp must match the claim
now at that index. When a claim is edited, these fail, and the fix is to
re-adjudicate — which is the correct response, not an inconvenience.

Superseded artifacts live in `data/adjudication/superseded_*/` and are
skipped: they are kept deliberately, for aggregate counts that never depended
on which claim was which.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from claimset import DOC, check_alignment, load_claims        # noqa: E402

ADJ = ROOT / "data" / "adjudication"
# only these prefixes judge the claim block; the rest audit extractions
CLAIM_AUDITS = ("claims_", "attack_")


def _artifacts() -> list[Path]:
    return sorted(p for p in ADJ.glob("*.json")
                  if p.name.startswith(CLAIM_AUDITS))


def test_absent_adjudication_is_recorded_rather_than_implied():
    """No current adjudication is a fine state; a SILENT one is not.

    When every artifact is archived, the parametrized test above has nothing
    to run and the suite goes green — "no adjudication" and "adjudication all
    valid" become indistinguishable at a glance. That is the shape of failure
    this whole file exists for: D150, D152 and D153 were each a case of
    absence reading as confirmation, and D154's aggregator reported SURVIVES
    on a third of the data for the same reason.

    So the invariant is: either current artifacts exist, or the archive the
    claims were retired into says why. A README is a weak guarantee, but it
    forces the person emptying the directory to write down what is owed.
    """
    if _artifacts():
        return
    archives = sorted(p for p in ADJ.glob("superseded_*") if p.is_dir())
    assert archives, (
        f"{ADJ.relative_to(ROOT)} holds no claim adjudication and no "
        f"superseded_* archive explaining its absence. The claims are "
        f"currently unjudged and nothing says so.")
    assert (archives[-1] / "README.md").exists(), (
        f"{archives[-1].name} has no README. When an adjudication is retired "
        f"the archive must record what it established and what is owed, or "
        f"the empty directory reads as though nothing was ever needed.")


def test_every_claim_supplies_parseable_evidence():
    """What the adjudicator receives must resolve, and must be valid JSON.

    `_nums` used to end in `[:2600]`, which cut large `results` blocks
    mid-structure — the rater got JSON that stopped in the middle of a number
    and no way to know it was incomplete, then judged the claim anyway. D92
    measured the cost of exactly that: truncation manufactured 6 of 8
    disagreements on arxiv50. Nothing caught it because nothing had ever
    parsed the evidence the way the rater has to.

    So this parses every claim's evidence block the way a reader would, and
    fails on a key that silently resolves to nothing — a citation that looks
    present in `docs/18` and arrives empty is the quietest way to send an
    adjudicator into a claim blind.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_adj", ROOT / "scripts" / "adjudicate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.argv = ["adjudicate.py", "__probe__"]
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass                      # module runs a CLI; the probe arg exits it

    for c in load_claims():
        cited = [tuple(c["src"])] + [tuple(x) for x in c.get("extra", [])]
        for path, keys in cited:
            blob = mod._nums(path, keys)
            body = blob.split("\n\n[")[0]        # strip the omitted-keys note
            try:
                got = json.loads(body)
            except json.JSONDecodeError as e:
                raise AssertionError(
                    f"row {c['row']}: evidence from {path} is not valid JSON "
                    f"({e}). The adjudicator would receive this verbatim.")
            missing = [k for k in keys if k not in got]
            if missing:
                assert "omitted for length" in blob, (
                    f"row {c['row']}: keys {missing} cited from {path} "
                    f"resolve to nothing — the claim would be judged without "
                    f"the evidence it names.")


def test_claims_block_parses():
    claims = load_claims()
    assert claims, f"{DOC.name} has an empty claims block"
    for i, c in enumerate(claims):
        for k in ("claim", "scope", "src"):
            assert c.get(k), f"claim {i} is missing {k!r}"
        path = ROOT / c["src"][0]
        assert path.exists(), f"claim {i} cites a missing file: {c['src'][0]}"
        for xp, _ in c.get("extra", []):
            assert (ROOT / xp).exists(), f"claim {i} extra missing: {xp}"


@pytest.mark.parametrize("p", _artifacts(), ids=lambda p: p.stem)
def test_stored_verdicts_still_refer_to_current_claims(p: Path):
    art = json.loads(p.read_text())
    bad = check_alignment(art, load_claims())
    assert not bad, (
        f"{p.name} no longer refers to the current claim block:\n  "
        + "\n  ".join(bad)
        + "\n\nThe claims changed after this was judged. Its indices now point "
          "at different claims, so its verdicts cannot be attributed. Re-run "
          "`scripts/adjudicate.py`, or move it to data/adjudication/"
          "superseded_n<N>/ if it is being kept for aggregate counts only."
    )


def prose_rows() -> list[tuple[str, str]]:
    """(row id, claim text) for every row of the claims table in `docs/18`."""
    out = []
    for ln in DOC.read_text().splitlines():
        if not ln.startswith("| "):
            continue
        cells = [c.strip() for c in ln.split("|")[1:-1]]
        if len(cells) < 2 or cells[0] in ("#",) or set(cells[0]) <= set("-"):
            continue
        out.append((cells[0], cells[1]))
    return out


def test_every_prose_row_is_adjudicated_or_says_it_is_not():
    """The paper's table and the adjudicated block must describe one set.

    The first version of this test compared *counts* — and passed, on a table
    of 14 rows against a block of 10 claims, because the row filter dropped
    the lettered rows (1b, 1c, 1d, 5b) and 10 happened to equal 10. A count is
    not a correspondence; two lists of the same length can share nothing. That
    is the D147 failure (a stated conclusion sitting above a check that does
    not test it) reproduced inside the test written to prevent it, which is
    why the check is now a bijection over declared row ids.

    Each claim in the JSON block carries `row`, naming the prose row it
    renders. A prose row with no claim behind it must be marked `*`, meaning
    "in the paper, never adjudicated" — an honest state, and one a reader can
    see. What is not allowed is an unmarked row that no adjudicator ever
    judged, because `docs/18` tells the reader the table is a rendering of
    the adjudicated block.
    """
    claims = load_claims()
    rows = prose_rows()
    assert rows, f"{DOC.name}: no claims table rows found"

    declared = {}
    for i, c in enumerate(claims):
        assert "row" in c, (
            f"claim {i} has no `row` field naming its prose table row; "
            f"without it the table and the block cannot be checked against "
            f"each other, only counted (D153)."
        )
        for r in ([c["row"]] if isinstance(c["row"], str) else c["row"]):
            assert r not in declared, (
                f"prose row {r!r} is claimed by both claim {declared[r]} and "
                f"claim {i}")
            declared[r] = i

    ids = [rid.rstrip("*") for rid, _ in rows]
    assert len(ids) == len(set(ids)), f"{DOC.name}: duplicate row ids in table"

    unmarked_missing = [rid for rid, _ in rows
                        if not rid.endswith("*") and rid not in declared]
    assert not unmarked_missing, (
        f"{DOC.name}: rows {unmarked_missing} appear in the paper's claims "
        f"table but in no adjudicated claim. Either add them to the "
        f"machine-readable block and re-adjudicate, or mark them `*` to say "
        f"plainly that they are unadjudicated (D153)."
    )

    dangling = sorted(set(declared) - set(ids))
    assert not dangling, (
        f"{DOC.name}: claims reference prose rows {dangling}, which the table "
        f"does not contain — the block has drifted ahead of the table.")
