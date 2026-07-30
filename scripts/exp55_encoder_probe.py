"""Does label-projection survive an encoder swap, and does over-provisioning K help?

The go/no-go probe before committing to a 2.2 GB re-embed. The project's
central bet is that a relation gets usable coordinates from its **label**
projected into a frozen basis — which is why a never-trained relation is
answerable on arrival (D113, D116, D125). If that mechanism is a property of
the geometry rather than of BGE-M3 specifically, it should survive a change of
encoder. If it does not, that is a finding worth having before the swap, not
after.

**Measured at the IDENTIFICATION level: no store walk, no residual
thresholds.** That is deliberate. D125 established that residual thresholds do
not transfer across representation dimensionality, so an end-to-end probe on a
768-d encoder using 1024-d thresholds would look like an encoder failure while
actually being a calibration failure. Removing thresholds removes the single
most likely way to manufacture a fake negative.

**Three factors, crossed, because two of them are nearly free.**

  * **encoder** — BGE-M3 (1024-d) against EmbeddingGemma (768-d). The
    expensive factor: one embedding pass each.
  * **anchor pool and K** — free once labels are embedded, since `fit_anchors`
    runs on cached vectors. Note that **over-provisioning past the relation
    count is impossible from the corpus's own labels**: k-means cannot place
    96 anchors among 49 points. So over-provisioning *requires* an external
    pool, and this uses the 13,713 labelled Wikidata properties that never saw
    this corpus (exp21's device). K sweeps from far below to far above the
    corpus relation count.
  * **prefix strategy** (EmbeddingGemma only) — costs one extra pass and is
    the factor most likely to be mistaken for an encoder result. Gemma
    *requires* asymmetric task prefixes: `task: … | query: …` for queries,
    `title: … | text: …` for documents. This architecture needs questions and
    relation labels co-located in ONE geometry, while a retrieval encoder is
    trained to align queries *to* documents. Choosing wrong and reporting
    "Gemma is worse" would be measuring our prefix choice.

**What decides it.** Novel-relation identification: hold 12 relations out of
the head's training entirely, then ask whether a question about one of them
still picks its label out of the full relation set. Chance is 1/n. Trained
relations are the control ceiling, and 1-NN over training questions is the
non-parametric reference.

Usage: .venv/bin/python scripts/exp55_encoder_probe.py [m3|gemma|both]
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
from codec.manifest import run_manifest, wilson_ci               # noqa: E402
from foundation.kb import KB                                     # noqa: E402

SEED, MIN_ALIAS, N_SUBJ, N_HOLD_REL = 0, 6, 40, 12
TRAIN_ALIASES, N_EVAL_ALIAS = 2, 2
KS = (4, 8, 16, 32, 48, 64, 96, 128, 192, 256)
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
by_rel = collections.defaultdict(list)
seen = set()
for c in wiki:
    if c["pid"] in LABEL and (c["subject"], c["pid"]) not in seen:
        seen.add((c["subject"], c["pid"]))
        by_rel[c["pid"]].append(c["subject"])
rng = np.random.default_rng(SEED)
SUBJ = {}
for r in RELS:
    s = sorted(set(by_rel[r]))
    SUBJ[r] = ([s[i] for i in sorted(rng.choice(len(s), N_SUBJ, replace=False))]
               if len(s) > N_SUBJ else s)

HELD_R = {RELS[i] for i in
          sorted(rng.permutation(len(RELS))[:N_HOLD_REL])}
TRAINED_R = [r for r in RELS if r not in HELD_R]
rows = [{"rel": r, "ai": ai, "alias": a, "subj": s}
        for r in RELS for ai, a in enumerate(ALIAS[r]) for s in SUBJ[r]]
QTEXT = [f"What is the {x['alias']} of {x['subj']}?" for x in rows]
# external pool: every labelled Wikidata property, so K can exceed the corpus
EXT = sorted({v["label"] for v in props.values() if v.get("label")})
print(f"{len(RELS)} relations ({len(TRAINED_R)} trained / {len(HELD_R)} held "
      f"out ENTIRELY), {len(rows)} questions")
print(f"external anchor pool: {len(EXT)} Wikidata labels — this is what makes "
      f"K > {len(TRAINED_R)} possible at all", flush=True)

# --------------------------------------------------------------------------
# Encoders. Each returns a callable (texts, kind) -> unit vectors, where kind
# is "query" or "doc"; a symmetric encoder ignores it.
# --------------------------------------------------------------------------
def enc_m3():
    import v06_pipeline as P
    return lambda texts, kind: P.unit(P.embed_texts(list(texts))), 1024


_GEMMA = None


def enc_gemma(prefix_mode: str):
    """EmbeddingGemma, using its OWN registered prompts rather than literals.

    The strings are identical to what we would hand-roll today
    (`task: sentence similarity | query: ` etc.), but naming them means a
    change in the model card cannot silently turn into a wrong prefix that
    reads as an encoder result. `symmetric` puts questions AND labels through
    one prompt so they share a geometry, which is what predicting a sum of
    label coordinates from a question requires; `asymmetric` uses the
    query/document split the model was trained for, which is right for
    retrieval and may be wrong for this architecture. That is the question.
    """
    global _GEMMA
    from sentence_transformers import SentenceTransformer
    if _GEMMA is None:
        _GEMMA = SentenceTransformer("google/embeddinggemma-300m",
                                     device="cuda")
    m = _GEMMA

    def go(texts, kind):
        name = ("STS" if prefix_mode == "symmetric"
                else ("query" if kind == "query" else "document"))
        e = m.encode(list(texts), prompt_name=name, batch_size=128,
                     convert_to_numpy=True, normalize_embeddings=True,
                     show_progress_bar=False)
        return e.astype(np.float32)
    return go, m.get_embedding_dimension()


import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402


def identification(Z, RC_all, dim, tag):
    """Train on TRAINED relations only; identify over ALL relations.

    The head predicts a relation coordinate from a question. A held-out
    relation is never in training, so getting it right requires its LABEL
    coordinate to sit where the head learned to point — which is the whole
    mechanism under test.
    """
    M = np.stack([RC_all[r] for r in RELS])
    ridx = {r: i for i, r in enumerate(RELS)}
    tr = [i for i, x in enumerate(rows)
          if x["rel"] in TRAINED_R and x["ai"] < TRAIN_ALIASES]
    ev_tr = [i for i, x in enumerate(rows)
             if x["rel"] in TRAINED_R and x["ai"] >= MIN_ALIAS - N_EVAL_ALIAS]
    ev_nv = [i for i, x in enumerate(rows) if x["rel"] in HELD_R]
    X = torch.tensor(Z[tr])
    Y = torch.tensor(np.stack([RC_all[rows[i]["rel"]] for i in tr]))
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
            p = hd(torch.tensor(Z[idxs])).numpy()
        p = p / (np.linalg.norm(p, axis=1, keepdims=True) + 1e-9)
        pred = (p @ M.T).argmax(1)
        return float(np.mean([RELS[int(j)] == rows[i]["rel"]
                              for j, i in zip(pred, idxs)]))

    nn_pred = (Z[ev_nv] @ Z[tr].T).argmax(1)
    knn_nv = float(np.mean([rows[tr[int(j)]]["rel"] == rows[i]["rel"]
                            for j, i in zip(nn_pred, ev_nv)]))
    return {"trained_heldout_alias": round(acc(ev_tr), 4),
            "NOVEL_relation": round(acc(ev_nv), 4),
            "novel_1nn_reference": round(knn_nv, 4),
            "n_novel": len(ev_nv), "chance": round(1 / len(RELS), 4)}


def run_arm(name, encode, edim):
    cache = ROOT / "results" / f"exp55_{name}_emb.npz"
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        assert list(z["qtext"]) == QTEXT and list(z["ext"]) == EXT, \
            f"cache misaligned for {name}; delete it"
        Zq, Zl, Ze = z["Zq"], z["Zl"], z["Ze"]
    else:
        print(f"  embedding {len(QTEXT)} questions...", flush=True)
        Zq = encode(QTEXT, "query")
        Zl = encode([LABEL[r] for r in RELS], "doc")
        print(f"  embedding {len(EXT)} external labels...", flush=True)
        Ze = encode(EXT, "doc")
        np.savez(cache, Zq=Zq, Zl=Zl, Ze=Ze, qtext=np.array(QTEXT),
                 ext=np.array(EXT))
    RAW = {r: Zl[i] for i, r in enumerate(RELS)}
    out = {"dim": int(edim), "raw_1024_or_768": identification(Zq, RAW, edim,
                                                               "raw")}
    print(f"\n  {'basis':>26} {'trained':>9} {'NOVEL':>9} {'1-NN nov':>9}")
    r0 = out["raw_1024_or_768"]
    print(f"  {'raw label space':>26} {r0['trained_heldout_alias']:9.4f} "
          f"{r0['NOVEL_relation']:9.4f} {r0['novel_1nn_reference']:9.4f}")
    out["basis"] = {}
    for pool_name, pool in (("corpus", np.stack([RAW[r] for r in TRAINED_R])),
                            ("external13k", Ze)):
        for K in KS:
            if K > len(pool):
                continue
            PC = fit_anchors(pool, K, seed=SEED)
            PC = PC / (np.linalg.norm(PC, axis=1, keepdims=True) + 1e-9)
            C = {r: RAW[r] @ PC.T for r in RELS}
            C = {r: v / (np.linalg.norm(v) + 1e-9) for r, v in C.items()}
            res = identification(Zq, C, K, f"{pool_name}K{K}")
            over = "  <- over-provisioned" if K > len(TRAINED_R) else ""
            out["basis"][f"{pool_name}_K{K}"] = res
            print(f"  {pool_name + ' K=' + str(K):>26} "
                  f"{res['trained_heldout_alias']:9.4f} "
                  f"{res['NOVEL_relation']:9.4f} "
                  f"{res['novel_1nn_reference']:9.4f}{over}", flush=True)
    return out


ARMS = {}
if WHICH in ("m3", "both"):
    print("\n=== ARM: BGE-M3 (current encoder) ===", flush=True)
    e, d = enc_m3()
    ARMS["m3"] = run_arm("m3", e, d)
if WHICH in ("gemma", "both"):
    for mode in ("symmetric", "asymmetric"):
        print(f"\n=== ARM: EmbeddingGemma, {mode} prefixes ===", flush=True)
        e, d = enc_gemma(mode)
        ARMS[f"gemma_{mode}"] = run_arm(f"gemma_{mode}", e, d)

# The PARETO FRONTIER, not a single best cell. Reporting "best NOVEL" picks
# whichever K maximises transfer while hiding what it costs in trained
# accuracy — it crowns M3's corpus_K4 at 0.130 NOVEL without mentioning that
# the same cell scores 0.215 trained. That is the defect this session kept
# finding in its own summary statistics (D159, D161, D162): a statistic that
# selects on one axis and stays silent about the other.
summary = {}
print(f"\n=== Pareto frontier per arm (not dominated on BOTH axes) ===")
for name, a in ARMS.items():
    cells = [("raw", a["raw_1024_or_768"])] + list(a["basis"].items())
    pts = [(k, v["trained_heldout_alias"], v["NOVEL_relation"])
           for k, v in cells]
    front = [p for p in pts
             if not any(q[1] >= p[1] and q[2] >= p[2] and q[1:] != p[1:]
                        for q in pts)]
    front.sort(key=lambda x: -x[1])
    summary[name] = {"pareto": [{"cell": k, "trained": t, "novel": n}
                                for k, t, n in front],
                     "raw_novel": a["raw_1024_or_768"]["NOVEL_relation"]}
    print(f"  {name}:")
    for k, t, n in front:
        print(f"    {k:22s} trained {t:.4f}  NOVEL {n:.4f}")

# and the comparison that actually decides an encoder: matched trained accuracy
TARGET = 0.55
print(f"\n=== at matched trained accuracy (~{TARGET}) ===")
for name, a in ARMS.items():
    cells = [("raw", a["raw_1024_or_768"])] + list(a["basis"].items())
    k, v = min(cells, key=lambda kv:
               abs(kv[1]["trained_heldout_alias"] - TARGET))
    summary[name]["matched"] = {"cell": k,
                                "trained": v["trained_heldout_alias"],
                                "novel": v["NOVEL_relation"]}
    print(f"  {name:22s} {k:18s} trained {v['trained_heldout_alias']:.4f}  "
          f"NOVEL {v['NOVEL_relation']:.4f}")

out = {"manifest": run_manifest(seed=SEED,
                                config={"KS": list(KS), "N_HOLD_REL": N_HOLD_REL,
                                        "MIN_ALIAS": MIN_ALIAS,
                                        "N_SUBJ": N_SUBJ}),
       "n_relations": len(RELS), "n_trained": len(TRAINED_R),
       "n_held_relations": len(HELD_R), "n_questions": len(rows),
       "n_external_pool": len(EXT), "arms": ARMS, "summary": summary,
       "scope": ("Identification-level only: no store walk and NO residual "
                 "thresholds, because thresholds do not transfer across "
                 "representation dimensionality (D125) and an end-to-end "
                 "probe would confound encoder quality with calibration. "
                 "Over-provisioning (K above the corpus relation count) is "
                 "possible ONLY from the external 13,713-label Wikidata pool "
                 "— k-means cannot place more anchors than there are corpus "
                 "labels. Held-out relations never enter head training and "
                 "never move the basis; they get coordinates by projection, "
                 "which is the append-only property under test. The Gemma "
                 "prefix arms exist because that encoder requires asymmetric "
                 "task prefixes while this architecture needs questions and "
                 "labels in one geometry; reporting a Gemma result without "
                 "varying it would measure the prefix choice.")}
(ROOT / "results" / "exp55_encoder_probe.json").write_text(json.dumps(out, indent=1))
print("\n[done] results/exp55_encoder_probe.json")
