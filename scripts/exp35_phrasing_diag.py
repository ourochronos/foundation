"""Where does the phrasing failure live — encoder or head? (D129)

D127 found phrasing is the dominant failure (−0.719 for an unseen alias of a
KNOWN relation). D128 refuted the obvious fix. The standing assumption is
that the frozen encoder's paraphrase geometry is the ceiling, which would
make fine-tuning it the next move — an expensive, hard-to-reverse step.

That assumption has never been tested. Three cheap diagnostics settle it, and
they attribute the failure to a specific component:

  1. ENCODER GEOMETRY. Embed the same question rendered with different
     aliases of the same relation. Measure within-relation similarity against
     between-relation similarity. If within ≈ between, the encoder genuinely
     does not separate paraphrases and fine-tuning is the honest answer.

  2. NEAREST-NEIGHBOUR, NO HEAD AT ALL. For a held-out-alias question, find
     the closest TRAINING question in embedding space and take its relation.
     This uses the encoder and nothing else. If it works, the information is
     present in the embedding and the head is what is failing to use it —
     which fine-tuning would not fix.

  3. ALIAS-COUNT ABLATION. Train the head on 1, 2, 3, 4 aliases per relation
     and evaluate on held-out ones. D127/D128 both trained on exactly two. If
     the curve is still climbing at four, the fix is more surface forms per
     relation, not a different encoder.

Only if (1) shows poor geometry AND (2) fails AND (3) is flat is fine-tuning
the indicated next step.

Usage: .venv/bin/python scripts/exp35_phrasing_diag.py
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
from codec.manifest import run_manifest, wilson_ci               # noqa: E402
from foundation.kb import KB                                     # noqa: E402

SEED, MIN_ALIAS, N_SUBJ = 0, 6, 60
N_EVAL_ALIAS = 2

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
print(f"{len(RELS)} relations with >= {MIN_ALIAS} usable aliases")
print("  " + "; ".join(f"{LABEL[r]}: {ALIAS[r][:3]}..." for r in RELS[:3]))

gold = collections.defaultdict(set)
for c in wiki:
    if c["pid"] in LABEL:
        gold[(c["subject"], c["pid"])].add(c["object"])
by_rel = collections.defaultdict(list)
for (s, r) in sorted(gold):
    by_rel[r].append(s)
rng = np.random.default_rng(SEED)
SUBJ = {}
for r in RELS:
    xs = by_rel[r]
    SUBJ[r] = ([xs[i] for i in sorted(rng.choice(len(xs), N_SUBJ,
                                                 replace=False))]
               if len(xs) > N_SUBJ else xs)

rows = []
for r in RELS:
    for ai, a in enumerate(ALIAS[r]):
        for s in SUBJ[r]:
            rows.append({"rel": r, "ai": ai, "subject": s,
                         "text": f"What is the {a} of {s}?",
                         "answers": sorted(gold[(s, r)])})
print(f"{len(rows)} questions ({MIN_ALIAS} aliases x <= {N_SUBJ} subjects "
      f"x {len(RELS)} relations)", flush=True)

cache = ROOT / "results" / "exp35_emb.npz"
if cache.exists():
    z = np.load(cache, allow_pickle=True)
    assert list(z["texts"]) == [r["text"] for r in rows], "cache misaligned"
    Z, Zl = z["Z"], z["Zl"]
else:
    Z = P.unit(P.embed_texts([r["text"] for r in rows]))
    Zl = P.unit(P.embed_texts([LABEL[r] for r in RELS]))
    np.savez(cache, Z=Z, Zl=Zl,
             texts=np.array([r["text"] for r in rows]))
RC = {r: Zl[i] for i, r in enumerate(RELS)}
print(f"embeddings {Z.shape}", flush=True)

# ---------------------------------------------------------------------------
# 1. ENCODER GEOMETRY — does the encoder separate paraphrases by relation?
# ---------------------------------------------------------------------------
idx_of = collections.defaultdict(list)
for i, r in enumerate(rows):
    idx_of[(r["rel"], r["ai"])].append(i)
# same subject, different alias, same relation  vs  same subject, different
# relation — holding the subject fixed removes entity content from both
subj_rows = collections.defaultdict(list)
for i, r in enumerate(rows):
    subj_rows[r["subject"]].append(i)
within, between = [], []
for s, ids in subj_rows.items():
    for i in ids:
        for j in ids:
            if i >= j:
                continue
            c = float(Z[i] @ Z[j])
            (within if rows[i]["rel"] == rows[j]["rel"]
             else between).append(c)
print("\n1. ENCODER GEOMETRY (subject held fixed)")
print(f"   same relation, different alias : mean {np.mean(within):.3f}  "
      f"p10 {np.percentile(within, 10):.3f}   (n={len(within)})")
print(f"   different relation             : mean {np.mean(between):.3f}  "
      f"p90 {np.percentile(between, 90):.3f}   (n={len(between)})")
gap = float(np.mean(within) - np.mean(between))
print(f"   separation {gap:+.3f}  -> "
      f"{'encoder DOES separate paraphrases' if gap > 0.05 else 'encoder does NOT separate'}")

# ---------------------------------------------------------------------------
# 2. NEAREST NEIGHBOUR, NO HEAD — is the information already in the embedding?
# ---------------------------------------------------------------------------
TRAIN_AI = list(range(MIN_ALIAS - N_EVAL_ALIAS))
EVAL_AI = list(range(MIN_ALIAS - N_EVAL_ALIAS, MIN_ALIAS))
tr = [i for i, r in enumerate(rows) if r["ai"] in TRAIN_AI]
ev = [i for i, r in enumerate(rows) if r["ai"] in EVAL_AI]
Ztr = Z[tr]
hit = 0
B = 512
for a in range(0, len(ev), B):
    chunk = ev[a:a + B]
    S = Z[chunk] @ Ztr.T
    nn = S.argmax(1)
    for k, i in enumerate(chunk):
        hit += rows[tr[int(nn[k])]]["rel"] == rows[i]["rel"]
nn_acc = hit / len(ev)
lo_nn, hi_nn = wilson_ci(hit, len(ev))
print("\n2. NEAREST-NEIGHBOUR RELATION ID (encoder only, no head)")
print(f"   held-out-alias questions matched to a TRAINING question: "
      f"{nn_acc:.3f}  CI95 [{lo_nn:.3f}, {hi_nn:.3f}]  (n={len(ev)}, "
      f"chance {1/len(RELS):.3f})")
print(f"   -> {'information IS in the embedding; the HEAD is the bottleneck' if nn_acc > 0.6 else 'information is not recoverable from the embedding'}")

# ---------------------------------------------------------------------------
# 3. ALIAS-COUNT ABLATION — is the fix simply more surface forms?
# ---------------------------------------------------------------------------
import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402

print("\n3. ALIAS-COUNT ABLATION (head trained on N aliases/relation)")
print(f"   {'N':>3} {'held-out alias top-1':>21} {'train alias':>12}")
abl = {}
for N in (1, 2, 3, 4):
    tri = [i for i, r in enumerate(rows) if r["ai"] < N]
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
    M = np.stack([RC[r] for r in RELS])
    ri = {r: i for i, r in enumerate(RELS)}

    def acc(ids):
        with torch.no_grad():
            pr = hd(torch.tensor(Z[ids])).numpy()
        pr = pr / (np.linalg.norm(pr, axis=1, keepdims=True) + 1e-9)
        pred = (pr @ M.T).argmax(1)
        return float(np.mean([RELS[int(pred[k])] == rows[i]["rel"]
                              for k, i in enumerate(ids)]))

    a_ev, a_tr = acc(ev), acc(tri)
    abl[N] = {"held_out_alias": round(a_ev, 4), "train_alias": round(a_tr, 4)}
    print(f"   {N:3d} {a_ev:21.3f} {a_tr:12.3f}", flush=True)

slope = abl[4]["held_out_alias"] - abl[2]["held_out_alias"]
print(f"   2 -> 4 aliases: {slope:+.3f}  -> "
      f"{'still climbing; MORE ALIASES is the fix' if slope > 0.05 else 'flat; more aliases will not fix it'}")

verdict = ("head/data" if nn_acc > 0.6 else "encoder")
print(f"\nVERDICT: the bottleneck is the {verdict.upper()}."
      f"  Fine-tuning the encoder is "
      f"{'NOT indicated' if verdict == 'head/data' else 'indicated'}.")

out = {
    "manifest": run_manifest(seed=SEED, config={"MIN_ALIAS": MIN_ALIAS,
                                                "N_SUBJ": N_SUBJ}),
    "n_relations": len(RELS), "n_questions": len(rows),
    "encoder_geometry": {"within_mean": float(np.mean(within)),
                         "between_mean": float(np.mean(between)),
                         "separation": round(gap, 4)},
    "nearest_neighbour_relation_id": {"acc": round(nn_acc, 4),
                                      "ci95": [round(lo_nn, 4),
                                               round(hi_nn, 4)],
                                      "chance": round(1 / len(RELS), 4)},
    "alias_count_ablation": abl,
    "verdict": verdict,
    "scope": ("Depth-1 only, because D127 showed composition is not the "
              "problem. Subject is held fixed in the geometry test so entity "
              "content cannot inflate similarity. The nearest-neighbour test "
              "uses no trained parameters at all, which is what makes it an "
              "encoder-versus-head attribution rather than another accuracy."),
}
(ROOT / "results" / "exp35_phrasing_diag.json").write_text(json.dumps(out,
                                                                      indent=1))
print("\n[done] results/exp35_phrasing_diag.json")

# ---------------------------------------------------------------------------
# 4. The head gets 0.614 where nearest-neighbour gets 0.943. A trained
# parametric map is DESTROYING information that a trivial baseline preserves.
# That is not a tuning problem, it is the wrong component — so test the
# alternatives that need no parametric head at all.
#
#   4a  k-NN regression: predict the target as the mean of the k nearest
#       TRAINING questions' targets. Non-parametric, and adding a relation
#       means adding rows rather than retraining — which is the project's own
#       reindex-free thesis applied to the head.
#   4b  direct label scoring: score the question against each relation's LABEL
#       embedding. Zero parameters, zero training rows, and the only option
#       that can work for a relation with no training questions at all (D125).
# ---------------------------------------------------------------------------
M = np.stack([RC[r] for r in RELS])
tri2 = [i for i, r in enumerate(rows) if r["ai"] < 2]      # D127's regime
Ztr2 = Z[tri2]
Ytr2 = np.stack([RC[rows[i]["rel"]] for i in tri2])

print("\n4. ALTERNATIVES TO THE PARAMETRIC HEAD (trained on 2 aliases)")
alt = {}
for k in (1, 5, 20):
    hit = 0
    for a in range(0, len(ev), B):
        chunk = ev[a:a + B]
        S = Z[chunk] @ Ztr2.T
        top = np.argpartition(-S, k, axis=1)[:, :k]
        for m, i in enumerate(chunk):
            pred = P.unit(Ytr2[top[m]].mean(0))
            hit += RELS[int((pred @ M.T).argmax())] == rows[i]["rel"]
    a_ = hit / len(ev)
    alt[f"knn_k{k}"] = round(a_, 4)
    print(f"   k-NN regression, k={k:<3d}      held-out alias top-1 {a_:.3f}")

hit = 0
for a in range(0, len(ev), B):
    chunk = ev[a:a + B]
    S = Z[chunk] @ M.T
    pred = S.argmax(1)
    for m, i in enumerate(chunk):
        hit += RELS[int(pred[m])] == rows[i]["rel"]
lab_acc = hit / len(ev)
alt["direct_label_scoring"] = round(lab_acc, 4)
lo_l, hi_l = wilson_ci(hit, len(ev))
print(f"   direct label scoring        held-out alias top-1 {lab_acc:.3f}  "
      f"CI95 [{lo_l:.3f}, {hi_l:.3f}]   (zero parameters)")
print(f"   trained head (2 aliases)    held-out alias top-1 "
      f"{abl[2]['held_out_alias']:.3f}")
print(f"   nearest neighbour           held-out alias top-1 {nn_acc:.3f}")

best_alt = max(alt, key=alt.get)
print(f"\n   best non-parametric option: {best_alt} at {alt[best_alt]:.3f} "
      f"vs the head's {abl[2]['held_out_alias']:.3f} "
      f"({alt[best_alt] - abl[2]['held_out_alias']:+.3f})")
out["alternatives_to_head"] = alt
out["head_baseline_2alias"] = abl[2]["held_out_alias"]
(ROOT / "results" / "exp35_phrasing_diag.json").write_text(json.dumps(out,
                                                                      indent=1))
print("[done] alternatives appended")
