"""A7 — codec OOD eval on real Wikipedia sentences (threat #5).

59 real number-bearing sentences (Economy of Japan + Amazon River) through
the FULL shipping pipeline built on the fly: BGE-M3 dense+sparse -> whiten ->
head-tagged sparse slots -> pooler s-vec -> decoder_v2t -> number/entity EM
+ binding, at sigma 0 and 0.5. Labels: regex numbers + spaCy PROPN entities.
In-distribution reference (synthetic register): entity 0.462 / number 0.720 /
binding 0.617.

Usage: .venv/bin/python scripts/probe_ood_codec.py
"""
from __future__ import annotations
import json, re, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, torch
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from codec import whiten as W
from codec.data import Proposition
from codec.decoder import SoftPrefixDecoder, build_sparse_tensors
from codec.evals import fidelity as F
from codec.role_bits import _nlp
from codec.struct_pooler import StructPooler
from codec.structure_channel import MAXLEN

def unit(X): return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)
NUMLIKE = re.compile(r"^\d[\d,.:%-]*$")

sents = json.loads((ROOT / "data" / "ood_sentences_v0.json").read_text())
nlp = _nlp()
props = []
for t in sents:
    doc = nlp(t)
    nums = re.findall(r"\$?\d[\d,]*(?:\.\d+)?%?", t)
    nums = [n for n in nums if len(n.strip('$%')) > 0]
    ents = []
    cur = []
    for tok in doc:
        if tok.pos_ == "PROPN":
            cur.append(tok.text)
        else:
            if cur: ents.append(" ".join(cur)); cur = []
    if cur: ents.append(" ".join(cur))
    props.append(Proposition(text=t, entities=[e for e in ents if e in t],
                             numbers=[n for n in nums if n in t], domain="ood"))

from codec.encode import M3Encoder
enc = M3Encoder()
whitener = W.load(str(ROOT / "results" / "whiten_v0.npz"))
dense, lex = enc.encode(sents, sparse=True)
Z = unit(W.apply(dense, whitener))

# head-tagged sparse rows (inline build_tagged logic)
sp_rows = []
m3tok = enc.model.tokenizer
for t, l in zip(sents, lex):
    toks0 = sorted(l.items(), key=lambda kv: -float(kv[1]))[:24]
    toks = [(m3tok.decode([int(tid)]).strip(), w) for tid, w in toks0]
    toks = [(s_, w) for s_, w in toks if s_]
    doc = nlp(t)
    out_t, out_w = [], []
    for tok_s, wgt in toks:
        tagged = tok_s
        if NUMLIKE.match(tok_s):
            for tk in doc:
                if tk.text == tok_s or tk.text.replace(",", "") == tok_s.replace(",", ""):
                    h = tk.head
                    for _ in range(3):
                        if h.like_num or h.pos_ == "NUM": h = h.head
                        else: break
                    if h is not tk and not NUMLIKE.match(h.text):
                        tagged = f"{tok_s} {h.text}"
                    break
        out_t.append(tagged); out_w.append(float(wgt))
    sp_rows.append({"tokens": out_t, "weights": out_w})

pooler = StructPooler(d_pe=32)
pooler.load_state_dict(torch.load(ROOT / "checkpoints" / "struct_pooler_v2.pt",
                                  map_location="cuda"))
pooler = pooler.to("cuda").eval()
vecs = enc.encode_tokens(sents)
T = torch.zeros(len(sents), MAXLEN, 1024); M = torch.zeros(len(sents), MAXLEN, dtype=torch.bool)
for i, v in enumerate(vecs):
    L = min(len(v), MAXLEN); T[i, :L] = torch.from_numpy(np.asarray(v[:L], dtype=np.float32)); M[i, :L] = True
with torch.no_grad():
    S = pooler(T.to("cuda"), M.to("cuda")).cpu()
del pooler
dec = SoftPrefixDecoder.load(ROOT / "checkpoints" / "decoder_v2t")
sp = build_sparse_tensors(sp_rows, dec.tokenizer, dec.k_sparse, max_sub=6)
bp = F.binding_pairs(props)
rows = []
for sg in (0.0, 0.5):
    rec = F.reconstruct(dec, Z, bs=8, sigma=sg, sp=sp, s=S)
    em = F.em_rates(rec, props)
    b = F.binding_rate(rec, bp)
    rows.append({"sigma": sg, "entity_em": em["entity_em"], "number_em": em["number_em"],
                 "n_entities": em["n_entities"], "n_numbers": em["n_numbers"],
                 "binding": b["binding_rate"]})
    print(f"[OOD σ={sg}] entity={em['entity_em']:.3f} (n={em['n_entities']}) "
          f"number={em['number_em']:.3f} (n={em['n_numbers']}) binding={b['binding_rate']:.3f}")
    if sg == 0.0:
        for p, r in list(zip(props, rec))[:3]:
            print(f"  orig : {p.text[:84]}\n  recon: {r[:84]}")
(ROOT / "results" / "ood_codec_a7.json").write_text(json.dumps(
    {"generated_at": datetime.now(timezone.utc).isoformat(), "n": len(sents),
     "rows": rows, "reference_in_dist": {"entity": 0.462, "number": 0.720,
                                         "binding": 0.617}}, indent=2))
print("[done] results/ood_codec_a7.json")
