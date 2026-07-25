"""A2 — frame-only cycle: does the gist carry the FRAME, or just the topic?

The adversary's falsification design (threat #4): decode under (i) true gist,
(ii) same-domain WRONG gist, (iii) null gist — all with true symbols — then
MASK identities to placeholders in recon and reference before comparing, so
identity anchoring cannot fake frame preservation. Metrics: masked-cycle cos
(encode masked recon vs masked reference) and predicate-word EM (content
words that are NOT identity tokens).

If (i) ~= (ii): gist = topic only; D24/D28 rhetoric gets cut back.
If (i) >> (ii): the frame claim survives an identity-clean instrument.

Usage: .venv/bin/python scripts/probe_frame_cycle.py
"""
from __future__ import annotations
import json, re, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, torch
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from codec import data as D_, whiten as W
from codec.decoder import SoftPrefixDecoder, build_sparse_tensors
from codec.evals import fidelity as F

def unit(X): return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)

STOP = set("the a an of to in on at by for with from was were is are that it its "
           "and or as this these those has have had be been will".split())

def mask_ids(text, props_row):
    t = text
    for k, e in enumerate(sorted(props_row.entities, key=len, reverse=True)):
        t = t.replace(e, f"ENTITY{k}")
    for k, n in enumerate(sorted(props_row.numbers, key=len, reverse=True)):
        t = t.replace(n, f"NUM{k}")
    t = re.sub(r"\d[\d,.:]*", "NUMX", t)      # any residual digits
    return t

def pred_words(text, props_row):
    masked = mask_ids(text, props_row).lower()
    return {w for w in re.findall(r"[a-z][a-z-]+", masked)
            if w not in STOP and len(w) > 2 and not w.startswith(("entity", "num"))}

clean = [D_.Proposition(**json.loads(l)) for l in
         (ROOT / "data" / "clean_v0.jsonl").read_text().splitlines() if l.strip()]
whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
Z = unit(W.apply(np.load(ROOT / "results" / "dense_v0.npy"), whitener))
sparse_rows = json.loads((ROOT / "results" / "sparse_tagged_v0.json").read_text())
S_all = np.load(ROOT / "results" / "s_vecs_v0.npy")
_, eval_p = D_.split(clean, eval_frac=0.1)
ek = {p.text for p in eval_p}
is_ev = np.array([p.text in ek for p in clean])
N = 200
P_ev = [p for p in clean if p.text in ek][:N]
Z_ev = Z[is_ev][:N]
domains = np.array([p.domain for p in P_ev])
all_ev_Z = Z[is_ev]
all_ev_P = [p for p in clean if p.text in ek]

# same-domain WRONG gist: another eval prop from the same domain
rng = np.random.default_rng(0)
wrong = np.zeros_like(Z_ev)
for i, p in enumerate(P_ev):
    pool = [j for j, q in enumerate(all_ev_P) if q.domain == p.domain
            and q.text != p.text]
    wrong[i] = all_ev_Z[rng.choice(pool)]

dec = SoftPrefixDecoder.load(ROOT / "checkpoints" / "decoder_v2t")
sp = build_sparse_tensors([r for r, e in zip(sparse_rows, is_ev) if e][:N],
                          dec.tokenizer, dec.k_sparse, max_sub=6)
s = torch.from_numpy(S_all[is_ev][:N]).float()
conds = {"true_gist": Z_ev, "same_domain_wrong": wrong,
         "null_gist": np.zeros_like(Z_ev)}
recs = {k: F.reconstruct(dec, v, bs=16, sp=sp, s=s) for k, v in conds.items()}
del dec; torch.cuda.empty_cache()

from codec.encode import M3Encoder
m3 = M3Encoder()
ref_masked = [mask_ids(p.text, p) for p in P_ev]
dref, _ = m3.encode(ref_masked, sparse=False)
Zref = unit(W.apply(dref, whitener))
out_rows = []
for k, rec in recs.items():
    rm = [mask_ids(r, p) for r, p in zip(rec, P_ev)]
    dr, _ = m3.encode(rm, sparse=False)
    Zr = unit(W.apply(dr, whitener))
    cyc = float(np.einsum("ij,ij->i", Zr, Zref).mean())
    pw = []
    for r, p in zip(rec, P_ev):
        ref_w, rec_w = pred_words(p.text, p), pred_words(r, p)
        pw.append(len(ref_w & rec_w) / max(len(ref_w), 1))
    out_rows.append({"cond": k, "masked_cycle": cyc,
                     "predicate_recall": float(np.mean(pw))})
    print(f"[{k:>18}] masked-cycle={cyc:.3f} predicate-recall={np.mean(pw):.3f}")

d = out_rows[0]["masked_cycle"] - out_rows[1]["masked_cycle"]
print(f"[verdict] true-vs-wrong-gist masked-cycle gap = {d:+.3f} "
      + ("— gist carries FRAME beyond topic" if d > 0.05 else
         "— gist is ~topic-only; cut back D24/D28 rhetoric"))
(ROOT / "results" / "frame_cycle_a2.json").write_text(json.dumps(
    {"generated_at": datetime.now(timezone.utc).isoformat(), "n": N,
     "rows": out_rows, "gap": d}, indent=2))
print("[done] results/frame_cycle_a2.json")
