"""M1-rescoped — relation phrase -> curated schema property (D67).

Classifier: carrier-sentence embeddings both sides ("X {phrase} Y."),
max-sim over a property's label+alias carriers, value-kind gate.
tau calibrated on MQuAKE's 36 relation->P-id mappings (free labels),
NEVER on the audit. Audit labels were frozen in c3acfac before this ran.

Usage: .venv/bin/python scripts/probe_schema_map_m1.py
"""
from __future__ import annotations
import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from codec.manifest import run_manifest, wilson_ci  # noqa: E402
from codec.individuation import is_value            # noqa: E402
import v06_pipeline as P                            # noqa: E402

schema = json.loads((ROOT / "data" / "schema_v0.json").read_text())
ext = [json.loads(l) for l in
       (ROOT / "data" / "musique" / "triples_v0.jsonl").read_text().splitlines()]
all_facts = []
for d in ext:
    for t in d["triples"]:
        if isinstance(t, list) and len(t) == 3:
            s, r, o = (str(x) for x in t)
            r = re.sub(r"[^a-z0-9 ]", "", r.lower()).strip()
            if r:
                all_facts.append({"relation": r, "object": o})
rels = sorted({f["relation"] for f in all_facts})
vf = defaultdict(list)
for f in all_facts:
    vf[f["relation"]].append(is_value(f["object"]))
rel_kind = {r: "value" if sum(v) / len(v) > 0.5 else "entity"
            for r, v in vf.items()}

# embeddings
prop_texts, prop_of = [], []
for i, p in enumerate(schema):
    for phr in [p["label"]] + p["aliases"]:
        prop_texts.append(f"X {phr} Y.")
        prop_of.append(i)
mq = json.loads((ROOT / "data" / "mquake" / "MQuAKE-CF-3k.json").read_text())
mq_rel = {}
for c in mq:
    for rw in c["requested_rewrite"]:
        mq_rel.setdefault(rw["relation_id"],
                          rw["prompt"].format("X") + " Y.")
mq_pids = sorted(mq_rel)
cache = ROOT / "results" / "m1_schema_emb.npz"
if cache.exists():
    z = np.load(cache)
    Zp, Zr, Zm = z["Zp"], z["Zr"], z["Zm"]
else:
    Zp = P.embed_texts(prop_texts)
    Zr = np.load(ROOT / "results" / "m1_rel_carrier_emb.npz")["Z"]
    Zm = P.embed_texts([mq_rel[p] for p in mq_pids])
    np.savez(cache, Zp=Zp, Zr=Zr, Zm=Zm)

pid_of = [p["pid"] for p in schema]
kind_of = {p["pid"]: p["value_kind"] for p in schema}
S_prop = Zp  # [n_carriers, d]


def classify(zvec, kind, tau):
    sims = zvec @ S_prop.T
    best_per_prop = defaultdict(float)
    for j, s in enumerate(sims):
        i = prop_of[j]
        if s > best_per_prop[i]:
            best_per_prop[i] = float(s)
    order = sorted(best_per_prop.items(), key=lambda x: -x[1])
    for i, s in order:
        if s < tau:
            break
        if kind is None or kind_of[pid_of[i]] == kind:
            return pid_of[i], s
    return None, order[0][1] if order else 0.0


# tau calibration on MQuAKE: in-schema pids are positives; the pids NOT
# in schema_v0 are genuine NONE cases — v1 had no rejection class and tau
# collapsed to the floor (coverage 0.979, audit 0.40)
in_schema = [p for p in mq_pids if p in set(pid_of)]
none_cases = [p for p in mq_pids if p not in set(pid_of)]
best_tau, best_acc = None, -1
for tau in np.arange(0.60, 0.95, 0.0125):
    ok = 0
    for p, zm in zip(mq_pids, Zm):
        got, _ = classify(zm, None, tau)
        ok += (got == p) if p in set(pid_of) else (got is None)
    acc = ok / len(mq_pids)
    if acc > best_acc:
        best_acc, best_tau = acc, float(tau)
print(f"[calib] {len(in_schema)} positives + {len(none_cases)} NONE cases",
      flush=True)
print(f"[calib] MQuAKE {len(in_schema)} in-schema relations: "
      f"acc={best_acc:.3f} at tau={best_tau:.3f}", flush=True)

# audit
audit = json.loads((ROOT / "data" / "m1_audit_100.json").read_text())
rel_i = {r: i for i, r in enumerate(rels)}
ok = both_none = 0
errs = []
for row in audit:
    r = re.sub(r"[^a-z0-9 ]", "", str(row["triple"][1]).lower()).strip()
    gold = row.get("gold_pid")
    if r in rel_i:
        # kind gate PER INSTANCE: "born"+date -> P569, "born in"+place ->
        # P19 (per-relation majority kind broke ambiguous phrases)
        inst_kind = "value" if is_value(str(row["triple"][2])) else "entity"
        got, s = classify(Zr[rel_i[r]], inst_kind, best_tau)
    else:
        got = None
    hit = got == gold
    ok += hit
    if not hit and len(errs) < 8:
        errs.append((r, gold, got))
lo, hi = wilson_ci(ok, len(audit))
print(f"[audit] mapping accuracy = {ok}/100 = {ok/100:.2f} "
      f"(CI {lo:.2f}-{hi:.2f}) [target >=0.85]", flush=True)
print(f"[audit] sample errors: {errs[:6]}", flush=True)

# coverage over all triples
mapped = 0
rel_map = {}
for r in rels:
    for kind in ("entity", "value"):
        got, s = classify(Zr[rel_i[r]], kind, best_tau)
        rel_map[(r, kind)] = got
for f in all_facts:
    kind = "value" if is_value(f["object"]) else "entity"
    mapped += rel_map[(f["relation"], kind)] is not None
rel_map = {f"{r}|{k}": v for (r, k), v in rel_map.items()}
print(f"[coverage] {mapped}/{len(all_facts)} triples mapped = "
      f"{mapped/len(all_facts):.3f} [registered 0.70; gold-mappable rate "
      f"in audit was 0.57 — the target measured extraction, not this]",
      flush=True)
json.dump({"tau": best_tau, "calib_acc": best_acc,
           "audit_acc": ok / 100, "audit_ci95": [lo, hi],
           "coverage": mapped / len(all_facts),
           "n_canonical_used": len({v for v in rel_map.values() if v}),
           "rel_map": rel_map,
           "manifest": run_manifest(seed=0)},
          open(ROOT / "results" / "schema_map_m1.json", "w"), indent=1)
print("[done] results/schema_map_m1.json", flush=True)
