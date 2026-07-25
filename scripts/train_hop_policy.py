"""C3 — train the hop policy (reasoner v0) against the D30 oracle floors.

Model: one small MLP applied per step (weight-tied recurrence; loop count =
hop count -> T4's instrument). Heads: relation (7) + HALT + ABSTAIN = 9-way.
Features per step: question gist, current-entry gist (zeros at step 0), B2
store readouts (id_cov, margin, top, step one-hot), and id-overlap stats.
Hand-off mask and walk knobs are oracle-default in v0 (closed action space).

Supervision: teacher-forced gold chains (world v3 labels, not oracle
success) — every hop case supervises its full relation sequence + HALT;
every no-answer query supervises ABSTAIN after the probe retrieval.

Eval (rungs 1-2): held-out ENTITIES for trained compositions; big_pop held
out ENTIRELY (composition generalization); end-to-end env walks vs floors:
single 0.743, cap_pop 0.756, ceo_born 0.375, loc_cap 0.140, loc_big 0.073,
3-hop 0.000, no-answer abstain 0.061.

Usage: .venv/bin/python scripts/train_hop_policy.py
"""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, torch
import torch.nn as nn
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from codec.hop_env import ABSTAIN, HALT, Action, HopEnv
from codec.memory_store import MemoryStore, fit_translation, id_tokens
from codec.structure_channel import hash_test_mask
from codec.role_bits import _nlp

def unit(X): return X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)

import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument("--world", default="closed_world_v3")
_ap.add_argument("--tag", default="v0")
ARGS = _ap.parse_args()
world = json.loads((ROOT / "data" / f"{ARGS.world}.json").read_text())
facts, queries, hops = world["facts"], world["queries"], world["hops"]
_cache = ROOT / "results" / f"{ARGS.world}_emb.npz"
if _cache.exists():
    z = np.load(_cache)
    Zf, Zq, Zh = z["Zf"], z["Zq"], z["Zh"]
else:
    from codec.encode import M3Encoder
    from codec import whiten as _W
    _enc = M3Encoder()
    _wh = _W.load(str(ROOT / "results" / "whiten_v0.npz"))
    def _emb(ts):
        d, _ = _enc.encode(ts, sparse=False)
        return unit(_W.apply(d, _wh))
    print(f"[encode] {len(facts)}+{len(queries)}+{len(hops)}", flush=True)
    Zf = _emb([f["text"] for f in facts])
    Zq = _emb([q["text"] for q in queries])
    Zh = _emb([h["text"] for h in hops])
    np.savez(_cache, Zf=Zf, Zq=Zq, Zh=Zh)
nlp = _nlp()
HELD = set(world["held_out_phrasings"])

def qids_of(text):
    doc = nlp(text)
    return id_tokens([t.text.rstrip("'s") if t.text.endswith("'s") else t.text
                      for t in doc if t.pos_ == "PROPN"]
                     + [t.text for t in doc if t.like_num])

store = MemoryStore()
for f, zf in zip(facts, Zf):
    store.add(zf, f["entities"] + f["numbers"], f["text"])
RELS = sorted({f["relation"] for f in facts})
N_ACT = len(RELS) + 2                   # + HALT + ABSTAIN
A_HALT, A_ABST = len(RELS), len(RELS) + 1
seen = [i for i, q in enumerate(queries) if q["kind"] == "single"
        and q["phrasing_idx"] not in HELD]
t_by_rel = {}
for rel in RELS:
    tr = [i for i in seen if queries[i]["relation"] == rel][:300]
    t_by_rel[rel] = fit_translation(
        Zq[tr], np.stack([Zf[queries[i]["fact_idx"]] for i in tr]))
env = HopEnv(store, RELS, t_by_rel)

def feats(obs):
    cz = obs.cur_z if obs.cur_z is not None else np.zeros(1024, np.float32)
    step1h = np.zeros(4, np.float32); step1h[min(obs.step, 3)] = 1
    ov = (len(obs.q_ids & obs.cur_ids) / max(len(obs.q_ids), 1)
          if obs.cur_ids else 0.0)
    return np.concatenate([obs.q_z, cz,
                           [obs.id_cov, obs.margin, obs.top_score, ov],
                           step1h]).astype(np.float32)

# ---------- teacher-forced dataset ----------
HOLDOUTS = set(world.get("holdout_compositions", ["big_pop"]))
X_rows, y_rows, tags = [], [], []
def add_case(q_z, q_ids, chain, tag, abstain=False):
    obs = env.reset(q_z, q_ids)
    for k, rel in enumerate(chain):
        X_rows.append(feats(obs)); tags.append(tag)
        y_rows.append(A_ABST if (abstain and k == 1) else
                      (RELS.index(rel) if k < len(chain) else A_HALT))
        a = Action(relation=RELS.index(rel) if k < len(chain) else HALT,
                   hand_ids=(obs.cur_ids or set()) - q_ids if k else set(),
                   demote_ids=q_ids if k else set(), exclude_visited=k > 0)
        obs, _ = env.step(a)
    X_rows.append(feats(obs)); tags.append(tag)
    y_rows.append(A_ABST if abstain else A_HALT)

hop_m = hash_test_mask([h["text"] for h in hops], frac=0.3)   # 30% test
for i, h in enumerate(hops):
    if h["kind"] in HOLDOUTS or hop_m[i]:
        continue
    add_case(Zh[i], qids_of(h["text"]), h["chain"], "hop")
