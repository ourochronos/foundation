"""J1 — the promotion/staleness demonstration (T6's first probe).

Crystallize 500 hot facts from world v4 into Qwen3-0.6B weights (plain-text
QA LoRA, gfx1201-safe config per H1: all-linear targets, no chat template,
adamw_torch, math SDPA). Then measure BOTH poles of the dial in one system:
  accuracy  crystallized (retrieval-free generation) vs externalized (store
            translation addressing + identity)
  latency   wall-clock per query, both paths
  STALENESS supersede 100 of the 500 in the store -> store answers update
            transparently (D25 machinery); crystallized copies keep
            answering the OLD object. Measure both rates.

Usage: .venv/bin/python scripts/probe_promotion.py
"""
from __future__ import annotations
import json, random, sys, time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, torch
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from codec import whiten as W
from codec.memory_store import MemoryStore, fit_translation, id_tokens
from codec.role_bits import _nlp

def unit(X): return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)

torch.backends.cuda.enable_flash_sdp(False)
torch.backends.cuda.enable_mem_efficient_sdp(False)

world = json.loads((ROOT / "data" / "closed_world_v4.json").read_text())
facts, queries = world["facts"], world["queries"]
z = np.load(ROOT / "results" / "closed_world_v4_emb.npz")
Zf, Zq = z["Zf"], z["Zq"]
nlp = _nlp()
rng = random.Random(3)
PHR = json.loads((ROOT / "data" / "query_phrasings_v3.json").read_text())
PHR["headquartered_in"] = ["Where is {X} headquartered?", "In which city is {X} based?",
    "Name the home city of {X}.", "What city hosts {X}'s head office?"]
PHR["mayor_of"] = ["Who is the mayor of {X}?", "Name {X}'s mayor.",
    "Who leads the city government of {X}?", "Who runs city hall in {X}?"]

# hot set: 500 capital facts (editable, single-object, phrasing-rich)
cap_facts = [i for i, f in enumerate(facts) if f["relation"] == "capital_of"
             and (f["year"] is None or f["year"] >= 2000)]
hot = rng.sample(cap_facts, 500)
train_rows = []
for fi in hot:
    f = facts[fi]
    for pi in rng.sample(range(8), 5):          # 5 phrasings each, 3 held for eval
        q = PHR["capital_of"][pi].format(X=f["subject"])
        train_rows.append((q, f["object"]))
rng.shuffle(train_rows)
print(f"[data] {len(train_rows)} QA pairs from 500 hot facts", flush=True)

from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-0.6B")
if tok.pad_token is None: tok.pad_token = tok.eos_token
lm = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3-0.6B", dtype=torch.bfloat16)
lm = get_peft_model(lm, LoraConfig(task_type="CAUSAL_LM", r=16, lora_alpha=32,
                                   lora_dropout=0.05, target_modules="all-linear"))
lm = lm.to("cuda"); lm.config.use_cache = False

def encode_batch(rows):
    texts = [f"Q: {q}\nA: {a}{tok.eos_token}" for q, a in rows]
    enc = tok(texts, padding=True, truncation=True, max_length=64,
              return_tensors="pt", add_special_tokens=False)
    labels = enc["input_ids"].clone()
    labels[enc["attention_mask"] == 0] = -100
    # mask the question part: everything before "A:" position approximated by
    # masking the first len(Q-part) tokens
    for i, (q, a) in enumerate(rows):
        qlen = len(tok(f"Q: {q}\nA:", add_special_tokens=False)["input_ids"])
        labels[i, :qlen] = -100
    return enc["input_ids"], enc["attention_mask"], labels

opt = torch.optim.AdamW([p for p in lm.parameters() if p.requires_grad], lr=2e-4)
lm.train()
for ep in range(3):
    rng.shuffle(train_rows)
    tot = n = 0
    for i in range(0, len(train_rows), 16):
        ids, attn, lab = encode_batch(train_rows[i:i+16])
        out = lm(input_ids=ids.to("cuda"), attention_mask=attn.to("cuda"),
                 labels=lab.to("cuda"))
        out.loss.backward(); opt.step(); opt.zero_grad(set_to_none=True)
        tot += out.loss.item(); n += 1
    print(f"[train] ep{ep+1} loss={tot/n:.4f}", flush=True)
lm.config.use_cache = True
lm.eval()

