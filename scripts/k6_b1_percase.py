"""B1 per-case: Qwen3-0.6B reads the ENTIRE per-case store (strongest
baseline form — no retrieval loss at all) and answers the multi-hop
question. Formal both-settings comparison for docs/09.

Usage: .venv/bin/python scripts/k6_b1_percase.py
"""
from __future__ import annotations
import json, sys, time
from collections import Counter
from pathlib import Path
import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
__file__str = str(ROOT / "scripts" / "k6_percase_clean.py")
src = (ROOT / "scripts" / "k6_percase_clean.py").read_text()
head = src.split("variants = [")[0].replace(
    'ROOT = Path(__file__).resolve().parent.parent', f'ROOT = Path("{ROOT}")')
exec(head)  # noqa: S102
from codec.manifest import run_manifest, wilson_ci  # noqa: E402

from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: E402
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-0.6B")
lm = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3-0.6B", dtype=torch.bfloat16, device_map="cuda")
lm.eval()

def read_answer(question, ctx):
    prompt = ("Facts:\n" + "\n".join(f"- {c}" for c in ctx)
              + f"\nQuestion: {question}\nAnswer:")
    ids = tok(prompt, return_tensors="pt").to("cuda")
    with torch.no_grad():
        out = lm.generate(**ids, max_new_tokens=16, do_sample=False,
                          pad_token_id=tok.eos_token_id)
    return tok.decode(out[0][ids["input_ids"].shape[1]:],
                      skip_special_tokens=True).strip().split("\n")[0]

hitk, nk = Counter(), Counter()
t_all = n_all = 0
for c in test_cases:
    st_rows = []
    tl, tr_ = c["orig"]["triples_labeled"], c["orig"]["triples"]
    bad = False
    for (sl, rl, ol), t in zip(tl, tr_):
        if (sl, t[1], ol) not in fact_key: bad = True; break
        st_rows.append((sl, rl, ol))
    if bad: continue
    ek = {tuple(t) for t in c["orig"]["edit_triples"]}
    for (sl, rl, ol), t in zip(c["orig"]["new_triples_labeled"],
                               c["orig"]["new_triples"]):
        if tuple(t) not in ek and (sl, t[1], ol) in fact_key:
            st_rows.append((sl, rl, ol))
    texts = {}
    for sl, rl, ol in st_rows:
        texts[(sl, rl)] = f"{sl} — {rl}: {ol}."
    for rw in c["requested_rewrite"]:
        key = (rw["subject"], rw["relation_id"], rw["target_true"]["str"])
        if key in fact_key:
            texts[(rw["subject"], rw["relation_id"])] = \
                (f"{rw['prompt'].format(rw['subject'])} "
                 f"{rw['target_new']['str']}.")
    row = hop_rows.get((c["case_id"], 0))
    if row is None: continue
    i, h = row
    golds = {c["new_answer"].lower()} | {a.lower() for a in
                                         c.get("new_answer_alias", [])}
    t0 = time.perf_counter()
    pred = read_answer(h["text"], list(texts.values())).lower()
    t_all += time.perf_counter() - t0; n_all += 1
    nh = len(tl); nk[nh] += 1
    hitk[nh] += any(g in pred or (pred in g and len(pred) > 2)
                    for g in golds if len(g) > 2)
res = {}
for nh in sorted(nk):
    res[f"{nh}hop"] = {"p1": hitk[nh]/nk[nh], "n": nk[nh],
                       "p1_ci95": wilson_ci(hitk[nh], nk[nh])}
    print(f"[b1-percase {nh}hop] P@1={hitk[nh]/nk[nh]:.3f} (n={nk[nh]})",
          flush=True)
tot = sum(hitk.values())/sum(nk.values())
print(f"[b1-percase all] P@1={tot:.3f} | {1000*t_all/n_all:.0f} ms/q",
      flush=True)
(ROOT/"results"/"k6_b1_percase.json").write_text(json.dumps(
    {"results": res, "overall": tot, "ms_per_question": 1000*t_all/n_all,
     "note": "reader sees the ENTIRE per-case store (no retrieval loss)",
     "manifest": run_manifest(seed=0)}, indent=2))
print("[done] results/k6_b1_percase.json", flush=True)
