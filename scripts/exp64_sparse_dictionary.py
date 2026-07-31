"""A sparse OVERCOMPLETE dictionary as the relation basis (D168's live thread)

D168 closed the basis arc with task-partition alignment as the surviving
account, and left one thread open. If categories live in **superposition** —
more features than dimensions, packed non-orthogonally because axis-alignment
would cap what a space can express — then recovering them wants a **sparse
overcomplete dictionary**, which is what sparse-autoencoder practice uses at
4×–64× expansion. Every K sweep in this project topped out at 256 atoms in
768–1024 dimensions: always *under*complete, so over-provisioning in the sense
superposition means was never actually tested.

D168 also argued a *dense* projection cannot get there: at K ≥ d the span
becomes the whole space, nothing is discarded, and the basis collapses toward
raw label space. That argument is tested here directly rather than asserted —
`dense_random_2048` is exactly that control.

**Two accounts now collide, and this experiment is the contest.**

  * *superposition* — the categories are present but blurred by any dense
    compressive projection; a sparse code **selects** features instead of
    mixing them, so it should recover what k-means smears;
  * *alignment* (D168) — a basis buys generalisation in proportion to how well
    it separates the **task** partition, and an SAE is trained on
    **reconstruction**, which has no access to that partition at all.

**Registered prediction, before running: the sparse dictionary LOSES to
`lda_between`.** D168 measured alignment as the operative variable with
r = −0.90 dose-response, and an unsupervised reconstruction objective cannot
see the partition. I expect it to beat raw space and beat random, and to sit
somewhere near `kmeans_label` — better at representing the space, no better at
separating relations in it. **If it wins, the superposition account is doing
more work than the alignment account and the two need reconciling** — which
would be the more interesting result and is why this is worth running.

The invariant is unchanged: a relation's coordinate is its **label** encoded by
the frozen dictionary, so a relation with zero instances still arrives with
coordinates. Sparsity changes how the axes are chosen and read, never what a
relation's coordinate depends on.

Sparsity is **measured, not assumed** — mean L0 is reported for every cell, so
a dictionary that quietly learned a dense code cannot be mistaken for a sparse
one.

Usage: .venv/bin/python scripts/exp64_sparse_dictionary.py [m3|gemma|both]
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
TRAIN_ALIASES, N_EVAL_ALIAS = 2, 2
EXPANSIONS = (2, 4, 8)                 # atoms = expansion x d
L1S = (1e-3, 3e-3, 1e-2)
SAE_EPOCHS = 150
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
print(f"{len(RELS)} relations ({len(TRAINED_R)} trained), {len(rows)} "
      f"questions, {len(ENTS)} entities", flush=True)

import torch                                                     # noqa: E402
from torch import nn                                             # noqa: E402


def unit(a):
    return a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9)


class SAE(nn.Module):
    """Standard sparse autoencoder: ReLU encoder, unit-norm decoder columns.

    Decoder columns are renormalised after every step. Without it the model
    shrinks h and grows W_d to cheat the L1 penalty, and the reported sparsity
    becomes meaningless — which is why L0 is measured below rather than
    inferred from lambda.
    """

    def __init__(self, d, k):
        super().__init__()
        self.b_d = nn.Parameter(torch.zeros(d))
        self.W_e = nn.Linear(d, k)
        self.W_d = nn.Linear(k, d, bias=False)
        with torch.no_grad():
            self.W_d.weight.copy_(self.W_e.weight.T.contiguous())
            self._renorm()

    def _renorm(self):
        with torch.no_grad():
            w = self.W_d.weight
            w /= (w.norm(dim=0, keepdim=True) + 1e-8)

    def encode(self, x):
        return torch.relu(self.W_e(x - self.b_d))

    def forward(self, x):
        h = self.encode(x)
        return self.W_d(h) + self.b_d, h


def train_sae(X, k, l1, seed=SEED):
    torch.manual_seed(seed)
    d = X.shape[1]
    m = SAE(d, k)
    op = torch.optim.AdamW(m.parameters(), lr=1e-3, weight_decay=0.0)
    Xt = torch.tensor(X)
    for _ in range(SAE_EPOCHS):
        for b in torch.randperm(len(Xt)).split(512):
            op.zero_grad()
            xb = Xt[b]
            xh, h = m(xb)
            loss = ((xh - xb) ** 2).sum(-1).mean() + l1 * h.abs().sum(-1).mean()
            loss.backward()
            op.step()
            m._renorm()
    m.eval()
    with torch.no_grad():
        xh, h = m(Xt)
        rec = 1.0 - (((xh - Xt) ** 2).sum() / (Xt ** 2).sum()).item()
        l0 = float((h > 1e-6).float().sum(-1).mean())
    return m, rec, l0


def identify(Z, C_all, dim):
    """Head trained on TRAINED relations; identification over ALL of them."""
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


ARMS = (["m3"] if WHICH in ("m3", "both") else []) + \
       (["gemma_symmetric"] if WHICH in ("gemma", "both") else [])
OUT = {}
for arm in ARMS:
    z = np.load(ROOT / "results" / f"exp56_{arm}_emb.npz", allow_pickle=True)
    assert list(z["qtext"]) == QTEXT and list(z["ents"]) == ENTS, \
        f"population drift vs exp56 for {arm}"
    Zq, Zl, Zent = z["Zq"], z["Zl"], z["Zent"]
    d = Zq.shape[1]
    RAW = {r: Zl[i] for i, r in enumerate(RELS)}
    L_tr = np.stack([RAW[r] for r in TRAINED_R])
    print(f"\n=== ARM: {arm} (d={d}) ===", flush=True)
    res = {}

    # ---- controls, in-run, must reproduce exp56 -------------------------
    prev = json.loads((ROOT / "results"
                       / "exp56_anchor_strategy.json").read_text())["arms"][arm]
    t, n = identify(Zq, RAW, d)
    res["raw_label_space"] = {"trained": t, "novel": n, "K": d, "l0": d}
    PC = unit(fit_anchors(L_tr, 32, seed=SEED))
    t, n = identify(Zq, {r: unit(RAW[r] @ PC.T) for r in RELS}, 32)
    res["kmeans_label_K32"] = {"trained": t, "novel": n, "K": 32, "l0": 32}
    assert abs(n - prev["kmeans_label_K32"]["novel"]) < 1e-3, \
        f"kmeans control does not reproduce exp56 ({n} vs " \
        f"{prev['kmeans_label_K32']['novel']})"
    groups = [Zq[[i for i, x in enumerate(rows)
                  if x["rel"] == r and x["ai"] < TRAIN_ALIASES]]
              for r in TRAINED_R]
    mus = [g.mean(0) for g in groups if len(g)]
    ns = [len(g) for g in groups if len(g)]
    M_ = np.stack(mus)
    mu = np.average(M_, axis=0, weights=ns)
    D_ = (M_ - mu) * np.sqrt(np.array(ns))[:, None]
    PC = unit(np.linalg.svd(D_, full_matrices=False)[2][:32])
    t, n = identify(Zq, {r: unit(RAW[r] @ PC.T) for r in RELS}, 32)
    res["lda_between_K32"] = {"trained": t, "novel": n, "K": 32, "l0": 32}
    assert abs(n - prev["lda_between_K32"]["novel"]) < 1e-3, \
        f"lda control does not reproduce exp56 ({n} vs " \
        f"{prev['lda_between_K32']['novel']})"
    print(f"  controls reproduce exp56 "
          f"(kmeans {res['kmeans_label_K32']['novel']}, "
          f"lda {res['lda_between_K32']['novel']})", flush=True)

    # D168 claimed a DENSE overcomplete basis collapses toward raw space
    # because nothing is discarded. Tested, not asserted.
    g = np.random.default_rng(SEED).standard_normal((2048, d)).astype(np.float32)
    PC = unit(g)
    t, n = identify(Zq, {r: unit(RAW[r] @ PC.T) for r in RELS}, 2048)
    res["dense_random_2048"] = {"trained": t, "novel": n, "K": 2048,
                                "l0": 2048}
    print(f"  dense_random_2048 (D168's control): trained {t:.4f} "
          f"novel {n:.4f}  vs raw novel "
          f"{res['raw_label_space']['novel']:.4f}", flush=True)

    # ---- the sparse overcomplete dictionaries ---------------------------
    POOL = unit(np.concatenate([Zq, Zent, Zl], 0)).astype(np.float32)
    print(f"  SAE training pool: {len(POOL)} vectors "
          f"(questions + entities + labels)", flush=True)
    print(f"  {'atoms':>7} {'l1':>7} {'recon':>7} {'L0':>7} "
          f"{'trained':>8} {'NOVEL':>8}")
    for ex in EXPANSIONS:
        k = ex * d
        for l1 in L1S:
            m, rec, l0 = train_sae(POOL, k, l1)
            with torch.no_grad():
                H = m.encode(torch.tensor(np.stack([RAW[r] for r in RELS]))
                             ).numpy()
            if not np.isfinite(H).all() or H.sum() == 0:
                print(f"  {k:7d} {l1:7.4f}  degenerate code, skipped")
                continue
            C = {r: unit(H[i]) for i, r in enumerate(RELS)}
            t, n = identify(Zq, C, k)
            lab_l0 = float((H > 1e-6).sum(-1).mean())
            res[f"sae_x{ex}_l1{l1}"] = {"trained": t, "novel": n, "K": k,
                                        "recon": round(rec, 4),
                                        "l0_pool": round(l0, 2),
                                        "l0_labels": round(lab_l0, 2)}
            print(f"  {k:7d} {l1:7.4f} {rec:7.4f} {lab_l0:7.2f} "
                  f"{t:8.4f} {n:8.4f}", flush=True)
    OUT[arm] = res

print("\n=== best sparse dictionary vs the controls ===")
verdicts = {}
for arm, res in OUT.items():
    sae = {k: v for k, v in res.items() if k.startswith("sae_")}
    if not sae:
        continue
    best = max(sae, key=lambda k: sae[k]["novel"])
    b = sae[best]
    lda = res["lda_between_K32"]["novel"]
    km = res["kmeans_label_K32"]["novel"]
    raw = res["raw_label_space"]["novel"]
    dr = res["dense_random_2048"]["novel"]
    print(f"\n  {arm}:")
    print(f"    raw label space          {raw:.4f}")
    print(f"    dense_random_2048        {dr:.4f}   (D168's collapse control)")
    print(f"    kmeans_label K=32        {km:.4f}")
    print(f"    lda_between K=32         {lda:.4f}   <- champion")
    print(f"    best sparse ({best})  {b['novel']:.4f}   "
          f"L0={b['l0_labels']}, recon={b['recon']}")
    verdicts[arm] = {"best_sae": best, "best_sae_novel": b["novel"],
                     "vs_lda": round(b["novel"] - lda, 4),
                     "vs_kmeans": round(b["novel"] - km, 4),
                     "vs_raw": round(b["novel"] - raw, 4),
                     "dense_overcomplete_vs_raw": round(dr - raw, 4)}
    print(f"    -> vs lda {verdicts[arm]['vs_lda']:+.4f}, "
          f"vs kmeans {verdicts[arm]['vs_kmeans']:+.4f}, "
          f"vs raw {verdicts[arm]['vs_raw']:+.4f}")

mv = float(np.mean([v["vs_lda"] for v in verdicts.values()])) if verdicts else 0.0
mc = float(np.mean([v["dense_overcomplete_vs_raw"]
                    for v in verdicts.values()])) if verdicts else 0.0
if mv > 0.02:
    verdict = (f"SPARSE WINS — the overcomplete dictionary beats lda_between "
               f"by {mv:+.4f}. The superposition account does work the "
               f"alignment account does not, and the two need reconciling: "
               f"an unsupervised reconstruction objective has no access to "
               f"the task partition, yet outperformed a supervised one.")
elif mv > -0.02:
    verdict = (f"PARITY — sparse and lda_between are within noise "
               f"({mv:+.4f}). Sparsity is not obviously the missing "
               f"instrument, and the cheaper supervised basis should be "
               f"preferred.")
else:
    verdict = (f"SPARSE LOSES — {mv:+.4f} against lda_between, as predicted. "
               f"An SAE optimises RECONSTRUCTION and D168 established that "
               f"generalisation tracks TASK-PARTITION alignment, which "
               f"reconstruction cannot see. Superposition may be true of the "
               f"space and still not tell you how to pick a basis for a task.")
print(f"\n  D168's dense-overcomplete claim: dense_random_2048 minus raw = "
       f"{mc:+.4f} (near zero confirms the collapse argument)")
print(f"\n=== VERDICT ===\n  {verdict}")

out = {"manifest": run_manifest(seed=SEED,
                                config={"EXPANSIONS": list(EXPANSIONS),
                                        "L1S": list(L1S),
                                        "SAE_EPOCHS": SAE_EPOCHS,
                                        "N_HOLD_REL": N_HOLD_REL}),
       "n_relations": len(RELS), "n_trained": len(TRAINED_R),
       "chance": round(1 / len(RELS), 4),
       "arms": OUT, "verdicts": verdicts, "verdict": verdict,
       "registered_prediction": (
           "the sparse dictionary LOSES to lda_between, because an SAE "
           "optimises reconstruction and D168 measured task-partition "
           "alignment as the operative variable with r=-0.90; expected to "
           "beat raw and random and sit near kmeans_label. If it WINS, the "
           "superposition account is doing more work than the alignment "
           "account and they need reconciling."),
       "scope": ("Tests the one thread D168 left open: superposed categories "
                 "want a sparse OVERCOMPLETE dictionary, and every K sweep in "
                 "this project was undercomplete (max 256 atoms in 768-1024 "
                 "dimensions). Coordinates are the relation's LABEL encoded "
                 "by the frozen dictionary, so zero-instance arrival is "
                 "preserved exactly as in every other basis strategy. "
                 "Sparsity is MEASURED as mean L0 over the label codes, not "
                 "inferred from the L1 weight, and decoder columns are "
                 "renormalised each step so the penalty cannot be gamed by "
                 "shrinking h. Both dense controls reproduce exp56 in-run or "
                 "the script aborts (D158). dense_random_2048 tests D168's "
                 "own assertion that a dense overcomplete projection "
                 "collapses toward raw label space. Identification level "
                 "only — and D169 showed identification results do not "
                 "transfer to the pipeline, so nothing here is a "
                 "recommendation until gated.")}
(ROOT / "results" / "exp64_sparse_dictionary.json").write_text(
    json.dumps(out, indent=1))
print("\n[done] results/exp64_sparse_dictionary.json")