@torch.no_grad()
def crystal_answer(q):
    ids = tok(f"Q: {q}\nA:", return_tensors="pt", add_special_tokens=False)
    out = lm.generate(input_ids=ids["input_ids"].to("cuda"),
                      attention_mask=ids["attention_mask"].to("cuda"),
                      max_new_tokens=12, do_sample=False,
                      pad_token_id=tok.pad_token_id)
    return tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)

# store path setup
store = MemoryStore()
for f, zf in zip(facts, Zf): store.add(zf, f["entities"] + f["numbers"], f["text"])
HELD = set(world["held_out_phrasings"])
seen = [i for i, q in enumerate(queries) if q["kind"] == "single"
        and q["phrasing_idx"] not in HELD]
tr = [i for i in seen if queries[i]["relation"] == "capital_of"][:300]
t_cap = fit_translation(Zq[tr], np.stack([Zf[queries[i]["fact_idx"]] for i in tr]))
from codec.encode import M3Encoder
enc3 = M3Encoder()
wh = W.load(str(ROOT / "results" / "whiten_v0.npz"))
def store_answer(q):
    d, _ = enc3.encode([q], sparse=False)
    zq = unit(W.apply(d, wh))[0]
    ids = id_tokens([t.text.rstrip("'s") if t.text.endswith("'s") else t.text
                     for t in nlp(q) if t.pos_ == "PROPN"])
    r = store.query(zq + t_cap, ids, k=1, id_weight=0.5)[0]
    return r[2]

# eval on held phrasings (unseen by BOTH paths' training)
eval_set = [(PHR["capital_of"][8 + (k % 4)].format(X=facts[fi]["subject"]), fi)
            for k, fi in enumerate(hot[:300])]
t0 = time.time()
c_hits = sum(facts[fi]["object"].split()[0] in crystal_answer(q)
             for q, fi in eval_set)
t_c = (time.time() - t0) / len(eval_set)
t0 = time.time()
s_hits = sum(facts[fi]["object"].split()[0] in store_answer(q)
             for q, fi in eval_set)
t_s = (time.time() - t0) / len(eval_set)
print(f"[accuracy] crystallized={c_hits/len(eval_set):.3f} "
      f"store={s_hits/len(eval_set):.3f} (n={len(eval_set)}, unseen phrasings)")
print(f"[latency ] crystallized={t_c*1000:.0f}ms/q store={t_s*1000:.0f}ms/q")

# STALENESS: supersede 100 hot facts in the store
cities = sorted({f["object"] for f in facts if f["relation"] == "capital_of"})
edited = []
E_T = ["The capital of {c} was moved to {n}.", "{n} became the new capital of {c}."]
etexts = []
for fi in hot[:100]:
    f = facts[fi]
    new = rng.choice([x for x in cities if x != f["object"]])
    edited.append((fi, f["subject"], f["object"], new))
    etexts.append(rng.choice(E_T).format(c=f["subject"], n=new))
d, _ = enc3.encode(etexts, sparse=False)
Ze = unit(W.apply(d, wh))
for (fi, c, old, new), zv, txt in zip(edited, Ze, etexts):
    top = store.query(zv, id_tokens([c, new]), k=1, id_weight=0.5)[0]
    ni = store.add(zv, [c, new], txt)
    if top[1] >= 0.88:
        store.supersede(top[0], ni)
post_q = [(PHR["capital_of"][8 + (k % 4)].format(X=c), old, new)
          for k, (fi, c, old, new) in enumerate(edited)]
s_new = sum(new.split()[0] in store_answer(q) for q, old, new in post_q)
c_stale = sum(old.split()[0] in crystal_answer(q) for q, old, new in post_q)
c_new = sum(new.split()[0] in crystal_answer(q) for q, old, new in post_q)
print(f"[staleness after 100 edits] store answers NEW: {s_new/100:.2f} | "
      f"crystallized answers OLD (stale): {c_stale/100:.2f}, NEW: {c_new/100:.2f}")

(ROOT / "results" / "promotion_j1.json").write_text(json.dumps(
    {"generated_at": datetime.now(timezone.utc).isoformat(),
     "crystal_acc": c_hits/len(eval_set), "store_acc": s_hits/len(eval_set),
     "crystal_ms": t_c*1000, "store_ms": t_s*1000,
     "store_new_after_edit": s_new/100, "crystal_stale": c_stale/100,
     "crystal_new": c_new/100}, indent=2))
print("[done] results/promotion_j1.json")
