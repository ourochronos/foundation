"""L2 ingest v0 — passages → triples → registry/store → 2-hop QA (MuSiQue).

Three phases, resumable:
  extract   Bonsai-27B (local, 1-bit) pulls "S | R | O" lines per paragraph
            → data/musique/triples_v0.jsonl
  measure   extraction recall proxy: does each gold decomposition answer
            appear as an object among that paragraph's extracted triples?
  qa        registry ingest (document = batch, D52 locality); relation
            protos/operators fit from SYNTHESIZED questions (template over
            the open relation string — no hand schema per relation, one
            rule for all); 2-hop execution with ORACLE chain relations
            (mapped to extracted relation strings by embedding similarity).
            Open-relation DETECTION is explicitly v1 scope — this measures
            ingest quality through the store machinery, not question
            understanding (logged in D60).

Usage: .venv/bin/python scripts/ingest_v0.py extract|measure|qa
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

DATA = ROOT / "data" / "musique"
TRIPLES = DATA / "triples_v0.jsonl"

PROMPT = """Extract all factual relations from the passage as triples.
One per line, exactly: SUBJECT | RELATION | OBJECT
Use short lowercase relation phrases (2-4 words). Use full entity names.
Only facts stated in the passage. No commentary.

Passage: Glenhis Hernandez (born 7 October 1990 in Havana) is a Cuban
taekwondo practitioner. She won the World Championship title in 2013.
Triples:
Glenhis Hernandez | born in | Havana
Glenhis Hernandez | birth year | 1990
Glenhis Hernandez | nationality | Cuban
Glenhis Hernandez | sport | taekwondo
Glenhis Hernandez | won | World Championship title 2013

