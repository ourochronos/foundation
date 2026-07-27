"""M1 final — Haiku phrase→schema map scored on the FROZEN audit, then the
MuSiQue QA rerun through pid-canonical relations with format-normalized
chain mapping (decomposition ">>" relnames matched against schema labels
directly — the D71 trace fix).

Usage: .venv/bin/python scripts/probe_m1_final.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from codec.individuation import EntityRegistry, is_value          # noqa: E402
from codec.manifest import run_manifest, wilson_ci                # noqa: E402
from codec.memory_store import MemoryStore, fit_translation       # noqa: E402
from codec.walker import ChannelWalker                            # noqa: E402
import v06_pipeline as P                                          # noqa: E402


def norm(r):
    return re.sub(r"[^a-z0-9 ]", "", str(r).lower()).strip()


# ---- merge Haiku shards -> (phrase, kind) -> pid --------------------------
rel_map = {}
for f in sorted((ROOT / "data" / "m1_shards").glob("out_*.jsonl")):
    for line in f.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            rel_map[(d["phrase"], d["kind"])] = d.get("pid")
        except Exception:
            continue
print(f"[merge] {len(rel_map)} (phrase,kind) classifications", flush=True)

# ---- audit (frozen labels, c3acfac) ---------------------------------------
audit = json.loads((ROOT / "data" / "m1_audit_100.json").read_text())
ok = 0
errs = []
for row in audit:
    r = norm(row["triple"][1])
    kind = "value" if is_value(str(row["triple"][2])) else "entity"
    got = rel_map.get((r, kind))
    gold = row.get("gold_pid")
    ok += got == gold
    if got != gold and len(errs) < 10:
        errs.append((r, kind, gold, got))
lo, hi = wilson_ci(ok, len(audit))
print(f"[audit] Haiku mapping accuracy = {ok}/100 = {ok/100:.2f} "
      f"(CI {lo:.2f}-{hi:.2f}) [gate >=0.85; cosine v2 was 0.56]",
      flush=True)
print(f"[audit] errors: {errs[:8]}", flush=True)

# ---- rebuild facts with pid-canonical relations ----------------------------
rows = json.loads((ROOT / "data" / "musique" /
                   "musique_2hop_150.json").read_text())
ext = {json.loads(l)["pid"]: json.loads(l) for l in
       (ROOT / "data" / "musique" / "triples_v0.jsonl"
        ).read_text().splitlines()}
all_facts, mapped_n = [], 0
for r in rows:
    for pi in range(len(r["paragraphs"])):
        d = ext.get(f"{r['id']}#{pi}")
        if not d:
            continue
        for t in d["triples"]:
            if not (isinstance(t, list) and len(t) == 3):
                continue
            s_, rel, o = (str(x) for x in t)
            reln = norm(rel)
            if not reln:
                continue
            kind = "value" if is_value(o) else "entity"
            pid = rel_map.get((reln, kind))
            mapped_n += pid is not None
            all_facts.append({"batch": r["id"], "subject": s_,
                              "pid": pid, "raw": reln, "object": o,
                              "text": f"{s_} — {rel}: {o}."})
cov = mapped_n / len(all_facts)
print(f"[coverage] {mapped_n}/{len(all_facts)} = {cov:.3f} "
      f"(gold-mappable base rate 0.57)", flush=True)

cache = ROOT / "results" / "ingest_v0_emb.npz"
z = np.load(cache)
Zf, Zq = z["Zf"], z["Zq"]
assert len(Zf) == len(all_facts), "fact alignment drift"

schema = json.loads((ROOT / "data" / "schema_v0.json").read_text())
label_of = {p["pid"]: p["label"] for p in schema}
alias_ix = {}
for p in schema:
    for a in [p["label"]] + p["aliases"]:
        alias_ix.setdefault(norm(a), p["pid"])

by_pid = defaultdict(list)
for i, f in enumerate(all_facts):
    if f["pid"]:
        by_pid[f["pid"]].append(i)
protos, ops = {}, {}
for pid, idxs in by_pid.items():
    if len(idxs) >= 2:
        protos[pid] = P.unit(Zq[idxs].mean(0))
        ops[pid] = fit_translation(Zq[idxs], Zf[idxs])
print(f"[canon] {len(protos)} pid-relations with fitted operators",
      flush=True)

reg = EntityRegistry()
store = MemoryStore()
for f, zf in zip(all_facts, Zf):
    rel = f["pid"] or f["raw"]
    se = reg.resolve_write(f["subject"], rel, "s", None, batch=f["batch"])
    oe = reg.resolve_write(f["object"], rel, "o", se, batch=f["batch"])
    reg._get(se).neighbors.add(oe)
    i = store.add(zf, [], f["text"])
    store.ids[i] = {se, oe}
    store.content_ids[i] = {se, oe}
walker = ChannelWalker(store, protos=protos, ops=ops)

# ---- chain mapping: ">>" relname -> pid by label/alias match, embedding
# fallback against schema carrier questions --------------------------------
pids = sorted(protos)
pcarrier = [f"What is the {label_of[p]} of X?" for p in pids]
ccache = ROOT / "results" / "m1_final_emb.npz"
if ccache.exists():
    Zc = np.load(ccache)["Zc"]
else:
    Zc = P.embed_texts(pcarrier)
    np.savez(ccache, Zc=Zc)


def map_step(step_q):
    reln = norm(step_q.split(">>")[-1])
    if reln in alias_ix and alias_ix[reln] in protos:
        return alias_ix[reln]
    zq = P.embed_texts([f"What is the {reln} of X?"])[0]
    return pids[int(np.argmax(zq @ Zc.T))]


hit = n = 0
for r in rows:
    steps = r["decomposition"]
    chain = [map_step(s_["question"]) for s_ in steps]
    subj_q = steps[0]["question"]
    cands = [nm for nm in reg.by_form if nm.lower() in subj_q.lower()
             and len(nm) > 3]
    n += 1
    if not cands:
        continue
    eids = reg.resolve_query(max(cands, key=len), chain[0]) or \
        reg.resolve_query(max(cands, key=len))
    golds = {r["answer"].lower()} | {a.lower() for a in r["aliases"]}
    best_sc, best_obj = -1e9, None
    for e in eids[:8]:
        got = walker.walk({e}, chain)
        if got is None:
            continue
        sc = store.query(walker.pt[chain[0]], {e}, k=1, id_weight=1.0)
        if sc and sc[0][1] > best_sc:
            best_sc, best_obj = sc[0][1], all_facts[got]["object"].lower()
    if best_obj is not None:
        hit += any(g in best_obj or best_obj in g
                   for g in golds if len(g) > 2)
lo2, hi2 = wilson_ci(hit, n)
print(f"[qa] 2-hop EM = {hit}/{n} = {hit/n:.3f} (CI {lo2:.2f}-{hi2:.2f}) "
      f"[D61 floor 0.020; extraction ceiling 0.567]", flush=True)

json.dump({"audit_acc": ok / 100, "audit_ci95": [lo, hi],
           "coverage": cov, "n_pid_relations": len(protos),
           "qa_em": hit / n, "qa_n": n, "qa_ci95": [lo2, hi2],
           "manifest": run_manifest(seed=0)},
          open(ROOT / "results" / "m1_final.json", "w"), indent=1)
print("[done] results/m1_final.json", flush=True)
