"""M1 — relation canonicalization (the D61 gate; targets per D64/F12).

Merge rule (closed-form): union-find over relation pairs with
  (a) phrase-embedding cos >= tau,
  (b) value-type agreement (object kind must match),
  (c) auto-merge on shared (subject, object) evidence regardless of tau
      ("X born in Havana" + "X birthplace Havana" -> same relation).
Canonical member = highest fact count. Protos/operators refit by POOLING
member rows (no re-embedding).

Targets: canonical count in [30,120]; antonym-control precision >= 0.9
(opposite-lemma pairs must NOT merge); MuSiQue oracle-chain QA >= 0.40.

Usage: .venv/bin/python scripts/probe_canon_m1.py
"""
from __future__ import annotations
import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from codec.individuation import EntityRegistry, is_value  # noqa: E402
from codec.manifest import run_manifest, wilson_ci        # noqa: E402
from codec.memory_store import MemoryStore, fit_translation  # noqa: E402
from codec.walker import ChannelWalker                    # noqa: E402
import v06_pipeline as P                                  # noqa: E402

DATA = ROOT / "data" / "musique"
rows = json.loads((DATA / "musique_2hop_150.json").read_text())
ext = {}
for line in (DATA / "triples_v0.jsonl").read_text().splitlines():
    d = json.loads(line)
    ext[d["pid"]] = d
all_facts = []
for r in rows:
    for pi in range(len(r["paragraphs"])):
        d = ext.get(f"{r['id']}#{pi}")
        if not d:
            continue
        for t in d["triples"]:
            if not (isinstance(t, list) and len(t) == 3):
                continue
            s, rel, o = (str(x) for x in t)
            rel = re.sub(r"[^a-z0-9 ]", "", rel.lower()).strip()
            if rel:
                all_facts.append({"batch": f"{r['id']}#{pi}", "subject": s,
                                  "relation": rel, "object": o,
                                  "text": f"{s} — {rel}: {o}."})
rels = sorted({f["relation"] for f in all_facts})
z = np.load(ROOT / "results" / "ingest_v0_emb.npz")
Zf, Zq = z["Zf"], z["Zq"]
# v2: relation similarity from CARRIER-TEMPLATE embeddings ("X {rel} Y.")
# — bare 2-word phrases sit off-manifold for the proposition-fit whitener
rcache = ROOT / "results" / "m1_rel_carrier_emb.npz"
if rcache.exists():
    Zrel = np.load(rcache)["Z"]
else:
    Zrel = P.embed_texts([f"X {r} Y." for r in rels])
    np.savez(rcache, Z=Zrel)
rel_i = {r: i for i, r in enumerate(rels)}
freq = Counter(f["relation"] for f in all_facts)
val_frac = defaultdict(list)
so_pairs = defaultdict(set)
for f in all_facts:
    val_frac[f["relation"]].append(is_value(f["object"]))
    so_pairs[f["relation"]].add((f["subject"].lower(), f["object"].lower()))
vkind = {r: (sum(v) / len(v)) > 0.5 for r, v in val_frac.items()}

OPP = [("birth", "death"), ("born", "died"), ("found", "dissolv"),
       ("start", "end"), ("join", "left"), ("largest", "smallest"),
       ("highest", "lowest"), ("predecessor", "successor"),
       ("before", "after"), ("north", "south")]
def opposed(a, b):
    return any((x in a and y in b) or (y in a and x in b) for x, y in OPP)

parent = list(range(len(rels)))
def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i
def union(i, j):
    parent[find(i)] = find(j)

S = Zrel @ Zrel.T
TAU = float(__import__('os').environ.get('M1_TAU', '0.70'))
merged_pairs = []
for i in range(len(rels)):
    for j in range(i + 1, len(rels)):
        a, b = rels[i], rels[j]
        if vkind[a] != vkind[b]:
            continue
        evid = len(so_pairs[a] & so_pairs[b]) > 0
        if evid or S[i, j] >= TAU:
            union(i, j)
            merged_pairs.append((a, b, float(S[i, j]), evid))
