"""How should relation anchors be chosen relative to entity anchors? (D164 rev-d)

exp55 settled *which encoder* and said a small corpus-fitted basis beats a
large external one. It left two things open that it could not separate, and a
third it never asked.

**What exp55 confounded.** Anchors cannot exceed the pool they are fitted
from, so K > 44 required the external 13,713-label Wikidata pool — meaning
"over-provisioning hurts" and "the external pool hurts" were the same cell.
The **offset pool** breaks that: 12,904 triples give 12,904 corpus-derived
direction vectors, so K can go past 44 *without* leaving the corpus. Any
remaining over-provisioning penalty is then about K, not about provenance.

**What it never asked.** Every basis so far is fitted from relation LABELS —
which is a lexical object. A relation is a thing that *transforms* entities,
and that transformation is visible as `emb(object) − emb(subject)`. Six
strategies, differing only in where the K directions come from and how they
are chosen:

  * `kmeans_label`      — k-means on trained relation labels. exp55's baseline.
  * `pca_label`         — top-K principal components of those labels.
                          Orthogonal by construction; tests whether spread
                          alone explains the basis's value.
  * `lda_between`       — top-K eigenvectors of the BETWEEN-RELATION scatter
                          of question embeddings: the directions along which
                          relation means differ most. This is "the best set
                          that differentiates the relations", stated exactly.
  * `kmeans_offset`     — k-means on individual `emb(obj) − emb(subj)`
                          vectors. Relational rather than lexical, and the
                          only corpus pool large enough to over-provision.
  * `entity_complement` — fit an entity subspace first, project it OUT of the
                          labels, then fit anchors in what remains. This is
                          the orthogonality question made operational: if
                          relation information is separable from entity
                          information, removing the entity subspace should
                          help; if relations are *carried by* entity
                          structure, it should hurt.
  * `random_orthonormal`— the floor. exp20 showed content matters (never
                          above 1.7x chance); kept so the claim stays checked.

**The invariant across all six**: a relation's coordinate is always
`unit(label_r @ PC.T)`. Only the BASIS changes. That preserves the property
the whole product claim rests on — a relation that has never been seen gets
coordinates from its label on arrival, with no instances required. A basis
fitted from offsets still admits a zero-instance relation, because the offsets
only decided *where the axes point*.

**Orthogonality is measured, not assumed.** Each basis reports mean pairwise
|cos| between its anchors, so "what degree of orthogonality do we want" is
answered by looking at the relationship between coherence and transfer rather
than by picking a prior.

Usage: .venv/bin/python scripts/exp56_anchor_strategy.py [m3|gemma|both]
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

from codec.evals.anchors import fit_anchors                      # noqa: E402
from codec.manifest import run_manifest                          # noqa: E402
from foundation.kb import KB                                     # noqa: E402

SEED, MIN_ALIAS, N_SUBJ, N_HOLD_REL = 0, 6, 40, 12
TRAIN_ALIASES, N_EVAL_ALIAS, K_ENTITY = 2, 2, 32
KS = (4, 8, 16, 32, 43, 64, 128, 256)
WHICH = sys.argv[1] if len(sys.argv) > 1 else "both"

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
    if lab and len(al) >= MIN_ALIAS:
        LABEL[p], ALIAS[p] = lab, al[:MIN_ALIAS]
RELS = sorted(LABEL)
TRIP = sorted({(c["subject"], c["pid"], c["object"]) for c in wiki
               if c["pid"] in LABEL})
by_rel = collections.defaultdict(list)
for s, p, o in TRIP:
    by_rel[p].append(s)
rng = np.random.default_rng(SEED)
SUBJ = {}
for r in RELS:
    s = sorted(set(by_rel[r]))
    SUBJ[r] = ([s[i] for i in sorted(rng.choice(len(s), N_SUBJ, replace=False))]
               if len(s) > N_SUBJ else s)
HELD_R = {RELS[i] for i in sorted(rng.permutation(len(RELS))[:N_HOLD_REL])}
TRAINED_R = [r for r in RELS if r not in HELD_R]
rows = [{"rel": r, "ai": ai, "alias": a, "subj": s}
        for r in RELS for ai, a in enumerate(ALIAS[r]) for s in SUBJ[r]]
QTEXT = [f"What is the {x['alias']} of {x['subj']}?" for x in rows]
ENTS = sorted({t[0] for t in TRIP} | {t[2] for t in TRIP})
print(f"{len(RELS)} relations ({len(TRAINED_R)} trained / {len(HELD_R)} held), "
      f"{len(rows)} questions, {len(TRIP)} triples, {len(ENTS)} entities")
print(f"offset pool = {len(TRIP)} corpus vectors, so K can exceed "
      f"{len(TRAINED_R)} WITHOUT the external vocabulary", flush=True)

_GEMMA = None


def encoder(kind_name):
    if kind_name == "m3":
        import v06_pipeline as P
        return (lambda t, k: P.unit(P.embed_texts(list(t))).astype(np.float32))
    global _GEMMA
    from sentence_transformers import SentenceTransformer
    if _GEMMA is None:
        _GEMMA = SentenceTransformer("google/embeddinggemma-300m",
                                     device="cuda")
    # Exact match, never a suffix test. `"gemma_asymmetric".endswith(
    # "symmetric")` is TRUE — "a-symmetric" ends in "symmetric" — so the first
    # version silently ran both arms through the STS prompt and produced two
    # byte-identical caches and two identical result tables. The tell was
    # 36 of 36 cells agreeing to four decimals; nothing else would have caught
    # it, because a wrong prefix produces perfectly plausible numbers.
    if kind_name not in ("gemma_symmetric", "gemma_asymmetric"):
        raise ValueError(f"unknown arm {kind_name!r}")
    sym = kind_name == "gemma_symmetric"

    def go(t, k):
        name = "STS" if sym else ("query" if k == "query" else "document")
        return _GEMMA.encode(list(t), prompt_name=name, batch_size=128,
                             convert_to_numpy=True,
                             normalize_embeddings=True,
                             show_progress_bar=False).astype(np.float32)
    return go


import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402


def unit(a):
    return a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9)


def coherence(PC):
    """Mean pairwise |cos| between anchors. 0 = orthogonal, 1 = collinear."""
    G = np.abs(unit(PC) @ unit(PC).T)
    n = len(PC)
    return float((G.sum() - np.trace(G)) / max(n * (n - 1), 1))


def build_basis(strategy, K, L_tr, Zq, Zent, OFF_tr, d):
    """K directions from trained data only. Held-out relations never enter."""
    if strategy == "kmeans_label":
        return unit(fit_anchors(L_tr, K, seed=SEED)) if K <= len(L_tr) else None
    if strategy == "pca_label":
        if K > len(L_tr) - 1:
            return None
        X = L_tr - L_tr.mean(0)
        return unit(np.linalg.svd(X, full_matrices=False)[2][:K])
    if strategy == "lda_between":
        if K > len(TRAINED_R) - 1:
            return None
        mus, ns = [], []
        for r in TRAINED_R:
            idx = [i for i, x in enumerate(rows)
                   if x["rel"] == r and x["ai"] < TRAIN_ALIASES]
            if idx:
                mus.append(Zq[idx].mean(0))
                ns.append(len(idx))
        M = np.stack(mus)
        mu = np.average(M, axis=0, weights=ns)
        D = (M - mu) * np.sqrt(np.array(ns))[:, None]
        return unit(np.linalg.svd(D, full_matrices=False)[2][:K])
    if strategy == "kmeans_offset":
        return unit(fit_anchors(OFF_tr, K, seed=SEED)) if K <= len(OFF_tr) \
            else None
    if strategy == "entity_complement":
        if K > len(L_tr):
            return None
        E = fit_anchors(Zent, K_ENTITY, seed=SEED)
        Q = np.linalg.qr(E.T)[0]                    # [d, K_ENTITY] orthonormal
        Lp = L_tr - (L_tr @ Q) @ Q.T                # strip the entity subspace
        keep = np.linalg.norm(Lp, axis=1) > 1e-6
        if keep.sum() < K:
            return None
        return unit(fit_anchors(unit(Lp[keep]), K, seed=SEED))
    if strategy == "random_orthonormal":
        if K > d:
            return None
        g = np.random.default_rng(SEED).standard_normal((d, K))
        return unit(np.linalg.qr(g)[0].T.astype(np.float32))
    raise ValueError(strategy)


def identify(Z, C_all, dim):
    """Train on TRAINED relations; identify over ALL. Coordinates from LABELS."""
    M = np.stack([C_all[r] for r in RELS])
    tr = [i for i, x in enumerate(rows)
          if x["rel"] in TRAINED_R and x["ai"] < TRAIN_ALIASES]
    ev_t = [i for i, x in enumerate(rows)
            if x["rel"] in TRAINED_R and x["ai"] >= MIN_ALIAS - N_EVAL_ALIAS]
    ev_n = [i for i, x in enumerate(rows) if x["rel"] in HELD_R]
    X = torch.tensor(Z[tr])
    Y = torch.tensor(np.stack([C_all[rows[i]["rel"]] for i in tr]))
    torch.manual_seed(SEED)
    hd = nn.Sequential(nn.Linear(Z.shape[1], 512), nn.GELU(),
                       nn.Linear(512, dim))
    op = torch.optim.AdamW(hd.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(40):
        for b in torch.randperm(len(X)).split(512):
            op.zero_grad()
            ((hd(X[b]) - Y[b]) ** 2).sum(-1).mean().backward()
            op.step()
    hd.eval()

    def acc(idxs):
        with torch.no_grad():
            p = unit(hd(torch.tensor(Z[idxs])).numpy())
        pred = (p @ M.T).argmax(1)
        return float(np.mean([RELS[int(j)] == rows[i]["rel"]
                              for j, i in zip(pred, idxs)]))
    return round(acc(ev_t), 4), round(acc(ev_n), 4)


STRATS = ["kmeans_label", "pca_label", "lda_between", "kmeans_offset",
          "entity_complement", "random_orthonormal"]
ARMS = (["m3"] if WHICH in ("m3", "both") else []) + \
       ([f"gemma_{m}" for m in ("symmetric", "asymmetric")]
        if WHICH in ("gemma", "both") else [])
OUT = {}
for arm in ARMS:
    print(f"\n=== ARM: {arm} ===", flush=True)
    enc = encoder(arm)
    cache = ROOT / "results" / f"exp56_{arm}_emb.npz"
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        assert list(z["qtext"]) == QTEXT and list(z["ents"]) == ENTS, \
            f"cache misaligned for {arm}; delete it"
        Zq, Zl, Zent = z["Zq"], z["Zl"], z["Zent"]
    else:
        print(f"  embedding {len(QTEXT)} q + {len(RELS)} labels + "
              f"{len(ENTS)} entities...", flush=True)
        Zq = enc(QTEXT, "query")
        Zl = enc([LABEL[r] for r in RELS], "doc")
        Zent = enc(ENTS, "doc")
        np.savez(cache, Zq=Zq, Zl=Zl, Zent=Zent, qtext=np.array(QTEXT),
                 ents=np.array(ENTS))
    d = Zq.shape[1]
    RAW = {r: Zl[i] for i, r in enumerate(RELS)}
    ei = {e: i for i, e in enumerate(ENTS)}
    OFF_tr = unit(np.stack([Zent[ei[o]] - Zent[ei[s]]
                            for s, p, o in TRIP if p in TRAINED_R]))
    L_tr = np.stack([RAW[r] for r in TRAINED_R])
    res = {}
    print(f"  {'strategy':>20} {'K':>4} {'trained':>8} {'NOVEL':>8} "
          f"{'coherence':>10}")
    for st in STRATS:
        for K in KS:
            PC = build_basis(st, K, L_tr, Zq, Zent, OFF_tr, d)
            if PC is None:
                continue
            C = {r: unit(RAW[r] @ PC.T) for r in RELS}
            t, n = identify(Zq, C, PC.shape[0])
            res[f"{st}_K{K}"] = {"strategy": st, "K": K, "trained": t,
                                 "novel": n, "coherence": round(coherence(PC), 4)}
            print(f"  {st:>20} {K:4d} {t:8.4f} {n:8.4f} "
                  f"{res[f'{st}_K{K}']['coherence']:10.4f}", flush=True)
    OUT[arm] = res

print("\n=== best NOVEL per strategy per arm, with what it costs ===")
print(f"{'arm':>18} {'strategy':>20} {'K':>4} {'trained':>8} {'NOVEL':>8} "
      f"{'coher':>7}")
for arm, res in OUT.items():
    for st in STRATS:
        cells = [v for v in res.values() if v["strategy"] == st]
        if not cells:
            continue
        b = max(cells, key=lambda v: v["novel"])
        print(f"{arm:>18} {st:>20} {b['K']:4d} {b['trained']:8.4f} "
              f"{b['novel']:8.4f} {b['coherence']:7.4f}")

print("\n=== does orthogonality predict transfer? "
      "(corr of coherence vs NOVEL, within arm) ===")
corrs = {}
for arm, res in OUT.items():
    c = np.array([v["coherence"] for v in res.values()])
    n = np.array([v["novel"] for v in res.values()])
    corrs[arm] = round(float(np.corrcoef(c, n)[0, 1]), 4)
    print(f"  {arm:>18} r = {corrs[arm]:+.4f}  over {len(c)} cells")
print("  (negative r = more orthogonal bases transfer better)")

out = {"manifest": run_manifest(seed=SEED,
                                config={"KS": list(KS), "STRATS": STRATS,
                                        "K_ENTITY": K_ENTITY,
                                        "N_HOLD_REL": N_HOLD_REL}),
       "n_relations": len(RELS), "n_trained": len(TRAINED_R),
       "n_triples": len(TRIP), "n_entities": len(ENTS),
       "chance": round(1 / len(RELS), 4),
       "arms": OUT, "coherence_novel_corr": corrs,
       "scope": ("Six anchor strategies differing ONLY in where the K basis "
                 "directions come from. In every one a relation's coordinate "
                 "is still unit(label @ PC.T), so zero-instance arrival is "
                 "preserved even when the basis is fitted from offsets — the "
                 "offsets decide where the axes point, not what a relation's "
                 "coordinate is. All bases are fitted on TRAINED relations "
                 "only; held-out relations never enter and never move a "
                 "basis. The offset pool (12,904 corpus triples) is what "
                 "lets K exceed the relation count without the external "
                 "Wikidata vocabulary, which exp55 could not separate from "
                 "over-provisioning itself. Identification level only: no "
                 "store walk, no residual thresholds (D125). Orthogonality "
                 "is measured as mean pairwise |cos| between anchors and "
                 "correlated against transfer rather than assumed.")}
(ROOT / "results" / "exp56_anchor_strategy.json").write_text(
    json.dumps(out, indent=1))
print("\n[done] results/exp56_anchor_strategy.json")
