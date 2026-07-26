"""K6 B1 — matched-scale baseline (docs/09): same BGE-M3 embeddings, same
post-edit pooled store, retrieval (dense+id, top-5 live facts) -> local
Qwen3-0.6B reads and answers. Isolates the architecture (operators/typed
planning/supersession-addressing) from capacity: same encoder, same
parameter scale as our decoder.

Usage: .venv/bin/python scripts/k6_b1_baseline.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from codec.manifest import run_manifest, wilson_ci                # noqa: E402
from codec.memory_store import MemoryStore, id_tokens             # noqa: E402
import v06_pipeline as P                                          # noqa: E402

w = json.loads((ROOT / "data" / "mquake" / "world_cf3k.json").read_text())
facts, hops = w["facts"], w["hops"]
cases = json.loads((ROOT / "data" / "mquake" /
                    "MQuAKE-CF-3k.json").read_text())
case_by_id = {c["case_id"]: c for c in cases}
z = np.load(ROOT / "results" / "mquake_cf3k_emb_v2.npz")
Zf, Zh = z["Zf"], z["Zh"]
ez = np.load(ROOT / "results" / "k6_edit_emb.npz")
Zn = ez["Zn"]

store = MemoryStore()
for f, zf in zip(facts, Zf):
    store.add(zf, f["entities"], f["text"])
fact_key = {(f["subject"], f["relation"], f["object"]): i
            for i, f in enumerate(facts)}
test_ids = set()
edit_texts = []
k = 0
for c in cases:
    if c["case_id"] in set(w["train_case_ids"]):
        continue
    test_ids.add(c["case_id"])
    for rw in c["requested_rewrite"]:
        key = (rw["subject"], rw["relation_id"], rw["target_true"]["str"])
        if key not in fact_key:
            continue
        txt = (f"{rw['prompt'].format(rw['subject'])} "
               f"{rw['target_new']['str']}.")
        ni = store.add(Zn[k], [rw["subject"], rw["target_new"]["str"]], txt)
        store.supersede(fact_key[key], ni)
        k += 1
print(f"[b1] store ready: {k} edits applied", flush=True)

from transformers import AutoModelForCausalLM, AutoTokenizer      # noqa: E402
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-0.6B")
lm = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3-0.6B", torch_dtype=torch.bfloat16, device_map="cuda")
lm.eval()


def read_answer(question: str, ctx: list[str]) -> str:
    prompt = ("Facts:\n" + "\n".join(f"- {c}" for c in ctx)
              + f"\nQuestion: {question}\nAnswer:")
    ids = tok(prompt, return_tensors="pt").to("cuda")
    with torch.no_grad():
        out = lm.generate(**ids, max_new_tokens=16, do_sample=False,
                          pad_token_id=tok.eos_token_id)
    return tok.decode(out[0][ids["input_ids"].shape[1]:],
                      skip_special_tokens=True).strip().split("\n")[0]


res, t_all, n_all = {}, 0.0, 0
for nh in ("2hop", "3hop", "4hop"):
    rows = [(h, Zh[i]) for i, h in enumerate(hops)
            if not h["train"] and h["kind"] == nh and h["phrasing"] == 0]
    hit = 0
    for h, zq in rows:
        c = case_by_id[h["case_id"]]
        golds = {c["new_answer"].lower()} \
            | {a.lower() for a in c.get("new_answer_alias", [])}
        t0 = time.perf_counter()
        top = store.query(zq, id_tokens([h["subject"]]), k=5, id_weight=0.5)
        ctx = [store.texts[i] for i, _s, _t in top]
        pred = read_answer(h["text"], ctx).lower()
        t_all += time.perf_counter() - t0
        n_all += 1
        hit += any(g in pred or pred in g for g in golds if len(g) > 2)
    res[nh] = {"p1": hit / len(rows), "n": len(rows),
               "p1_ci95": wilson_ci(hit, len(rows))}
    print(f"[b1-POST {nh}] P@1={hit/len(rows):.3f} (n={len(rows)})",
          flush=True)
m = sum(res[k]["p1"] * res[k]["n"] for k in res) / sum(res[k]["n"]
                                                       for k in res)
print(f"[b1-POST all] P@1={m:.3f} | {1000*t_all/n_all:.0f} ms/question",
      flush=True)
out = ROOT / "results" / "k6_b1_baseline.json"
out.write_text(json.dumps(
    {"post_edit": res, "overall_p1": m,
     "ms_per_question": 1000 * t_all / n_all,
     "reader": "Qwen3-0.6B, top-5 facts, greedy",
     "manifest": run_manifest(seed=0)}, indent=2))
print(f"[done] {out.relative_to(ROOT)}")