sing_m = hash_test_mask([queries[i]["text"] for i in
                         [j for j, q in enumerate(queries) if q["kind"] == "single"]],
                        frac=0.3)
singles = [j for j, q in enumerate(queries) if q["kind"] == "single"]
for k, i in enumerate(singles):
    if sing_m[k]:
        continue
    add_case(Zq[i], qids_of(queries[i]["text"]), [queries[i]["relation"]], "single")
na = [j for j, q in enumerate(queries) if q["kind"] == "no_answer"]
na_m = hash_test_mask([queries[i]["text"] for i in na], frac=0.3)
for k, i in enumerate(na):
    if na_m[k]:
        continue
    add_case(Zq[i], qids_of(queries[i]["text"]), [queries[i]["relation"]],
             "no_answer", abstain=True)

X = torch.tensor(np.stack(X_rows)); y = torch.tensor(y_rows)
print(f"[data] {len(X)} steps ({dict((t, tags.count(t)) for t in set(tags))})",
      flush=True)

net = nn.Sequential(nn.Linear(X.shape[1], 512), nn.GELU(),
                    nn.Linear(512, 256), nn.GELU(), nn.Linear(256, N_ACT))
dev = "cuda" if torch.cuda.is_available() else "cpu"
net = net.to(dev); X = X.to(dev); y = y.to(dev)
# class weights: abstain/halt are rare relative to relation steps
w = torch.bincount(y, minlength=N_ACT).float()
w = (w.sum() / w.clamp(min=1)).clamp(max=20.0)
opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=0.01)
lossf = nn.CrossEntropyLoss(weight=w.to(dev))
for ep in range(60):
    perm = torch.randperm(len(X), device=dev)
    tot = 0.0
    for i in range(0, len(X), 512):
        b = perm[i:i + 512]
        loss = lossf(net(X[b]), y[b])
        opt.zero_grad(); loss.backward(); opt.step()
        tot += loss.item()
    if ep % 20 == 19:
        print(f"[train] ep{ep+1} loss={tot / (len(X) // 512 + 1):.4f}", flush=True)
n_params = sum(p.numel() for p in net.parameters())
torch.save(net.state_dict(), ROOT / "checkpoints" / f"hop_policy_{ARGS.tag}.pt")
print(f"[save] hop_policy_{ARGS.tag}.pt ({n_params:,} params)")

# ---------- end-to-end eval: policy drives the env ----------
@torch.no_grad()
def policy_walk(q_z, q_ids, max_steps=4):
    obs = env.reset(q_z, q_ids)
    for _ in range(max_steps + 1):
        a_idx = int(net(torch.tensor(feats(obs))[None].to(dev)).argmax())
        if a_idx == A_HALT:
            return env.cur, "halt"
        if a_idx == A_ABST:
            return None, "abstain"
        a = Action(relation=a_idx,
                   hand_ids=(obs.cur_ids or set()) - q_ids if obs.step else set(),
                   demote_ids=q_ids if obs.step else set(),
                   exclude_visited=obs.step > 0)
        obs, done = env.step(a)
        if done:
            return env.cur, "maxed"
    return env.cur, "maxed"

net.eval()
res = {}
floors = {"single": 0.743, "cap_pop": 0.756, "big_pop": 0.600,
          "ceo_born": 0.375, "loc_cap": 0.140, "loc_big": 0.073,
          "loc_cap_pop": 0.000, "no_answer": 0.061}
for kind in sorted({h["kind"] for h in hops}):
    cases = [(h, Zh[i]) for i, h in enumerate(hops) if h["kind"] == kind
             and (hop_m[i] or kind in HOLDOUTS)]
    hit = sum(policy_walk(zq, qids_of(h["text"]))[0] == h["answer_fact"]
              for h, zq in cases)
    res[kind] = hit / max(len(cases), 1)
    note = " [HELD-OUT COMPOSITION]" if kind in HOLDOUTS else ""
    print(f"[policy {kind:>12}] P@1 = {res[kind]:.3f} (n={len(cases)}, "
          f"oracle floor {floors.get(kind, float('nan'))}){note}", flush=True)
tests = [i for k, i in enumerate(singles) if sing_m[k]][:400]
hit = sum(policy_walk(Zq[i], qids_of(queries[i]["text"]))[0]
          == queries[i]["fact_idx"] for i in tests)
res["single"] = hit / len(tests)
print(f"[policy       single] P@1 = {res['single']:.3f} (n={len(tests)}, "
      f"floor 0.743)")
na_test = [i for k, i in enumerate(na) if na_m[k]]
ab = sum(policy_walk(Zq[i], qids_of(queries[i]["text"]))[1] == "abstain"
         for i in na_test)
fa = sum(policy_walk(Zq[i], qids_of(queries[i]["text"]))[1] == "abstain"
         for i in tests[:200])
res["no_answer_abstain"] = ab / len(na_test)
res["false_abstain"] = fa / 200
print(f"[policy    no_answer] abstain recall = {ab / len(na_test):.3f} "
      f"(floor 0.061) | false-abstain on answerable = {fa / 200:.3f}")

(ROOT / "results" / f"hop_policy_{ARGS.tag}.json").write_text(json.dumps(
    {"generated_at": datetime.now(timezone.utc).isoformat(),
     "n_params": n_params, "results": res, "floors": floors,
     "holdout_compositions": sorted(HOLDOUTS)}, indent=2))
print(f"[done] results/hop_policy_{ARGS.tag}.json")
