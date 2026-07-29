"""Alias scaling past 4, and the anchor K-sweep for the fallback path (D139).

Task 6, the two parts of it that are measurable now.

**A. Alias scaling.** D129 measured relation identification improving with
the number of aliases per relation — 0.600 / 0.614 / 0.669 / 0.748 for
1/2/3/4 — and stopped at 4 with the curve still climbing. Wikidata has far
more: median 12 per relation, max 80, and 34 of our relations carry >= 12.
This extends the curve to 12 and finds where it flattens, which decides
whether "collect more aliases" is a real lever or a exhausted one.

**B. Anchor K for the fallback path.** D114 swept K when the basis was the
whole representation and found a knee at 8 for 26 relations. D125/D131
narrowed the basis's job to the *novel-relation fallback* — the path taken
when retrieval has no stored example — and D136 confirmed no router beats
the components, so the fallback must stand on its own. K was never swept for
that job at this vocabulary size.

Deliberately NOT here: expanding the wiki crawl (a data-collection task, not
a measurement), and the decoder-headroom probe, which inspection settles —
the walker returns store objects verbatim (D81 quote-never-reconstruct) and
invokes no decoder at any point, so decoder capacity cannot bound any result
in D110-D138.

Usage: .venv/bin/python scripts/exp43_scaling.py
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import v06_pipeline as P                                        # noqa: E402
from codec.evals.anchors import fit_anchors                      # noqa: E402
from codec.manifest import run_manifest                          # noqa: E402
from foundation.kb import KB                                     # noqa: E402

SEED, N_SUBJ, MAX_AL = 0, 40, 12
sch = {d["pid"]: d for d in
       json.loads((ROOT / "data" / "schema_v0.json").read_text())}
props = json.loads((ROOT / "data" / "wikidata_properties.json").read_text())
kb = KB(backend="pg", table="poc")
wiki = [c for c in kb.claims
        if not c["page"].startswith(("arxiv:", "hf:", "user"))]
LABEL, ALIAS = {}, {}
for c in wiki:
    p = c["pid"]
    if p in LABEL:
        continue
    lab = (sch.get(p) or {}).get("label") or (props.get(p) or {}).get("label")
    al = list((sch.get(p) or {}).get("aliases", []))
    al += [a for a in (props.get(p) or {}).get("aliases", []) if a not in al]
    al = [a for a in al if 2 < len(a) < 40]
    if lab and len(al) >= MAX_AL:
        LABEL[p], ALIAS[p] = lab, al[:MAX_AL]
RELS = sorted(LABEL)
print(f"{len(RELS)} relations carry >= {MAX_AL} aliases")

gold = collections.defaultdict(set)
for c in wiki:
    if c["pid"] in LABEL:
        gold[(c["subject"], c["pid"])].add(c["object"])
by_rel = collections.defaultdict(list)
for (s, r) in sorted(gold):
    by_rel[r].append(s)
rng = np.random.default_rng(SEED)
SUBJ = {r: ([by_rel[r][i] for i in
             sorted(rng.choice(len(by_rel[r]), N_SUBJ, replace=False))]
            if len(by_rel[r]) > N_SUBJ else by_rel[r]) for r in RELS}

rows = [{"rel": r, "ai": ai, "text": f"What is the {a} of {s}?"}
        for r in RELS for ai, a in enumerate(ALIAS[r]) for s in SUBJ[r]]
cache = ROOT / "results" / "exp43_emb.npz"
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    assert list(z["texts"]) == [x["text"] for x in rows], "cache misaligned"
    Z, Zl = z["Z"], z["Zl"]
else:
    Z = P.unit(P.embed_texts([x["text"] for x in rows]))
    Zl = P.unit(P.embed_texts([LABEL[r] for r in RELS]))
    np.savez(cache, Z=Z, Zl=Zl,
             texts=np.array([x["text"] for x in rows]))
RC = {r: Zl[i] for i, r in enumerate(RELS)}
print(f"{len(rows)} questions embedded", flush=True)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

EVAL = [i for i, x in enumerate(rows) if x["ai"] >= MAX_AL - 2]
M = np.stack([RC[r] for r in RELS])


def head_acc(n_alias):
    tri = [i for i, x in enumerate(rows) if x["ai"] < n_alias]
    X = torch.tensor(Z[tri])
    Y = torch.tensor(np.stack([RC[rows[i]["rel"]] for i in tri]))
    torch.manual_seed(SEED)
    hd = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, 1024))
    op = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(X)).split(512):
            op.zero_grad()
            ((hd(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
            op.step()
    hd.eval()
    with torch.no_grad():
        pr = hd(torch.tensor(Z[EVAL])).numpy()
    pr = pr / (np.linalg.norm(pr, axis=1, keepdims=True) + 1e-9)
    pred = (pr @ M.T).argmax(1)
    return float(np.mean([RELS[int(pred[k])] == rows[i]["rel"]
                          for k, i in enumerate(EVAL)]))


def knn_acc(n_alias):
    tri = [i for i, x in enumerate(rows) if x["ai"] < n_alias]
    S = Z[EVAL] @ Z[tri].T
    nn_ = S.argmax(1)
    return float(np.mean([rows[tri[int(nn_[k])]]["rel"] == rows[i]["rel"]
                          for k, i in enumerate(EVAL)]))


print(f"\nA. ALIAS SCALING  (held-out aliases {MAX_AL-1},{MAX_AL}; "
      f"chance {1/len(RELS):.3f})")
print(f"{'aliases':>8} {'head':>8} {'1-NN':>8}")
alias_curve = {}
for n in (2, 4, 6, 8, 10):
    h, k = head_acc(n), knn_acc(n)
    alias_curve[n] = {"head": round(h, 4), "knn": round(k, 4)}
    print(f"{n:8d} {h:8.3f} {k:8.3f}", flush=True)
d24 = alias_curve[4]["head"] - alias_curve[2]["head"]
d410 = alias_curve[10]["head"] - alias_curve[4]["head"]
print(f"  head: 2->4 {d24:+.3f} (D129 measured +0.134); "
      f"4->10 {d410:+.3f}")

# ---- B. anchor K for the fallback path on NOVEL relations ----
HOLD = {RELS[i] for i in sorted(rng.permutation(len(RELS))[:8])}
tr = [i for i, x in enumerate(rows)
      if x["rel"] not in HOLD and x["ai"] < MAX_AL - 2]
ev = [i for i, x in enumerate(rows) if x["rel"] in HOLD]
KNOWN = [r for r in RELS if r not in HOLD]
print(f"\nB. ANCHOR K FOR THE FALLBACK PATH  ({len(HOLD)} relations held out "
      f"entirely, {len(ev)} eval questions)")
print(f"{'K':>5} {'novel-relation top-1':>21} {'known-relation top-1':>21}")
kcurve = {}
for K in (8, 16, 32, 48, 64):
    if K > len(KNOWN):
        continue
    PC = P.unit(fit_anchors(np.stack([RC[r] for r in KNOWN]), K, seed=SEED))
    C = {r: P.unit(RC[r] @ PC.T) for r in RELS}
    Mk = np.stack([C[r] for r in RELS])
    X = torch.tensor(Z[tr])
    Y = torch.tensor(np.stack([C[rows[i]["rel"]] for i in tr]))
    torch.manual_seed(SEED)
    hd = nn.Sequential(nn.Linear(1024, 512), nn.GELU(), nn.Linear(512, K))
    op = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(X)).split(512):
            op.zero_grad()
            ((hd(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
            op.step()
    hd.eval()

    def acc(ids):
        with torch.no_grad():
            pr = hd(torch.tensor(Z[ids])).numpy()
        pr = pr / (np.linalg.norm(pr, axis=1, keepdims=True) + 1e-9)
        pred = (pr @ Mk.T).argmax(1)
        return float(np.mean([RELS[int(pred[k])] == rows[i]["rel"]
                              for k, i in enumerate(ids)]))

    nov, kno = acc(ev), acc([i for i in tr][:3000])
    kcurve[K] = {"novel": round(nov, 4), "known": round(kno, 4)}
    print(f"{K:5d} {nov:21.3f} {kno:21.3f}", flush=True)
bestK = max(kcurve, key=lambda k: kcurve[k]["novel"])
print(f"  best K for the fallback path: {bestK} "
      f"(novel {kcurve[bestK]['novel']:.3f}); D114's knee was 8 at 26 "
      f"relations when the basis was the whole representation")

out = {
    "manifest": run_manifest(seed=SEED, config={"MAX_AL": MAX_AL,
                                                "N_SUBJ": N_SUBJ}),
    "n_relations": len(RELS), "alias_curve": alias_curve,
    "anchor_k_fallback": kcurve, "best_k": bestK,
    "decoder_probe": ("not run, and not needed: the walker returns store "
                      "objects verbatim (D81 quote-never-reconstruct) and "
                      "invokes no decoder at any point, so decoder capacity "
                      "cannot bound any result in D110-D138"),
    "scope": ("Alias scaling uses the 34 relations carrying >=12 aliases, "
              "with the last two held out as evaluation phrasings; the head "
              "and a 1-NN baseline are reported together per the D129 "
              "addendum. The K sweep is scoped to the FALLBACK path only — "
              "8 relations held out entirely, basis fit on the rest — which "
              "is the job D125/D131/D136 left the basis doing."),
}
(ROOT / "results" / "exp43_scaling.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp43_scaling.json")
