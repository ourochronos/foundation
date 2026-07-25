"""M1 baseline: encode seed propositions, measure isotropy raw vs whitened,
run the anchor-spanning probe. Produces results/baseline_v0.json + artifacts.

Usage: .venv/bin/python scripts/baseline_isotropy.py [--cpu]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec import data as D          # noqa: E402
from codec import whiten as W        # noqa: E402
from codec.encode import M3Encoder, sparse_stats  # noqa: E402
from codec.evals.anchors import spanning_report   # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--anchors", type=int, nargs="*", default=[64, 256, 1024])
    args = ap.parse_args()

    props, stats = D.load_dir(ROOT / "data" / "propositions")
    if len(props) < 200:
        sys.exit(f"only {len(props)} propositions found — wait for generators")
    print(f"[data] {stats['kept']} kept / {stats['lines']} lines "
          f"({stats['dupes']} dupes, {stats['parse_errors']} parse errors, "
          f"{stats['dropped_labels']} labels dropped) {stats['by_domain']}")
    D.save_jsonl(props, ROOT / "data" / "clean_v0.jsonl")

    train, evals = D.split(props, eval_frac=0.1)
    print(f"[split] train={len(train)} eval={len(evals)}")

    enc = M3Encoder(device="cpu" if args.cpu else None)
    texts = [p.text for p in props]
    dense, lex = enc.encode(texts)
    print(f"[encode] dense {dense.shape} on {enc.device}")
    np.save(ROOT / "results" / "dense_v0.npy", dense)
    sp = sparse_stats(lex)
    print(f"[sparse] {sp}")

    train_keys = {p.text for p in train}
    is_train = np.array([t in train_keys for t in texts])
    X_train, X_eval = dense[is_train], dense[~is_train]

    iso_raw = W.isotropy_report(dense)
    whitener = W.fit(X_train)
    W.save(whitener, str(ROOT / "results" / "whiten_v0.npz"))
    dense_w = W.apply(dense, whitener)
    iso_white = W.isotropy_report(dense_w)
    for name, iso in [("raw", iso_raw), ("whitened", iso_white)]:
        print(f"[isotropy/{name}] mean|cos|={iso['mean_abs_cos']:.4f} "
              f"eff_rank={iso['effective_rank']:.1f}/{iso['dim']} "
              f"top1_share={iso['top1_eig_share']:.4f}")
    if whitener["underdetermined"]:
        print(f"[warn] whitener fit on n={whitener['n_fit']} < 4*d — "
              "treat whitened metrics as provisional until the corpus grows")

    Xw_train, Xw_eval = dense_w[is_train], dense_w[~is_train]
    rows = spanning_report(Xw_train, Xw_eval, args.anchors)
    for r in rows:
        if "skipped" in r:
            print(f"[anchors n={r['n_anchors']}] skipped: {r['skipped']}")
        else:
            print(f"[anchors n={r['n_anchors']}] nearest_cos mean/median/p10 = "
                  f"{r['nearest_cos_mean']:.3f}/{r['nearest_cos_median']:.3f}/{r['nearest_cos_p10']:.3f}  "
                  f"phase_bound(top8) = {r['phase_bound_mean']:.3f}/{r['phase_bound_median']:.3f}/{r['phase_bound_p10']:.3f}")

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": stats, "n_train": len(train), "n_eval": len(evals),
        "sparse": sp, "isotropy_raw": iso_raw, "isotropy_whitened": iso_white,
        "whitener_underdetermined": bool(whitener["underdetermined"]),
        "anchor_spanning_whitened": rows,
    }
    (ROOT / "results" / "baseline_v0.json").write_text(json.dumps(out, indent=2))
    print(f"[done] results/baseline_v0.json")


if __name__ == "__main__":
    main()
