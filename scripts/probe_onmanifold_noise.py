"""A3 — On-manifold error model (07-phase3-plan.md; adversary threat #6).

D24/D27 measured robustness to ISOTROPIC noise — but in 1024-d whitened
space a random direction is near-orthogonal to the data manifold and barely
moves cosine rank order. A reasoner's real errors are ON-manifold: the
predicted query latent drifts toward a CONFUSABLE fact (same relation,
different entity). This sweep interpolates query latents toward confusables
at matched latent-cos levels and re-measures retrieval, gist-only vs
+identity rescoring.

Pre-registered expectations (from the plan): gist P@1 degrades sharply where
isotropic noise cost ~nothing, and identity rescoring FINALLY activates —
strengthening the architecture story while killing the "invariance" framing.

Usage: .venv/bin/python scripts/probe_onmanifold_noise.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec.memory_store import MemoryStore, id_tokens   # noqa: E402
from codec.role_bits import _nlp                        # noqa: E402


def unit(X):
    return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)


def slerp_to(z, target, cos_goal):
    """Interpolate z toward target until cos(result, z) ~= cos_goal."""
    lo, hi = 0.0, 1.0
    for _ in range(30):
        t = (lo + hi) / 2
        m = unit((1 - t) * z + t * target)
        if float(m @ z) > cos_goal:
            lo = t
        else:
            hi = t
    return unit((1 - lo) * z + lo * target)


def main() -> None:
    world = json.loads((ROOT / "data" / "closed_world_v1.json").read_text())
    facts, queries = world["facts"], world["queries"]
    z = np.load(ROOT / "results" / "closed_world_v1_emb.npz")
    Zf, Zq = z["Zf"], z["Zq"]
    nlp = _nlp()

    store = MemoryStore()
    for f, zf in zip(facts, Zf):
        store.add(zf, f["entities"] + f["numbers"], f["text"])

    by_rel = {}
    for i, f in enumerate(facts):
        by_rel.setdefault(f["relation"], []).append(i)

    para = [i for i, q in enumerate(queries) if q["kind"] == "paraphrase"][:400]
    qids = {i: id_tokens([t.text.rstrip("'s") if t.text.endswith("'s") else t.text
                          for t in nlp(queries[i]["text"]) if t.pos_ == "PROPN"]
                         + [t.text for t in nlp(queries[i]["text"]) if t.like_num])
            for i in para}

    rng = np.random.default_rng(0)
    rows = []
    for cos_goal in (1.0, 0.9, 0.8, 0.7, 0.55):
        hit_g = hit_id = 0
        for i in para:
            zq = Zq[i]
            if cos_goal < 1.0:
                # confusable: same-relation fact about a DIFFERENT entity
                pool = by_rel[queries[i]["relation"]]
                j = pool[rng.integers(len(pool))]
                while j == queries[i]["fact_idx"]:
                    j = pool[rng.integers(len(pool))]
                zq = slerp_to(zq, Zf[j], cos_goal)
            rg = store.query(zq, None, k=1, id_weight=0.0)[0]
            ri = store.query(zq, qids[i], k=1, id_weight=0.5)[0]
            hit_g += rg[0] == queries[i]["fact_idx"]
            hit_id += ri[0] == queries[i]["fact_idx"]
        g, gi = hit_g / len(para), hit_id / len(para)
        rows.append({"cos": cos_goal, "gist": g, "with_identity": gi,
                     "delta": gi - g})
        print(f"[on-manifold cos={cos_goal:.2f}] gist={g:.3f} "
              f"+identity={gi:.3f} (Δ={gi - g:+.3f})")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "n": len(para), "rows": rows,
           "isotropic_reference": "hop_v1.json noisy_paraphrase: gist flat to "
                                  "cos 0.55 (0.763->0.732), delta <= +0.010"}
    (ROOT / "results" / "onmanifold_noise_a3.json").write_text(json.dumps(out, indent=2))
    print("[done] results/onmanifold_noise_a3.json")


if __name__ == "__main__":
    main()