Passage: {passage}
Triples:
"""


def extract():
    rows = json.loads((DATA / "musique_2hop_150.json").read_text())
    done = set()
    if TRIPLES.exists():
        for line in TRIPLES.read_text().splitlines():
            done.add(json.loads(line)["pid"])
    out = TRIPLES.open("a")
    n = 0
    for r in rows:
        for pi, p in enumerate(r["paragraphs"]):
            pid = f"{r['id']}#{pi}"
            if pid in done:
                continue
            text = f"{p['title']}: {p['text'][:1200]}"
            res = subprocess.run(
                [str(ROOT / "bonsai.sh"), "-p",
                 PROMPT.format(passage=text)],
                capture_output=True, text=True, timeout=180)
            triples = []
            for line in res.stdout.splitlines():
                m = line.split("|")
                if len(m) == 3 and all(x.strip() for x in m):
                    s, rel, o = (x.strip() for x in m)
                    if len(s) < 80 and len(rel) < 40 and len(o) < 80:
                        triples.append([s, rel.lower(), o])
            out.write(json.dumps({"pid": pid, "title": p["title"],
                                  "triples": triples}) + "\n")
            out.flush()
            n += 1
            if n % 25 == 0:
                print(f"[extract] {n} paragraphs", flush=True)
    print(f"[extract] done (+{n})", flush=True)


def measure():
    rows = json.loads((DATA / "musique_2hop_150.json").read_text())
    ext = {}
    for line in TRIPLES.read_text().splitlines():
        d = json.loads(line)
        ext[d["pid"]] = d["triples"]
    tot = hit = 0
    per_q = []
    for r in rows:
        found = 0
        for step in r["decomposition"]:
            ans = step["answer"].lower()
            ok = any(ans in o.lower() or o.lower() in ans
                     for pi in range(len(r["paragraphs"]))
                     for _s, _rel, o in ext.get(f"{r['id']}#{pi}", [])
                     if len(o) > 2)
            tot += 1
            hit += ok
            found += ok
        per_q.append(found == len(r["decomposition"]))
    print(f"[measure] step-answer recall {hit}/{tot} = {hit/tot:.3f} | "
          f"both-steps-covered {sum(per_q)}/{len(per_q)} = "
          f"{sum(per_q)/len(per_q):.3f}", flush=True)
    json.dump({"step_recall": hit / tot,
               "full_coverage": sum(per_q) / len(per_q)},
              open(ROOT / "results" / "ingest_v0_extract.json", "w"),
              indent=2)


def qa():
    import numpy as np
    from codec.individuation import EntityRegistry
    from codec.manifest import run_manifest, wilson_ci
    from codec.memory_store import MemoryStore, fit_translation, id_tokens
    from codec.walker import ChannelWalker
    import v06_pipeline as P

    rows = json.loads((DATA / "musique_2hop_150.json").read_text())
    ext = {}
    for line in TRIPLES.read_text().splitlines():
        d = json.loads(line)
        ext[d["pid"]] = d
    # collect triples per question-document batch
    all_facts = []
    for r in rows:
        for pi in range(len(r["paragraphs"])):
            d = ext.get(f"{r['id']}#{pi}")
            if not d:
                continue
            for s, rel, o in d["triples"]:
                rel = re.sub(r"[^a-z0-9 ]", "", rel).strip()
                if rel:
                    all_facts.append({"batch": f"{r['id']}#{pi}",
                                      "subject": s, "relation": rel,
                                      "object": o,
                                      "text": f"{s} — {rel}: {o}."})
    rels = sorted({f["relation"] for f in all_facts})
    print(f"[qa] {len(all_facts)} triples, {len(rels)} open relations",
          flush=True)
    # synthesized questions (ONE rule for all relations — no per-relation
    # hand schema): "What is the {rel} of {s}?"
    fact_texts = [f["text"] for f in all_facts]
    q_texts = [f"What is the {f['relation']} of {f['subject']}?"
               for f in all_facts]
    cache = ROOT / "results" / "ingest_v0_emb.npz"
    if cache.exists():
        z = np.load(cache)
        Zf, Zq, Zrel = z["Zf"], z["Zq"], z["Zrel"]
    else:
        Zf = P.embed_texts(fact_texts)
        Zq = P.embed_texts(q_texts)
        Zrel = P.embed_texts(rels)
        np.savez(cache, Zf=Zf, Zq=Zq, Zrel=Zrel)
    rel_i = {r: i for i, r in enumerate(rels)}
    reg = EntityRegistry()
    store = MemoryStore()
    for f, zf in zip(all_facts, Zf):
        se = reg.resolve_write(f["subject"], f["relation"], "s", None,
                               batch=f["batch"])
        oe = reg.resolve_write(f["object"], f["relation"], "o", se,
                               batch=f["batch"])
        reg._get(se).neighbors.add(oe)
        i = store.add(zf, [], f["text"])
        store.ids[i] = {se, oe}
        store.content_ids[i] = {se, oe}
    # per-relation proto/operator from synthesized questions
    by_rel: dict[str, list[int]] = {}
    for i, f in enumerate(all_facts):
        by_rel.setdefault(f["relation"], []).append(i)
    protos, ops = {}, {}
    for r, idxs in by_rel.items():
        protos[r] = P.unit(Zq[idxs].mean(0))
        ops[r] = fit_translation(Zq[idxs], Zf[idxs])
    walker = ChannelWalker(store, protos=protos, ops=ops)

    # oracle-chain 2-hop: decomposition gives step questions; map each step
    # to the nearest extracted relation by embedding similarity
    dq_texts = [s["question"] for r in rows for s in r["decomposition"]]
    dcache = ROOT / "results" / "ingest_v0_dq_emb.npz"
    if dcache.exists():
        Zd = np.load(dcache)["Zd"]
    else:
        Zd = P.embed_texts(dq_texts)
        np.savez(dcache, Zd=Zd)
    di = 0
    hit = n = 0
    for r in rows:
        steps = r["decomposition"]
        chain = []
        for s_ in steps:
            sims = Zd[di] @ Zrel.T
            chain.append(rels[int(np.argmax(sims))])
            di += 1
        subj = steps[0]["question"]
        cands = [nm for nm in reg.by_form if nm.lower() in subj.lower()
                 and len(nm) > 3]
        if not cands:
            n += 1
            continue
        subj_form = max(cands, key=len)
        eids = reg.resolve_query(subj_form)
        if not eids:
            n += 1
            continue
        got = walker.walk(set(eids[:1]), chain)
        n += 1
        if got is None:
            continue
        golds = {r["answer"].lower()} | {a.lower() for a in r["aliases"]}
        obj = all_facts[got]["object"].lower()
        hit += any(g in obj or obj in g for g in golds if len(g) > 2)
    lo, hi = wilson_ci(hit, n)
    print(f"[qa] oracle-chain 2-hop EM = {hit}/{n} = {hit/n:.3f} "
          f"(CI {lo:.2f}-{hi:.2f})", flush=True)
    json.dump({"em": hit / n, "n": n, "ci95": [lo, hi],
               "n_triples": len(all_facts), "n_relations": len(rels),
               "scope": "oracle chain relations; open-relation detection "
                        "is v1",
               "manifest": run_manifest(seed=0)},
              open(ROOT / "results" / "ingest_v0_qa.json", "w"), indent=2)


if __name__ == "__main__":
    {"extract": extract, "measure": measure, "qa": qa}[sys.argv[1]]()
