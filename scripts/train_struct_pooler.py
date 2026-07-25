"""Train the structural pooler and test binding-transfer to held-out types.

Two split configurations (--split):
  v1  minimal preserve coverage (active_passive, synonym_swap, clause_reorder);
      formality_shift + paraphrase held out — answered the TRANSFER question
      (D17) at the cost of the formality ordering defect (D18).
  v2  ALL v1-era preserving types trained (the D18 fix); the fresh holdout is
      cleft_construction, nominalization, contraction_expansion — generated
      after v1 shipped, so transfer-to-unseen-preserve stays measurable.

Controls: random-init pooler baseline (architecture-only null). Early stopping
on a validation slice of TRAINED types only; held-out types scored once.

Usage: .venv/bin/python scripts/train_struct_pooler.py [--split v2 --tag v2]
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec.struct_pooler import StructPooler, pooler_loss   # noqa: E402

_COMMON = dict(
    train_invert=["argument_swap", "location_swap", "quantity_double",
                  "negation", "comparative_flip"],
    held_structural=["causal_reverse", "date_shift"],
    held_marked=["tense_shift", "hedge"],
    held_valence=["presence_absence", "success_failure", "approval_rejection",
                  "superlative_flip", "quantifier_change", "increase_decrease"],
)
SPLITS = {
    "v1": {**_COMMON,
           "train_preserve": ["active_passive", "synonym_swap", "clause_reorder"],
           "held_preserve": ["formality_shift", "paraphrase"]},
    "v2": {**_COMMON,
           "train_preserve": ["active_passive", "synonym_swap", "clause_reorder",
                              "formality_shift", "paraphrase"],
           "held_preserve": ["cleft_construction", "nominalization",
                             "contraction_expansion"]},
}

CACHE = ROOT / "results" / "token_vecs.npz"
MAXLEN = 64
N_CORPUS = 1500


def load_pairs():
    by_rel = {}
    for f in sorted((ROOT / "data" / "relations").glob("prop_*.jsonl")):
        rows, seen = [], set()
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            o = json.loads(line)
            if o["x"].lower() in seen:
                continue
            seen.add(o["x"].lower())
            rows.append(o)
        if rows:
            by_rel[rows[0]["relation"]] = rows
    return by_rel


def build_token_cache(texts: list[str]) -> None:
    from codec.encode import M3Encoder
    enc = M3Encoder()
    vecs = enc.encode_tokens(texts)
    del enc
    torch.cuda.empty_cache()
    n = len(texts)
    d = vecs[0].shape[1]
    T = np.zeros((n, MAXLEN, d), dtype=np.float16)
    M = np.zeros((n, MAXLEN), dtype=bool)
    for i, v in enumerate(vecs):
        L = min(len(v), MAXLEN)
        T[i, :L] = v[:L]
        M[i, :L] = True
    np.savez(CACHE, T=T, M=M, texts=np.array(texts))
    print(f"[cache] token vectors {T.shape} -> {CACHE}")


def test_mask(rows):
    return np.array([int.from_bytes(hashlib.sha256(r["x"].encode()).digest()[:4],
                                    "big") < 0.2 * 2**32 for r in rows])


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="v2", choices=sorted(SPLITS))
    ap.add_argument("--tag", default=None, help="checkpoint tag (default: split)")
    ap.add_argument("--d-pe", type=int, default=32,
                    help="0 = no position features (the v0 set-function ablation)")
    args = ap.parse_args()
    args.tag = args.tag or args.split
    sp = SPLITS[args.split]
    TRAIN_INVERT, TRAIN_PRESERVE = sp["train_invert"], sp["train_preserve"]
    HELD_STRUCTURAL, HELD_MARKED = sp["held_structural"], sp["held_marked"]
    HELD_VALENCE, HELD_PRESERVE = sp["held_valence"], sp["held_preserve"]

    rng = np.random.default_rng(0)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    by_rel = load_pairs()

    clean = [json.loads(l) for l in
             (ROOT / "data" / "clean_v0.jsonl").read_text().splitlines() if l.strip()]
    corpus_sel = rng.permutation(len(clean))[:N_CORPUS]
    corpus_texts = [clean[i]["text"] for i in corpus_sel]
    domains = np.array([clean[i]["domain"] for i in corpus_sel])

    texts, tindex = [], {}
    for rel, rows in sorted(by_rel.items()):
        for r in rows:
            for side in ("x", "y"):
                t = r[side]
                if t not in tindex:
                    tindex[t] = len(texts)
                    texts.append(t)
    for t in corpus_texts:
        if t not in tindex:
            tindex[t] = len(texts)
            texts.append(t)

    if not CACHE.exists() or list(np.load(CACHE, allow_pickle=True)["texts"]) != texts:
        print(f"[encode] extracting token vectors for {len(texts)} texts")
        build_token_cache(texts)
    z = np.load(CACHE, allow_pickle=True)
    T = torch.from_numpy(z["T"].astype(np.float32))
    M = torch.from_numpy(z["M"])
    print(f"[data] {len(texts)} texts tokenized, cache {tuple(T.shape)}")

    def pair_ids(rel, split):
        rows = by_rel[rel]
        m = test_mask(rows)
        keep = [r for r, t in zip(rows, m) if (t if split == "test" else not t)]
        xi = torch.tensor([tindex[r["x"]] for r in keep])
        yi = torch.tensor([tindex[r["y"]] for r in keep])
        return xi, yi

    def cat_ids(rels, split):
        xs, ys = zip(*[pair_ids(r, split) for r in rels])
        return torch.cat(xs), torch.cat(ys)

    xi_tr, yi_tr = cat_ids(TRAIN_INVERT, "train")
    xp_tr, yp_tr = cat_ids(TRAIN_PRESERVE, "train")
    # validation = slice of TRAIN-split (held-out categories never touched)
    n_vi, n_vp = len(xi_tr) // 6, len(xp_tr) // 6
    vi = (xi_tr[:n_vi], yi_tr[:n_vi]); xi_tr, yi_tr = xi_tr[n_vi:], yi_tr[n_vi:]
    vp = (xp_tr[:n_vp], yp_tr[:n_vp]); xp_tr, yp_tr = xp_tr[n_vp:], yp_tr[n_vp:]
    neg_pool = torch.tensor([tindex[t] for t in corpus_texts])
    print(f"[pairs] train invert={len(xi_tr)} preserve={len(xp_tr)} "
          f"val={n_vi}+{n_vp} negpool={len(neg_pool)}")

    pooler = StructPooler(d_pe=args.d_pe).to(dev)

    def s_of(ids: torch.Tensor, model, bs: int = 256) -> torch.Tensor:
        outs = []
        with torch.no_grad():
            model.eval()
            for i in range(0, len(ids), bs):
                b = ids[i:i + bs]
                outs.append(model(T[b].to(dev), M[b].to(dev)).cpu())
        return torch.cat(outs)

    def mag(model, rels, split="test"):
        out = {}
        for rel in rels:
            xi, yi = pair_ids(rel, split)
            sx, sy = s_of(xi, model), s_of(yi, model)
            out[rel] = float((sx * sy).sum(-1).mean())
        return out

    # random-init control before training
    null_mags = mag(pooler, list(by_rel))

    opt = torch.optim.AdamW(pooler.parameters(), lr=3e-4, weight_decay=0.05)
    g = torch.Generator().manual_seed(0)
    best_val, best_state, patience = -1e9, None, 0
    for step in range(1, 801):
        pooler.train()
        idx = torch.randint(0, len(xi_tr), (64,), generator=g)
        bxi, byi = xi_tr[idx], yi_tr[idx]
        idxp = torch.randint(0, len(xp_tr), (64,), generator=g)
        bxp, byp = xp_tr[idxp], yp_tr[idxp]
        bn = neg_pool[torch.randint(0, len(neg_pool), (128,), generator=g)]

        def fwd(ids):
            return pooler(T[ids].to(dev), M[ids].to(dev))

        loss, logs = pooler_loss(fwd(bxi), fwd(byi), fwd(bxp), fwd(byp), fwd(bn))
        opt.zero_grad(); loss.backward(); opt.step()

        if step % 50 == 0:
            svx, svy = s_of(vi[0], pooler), s_of(vi[1], pooler)
            spx, spy = s_of(vp[0], pooler), s_of(vp[1], pooler)
            v_sep = float((spx * spy).sum(-1).mean() - (svx * svy).sum(-1).mean())
            print(f"[train] {step} loss={logs['loss']:.4f} inv={logs['inv']:.3f} "
                  f"pre={logs['pre']:.3f} val_sep={v_sep:.3f}", flush=True)
            if v_sep > best_val + 1e-3:
                best_val, patience = v_sep, 0
                best_state = {k: v.detach().clone() for k, v in pooler.state_dict().items()}
            else:
                patience += 1
                if patience >= 4:
                    print(f"[early-stop] step {step}")
                    break
    if best_state:
        pooler.load_state_dict(best_state)

    # ---------- evaluation ----------
    trained_mags = mag(pooler, list(by_rel))
    print(f"\n{'type':>18} {'role':>15}  random-init -> trained (s-space cos)")
    roles = {}
    for rel in sorted(by_rel):
        role = ("train-invert" if rel in TRAIN_INVERT else
                "train-preserve" if rel in TRAIN_PRESERVE else
                "HELD-structural" if rel in HELD_STRUCTURAL else
                "HELD-marked" if rel in HELD_MARKED else
                "HELD-valence" if rel in HELD_VALENCE else
                "HELD-preserve")
        roles[rel] = role
        print(f"{rel:>18} {role:>15}  {null_mags[rel]:.3f} -> {trained_mags[rel]:.3f}")

    def rmean(role):
        v = [trained_mags[r] for r in trained_mags if roles.get(r) == role]
        return float(np.mean(v)) if v else float("nan")

    sums = {r: rmean(r) for r in ["train-invert", "train-preserve", "HELD-structural",
                                   "HELD-marked", "HELD-valence", "HELD-preserve"]}
    print("\n[means]", {k: round(v, 3) for k, v in sums.items()})

    # non-degeneracy: spread + domain purity in s-space
    s_corpus = s_of(neg_pool, pooler).numpy()
    Gs = s_corpus @ s_corpus.T
    np.fill_diagonal(Gs, -np.inf)
    nn = np.argpartition(-Gs, 10, axis=1)[:, :10]
    purity = float(np.mean([np.mean(domains[nn[i]] == domains[i])
                            for i in range(len(domains))]))
    iu = np.triu_indices(len(s_corpus), k=1)
    spread = float(np.abs((s_corpus @ s_corpus.T)[iu]).mean())
    print(f"[s-space] mean|cos| random props={spread:.3f} | domain purity@10={purity:.3f}")

    generalizes = (sums["HELD-structural"] < sums["HELD-preserve"] - 0.10)
    verdict = ("BINDING TRANSFERS — held-out structural types separate in s-space"
               if generalizes else
               "no transfer to held-out structural types")
    print(f"[verdict] {verdict}")

    torch.save(pooler.state_dict(), ROOT / "checkpoints" / f"struct_pooler_{args.tag}.pt")
    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "d_pe": args.d_pe, "split": args.split,
           "splits": {"train_invert": TRAIN_INVERT, "train_preserve": TRAIN_PRESERVE,
                      "held_structural": HELD_STRUCTURAL, "held_marked": HELD_MARKED,
                      "held_valence": HELD_VALENCE, "held_preserve": HELD_PRESERVE},
           "random_init": null_mags, "trained": trained_mags, "role_means": sums,
           "s_spread": spread, "s_domain_purity": purity, "verdict": verdict}
    (ROOT / "results" / f"struct_pooler_{args.tag}.json").write_text(json.dumps(out, indent=2))
    print(f"[done] results/struct_pooler_{args.tag}.json")


if __name__ == "__main__":
    main()
