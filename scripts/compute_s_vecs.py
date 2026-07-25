"""Compute structure s-vectors for every corpus proposition (codec v2 input).

s = StructPooler_v2( BGE-M3 ColBERT token vectors ), 192-d unit rows, saved to
results/s_vecs_v0.npy row-aligned with data/clean_v0.jsonl. Token vectors are
transient (chunked) — only the pooled s survives, so the cache is 12MB, not
2GB. Meta sidecar keys the cache on the text list and the pooler checkpoint;
mismatch on either forces a rebuild.

Usage: .venv/bin/python scripts/compute_s_vecs.py [--pooler-tag v2]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec.struct_pooler import StructPooler        # noqa: E402
from codec.structure_channel import MAXLEN          # noqa: E402

OUT = ROOT / "results" / "s_vecs_v0.npy"
META = ROOT / "results" / "s_vecs_v0.meta.json"


def fingerprint(texts: list[str], ckpt: Path) -> str:
    h = hashlib.sha256()
    for t in texts:
        h.update(t.encode())
    h.update(ckpt.read_bytes())
    return h.hexdigest()[:16]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pooler-tag", default="v2")
    ap.add_argument("--chunk", type=int, default=512)
    args = ap.parse_args()

    texts = [json.loads(l)["text"] for l in
             (ROOT / "data" / "clean_v0.jsonl").read_text().splitlines() if l.strip()]
    ckpt = ROOT / "checkpoints" / f"struct_pooler_{args.pooler_tag}.pt"
    fp = fingerprint(texts, ckpt)

    if OUT.exists() and META.exists():
        meta = json.loads(META.read_text())
        if meta.get("fingerprint") == fp:
            print(f"[cache] s_vecs_v0.npy current ({len(texts)} rows, {fp})")
            return
        print(f"[cache] stale ({meta.get('fingerprint')} != {fp}) — recomputing")

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    pooler = StructPooler(d_pe=32)
    pooler.load_state_dict(torch.load(ckpt, map_location=dev))
    pooler = pooler.to(dev).eval()

    from codec.encode import M3Encoder
    enc = M3Encoder()

    S = np.zeros((len(texts), 192), dtype=np.float32)
    for i in range(0, len(texts), args.chunk):
        batch = texts[i:i + args.chunk]
        vecs = enc.encode_tokens(batch)
        T = torch.zeros(len(batch), MAXLEN, 1024)
        M = torch.zeros(len(batch), MAXLEN, dtype=torch.bool)
        for j, v in enumerate(vecs):
            L = min(len(v), MAXLEN)
            T[j, :L] = torch.from_numpy(np.asarray(v[:L], dtype=np.float32))
            M[j, :L] = True
        with torch.no_grad():
            S[i:i + args.chunk] = pooler(T.to(dev), M.to(dev)).cpu().numpy()
        if (i // args.chunk) % 8 == 0:
            print(f"[s] {i + len(batch)}/{len(texts)}", flush=True)

    np.save(OUT, S)
    META.write_text(json.dumps({"fingerprint": fp, "n": len(texts),
                                "pooler_tag": args.pooler_tag}))
    print(f"[done] {OUT.name} {S.shape} (pooler {args.pooler_tag}, {fp})")


if __name__ == "__main__":
    main()