canon_of = {}
groups = defaultdict(list)
for i, r in enumerate(rels):
    groups[find(i)].append(r)
for g in groups.values():
    can = max(g, key=lambda r: freq[r])
    for r in g:
        canon_of[r] = can
n_canon = len(set(canon_of.values()))
# antonym control
ctl = [(a, b) for i, a in enumerate(rels) for b in rels[i+1:]
       if opposed(a, b)]
bad = [(a, b) for a, b in ctl if canon_of[a] == canon_of[b]]
prec = 1 - len(bad) / max(len(ctl), 1)
print(f"[m1] {len(rels)} -> {n_canon} canonical relations (tau={TAU}) | "
      f"antonym control: {len(ctl)} pairs, precision={prec:.3f} "
      f"(bad: {bad[:4]})", flush=True)

# rebuild store under canonical relations; pool member rows for protos/ops
canon_rows = defaultdict(list)
for i, f in enumerate(all_facts):
    canon_rows[canon_of[f["relation"]]].append(i)
protos, ops = {}, {}
for c, idxs in canon_rows.items():
    protos[c] = P.unit(Zq[idxs].mean(0))
    ops[c] = fit_translation(Zq[idxs], Zf[idxs])
reg = EntityRegistry()
store = MemoryStore()
for f, zf in zip(all_facts, Zf):
    c = canon_of[f["relation"]]
    qb = f["batch"].split("#")[0]   # v2: batch = QUESTION (a retrieval
    # session is one discourse context; paragraph-level batches split the
    # same entity across a question's own paragraphs, killing hand-off)
    se = reg.resolve_write(f["subject"], c, "s", None, batch=qb)
    oe = reg.resolve_write(f["object"], c, "o", se, batch=qb)
    reg._get(se).neighbors.add(oe)
    i = store.add(zf, [], f["text"])
    store.ids[i] = {se, oe}
    store.content_ids[i] = {se, oe}
walker = ChannelWalker(store, protos=protos, ops=ops)

cans = sorted(protos)
Zcan = np.stack([Zrel[rel_i[c]] for c in cans])
dq = np.load(ROOT / "results" / "ingest_v0_dq_emb.npz")["Zd"]
di = 0
hit = n = 0
for r in rows:
    steps = r["decomposition"]
    chain = []
    for s_ in steps:
        chain.append(cans[int(np.argmax(dq[di] @ Zcan.T))])
        di += 1
    subj = steps[0]["question"]
    cands = [nm for nm in reg.by_form if nm.lower() in subj.lower()
             and len(nm) > 3]
    n += 1
    if not cands:
        continue
    eids = reg.resolve_query(max(cands, key=len))
    if not eids:
        continue
    got = walker.walk(set(eids[:1]), chain)
    if got is None:
        continue
    golds = {r["answer"].lower()} | {a.lower() for a in r["aliases"]}
    obj = all_facts[got]["object"].lower()
    hit += any(g in obj or obj in g for g in golds if len(g) > 2)
lo, hi = wilson_ci(hit, n)
print(f"[m1] oracle-chain 2-hop EM = {hit}/{n} = {hit/n:.3f} "
      f"(CI {lo:.2f}-{hi:.2f}) [D61 baseline 0.020; target >=0.40; "
      f"extraction ceiling 0.567]", flush=True)
(ROOT / "results" / "canon_m1.json").write_text(json.dumps(
    {"n_relations": len(rels), "n_canonical": n_canon, "tau": TAU,
     "antonym_control": {"pairs": len(ctl), "precision": prec,
                         "merged_bad": bad},
     "qa_em": hit / n, "qa_n": n, "qa_ci95": [lo, hi],
     "targets": {"count_range": [30, 120], "antonym_prec": 0.9,
                 "qa": 0.40},
     "manifest": run_manifest(seed=0)}, indent=2))
print("[done] results/canon_m1.json", flush=True)
