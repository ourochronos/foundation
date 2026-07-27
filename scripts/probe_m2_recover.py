"""M2 / G3 — individuation recoverability from content geometry (docs/07 R2).

REGISTERED TARGETS (07-phase3-plan, unchanged): pairwise-F1 >= 0.80 vs the
registry partition AND beat the surface-only baseline by >= 15 points;
below either => identity needs the symbolic scaffold (also a finding,
criterion-scored).

PROTOCOL (pre-registered here, committed BEFORE the scoring run — D64):
- World: w41+w43 union ingested through the closed-form registry (the
  probe_individuation_j4 head, unchanged). Registry partition = live eids.
- Mention = (fact, slot): every subject occurrence + every entity-object
  occurrence of a surface form; mention vector = that fact's gist (BGE-M3,
  cached). "Fact-anchor clusters" per Entity.anchor = means of fact gists,
  so clustering mention gists IS the registered instrument.
- Scope: COLLIDED forms only (>= 2 live eids) — the registered text says
  "for same-name entities"; on unique forms the surface baseline is
  perfect by construction and the +15 clause would be unsatisfiable.
  Single-eid forms are kept as a non-gating over-split control.
- PRIMARY variant (gates): per-form CENTERED gists — subtract the form's
  mention mean, L2-normalize, agglomerative AVERAGE linkage on euclidean
  distance (= monotone in cosine), cut at tau. Centering removes the
  shared name+type component that D9/D21 measured as dominant; raw-gist
  clustering is registered as a SECONDARY precisely to show that confound,
  not to gate. Choosing the primary at registration time, before any
  number is computed, is the D64-sanctioned moment for this call.
- tau selection: forms split CALIB/EVAL by md5(form) parity; tau* =
  argmax micro pairwise-F1 on CALIB collided forms (sweep 0.05..1.40 step
  0.05); frozen; gate scored on EVAL collided forms only.
- Metric: micro pairwise P/R/F1 over same-form mention pairs (tp = pred
  same & registry same). Surface baseline: ALL same-form pairs predicted
  same. Wilson CIs on P and R pair counts (pairs are not independent —
  CIs are nominal, per house style).
- Secondaries (non-gating): raw-gist variant, complete/single linkage,
  over-split rate on single-eid control forms at tau*, registry-vs-batch
  agreement on cross-batch pairs (registry quality context).

Usage: .venv/bin/python scripts/probe_m2_recover.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

_src = (ROOT / "scripts" / "probe_individuation_j4.py").read_text()
_head = _src.split("# ---- store + eid-based artifacts")[0].replace(
    'ROOT = Path(__file__).resolve().parent.parent', f'ROOT = Path("{ROOT}")')
exec(_head)  # noqa: S102 — reg, facts_u, Zf_u, subj_eid, obj_eid, n1, is_value

from codec.manifest import run_manifest, wilson_ci  # noqa: E402

live = {e: reg._get(e).eid for e in reg.entities}

# ---- mention table ---------------------------------------------------------
mentions = defaultdict(list)          # form -> [(vec_idx, live_eid, batch)]
for fi, f in enumerate(facts_u):
    b = "w41" if fi < n1 else "w43"
    mentions[f["subject"]].append((fi, live[subj_eid[fi]], b))
    if obj_eid[fi] is not None:
        mentions[f["object"]].append((fi, live[obj_eid[fi]], b))

collided, single = {}, {}
for form, ms in mentions.items():
    if len(ms) < 2:
        continue
    (collided if len({e for _, e, _ in ms}) > 1 else single)[form] = ms

def split_of(form: str) -> str:
    return "calib" if int(hashlib.md5(form.encode()).hexdigest(), 16) % 2 \
        else "eval"

CAL = {f: m for f, m in collided.items() if split_of(f) == "calib"}
EVA = {f: m for f, m in collided.items() if split_of(f) == "eval"}
print(f"[m2] forms: collided={len(collided)} (calib={len(CAL)} "
      f"eval={len(EVA)}) single-eid controls={len(single)}; "
      f"mentions total={sum(len(m) for m in mentions.values())}", flush=True)

Z = Zf_u / (np.linalg.norm(Zf_u, axis=1, keepdims=True) + 1e-12)


def vectors(ms, centered: bool) -> np.ndarray:
    V = Z[[fi for fi, _, _ in ms]].astype(np.float64)
    if centered:
        V = V - V.mean(0, keepdims=True)
        V /= (np.linalg.norm(V, axis=1, keepdims=True) + 1e-12)
    return V


def cluster(V: np.ndarray, tau: float, linkage: str) -> np.ndarray:
    """Tiny agglomerative on euclidean distance; merges while the linkage
    distance of the closest pair of clusters is <= tau."""
    n = len(V)
    D = np.linalg.norm(V[:, None] - V[None, :], axis=2)
    groups = [[i] for i in range(n)]
    while len(groups) > 1:
        best, bi, bj = None, -1, -1
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                block = D[np.ix_(groups[i], groups[j])]
                d = {"average": block.mean, "complete": block.max,
                     "single": block.min}[linkage]()
                if best is None or d < best:
                    best, bi, bj = d, i, j
        if best is None or best > tau:
            break
        groups[bi] += groups[bj]
        del groups[bj]
    lab = np.empty(n, int)
    for g, mem in enumerate(groups):
        lab[mem] = g
    return lab


def score(form_sets: dict, tau: float, centered: bool,
          linkage: str = "average"):
    tp = fp = fn = tn = 0
    for form, ms in form_sets.items():
        lab = cluster(vectors(ms, centered), tau, linkage)
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                same_t = ms[i][1] == ms[j][1]
                same_p = lab[i] == lab[j]
                tp += same_p and same_t
                fp += same_p and not same_t
                fn += (not same_p) and same_t
                tn += (not same_p) and (not same_t)
    P = tp / max(tp + fp, 1)
    R = tp / max(tp + fn, 1)
    F = 2 * tp / max(2 * tp + fp + fn, 1)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": P, "recall": R, "f1": F}


def surface(form_sets: dict):
    ts = td = 0
    for _, ms in form_sets.items():
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                ts += ms[i][1] == ms[j][1]
                td += ms[i][1] != ms[j][1]
    return {"tp": ts, "fp": td, "fn": 0,
            "precision": ts / max(ts + td, 1), "recall": 1.0,
            "f1": 2 * ts / max(2 * ts + td, 1)}


TAUS = [round(t, 2) for t in np.arange(0.05, 1.41, 0.05)]

# ---- primary: centered, average linkage; tau on CALIB ----------------------
sweep = [(t, score(CAL, t, centered=True)["f1"]) for t in TAUS]
tau_star = max(sweep, key=lambda x: x[1])[0]
print(f"[m2] calib sweep (centered/avg): "
      f"best tau={tau_star} f1={max(s for _, s in sweep):.3f}", flush=True)

prim = score(EVA, tau_star, centered=True)
base = surface(EVA)
gate_f1 = prim["f1"] >= 0.80
gate_beat = prim["f1"] >= base["f1"] + 0.15
print(f"[m2] PRIMARY eval: F1={prim['f1']:.3f} "
      f"(P={prim['precision']:.3f} R={prim['recall']:.3f}; "
      f"tp={prim['tp']} fp={prim['fp']} fn={prim['fn']}) "
      f"[gate >=0.80: {'PASS' if gate_f1 else 'FAIL'}]", flush=True)
print(f"[m2] surface baseline eval: F1={base['f1']:.3f} "
      f"(P={base['precision']:.3f}) | beat-by-15: "
      f"{prim['f1']:.3f} vs {base['f1'] + 0.15:.3f} "
      f"[{'PASS' if gate_beat else 'FAIL'}]", flush=True)

# ---- secondaries (non-gating) ----------------------------------------------
sec = {}
raw_sweep = [(t, score(CAL, t, centered=False)["f1"]) for t in TAUS]
tau_raw = max(raw_sweep, key=lambda x: x[1])[0]
sec["raw_gist"] = {"tau": tau_raw,
                   **score(EVA, tau_raw, centered=False)}
for lk in ("complete", "single"):
    sw = [(t, score(CAL, t, centered=True, linkage=lk)["f1"]) for t in TAUS]
    tl = max(sw, key=lambda x: x[1])[0]
    sec[f"centered_{lk}"] = {"tau": tl,
                             **score(EVA, tl, centered=True, linkage=lk)}
ctl = score({f: m for f, m in single.items()
             if split_of(f) == "eval"}, tau_star, centered=True)
sec["oversplit_control"] = {
    "split_rate_on_true_same": ctl["fn"] / max(ctl["fn"] + ctl["tp"], 1),
    "n_pairs": ctl["fn"] + ctl["tp"]}
agree = tot = 0
for form, ms in collided.items():
    for i in range(len(ms)):
        for j in range(i + 1, len(ms)):
            if ms[i][2] != ms[j][2]:
                tot += 1
                agree += ms[i][1] != ms[j][1]
sec["registry_vs_batch"] = {"cross_batch_pairs": tot,
                            "registry_splits_them": agree / max(tot, 1)}
for k, v in sec.items():
    show = {kk: (round(vv, 3) if isinstance(vv, float) else vv)
            for kk, vv in v.items() if kk not in ("tp", "fp", "fn", "tn")}
    print(f"[m2] secondary {k}: {show}", flush=True)

verdict = "PASS" if (gate_f1 and gate_beat) else "FAIL"
print(f"[m2] G3 VERDICT: {verdict}", flush=True)

json.dump({
    "protocol": "see module docstring; committed before scoring run",
    "n_forms": {"collided_calib": len(CAL), "collided_eval": len(EVA),
                "single_controls": len(single)},
    "tau_star": tau_star,
    "primary_eval": {**prim,
                     "precision_ci95": wilson_ci(
                         prim["tp"], max(prim["tp"] + prim["fp"], 1)),
                     "recall_ci95": wilson_ci(
                         prim["tp"], max(prim["tp"] + prim["fn"], 1))},
    "surface_baseline_eval": base,
    "gates": {"f1_ge_0.80": bool(gate_f1),
              "beats_surface_by_15": bool(gate_beat),
              "verdict": verdict},
    "calib_sweep": sweep,
    "secondaries": sec,
    "manifest": run_manifest(seed=0),
}, open(ROOT / "results" / "m2_recover.json", "w"), indent=1,
    default=lambda o: o.item() if hasattr(o, "item") else str(o))
print("[done] results/m2_recover.json", flush=True)
