"""End-to-end smoke test for the assembled structure channel.

Every other structure probe reads cached embeddings, so nothing else exercises
`StructureChannel`'s public API from raw text: encode -> whiten -> tokens ->
pair_scores. This does, on sentences that appear in no dataset, and checks the
division of labour holds — each mechanism should fire on the case it owns and
stay quiet elsewhere:

    cleft rewrite   preserving  -> all three high
    role swap       changing    -> ROLE BITS fire (continuous channels can't
                                   see it; the pair is bag-of-words identical)
    negation        changing    -> AMP fires (valence steering direction)

Also reported, deliberately NOT asserted: a bare literal substitution
("Tuesday" -> "Saturday"). That is an IDENTITY edit, and D3 routes identities
to the symbolic identity channel, not here — the structure channel is not the
instrument for it and scores it ~0.92. It stays in the output because it is
the clearest demonstration of why the codec-level comparison needs to be
`min(struct_sim, identity_sim)` (D20 caveat, queue item 3): the pooler catches
substantial date substitutions in the pair corpus (date_shift s_cos 0.71) but
cannot be relied on for a single-token swap.

Needs the GPU and the shipping checkpoints. Exits non-zero on any violation.

Usage: .venv/bin/python scripts/check_structure_channel.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec import whiten as W                       # noqa: E402
from codec.structure_channel import StructureChannel  # noqa: E402

BASE = "Harrow Freight moved 3,100 pallets to the Denver hub on Tuesday."

# (label, y, expected class, which mechanism must be the one that fires)
CASES = [
    ("cleft", "It was Harrow Freight that moved 3,100 pallets to the Denver "
              "hub on Tuesday.", "preserve", None),
    ("passive", "3,100 pallets were moved by Harrow Freight to the Denver hub "
                "on Tuesday.", "preserve", None),
    ("role swap", "The Denver hub moved 3,100 pallets to Harrow Freight on "
                  "Tuesday.", "change", "role_sim"),
    ("negation", "Harrow Freight did not move 3,100 pallets to the Denver hub "
                 "on Tuesday.", "change", "amp_cos"),
]

# identity edits — the symbolic identity channel's job (D3), reported only
DELEGATED = [
    ("date swap", "Harrow Freight moved 3,100 pallets to the Denver hub on "
                  "Saturday."),
    ("quantity", "Harrow Freight moved 6,200 pallets to the Denver hub on "
                 "Tuesday."),
]

PRESERVE_FLOOR = 0.70    # a preserving rewrite must stay clearly high
CHANGE_CEILING = 0.70    # a changing rewrite must be pushed clearly down


def main() -> None:
    from codec.encode import M3Encoder

    ch = StructureChannel.load(ROOT)
    print(f"[config] amp P{ch.P.shape} gain {ch.gamma} | device {ch.device}")
    enc = M3Encoder()
    whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))

    xs = [BASE] * (len(CASES) + len(DELEGATED))
    ys = [c[1] for c in CASES] + [d[1] for d in DELEGATED]

    def z(texts):
        d, _ = enc.encode(texts, sparse=False)
        Z = W.apply(d, whitener)
        return Z / (np.linalg.norm(Z, axis=1, keepdims=True) + 1e-12)

    Tx, Mx = ch.tokens(xs, enc)
    Ty, My = ch.tokens(ys, enc)
    sc = ch.pair_scores(xs, ys, z(xs), z(ys), Tx, Mx, Ty, My)

    print(f"\n{'case':>12} {'class':>9} {'role':>6} {'s':>6} {'amp':>7} "
          f"{'combined':>9}  check")
    failures = []
    for i, (label, _, cls, mech) in enumerate(CASES):
        r, s, a = (float(sc["role_sim"][i]), float(sc["s_cos"][i]),
                   float(sc["amp_cos"][i]))
        comb = float(sc["combined"][i])
        notes = []
        if cls == "preserve" and comb < PRESERVE_FLOOR:
            notes.append(f"combined {comb:.2f} < floor {PRESERVE_FLOOR}")
        if cls == "change":
            if comb > CHANGE_CEILING:
                notes.append(f"combined {comb:.2f} > ceiling {CHANGE_CEILING}")
            # the named mechanism must be the one doing the work
            if mech and {"role_sim": r, "s_cos": s, "amp_cos": a}[mech] > CHANGE_CEILING:
                notes.append(f"{mech} did not fire")
        print(f"{label:>12} {cls:>9} {r:>6.2f} {s:>6.2f} {a:>7.2f} {comb:>9.2f}"
              f"  {'ok' if not notes else 'FAIL'}")
        if notes:
            failures.append((label, notes))

    for j, (label, _) in enumerate(DELEGATED, start=len(CASES)):
        print(f"{label:>12} {'identity':>9} {sc['role_sim'][j]:>6.2f} "
              f"{sc['s_cos'][j]:>6.2f} {sc['amp_cos'][j]:>7.2f} "
              f"{sc['combined'][j]:>9.2f}  n/a (identity channel, D3)")

    if failures:
        print(f"\n{len(failures)} FAILURE(S):")
        for label, notes in failures:
            print(f"  {label}: {'; '.join(notes)}")
        raise SystemExit(1)
    print("\n[ok] preserving rewrites stay high; each changing rewrite is "
          "caught by the mechanism that owns it. Identity edits sit high here "
          "BY DESIGN — they need min(struct_sim, identity_sim) at codec level.")


if __name__ == "__main__":
    main()
