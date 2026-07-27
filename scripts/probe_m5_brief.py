"""M5 / G4 — grounded synthesis gate (docs/07 R5; 10-poc-plan G4).

REGISTERED TARGETS (unchanged): entailment-judged faithfulness >= 0.9
(n=50); distractor-subgraph unsupported-claim refusal >= 0.8; planted
disputes surfaced via views >= 0.8.

PROTOCOL (pre-registered, committed BEFORE scoring — D64):
- Store layer: pid-bearing statements from data/wiki/shards_final (the
  G2-passed corpus), sid = "file:line". Renderer: codec/brief.py
  (templates + citations, D76 — decoder out of the loop).
- Subjects: the 15 richest bio subjects (>= 20 pid-entries).
- FAITHFULNESS: pool all kind=fact sentences over the 15 briefs; seed-7
  sample of 50; two Haiku judges (25 each) grade ENTAILED/NOT_ENTAILED of
  the rendered sentence against the cited entry's STATEMENT TEXT — the
  stored evidence, NOT the triple (the triple is the rendering input;
  judging against it would be circular). Labels frozen to
  data/m5_faithfulness_labels.jsonl before scoring. Gate: >= 45/50.
- DISTRACTOR (n=25): (subject, aspect-pid) pairs where the subject has NO
  entry with that pid; pool = subject's own entries + 4 same-pid entries
  from OTHER subjects. Refusal = abstain AND zero sentences citing
  distractor sids. Gate: >= 20/25. (The renderer self-filters a mixed
  pool — the invariant is tested, not assumed.)
- DISPUTES (n=25): subjects holding a functional-pid entry (D78 set) get
  a planted counter-claim (year+3 for dates, another subject's value
  otherwise; page="planted:src2"). Surfaced = the brief emits a
  kind=dispute sentence for that pid citing BOTH the original and the
  planted sid. Gate: >= 20/25.
- Deterministic clauses run at commit; faithfulness scored when the
  frozen judge labels land. Artifact: results/m5_brief.json.

ROUND 2 (pre-registered with the renderer amendment, D81): round-1
faithfulness 0.840 (42/50) — 6/8 failures were store-entry defects
surfacing downstream, 2/8 template over-strength. Renderer gains
verb-echo (render at evidence strength) + per-entry guards (quote-like
objects, subjectless statements → withheld). Round 2 = FRESH sample,
seed 8, fresh judges, labels frozen to
data/m5_faithfulness_labels_r2.jsonl. Round-1 artifacts kept.

Usage: .venv/bin/python scripts/probe_m5_brief.py [score]
  (no arg: render briefs + deterministic gates + judge shards;
   "score": apply frozen labels and finalize)
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codec.brief import FUNCTIONAL_PIDS, subject_brief  # noqa: E402
from codec.manifest import run_manifest, wilson_ci      # noqa: E402

ROUND = 2
rng = random.Random(8 if ROUND == 2 else 7)
SFX = "_r2" if ROUND == 2 else ""

entries = []
for f in sorted((ROOT / "data/wiki/shards_final").glob("out_*.jsonl")):
    for ln, line in enumerate(f.read_text().splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("pid") and d.get("subject") and d.get("object") \
                and d.get("statement"):
            entries.append({"subject": str(d["subject"]),
                            "pid": d["pid"], "object": str(d["object"]),
                            "statement": str(d["statement"]),
                            "page": d.get("page", "?"),
                            "sid": f"{f.name}:{ln}"})
by_subj = defaultdict(list)
for e in entries:
    by_subj[e["subject"]].append(e)
rich = sorted(by_subj, key=lambda s: -len(by_subj[s]))[:15]
print(f"[m5] {len(entries)} pid-entries; subjects: {rich}", flush=True)

briefs = {s: subject_brief(s, by_subj[s]) for s in rich}
facts = [(s, i, sen) for s in rich
         for i, sen in enumerate(briefs[s]["sentences"])
         if sen["kind"] == "fact"]
print(f"[m5] {sum(len(b['sentences']) for b in briefs.values())} sentences "
      f"({len(facts)} fact-kind) over {len(rich)} briefs", flush=True)

# ---- faithfulness judge set (n=50, seed 7) ---------------------------------
sample = rng.sample(facts, 50)
sid_map = {e["sid"]: e for e in entries}
judge_items = []
for k, (s, i, sen) in enumerate(sample):
    src = sid_map[sen["citations"][0]]
    judge_items.append({"idx": k, "subject": s,
                        "rendered": sen["text"],
                        "source_statement": src["statement"],
                        "source_page": src["page"]})
J = ROOT / "data" / "m5_judge"
J.mkdir(exist_ok=True)
for half in (0, 1):
    (J / f"in{SFX}_{half}.json").write_text(json.dumps(
        judge_items[half * 25:(half + 1) * 25], indent=1))

# ---- distractor control (n=25, deterministic) ------------------------------
all_pids = sorted({e["pid"] for e in entries})
cases, hits = [], 0
pool_by_pid = defaultdict(list)
for e in entries:
    pool_by_pid[e["pid"]].append(e)
cand = [(s, p) for s in rich for p in all_pids
        if not any(e["pid"] == p for e in by_subj[s])
        and len([x for x in pool_by_pid[p]
                 if x["subject"] != s]) >= 4]
rng.shuffle(cand)
for s, p in cand[:25]:
    distract = rng.sample([x for x in pool_by_pid[p]
                           if x["subject"] != s], 4)
    b = subject_brief(s, by_subj[s] + distract, aspect=p)
    d_sids = {x["sid"] for x in distract}
    leaked = [sen for sen in b["sentences"]
              if set(sen["citations"]) & d_sids]
    ok = b["abstain"] and not leaked
    hits += ok
    cases.append({"subject": s, "aspect": p, "refused": bool(b["abstain"]),
                  "leaked": len(leaked), "ok": bool(ok)})
distr = {"n": len(cases), "ok": hits, "rate": hits / max(len(cases), 1),
         "ci95": wilson_ci(hits, max(len(cases), 1))}
print(f"[m5] distractor refusal: {hits}/{len(cases)} = {distr['rate']:.3f} "
      f"[gate >=0.8]", flush=True)

# ---- planted disputes (n=25, deterministic) --------------------------------
fsubj = [(s, e) for s in by_subj for e in by_subj[s]
         if e["pid"] in FUNCTIONAL_PIDS]
rng.shuffle(fsubj)
seen, planted, surfaced = set(), [], 0
for s, e in fsubj:
    if len(planted) >= 25 or (s, e["pid"]) in seen:
        continue
    seen.add((s, e["pid"]))
    if re.search(r"\d{3,4}", e["object"]):
        counter = re.sub(r"(\d{3,4})",
                         lambda m: str(int(m.group(1)) + 3),
                         e["object"], count=1)
    else:
        others = [x["object"] for x in pool_by_pid[e["pid"]]
                  if x["subject"] != s
                  and x["object"].lower() != e["object"].lower()]
        if not others:
            continue
        counter = rng.choice(others)
    plant = {"subject": s, "pid": e["pid"], "object": counter,
             "statement": f"[planted] {s} {e['pid']}: {counter}",
             "page": "planted:src2", "sid": f"planted:{len(planted)}"}
    b = subject_brief(s, by_subj[s] + [plant])
    disp = [sen for sen in b["sentences"]
            if sen["kind"] == "dispute" and sen["pid"] == e["pid"]
            and plant["sid"] in sen["citations"]
            and any(c != plant["sid"] for c in sen["citations"])]
    ok = bool(disp)
    surfaced += ok
    planted.append({"subject": s, "pid": e["pid"], "orig": e["object"],
                    "counter": counter, "surfaced": ok})
disp = {"n": len(planted), "ok": surfaced,
        "rate": surfaced / max(len(planted), 1),
        "ci95": wilson_ci(surfaced, max(len(planted), 1))}
print(f"[m5] dispute surfacing: {surfaced}/{len(planted)} = "
      f"{disp['rate']:.3f} [gate >=0.8]", flush=True)

out = {"round": ROUND, "subjects": rich,
       "n_sentences": sum(len(b["sentences"]) for b in briefs.values()),
       "n_withheld": sum(len(b.get("withheld", []))
                         for b in briefs.values()),
       "distractor": distr, "disputes": disp,
       "faithfulness": None,
       "manifest": run_manifest(seed=8 if ROUND == 2 else 7)}

# ---- faithfulness scoring (after frozen labels land) ------------------------
LBL = ROOT / "data" / f"m5_faithfulness_labels{SFX}.jsonl"
if len(sys.argv) > 1 and sys.argv[1] == "score":
    labels = {}
    for line in LBL.read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            labels[int(d["idx"])] = d["verdict"].strip().upper()
    ok = sum(1 for k in range(50) if labels.get(k) == "ENTAILED")
    out["faithfulness"] = {"n": 50, "entailed": ok, "rate": ok / 50,
                           "ci95": wilson_ci(ok, 50),
                           "labels_file": str(LBL.relative_to(ROOT))}
    print(f"[m5] faithfulness: {ok}/50 = {ok/50:.3f} [gate >=0.9]",
          flush=True)
    g = (out["faithfulness"]["rate"] >= 0.9, distr["rate"] >= 0.8,
         disp["rate"] >= 0.8)
    out["verdict"] = "PASS" if all(g) else "FAIL"
    print(f"[m5] G4 VERDICT: {out['verdict']} "
          f"(faith {g[0]}, distractor {g[1]}, disputes {g[2]})", flush=True)

json.dump(out, open(ROOT / "results" / "m5_brief.json", "w"), indent=1)
json.dump({s: briefs[s] for s in rich},
          open(ROOT / "data" / "m5_briefs.json", "w"), indent=1)
print("[done] results/m5_brief.json", flush=True)
